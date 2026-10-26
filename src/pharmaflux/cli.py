"""Ligne de commande de Pharmaflux.

``collecte`` : un passage d'archivage (télécharger, comparer, archiver,
consigner). ``etat`` : ce que contient l'archive, d'après le manifeste.
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

VARIABLE_RACINE = "PHARMAFLUX_DATA"
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
