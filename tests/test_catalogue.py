"""Le catalogue déclare treize entrées cohérentes."""

import pytest

from pharmaflux.collecte.catalogue import (
    CATALOGUE,
    Cadence,
    IdentifiantInconnu,
    ModeEmpreinte,
    entrees_bdpm_par_url,
    par_identifiant,
)


def test_treize_entrees_identifiants_uniques() -> None:
    assert len(CATALOGUE) == 13
    identifiants = [e.identifiant for e in CATALOGUE]
    assert len(set(identifiants)) == 13
    assert all(e.url.startswith("https://") for e in CATALOGUE)
    assert all("é" not in e.identifiant and " " not in e.fichier for e in CATALOGUE)


def test_la_page_est_en_tete() -> None:
    assert CATALOGUE[0].identifiant == "bdpm.page_telechargement"
    assert CATALOGUE[0].empreinte is ModeEmpreinte.PAGE_BDPM
    assert CATALOGUE[0].extension == ".html"


def test_onze_fichiers_bdpm_et_les_cas_particuliers() -> None:
    fichiers = entrees_bdpm_par_url()
    assert len(fichiers) == 11
    infos = next(e for e in fichiers.values() if e.fichier == "CIS_InfoImportantes.txt")
    assert infos.url.endswith("/download/CIS_InfoImportantes.txt")
    assert infos.empreinte is ModeEmpreinte.LIGNES_TRIEES
    openmedic = CATALOGUE[-1]
    assert openmedic.cadence is Cadence.QUOTIDIENNE
    assert openmedic.extension == ".json"


def test_par_identifiant_garde_l_ordre_du_catalogue() -> None:
    choisies = par_identifiant(["bdpm.mitm", "bdpm.specialites"])
    assert [e.identifiant for e in choisies] == ["bdpm.specialites", "bdpm.mitm"]


def test_identifiant_inconnu() -> None:
    with pytest.raises(IdentifiantInconnu, match=r"bdpm\.inexistant"):
        par_identifiant(["bdpm.specialites", "bdpm.inexistant"])
