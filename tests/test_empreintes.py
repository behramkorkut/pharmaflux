"""Lecture de la page et empreintes de comparaison, sur les extraits réels."""

import json

import pytest

from pharmaflux.collecte.catalogue import SITE_BDPM, ModeEmpreinte
from pharmaflux.collecte.empreintes import empreinte_comparaison, projection_datagouv, sha256_hex
from pharmaflux.collecte.page import AnalyseImpossible, analyser_page
from tests.conftest import contenu_fixture, entree

PAGE = contenu_fixture(entree("bdpm.page_telechargement"))
INFOS = contenu_fixture(entree("bdpm.infos_importantes"))
METADONNEES = contenu_fixture(entree("openmedic.metadonnees"))


def test_la_page_donne_onze_liens_avec_date_et_taille() -> None:
    liens = analyser_page(PAGE)
    assert len(liens) == 12, "onze fichiers de données et la documentation PDF du format"
    assert sum(lien.est_fichier_de_donnees for lien in liens) == 11
    pdf = next(lien for lien in liens if not lien.est_fichier_de_donnees)
    assert pdf.nom.endswith(".pdf") and pdf.date_affichee is None
    par_nom = {lien.nom: lien for lien in liens}
    specialites = par_nom["CIS_bdpm.txt"]
    assert specialites.url == f"{SITE_BDPM}/download/file/CIS_bdpm.txt"
    assert specialites.libelle == "Fichier des spécialités"
    assert specialites.date_affichee == "2026-09-29"
    assert specialites.taille_affichee_ko == 3101
    assert par_nom["CIS_CIP_bdpm.txt"].date_affichee == "2026-10-23"
    infos = par_nom["CIS_InfoImportantes.txt"]
    assert infos.url == f"{SITE_BDPM}/download/CIS_InfoImportantes.txt"
    assert infos.date_affichee is None and infos.taille_affichee_ko is None


def test_page_sans_lien_refusee() -> None:
    with pytest.raises(AnalyseImpossible):
        analyser_page(b"<html><body>Maintenance en cours</body></html>")


def test_lignes_triees_ignorent_l_ordre_mais_pas_le_contenu() -> None:
    lignes = INFOS.split(b"\n")
    melangees = b"\n".join(lignes[::-1])
    assert melangees != INFOS
    empreinte = empreinte_comparaison(ModeEmpreinte.LIGNES_TRIEES, INFOS)
    assert empreinte == empreinte_comparaison(ModeEmpreinte.LIGNES_TRIEES, melangees)
    assert empreinte != empreinte_comparaison(ModeEmpreinte.LIGNES_TRIEES, INFOS + b"60000000\tx\n")
    assert empreinte != sha256_hex(INFOS)


def test_page_ignore_le_nonce_mais_pas_une_date() -> None:
    empreinte = empreinte_comparaison(ModeEmpreinte.PAGE_BDPM, PAGE)
    autre_nonce = PAGE.replace(b"7KSjne/4hYYj0QHlCN6aaA==", b"AUTRE_NONCE_A_CHAQUE_REPONSE")
    assert autre_nonce != PAGE
    assert empreinte == empreinte_comparaison(ModeEmpreinte.PAGE_BDPM, autre_nonce)
    date_changee = PAGE.replace(b"29/09/2026, 3101 Ko", b"30/10/2026, 3101 Ko", 1)
    assert empreinte != empreinte_comparaison(ModeEmpreinte.PAGE_BDPM, date_changee)
    taille_changee = PAGE.replace(b"29/09/2026, 3101 Ko", b"29/09/2026, 3102 Ko", 1)
    assert empreinte != empreinte_comparaison(ModeEmpreinte.PAGE_BDPM, taille_changee)


def test_metadonnees_ignorent_le_robot_mais_pas_une_ressource() -> None:
    jeu = json.loads(METADONNEES)
    empreinte = empreinte_comparaison(ModeEmpreinte.METADONNEES_DATAGOUV, METADONNEES)

    bruit = json.loads(METADONNEES)
    bruit["metrics"]["views"] += 1
    bruit["last_update"] = "2026-12-31T00:00:00+00:00"
    bruit["resources"][0]["last_modified"] = "2026-12-31T00:00:00+00:00"
    bruit["resources"].reverse()
    assert empreinte == empreinte_comparaison(
        ModeEmpreinte.METADONNEES_DATAGOUV, json.dumps(bruit).encode()
    )

    publication = json.loads(METADONNEES)
    publication["resources"].append(
        dict(jeu["resources"][0], id="nouvelle", title="Open Medic 2026")
    )
    assert empreinte != empreinte_comparaison(
        ModeEmpreinte.METADONNEES_DATAGOUV, json.dumps(publication).encode()
    )
    correctif = json.loads(METADONNEES)
    correctif["last_modified"] = "2026-12-31T00:00:00+00:00"
    assert empreinte != empreinte_comparaison(
        ModeEmpreinte.METADONNEES_DATAGOUV, json.dumps(correctif).encode()
    )


def test_projection_datagouv() -> None:
    projection = projection_datagouv(METADONNEES)
    assert projection["nombre_ressources"] == 6
    assert projection["last_modified"] == "2026-07-11T20:34:33.736000+00:00"
    assert set(projection["ressources"][0]) == {
        "id",
        "title",
        "url",
        "format",
        "created_at",
        "description",
    }


def test_json_invalide_refuse() -> None:
    with pytest.raises(AnalyseImpossible):
        empreinte_comparaison(ModeEmpreinte.METADONNEES_DATAGOUV, b"<html>erreur</html>")
    with pytest.raises(AnalyseImpossible):
        empreinte_comparaison(ModeEmpreinte.METADONNEES_DATAGOUV, b'{"resources": null}')
