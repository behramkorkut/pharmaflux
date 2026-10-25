"""Archive bronze : écriture immuable des octets reçus, compressés.

Chemin : ``<racine>/bronze/<source>/<fichier>/<AAAA-MM-JJ>/``
``<horodatage UTC>__<sha256 12 car.><ext>.gz``.
Le contenu est écrit dans un fichier temporaire du même dossier, puis lié
sous son nom définitif par ``os.link`` : l'opération échoue si le chemin
existe déjà, il n'y a donc jamais de réécriture ni de fichier partiel
visible sous un nom d'archive.
"""

from __future__ import annotations

import gzip
import os
from datetime import datetime
from pathlib import Path

from pharmaflux.collecte.catalogue import Entree

FORMAT_HORODATAGE = "%Y%m%dT%H%M%SZ"


class ArchiveExistante(FileExistsError):  # noqa: N818 (nom français voulu)
    """Le chemin d'archive existe déjà : on ne réécrit jamais."""


def chemin_archive(racine: Path, entree: Entree, horodatage: datetime, sha256: str) -> Path:
    """Le chemin d'archive d'un contenu reçu à ``horodatage`` (UTC)."""
    nom = f"{horodatage.strftime(FORMAT_HORODATAGE)}__{sha256[:12]}{entree.extension}.gz"
    return (
        racine / "bronze" / entree.source / entree.fichier / horodatage.strftime("%Y-%m-%d") / nom
    )


def ecrire_archive(chemin: Path, contenu: bytes, horodatage: datetime) -> None:
    """Écrit ``contenu`` compressé sous ``chemin``. Lève ``ArchiveExistante`` s'il existe."""
    if chemin.exists():
        raise ArchiveExistante(str(chemin))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.parent / f".{chemin.name}.partiel-{os.getpid()}"
    try:
        with temporaire.open("wb") as fichier:
            with gzip.GzipFile(
                filename="", fileobj=fichier, mode="wb", mtime=int(horodatage.timestamp())
            ) as compresseur:
                compresseur.write(contenu)
            fichier.flush()
            os.fsync(fichier.fileno())
        try:
            os.link(temporaire, chemin)
        except FileExistsError as exc:
            raise ArchiveExistante(str(chemin)) from exc
    finally:
        temporaire.unlink(missing_ok=True)


def lire_archive(chemin: Path) -> bytes:
    """Les octets bruts d'une archive (décompression seulement)."""
    with gzip.open(chemin, "rb") as fichier:
        return fichier.read()
