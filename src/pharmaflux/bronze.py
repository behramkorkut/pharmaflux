"""Lecture de l'archive bronze : la seule porte d'entrée vers ``bronze/``.

Le collecteur y écrit (``collecte/archive.py``) ; tout ce qui lit une
archive (le profil, la vérification des contrats, ``etat``) passe par ici,
jamais par le système de fichiers directement. Une archive est un fichier
``<racine>/bronze/<source>/<fichier>/<AAAA-MM-JJ>/<horodatage UTC>__<sha256 12 car.><ext>.gz``.

Tout nom qui commence par un point est ignoré : fichier temporaire du
collecteur (``.<nom>.partiel-<pid>``, écriture en cours ou interrompue),
dossier ``.rsync-partiel/`` d'un rapatriement coupé, fichier caché du
système. Les fichiers temporaires sont listés à part, pour ``etat``.
"""

from __future__ import annotations

import gzip
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DOSSIER_BRONZE = "bronze"
FORMAT_HORODATAGE = "%Y%m%dT%H%M%SZ"
MOTIF_NOM = re.compile(
    r"^(?P<horodatage>\d{8}T\d{6}Z)__(?P<sha256>[0-9a-f]{12})(?P<extension>(?:\.[A-Za-z0-9]+)?)\.gz$"
)
MOTIF_PARTIEL = re.compile(r"^\..+\.partiel-\d+$")


class NomArchiveInvalide(ValueError):  # noqa: N818 (nom français voulu)
    """Un fichier visible de ``bronze/`` n'a pas la forme d'une archive : à regarder."""


@dataclass(frozen=True, slots=True)
class Archive:
    """Une archive du bronze, identifiée par son nom (jamais ouverte avant ``lire``)."""

    chemin: Path
    source: str
    fichier: str
    horodatage: datetime  # UTC, celui du nom
    sha256_prefixe: str  # les 12 premiers caractères du sha256 des octets bruts

    def relatif(self, racine: Path) -> str:
        """Le chemin tel que le manifeste l'écrit : relatif à la racine, séparateur ``/``."""
        return self.chemin.relative_to(racine).as_posix()

    def lire(self) -> bytes:
        """Les octets bruts reçus de la source (décompression seulement, aucun décodage)."""
        return lire_archive(self.chemin)


def lire_archive(chemin: Path) -> bytes:
    """Les octets bruts d'une archive (décompression seulement)."""
    with gzip.open(chemin, "rb") as fichier:
        return fichier.read()


def lister(racine: Path, source: str, fichier: str) -> list[Archive]:
    """Les archives d'un fichier source, de la plus ancienne à la plus récente.

    L'ordre est celui de l'horodatage du nom (UTC), puis du nom complet. Rien
    si le dossier n'existe pas. Un fichier visible qui n'a pas la forme d'une
    archive lève ``NomArchiveInvalide`` : le bronze n'est écrit que par le
    collecteur, un intrus mérite une erreur franche plutôt qu'un silence.
    """
    dossier = racine / DOSSIER_BRONZE / source / fichier
    if not dossier.is_dir():
        return []
    archives = [
        _analyser(element, source, fichier)
        for jour in _visibles(dossier)
        if jour.is_dir()
        for element in _visibles(jour)
        if element.is_file()
    ]
    archives.sort(key=lambda archive: (archive.horodatage, archive.chemin.name))
    return archives


def derniere(racine: Path, source: str, fichier: str) -> Archive | None:
    """La plus récente archive d'un fichier source, ou ``None``."""
    archives = lister(racine, source, fichier)
    return archives[-1] if archives else None


def fichiers_partiels(racine: Path) -> list[Path]:
    """Les fichiers temporaires ``.<nom>.partiel-<pid>`` présents sous ``bronze/``.

    Le collecteur les efface lui-même, succès ou échec (``ecrire_archive``) :
    en dehors d'un passage en cours, un tel fichier est le reste d'un
    processus tué net (plafond mémoire, coupure). Les dossiers cachés
    (``.rsync-partiel/``) ne sont pas parcourus.
    """
    dossier = racine / DOSSIER_BRONZE
    if not dossier.is_dir():
        return []
    partiels: list[Path] = []
    for parent, sous_dossiers, noms in os.walk(dossier):
        sous_dossiers[:] = sorted(nom for nom in sous_dossiers if not nom.startswith("."))
        partiels.extend(Path(parent) / nom for nom in sorted(noms) if MOTIF_PARTIEL.match(nom))
    return partiels


def _visibles(dossier: Path) -> list[Path]:
    return sorted(element for element in dossier.iterdir() if not element.name.startswith("."))


def _analyser(chemin: Path, source: str, fichier: str) -> Archive:
    correspondance = MOTIF_NOM.match(chemin.name)
    if correspondance is None:
        raise NomArchiveInvalide(
            f"{chemin} : nom sans la forme <horodatage>__<sha256 12 car.>.<ext>.gz"
        )
    horodatage = datetime.strptime(correspondance["horodatage"], FORMAT_HORODATAGE).replace(
        tzinfo=UTC
    )
    return Archive(
        chemin=chemin,
        source=source,
        fichier=fichier,
        horodatage=horodatage,
        sha256_prefixe=correspondance["sha256"],
    )
