"""Ligne de commande de Pharmaflux.

``collecte`` : un passage d'archivage (télécharger, comparer, archiver,
consigner). ``etat`` : ce que contient l'archive, d'après le manifeste.
``profil`` : une archive contre son contrat de schéma, anomalies et mesures.
``questions verifier`` : le jeu de questions de référence rejoué sur l'archive.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version as version_du_paquet
from pathlib import Path
from typing import Annotated, TextIO

import httpx
import typer

from pharmaflux import bronze
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.catalogue import CATALOGUE, Entree, IdentifiantInconnu, par_identifiant
from pharmaflux.collecte.etat import calculer_etat, formater_etat
from pharmaflux.collecte.passage import executer_passage, maintenant_utc
from pharmaflux.collecte.telechargement import Telechargeur
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.contrats.modele import Contrat
from pharmaflux.contrats.profil import ArchiveIntrouvable, profiler_racine
from pharmaflux.contrats.rendu import rendre_markdown, resume
from pharmaflux.evaluation import questions as jeu_questions
from pharmaflux.evaluation.verification import formater_bilan, verifier_jeu

VARIABLE_RACINE = "PHARMAFLUX_DATA"
QUESTIONS_PAR_DEFAUT = Path("evaluation/questions-reference-v0.toml")
RACINE_PAR_DEFAUT = Path.home() / "pharmaflux-data"

# Remplacé par les tests pour simuler le serveur ; None = vrai réseau.
fabriquer_transport: Callable[[], httpx.BaseTransport | None] = lambda: None  # noqa: E731

application = typer.Typer(
    name="pharmaflux",
    help="Pharmaflux : archivage et connaissance du médicament, sur données publiques.",
    no_args_is_help=True,
    add_completion=False,
)

OptionRacine = Annotated[
    Path | None,
    typer.Option(
        "--racine",
        help=f"Racine de l'archive. Défaut : {VARIABLE_RACINE}, sinon ~/pharmaflux-data.",
    ),
]


class FormateurUTC(logging.Formatter):
    """Horodatages du journal en UTC (``2026-10-24T14:17:03Z``), comme le manifeste."""

    def formatTime(  # noqa: N802 (nom imposé par logging)
        self, record: logging.LogRecord, datefmt: str | None = None
    ) -> str:
        return datetime.fromtimestamp(record.created, UTC).strftime(datefmt or "%Y-%m-%dT%H:%M:%SZ")


def configurer_journal(flux: TextIO = sys.stdout) -> None:
    """Le journal du collecteur sur ``flux`` (journald via stdout sous systemd), en UTC."""
    gestionnaire = logging.StreamHandler(flux)
    gestionnaire.setFormatter(FormateurUTC("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[gestionnaire])


def _afficher_version(demandee: bool) -> None:
    if demandee:
        typer.echo(f"pharmaflux {version_du_paquet('pharmaflux')}")
        raise typer.Exit()


@application.callback()
def principal(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Affiche la version et quitte.",
            callback=_afficher_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Pharmaflux : archivage et connaissance du médicament, sur données publiques."""


@application.command()
def collecte(
    source: Annotated[
        list[str] | None,
        typer.Option(
            "--source",
            help="Identifiant d'une entrée du catalogue (répétable). Toutes par défaut.",
        ),
    ] = None,
    racine: OptionRacine = None,
) -> None:
    """Un passage de collecte : télécharge, archive, consigne dans le manifeste."""
    configurer_journal()
    entrees = _entrees(source)
    with Telechargeur(transport=fabriquer_transport()) as telechargeur:
        bilan = executer_passage(_racine(racine), entrees, telechargeur)
    typer.echo(bilan.resume())
    raise typer.Exit(code=bilan.code_sortie)


@application.command()
def etat(racine: OptionRacine = None) -> None:
    """État de l'archive : dernière archive, dernier changement, erreurs, passages des 24 h."""
    chemin = _racine(racine)
    # Le manifeste est parcouru en flux : la mémoire ne dépend pas de son âge.
    etat_archive = calculer_etat(manifeste.parcourir(chemin), maintenant_utc())
    if not etat_archive.nombre_enregistrements:
        typer.echo(f"aucun passage dans {chemin} ({manifeste.chemin_manifeste(chemin)} absent).")
        return
    typer.echo(f"racine : {chemin}")
    typer.echo(
        f"{etat_archive.nombre_enregistrements} lignes de manifeste ; "
        f"dernier passage : {etat_archive.dernier_passage}"
    )
    typer.echo("")
    typer.echo(formater_etat(etat_archive.lignes))
    typer.echo("")
    typer.echo(_rapport_partiels(chemin))


def _rapport_partiels(chemin: Path) -> str:
    """Les fichiers temporaires laissés sous ``bronze/`` (passage tué net), ou rien."""
    partiels = bronze.fichiers_partiels(chemin)
    if not partiels:
        return "aucun fichier partiel dans bronze/."
    lignes = [
        f"{len(partiels)} fichier(s) partiel(s) dans bronze/ "
        "(passage en cours, ou écriture interrompue : à vérifier avant de supprimer) :"
    ]
    for partiel in partiels:
        modifie = datetime.fromtimestamp(partiel.stat().st_mtime, UTC).strftime("%Y-%m-%d %H:%MZ")
        lignes.append(f"  {partiel.relative_to(chemin).as_posix()}  (modifié le {modifie})")
    return "\n".join(lignes)


@application.command()
def profil(
    fichier: Annotated[
        list[str] | None,
        typer.Option(
            "--fichier",
            help="Identifiant (bdpm.specialites) ou nom de fichier (CIS_bdpm.txt), répétable."
            " Les onze fichiers TSV par défaut.",
        ),
    ] = None,
    racine: OptionRacine = None,
    archive: Annotated[
        Path | None,
        typer.Option(
            "--archive",
            help="Une archive précise (chemin absolu ou relatif à la racine) à la place de la"
            " dernière ; avec un seul --fichier, ou déduit du chemin.",
        ),
    ] = None,
    markdown: Annotated[
        Path | None,
        typer.Option(
            "--markdown", help="Écrit un fichier <identifiant>.md par source dans ce dossier."
        ),
    ] = None,
) -> None:
    """Profil d'archives contre leur contrat : conformité, clé, colonnes, dates, liens.

    Code de sortie 1 si une anomalie bloquante est trouvée (encodage, fin de
    ligne, nombre de colonnes, clé déclarée unique non unique).
    """
    chemin = _racine(racine)
    contrats = charger_tous()
    selection = _selection_contrats(fichier, archive, contrats)
    try:
        profils = profiler_racine(chemin, contrats, selection, archive)
    except (ArchiveIntrouvable, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--archive") from exc
    instant = maintenant_utc()
    if markdown is not None:
        markdown.mkdir(parents=True, exist_ok=True)
        for profil_ in profils:
            cible = markdown / f"{profil_.contrat.identifiant}.md"
            cible.write_text(rendre_markdown(profil_, instant), encoding="utf-8")
            typer.echo(f"{resume(profil_)}  → {cible}")
    else:
        for profil_ in profils:
            typer.echo(rendre_markdown(profil_, instant))
    bloquantes = sum(profil_.nombre_bloquantes for profil_ in profils)
    typer.echo(f"{len(profils)} fichier(s) profilé(s), {bloquantes} anomalie(s) bloquante(s).")
    raise typer.Exit(code=1 if bloquantes else 0)


def _selection_contrats(
    fichiers: list[str] | None, archive: Path | None, contrats: dict[str, Contrat]
) -> list[str]:
    """Les identifiants demandés, par identifiant ou nom de fichier ; déduits de l'archive sinon."""
    par_fichier = {contrat.fichier: identifiant for identifiant, contrat in contrats.items()}
    if not fichiers:
        if archive is None:
            return list(contrats)
        # bronze/<source>/<fichier>/<jour>/<archive> : le fichier est l'avant-avant-dernier dossier.
        nom = archive.parent.parent.name
        if nom not in par_fichier:
            raise typer.BadParameter(
                f"fichier non déduit de {archive} ; précise --fichier", param_hint="--archive"
            )
        return [par_fichier[nom]]
    selection = []
    for demande in fichiers:
        identifiant = demande if demande in contrats else par_fichier.get(demande)
        if identifiant is None:
            connus = ", ".join(sorted(par_fichier))
            raise typer.BadParameter(
                f"{demande} inconnu ; fichiers : {connus}", param_hint="--fichier"
            )
        selection.append(identifiant)
    if archive is not None and len(selection) != 1:
        raise typer.BadParameter("--archive demande un seul --fichier", param_hint="--archive")
    return selection


questions = typer.Typer(
    name="questions",
    help="Jeu de questions de référence (PRD annexe B) : rejeu sur l'archive.",
    no_args_is_help=True,
)
application.add_typer(questions)


@questions.command("verifier")
def questions_verifier(
    racine: OptionRacine = None,
    fichier_questions: Annotated[
        Path,
        typer.Option(
            "--questions",
            help="Le jeu de questions TOML.",
            show_default=True,
        ),
    ] = QUESTIONS_PAR_DEFAUT,
) -> None:
    """Rejoue chaque question : archive citée relue, sha256 vérifié, valeur recalculée.

    Code de sortie 1 au moindre écart, archive introuvable, sha256 différent
    ou archive non conforme à son contrat.
    """
    contrats = charger_tous()
    try:
        jeu = jeu_questions.charger(fichier_questions, contrats)
    except jeu_questions.JeuInvalide as exc:
        raise typer.BadParameter(str(exc), param_hint="--questions") from exc
    bilan = verifier_jeu(jeu, _racine(racine), contrats)
    typer.echo(formater_bilan(bilan))
    raise typer.Exit(code=bilan.code_sortie)


@application.command()
def catalogue() -> None:
    """Les entrées du catalogue : identifiant, cadence, mode d'empreinte, URL."""
    for entree in CATALOGUE:
        typer.echo(
            f"{entree.identifiant:28} {entree.cadence:15} {entree.empreinte:22} {entree.url}"
        )


def _entrees(identifiants: list[str] | None) -> list[Entree]:
    if not identifiants:
        return list(CATALOGUE)
    try:
        return par_identifiant(identifiants)
    except IdentifiantInconnu as exc:
        raise typer.BadParameter(str(exc), param_hint="--source") from exc


def _racine(racine: Path | None) -> Path:
    if racine is not None:
        return racine
    variable = os.environ.get(VARIABLE_RACINE)
    return Path(variable) if variable else RACINE_PAR_DEFAUT
