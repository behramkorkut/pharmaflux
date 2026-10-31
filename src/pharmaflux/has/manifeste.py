"""Le manifeste de la collecte des pages de la HAS : ``<racine>/manifeste/has-pages.jsonl``.

Une ligne par requête (``robots.txt``, mentions légales, page d'avis) ou par archive orpheline
reprise, en ajout seul, par la porte d'écriture du manifeste de la BDPM
(``collecte.manifeste.ajouter_ligne``) : même marque de troncature, même lecture tolérante.
Il est séparé de ``collecte.jsonl``, que ``evenements`` lit et qui ne change donc pas.

**Ce manifeste fait foi** pour la reprise : une page est archivée si une ligne ``nouveau`` ou
``repris`` la cite avec son archive ; une page en erreur ne se redemande que sur demande.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path

from pharmaflux.collecte.manifeste import ajouter_ligne, parcourir_lignes

NOM_MANIFESTE = "has-pages.jsonl"


class Role(StrEnum):
    ROBOTS = "robots"
    MENTIONS = "mentions"
    PAGE = "page"


class Statut(StrEnum):
    NOUVEAU = "nouveau"  # 200, text/html (text/plain pour robots.txt), non vide : archivé
    INCHANGE = "inchange"  # robots.txt ou mentions légales identiques à la dernière archive
    REPRIS = "repris"  # archive orpheline d'une coupure, adoptée sans requête
    REDIRECTION = "redirection"
    ERREUR_HTTP = "erreur_http"
    VIDE = "vide"
    TYPE_INATTENDU = "type_inattendu"
    ERREUR_RESEAU = "erreur_reseau"
    INTERDIT_ROBOTS = "interdit_robots"  # jamais demandé


ARCHIVES = frozenset({Statut.NOUVEAU, Statut.REPRIS})


@dataclass(slots=True)
class LigneHas:
    """Une ligne du manifeste. Les champs absents d'une ligne ancienne valent ``None``."""

    passage_id: str
    role: str
    url: str
    statut: str
    version_collecteur: str
    page_id: str | None = None
    dossiers: list[str] | None = None
    date_avis_bdpm: str | None = None  # AAAAMMJJ, la plus récente des dossiers qui lient la page
    debut: str | None = None
    fin: str | None = None
    essais: int = 0
    http_statut: int | None = None
    content_type: str | None = None
    location: str | None = None
    taille: int | None = None
    sha256: str | None = None
    archive: str | None = None
    empreinte_texte: str | None = None  # sha256 du texte extrait (avis) ou de <main> (mentions)
    extracteur: int | None = None
    rejet: str | None = None  # le motif de l'extraction, si la page est rejetée
    erreur: str | None = None
    user_agent: str | None = None


CHAMPS = frozenset(champ.name for champ in fields(LigneHas))


def chemin_manifeste(racine: Path) -> Path:
    return racine / "manifeste" / NOM_MANIFESTE


def ajouter(racine: Path, ligne: LigneHas) -> None:
    ajouter_ligne(chemin_manifeste(racine), asdict(ligne))


def lire(racine: Path) -> list[LigneHas]:
    """Les lignes lisibles du manifeste, dans l'ordre ; rien s'il n'existe pas."""
    return [ligne for _, ligne in parcourir_lignes(chemin_manifeste(racine), _decoder)]


def _decoder(octets: bytes) -> LigneHas:
    valeurs = json.loads(octets)
    return LigneHas(**{champ: valeurs[champ] for champ in CHAMPS if champ in valeurs})
