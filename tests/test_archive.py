"""L'archive bronze : chemin, immuabilité, écriture interrompue."""

import gzip
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pharmaflux.collecte.archive import (
    ArchiveExistante,
    chemin_archive,
    ecrire_archive,
    lire_archive,
)
from pharmaflux.collecte.empreintes import sha256_hex
from tests.conftest import entree

INSTANT = datetime(2026, 10, 24, 14, 17, 3, tzinfo=UTC)
CONTENU = "61266250\tA 313 200 000 UI POUR CENT, pommade\r\n".encode("cp1252")


def test_chemin_archive(tmp_path: Path) -> None:
    sha = sha256_hex(CONTENU)
    chemin = chemin_archive(tmp_path, entree("bdpm.specialites"), INSTANT, sha)
    assert chemin == (
        tmp_path / "bronze/bdpm/CIS_bdpm.txt/2026-10-24" / f"20261024T141703Z__{sha[:12]}.txt.gz"
    )
    page = chemin_archive(tmp_path, entree("bdpm.page_telechargement"), INSTANT, sha)
    assert page.name.endswith(".html.gz") and page.parent.parent.name == "telechargement.html"
    meta = chemin_archive(tmp_path, entree("openmedic.metadonnees"), INSTANT, sha)
    assert meta.parts[-4:-1] == ("openmedic", "metadonnees.json", "2026-10-24")
    assert meta.name.endswith(".json.gz")


def test_ecrit_les_octets_bruts_compresses(tmp_path: Path) -> None:
    chemin = tmp_path / "bronze/x/y/2026-10-24/a__b.txt.gz"
    ecrire_archive(chemin, CONTENU, INSTANT)
    assert chemin.exists()
    with gzip.open(chemin, "rb") as fichier:
        assert fichier.read() == CONTENU
    assert lire_archive(chemin) == CONTENU
    assert [p.name for p in chemin.parent.iterdir()] == [chemin.name], "aucun fichier temporaire"


def test_refuse_de_reecrire(tmp_path: Path) -> None:
    chemin = tmp_path / "a__b.txt.gz"
    ecrire_archive(chemin, CONTENU, INSTANT)
    with pytest.raises(ArchiveExistante):
        ecrire_archive(chemin, b"autre contenu", INSTANT)
    assert lire_archive(chemin) == CONTENU, "le contenu d'origine est intact"


def test_ecriture_interrompue_ne_laisse_rien(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chemin = tmp_path / "bronze/x/y/2026-10-24/a__b.txt.gz"

    def ecriture_qui_casse(_self: gzip.GzipFile, _data: bytes) -> int:
        raise OSError("disque plein")

    monkeypatch.setattr(gzip.GzipFile, "write", ecriture_qui_casse)
    with pytest.raises(OSError, match="disque plein"):
        ecrire_archive(chemin, CONTENU, INSTANT)
    assert not chemin.exists()
    assert list(chemin.parent.iterdir()) == [], "ni archive partielle ni fichier temporaire"
