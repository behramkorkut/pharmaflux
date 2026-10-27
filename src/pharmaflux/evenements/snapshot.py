"""Snapshot normalisé d'une archive : ce que le fichier dit, prêt à être comparé (ADR 0005).

Une archive est lue une seule fois par ``contrats.verification`` ; les lignes
bien formées deviennent des ``Ligne`` figées qui partagent leurs tuples bruts
avec la ``Lecture`` et portent leurs valeurs normalisées
(``contrats.normalisation``) et leurs anomalies. Un fichier à clé unique est
un dictionnaire clé normalisée → ligne ; un fichier sans clé unique est un
multiensemble (empreinte de la ligne normalisée → ligne, occurrences). Une
anomalie bloquante, ou une clé **normalisée** qui se répète alors que les
clés brutes sont distinctes (`" X"` et `"X"`), rend un snapshot **écarté**
avec son motif, jamais une exception : un fichier à clé dont la clé est
ambiguë ne se compare pas. Le snapshot porte son archive, la version du
contrat et son bilan.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pharmaflux import bronze
from pharmaflux.collecte.empreintes import sha256_hex
from pharmaflux.contrats.modele import Contrat, Regle, TypeNom, TypeValeur
from pharmaflux.contrats.normalisation import normaliser_valeur
from pharmaflux.contrats.verification import FICHIER_ENTIER, Lecture, verifier

# Entre les valeurs d'une ligne dans son empreinte : jamais dans une valeur TSV.
SEPARATEUR_EMPREINTE = "\x1f"


class Identite(StrEnum):
    """Ce qui identifie une ligne : sa clé déclarée unique, ou la ligne entière."""

    CLE = "cle"
    LIGNE = "ligne"


@dataclass(frozen=True, slots=True)
class Ligne:
    """Une ligne bien formée : numéro dans le fichier, valeurs brutes, normalisées, anomalies.

    ``brutes`` est le tuple de la ``Lecture``, pas une copie ; ``normalisees``
    est ``brutes`` même quand rien ne change, et chaque valeur inchangée est le
    même objet chaîne. Une valeur normalisée qui se répète d'une ligne à
    l'autre n'existe qu'une fois, comme les brutes dans la ``Lecture``.
    ``anomalies`` : (colonne ou None, règle), dans l'ordre de la vérification.
    """

    numero: int
    brutes: tuple[str, ...]
    normalisees: tuple[str, ...]
    anomalies: tuple[tuple[str | None, Regle], ...]

    @property
    def empreinte(self) -> str:
        return empreinte_ligne(self.normalisees)


def empreinte_ligne(normalisees: tuple[str, ...]) -> str:
    """sha256 des valeurs normalisées jointes par ``\\x1f`` : l'identité d'une ligne sans clé."""
    return hashlib.sha256(SEPARATEUR_EMPREINTE.join(normalisees).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BilanSnapshot:
    """Les mesures d'un snapshot : une mesure, jamais une alerte (§0 J)."""

    archive: str
    sha256: str
    version_contrat: str
    lignes: int  # lignes non vides, bien formées ou non
    lignes_bien_formees: int
    entites: int  # clés distinctes, ou lignes normalisées distinctes
    occurrences_en_doublon: int  # lignes au-delà de la première pour une même entité
    anomalies: tuple[tuple[Regle, int], ...]  # par règle, dans l'ordre de ``Regle``
    graphies: tuple[tuple[str, tuple[tuple[str, int], ...]], ...]  # colonne à canonique → graphies
    motif_ecart: str | None  # le snapshot est écarté quand il n'est pas None

    @property
    def ecarte(self) -> bool:
        return self.motif_ecart is not None


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Une archive normalisée. Les dictionnaires ne sont pas à modifier."""

    contrat: Contrat
    archive: str  # chemin relatif à la racine, comme le manifeste
    sha256: str
    horodatage: datetime | None  # celui du nom de l'archive, UTC, quand il est connu
    identite: Identite
    par_cle: Mapping[tuple[str, ...], Ligne]  # fichier à clé : clé normalisée → ligne
    par_ligne: Mapping[str, tuple[Ligne, int]]  # ligne à ligne : empreinte → (ligne, occurrences)
    bilan: BilanSnapshot

    @property
    def ecarte(self) -> bool:
        return self.bilan.ecarte

    @property
    def motif_ecart(self) -> str | None:
        return self.bilan.motif_ecart

    @property
    def lignes(self) -> list[Ligne]:
        """Les lignes, dans l'ordre du fichier (première occurrence pour un doublon)."""
        if self.identite is Identite.CLE:
            lignes = list(self.par_cle.values())
        else:
            lignes = [ligne for ligne, _ in self.par_ligne.values()]
        lignes.sort(key=lambda ligne: ligne.numero)
        return lignes


def lire(contrat: Contrat, archive: bronze.Archive, racine: Path) -> Snapshot:
    """Le snapshot d'une archive du bronze (lue une fois, par ``bronze``)."""
    return construire(contrat, archive.lire(), archive.relatif(racine), archive.horodatage)


def construire(
    contrat: Contrat, octets: bytes, archive: str, horodatage: datetime | None = None
) -> Snapshot:
    """Le snapshot de ``octets`` (archive ``archive``) contre ``contrat``."""
    lecture = verifier(contrat, octets, fichier=archive)
    return depuis_lecture(lecture, sha256_hex(octets), horodatage)


def depuis_lecture(lecture: Lecture, sha256: str, horodatage: datetime | None = None) -> Snapshot:
    """Le snapshot d'une lecture déjà faite : aucune seconde lecture du fichier."""
    contrat = lecture.contrat
    types = [colonne.type for colonne in contrat.colonnes]
    par_numero: dict[int, list[tuple[str | None, Regle]]] = {}
    for anomalie in lecture.anomalies:
        if anomalie.ligne != FICHIER_ENTIER:
            par_numero.setdefault(anomalie.ligne, []).append((anomalie.colonne, anomalie.regle))
    identite = Identite.CLE if contrat.cle.unique else Identite.LIGNE
    index_cle = [contrat.index(nom) for nom in contrat.cle.colonnes]
    par_cle: dict[tuple[str, ...], Ligne] = {}
    par_ligne: dict[str, tuple[Ligne, int]] = {}
    doublons = 0
    collisions: dict[tuple[str, ...], int] = {}  # clé normalisée répétée → lignes au-delà de la 1re
    partagees: dict[str, str] = {}  # valeur normalisée → le premier objet chaîne vu
    for numero, brutes in lecture.lignes:
        normalisees = tuple(
            _partager(partagees, brute, normaliser_valeur(type_, brute).valeur)
            for type_, brute in zip(types, brutes, strict=True)
        )
        if normalisees == brutes:
            normalisees = brutes  # même objet : rien n'a changé, rien n'est copié
        ligne = Ligne(numero, brutes, normalisees, tuple(par_numero.get(numero, ())))
        if identite is Identite.CLE:
            cle = tuple(normalisees[i] for i in index_cle)
            if cle in par_cle:
                # Clés brutes répétées (bloquant, ``cle_non_unique``) ou clés brutes distinctes
                # de même forme normalisée : dans les deux cas le snapshot est écarté.
                doublons += 1
                collisions[cle] = collisions.get(cle, 0) + 1
            else:
                par_cle[cle] = ligne
        else:
            empreinte = ligne.empreinte
            premiere, occurrences = par_ligne.get(empreinte, (ligne, 0))
            par_ligne[empreinte] = (premiere, occurrences + 1)
            doublons += occurrences > 0
    bilan = BilanSnapshot(
        archive=lecture.fichier,
        sha256=sha256,
        version_contrat=contrat.version,
        lignes=lecture.nombre_lignes,
        lignes_bien_formees=len(lecture.lignes),
        entites=len(par_cle) if identite is Identite.CLE else len(par_ligne),
        occurrences_en_doublon=doublons,
        anomalies=_anomalies_par_regle(lecture),
        graphies=_graphies(contrat, lecture),
        motif_ecart=_motif_ecart(lecture, collisions, par_cle),
    )
    return Snapshot(
        contrat=contrat,
        archive=lecture.fichier,
        sha256=sha256,
        horodatage=horodatage,
        identite=identite,
        par_cle=par_cle,
        par_ligne=par_ligne,
        bilan=bilan,
    )


def _partager(partagees: dict[str, str], brute: str, normalisee: str) -> str:
    """La brute elle-même quand rien ne change ; sinon le premier objet vu pour cette valeur."""
    if normalisee == brute:
        return brute
    return partagees.setdefault(normalisee, normalisee)


def _anomalies_par_regle(lecture: Lecture) -> tuple[tuple[Regle, int], ...]:
    comptes = Counter(anomalie.regle for anomalie in lecture.anomalies)
    return tuple((regle, comptes[regle]) for regle in Regle if comptes[regle])


def _motif_ecart(
    lecture: Lecture,
    collisions: dict[tuple[str, ...], int],
    par_cle: dict[tuple[str, ...], Ligne],
) -> str | None:
    """Pourquoi le snapshot est écarté, ou None.

    « 3 anomalie(s) bloquante(s) : fin_de_ligne (1), nombre_colonnes (2) », puis,
    s'il y a lieu, « clé normalisée non unique : 1 clé(s), 2 lignes, première
    ligne 812 » (les lignes en trop, et la première ligne de la première clé
    répétée). Une clé normalisée répétée sans bloquante brute écarte à elle seule.
    """
    motifs = []
    bloquantes = Counter(anomalie.regle for anomalie in lecture.bloquantes)
    if bloquantes:
        detail = ", ".join(f"{regle} ({n})" for regle, n in sorted(bloquantes.items()))
        motifs.append(f"{sum(bloquantes.values())} anomalie(s) bloquante(s) : {detail}")
    if collisions:
        premiere = min(par_cle[cle].numero for cle in collisions)
        lignes = sum(collisions.values()) + len(collisions)
        motifs.append(
            f"clé normalisée non unique : {len(collisions)} clé(s), {lignes} lignes,"
            f" première ligne {premiere}"
        )
    return " ; ".join(motifs) if motifs else None


def _graphies(
    contrat: Contrat, lecture: Lecture
) -> tuple[tuple[str, tuple[tuple[str, int], ...]], ...]:
    """Pour chaque colonne dont l'énumération a une table ``canonique``, les graphies brutes.

    Le compte de chaque graphie, élément par élément pour une liste ; c'est le
    bilan qui dit le jour où la BDPM change de graphie, pas un événement.
    """
    resultat = []
    for i, colonne in enumerate(contrat.colonnes):
        type_ = colonne.type
        elements = type_.de if type_.nom is TypeNom.LISTE and type_.de is not None else type_
        if elements.nom is not TypeNom.ENUMERATION or not elements.canonique:
            continue
        comptes: Counter[str] = Counter()
        for _, valeurs in lecture.lignes:
            comptes.update(_elements(type_, valeurs[i]))
        resultat.append((colonne.nom, tuple(sorted(comptes.items(), key=lambda g: (-g[1], g[0])))))
    return tuple(resultat)


def _elements(type_: TypeValeur, valeur: str) -> list[str]:
    if valeur == "":
        return []
    if type_.nom is TypeNom.LISTE and type_.separateur is not None:
        return valeur.split(type_.separateur)
    return [valeur]
