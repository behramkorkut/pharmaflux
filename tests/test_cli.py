"""La ligne de commande : aide, version, collecte et état sur le serveur simulé."""

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.cli import application
from tests.conftest import ServeurSimule

lanceur = CliRunner()


def test_aide_liste_les_commandes() -> None:
    resultat = lanceur.invoke(application, ["--help"])
    assert resultat.exit_code == 0
    assert "collecte" in resultat.output and "etat" in resultat.output


def test_sans_argument_affiche_l_aide() -> None:
    resultat = lanceur.invoke(application, [])
    assert "collecte" in resultat.output


def test_version() -> None:
    resultat = lanceur.invoke(application, ["--version"])
    assert resultat.exit_code == 0
    assert resultat.output.startswith("pharmaflux 0.")


def test_catalogue() -> None:
    resultat = lanceur.invoke(application, ["catalogue"])
    assert resultat.exit_code == 0
    assert len(resultat.output.splitlines()) == 14


def test_source_inconnue() -> None:
    resultat = lanceur.invoke(application, ["collecte", "--source", "bdpm.inexistant"])
    assert resultat.exit_code == 2
    assert "bdpm.inexistant" in resultat.output


def test_collecte_puis_etat(
    racine: Path, serveur: ServeurSimule, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "fabriquer_transport", serveur.transport)
    monkeypatch.setattr("pharmaflux.collecte.passage.PAUSE_SECONDES", 0)
    monkeypatch.setattr("time.sleep", lambda _: None)
    arguments = ["collecte", "--racine", str(racine), "--source", "bdpm.page_telechargement"]
    arguments += ["--source", "bdpm.specialites"]
    resultat = lanceur.invoke(application, arguments)
    assert resultat.exit_code == 0, resultat.output
    assert "2 nouveau(x)" in resultat.output
    assert (racine / "manifeste" / "collecte.jsonl").exists()

    etat = lanceur.invoke(application, ["etat", "--racine", str(racine)])
    assert etat.exit_code == 0, etat.output
    assert "bdpm.specialites" in etat.output and "CIS_bdpm.txt" in etat.output
    assert "2 lignes de manifeste" in etat.output
    assert "aucun fichier partiel dans bronze/." in etat.output


def test_etat_signale_les_fichiers_partiels(
    racine: Path, serveur: ServeurSimule, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "fabriquer_transport", serveur.transport)
    monkeypatch.setattr("time.sleep", lambda _: None)
    lanceur.invoke(application, ["collecte", "--racine", str(racine), "--source", "bdpm.mitm"])
    jour = next((racine / "bronze" / "bdpm" / "CIS_MITM.txt").iterdir())
    (jour / ".20261024T151703Z__abcdef012345.txt.gz.partiel-4242").write_bytes(b"coupe")
    (jour / ".rsync-partiel").mkdir()
    (jour / ".rsync-partiel" / "20261024T161703Z__abcdef012345.txt.gz").write_bytes(b"morceau")

    etat = lanceur.invoke(application, ["etat", "--racine", str(racine)])
    assert etat.exit_code == 0, etat.output
    assert "1 fichier(s) partiel(s) dans bronze/" in etat.output
    assert ".partiel-4242  (modifié le 20" in etat.output
    assert ".rsync-partiel" not in etat.output


def test_journal_en_utc() -> None:
    """Mission 01, décision 9 : les horodatages du journal sont en UTC, comme le manifeste."""
    instant = datetime(2026, 10, 24, 14, 17, 3, tzinfo=UTC)
    enregistrement = logging.LogRecord("pharmaflux", logging.INFO, "", 0, "début", None, None)
    enregistrement.created = instant.timestamp()
    texte = cli.FormateurUTC("%(asctime)s %(levelname)s %(message)s").format(enregistrement)
    assert texte == "2026-10-24T14:17:03Z INFO début"


def test_collecte_en_erreur_sort_non_nul(
    racine: Path, serveur: ServeurSimule, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "fabriquer_transport", serveur.transport)
    monkeypatch.setattr("time.sleep", lambda _: None)
    serveur.scenariser(
        "https://base-donnees-publique.medicaments.gouv.fr/download/file/CIS_MITM.txt",
        (404, b"", {}),
    )
    resultat = lanceur.invoke(
        application, ["collecte", "--racine", str(racine), "--source", "bdpm.mitm"]
    )
    assert resultat.exit_code == 1
    assert "1 erreur(s)" in resultat.output


def test_racine_par_variable_d_environnement(racine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHARMAFLUX_DATA", str(racine))
    resultat = lanceur.invoke(application, ["etat"])
    assert resultat.exit_code == 0
    assert str(racine) in resultat.output and "aucun passage" in resultat.output
