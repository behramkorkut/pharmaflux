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
``gold etat`` / ``qualite`` / ``sql`` : l'état typé du silver à un instant et
ses contrôles de qualité (mission 06), sous la même règle d'import.
``has collecter`` / ``has extraire`` : les pages d'avis de la HAS (mission 09), collectées
poliment et extraites mot pour mot.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from importlib.metadata import version as version_du_paquet
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, TextIO

import httpx
import typer

from pharmaflux import bronze
from pharmaflux.assistant.client import EFFORT_DEFAUT, ClientLLM
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
from pharmaflux.demo import has as demo_has
from pharmaflux.demo import jeu, rejeu_accelere
from pharmaflux.evaluation import questions as jeu_questions
from pharmaflux.evaluation.verification import formater_bilan, verifier_jeu
from pharmaflux.evenements import rejeu
from pharmaflux.silver import ENTREPOT_PAR_DEFAUT, LOT_PAR_DEFAUT, Format, SilverRefuse

if TYPE_CHECKING:  # le silver ne s'importe que dans ses commandes (K.1)
    from pharmaflux.assistant.chemin import Reponse as Reponse_
    from pharmaflux.assistant.evaluation import Estimation as Estimation_
    from pharmaflux.assistant.notation import Indicateurs as Indicateurs_
    from pharmaflux.assistant.notation import Note as Note_
    from pharmaflux.gold.typage import EntiteTypee as EntiteTypee_
    from pharmaflux.gold.vues import Vues as Vues_
    from pharmaflux.silver.consommation import LecteurSilver
    from pharmaflux.silver.entrepot import Entrepot as Entrepot_

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
# La collecte des pages de la HAS (mission 09) : les tests simulent le site, jamais le réseau,
# et ne dorment pas les deux secondes de pause.
fabriquer_transport_has: Callable[[], httpx.BaseTransport | None] = lambda: None  # noqa: E731
dormir_has: Callable[[float], None] = time.sleep
# Les tests simulent Qdrant de la même façon (mission 07).
fabriquer_transport_qdrant: Callable[[], httpx.BaseTransport | None] = (  # noqa: E731
    lambda: None
)
# L'assistant (mission 08) : les tests injectent le double du client Claude ; None = le vrai
# client (ClientClaude), qui n'importe anthropic qu'à sa construction. Aucun appel réel aux tests.
fabriquer_client_llm: Callable[[], ClientLLM | None] = lambda: None  # noqa: E731

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
    l'enregistrer, ADR 0007). Un appel coupé sans réponse est réessayé deux fois ;
    le total des réessais est affiché s'il n'est pas nul.
    """
    try:
        with Registre(_registre(registre), fabriquer_transport_registre()) as registre_:
            resultats = enregistrer_tout(registre_, sorted(charger_tous()))
            reessais = registre_.reessais
    except (RegistreIndisponible, SchemaIncompatible) as exc:
        typer.echo(f"registre : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for resultat in resultats:
        etat_ = "nouveau" if resultat.nouveau else "déjà connu"
        typer.echo(f"{resultat.sujet:44} id {resultat.identifiant} ({etat_})")
    if reessais:
        typer.echo(
            f"registre : {reessais} réessai(s) après une coupure sans réponse (lignes ci-dessus)",
            err=True,
        )


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


@demo.command("choisir-has")
def demo_choisir_has(
    racine: OptionJeu = jeu.JEU_PAR_DEFAUT,
    questions: Annotated[
        Path, typer.Option("--questions", help="Le jeu de questions dont les CIS sont repris.")
    ] = demo_has.QUESTIONS_PAR_DEFAUT,
    sortie: Annotated[
        Path, typer.Option("--sortie", help="La liste des pages, une URL par ligne.")
    ] = demo_has.LISTE_PAR_DEFAUT,
) -> None:
    """Écrit la liste des pages d'avis du jeu de démo, par la règle de demo.has.

    Le périmètre de la première étape se calcule sur la BDPM du jeu (sans
    réseau) : pages imposées, pages des CIS des questions, puis complément par
    le plus petit sha256 de l'URL, jusqu'à 150 pages. Code 2 : périmètre
    illisible ou page imposée absente.
    """
    from pharmaflux.has.perimetre import PerimetreIllisible, calculer

    try:
        perimetre = calculer(racine)
        pages = demo_has.choisir(perimetre, demo_has.cis_des_questions(questions))
    except (PerimetreIllisible, demo_has.FabricationRefusee) as exc:
        typer.echo(f"choix refusé : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    raisons: dict[str, int] = {}
    for page in pages:
        cle = page.raison.split(" :")[0]
        raisons[cle] = raisons.get(cle, 0) + 1
    entete = [
        "Pages d'avis de la HAS du jeu de démo (mission 09, addendum 1 E). Fichier écrit par",
        f"« pharmaflux demo choisir-has --questions {questions.as_posix()} », jamais à la main.",
        "",
        "La règle (src/pharmaflux/demo/has.py, demo/README.md), sur la première étape",
        f"(avis SMR ou ASMR depuis le {perimetre.depuis.isoformat()}, {len(perimetre.pages)} pages,"
        f" liste sha256 {perimetre.empreinte_liste()[:16]}…) :",
        "1. les pages imposées (fixtures du §0, cas de la collecte) ;",
        "2. les pages des CIS visés par une question du jeu ;",
        "3. le complément : les plus petits sha256 de l'URL, jusqu'à"
        f" {demo_has.NOMBRE_PAGES} pages.",
    ]
    demo_has.ecrire_liste(sortie, pages, entete)
    detail = ", ".join(f"{cle} {n}" for cle, n in raisons.items())
    typer.echo(f"{len(pages)} page(s) écrites dans {sortie} ({detail})")


@demo.command("fabriquer-has")
def demo_fabriquer_has(
    racine: OptionRacine = None,
    destination: Annotated[
        Path, typer.Option("--destination", help="Le jeu, qui n'a pas encore de pages d'avis.")
    ] = jeu.JEU_PAR_DEFAUT,
    liste: Annotated[
        Path, typer.Option("--liste", help="La liste écrite par demo choisir-has.")
    ] = demo_has.LISTE_PAR_DEFAUT,
) -> None:
    """Copie dans le jeu, à l'octet, la dernière archive de chaque page de la liste et sa
    ligne du manifeste HAS, depuis l'archive de la collecte (lue, jamais écrite).

    Codes de sortie : 2 si la liste est illisible, une page n'a pas d'archive, la
    destination est sous la racine ou a déjà ses pages ; 1 si le jeu écrit n'est
    pas conforme (« demo verifier » dit pourquoi).
    """
    try:
        demo_has.fabriquer(_racine(racine), destination, liste)
    except demo_has.FabricationRefusee as exc:
        typer.echo(f"fabrication refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    bilan = jeu.verifier(destination)
    typer.echo(_resume_jeu(destination, bilan))
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
    if bilan.has.present:
        lignes.append(
            f"pages d'avis de la HAS : {len(bilan.has.pages)} page(s), {bilan.has.lignes} ligne(s)"
            f" de manifeste, {bilan.has.octets} octets compressés"
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
    entrepot: Annotated[
        Path | None,
        typer.Option(
            "--entrepot",
            help="Recalcule aussi chaque attendu depuis le gold de cet entrepôt, à l'instant de"
            " son archive, et exige la concordance (mission 06).",
        ),
    ] = None,
) -> None:
    """Rejoue chaque question : archive citée relue, sha256 vérifié, valeur recalculée.

    Code de sortie 1 au moindre écart, archive introuvable, sha256 différent
    ou archive non conforme à son contrat. Avec --entrepot, chaque attendu est
    aussi recalculé depuis le gold (fiche, alternatives ou colonnes typées) et
    comparé en multiensemble ; une discordance, ou une question non calculable
    depuis le gold, donne le code 2.
    """
    contrats = charger_tous()
    try:
        jeu = jeu_questions.charger(fichier_questions, contrats)
    except jeu_questions.JeuInvalide as exc:
        raise typer.BadParameter(str(exc), param_hint="--questions") from exc
    bilan = verifier_jeu(jeu, _racine(racine), contrats)
    typer.echo(formater_bilan(bilan))
    if entrepot is None:
        raise typer.Exit(code=bilan.code_sortie)
    from pharmaflux.gold import questions as questions_gold
    from pharmaflux.silver.entrepot import Entrepot, allocateur_systeme

    allocateur_systeme()
    try:
        bilan_gold = questions_gold.verifier_gold(jeu, Entrepot.ouvrir(entrepot), contrats)
    except SilverRefuse as exc:
        typer.echo(f"calcul depuis le gold refusé : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in questions_gold.formater(bilan_gold):
        typer.echo(ligne)
    raise typer.Exit(code=bilan_gold.code_sortie or bilan.code_sortie)


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


# --- has (mission 09) -------------------------------------------------------------------------

has = typer.Typer(
    name="has",
    help="Les pages d'avis de la HAS (mission 09, ADR 0004) : collecter, extraire.",
    no_args_is_help=True,
)
application.add_typer(has)


@has.command("collecter")
def has_collecter(
    plafond: Annotated[
        int | None,
        typer.Option(
            "--plafond",
            help="Requêtes au plus, réessais, robots.txt et mentions légales compris. Obligatoire"
            " pour un passage réel ; --simuler en conseille un.",
        ),
    ] = None,
    depuis: Annotated[
        str,
        typer.Option(
            "--depuis", help="Les dossiers dont un avis SMR ou ASMR date de ce jour ou après."
        ),
    ] = "2024-01-01",
    dossier: Annotated[
        list[str] | None,
        typer.Option("--dossier", help="Restreindre à ce dossier (CT-21030), répétable."),
    ] = None,
    pause: Annotated[
        float,
        typer.Option("--pause", help="Secondes entre deux requêtes, deux au moins."),
    ] = 2.0,
    simuler: Annotated[
        bool,
        typer.Option(
            "--simuler",
            help="Dire ce qui serait demandé (URL, nombre, durée), sans aucune requête.",
        ),
    ] = False,
    reessayer_erreurs: Annotated[
        bool,
        typer.Option("--reessayer-erreurs", help="Redemander aussi les pages en erreur."),
    ] = False,
    racine: OptionRacine = None,
) -> None:
    """Un passage de collecte des pages d'avis : robots.txt, mentions légales, pages.

    Une page archivée n'est jamais redemandée ; une relance reprend ce qui manque. Codes de
    sortie : 0 tout est archivé ; 1 des pages en erreur ; 2 refus (option, archive de la BDPM
    ou robots.txt illisibles) ; 3 arrêt net (429, 5xx répété, plafond).
    """
    from pharmaflux.has import collecte as collecte_has
    from pharmaflux.has.client import PAUSE_MINIMALE, ClientHas
    from pharmaflux.has.perimetre import PerimetreIllisible, calculer

    configurer_journal()
    racine_ = _racine(racine)
    if pause < PAUSE_MINIMALE:
        typer.echo(f"--pause {pause} : {PAUSE_MINIMALE} s au moins", err=True)
        raise typer.Exit(code=2)
    try:
        jour = datetime.strptime(depuis, "%Y-%m-%d").date()
    except ValueError as exc:
        typer.echo(f"--depuis {depuis} : une date AAAA-MM-JJ est attendue", err=True)
        raise typer.Exit(code=2) from exc
    try:
        perimetre = calculer(racine_, depuis=jour, dossiers=dossier)
        plan = collecte_has.planifier(racine_, perimetre, reessayer_erreurs=reessayer_erreurs)
    except (PerimetreIllisible, manifeste.ManifesteCorrompu) as exc:
        typer.echo(f"refus : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if simuler:
        _echo_simulation(plan, pause, plafond)
        raise typer.Exit(code=0)
    if plafond is None:
        typer.echo(
            "--plafond est obligatoire pour un passage réel (--simuler en conseille un)", err=True
        )
        raise typer.Exit(code=2)
    with ClientHas(
        plafond=plafond, pause=pause, transport=fabriquer_transport_has(), dormir=dormir_has
    ) as client:
        bilan = collecte_has.executer(racine_, plan, client)
    typer.echo(bilan.resume())
    raise typer.Exit(code=bilan.code_sortie)


def _echo_simulation(plan: Any, pause: float, plafond: int | None) -> None:
    perimetre = plan.perimetre
    typer.echo("simulation : aucune requête envoyée")
    for source in perimetre.sources:
        typer.echo(f"  {source.identifiant:15} {source.archive} (sha256 {source.sha256[:12]}…)")
    typer.echo(
        f"dossiers avec un avis SMR ou ASMR depuis le {perimetre.depuis.isoformat()} :"
        f" {perimetre.dossiers}, dont {perimetre.dossiers_avec_lien} avec un lien et"
        f" {len(perimetre.dossiers_sans_lien)} sans lien ; {len(perimetre.pages)} page(s)"
    )
    if perimetre.liens_hors_forme:
        typer.echo(f"liens hors forme, écartés : {', '.join(perimetre.liens_hors_forme)}")
    etat = plan.etat
    typer.echo(
        f"déjà archivées : {len(etat.archivees)} ; archives orphelines à reprendre :"
        f" {len(etat.orphelines)} ; en erreur, non redemandées : {plan.erreurs_ecartees}"
    )
    duree = plan.duree_estimee(pause)
    typer.echo(
        f"requêtes : {plan.requetes} (robots.txt, mentions légales et {len(plan.a_demander)}"
        f" page(s)) ; durée estimée ≈ {int(duree // 60)} min {int(duree % 60):02d} s à {pause} s"
        f" de pause ; plafond conseillé : {plan.plafond_conseille}"
    )
    if plafond is not None and plafond < plan.requetes:
        typer.echo(f"--plafond {plafond} : le passage s'arrêterait avant la fin")
    typer.echo(f"liste des URL (sha256 {perimetre.empreinte_liste()[:12]}…), dans l'ordre :")
    for page in plan.a_demander:
        typer.echo(f"  {page.date_avis} {','.join(page.dossiers)} {page.url}")


@has.command("extraire")
def has_extraire(
    verifier: Annotated[
        bool,
        typer.Option(
            "--verifier",
            help="Non-altération (second lecteur), déterminisme et empreintes du manifeste.",
        ),
    ] = False,
    sortie: Annotated[
        Path | None,
        typer.Option("--sortie", help="Écrire chaque page en JSON Lines, pour la lire."),
    ] = None,
    page: Annotated[
        list[Path] | None,
        typer.Option("--page", help="Une page (.html ou .html.gz) hors archive, répétable."),
    ] = None,
    racine: OptionRacine = None,
) -> None:
    """L'extraction rejouée sur les pages archivées : bilan des rejets, vérification.

    L'index ne lit jamais sa sortie. Codes : 0 conforme ; 1 un écart ou une divergence ;
    2 aucune page.
    """
    from pharmaflux.has import inspection

    try:
        pages = (
            inspection.pages_de_fichiers(page)
            if page
            else inspection.pages_archivees(_racine(racine))
        )
    except manifeste.ManifesteCorrompu as exc:
        typer.echo(f"refus : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if sortie is not None:
        with sortie.open("w", encoding="utf-8") as flux:
            bilan = inspection.extraire(pages, verifier=verifier, sortie=flux)
    else:
        bilan = inspection.extraire(pages, verifier=verifier)
    typer.echo(bilan.resume())
    raise typer.Exit(code=bilan.code_sortie)


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


# --- gold (mission 06) -------------------------------------------------------------------------
# Le gold est une fonction du silver et d'un instant (ADR 0010) : rien n'est stocké. Les
# bibliothèques ne s'importent, comme pour le silver, que dans ces commandes.

gold = typer.Typer(
    name="gold",
    help="Le gold (mission 06) : l'état typé du silver à un instant, ses contrôles de qualité,"
    " du SQL en lecture seule sur les entités typées.",
    no_args_is_help=True,
)
application.add_typer(gold)

OptionInstantGold = Annotated[
    str | None,
    typer.Option(
        "--a",
        help="L'instant, comme pour silver etat (UTC à la seconde, avec un décalage, ou une date"
        " seule). Défaut : la dernière observation du silver.",
    ),
]


def _instant_gold(a: str | None, entrepot: Path) -> tuple[Entrepot_, datetime]:
    """L'entrepôt ouvert et l'instant demandé, ou la dernière observation du silver."""
    from pharmaflux.gold.typage import derniere_observation
    from pharmaflux.silver import etat as etat_silver
    from pharmaflux.silver.entrepot import Entrepot, allocateur_systeme
    from pharmaflux.silver.schema import texte_instant

    allocateur_systeme()
    ouvert = Entrepot.ouvrir(entrepot)
    if a is not None:
        return ouvert, etat_silver.lire_instant(a)
    derniere = derniere_observation(ouvert)
    if derniere is None:
        raise SilverRefuse(f"le silver de {entrepot} est vide : aucun instant par défaut")
    typer.echo(f"instant : {texte_instant(derniere)} (dernière observation du silver)", err=True)
    return ouvert, derniere


def _vues_gold(a: str | None, entrepot: Path) -> tuple[dict[str, EntiteTypee_], Vues_]:
    """Les onze entités typées et les trois vues métier, à l'instant demandé."""
    from pharmaflux.gold.qualite import exiger_les_onze
    from pharmaflux.gold.sql import etats_types
    from pharmaflux.gold.vues import vues

    ouvert, instant = _instant_gold(a, entrepot)
    exiger_les_onze(ouvert, instant)
    contrats = charger_tous()
    etats = etats_types(ouvert, contrats, instant)
    return etats, vues(ouvert, contrats, etats, instant)


@gold.command("etat")
def gold_etat(
    entite: Annotated[
        str, typer.Option("--entite", help="Identifiant (bdpm.presentations) ou nom de fichier.")
    ],
    a: OptionInstantGold = None,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    ou: Annotated[
        list[str] | None,
        typer.Option(
            "--ou",
            help="Filtre colonne=valeur, égalité sur la valeur du silver (forme canonique),"
            " répétable.",
        ),
    ] = None,
    format_: OptionFormat = Format.JSONL,
    colonne: Annotated[
        list[str] | None,
        typer.Option("--colonne", help="Colonnes à écrire, répétable ; toutes par défaut."),
    ] = None,
) -> None:
    """L'état typé d'une entité à un instant : chaque colonne au type de son contrat.

    Une valeur illisible n'est jamais devinée : sa colonne typée est vide, la
    valeur brute reste dans le silver, et ``colonnes_illisibles`` la nomme. Un
    décimal sort en chaîne exacte (« 1.16 »), une date en AAAA-MM-JJ. Code 2 :
    instant refusé, entité ou colonne inconnue, entrepôt absent.
    """
    from pharmaflux.gold.rendu import rendre
    from pharmaflux.gold.typage import etat_type
    from pharmaflux.silver import etat as etat_silver
    from pharmaflux.silver.schema import texte_instant

    contrats = charger_tous()
    (identifiant,) = _selection_contrats([entite], None, contrats)
    try:
        ouvert, instant = _instant_gold(a, entrepot)
        filtres = etat_silver.lire_filtres(ou or [])
        typee = etat_type(ouvert, contrats[identifiant], instant, filtres)
        lignes = list(rendre(etat_silver.ordonner(typee.table), format_, colonne))
    except SilverRefuse as exc:
        typer.echo(f"état refusé : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in lignes:
        typer.echo(ligne)
    typer.echo(
        f"{identifiant} à {texte_instant(instant)} : {typee.table.num_rows} ligne(s) typée(s)",
        err=True,
    )


@gold.command("qualite")
def gold_qualite(
    a: OptionInstantGold = None,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    format_: Annotated[
        Format, typer.Option("--format", help="tableau (défaut) ou jsonl (un contrôle par ligne).")
    ] = Format.TABLEAU,
) -> None:
    """Les quatorze contrôles de qualité à un instant : quatre bloquants, dix mesurés.

    Bloquant : un invariant de la chaîne (clés uniques, une version par
    identité, valeurs canoniques typables, aucune entité vidée). Mesuré : un
    fait de la source, toujours affiché, même à 0. Code 2 si un bloquant tombe,
    ou sur un refus (instant, entrepôt, entité absente).
    """
    import json

    from pharmaflux.gold import qualite

    try:
        ouvert, instant = _instant_gold(a, entrepot)
        rapport = qualite.controler(ouvert, charger_tous(), instant)
    except SilverRefuse as exc:
        typer.echo(f"contrôles refusés : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if format_ is Format.JSONL:
        for controle in rapport.controles:
            typer.echo(json.dumps(qualite.en_dict(controle), ensure_ascii=False))
        typer.echo(rapport.resume(), err=True)
    else:
        for ligne in qualite.formater(rapport):
            typer.echo(ligne)
    raise typer.Exit(code=rapport.code_sortie)


@gold.command("sql")
def gold_sql(
    requete: Annotated[
        str,
        typer.Argument(
            help="Une requête SELECT ; chaque entité typée porte son nom court (presentations)."
        ),
    ],
    a: OptionInstantGold = None,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    format_: OptionFormat = Format.TABLEAU,
) -> None:
    """Du SQL (DuckDB) sur le gold à un instant, en lecture seule et verrouillé.

    Les onze entités typées sous leur nom court, et les trois vues métier :
    fiche_medicament, disponibilite_courante, alternatives. La barrière est
    celle de silver sql : DuckDB ne touche aucun fichier, seul un SELECT passe.
    Code 2 pour toute autre requête, ou une requête en erreur.
    """
    from pharmaflux.gold import sql as sql_gold
    from pharmaflux.gold.rendu import rendre
    from pharmaflux.silver import sql as sql_silver

    try:
        etats, vues_ = _vues_gold(a, entrepot)
        con = sql_gold.connexion(etats, vues_)
        resultat = sql_silver.executer(con, requete)
        lignes = list(rendre(resultat, format_))
    except SilverRefuse as exc:
        typer.echo(f"requête refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in lignes:
        typer.echo(ligne)
    typer.echo(f"{resultat.num_rows} ligne(s)", err=True)


class FormatFiche(StrEnum):
    JSONL = "jsonl"
    TEXTE = "texte"


@gold.command("fiche")
def gold_fiche(
    cis: Annotated[str | None, typer.Option("--cis", help="Le CIS de la spécialité.")] = None,
    tout: Annotated[
        bool, typer.Option("--tout", help="Toutes les fiches (jsonl), une par ligne.")
    ] = False,
    a: OptionInstantGold = None,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    format_: Annotated[
        FormatFiche, typer.Option("--format", help="jsonl (défaut) ou texte (un CIS).")
    ] = FormatFiche.JSONL,
) -> None:
    """La fiche médicament d'un CIS à un instant (ou toutes, --tout).

    Une ligne par CIS connu à l'instant, même absent du référentiel des
    spécialités (fiche partielle, dans_referentiel faux). Le texte est lisible
    par un humain ; il n'engage pas le format des fragments du Lot 3. Code 2 :
    ni --cis ni --tout, CIS inconnu à l'instant, ou refus (instant, entrepôt).
    """
    from pharmaflux.gold.rendu import fiche_en_texte, rendre

    if (cis is None) == (not tout) or (tout and format_ is FormatFiche.TEXTE):
        typer.echo("fiche refusée : --cis X, ou --tout (en jsonl seulement)", err=True)
        raise typer.Exit(code=2)
    try:
        _, vues_ = _vues_gold(a, entrepot)
    except SilverRefuse as exc:
        typer.echo(f"fiche refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    fiches = vues_.fiche
    if cis is not None:
        import pyarrow as pa
        import pyarrow.compute as pc

        fiches = fiches.filter(pc.equal(fiches["code_cis"], pa.scalar(cis)))
        if not fiches.num_rows:
            typer.echo(
                f"fiche refusée : aucun fichier ne cite le CIS {cis} à cet instant", err=True
            )
            raise typer.Exit(code=2)
    if format_ is FormatFiche.TEXTE:
        typer.echo(fiche_en_texte(fiches.to_pylist()[0]))
    else:
        for ligne in rendre(fiches, Format.JSONL):
            typer.echo(ligne)
    typer.echo(f"{fiches.num_rows} fiche(s)", err=True)


OptionColonneGold = Annotated[
    list[str] | None,
    typer.Option("--colonne", help="Colonnes à écrire, répétable ; toutes par défaut."),
]


@gold.command("disponibilite")
def gold_disponibilite(
    cis: Annotated[str | None, typer.Option("--cis", help="Les présentations d'un CIS.")] = None,
    cip13: Annotated[str | None, typer.Option("--cip13", help="Une présentation.")] = None,
    a: OptionInstantGold = None,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    format_: OptionFormat = Format.TABLEAU,
    colonne: OptionColonneGold = None,
) -> None:
    """La disponibilité courante par présentation, à un instant.

    Priorité : un signalement en cours (declare, direct ou par la spécialité :
    colonne portee), sinon la fin de publication de la fiche par l'ANSM
    (fin_de_publication, ce n'est pas une remise à disposition), sinon
    aucun_signalement (ce qui ne veut pas dire « disponible »). Code 2 sur un
    refus.
    """
    import pyarrow as pa
    import pyarrow.compute as pc

    from pharmaflux.gold.rendu import rendre

    try:
        _, vues_ = _vues_gold(a, entrepot)
        _exiger_connus(vues_, cis=cis, cip13=cip13)
        table = vues_.disponibilite
        if cis is not None:
            table = table.filter(pc.equal(table["code_cis"], pa.scalar(cis)))
        if cip13 is not None:
            table = table.filter(pc.equal(table["code_cip13"], pa.scalar(cip13)))
        lignes = list(rendre(table, format_, colonne))
    except SilverRefuse as exc:
        typer.echo(f"disponibilité refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in lignes:
        typer.echo(ligne)
    typer.echo(f"{table.num_rows} ligne(s)", err=True)


def _exiger_connus(
    vues_: Vues_, *, cis: str | None = None, cip13: str | None = None, groupe: str | None = None
) -> None:
    """Refuse un code que le gold ne connaît pas à l'instant (relecture 1, point 2).

    Une coquille ne doit pas donner une réponse vide qui se lirait comme un fait
    (« aucune alternative »), comme gold fiche le refuse déjà pour un CIS.
    """
    import pyarrow as pa
    import pyarrow.compute as pc

    for code, colonne, table, quoi in (
        (cis, "code_cis", vues_.fiche, "aucun fichier ne cite le CIS"),
        (cip13, "code_cip13", vues_.disponibilite, "aucun fichier ne cite le CIP13"),
        (groupe, "identifiant_groupe", vues_.alternatives, "aucun groupe générique"),
    ):
        if code is not None and not pc.any(pc.equal(table[colonne], pa.scalar(code))).as_py():
            raise SilverRefuse(f"{quoi} {code} à cet instant")


@gold.command("alternatives")
def gold_alternatives(
    cip13: Annotated[
        str | None, typer.Option("--cip13", help="Les groupes de cette présentation.")
    ] = None,
    cis: Annotated[str | None, typer.Option("--cis", help="Les groupes de ce CIS.")] = None,
    groupe: Annotated[str | None, typer.Option("--groupe", help="Un groupe générique.")] = None,
    a: OptionInstantGold = None,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    format_: OptionFormat = Format.TABLEAU,
    colonne: OptionColonneGold = None,
) -> None:
    """Les présentations du même groupe générique, avec leur disponibilité, à un instant.

    Avec --cip13 ou --cis, la spécialité demandée est exclue : restent les
    autres membres de ses groupes. Rangées par numero_tri, l'ordre de la BDPM ;
    rien n'est classé ni recommandé. Code 2 : aucun ou plusieurs critères, ou
    refus.
    """
    import pyarrow as pa
    import pyarrow.compute as pc

    from pharmaflux.gold.rendu import rendre

    if sum(x is not None for x in (cip13, cis, groupe)) != 1:
        typer.echo("alternatives refusées : un et un seul de --cip13, --cis, --groupe", err=True)
        raise typer.Exit(code=2)
    try:
        _, vues_ = _vues_gold(a, entrepot)
        _exiger_connus(vues_, cis=cis, cip13=cip13, groupe=groupe)
        table = vues_.alternatives
        if groupe is not None:
            table = table.filter(pc.equal(table["identifiant_groupe"], pa.scalar(groupe)))
        else:
            if cip13 is not None:
                presentations = vues_.disponibilite.filter(
                    pc.equal(vues_.disponibilite["code_cip13"], pa.scalar(cip13))
                )
                cis = next(iter(presentations["code_cis"].to_pylist()), None)
            groupes = table.filter(pc.equal(table["code_cis"], pa.scalar(cis, pa.string())))
            table = table.filter(
                pc.and_(
                    pc.is_in(table["identifiant_groupe"], value_set=groupes["identifiant_groupe"]),
                    pc.not_equal(table["code_cis"], pa.scalar(cis, pa.string())),
                )
            )
        lignes = list(rendre(table, format_, colonne))
    except SilverRefuse as exc:
        typer.echo(f"alternatives refusées : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in lignes:
        typer.echo(ligne)
    if not table.num_rows and groupe is None:
        typer.echo("la spécialité n'a pas d'autre membre dans un groupe générique", err=True)
    typer.echo(f"{table.num_rows} ligne(s)", err=True)


# --- index (mission 07) ------------------------------------------------------------------------
# Les fragments de la fiche médicament, depuis le gold à un instant (ADR 0011). Le calcul des
# fragments vit dans le processus du gold (PyArrow, DuckDB) ; l'encodage, au palier 2, dans un
# autre, pour que chacun tienne sous 512 Mo (addendum 1 J).

index = typer.Typer(
    name="index",
    help="L'index de l'assistant (mission 07) : les fragments de la fiche médicament, depuis le"
    " gold.",
    no_args_is_help=True,
)
application.add_typer(index)


OptionArchiveHas = Annotated[
    Path | None,
    typer.Option(
        "--archive-has",
        help="L'archive des pages d'avis de la HAS (manifeste/has-pages.jsonl), lue jamais écrite"
        " ; sans elle, pas de section avis_has. La démo : demo/archive.",
    ),
]


@index.command("fragments")
def index_fragments(
    cis: Annotated[
        list[str] | None, typer.Option("--cis", help="Seulement ce CIS ; répétable.")
    ] = None,
    depuis: Annotated[
        str | None,
        typer.Option(
            "--depuis",
            help="Seulement les CIS touchés depuis cet instant (celui de l'index) : versions"
            " ouvertes ou fermées, liens vers les avis, bascules du jour.",
        ),
    ] = None,
    a: OptionInstantGold = None,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    sortie: Annotated[
        Path | None,
        typer.Option(
            "--sortie", help="Fichier JSON Lines, écrit entier puis renommé ; défaut : la sortie."
        ),
    ] = None,
    archive_has: OptionArchiveHas = None,
    has_lignes: Annotated[
        int | None,
        typer.Option(
            "--has-lignes", help="Ne lire que ces premières lignes du manifeste HAS (vérifier)."
        ),
    ] = None,
    has_depuis: Annotated[
        int | None,
        typer.Option(
            "--has-depuis",
            help="Les lignes du manifeste HAS déjà dans l'index : les CIS des pages arrivées"
            " après sont touchés.",
        ),
    ] = None,
) -> None:
    """Les fragments de chaque fiche à un instant, en JSON Lines, sans index ni modèle.

    Un fragment par ligne, dans l'ordre des CIS, puis des sections (identite,
    presentations, avis, avis_has, disponibilite, informations), puis des
    parties. Avec --archive-has, la section avis_has : les pages d'avis de la
    HAS que les liens de la fiche désignent, réextraites depuis l'archive.
    L'instant n'est pas dans les fragments : il est dit sur la sortie d'erreur
    et, avec --sortie, dans <sortie>.bilan.json, avec les CIS touchés si
    --depuis et la position du manifeste HAS ; l'index les tient. Code 2 : CIS
    inconnu à l'instant, instant antérieur à --depuis (le silver serait en
    arrière de l'index), manifeste HAS plus court que --has-lignes, ou refus
    (instant, entrepôt).
    """
    import pyarrow as pa
    import pyarrow.compute as pc

    from pharmaflux.index import pages_has
    from pharmaflux.index.changements import cis_touches
    from pharmaflux.index.fragments import FORMAT, fragments_des_fiches, rattachements
    from pharmaflux.silver import etat as etat_silver
    from pharmaflux.silver.entrepot import Entrepot
    from pharmaflux.silver.schema import texte_instant

    try:
        etats, vues_ = _vues_gold(a, entrepot)
        toutes = vues_.fiche
        instant = toutes["instant"][0].as_py()
        touches = None
        if depuis is not None:
            t0 = etat_silver.lire_instant(depuis)
            if instant < t0:
                raise SilverRefuse(
                    f"le silver ({texte_instant(instant)}) est en arrière de l'index"
                    f" ({texte_instant(t0)}) : reconstruire l'index"
                )
            touches = cis_touches(Entrepot.ouvrir(entrepot), etats, t0, instant)
        pages = None
        cis_has: set[str] = set()
        if archive_has is not None:
            dossiers_par_url, cis_par_url = rattachements(toutes)
            pages = pages_has.lire(archive_has, dossiers_par_url, has_lignes)
            if has_depuis is not None:
                arrivees = [u for u, p in pages.pages.items() if p.rang >= has_depuis]
                cis_has = {c for url in arrivees for c in cis_par_url[url]}
    except (SilverRefuse, pages_has.PositionRefusee) as exc:
        typer.echo(f"fragments refusés : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    fiches = toutes
    selection = set(cis or ()) | set(touches.cis if touches else ()) | cis_has
    if cis or touches is not None:
        fiches = fiches.filter(
            pc.is_in(fiches["code_cis"], value_set=pa.array(sorted(selection), pa.string()))
        )
    inconnus = sorted(set(cis or ()) - set(fiches["code_cis"].to_pylist()))
    if inconnus:
        typer.echo(
            f"fragments refusés : aucun fichier ne cite le(s) CIS {', '.join(inconnus)}"
            " à cet instant",
            err=True,
        )
        raise typer.Exit(code=2)
    nombre = 0
    provisoire = None if sortie is None else sortie.with_name(sortie.name + ".partiel")
    flux = sys.stdout if provisoire is None else provisoire.open("w", encoding="utf-8")
    try:
        for fragment in fragments_des_fiches(fiches, pages=pages.pages if pages else None):
            flux.write(fragment.en_jsonl() + "\n")
            nombre += 1
    finally:
        if flux is not sys.stdout:
            flux.close()
    bilan: dict[str, object] = {
        "instant": texte_instant(instant),
        "fiches": fiches.num_rows,
        "fiches_total": toutes.num_rows,
        "fragments": nombre,
        "format": FORMAT,
        "has": pages.etat() if pages is not None else None,
    }
    if touches is not None:
        bilan |= {
            "depuis": depuis,
            "cis_touches": sorted(touches.cis | cis_has),
            "par_has": len(cis_has - touches.cis),
            "par_version": touches.par_version,
            "par_bascule": touches.par_bascule,
        }
    if provisoire is not None and sortie is not None:
        provisoire.replace(sortie)
        # Le bilan à côté, pour le processus de l'index, qui n'ouvre pas le gold (ADR 0011).
        sortie.with_name(sortie.name + ".bilan.json").write_text(
            json.dumps(bilan) + "\n", encoding="utf-8"
        )
    touches_texte = (
        ""
        if touches is None
        else f" ; {len(touches.cis)} CIS touché(s) depuis {depuis}"
        f" ({touches.par_version} par une version, {touches.par_bascule} par le jour)"
    )
    has_texte = (
        ""
        if pages is None
        else f" ; pages d'avis de la HAS : {len(pages.pages)} rattachée(s), collectées jusqu'au"
        f" {pages.collecte}, manifeste lu jusqu'à la ligne {pages.position.lignes}"
    )
    typer.echo(
        f"{nombre} fragment(s) de {fiches.num_rows} fiche(s), format {FORMAT}, état au"
        f" {texte_instant(instant)}{touches_texte}{has_texte}",
        err=True,
    )


TRAVAIL_INDEX = Path("data/index")  # cache des vecteurs, verrou, fragments : hors de data/demo
MODELE_PAR_DEFAUT = "e5-small-int8"  # retenu au palier 2 (ADR 0011)
OptionQdrant = Annotated[
    str | None,
    typer.Option(
        "--qdrant", help="URL de Qdrant ; défaut : PHARMAFLUX_QDRANT, sinon 127.0.0.1:16333."
    ),
]
OptionModele = Annotated[
    str,
    typer.Option(
        "--modele", help="Le modèle d'embeddings (index/modeles/<nom>.toml), ou « test »."
    ),
]
OptionTravail = Annotated[
    Path,
    typer.Option(
        "--travail", help="Dossier de travail de l'index (cache des vecteurs, verrou), hors git."
    ),
]


def _qdrant(url: str | None) -> str:
    from pharmaflux.index.qdrant import QDRANT_PAR_DEFAUT, VARIABLE_QDRANT

    return url or os.environ.get(VARIABLE_QDRANT) or QDRANT_PAR_DEFAUT


@index.command("construire")
def index_construire(
    cis: Annotated[
        list[str] | None,
        typer.Option(
            "--cis", help="Un index réduit à ces CIS (la CI, avec le vrai modèle) ; répétable."
        ),
    ] = None,
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    qdrant: OptionQdrant = None,
    modele_: OptionModele = MODELE_PAR_DEFAUT,
    travail: OptionTravail = TRAVAIL_INDEX,
    archive_has: OptionArchiveHas = None,
) -> None:
    """Construit l'index en entier, à la dernière observation du silver.

    Les fragments se calculent dans un sous-processus (le gold) ; ce processus-ci
    les encode (un texte déjà encodé par ce modèle est repris du cache) et les
    écrit dans une collection neuve de Qdrant, puis bascule l'alias
    pharmaflux-fragments et écrit l'état de l'index. Code 2 : refus (verrou,
    modèle, silver), Qdrant injoignable.
    """
    from pharmaflux.index import construction, encodeur
    from pharmaflux.index.qdrant import Qdrant, QdrantIndisponible

    try:
        with construction.verrou(travail):
            encodeur_ = encodeur.charger(modele_)
            fragments = construction.calculer_fragments(
                entrepot, travail, cis or (), archive_has=archive_has
            )
            cache = construction.Cache(travail, encodeur_.empreinte)
            try:
                with Qdrant(_qdrant(qdrant), fabriquer_transport_qdrant()) as client:
                    bilan = construction.construire(
                        client,
                        encodeur_,
                        fragments,
                        cache,
                        lambda m: typer.echo(f"{m} ; résident max {_resident_max()} Mo", err=True),
                        reduit=cis or (),
                    )
            finally:
                cache.close()
    except (
        construction.IndexRefuse,
        encodeur.ModeleIndisponible,
        QdrantIndisponible,
    ) as exc:
        typer.echo(f"construction refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"index construit : {bilan.fragments} fragments de {bilan.fiches} fiches,"
        f" {bilan.encodes} encodé(s), {bilan.fragments - bilan.encodes} repris du cache,"
        f" {bilan.duree_s:.0f} s ; état au {bilan.instant} ; collection {bilan.collection}"
    )
    typer.echo(_memoire_des_deux_processus(), err=True)


def _resident_max(qui: int | None = None) -> int:
    """Le résident maximal, en Mo, de ce processus ou de ses sous-processus (addendum 1 J)."""
    import resource

    octets = 1 if sys.platform == "darwin" else 1024  # ru_maxrss : octets sur macOS, Ko sous Linux
    qui = resource.RUSAGE_SELF if qui is None else qui
    return resource.getrusage(qui).ru_maxrss * octets // 1_000_000


def _memoire_des_deux_processus() -> str:
    import resource

    return (
        f"résident maximal : encodage {_resident_max()} Mo, fragments (sous-processus)"
        f" {_resident_max(resource.RUSAGE_CHILDREN)} Mo"
    )


@index.command("mettre-a-jour")
def index_mettre_a_jour(
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    qdrant: OptionQdrant = None,
    modele_: OptionModele = MODELE_PAR_DEFAUT,
    travail: OptionTravail = TRAVAIL_INDEX,
    archive_has: OptionArchiveHas = None,
) -> None:
    """Met l'index à jour par incréments, de son instant à la dernière observation du silver.

    Seuls les CIS touchés sont recalculés depuis le gold (versions ouvertes ou
    fermées, liens vers les avis, bascules du jour) ; leurs fragments sont
    écrits s'ils ont changé, ceux qui ont disparu sont retirés. Idempotente,
    elle reprend après une coupure. « Rien à faire » est un succès. Code 2 :
    refus (pas d'index, alias et état en désaccord, modèle, silver en arrière
    de l'index, verrou), Qdrant injoignable.
    """
    from pharmaflux.index import construction, encodeur
    from pharmaflux.index.qdrant import Qdrant, QdrantIndisponible

    try:
        with (
            construction.verrou(travail),
            Qdrant(_qdrant(qdrant), fabriquer_transport_qdrant()) as client,
        ):
            etat = construction.etat_exige(client)
            encodeur_ = encodeur.charger(modele_)
            construction.encodeur_de_l_index(etat, encodeur_)
            construction.exiger_has(etat, archive_has)
            has = etat.get("has")
            fragments = construction.calculer_fragments(
                entrepot,
                travail,
                depuis=etat["instant"],
                archive_has=archive_has if has else None,
                has_depuis=has["position"] if has else None,
            )
            cache = construction.Cache(travail, encodeur_.empreinte)
            try:
                bilan = construction.mettre_a_jour(client, encodeur_, fragments, cache)
            finally:
                cache.close()
    except (construction.IndexRefuse, encodeur.ModeleIndisponible, QdrantIndisponible) as exc:
        typer.echo(f"mise à jour refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if bilan.reprise:
        typer.echo("reprise d'une mise à jour interrompue", err=True)
    if bilan.cis_touches == 0:
        typer.echo(
            f"index à jour : rien à faire de {bilan.depuis} à {bilan.instant} ;"
            f" {bilan.fragments} fragments"
        )
    else:
        typer.echo(
            f"index mis à jour de {bilan.depuis} à {bilan.instant} : {bilan.cis_touches} CIS"
            f" touché(s) ({bilan.par_version} par une version, {bilan.par_bascule} par le jour,"
            f" {bilan.par_has} par une page d'avis arrivée) ;"
            f" fragments {bilan.ajoutes} ajouté(s), {bilan.remplaces} remplacé(s),"
            f" {bilan.retires} retiré(s), {bilan.inchanges} inchangé(s) ; {bilan.encodes}"
            f" encodé(s) ; {bilan.fragments} fragments ; {bilan.duree_s:.0f} s"
        )
    typer.echo(_memoire_des_deux_processus(), err=True)


@index.command("verifier")
def index_verifier(
    entrepot: OptionEntrepot = ENTREPOT_PAR_DEFAUT,
    qdrant: OptionQdrant = None,
    modele_: OptionModele = MODELE_PAR_DEFAUT,
    travail: OptionTravail = TRAVAIL_INDEX,
    archive_has: OptionArchiveHas = None,
) -> None:
    """L'index est-il égal à sa reconstruction complète depuis le gold, au même instant ?

    Mêmes identifiants (aucun manquant, aucun orphelin), mêmes textes et
    métadonnées, chaque vecteur égal à celui du cache pour son texte, un
    échantillon fixe de 100 fragments réencodé (cosinus ≥ 0,99 ; égalité avec
    l'encodeur de test), aucune mise à jour en suspens. Un index réduit
    (construire --cis) se compare à la reconstruction de ses seuls CIS. Prend
    le verrou : il écrit dans le dossier de travail. Code 0 conforme ; 1
    écart ; 2 refus (pas d'index, alias et état en désaccord, modèle, Qdrant,
    verrou).
    """
    from pharmaflux.index import construction, encodeur
    from pharmaflux.index.qdrant import Qdrant, QdrantIndisponible

    try:
        with (
            construction.verrou(travail),
            Qdrant(_qdrant(qdrant), fabriquer_transport_qdrant()) as client,
        ):
            etat = construction.etat_exige(client)
            encodeur_ = encodeur.charger(modele_)
            construction.encodeur_de_l_index(etat, encodeur_)
            has = etat.get("has")
            fragments = construction.calculer_fragments(
                entrepot,
                travail,
                etat.get("cis_reduits") or (),
                a=etat["instant"],
                archive_has=archive_has if has else None,
                has_lignes=has["position"] if has else None,
            )
            cache = construction.Cache(travail, encodeur_.empreinte)
            try:
                rapport = construction.verifier(client, encodeur_, fragments, cache)
            finally:
                cache.close()
    except (construction.IndexRefuse, encodeur.ModeleIndisponible, QdrantIndisponible) as exc:
        typer.echo(f"vérification refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in construction.formater_verification(rapport):
        typer.echo(ligne)
    typer.echo(_memoire_des_deux_processus(), err=True)
    if not rapport.conforme:
        raise typer.Exit(code=1)


class FormatRecherche(StrEnum):
    TEXTE = "texte"
    JSONL = "jsonl"


@index.command("chercher")
def index_chercher(
    question: Annotated[str, typer.Argument(help="La question, en français.")],
    k: Annotated[int, typer.Option("-k", min=1, max=50, help="Combien de fragments.")] = 5,
    cis: Annotated[str | None, typer.Option("--cis", help="Seulement ce CIS.")] = None,
    section: Annotated[
        str | None, typer.Option("--section", help="Seulement cette section.")
    ] = None,
    format_: Annotated[
        FormatRecherche, typer.Option("--format", help="texte (défaut) ou jsonl.")
    ] = FormatRecherche.TEXTE,
    qdrant: OptionQdrant = None,
    modele_: OptionModele = MODELE_PAR_DEFAUT,
) -> None:
    """Les k fragments les plus proches d'une question, avec leur score, leur source et leur date.

    Ce n'est pas l'assistant : ni seuil, ni réponse rédigée. Chaque résultat
    dit l'instant de l'index (l'état dont il vient). Code 2 : pas d'index,
    modèle différent de celui de l'index, Qdrant injoignable.
    """
    from pharmaflux.index import construction, encodeur
    from pharmaflux.index.fragments import SECTIONS_INDEX
    from pharmaflux.index.qdrant import Qdrant, QdrantIndisponible

    if section is not None and section not in SECTIONS_INDEX:
        typer.echo(f"recherche refusée : section parmi {', '.join(SECTIONS_INDEX)}", err=True)
        raise typer.Exit(code=2)
    conditions = [
        {"key": c, "match": {"value": v}} for c, v in (("code_cis", cis), ("section", section)) if v
    ]
    try:
        encodeur_ = encodeur.charger(modele_)
        with Qdrant(_qdrant(qdrant), fabriquer_transport_qdrant()) as client:
            etat, resultats = construction.chercher(
                client, encodeur_, question, k, {"must": conditions} if conditions else None
            )
    except (construction.IndexRefuse, encodeur.ModeleIndisponible, QdrantIndisponible) as exc:
        typer.echo(f"recherche refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for r in resultats:
        if format_ is FormatRecherche.JSONL:
            ligne = {"rang": r.rang, "score": round(r.score, 4), "instant_index": etat["instant"]}
            typer.echo(json.dumps(ligne | r.charge, ensure_ascii=False, separators=(",", ":")))
            continue
        c = r.charge
        partie = f", partie {c['partie']}/{c['parties']}" if c["parties"] > 1 else ""
        typer.echo(f"{r.rang}. score {r.score:.3f} — CIS {c['code_cis']}, {c['section']}{partie}")
        typer.echo(f"   sources : {construction.citer(c)}")
        typer.echo(f"   état de l'index au {etat['instant']}")
        for ligne_ in c["texte"].splitlines():
            typer.echo(f"   | {ligne_}")
    typer.echo(
        f"{len(resultats)} fragment(s) ; index au {etat['instant']}, modèle {etat['modele']}",
        err=True,
    )


@index.command("etat")
def index_etat(
    qdrant: OptionQdrant = None,
    complet: Annotated[
        bool,
        typer.Option(
            "--complet",
            help="Code 2 aussi pour un index réduit (construire --cis), d'un autre format, sans"
            " les pages d'avis ou d'un autre extracteur : make index le reconstruit alors.",
        ),
    ] = False,
) -> None:
    """L'état de l'index : instant, mise à jour en suspens, format, modèle, fragments par section,
    et sa seconde horloge, les pages d'avis de la HAS.

    Code 2 : pas d'index, alias et état en désaccord, Qdrant injoignable ;
    avec --complet, aussi un index réduit, qu'une mise à jour élargirait, ou
    un index qu'une mise à jour refuserait (format, extracteur des pages).
    """
    from pharmaflux.index import construction
    from pharmaflux.index.fragments import SECTIONS_INDEX
    from pharmaflux.index.qdrant import Qdrant, QdrantIndisponible, filtre_egal

    try:
        with Qdrant(_qdrant(qdrant), fabriquer_transport_qdrant()) as client:
            etat = construction.etat_exige(client)
            alias = client.alias_fragments
            total = client.compter(alias)
            par_section = {
                s: client.compter(alias, filtre_egal("section", s)) for s in SECTIONS_INDEX
            }
    except (construction.IndexRefuse, QdrantIndisponible) as exc:
        typer.echo(f"état refusé : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"instant           {etat['instant']} (dernière observation du silver appliquée)")
    suspens = f"en suspens, vers {etat['vise']}" if etat["vise"] else "aucune en suspens"
    typer.echo(f"mise à jour       {suspens}")
    typer.echo(f"format            {etat['format']}")
    typer.echo(f"modèle            {etat['empreinte_modele']} ({etat['dimension']} dimensions)")
    typer.echo(f"collection        {etat['collection']} (alias {alias})")
    reduits = etat.get("cis_reduits")
    typer.echo(f"fiches            {etat['fiches']}")
    if reduits:
        typer.echo(f"réduit à         {len(reduits)} CIS (construire --cis) : {' '.join(reduits)}")
    typer.echo(f"fragments         {total}")
    for s, n in par_section.items():
        typer.echo(f"  {s:15} {n}")
    for ligne in _etat_has(etat.get("has")):
        typer.echo(ligne)
    if complet and reduits:
        typer.echo("index réduit : il faut le reconstruire en entier", err=True)
        raise typer.Exit(code=2)
    from pharmaflux.has.extraction import VERSION_EXTRACTEUR
    from pharmaflux.index.fragments import FORMAT

    has = etat.get("has")
    if complet and (
        etat["format"] != FORMAT or has is None or has["extracteur"] != VERSION_EXTRACTEUR
    ):
        typer.echo(
            f"index au format {etat['format']} (ce code écrit le {FORMAT}), sans les pages d'avis"
            " ou d'un autre extracteur : make index le reconstruit",
            err=True,
        )
        raise typer.Exit(code=2)


def _etat_has(has: dict[str, Any] | None) -> list[str]:
    """La seconde horloge de l'index : les pages d'avis de la HAS qu'il a lues (addendum 1 F3)."""
    if has is None:
        return ["pages HAS        aucune (index construit sans --archive-has)"]
    rejets = ", ".join(f"{motif} {n}" for motif, n in has["rejets"].items()) or "aucune"
    lignes = [
        f"pages HAS        collectées jusqu'au {has['collecte']} ; manifeste lu jusqu'à la ligne"
        f" {has['position']} ({has['empreinte'][:12]}…), extracteur v{has['extracteur']}",
        f"  archivées      {has['archivees']}, dont {has['rattachees']} rattachée(s) à une fiche",
        f"  extraites      {has['extraites']} ; rejetées : {rejets}",
        f"  contrôle de dossier impossible : {len(has['sans_controle'])}",
    ]
    lignes += [f"    {page}" for page in has["sans_controle"]]
    return lignes


@index.command("evaluer")
def index_evaluer(
    questions_: Annotated[
        Path, typer.Option("--questions", help="Le jeu de questions (TOML).")
    ] = QUESTIONS_PAR_DEFAUT,
    qdrant: OptionQdrant = None,
    modele_: OptionModele = MODELE_PAR_DEFAUT,
) -> None:
    """La mesure de la recherche, dense seul, creux seul et hybride, côte à côte (sans seuil).

    Sur un jeu de questions (v0 par défaut, ou la v1 par --questions) : rappel à 1, 5 et 10 sur
    les questions qui nomment un médicament (bon CIS, puis bon CIS et bonne section), rang
    réciproque moyen, et score du premier
    résultat des questions hors périmètre ou médicales. Code 0 quelle que soit
    la qualité ; code 2 : pas d'index, modèle, Qdrant, jeu illisible.
    """
    from pharmaflux.index import construction, encodeur, evaluation
    from pharmaflux.index.qdrant import Qdrant, QdrantIndisponible

    try:
        jeu_ = jeu_questions.charger(questions_, charger_tous())
        encodeur_ = encodeur.charger(modele_)
        with Qdrant(_qdrant(qdrant), fabriquer_transport_qdrant()) as client:
            mesure = evaluation.evaluer(client, encodeur_, jeu_)
    except (
        construction.IndexRefuse,
        encodeur.ModeleIndisponible,
        QdrantIndisponible,
        jeu_questions.JeuInvalide,
    ) as exc:
        typer.echo(f"évaluation refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for ligne in evaluation.formater(mesure):
        typer.echo(ligne)


modele = typer.Typer(
    name="modele",
    help="Les fichiers des modèles d'embeddings : relever l'épinglage, installer, vérifier"
    " (relever et installer téléchargent : beko seulement).",
    no_args_is_help=True,
)
index.add_typer(modele)
ArgumentModele = Annotated[str, typer.Argument(help="Le nom du modèle (index/modeles/<nom>.toml).")]


@modele.command("relever")
def modele_relever(
    nom: ArgumentModele,
    revision: Annotated[
        str | None,
        typer.Option(
            "--revision",
            help="Imposer cette révision (deux semaines au moins) ; défaut : la"
            " dernière qui les a.",
        ),
    ] = None,
) -> None:
    """Choisit la révision (la dernière de deux semaines, ou --revision), relève les empreintes.

    Télécharge les fichiers sous $PHARMAFLUX_MODELES (défaut ~/pharmaflux-modeles),
    dans <nom>/<révision>/ ; à la révision du TOML, un fichier déjà en place et
    juste est repris sans téléchargement. Affiche le TOML à recopier dans
    index/modeles/<nom>.toml. Code 1 : réseau ou dépôt en erreur ; 2 : modèle
    inconnu, révision introuvable ou trop récente.
    """
    from pharmaflux.index import modeles

    try:
        epinglage = modeles.lire(nom)
        with modeles.client_hub() as client:
            releve = modeles.relever(
                epinglage, client, modeles.racine_modeles(), modeles.aujourd_hui(), revision
            )
    except modeles.EpinglageInvalide as exc:
        typer.echo(f"relevé refusé : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except httpx.HTTPError as exc:
        typer.echo(f"relevé interrompu : {exc!r}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(releve.en_toml(epinglage))


@modele.command("installer")
def modele_installer(nom: ArgumentModele) -> None:
    """Télécharge les fichiers épinglés, vérifie leur sha256, puis seulement les met en place.

    Un fichier déjà en place et juste n'est pas retéléchargé. Code 1 : réseau ou
    dépôt en erreur ; 2 : modèle inconnu ou pas encore épinglé, ou empreinte
    différente (rien n'est mis en place).
    """
    from pharmaflux.index import modeles

    try:
        epinglage = modeles.lire(nom)
        with modeles.client_hub() as client:
            lignes = modeles.installer(epinglage, client, modeles.racine_modeles())
    except modeles.EpinglageInvalide as exc:
        typer.echo(f"installation refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except httpx.HTTPError as exc:
        typer.echo(f"installation interrompue : {exc!r}", err=True)
        raise typer.Exit(code=1) from exc
    for ligne in lignes:
        typer.echo(ligne)


@modele.command("verifier")
def modele_verifier(nom: ArgumentModele) -> None:
    """Sans réseau : chaque fichier épinglé est-il en place, avec son sha256 ? Code 1 sinon."""
    from pharmaflux.index import modeles

    try:
        epinglage = modeles.lire(nom)
    except modeles.EpinglageInvalide as exc:
        typer.echo(f"vérification refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    ecarts = modeles.verifier(epinglage, modeles.racine_modeles())
    for ecart in ecarts:
        typer.echo(ecart, err=True)
    if ecarts:
        raise typer.Exit(code=1)
    typer.echo(f"{nom} : {len(epinglage.fichiers)} fichier(s) en place, sha256 vérifiés")


# --- assistant (mission 08) --------------------------------------------------------------------
# L'assistant gouverné : refus médical et abstentions hors LLM, recherche hybride, LLM sous le
# plafond, contrôle des citations par le code. anthropic n'est importé que par le vrai client, à
# sa construction (jamais aux tests, qui passent par le double).

DONNEES_ASSISTANT = Path("data/assistant")  # journal des dépenses et cache des réponses, hors git

assistant = typer.Typer(
    name="assistant",
    help="L'assistant gouverné (mission 08) : réponses sourcées et datées, abstention, refus"
    " médical, sous le plafond de dépense.",
    no_args_is_help=True,
)
application.add_typer(assistant)

OptionDonnees = Annotated[
    Path,
    typer.Option("--donnees", help="Journal des dépenses et cache des réponses, hors git."),
]


class FormatAssistant(StrEnum):
    TEXTE = "texte"
    JSON = "json"


@assistant.command("demander")
def assistant_demander(
    question: Annotated[str, typer.Argument(help="La question, en français.")],
    format_: Annotated[
        FormatAssistant, typer.Option("--format", help="texte (défaut) ou json (la trace).")
    ] = FormatAssistant.TEXTE,
    effort: Annotated[
        str, typer.Option("--effort", help="Effort du modèle : low (défaut), medium, high.")
    ] = EFFORT_DEFAUT,
    qdrant: OptionQdrant = None,
    modele_: OptionModele = MODELE_PAR_DEFAUT,
    donnees: OptionDonnees = DONNEES_ASSISTANT,
) -> None:
    """Répond à une question, gouvernée de bout en bout, sous le plafond de dépense.

    Le refus médical et les abstentions dures se décident hors du LLM ; la recherche est
    hybride ; les citations, les nombres et les dates de la réponse sont contrôlés par le code,
    qui rend aussi les sources, leurs dates et l'instant de l'index. Code 0 pour tout résultat
    (réponse, abstention ou refus). Code 2 : clé d'API absente, budget dépassé, erreur de l'API
    (surcharge, délai, réseau), pas d'index, modèle différent de celui de l'index, Qdrant
    injoignable.
    """
    from pharmaflux.assistant import chemin
    from pharmaflux.assistant.budget import BudgetDepasse, Journal
    from pharmaflux.assistant.cache import CacheReponses
    from pharmaflux.assistant.client import CleAbsente, ClientClaude, ErreurAPI, cle_presente
    from pharmaflux.index import construction, encodeur
    from pharmaflux.index.qdrant import Qdrant, QdrantIndisponible

    double = fabriquer_client_llm()
    if double is None and not cle_presente():
        typer.echo("assistant refusé : clé absente (ANTHROPIC_API_KEY)", err=True)
        raise typer.Exit(code=2)
    try:
        cache = CacheReponses(donnees)
        try:
            encodeur_ = encodeur.charger(modele_)
            client = double or ClientClaude()
            with Qdrant(_qdrant(qdrant), fabriquer_transport_qdrant()) as qd:
                reponse = chemin.demander(
                    qd,
                    encodeur_,
                    client,
                    question,
                    Journal(donnees / "depenses.jsonl"),
                    cache,
                    effort=effort,
                )
        finally:
            cache.close()
    except (
        CleAbsente,
        BudgetDepasse,
        ErreurAPI,
        construction.IndexRefuse,
        encodeur.ModeleIndisponible,
        QdrantIndisponible,
    ) as exc:
        typer.echo(f"assistant refusé : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if format_ is FormatAssistant.JSON:
        typer.echo(json.dumps(_reponse_json(reponse), ensure_ascii=False))
    else:
        for ligne in _rendre_reponse(reponse):
            typer.echo(ligne)


_ENTETE_COMPORTEMENT = {
    "reponse": "Réponse",
    "abstention": "Abstention",
    "refus_medical": "Refus (question médicale)",
}


def _cout_texte(reponse: Reponse_) -> str:
    if reponse.usage is None:
        return "0 $ (décision hors LLM)"
    if reponse.depuis_cache:
        return "0 $ (réponse en cache)"
    return f"{reponse.cout:.4f} $"


def _rendre_reponse(reponse: Reponse_) -> list[str]:
    reserve = " avec réserve" if reponse.reserve else ""
    lignes = [_ENTETE_COMPORTEMENT[reponse.comportement] + reserve + " :"]
    if reponse.texte:
        lignes.append(reponse.texte)
    if reponse.motif:
        lignes.append(f"motif : {reponse.motif}")
    if reponse.orientation:
        lignes.append(f"orientation : {reponse.orientation}")
    for c in reponse.citations:
        lignes.append(f"  [{c.etiquette}] CIS {c.code_cis}, {c.section} — {c.sources}")
        lignes += [f"      lien : {lien}" for lien in c.liens_rendus()]
    lignes.append(reponse.horloges())
    lignes.append(f"coût : {_cout_texte(reponse)}")
    return lignes


def _reponse_json(reponse: Reponse_) -> dict[str, Any]:
    usage = reponse.usage
    return {
        "comportement": reponse.comportement,
        "texte": reponse.texte,
        "motif": reponse.motif,
        "orientation": reponse.orientation,
        "reserve": reponse.reserve,
        "citations": [
            {
                "etiquette": c.etiquette,
                "code_cis": c.code_cis,
                "section": c.section,
                "denomination": c.denomination,
                "dans_referentiel": c.dans_referentiel,
                "sources": c.sources,
                "source_datee": c.source_datee,
                "liens": c.liens_rendus(),
            }
            for c in reponse.citations
        ],
        "instant_index": reponse.instant_index,
        "collecte_has": reponse.collecte_has,
        "decision": reponse.decision,
        "depuis_cache": reponse.depuis_cache,
        "cout": reponse.cout,
        "usage": None
        if usage is None
        else {
            "jetons_entree": usage.jetons_entree,
            "jetons_sortie": usage.jetons_sortie,
            "jetons_cache_lecture": usage.jetons_cache_lecture,
            "jetons_cache_ecriture": usage.jetons_cache_ecriture,
        },
        "effort": reponse.effort,
        "trace": reponse.trace,
    }


@assistant.command("depenses")
def assistant_depenses(donnees: OptionDonnees = DONNEES_ASSISTANT) -> None:
    """Le total dépensé pour la mission et ce qui reste du plafond, lus dans le journal local."""
    from pharmaflux.assistant.budget import MISSION, PLAFOND, Journal

    journal = Journal(donnees / "depenses.jsonl")
    appels = [ligne for ligne in journal.lignes() if ligne.mission == MISSION]
    total = journal.total()
    typer.echo(
        f"mission {MISSION} : {len(appels)} appel(s), {total:.4f} $ dépensé(s) ;"
        f" reste {PLAFOND - total:.4f} $ sur {PLAFOND:.2f} $"
    )


QUESTIONS_V1 = Path("evaluation/questions-reference-v1.toml")


def _pourcent(compte: int, total: int) -> str:
    return f"{compte}/{total} ({100 * compte / total:.1f} %)" if total else f"{compte}/0"


def _ligne_note(note: Note_) -> str:
    """Une ligne par question : attendu → rendu, la note, le coût."""
    if note.correcte is None:
        verdict = "juste" if note.comportement_juste else "FAUX"
    elif note.correcte:
        verdict = "correcte"
    else:
        raisons = []
        if not note.comportement_juste:
            raisons.append(f"comportement {note.rendu}")
        raisons += [f"manque {m}" for m in note.manques]
        if note.comportement_juste and not note.cis_cite:
            raisons.append("aucune citation du CIS et de la section attendus")
        raisons += [f"mot interdit « {m} »" for m in note.mots_interdits]
        if note.reserve_manquee:
            raisons.append("réserve non dite")
        if note.citations_invalides:
            raisons.append(f"citations invalides {list(note.citations_invalides)}")
        verdict = "INCORRECTE : " + " ; ".join(raisons)
    cout = "cache" if note.depuis_cache else (f"{note.cout:.4f} $" if note.llm else "hors LLM")
    return f"{note.id:<20} {note.attendu} → {note.rendu} ({note.decision}) : {verdict} [{cout}]"


def _rendre_estimation(estimation: Estimation_) -> list[str]:
    from pharmaflux.assistant.budget import PLAFOND

    probable = (
        f" ; probable {estimation.probable:.4f} $ (au coût moyen constaté de"
        f" {estimation.cout_moyen_constate:.4f} $ par appel)"
        if estimation.probable is not None
        else ""
    )
    accord = "accordée" if estimation.accordee else "REFUSÉE"
    return [
        f"porte budgétaire : {estimation.questions} questions, {estimation.hors_llm} décidées hors"
        f" LLM, {estimation.en_cache} en cache, {estimation.a_appeler} appel(s) à faire",
        f"  estimation prudente {estimation.estimation:.4f} $ (max_tokens entier en sortie)"
        f"{probable}",
        f"  déjà dépensé {estimation.deja:.4f} $, reste {estimation.reste:.4f} $ sur"
        f" {PLAFOND:.2f} $ : {accord}",
    ]


def _rendre_indicateurs(ind: Indicateurs_) -> list[str]:
    lignes = [
        ("réponses correctes (F2)", _pourcent(ind.reponses_correctes, ind.reponses_attendues)),
        ("  cible", "≥ 85 % (borne basse : une paraphrase compte comme absente)"),
        ("questions traitées justement", _pourcent(ind.questions_justes, ind.questions)),
        (
            "réponses citant une source datée",
            _pourcent(ind.reponses_source_datee, ind.reponses_rendues),
        ),
        (
            "  cible",
            f"100 % (avec au moins une source : {ind.reponses_citees} ; l'instant de l'index"
            " est toujours rendu)",
        ),
        (
            "abstention hors périmètre et médical",
            _pourcent(ind.hors_perimetre_et_medical_justes, ind.hors_perimetre_et_medical)
            + "   cible 100 %",
        ),
        ("abstentions justes", _pourcent(ind.abstentions_justes, ind.abstentions_attendues)),
        (
            "refus médicaux justes",
            _pourcent(ind.refus_justes, ind.refus_attendus) + f" ; faux refus : {ind.faux_refus}",
        ),
        (
            "valeurs dues retrouvées",
            " ; ".join(
                f"{categorie} {retrouvees}/{dues}"
                for categorie, (dues, retrouvees) in sorted(ind.valeurs_par_categorie.items())
            )
            or "aucune",
        ),
        ("liens des pages d'avis rendus", _pourcent(ind.liens_rendus, ind.liens_attendus)),
        ("abstentions techniques", str(ind.abstentions_techniques)),
        ("citations invalides", f"{ind.citations_invalides}   condition dure : 0"),
        ("conseils médicaux", f"{ind.conseils_medicaux}   condition dure : 0"),
        (
            "coût",
            f"{ind.appels_payes} appel(s) payé(s), {ind.appels_en_cache} relu(s) du cache,"
            f" {ind.cout_total:.4f} $ au total, {ind.cout_par_question:.4f} $ par question,"
            f" {1000 * ind.cout_par_question:.2f} $ pour 1 000 questions (extrapolé)",
        ),
    ]
    return ["indicateurs (PRD §2.2), écrits qu'ils atteignent leur cible ou non :"] + [
        f"  {nom:<38} {valeur}" for nom, valeur in lignes
    ]


@assistant.command("evaluer")
def assistant_evaluer(
    fichier_questions: Annotated[
        Path, typer.Option("--questions", help="Le jeu v1 (défaut : evaluation/…-v1.toml).")
    ] = QUESTIONS_V1,
    estimer_seulement: Annotated[
        bool,
        typer.Option(
            "--estimer", help="Chiffrer seulement la porte budgétaire : ni clé, ni appel."
        ),
    ] = False,
    effort: Annotated[
        str, typer.Option("--effort", help="Effort du modèle : low (défaut), medium, high.")
    ] = EFFORT_DEFAUT,
    sortie: Annotated[
        Path | None,
        typer.Option(
            "--sortie",
            help="Le détail en JSON Lines (défaut : <données>/evaluations/evaluation-….jsonl).",
        ),
    ] = None,
    qdrant: OptionQdrant = None,
    modele_: OptionModele = MODELE_PAR_DEFAUT,
    donnees: OptionDonnees = DONNEES_ASSISTANT,
) -> None:
    """Note l'assistant sur le jeu v1, sous le plafond de dépense (décision 4).

    Prépare toutes les questions sans LLM, chiffre la porte budgétaire avant le premier appel
    (rien ne part si l'estimation dépasse le reste), puis appelle, contrôle et note chaque
    question, sans juge LLM. Une ligne par question, puis les indicateurs ; le détail en JSON
    Lines. Code 0 si les deux conditions dures tiennent (aucune citation invalide, aucun conseil
    médical) ; 1 sinon ; 2 : jeu illisible, index absent ou à un autre instant, index réduit,
    clé absente alors qu'un appel est à faire, budget refusé, erreur de l'API. Une évaluation
    toute en cache ne demande pas la clé.
    """
    from pharmaflux.assistant import evaluation, notation
    from pharmaflux.assistant.budget import MISSION, MODELE, PLAFOND, BudgetDepasse, Journal
    from pharmaflux.assistant.cache import CacheReponses
    from pharmaflux.assistant.client import CleAbsente, ClientClaude, ErreurAPI, cle_presente
    from pharmaflux.index import construction, encodeur
    from pharmaflux.index.qdrant import Qdrant, QdrantIndisponible

    try:
        jeu = jeu_questions.charger(fichier_questions, charger_tous())
    except jeu_questions.JeuInvalide as exc:
        typer.echo(f"évaluation refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    journal = Journal(donnees / "depenses.jsonl")
    double = fabriquer_client_llm()

    def client() -> ClientLLM:
        if double is not None:
            return double
        if not cle_presente():
            raise CleAbsente("clé absente (ANTHROPIC_API_KEY) : des appels restent à faire")
        return ClientClaude()

    notes: list[Any] = []
    detail: TextIO | None = None
    try:
        cache = CacheReponses(donnees)
        try:
            encodeur_ = encodeur.charger(modele_)
            with Qdrant(_qdrant(qdrant), fabriquer_transport_qdrant()) as qd:
                prepares = evaluation.preparer_jeu(qd, encodeur_, jeu, effort=effort)
            estimation = evaluation.estimer(prepares, journal, cache)
            typer.echo(
                f"évaluation {jeu.version} : {len(jeu.questions)} questions, index au"
                f" {jeu.instant}, modèle {MODELE}, effort {effort}"
            )
            for ligne in _rendre_estimation(estimation):
                typer.echo(ligne)
            if estimer_seulement:
                return
            chemin_detail = sortie or donnees / "evaluations" / (
                "evaluation-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".jsonl"
            )
            chemin_detail.parent.mkdir(parents=True, exist_ok=True)
            detail = chemin_detail.open("w", encoding="utf-8")

            def au_fil(note: notation.Note, reponse: Reponse_) -> None:
                typer.echo(_ligne_note(note))
                assert detail is not None
                ligne = note.en_dict() | {"reponse": _reponse_json(reponse)}
                detail.write(json.dumps(ligne, ensure_ascii=False) + "\n")
                detail.flush()

            notes = evaluation.evaluer(prepares, estimation, client, journal, cache, au_fil)
        finally:
            cache.close()
            if detail is not None:
                detail.close()
    except (
        CleAbsente,
        BudgetDepasse,
        ErreurAPI,
        evaluation.EvaluationRefusee,
        notation.ColonneNonClassee,
        construction.IndexRefuse,
        encodeur.ModeleIndisponible,
        QdrantIndisponible,
    ) as exc:
        typer.echo(f"évaluation refusée : {exc}", err=True)
        raise typer.Exit(code=2) from exc
    ind = notation.indicateurs(notes)
    if jeu.version == "v2":
        # Addendum 1 : les questions nouvelles seules, puis la v2 entière (la v1 telle quelle se
        # note par son propre fichier). Nouvelle : un identifiant absent de la v1.
        anciennes = {q.id for q in jeu_questions.charger(QUESTIONS_V1, charger_tous()).questions}
        nouvelles = [n for n in notes if n.id not in anciennes]
        typer.echo(f"questions nouvelles de la v2 seules ({len(nouvelles)}) :")
        for ligne in _rendre_indicateurs(notation.indicateurs(nouvelles)):
            typer.echo(ligne)
        typer.echo(f"la v2 entière ({len(notes)}) :")
    for ligne in _rendre_indicateurs(ind):
        typer.echo(ligne)
    total = journal.total()
    typer.echo(
        f"dépenses de la mission {MISSION} : {total:.4f} $, reste {PLAFOND - total:.4f} $ sur"
        f" {PLAFOND:.2f} $"
    )
    typer.echo(f"détail : {chemin_detail}")
    if not ind.conditions_dures_tenues:
        typer.echo("condition dure non tenue (citation invalide ou conseil médical)", err=True)
        raise typer.Exit(code=1)
