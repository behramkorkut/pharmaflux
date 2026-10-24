"""La ligne de commande répond : aide, version, commandes déclarées."""

from typer.testing import CliRunner

from pharmaflux.cli import application

lanceur = CliRunner()


def test_aide_liste_les_commandes() -> None:
    resultat = lanceur.invoke(application, ["--help"])
    assert resultat.exit_code == 0
    assert "collecte" in resultat.output
    assert "etat" in resultat.output


def test_sans_argument_affiche_l_aide() -> None:
    resultat = lanceur.invoke(application, [])
    assert "collecte" in resultat.output


def test_version() -> None:
    resultat = lanceur.invoke(application, ["--version"])
    assert resultat.exit_code == 0
    assert resultat.output.startswith("pharmaflux 0.")


def test_commandes_declarees_non_livrees() -> None:
    for arguments in (["collecte"], ["collecte", "--source", "bdpm.specialites"], ["etat"]):
        resultat = lanceur.invoke(application, arguments)
        assert resultat.exit_code == 2, arguments
