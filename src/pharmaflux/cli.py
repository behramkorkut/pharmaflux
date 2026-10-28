"""Ligne de commande de Pharmaflux.

``collecte`` : un passage d'archivage (télécharger, comparer, archiver,
consigner). ``etat`` : ce que contient l'archive, d'après le manifeste.
``profil`` : une archive contre son contrat de schéma, anomalies et mesures.
``questions verifier`` : le jeu de questions de référence rejoué sur l'archive.
``evenements`` : du bronze aux événements, rejeu complet ou reprise.
``publier`` : les fichiers d'événements sur le bus. ``verifier-bus`` : les
topics relus, dédoublonnés, appliqués et comparés à la référence. ``schemas
enregistrer`` : les schémas du dépôt dans le registre de Redpanda. ``suivre`` :
les événements publiés, au fil de l'eau, une ligne par message. ``demo
fabriquer`` / ``demo verifier`` : le jeu de démo figé ``demo/archive`` ;
``demo rejouer`` : le jeu rejoué sur le bus, dans l'ordre global des
observations, à la cadence accélérée. ``silver construire`` / ``etat`` /
``sql`` / ``comparer`` / ``verifier`` / ``consommer`` : le silver Iceberg
(mission 05), dont les bibliothèques ne s'importent que dans ces commandes.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version as version_du_paquet
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, TextIO

import httpx
import typer

from pharmaflux import bronze
from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import publication, suivi, verification
from pharmaflux.bus.client import (
    COURTIER_PAR_DEFAUT,
    VARIABLE_COURTIER,
    Bus,
    BusKafka,
    CourtierInjoignable,
    Lecteur,
    LecteurKafka,
)
from pharmaflux.bus.registre import (
    REGISTRE_PAR_DEFAUT,
    VARIABLE_REGISTRE,
    Registre,
    RegistreIndisponible,
    SchemaIncompatible,
    enregistrer_tout,
)
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.catalogue import CATALOGUE, Entree, IdentifiantInconnu, par_identifiant
from pharmaflux.collecte.etat import calculer_etat, formater_etat
from pharmaflux.collecte.passage import executer_passage, maintenant_utc
from pharmaflux.collecte.telechargement import Telechargeur
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.contrats.modele import Contrat
from pharmaflux.contrats.profil import ArchiveIntrouvable, profiler_racine
from pharmaflux.contrats.rendu import rendre_markdown, resume
from pharmaflux.demo import jeu, rejeu_accelere
from pharmaflux.evaluation import questions as jeu_questions
from pharmaflux.evaluation.verification import formater_bilan, verifier_jeu
from pharmaflux.evenements import rejeu
from pharmaflux.silver import ENTREPOT_PAR_DEFAUT, LOT_PAR_DEFAUT, Format, SilverRefuse

if TYPE_CHECKING:  # le silver ne s'importe que dans ses commandes (K.1)
    from pharmaflux.silver.consommation import LecteurSilver

VARIABLE_RACINE = "PHARMAFLUX_DATA"
QUESTIONS_PAR_DEFAUT = Path("evaluation/questions-reference-v0.toml")
SORTIE_PAR_DEFAUT = Path("data/evenements")  # ignoré par git ; jamais sous la racine de l'archive
RACINE_PAR_DEFAUT = Path.home() / "pharmaflux-data"

# Remplacés par les tests pour simuler le serveur des sources, le courtier et le registre de
# schémas ; None = le vrai réseau, le vrai Redpanda.
fabriquer_transport: Callable[[], httpx.BaseTransport | None] = lambda: None  # noqa: E731
fabriquer_bus: Callable[[str], Bus | None] = lambda _courtier: None  # noqa: E731
fabriquer_lecteur: Callable[[str], Lecteur | None] = lambda _courtier: None  # noqa: E731
fabriquer_suiveur: Callable[[str], suivi.Suiveur | None] = lambda _courtier: None  # noqa: E731
fabriquer_transport_registre: Callable[[], httpx.BaseTransport | None] = (  # noqa: E731
    lambda: None
)
fabriquer_lecteur_silver: Callable[[str], LecteurSilver | None] = lambda _courtier: None  # noqa: E731

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
OptionCourtier = Annotated[
    str | None,
    typer.Option(
        "--courtier",
        help=f"Adresse du courtier. Défaut : {VARIABLE_COURTIER}, sinon {COURTIER_PAR_DEFAUT}.",
    ),
]
OptionRegistre = Annotated[
    str | None,
    typer.Option(
        "--registre",
        help=f"URL du registre de schémas. Défaut : {VARIABLE_REGISTRE},"
        f" sinon {REGISTRE_PAR_DEFAUT}.",
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


@application.command()
def evenements(
    fichier: Annotated[
        list[str] | None,
        typer.Option(
            "--fichier",
            help="Identifiant (bdpm.presentations) ou nom de fichier (CIS_CIP_bdpm.txt), répétable."
            " Les onze fichiers TSV par défaut.",
        ),
    ] = None,
    racine: OptionRacine = None,
    sortie: Annotated[
        Path,
        typer.Option(
            "--sortie",
            help="Dossier de sortie : evenements/<entite>/*.jsonl, bilans/<entite>/*.json,"
            " etat.json. Relatif au dossier courant.",
            show_default=True,
        ),
    ] = SORTIE_PAR_DEFAUT,
    reprendre: Annotated[
        bool,
        typer.Option(
            "--reprendre",
            help="Ne traite que les archives postérieures à la dernière traitée (etat.json) ;"
            " refusé si une version de contrat a changé.",
        ),
    ] = False,
) -> None:
    """Du bronze aux événements : chaque archive comparée à la dernière retenue.

    Sans --reprendre, rejeu complet depuis la première archive de chaque
    fichier (la sortie du fichier est recalculée). Code de sortie 1 si une
    archive est illisible, 2 si la reprise est impossible ; un snapshot écarté
    est un constat, pas une panne. Le journal (une ligne par archive :
    décision, motif, événements) va sur la sortie d'erreur.
    """
    configurer_journal(sys.stderr)
    chemin = _racine(racine)
    contrats = charger_tous()
    selection = _selection_contrats(fichier, None, contrats)
    if sortie.resolve().is_relative_to(chemin.resolve()):
        raise typer.BadParameter(
            f"{sortie} est sous la racine de l'archive {chemin}, qui ne s'écrit pas",
            param_hint="--sortie",
        )
    try:
        rapport = rejeu.executer(
            chemin, sortie, contrats, selection, reprendre=reprendre, journal=_journal_evenements
        )
    except rejeu.ReprendreImpossible as exc:
        titre = "reprise impossible" if reprendre else "rejeu impossible"
        typer.echo(f"{titre} : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for bilan_ in rapport.resumes:
        types = ", ".join(f"{t} {n}" for t, n in sorted(bilan_.evenements.items())) or "aucun"
        typer.echo(
            f"{bilan_.identifiant:28} {bilan_.archives_lues} archive(s) lue(s),"
            f" {bilan_.retenues} retenue(s), {bilan_.ecartees} écartée(s),"
            f" {bilan_.en_attente} en attente ; événements : {types}"
            + (f" ; ERREUR {bilan_.erreur}" if bilan_.erreur else "")
        )
    typer.echo(f"sortie : {sortie}")
    raise typer.Exit(code=rapport.code_sortie)


def _journal_evenements(message: str) -> None:
    logging.getLogger("pharmaflux.evenements").info(message)


@application.command()
def publier(
    sortie: Annotated[
        Path,
        typer.Option(
            "--sortie",
            help="Sortie de « evenements » : ses fichiers JSONL sont publiés, son"
            " publication.json garde ce qui l'est déjà.",
            show_default=True,
        ),
    ] = SORTIE_PAR_DEFAUT,
    courtier: OptionCourtier = None,
    registre: OptionRegistre = None,
    reprendre: Annotated[
        bool,
        typer.Option(
            "--reprendre",
            help="Ne publie que les fichiers absents de publication.json ; refusé si un fichier"
            " publié a changé.",
        ),
    ] = False,
) -> None:
    """Publie les fichiers d'événements sur le bus, un topic par entité, dans l'ordre.

    L'état est écrit après l'accusé de réception de chaque fichier. Codes de
    sortie : 1 courtier ou registre injoignable, livraison en échec ; 2 état
    illisible, état existant sans --reprendre, fichier publié modifié ; 3 au
    moins un message dans la file des échecs.
    """
    configurer_journal()
    adresse = _courtier(courtier)
    bus = fabriquer_bus(adresse) or BusKafka(adresse)
    try:
        with Registre(_registre(registre), fabriquer_transport_registre()) as registre_:
            rapport = publication.executer(
                sortie, bus, registre_, reprendre=reprendre, journal=_journal_evenements
            )
    except publication.PublicationRefusee as exc:
        typer.echo(f"publication refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except (CourtierInjoignable, RegistreIndisponible, publication.LivraisonEchouee) as exc:
        typer.echo(f"publication interrompue : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for entite in rapport.resumes:
        typer.echo(
            f"{entite.identifiant:28} {entite.fichiers} fichier(s) publié(s)"
            f" ({entite.deja_publies} déjà), {entite.messages} message(s),"
            f" {entite.echecs} en échec"
        )
    for topic, nombre in sorted(rapport.topics.items()):
        typer.echo(f"  {topic} : {nombre} message(s)")
    typer.echo(f"durée : {rapport.duree_s:.1f} s ; état : {sortie / publication.NOM_PUBLICATION}")
    raise typer.Exit(code=rapport.code_sortie)


@application.command("verifier-bus")
def verifier_bus(
    sortie: Annotated[
        Path,
        typer.Option(
            "--sortie",
            help="Sortie de « evenements » : ses fichiers d'événements sont la référence par"
            " défaut ; avec --racine, son etat.json désigne le dernier snapshot retenu.",
            show_default=True,
        ),
    ] = SORTIE_PAR_DEFAUT,
    courtier: OptionCourtier = None,
    racine: Annotated[
        Path | None,
        typer.Option(
            "--racine",
            help="Compare au dernier snapshot retenu, recalculé depuis cette archive (lecture"
            " seule), au lieu des fichiers d'événements.",
        ),
    ] = None,
    fichier: Annotated[
        list[str] | None,
        typer.Option(
            "--fichier",
            help="Identifiant (bdpm.presentations) ou nom de fichier (CIS_CIP_bdpm.txt), répétable."
            " Les onze fichiers TSV par défaut.",
        ),
    ] = None,
) -> None:
    """Relit chaque topic depuis le début, dédoublonne par id, applique et compare à la référence.

    Vérifie aussi la rétention sans limite, la politique, le type d'horodatage
    et les partitions de chaque topic.
    Codes de sortie : 1 courtier injoignable, 2 référence introuvable (refusée
    avant de lire le bus) ou toute différence d'état ou de configuration ; les
    doublons sont rapportés, pas comptés comme différence.
    """
    configurer_journal()
    contrats = charger_tous()
    selection = _selection_contrats(fichier, None, contrats)
    try:
        if racine is None:
            reference = verification.reference_fichiers(sortie)
            description = f"fichiers d'événements de {sortie}"
        else:
            reference = verification.reference_archive(sortie, racine, contrats)
            description = (
                f"dernier snapshot retenu d'après {sortie / rejeu.NOM_ETAT},"
                f" recalculé depuis {racine}"
            )
    except verification.ReferenceIntrouvable as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except rejeu.ReprendreImpossible as exc:
        typer.echo(f"référence impossible : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    adresse = _courtier(courtier)
    lecteur = fabriquer_lecteur(adresse) or LecteurKafka(adresse)
    try:
        rapport = verification.verifier(
            lecteur,
            selection,
            reference,
            description_reference=description,
            journal=_journal_evenements,
        )
    except CourtierInjoignable as exc:
        typer.echo(f"vérification interrompue : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except rejeu.ReprendreImpossible as exc:
        typer.echo(f"référence impossible : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    finally:
        if isinstance(lecteur, LecteurKafka):
            lecteur.close()
    for topic in rapport.topics:
        if topic.entite == "echecs":
            ligne = f"{topic.topic:28} {topic.messages} message(s) dans la file"
        else:
            ligne = (
                f"{topic.entite:28} {topic.messages} message(s), {topic.doublons} doublon(s) ;"
                f" {topic.lignes_bus} ligne(s) sur le bus, {topic.lignes_reference} en référence"
            )
        configuration = ", ".join(f"{c}={v}" for c, v in topic.configuration.items())
        ligne += f" ; {topic.partitions} partition(s), {configuration or 'configuration inconnue'}"
        verdict = (
            " ; conforme" if topic.conforme else " ; DIFFÉRENCE : " + " | ".join(topic.differences)
        )
        typer.echo(ligne + verdict)
        for chemin, nombre in topic.doublons_par_fichier.items():
            typer.echo(f"  doublons : {nombre} de {chemin}")
    typer.echo(f"référence : {rapport.reference}")
    typer.echo(f"durée : {rapport.duree_s:.1f} s")
    raise typer.Exit(code=rapport.code_sortie)


@application.command()
def suivre(
    fichier: Annotated[
        list[str] | None,
        typer.Option(
            "--fichier",
            help="Identifiant (bdpm.presentations) ou nom de fichier (CIS_CIP_bdpm.txt), répétable."
            " Les onze fichiers TSV par défaut.",
        ),
    ] = None,
    courtier: OptionCourtier = None,
    nombre: Annotated[
        int | None,
        typer.Option("--nombre", help="S'arrête après N messages (illisibles compris)."),
    ] = None,
    depuis_le_debut: Annotated[
        bool,
        typer.Option("--depuis-le-debut", help="Part du début des topics au lieu de leur fin."),
    ] = False,
) -> None:
    """Affiche les événements publiés au fil de l'eau : une ligne lisible par message.

    Heure observée, entité, type, clé, colonnes changées. Lit les onze topics
    d'événements (jamais la file des échecs) depuis leur fin : à lancer avant
    « demo rejouer ». Un topic absent est attendu. Un message qui n'est pas un
    événement v1 va sur la sortie d'erreur et est compté. Ctrl-C arrête avec
    le résumé. Code 0, sauf courtier injoignable (1).
    """
    selection = _selection_contrats(fichier, None, charger_tous())
    topics = [env.nom_topic(entite) for entite in selection]
    adresse = _courtier(courtier)
    suiveur = fabriquer_suiveur(adresse) or LecteurKafka(adresse)
    try:
        resume = suivi.suivre(
            suiveur,
            topics,
            depuis_le_debut=depuis_le_debut,
            nombre=nombre,
            dire=typer.echo,
            dire_erreur=lambda message: typer.echo(message, err=True),
        )
    except CourtierInjoignable as exc:
        typer.echo(f"suivi interrompu : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        if isinstance(suiveur, LecteurKafka):
            suiveur.close()
    for ligne in suivi.formater_resume(resume):
        typer.echo(ligne)


schemas = typer.Typer(
    name="schemas",
    help="Schémas du bus : enregistrement dans le registre de Redpanda (ADR 0007).",
    no_args_is_help=True,
)
application.add_typer(schemas)


@schemas.command("enregistrer")
def schemas_enregistrer(registre: OptionRegistre = None) -> None:
    """Pose la règle BACKWARD_TRANSITIVE et enregistre les schémas du dépôt, sujet par sujet.

    Idempotent : un schéma déjà connu garde son identifiant. Code 1 si le
    registre est injoignable, ou si le schéma courant d'un sujet est
    incompatible avec ses versions enregistrées (contrôlé avant de
    l'enregistrer, ADR 0007).
    """
    try:
        with Registre(_registre(registre), fabriquer_transport_registre()) as registre_:
            resultats = enregistrer_tout(registre_, sorted(charger_tous()))
    except (RegistreIndisponible, SchemaIncompatible) as exc:
        typer.echo(f"registre : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for resultat in resultats:
        etat_ = "nouveau" if resultat.nouveau else "déjà connu"
        typer.echo(f"{resultat.sujet:44} id {resultat.identifiant} ({etat_})")


demo = typer.Typer(
    name="demo",
    help="Le jeu de démo figé (demo/archive, mission 04) : fabriquer, vérifier, rejouer.",
    no_args_is_help=True,
)
application.add_typer(demo)

OptionJeu = Annotated[
    Path,
    typer.Option(
        "--racine", help="Le jeu de démo (une archive). Défaut : demo/archive.", show_default=True
    ),
]


@demo.command("fabriquer")
def demo_fabriquer(
    jusqu_au_passage: Annotated[
        str,
        typer.Option(
            "--jusqu-au-passage",
            help="Identifiant du dernier passage de collecte repris (AAAAMMJJTHHMMSSZ), inclus.",
        ),
    ],
    destination: Annotated[
        Path,
        typer.Option("--destination", help="Dossier du jeu, absent ou vide.", show_default=True),
    ] = jeu.JEU_PAR_DEFAUT,
    racine: OptionRacine = None,
    fichier: Annotated[
        list[str] | None,
        typer.Option(
            "--fichier",
            help="Identifiant (bdpm.presentations) ou nom de fichier (CIS_CIP_bdpm.txt), répétable."
            " Les onze fichiers TSV par défaut.",
        ),
    ] = None,
) -> None:
    """Fabrique un jeu de démo : archives et lignes de manifeste, à l'octet, jusqu'au passage.

    La racine n'est jamais écrite. Codes de sortie : 2 si la destination n'est
    pas vide, est sous la racine, ou si la coupure est mal formée ; 1 si le
    jeu écrit n'est pas conforme (« demo verifier » dit pourquoi).
    """
    selection = _selection_contrats(fichier, None, charger_tous())
    try:
        bilan = jeu.fabriquer(_racine(racine), destination, jusqu_au_passage, selection)
    except jeu.FabricationRefusee as exc:
        raise typer.BadParameter(str(exc), param_hint="--destination") from exc
    typer.echo(_resume_jeu(destination, bilan))
    raise typer.Exit(code=0 if bilan.conforme else 1)


@demo.command("verifier")
def demo_verifier(racine: OptionJeu = jeu.JEU_PAR_DEFAUT) -> None:
    """Vérifie un jeu de démo : manifeste lisible et ordonné, archives citées présentes et au
    sha256 près, rien d'autre dans le dossier. Code 1 à la moindre anomalie."""
    bilan = jeu.verifier(racine)
    typer.echo(_resume_jeu(racine, bilan))
    raise typer.Exit(code=0 if bilan.conforme else 1)


@demo.command("rejouer")
def demo_rejouer(
    racine: OptionJeu = jeu.JEU_PAR_DEFAUT,
    sortie: Annotated[
        Path,
        typer.Option(
            "--sortie",
            help="Sortie de « evenements » et publication.json de la démo. Relative au dossier"
            " courant, jamais sous la racine.",
            show_default=True,
        ),
    ] = rejeu_accelere.SORTIE_PAR_DEFAUT,
    fichier: Annotated[
        list[str] | None,
        typer.Option(
            "--fichier",
            help="Identifiant (bdpm.presentations) ou nom de fichier (CIS_CIP_bdpm.txt), répétable."
            " Les onze fichiers TSV par défaut.",
        ),
    ] = None,
    facteur: Annotated[
        float,
        typer.Option(
            "--facteur",
            help="Accélération : une heure observée dure 3 600 / facteur secondes.",
            show_default=True,
        ),
    ] = rejeu_accelere.FACTEUR_PAR_DEFAUT,
    sans_pause: Annotated[
        bool, typer.Option("--sans-pause", help="Aucune attente entre les entrées (la CI).")
    ] = False,
    sans_passages: Annotated[
        bool,
        typer.Option(
            "--sans-passages", help="Tait les passages de collecte sans archive nouvelle."
        ),
    ] = False,
    reprendre: Annotated[
        bool,
        typer.Option(
            "--reprendre",
            help="Continue un rejeu interrompu : publie les fichiers absents de publication.json.",
        ),
    ] = False,
    courtier: OptionCourtier = None,
    registre: OptionRegistre = None,
) -> None:
    """Rejoue le jeu de démo sur le bus, dans l'ordre global des observations, en accéléré.

    « evenements » puis, à l'heure observée divisée par le facteur, une ligne
    par archive lue (ses événements publiés, ou son snapshot écarté) et une
    par passage sans archive. Refuse un bus qui n'est pas vide sans son état,
    ou un état sans bus : « make rebatir ». Codes de sortie : ceux de
    « publier » (1 courtier, registre ou livraison ; 2 refus ; 3 file des
    échecs), 0 sinon.
    """
    if facteur <= 0:
        raise typer.BadParameter(
            "un nombre strictement positif est attendu", param_hint="--facteur"
        )
    contrats = charger_tous()
    selection = _selection_contrats(fichier, None, contrats)
    if sortie.resolve().is_relative_to(racine.resolve()):
        raise typer.BadParameter(
            f"{sortie} est sous la racine {racine}, qui ne s'écrit pas", param_hint="--sortie"
        )
    adresse = _courtier(courtier)
    bus = fabriquer_bus(adresse) or BusKafka(adresse)
    try:
        with Registre(_registre(registre), fabriquer_transport_registre()) as registre_:
            resume = rejeu_accelere.executer(
                racine,
                sortie,
                contrats,
                selection,
                bus,
                registre_,
                reprendre=reprendre,
                facteur=facteur,
                sans_pause=sans_pause,
                sans_passages=sans_passages,
                journal=typer.echo,
            )
    except (rejeu_accelere.DemoRefusee, publication.PublicationRefusee) as exc:
        typer.echo(f"démo refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except rejeu.ReprendreImpossible as exc:
        titre = "reprise impossible" if reprendre else "rejeu impossible"
        typer.echo(f"démo refusée : {titre} : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except publication.LivraisonEchouee as exc:
        typer.echo(f"démo interrompue : {exc} ; relance avec --reprendre", err=True)
        raise typer.Exit(code=1) from exc
    except (CourtierInjoignable, RegistreIndisponible, rejeu_accelere.DemoInterrompue) as exc:
        typer.echo(f"démo interrompue : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for ligne in rejeu_accelere.formater_resume(resume):
        typer.echo(ligne)
    raise typer.Exit(code=resume.code_sortie)


def _resume_jeu(racine: Path, bilan: jeu.Bilan) -> str:
    lignes = [
        f"jeu : {racine}",
        f"{bilan.lignes} ligne(s) de manifeste, {bilan.passages} passage(s)"
        + (
            f" du {bilan.premier_passage} au {bilan.dernier_passage}"
            if bilan.premier_passage
            else ""
        ),
        f"{len(bilan.archives)} archive(s), {len(bilan.entites)} entité(s)",
    ]
    lignes.extend(
        f"  {identifiant:28} {nombre} archive(s)"
        for identifiant, nombre in bilan.archives_par_entite().items()
    )
    if bilan.conforme:
        lignes.append("conforme")
    else:
        lignes.append(f"NON CONFORME : {len(bilan.anomalies)} anomalie(s)")
        lignes.extend(f"  {anomalie}" for anomalie in bilan.anomalies)
    return "\n".join(lignes)


def _courtier(courtier: str | None) -> str:
    return courtier or os.environ.get(VARIABLE_COURTIER) or COURTIER_PAR_DEFAUT


def _registre(registre: str | None) -> str:
    return registre or os.environ.get(VARIABLE_REGISTRE) or REGISTRE_PAR_DEFAUT


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
            help="Le jeu de questions TOML. Le chemin par défaut est relatif au dossier courant : "
            "le jeu de référence est à la racine du dépôt.",
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


# --- silver (mission 05) -----------------------------------------------------------------------
# PyArrow, PyIceberg et DuckDB pèsent 100 Mo résidents : ils ne s'importent que dans ces
# commandes (addendum 1, K.1), et un test le vérifie.

silver = typer.Typer(
    name="silver",
    help="Le silver (mission 05) : tables Iceberg SCD2 par entité, état à une date, SQL en"
    " lecture seule, comparaison de deux entrepôts, vérification contre l'archive.",
    no_args_is_help=True,
)
application.add_typer(silver)

OptionEntrepot = Annotated[
    Path,
    typer.Option(
        "--entrepot",
        help="Dossier de l'entrepôt Iceberg (catalogue SQLite et tables), hors git.",
        show_default=True,
    ),
]
OptionFichierSilver = Annotated[
    list[str] | None,
    typer.Option(
        "--fichier",
        help="Identifiant (bdpm.presentations) ou nom de fichier (CIS_CIP_bdpm.txt), répétable."
        " Les onze fichiers TSV par défaut.",
    ),
]
OptionFormat = Annotated[
    Format, typer.Option("--format", help="jsonl (une version par ligne), tableau ou csv.")
]


def _journal_silver(message: str) -> None:
    logging.getLogger("pharmaflux.silver").info(message)


@silver.command("construire")
def silver_construire(
    sortie: Annotated[
        Path,
        typer.Option(
            "--sortie",
            help="Sortie de « evenements » : ses fichiers d'événements, dans l'ordre des noms.",
            show_default=True,
        ),
    ] = SORTIE_PAR_DEFAUT,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    fichier: OptionFichierSilver = None,
    lot: Annotated[
        int, typer.Option("--lot", help="Événements par commit Iceberg.", show_default=True)
    ] = LOT_PAR_DEFAUT,
) -> None:
    """Construit le silver depuis les fichiers d'événements, dans un entrepôt neuf.

    Une table Iceberg par entité, une version SCD2 par ligne (PRD §6.5), un
    commit par lot. Refuse un entrepôt non vide et ne l'efface jamais (code 2) ;
    code 2 aussi quand un événement ne peut pas être appliqué. Le journal (une
    ligne par fichier) va sur la sortie d'erreur.
    """
    configurer_journal(sys.stderr)
    from pharmaflux.silver import construction
    from pharmaflux.silver.entrepot import allocateur_systeme

    allocateur_systeme()
    contrats = charger_tous()
    selection = _selection_contrats(fichier, None, contrats)
    try:
        rapport = construction.construire(
            sortie, entrepot, contrats, selection, lot=lot, journal=_journal_silver
        )
    except SilverRefuse as exc:
        typer.echo(f"construction refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for entite_ in rapport.resumes:
        typer.echo(
            f"{entite_.identifiant:28} {entite_.fichiers} fichier(s), {entite_.evenements}"
            f" événement(s), {entite_.ouvertures} ouverture(s), {entite_.fermetures} fermeture(s),"
            f" {entite_.doublons} doublon(s), {entite_.commits} commit(s)"
        )
    typer.echo(f"entrepôt : {rapport.entrepot} ; durée : {rapport.duree_s:.1f} s")


@silver.command("etat")
def silver_etat(
    entite: Annotated[
        str, typer.Option("--entite", help="Identifiant (bdpm.presentations) ou nom de fichier.")
    ],
    a: Annotated[
        str,
        typer.Option(
            "--a",
            help="L'instant, UTC à la seconde, trois formes : 2026-10-26T14:00:00Z, avec un"
            " décalage (…T16:00:00+02:00), ou une date seule (minuit UTC). Rien d'autre.",
        ),
    ],
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    ou: Annotated[
        list[str] | None,
        typer.Option("--ou", help="Filtre colonne=valeur (égalité sur la chaîne), répétable."),
    ] = None,
    format_: OptionFormat = Format.JSONL,
    colonne: Annotated[
        list[str] | None,
        typer.Option("--colonne", help="Colonnes à écrire, répétable ; toutes par défaut."),
    ] = None,
) -> None:
    """Les versions valides à un instant : ce que l'on savait alors (PRD §2.1, objectif 2).

    Une version vaut de la date d'observation qui l'ouvre à celle qui la ferme,
    borne de fin exclue. Avant la première observation : aucune version ; après
    la dernière : les versions ouvertes ; code 0 et un message sur la sortie
    d'erreur dans les deux cas. Code 2 : instant refusé, entité ou colonne
    inconnue, entrepôt absent.
    """
    from pharmaflux.silver import etat as etat_silver
    from pharmaflux.silver.entrepot import Entrepot, allocateur_systeme
    from pharmaflux.silver.schema import texte_instant

    allocateur_systeme()
    contrats = charger_tous()
    (identifiant,) = _selection_contrats([entite], None, contrats)
    try:
        instant = etat_silver.lire_instant(a)
        filtres = etat_silver.lire_filtres(ou or [])
        table = Entrepot.ouvrir(entrepot).table(identifiant)
        if table is None:
            raise SilverRefuse(f"aucune table {identifiant} dans {entrepot}")
        versions = etat_silver.ordonner(etat_silver.etat_a(table, instant, filtres))
        premiere, derniere = etat_silver.bornes(table)
        lignes = list(etat_silver.rendre(versions, format_, colonne))
    except SilverRefuse as exc:
        typer.echo(f"état refusé : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in lignes:
        typer.echo(ligne)
    typer.echo(
        f"{identifiant} à {texte_instant(instant)} : {versions.num_rows} version(s) valide(s)",
        err=True,
    )
    if premiere is None or derniere is None:
        typer.echo("le silver de cette entité est vide", err=True)
    elif instant < premiere:
        typer.echo(
            f"aucune version : l'instant précède la première observation"
            f" ({texte_instant(premiere)})",
            err=True,
        )
    elif instant > derniere:
        typer.echo(
            f"le silver s'arrête à la dernière observation ({texte_instant(derniere)}) :"
            " ce sont les versions ouvertes",
            err=True,
        )


@silver.command("sql")
def silver_sql(
    requete: Annotated[
        str,
        typer.Argument(
            help="Une requête SELECT ; les tables portent le nom court de l'entité (presentations)."
        ),
    ],
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    format_: OptionFormat = Format.TABLEAU,
) -> None:
    """Du SQL (DuckDB) sur le silver, en lecture seule et verrouillé.

    DuckDB ne touche aucun fichier : les tables lui sont données en Arrow, l'accès
    externe est coupé, la configuration verrouillée, et seul un SELECT passe.
    Code 2 pour toute autre requête, ou une requête en erreur.
    """
    from pharmaflux.silver import etat as etat_silver
    from pharmaflux.silver import sql as sql_silver
    from pharmaflux.silver.entrepot import Entrepot, allocateur_systeme

    allocateur_systeme()
    try:
        con = sql_silver.connexion(Entrepot.ouvrir(entrepot))
        resultat = sql_silver.executer(con, requete)
        lignes = list(etat_silver.rendre(resultat, format_))
    except SilverRefuse as exc:
        typer.echo(f"requête refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in lignes:
        typer.echo(ligne)
    typer.echo(f"{resultat.num_rows} ligne(s)", err=True)


@silver.command("comparer")
def silver_comparer(
    a: Annotated[Path, typer.Argument(help="Premier entrepôt.")],
    b: Annotated[Path, typer.Argument(help="Second entrepôt.")],
) -> None:
    """Compare deux entrepôts : mêmes tables, mêmes versions, mêmes validités (PRD §7.1).

    Les métadonnées des snapshots, les fichiers Parquet et les propriétés de
    table sont hors de la comparaison. Code 2 à la première différence.
    """
    from pharmaflux.silver import comparaison
    from pharmaflux.silver.entrepot import Entrepot, allocateur_systeme

    allocateur_systeme()
    try:
        premier, second = Entrepot.ouvrir(a), Entrepot.ouvrir(b)
        differences = comparaison.comparer(premier, second)
    except SilverRefuse as exc:
        typer.echo(f"comparaison refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for difference in differences:
        typer.echo(f"DIFFÉRENCE : {difference}")
    if differences:
        raise typer.Exit(code=2)
    entites = premier.entites()
    typer.echo(f"identiques : {len(entites)} table(s) ({', '.join(entites)})")


@silver.command("verifier")
def silver_verifier(
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    sortie: Annotated[
        Path,
        typer.Option(
            "--sortie",
            help="Sortie de « evenements » : ses bilans donnent les archives et leur verdict.",
            show_default=True,
        ),
    ] = SORTIE_PAR_DEFAUT,
    racine: OptionRacine = None,
    fichier: OptionFichierSilver = None,
) -> None:
    """Vérifie le silver contre l'archive : l'état à chaque observation égale le snapshot.

    Pour chaque archive retenue, le snapshot normalisé est recalculé depuis le
    bronze et comparé, empreinte par empreinte, à l'état du silver à son
    horodatage ; une archive écartée doit laisser l'état du dernier retenu.
    Puis les invariants du SCD2 (DuckDB). Toute différence : code 2 ; référence
    introuvable (pas de bilans) : code 2 avant toute lecture.
    """
    configurer_journal(sys.stderr)
    from pharmaflux.silver import verification as verification_silver
    from pharmaflux.silver.entrepot import Entrepot, allocateur_systeme

    allocateur_systeme()
    contrats = charger_tous()
    selection = _selection_contrats(fichier, None, contrats)
    try:
        rapport = verification_silver.verifier(
            Entrepot.ouvrir(entrepot),
            sortie,
            _racine(racine),
            contrats,
            selection,
            journal=_journal_silver,
        )
    except SilverRefuse as exc:
        typer.echo(f"vérification refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for resultat in rapport.entites:
        for archive in resultat.archives:
            verdict = (
                "conforme"
                if archive.conforme
                else "DIFFÉRENCE : " + " | ".join(archive.differences)
            )
            typer.echo(
                f"{resultat.entite:28} {Path(archive.archive).name[:16]} ({archive.decision},"
                f" observée {archive.observee}) {archive.identites} identité(s) : {verdict}"
            )
        for note in resultat.notes:
            typer.echo(f"{resultat.entite:28} note : {note}")
        invariants = (
            "conformes"
            if not resultat.invariants
            else "TOMBÉS : " + " | ".join(resultat.invariants)
        )
        typer.echo(
            f"{resultat.entite:28} {resultat.versions} version(s), {resultat.ouvertes} ouverte(s),"
            f" {resultat.fichiers} fichier(s) Parquet, {resultat.snapshots} snapshot(s) ;"
            f" invariants : {invariants}"
        )
    typer.echo(
        f"{rapport.archives_conformes}/{rapport.archives_verifiees} archive(s) conforme(s) ;"
        f" durée : {rapport.duree_s:.1f} s"
    )
    raise typer.Exit(code=rapport.code_sortie)


@silver.command("consommer")
def silver_consommer(
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    courtier: OptionCourtier = None,
    fichier: OptionFichierSilver = None,
    lot: Annotated[
        int, typer.Option("--lot", help="Messages par commit Iceberg.", show_default=True)
    ] = LOT_PAR_DEFAUT,
) -> None:
    """Lit le bus et alimente le silver : chaque topic depuis la position gardée dans sa table.

    Toutes les partitions à la fois, jusqu'aux offsets de fin lus au départ ;
    un commit Iceberg par lot, qui porte la position ; les doublons sont
    reconnus à leur identifiant. L'entrepôt est créé s'il n'existe pas, et
    repris sinon. Codes : 1 courtier injoignable ; 2 refus (silver construit
    depuis les fichiers, bus rebâti ou vide, message qui n'est pas un
    événement v1, autre version de contrat) : rien n'est écrit.
    """
    configurer_journal(sys.stderr)
    from pharmaflux.silver import consommation
    from pharmaflux.silver.entrepot import allocateur_systeme

    allocateur_systeme()
    contrats = charger_tous()
    selection = _selection_contrats(fichier, None, contrats)
    adresse = _courtier(courtier)
    lecteur = fabriquer_lecteur_silver(adresse) or LecteurKafka(adresse)
    try:
        rapport = consommation.consommer(
            lecteur, entrepot, contrats, selection, lot=lot, journal=_journal_silver
        )
    except CourtierInjoignable as exc:
        typer.echo(f"consommation interrompue : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except SilverRefuse as exc:
        typer.echo(f"consommation refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    finally:
        if isinstance(lecteur, LecteurKafka):
            lecteur.close()
    for avertissement in rapport.avertissements:
        typer.echo(f"AVERTISSEMENT : {avertissement}", err=True)
    for entite_ in rapport.resumes:
        positions = ", ".join(f"p{p} → {v.suivant}" for p, v in sorted(entite_.positions.items()))
        notes = f" ; {' ; '.join(entite_.notes)}" if entite_.notes else ""
        typer.echo(
            f"{entite_.identifiant:28} {entite_.messages} message(s), {entite_.doublons}"
            f" doublon(s), {entite_.ouvertures} ouverture(s), {entite_.fermetures} fermeture(s),"
            f" {entite_.commits} commit(s) ; positions : {positions or 'aucune'}{notes}"
        )
    typer.echo(
        f"entrepôt : {rapport.entrepot} ; grappe : {rapport.grappe or 'inconnue'} ;"
        f" {rapport.messages} message(s) ; durée : {rapport.duree_s:.1f} s"
    )
