"""Contrats de schéma v0 : ce qu'un fichier source doit être, et ce que l'on constate.

Un contrat décrit un fichier TSV de la BDPM tel qu'il est reçu : encodage,
fin de ligne, colonnes typées dans l'ordre, clé, liens vers d'autres
fichiers. La vérification (``verification``) compare une archive à son
contrat et rend des anomalies ; elle ne corrige rien et ne convertit rien
(PRD §6.2 : on constate). Les contrats sont des fichiers TOML dans ``bdpm/``,
lus par ``chargeur``, qui garantit la cohérence décrite ici.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

VERSION_CONTRAT = "v0"

# Longueur maximale d'une valeur brute reproduite dans une anomalie.
LONGUEUR_VALEUR = 80


class TypeNom(StrEnum):
    """Les neuf types de valeur : jeu fermé (ordre de mission 01, §0 C, addendum 1)."""

    TEXTE = "texte"
    ENTIER = "entier"
    DECIMAL = "decimal"
    DATE = "date"
    BOOLEEN = "booleen"
    ENUMERATION = "enumeration"
    CODE = "code"
    URL = "url"
    LISTE = "liste"


# Les formats de date rencontrés dans la BDPM : motif strict (nombre exact de
# chiffres, ``strptime`` seul accepterait ``1/2/2020``), puis format ``strptime``
# pour vérifier que la date existe au calendrier.
FORMATS_DATE: dict[str, tuple[re.Pattern[str], str]] = {
    "JJ/MM/AAAA": (re.compile(r"\d{2}/\d{2}/\d{4}"), "%d/%m/%Y"),
    "AAAAMMJJ": (re.compile(r"\d{8}"), "%Y%m%d"),
    "AAAA-MM-JJ": (re.compile(r"\d{4}-\d{2}-\d{2}"), "%Y-%m-%d"),
}


class Regle(StrEnum):
    """Les règles qu'une anomalie peut enfreindre."""

    ENCODAGE = "encodage"
    FIN_DE_LIGNE = "fin_de_ligne"
    NOMBRE_COLONNES = "nombre_colonnes"
    CLE_NON_UNIQUE = "cle_non_unique"
    RETOUR_FINAL = "retour_final"
    LIGNE_VIDE = "ligne_vide"
    LIGNE_DUPLIQUEE = "ligne_dupliquee"
    VALEUR_MANQUANTE = "valeur_manquante"
    ESPACE_PARASITE = "espace_parasite"
    LONGUEUR_DEPASSEE = "longueur_depassee"
    ENTIER_ILLISIBLE = "entier_illisible"
    DECIMAL_ILLISIBLE = "decimal_illisible"
    DATE_ILLISIBLE = "date_illisible"
    DATE_HORS_PLAGE = "date_hors_plage"
    BOOLEEN_INCONNU = "booleen_inconnu"
    VALEUR_INCONNUE = "valeur_inconnue"
    CODE_ILLISIBLE = "code_illisible"
    URL_ILLISIBLE = "url_illisible"
    HOTE_INCONNU = "hote_inconnu"


# Bloquantes : le fichier ne se lit pas comme le contrat l'attend (addendum 1 :
# encodage, fin de ligne, nombre de colonnes, clé déclarée unique qui ne l'est
# pas). Tout le reste porte sur une valeur et ne bloque pas, ``valeur_inconnue``
# comprise ; le profil la met néanmoins en tête, premier signe d'un changement.
REGLES_BLOQUANTES = frozenset(
    {Regle.ENCODAGE, Regle.FIN_DE_LIGNE, Regle.NOMBRE_COLONNES, Regle.CLE_NON_UNIQUE}
)


@dataclass(frozen=True, slots=True)
class Anomalie:
    """Un constat : où (fichier, ligne, colonne), quelle règle, quelle valeur brute.

    ``ligne`` est numérotée à partir de 1 ; 0 désigne le fichier entier.
    ``colonne`` est None quand l'anomalie porte sur la ligne ou le fichier.
    ``valeur`` est la valeur reçue, tronquée à ``LONGUEUR_VALEUR``, ou le détail
    du constat quand il n'y a pas de valeur (nombre de colonnes, encodage).
    """

    fichier: str
    ligne: int
    colonne: str | None
    regle: Regle
    valeur: str

    @property
    def bloquante(self) -> bool:
        return self.regle in REGLES_BLOQUANTES


def tronquer(valeur: str) -> str:
    """La valeur telle quelle si elle est courte, sinon coupée avec une marque."""
    if len(valeur) <= LONGUEUR_VALEUR:
        return valeur
    return valeur[: LONGUEUR_VALEUR - 1] + "…"


@dataclass(frozen=True, slots=True)
class TypeValeur:
    """Un type et ses paramètres ; ``chargeur`` n'admet que ceux du type."""

    nom: TypeNom
    longueur_max: int | None = None  # texte
    decimales: int = 2  # decimal : chiffres après la virgule
    format: str | None = None  # date : une clé de FORMATS_DATE
    plage_min: date | None = None  # date
    plage_max: date | None = None  # date
    vrai: str | None = None  # booleen
    faux: str | None = None  # booleen
    valeurs: tuple[str, ...] = ()  # enumeration : liste fermée, telle qu'écrite dans le fichier
    motif: re.Pattern[str] | None = None  # code : doit couvrir toute la valeur
    hotes: tuple[str, ...] = ()  # url : hôtes admis ; vide = tous
    de: TypeValeur | None = None  # liste : type des éléments
    separateur: str | None = None  # liste


@dataclass(frozen=True, slots=True)
class Colonne:
    nom: str
    type: TypeValeur
    obligatoire: bool  # une valeur vide est alors une anomalie ``valeur_manquante``
    description: str = ""


class FinDeLigne(StrEnum):
    CRLF = "CRLF"
    LF = "LF"


class RetourFinal(StrEnum):
    OBLIGATOIRE = "obligatoire"  # son absence est signalée (``retour_final``)
    TOLERE = "tolere"  # le fichier peut finir sans retour à la ligne (CIS_MITM.txt)


class LignesVides(StrEnum):
    INTERDITES = "interdites"  # une ligne vide compte comme un nombre de colonnes faux
    ANOMALIE = "anomalie"  # signalée ``ligne_vide``, non bloquante, ignorée pour le reste


@dataclass(frozen=True, slots=True)
class Format:
    encodage: str  # nom de codec Python : cp1252, utf-8, ascii
    fin_de_ligne: FinDeLigne
    separateur: str = "\t"
    retour_final: RetourFinal = RetourFinal.OBLIGATOIRE
    lignes_vides: LignesVides = LignesVides.INTERDITES


@dataclass(frozen=True, slots=True)
class Source:
    """D'où vient le contrat : la documentation lue, l'archive sur laquelle il a été vérifié."""

    documentation: str
    documentation_sha256: str
    section: str
    date_verification: date
    archive_reference: str  # chemin relatif à la racine de données, comme le manifeste
    archive_sha256: str


@dataclass(frozen=True, slots=True)
class Cle:
    colonnes: tuple[str, ...]
    unique: bool  # si vrai, une clé répétée est bloquante (``cle_non_unique``)
    raison: str = ""  # obligatoire quand ``unique`` est faux


@dataclass(frozen=True, slots=True)
class Lien:
    """Une colonne qui référence une colonne d'un autre fichier : mesuré, jamais une anomalie."""

    colonne: str
    vers: str  # identifiant du catalogue (``bdpm.specialites``)
    colonne_cible: str


@dataclass(frozen=True, slots=True)
class Contrat:
    version: str
    identifiant: str
    fichier: str
    description: str
    source: Source
    format: Format
    colonnes: tuple[Colonne, ...]
    cle: Cle
    liens: tuple[Lien, ...] = ()

    @property
    def dossier_bronze(self) -> str:
        """« bronze/<source>/<fichier> », le dossier où la collecte archive ce fichier."""
        return f"bronze/{self.identifiant.partition('.')[0]}/{self.fichier}"

    @property
    def noms_colonnes(self) -> tuple[str, ...]:
        return tuple(colonne.nom for colonne in self.colonnes)

    def index(self, nom: str) -> int:
        """La position de la colonne ``nom`` ; ``chargeur`` garantit qu'elle existe."""
        return self.noms_colonnes.index(nom)
