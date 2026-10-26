"""La lecture du bronze : ordre chronologique, octets bruts, fichiers cachés ignorés."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pharmaflux import bronze
from pharmaflux.collecte.archive import chemin_archive, ecrire_archive
from pharmaflux.collecte.empreintes import sha256_hex
from tests.conftest import entree

SPECIALITES = entree("bdpm.specialites")
INSTANTS = (
    datetime(2026, 10, 24, 14, 17, 3, tzinfo=UTC),
    datetime(2026, 10, 24, 23, 17, 4, tzinfo=UTC),
    datetime(2026, 10, 25, 9, 17, 2, tzinfo=UTC),
)


def _archiver(racine: Path, instant: datetime, contenu: bytes) -> Path:
    chemin = chemin_archive(racine, SPECIALITES, instant, sha256_hex(contenu))
    ecrire_archive(chemin, contenu, instant)
    return chemin


@pytest.fixture
def racine_bronze(racine: Path) -> Path:
    # Écrites dans le désordre : l'ordre rendu doit venir du nom, pas du disque.
    for indice in (2, 0, 1):
        _archiver(racine, INSTANTS[indice], f"contenu {indice}\r\n".encode("cp1252"))
    jour = racine / "bronze" / "bdpm" / "CIS_bdpm.txt" / "2026-10-24"
    (jour / ".20261024T151703Z__abcdef012345.txt.gz.partiel-4242").write_bytes(b"coupe")
    (jour / ".DS_Store").write_bytes(b"")
    rsync = jour / ".rsync-partiel"
    rsync.mkdir()
    (rsync / "20261024T161703Z__abcdef012345.txt.gz").write_bytes(b"morceau")
    (rsync / ".x.partiel-1").write_bytes(b"")
    return racine


def test_lister_dans_l_ordre_chronologique(racine_bronze: Path) -> None:
    archives = bronze.lister(racine_bronze, "bdpm", "CIS_bdpm.txt")
    assert [archive.horodatage for archive in archives] == list(INSTANTS)
    assert [archive.lire() for archive in archives] == [
        f"contenu {indice}\r\n".encode("cp1252") for indice in (0, 1, 2)
    ]
    premiere = archives[0]
    assert premiere.source == "bdpm" and premiere.fichier == "CIS_bdpm.txt"
    assert premiere.horodatage.tzinfo is UTC
    assert premiere.sha256_prefixe == premiere.chemin.name.split("__")[1][:12]
    assert premiere.relatif(racine_bronze) == (
        f"bronze/bdpm/CIS_bdpm.txt/2026-10-24/{premiere.chemin.name}"
    )


def test_derniere(racine_bronze: Path) -> None:
    derniere = bronze.derniere(racine_bronze, "bdpm", "CIS_bdpm.txt")
    assert derniere is not None and derniere.horodatage == INSTANTS[-1]
    assert bronze.derniere(racine_bronze, "bdpm", "CIS_MITM.txt") is None
    assert bronze.lister(racine_bronze / "absente", "bdpm", "CIS_bdpm.txt") == []


def test_fichiers_partiels_sans_les_dossiers_caches(racine_bronze: Path) -> None:
    partiels = bronze.fichiers_partiels(racine_bronze)
    assert [chemin.name for chemin in partiels] == [
        ".20261024T151703Z__abcdef012345.txt.gz.partiel-4242"
    ], "le .rsync-partiel/ et le .DS_Store ne comptent pas"
    assert bronze.fichiers_partiels(racine_bronze / "absente") == []


def test_nom_inattendu_refuse(racine_bronze: Path) -> None:
    jour = racine_bronze / "bronze" / "bdpm" / "CIS_bdpm.txt" / "2026-10-25"
    (jour / "copie.txt.gz").write_bytes(b"")
    with pytest.raises(bronze.NomArchiveInvalide, match=r"copie\.txt\.gz"):
        bronze.lister(racine_bronze, "bdpm", "CIS_bdpm.txt")


def test_lire_archive_sans_extension() -> None:
    correspondance = bronze.MOTIF_NOM.match("20261024T141703Z__0123456789ab.gz")
    assert correspondance is not None and correspondance["extension"] == ""
