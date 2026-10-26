"""Profil d'une archive contre son contrat : conformité, clé, colonnes, dates, liens.

Tout est mesuré sur les chaînes telles qu'elles sont dans le fichier ; rien
n'est converti pour de bon (les dates et les nombres ne sont lus que pour
donner un minimum et un maximum). Les liens vers d'autres fichiers sont des
taux de correspondance, jamais des anomalies (addendum 1 de la mission 01).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pharmaflux import bronze
from pharmaflux.collecte.empreintes import sha256_hex
from pharmaflux.contrats.modele import (
    FORMATS_DATE,
    REGLES_BLOQUANTES,
    Anomalie,
    Colonne,
    Contrat,
    Lien,
    Regle,
    TypeNom,
)
from pharmaflux.contrats.verification import Lecture, verifier

EXEMPLES_PAR_REGLE = 5
SEUIL_REPARTITION = 30  # au plus tant de valeurs distinctes : répartition complète
EXEMPLES_ABSENTS = 5


@dataclass(slots=True)
class GroupeAnomalies:
    regle: Regle
    nombre: int
    exemples: list[Anomalie]

    @property
    def bloquante(self) -> bool:
        return self.regle in REGLES_BLOQUANTES


@dataclass(slots=True)
class ProfilColonne:
    nom: str
    type: str
    obligatoire: bool
    vides: int
    distinctes: int
    repartition: list[tuple[str, int]] | None  # valeur brute → nombre, si peu de valeurs
    minimum: str | None = None
    maximum: str | None = None


@dataclass(slots=True)
class OrdreDates:
    """Deux colonnes de dates d'une même ligne : combien de fois la première suit la seconde."""

    premiere: str
    seconde: str
    comparables: int  # lignes où les deux dates se lisent
    posterieure: int  # première > seconde
    egales: int
    anterieure: int


@dataclass(slots=True)
class ProfilLien:
    colonne: str
    vers: str
    colonne_cible: str
    archive_cible: str | None  # None : aucune archive du fichier cible
    lignes: int = 0  # lignes de la source à valeur non vide
    lignes_trouvees: int = 0
    distinctes: int = 0
    distinctes_trouvees: int = 0
    exemples_absents: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Profil:
    contrat: Contrat
    archive: str  # chemin relatif à la racine, comme le manifeste
    sha256: str
    archive_de_reference: bool  # l'archive est celle sur laquelle le contrat a été vérifié
    nombre_lignes: int
    lignes_bien_formees: int
    anomalies: list[GroupeAnomalies]
    cle_distinctes: int
    cle_repetees: int  # lignes au-delà de la première pour une même clé
    colonnes: list[ProfilColonne]
    ordres_dates: list[OrdreDates]
    liens: list[ProfilLien]

    @property
    def nombre_bloquantes(self) -> int:
        return sum(groupe.nombre for groupe in self.anomalies if groupe.bloquante)


def profiler(
    contrat: Contrat, octets: bytes, archive: str, cibles: dict[str, tuple[str, Lecture]]
) -> Profil:
    """Le profil de ``octets`` (archive ``archive``) contre ``contrat``.

    ``cibles`` : par identifiant de contrat cible, l'archive et la lecture déjà
    faite du fichier cible, pour mesurer les liens.
    """
    lecture = verifier(contrat, octets, fichier=archive)
    sha256 = sha256_hex(octets)
    index_cle = [contrat.index(nom) for nom in contrat.cle.colonnes]
    cles = Counter(tuple(valeurs[i] for i in index_cle) for _, valeurs in lecture.lignes)
    return Profil(
        contrat=contrat,
        archive=archive,
        sha256=sha256,
        archive_de_reference=(
            archive == contrat.source.archive_reference and sha256 == contrat.source.archive_sha256
        ),
        nombre_lignes=lecture.nombre_lignes,
        lignes_bien_formees=len(lecture.lignes),
        anomalies=_grouper(lecture),
        cle_distinctes=len(cles),
        cle_repetees=sum(nombre - 1 for nombre in cles.values()),
        colonnes=[
            _profil_colonne(colonne, i, lecture) for i, colonne in enumerate(contrat.colonnes)
        ],
        ordres_dates=_ordres_dates(contrat, lecture),
        liens=[_profil_lien(lien, contrat, lecture, cibles) for lien in contrat.liens],
    )


def _grouper(lecture: Lecture) -> list[GroupeAnomalies]:
    """Par règle : ``valeur_inconnue`` d'abord (addendum 1), les bloquantes, puis par nombre."""
    groupes = [
        GroupeAnomalies(regle, len(anomalies), anomalies[:EXEMPLES_PAR_REGLE])
        for regle, anomalies in lecture.par_regle().items()
    ]
    groupes.sort(
        key=lambda g: (g.regle is not Regle.VALEUR_INCONNUE, not g.bloquante, -g.nombre, g.regle)
    )
    return groupes


def _profil_colonne(colonne: Colonne, i: int, lecture: Lecture) -> ProfilColonne:
    valeurs = Counter(valeurs[i] for _, valeurs in lecture.lignes)
    vides = valeurs.pop("", 0)
    repartition = None
    if colonne.type.nom is TypeNom.ENUMERATION or len(valeurs) <= SEUIL_REPARTITION:
        repartition = sorted(valeurs.items(), key=lambda v: (-v[1], v[0]))
    minimum = maximum = None
    bornes = _bornes(colonne, valeurs)
    if bornes is not None:
        minimum, maximum = bornes
    return ProfilColonne(
        nom=colonne.nom,
        type=colonne.type.nom.value,
        obligatoire=colonne.obligatoire,
        vides=vides,
        distinctes=len(valeurs),
        repartition=repartition,
        minimum=minimum,
        maximum=maximum,
    )


def _bornes(colonne: Colonne, valeurs: Counter[str]) -> tuple[str, str] | None:
    """Minimum et maximum lisibles d'une colonne de dates ou de nombres, rendus tels qu'écrits."""
    nom = colonne.type.nom
    if nom is TypeNom.DATE:
        dates = {v: d for v in valeurs if (d := _lire_date(colonne.type.format, v)) is not None}
        return _extremes(dates)
    if nom in (TypeNom.ENTIER, TypeNom.DECIMAL):
        nombres = {v: n for v in valeurs if (n := _lire_nombre(v)) is not None}
        return _extremes(nombres)
    return None


def _extremes[V: (date, Decimal)](lues: dict[str, V]) -> tuple[str, str] | None:
    if not lues:
        return None
    ordre = sorted(lues, key=lues.__getitem__)
    return ordre[0], ordre[-1]


def _lire_date(format_: str | None, valeur: str) -> date | None:
    if format_ is None:
        return None
    motif, format_strptime = FORMATS_DATE[format_]
    if not motif.fullmatch(valeur):
        return None
    try:
        return datetime.strptime(valeur, format_strptime).date()
    except ValueError:
        return None


def _lire_nombre(valeur: str) -> Decimal | None:
    if valeur.count(",") > 1:  # « 1,003,48 » : illisible, hors bornes
        return None
    try:
        return Decimal(valeur.replace(",", "."))
    except InvalidOperation:
        return None


def _ordres_dates(contrat: Contrat, lecture: Lecture) -> list[OrdreDates]:
    """Pour chaque couple de colonnes de dates, l'ordre observé ligne à ligne."""
    dates = [(i, c) for i, c in enumerate(contrat.colonnes) if c.type.nom is TypeNom.DATE]
    ordres = []
    for rang, (i, premiere) in enumerate(dates):
        for j, seconde in dates[rang + 1 :]:
            ordre = OrdreDates(premiere.nom, seconde.nom, 0, 0, 0, 0)
            for _, valeurs in lecture.lignes:
                a = _lire_date(premiere.type.format, valeurs[i])
                b = _lire_date(seconde.type.format, valeurs[j])
                if a is None or b is None:
                    continue
                ordre.comparables += 1
                if a > b:
                    ordre.posterieure += 1
                elif a == b:
                    ordre.egales += 1
                else:
                    ordre.anterieure += 1
            ordres.append(ordre)
    return ordres


def _profil_lien(
    lien: Lien, contrat: Contrat, lecture: Lecture, cibles: dict[str, tuple[str, Lecture]]
) -> ProfilLien:
    """Part des valeurs de la colonne retrouvées dans la colonne cible du fichier cible."""
    cible = cibles.get(lien.vers)
    if cible is None:
        return ProfilLien(lien.colonne, lien.vers, lien.colonne_cible, None)
    archive_cible, lecture_cible = cible
    j = lecture_cible.contrat.index(lien.colonne_cible)
    connues = {valeurs[j] for _, valeurs in lecture_cible.lignes if valeurs[j]}
    i = contrat.index(lien.colonne)
    valeurs_source = Counter(valeurs[i] for _, valeurs in lecture.lignes if valeurs[i])
    absentes = [valeur for valeur in valeurs_source if valeur not in connues]
    return ProfilLien(
        colonne=lien.colonne,
        vers=lien.vers,
        colonne_cible=lien.colonne_cible,
        archive_cible=archive_cible,
        lignes=sum(valeurs_source.values()),
        lignes_trouvees=sum(n for v, n in valeurs_source.items() if v in connues),
        distinctes=len(valeurs_source),
        distinctes_trouvees=len(valeurs_source) - len(absentes),
        exemples_absents=absentes[:EXEMPLES_ABSENTS],
    )


class ArchiveIntrouvable(LookupError):  # noqa: N818 (nom français voulu)
    """Aucune archive pour ce fichier sous la racine, ou chemin donné introuvable."""


def profiler_racine(
    racine: Path,
    contrats: dict[str, Contrat],
    selection: list[str],
    archive: Path | None = None,
) -> list[Profil]:
    """Les profils des contrats ``selection`` sur ``racine``, dernière archive de chacun.

    ``archive`` : une archive précise (chemin absolu ou relatif à la racine) à la
    place de la dernière, pour l'unique contrat de ``selection``. Les cibles des
    liens sont toujours lues dans leur dernière archive, une seule fois.
    """
    if archive is not None and len(selection) != 1:
        raise ValueError("--archive s'applique à un seul fichier")
    lectures: dict[str, tuple[str, Lecture]] = {}

    def lecture_derniere(identifiant: str) -> tuple[str, Lecture] | None:
        if identifiant not in lectures:
            contrat = contrats[identifiant]
            derniere = bronze.derniere(racine, _source(identifiant), contrat.fichier)
            if derniere is None:
                return None
            relatif = derniere.relatif(racine)
            lectures[identifiant] = (relatif, verifier(contrat, derniere.lire(), fichier=relatif))
        return lectures[identifiant]

    profils = []
    for identifiant in selection:
        contrat = contrats[identifiant]
        if archive is not None:
            chemin = archive if archive.is_absolute() else racine / archive
            if not chemin.is_file():
                raise ArchiveIntrouvable(f"archive introuvable : {chemin}")
            octets = bronze.lire_archive(chemin)
            relatif = (
                chemin.relative_to(racine).as_posix()
                if chemin.is_relative_to(racine)
                else str(chemin)
            )
        else:
            derniere = bronze.derniere(racine, _source(identifiant), contrat.fichier)
            if derniere is None:
                raise ArchiveIntrouvable(f"aucune archive de {contrat.fichier} sous {racine}")
            octets, relatif = derniere.lire(), derniere.relatif(racine)
        cibles = {
            lien.vers: cible
            for lien in contrat.liens
            if (cible := lecture_derniere(lien.vers)) is not None
        }
        profils.append(profiler(contrat, octets, relatif, cibles))
    return profils


def _source(identifiant: str) -> str:
    return identifiant.partition(".")[0]
