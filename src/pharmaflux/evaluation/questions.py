"""Modèle et lecture stricte du jeu de questions de référence (``evaluation/*.toml``).

Une question a un identifiant stable (``categorie-NNN``), une catégorie de
l'annexe B du PRD, un texte en français et un **comportement attendu** :

- ``reponse`` : une valeur lue dans une archive précise (``attendu``), ou,
  tant que la source manque, ``calculable_au = "lotN"`` sans attendu ;
- ``abstention`` : l'assistant dit qu'il ne sait pas, avec un ``motif`` ;
  un ``attendu`` sans aucune ligne peut dire ce qui est absent ;
- ``refus_medical`` : l'assistant refuse et renvoie vers un professionnel.

Un ``attendu`` nomme la date de référence, le contrat (``fichier``),
l'archive (chemin relatif à la racine et sha256), la clé (colonnes et
valeurs qui sélectionnent les lignes), les colonnes lues et les lignes
attendues, telles quelles (valeurs brutes du fichier, jamais corrigées).
Comme pour les contrats, toute clé inconnue est refusée.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path

from pharmaflux.contrats.modele import Contrat
from pharmaflux.tomlstrict import TableStricte

VERSION_JEU = "v0"
CATEGORIES = (
    "disponibilite",
    "alternatives",
    "remboursement",
    "avis_has",
    "historique",
    "depense",
    "hors_perimetre",
    "medical",
)
LOTS = ("lot1", "lot2", "lot3", "lot4", "lot5")
MOTIF_ID = re.compile(r"(?P<categorie>[a-z_]+)-\d{3}")
MOTIF_SHA256 = re.compile(r"[0-9a-f]{64}")


class Comportement(StrEnum):
    REPONSE = "reponse"
    ABSTENTION = "abstention"
    REFUS_MEDICAL = "refus_medical"


class JeuInvalide(ValueError):  # noqa: N818 (nom français voulu)
    """Un jeu de questions mal formé : le message nomme la question et la clé en cause."""


class _Table(TableStricte):
    erreur = JeuInvalide


@dataclass(frozen=True, slots=True)
class Attendu:
    """Ce que ``questions verifier`` rejoue : l'archive, la sélection, les lignes."""

    date_reference: date
    fichier: str  # identifiant du contrat (bdpm.disponibilite)
    archive: str  # chemin relatif à la racine, comme dans le manifeste
    sha256: str  # des octets bruts de l'archive
    cle: Mapping[str, str]  # colonne → valeur : les lignes où toutes sont égales
    colonnes: tuple[str, ...]  # les colonnes lues sur ces lignes
    valeurs: tuple[Mapping[str, str], ...]  # les lignes attendues, dans l'ordre du fichier


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    categorie: str
    question: str
    comportement: Comportement
    attendu: Attendu | None = None
    motif: str | None = None  # abstention, refus : pourquoi
    orientation: str | None = None  # vers qui ou quoi renvoyer
    calculable_au: str | None = None  # réponse sans attendu : le lot qui l'apportera
    prudence: str | None = None  # la nuance que la réponse doit porter


@dataclass(frozen=True, slots=True)
class Jeu:
    version: str
    description: str
    questions: tuple[Question, ...] = field(default_factory=tuple)

    def par_categorie(self) -> dict[str, list[Question]]:
        groupes: dict[str, list[Question]] = {categorie: [] for categorie in CATEGORIES}
        for question in self.questions:
            groupes[question.categorie].append(question)
        return groupes


def charger(chemin: Path, contrats: Mapping[str, Contrat]) -> Jeu:
    """Le jeu d'un fichier TOML ; ``contrats`` vérifie fichiers et colonnes des attendus."""
    try:
        octets = chemin.read_bytes()
    except OSError as exc:
        raise JeuInvalide(f"{chemin} : illisible ({exc})") from exc
    return charger_octets(octets, str(chemin), contrats)


def charger_octets(octets: bytes, origine: str, contrats: Mapping[str, Contrat]) -> Jeu:
    try:
        brut = tomllib.loads(octets.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise JeuInvalide(f"{origine} : TOML illisible : {exc}") from exc
    racine = _Table(brut, origine)
    version = racine.texte("version")
    if version != VERSION_JEU:
        raise JeuInvalide(f"{origine} : version « {version} » ; attendu « {VERSION_JEU} »")
    description = racine.texte("description")
    questions = tuple(
        _question(table, contrats) for table in racine.tables("questions", obligatoire=True)
    )
    if not questions:
        raise JeuInvalide(f"{origine} : aucune question")
    ids = [question.id for question in questions]
    if len(set(ids)) != len(ids):
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        raise JeuInvalide(f"{origine} : identifiant(s) en double : {', '.join(doublons)}")
    racine.terminer()
    return Jeu(version=version, description=description, questions=questions)


def _question(table: _Table, contrats: Mapping[str, Contrat]) -> Question:
    id_ = table.texte("id")
    forme = MOTIF_ID.fullmatch(id_)
    if forme is None:
        raise JeuInvalide(f"{table.contexte} : id « {id_} » hors forme categorie-NNN")
    table.contexte = f"{table.contexte} ({id_})"
    categorie = table.texte("categorie")
    if categorie not in CATEGORIES:
        raise JeuInvalide(f"{table.contexte} : catégorie « {categorie} » inconnue")
    if forme.group("categorie") != categorie:
        raise JeuInvalide(f"{table.contexte} : l'id ne commence pas par « {categorie}- »")
    question = table.texte("question")
    nom = table.texte("comportement")
    try:
        comportement = Comportement(nom)
    except ValueError:
        attendus = ", ".join(c.value for c in Comportement)
        raise JeuInvalide(
            f"{table.contexte} : comportement « {nom} » inconnu ; attendu : {attendus}"
        ) from None
    motif = table.texte_facultatif("motif")
    orientation = table.texte_facultatif("orientation")
    calculable_au = table.texte_facultatif("calculable_au")
    prudence = table.texte_facultatif("prudence")
    table_attendu = table.table_facultative("attendu")
    attendu = None if table_attendu is None else _attendu(table_attendu, contrats)
    table.terminer()
    _coherence(table.contexte, comportement, attendu, motif, calculable_au)
    return Question(
        id=id_,
        categorie=categorie,
        question=question,
        comportement=comportement,
        attendu=attendu,
        motif=motif,
        orientation=orientation,
        calculable_au=calculable_au,
        prudence=prudence,
    )


def _coherence(
    contexte: str,
    comportement: Comportement,
    attendu: Attendu | None,
    motif: str | None,
    calculable_au: str | None,
) -> None:
    if calculable_au is not None and calculable_au not in LOTS:
        raise JeuInvalide(f"{contexte} : calculable_au « {calculable_au} » ; attendu : lot1 à lot5")
    if comportement is Comportement.REPONSE:
        if motif is not None:
            raise JeuInvalide(
                f"{contexte} : « motif » n'a de sens que pour une abstention ou un refus"
            )
        if (attendu is None) == (calculable_au is None):
            raise JeuInvalide(
                f"{contexte} : une réponse a un « attendu » ou un « calculable_au », pas les deux"
            )
        return
    if motif is None:
        raise JeuInvalide(f"{contexte} : une {comportement.value} exige un « motif »")
    if calculable_au is not None:
        raise JeuInvalide(f"{contexte} : « calculable_au » n'a de sens que pour une réponse")
    if comportement is Comportement.REFUS_MEDICAL and attendu is not None:
        raise JeuInvalide(f"{contexte} : un refus n'a pas d'« attendu »")
    if attendu is not None and attendu.valeurs:
        raise JeuInvalide(f"{contexte} : l'attendu d'une abstention ne contient aucune ligne")


def _archive_du_contrat(table: _Table, archive: str, contrat: Contrat, jour: date) -> None:
    """``archive`` est « <dossier bronze du contrat>/<jour de référence>/<nom>.gz », rien d'autre.

    Le dossier lie l'archive au contrat nommé : une archive d'un autre fichier serait
    lue avec les mauvaises colonnes (« archive non conforme » trompeur, ou comparaison
    fausse quand des noms coïncident). La forme exclut aussi un « .. » dans le chemin.
    """
    parties = archive.split("/")
    if parties[:3] != contrat.dossier_bronze.split("/"):
        raise JeuInvalide(
            f"{table.contexte} : « archive » est un chemin {contrat.dossier_bronze}/…, "
            f"le dossier bronze de {contrat.identifiant}"
        )
    if len(parties) < 4 or parties[3] != jour.isoformat():
        raise JeuInvalide(f"{table.contexte} : l'archive n'est pas du jour de référence {jour}")
    if len(parties) != 5 or not parties[4].endswith(".gz"):
        raise JeuInvalide(
            f"{table.contexte} : « archive » finit par le nom du fichier archivé, "
            "<horodatage>__<sha256 abrégé>.<ext>.gz"
        )


def _attendu(table: _Table, contrats: Mapping[str, Contrat]) -> Attendu:
    date_reference = table.date("date_reference", obligatoire=True)
    assert date_reference is not None
    fichier = table.texte("fichier")
    if fichier not in contrats:
        connus = ", ".join(sorted(contrats))
        raise JeuInvalide(
            f"{table.contexte} : fichier « {fichier} » sans contrat ; connus : {connus}"
        )
    contrat = contrats[fichier]
    archive = table.texte("archive")
    _archive_du_contrat(table, archive, contrat, date_reference)
    sha256 = table.texte("sha256")
    if not MOTIF_SHA256.fullmatch(sha256):
        raise JeuInvalide(f"{table.contexte} : « sha256 » doit être un sha256 hexadécimal")
    cle = table.table("cle").chaines()
    if not cle:
        raise JeuInvalide(f"{table.contexte} : clé sans colonne")
    _colonnes_connues(table, tuple(cle), contrat)
    colonnes = table.textes("colonnes", obligatoire=True)
    if not colonnes:
        raise JeuInvalide(f"{table.contexte} : aucune colonne à lire")
    if len(set(colonnes)) != len(colonnes):
        raise JeuInvalide(f"{table.contexte} : colonne(s) en double")
    _colonnes_connues(table, colonnes, contrat)
    valeurs = []
    for ligne in table.tables("valeurs", obligatoire=True):
        valeur = ligne.chaines()
        if set(valeur) != set(colonnes):
            raise JeuInvalide(f"{ligne.contexte} : une valeur par colonne lue, ni plus ni moins")
        valeurs.append(valeur)
    table.terminer()
    return Attendu(
        date_reference=date_reference,
        fichier=fichier,
        archive=archive,
        sha256=sha256,
        cle=cle,
        colonnes=colonnes,
        valeurs=tuple(valeurs),
    )


def _colonnes_connues(table: _Table, colonnes: tuple[str, ...], contrat: Contrat) -> None:
    inconnues = [nom for nom in colonnes if nom not in contrat.noms_colonnes]
    if inconnues:
        raise JeuInvalide(
            f"{table.contexte} : colonne(s) inconnue(s) de {contrat.identifiant} : "
            + ", ".join(inconnues)
        )
