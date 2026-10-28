"""Mission 05, palier 1 : le silver du jeu de démo ``demo/archive``, de bout en bout.

Les événements sont calculés dans un dossier jetable (``pharmaflux evenements
--racine demo/archive``), le silver construit, vérifié contre les 18 archives
retenues (et les 4 écartées), interrogé aux instants du README, et comparé à
une seconde construction. Une trentaine de secondes ; une seule fois par
session de tests. Aucun réseau, aucun conteneur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.demo.jeu import JEU_PAR_DEFAUT
from pharmaflux.evenements import rejeu
from pharmaflux.silver import comparaison, construction, verification
from pharmaflux.silver import etat as etat_silver
from pharmaflux.silver.entrepot import Entrepot

ARCHIVE_VIDE_ECARTEE = "2026-10-26T14:17:39Z"  # CIS_InfoImportantes.txt servi vide, écarté
PREMIERE_SUPPRESSION = "2026-10-24T23:17:12Z"  # 2 présentations disparaissent


@pytest.fixture(scope="module")
def demo_silver(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    sortie = tmp_path_factory.mktemp("demo") / "evenements"
    rapport = rejeu.executer(JEU_PAR_DEFAUT, sortie, charger_tous(), list(charger_tous()))
    assert rapport.code_sortie == 0
    dossier = tmp_path_factory.mktemp("demo") / "lakehouse"
    construction.construire(sortie, dossier, charger_tous(), list(charger_tous()))
    return sortie, dossier


def test_le_silver_du_jeu_est_conforme_aux_18_archives_retenues(
    demo_silver: tuple[Path, Path],
) -> None:
    sortie, dossier = demo_silver
    silver = Entrepot.ouvrir(dossier)
    assert len(silver.entites()) == 11
    rapport = verification.verifier(
        silver, sortie, JEU_PAR_DEFAUT, charger_tous(), list(charger_tous())
    )
    assert rapport.code_sortie == 0, [
        (a.archive, a.differences) for e in rapport.entites for a in e.archives if not a.conforme
    ] + [e.invariants for e in rapport.entites]
    decisions = [a.decision for e in rapport.entites for a in e.archives]
    assert decisions.count("retenu") == 18 and decisions.count("ecarte") == 4
    assert rapport.archives_conformes == rapport.archives_verifiees == 22
    assert sum(e.versions for e in rapport.entites) == 164_096
    assert sum(e.ouvertes for e in rapport.entites) == 164_086


def test_etats_du_readme(demo_silver: tuple[Path, Path]) -> None:
    _, dossier = demo_silver
    silver = Entrepot.ouvrir(dossier)
    presentations = silver.table("bdpm.presentations")
    infos = silver.table("bdpm.infos_importantes")
    assert presentations is not None and infos is not None
    # Dix présentations supprimées en trois fois : 20 898, 20 896, 20 895, 20 888.
    comptes = [
        etat_silver.etat_a(presentations, etat_silver.lire_instant(a)).num_rows
        for a in (
            "2026-10-24T19:41:46Z",
            "2026-10-24T23:17:11Z",
            PREMIERE_SUPPRESSION,
            "2026-10-26T00:17:12Z",
            "2026-10-27T00:17:08Z",  # le passage, quatre secondes avant l'archive
            "2026-10-27T00:17:12Z",
            "2026-11-01",
        )
    ]
    assert comptes == [20_898, 20_898, 20_896, 20_895, 20_895, 20_888, 20_888]
    # Une présentation disparue : présente juste avant, absente juste après.
    avant = etat_silver.etat_a(presentations, etat_silver.lire_instant("2026-10-24T23:17:11Z"))
    apres = etat_silver.etat_a(presentations, etat_silver.lire_instant(PREMIERE_SUPPRESSION))
    disparues = set(avant["code_cip13"].to_pylist()) - set(apres["code_cip13"].to_pylist())
    assert len(disparues) == 2
    cip = sorted(disparues)[0]
    assert (
        etat_silver.etat_a(
            presentations, etat_silver.lire_instant(PREMIERE_SUPPRESSION), {"code_cip13": cip}
        ).num_rows
        == 0
    )
    seule = etat_silver.etat_a(
        presentations, etat_silver.lire_instant("2026-10-24T23:17:11Z"), {"code_cip13": cip}
    )
    assert seule.num_rows == 1 and seule["fin_validite"][0].as_py() == etat_silver.lire_instant(
        PREMIERE_SUPPRESSION
    )
    # Le fichier vide écarté le 26/10 à 14:17:39 : l'état n'a pas bougé, tout est ouvert.
    a_14h17 = etat_silver.etat_a(infos, etat_silver.lire_instant(ARCHIVE_VIDE_ECARTEE))
    assert a_14h17.num_rows == 10_905 and a_14h17["fin_validite"].null_count == 10_905
    assert etat_silver.bornes(infos) == (
        etat_silver.lire_instant("2026-10-24T19:42:06Z"),
        etat_silver.lire_instant("2026-10-24T19:42:06Z"),
    )


def test_commandes_sur_le_jeu_et_seconde_construction_identique(
    demo_silver: tuple[Path, Path], tmp_path: Path
) -> None:
    sortie, dossier = demo_silver
    lanceur = CliRunner()
    r = lanceur.invoke(
        application,
        [
            "silver",
            "etat",
            "--entite",
            "bdpm.infos_importantes",
            "--a",
            ARCHIVE_VIDE_ECARTEE,
            "--entrepot",
            str(dossier),
            "--colonne",
            "code_cis",
            "--colonne",
            "fin_validite",
        ],
    )
    assert r.exit_code == 0 and "10905 version(s) valide(s)" in r.output
    assert "s'arrête à la dernière observation (2026-10-24T19:42:06Z)" in r.output
    assert sum(1 for ligne_ in r.stdout.splitlines() if ligne_.startswith("{")) == 10_905
    assert json.loads(r.stdout.splitlines()[0]) == {
        "code_cis": json.loads(r.stdout.splitlines()[0])["code_cis"],
        "fin_validite": None,
    }
    r = lanceur.invoke(
        application,
        [
            "silver",
            "sql",
            "SELECT count(*) AS n, count(fin_validite) AS fermees FROM presentations",
            "--entrepot",
            str(dossier),
            "--format",
            "csv",
        ],
    )
    assert r.exit_code == 0 and r.stdout.splitlines()[:2] == ["n,fermees", "20898,10"]
    autre = tmp_path / "autre"
    construction.construire(sortie, autre, charger_tous(), list(charger_tous()), lot=25_000)
    assert comparaison.comparer(Entrepot.ouvrir(dossier), Entrepot.ouvrir(autre)) == []
    r = lanceur.invoke(
        application,
        [
            "silver",
            "verifier",
            "--entrepot",
            str(autre),
            "--sortie",
            str(sortie),
            "--racine",
            str(JEU_PAR_DEFAUT),
            "--fichier",
            "bdpm.presentations",
            "--fichier",
            "CIS_InfoImportantes.txt",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "13/13 archive(s) conforme(s)" in r.output  # 4 présentations, 9 informations
