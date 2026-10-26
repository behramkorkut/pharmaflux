"""Un passage de bout en bout, sur le serveur simulé : tous les cas de l'ordre de mission."""

import json
import logging
from pathlib import Path

import httpx
import pytest

from pharmaflux.bronze import lire_archive
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.archive import chemin_archive, ecrire_archive
from pharmaflux.collecte.catalogue import CATALOGUE, SITE_BDPM, ModeEmpreinte
from pharmaflux.collecte.empreintes import sha256_hex
from pharmaflux.collecte.etat import calculer_etat
from pharmaflux.collecte.manifeste import CHAMPS, Statut
from tests.conftest import Horloge, Lanceur, ServeurSimule, contenu_fixture, entree

PAGE = entree("bdpm.page_telechargement")
SPECIALITES = entree("bdpm.specialites")
INFOS = entree("bdpm.infos_importantes")
MITM = entree("bdpm.mitm")
DOCUMENTATION = entree("bdpm.documentation_formats")
OPENMEDIC = entree("openmedic.metadonnees")
NONCE_RECU = b"7KSjne/4hYYj0QHlCN6aaA=="
PAGE_SANS_MITM = contenu_fixture(PAGE).replace(
    b'href="/download/file/CIS_MITM.txt"', b'href="/download/file/CIS_MITM_v2.txt"'
)
PAGE_MAINTENANCE = b"<html><body>Maintenance</body></html>"
DOC_V6 = DOCUMENTATION.fichier.replace("_v5.pdf", "_v6.pdf")
URL_DOC_V6 = DOCUMENTATION.url.replace("_v5.pdf", "_v6.pdf")
PAGE_DOC_V6 = contenu_fixture(PAGE).replace(b"_BDM_v5.pdf", b"_BDM_v6.pdf")


def _archives(racine: Path, fichier: str) -> list[Path]:
    return sorted((racine / "bronze" / "bdpm" / fichier).rglob("*.gz"))


def _lignes(racine: Path) -> list[dict[str, object]]:
    chemin = manifeste.chemin_manifeste(racine)
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines()]


def _par_fichier(racine: Path, passage_id: str) -> dict[str, dict[str, object]]:
    return {
        str(ligne["fichier"]): ligne
        for ligne in _lignes(racine)
        if ligne["passage_id"] == passage_id
    }


def test_premier_passage_archive_tout(
    lancer: Lanceur, racine: Path, serveur: ServeurSimule
) -> None:
    bilan = lancer()
    assert bilan.code_sortie == 0
    assert bilan.passage_id == "20261024T141700Z"
    assert bilan.compter(Statut.NOUVEAU) == 14 and bilan.compter(Statut.ERREUR) == 0
    assert len(serveur.requetes) == 14, "une requête par entrée, aucune autre"

    lignes = _par_fichier(racine, bilan.passage_id)
    assert len(lignes) == 14
    for entree_catalogue in CATALOGUE:
        ligne = lignes[entree_catalogue.fichier]
        brut = contenu_fixture(entree_catalogue)
        assert ligne["statut"] == "nouveau"
        assert ligne["sha256"] == sha256_hex(brut)
        assert ligne["taille_octets"] == len(brut)
        assert ligne["essais"] == 1 and ligne["http_statut"] == 200
        chemin = racine / str(ligne["chemin_archive"])
        assert chemin.is_file(), "le chemin du manifeste est relatif à la racine"
        assert lire_archive(chemin) == brut, "octets bruts, à l'identique"
        assert chemin.name.endswith(entree_catalogue.extension + ".gz")

    specialites = lignes["CIS_bdpm.txt"]
    assert specialites["date_source_affichee"] == "2026-09-29"
    assert specialites["taille_affichee_ko"] == 3101
    assert specialites["content_disposition_nom"] == "CIS_bdpm.txt"
    assert specialites["last_modified"] is None and specialites["etag"] is None
    infos = lignes["CIS_InfoImportantes.txt"]
    assert infos["date_source_affichee"] is None
    assert infos["content_disposition_nom"] == "CIS_InfoImportantes_20261024132108_bdpm.txt"
    assert infos["empreinte_comparaison"] != infos["sha256"]
    assert lignes["telechargement.html"]["date_source_affichee"] is None
    assert str(lignes["CIS_bdpm.txt"]["version_collecteur"]).startswith("0.1.0")


def test_passage_inchange_n_archive_rien(lancer: Lanceur, racine: Path, horloge: Horloge) -> None:
    premier = lancer()
    archives_avant = sorted(p for p in (racine / "bronze").rglob("*.gz"))
    horloge.avancer(hours=1)
    second = lancer()
    assert second.passage_id != premier.passage_id
    assert second.compter(Statut.INCHANGE) == 12, "tout sauf les quotidiennes, déjà collectées"
    assert second.compter(Statut.NOUVEAU) == 0 and second.code_sortie == 0
    assert sorted(p for p in (racine / "bronze").rglob("*.gz")) == archives_avant
    lignes = _par_fichier(racine, second.passage_id)
    assert len(lignes) == 12 and "metadonnees.json" not in lignes
    assert DOCUMENTATION.fichier not in lignes
    assert all(ligne["chemin_archive"] is None and ligne["sha256"] for ligne in lignes.values())
    assert lignes["CIS_bdpm.txt"]["date_source_affichee"] == "2026-09-29"


def test_quotidienne_revient_le_lendemain_ou_apres_erreur(
    lancer: Lanceur, horloge: Horloge, serveur: ServeurSimule
) -> None:
    lancer([OPENMEDIC])
    horloge.avancer(hours=1)
    assert lancer([OPENMEDIC]).enregistrements == []
    horloge.avancer(days=1)
    assert lancer([OPENMEDIC]).compter(Statut.INCHANGE) == 1
    serveur.scenariser(OPENMEDIC.url, (500, b"", {}))
    horloge.avancer(days=1)
    assert lancer([OPENMEDIC]).compter(Statut.ERREUR) == 1
    horloge.avancer(hours=1)
    assert lancer([OPENMEDIC]).compter(Statut.ERREUR) == 1, (
        "une erreur ne vaut pas collecte du jour"
    )


def test_octets_differents_fond_identique_inchange(
    lancer: Lanceur, serveur: ServeurSimule, horloge: Horloge
) -> None:
    lancer()
    horloge.avancer(hours=1)
    infos = contenu_fixture(INFOS).split(b"\n")
    serveur.remplacer_contenu(INFOS.url, b"\n".join(infos[::-1]))
    serveur.remplacer_contenu(PAGE.url, contenu_fixture(PAGE).replace(NONCE_RECU, b"AUTRE_NONCE"))
    bilan = lancer([PAGE, INFOS])
    assert [e.statut for e in bilan.enregistrements] == ["inchange", "inchange"]
    assert bilan.enregistrements[1].sha256 != sha256_hex(contenu_fixture(INFOS))


def test_changement_reel_archive(lancer: Lanceur, serveur: ServeurSimule, horloge: Horloge) -> None:
    lancer()
    horloge.avancer(hours=1)
    page = contenu_fixture(PAGE).replace(b"29/09/2026, 3101 Ko", b"25/10/2026, 3105 Ko", 1)
    serveur.remplacer_contenu(PAGE.url, page)
    serveur.remplacer_contenu(SPECIALITES.url, contenu_fixture(SPECIALITES) + b"nouvelle ligne\r\n")
    bilan = lancer([PAGE, SPECIALITES, INFOS])
    statuts = {e.fichier: e.statut for e in bilan.enregistrements}
    assert statuts == {
        "telechargement.html": "nouveau",
        "CIS_bdpm.txt": "nouveau",
        "CIS_InfoImportantes.txt": "inchange",
    }
    specialites = bilan.enregistrements[1]
    assert specialites.date_source_affichee == "2026-10-25"
    assert specialites.taille_affichee_ko == 3105
    assert specialites.chemin_archive and "2026-10-24/20261024T1517" in specialites.chemin_archive


def test_reponse_304(lancer: Lanceur, serveur: ServeurSimule) -> None:
    serveur.scenariser(OPENMEDIC.url, (304, b"", {"ETag": '"v1"'}))
    bilan = lancer([OPENMEDIC])
    (ligne,) = bilan.enregistrements
    assert ligne.statut == "non_modifie_304" and ligne.http_statut == 304
    assert ligne.etag == '"v1"' and ligne.sha256 is None and ligne.chemin_archive is None
    assert bilan.code_sortie == 0


def test_erreur_reseau_puis_succes(lancer: Lanceur, serveur: ServeurSimule) -> None:
    fixture = (200, contenu_fixture(SPECIALITES), {})
    serveur.scenariser(SPECIALITES.url, httpx.ConnectError("reset"), fixture)
    bilan = lancer([SPECIALITES])
    (ligne,) = bilan.enregistrements
    assert ligne.statut == "nouveau" and ligne.essais == 2 and ligne.erreur is None


def test_erreur_definitive_n_arrete_pas_les_autres(
    lancer: Lanceur, serveur: ServeurSimule, racine: Path
) -> None:
    serveur.scenariser(SPECIALITES.url, (503, b"", {}))
    serveur.scenariser(INFOS.url, httpx.ConnectTimeout("delai"))
    bilan = lancer()
    assert bilan.code_sortie == 1
    assert bilan.compter(Statut.ERREUR) == 2 and bilan.compter(Statut.NOUVEAU) == 12
    lignes = _par_fichier(racine, bilan.passage_id)
    assert len(lignes) == 14, "aucun passage ne manque, même en erreur"
    specialites = lignes["CIS_bdpm.txt"]
    assert specialites["statut"] == "erreur" and specialites["http_statut"] == 503
    assert specialites["essais"] == 3 and specialites["erreur"] == "HTTP 503"
    assert specialites["date_source_affichee"] == "2026-09-29", "la page a quand même été lue"
    infos = lignes["CIS_InfoImportantes.txt"]
    assert infos["http_statut"] is None and "ConnectTimeout" in str(infos["erreur"])
    assert infos["chemin_archive"] is None


def test_archive_existante_refusee(lancer: Lanceur, racine: Path, horloge: Horloge) -> None:
    brut = contenu_fixture(SPECIALITES)
    # Le collecteur lit l'horloge pour le passage, puis pour le début de l'entrée : +1 s.
    instant_entree = horloge.instant.replace(second=1)
    chemin = chemin_archive(racine, SPECIALITES, instant_entree, sha256_hex(brut))
    ecrire_archive(chemin, b"contenu anterieur", instant_entree)
    bilan = lancer([SPECIALITES])
    (ligne,) = bilan.enregistrements
    assert ligne.statut == "erreur" and ligne.erreur == "archive_existante"
    assert ligne.chemin_archive is None and bilan.code_sortie == 1
    assert lire_archive(chemin) == b"contenu anterieur", "jamais de réécriture"


def test_ecriture_interrompue(
    lancer: Lanceur, racine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gzip

    def ecriture_qui_casse(_self: gzip.GzipFile, _data: bytes) -> int:
        raise OSError("disque plein")

    monkeypatch.setattr(gzip.GzipFile, "write", ecriture_qui_casse)
    bilan = lancer([SPECIALITES])
    (ligne,) = bilan.enregistrements
    assert ligne.statut == "erreur" and str(ligne.erreur).startswith("ecriture:")
    assert ligne.sha256 == sha256_hex(contenu_fixture(SPECIALITES))
    assert not [p for p in (racine / "bronze").rglob("*") if p.is_file()], "aucun partiel"
    assert len(_lignes(racine)) == 1


def test_lien_absent_et_lien_nouveau(lancer: Lanceur, serveur: ServeurSimule, racine: Path) -> None:
    serveur.remplacer_contenu(PAGE.url, PAGE_SANS_MITM)
    bilan = lancer()
    lignes = _par_fichier(racine, bilan.passage_id)
    assert len(lignes) == 15
    mitm = lignes["CIS_MITM.txt"]
    assert mitm["statut"] == "erreur" and mitm["erreur"] == "lien_absent"
    assert mitm["chemin_archive"], "le fichier est quand même archivé : l'archive est irremplaçable"
    nouveau = lignes["CIS_MITM_v2.txt"]
    assert nouveau["statut"] == "erreur" and str(nouveau["erreur"]).startswith("lien_nouveau:")
    assert nouveau["url"] == f"{SITE_BDPM}/download/file/CIS_MITM_v2.txt"
    assert nouveau["identifiant"] is None and nouveau["date_source_affichee"] == "2026-10-13"
    assert bilan.code_sortie == 1


def test_page_illisible_n_empeche_pas_les_fichiers(lancer: Lanceur, serveur: ServeurSimule) -> None:
    serveur.remplacer_contenu(PAGE.url, PAGE_MAINTENANCE)
    bilan = lancer([PAGE, SPECIALITES])
    page, specialites = bilan.enregistrements
    assert page.statut == "erreur" and str(page.erreur).startswith("analyse_impossible")
    assert page.chemin_archive, "la page reçue est archivée quand même"
    assert page.empreinte_comparaison == page.sha256, "repli sur les octets"
    assert specialites.statut == "nouveau" and specialites.date_source_affichee is None


def test_lien_absent_archive_une_seule_fois(
    lancer: Lanceur, serveur: ServeurSimule, racine: Path, horloge: Horloge
) -> None:
    """C1 : l'alerte dure, l'archive n'est écrite qu'une fois."""
    serveur.remplacer_contenu(PAGE.url, PAGE_SANS_MITM)
    lancer([PAGE, MITM])
    horloge.avancer(hours=1)
    bilan = lancer([PAGE, MITM])
    mitm = bilan.enregistrements[1]  # la troisième ligne est le lien nouveau CIS_MITM_v2.txt
    assert mitm.statut == "erreur" and mitm.erreur == "lien_absent"
    assert mitm.chemin_archive is None and mitm.empreinte_comparaison
    assert len(_archives(racine, MITM.fichier)) == 1
    assert bilan.code_sortie == 1, "l'alerte reste visible"


def test_page_illisible_archivee_une_seule_fois(
    lancer: Lanceur, serveur: ServeurSimule, racine: Path, horloge: Horloge
) -> None:
    """C1 : une page de maintenance identique n'est pas réarchivée à chaque passage."""
    serveur.remplacer_contenu(PAGE.url, PAGE_MAINTENANCE)
    lancer([PAGE])
    horloge.avancer(hours=1)
    (page,) = lancer([PAGE]).enregistrements
    assert page.statut == "erreur" and str(page.erreur).startswith("analyse_impossible")
    assert page.chemin_archive is None
    assert len(_archives(racine, PAGE.fichier)) == 1
    horloge.avancer(hours=1)
    serveur.remplacer_contenu(PAGE.url, contenu_fixture(PAGE))
    (page,) = lancer([PAGE]).enregistrements
    assert page.statut == "nouveau", "la page revenue est archivée"
    assert len(_archives(racine, PAGE.fichier)) == 2


def test_erreur_http_et_lien_absent_s_enchainent(lancer: Lanceur, serveur: ServeurSimule) -> None:
    """C1 : ``lien_absent`` n'écrase pas l'erreur de téléchargement."""
    serveur.remplacer_contenu(PAGE.url, PAGE_SANS_MITM)
    serveur.scenariser(MITM.url, (404, b"", {}))
    mitm = lancer([PAGE, MITM]).enregistrements[1]
    assert mitm.statut == "erreur" and mitm.http_statut == 404
    assert mitm.erreur == "HTTP 404 ; lien_absent"


def test_manifeste_tronque_n_arrete_pas_la_collecte(
    lancer: Lanceur, racine: Path, horloge: Horloge
) -> None:
    """C2 : une dernière ligne coupée (coupure pendant l'écriture) est ignorée."""
    lancer([SPECIALITES])
    chemin = manifeste.chemin_manifeste(racine)
    with chemin.open("ab") as fichier:
        fichier.write(b'{"passage_id": "20261024T1517')
    horloge.avancer(hours=1)
    (ligne,) = lancer([SPECIALITES]).enregistrements
    assert ligne.statut == "inchange", "l'empreinte de la ligne saine est retrouvée"
    horloge.avancer(hours=1)
    lancer([SPECIALITES])
    relus = manifeste.lire(racine)
    assert [e.statut for e in relus] == ["nouveau", "inchange", "inchange"]
    brutes = chemin.read_bytes().split(b"\n")
    assert brutes[1].startswith(b'{"passage_id": "20261024T1517\t#'), "coupée, marquée, isolée"
    assert brutes[2].startswith(b"{") and brutes[-1] == b""


def test_manifeste_complet_et_ajout_seul(lancer: Lanceur, racine: Path, horloge: Horloge) -> None:
    lancer()
    horloge.avancer(hours=1)
    lancer()
    lignes = _lignes(racine)
    assert len(lignes) == 26
    for ligne in lignes:
        assert tuple(ligne) == CHAMPS, "toutes les colonnes, toujours dans le même ordre"
        assert ligne["debut"] <= ligne["fin"]
        assert ligne["debut"].endswith("+00:00"), "UTC"
    relus = manifeste.lire(racine)
    assert [e.passage_id for e in relus] == [ligne["passage_id"] for ligne in lignes]
    assert len(manifeste.dernieres_empreintes(relus)) == 14


def test_redirection_en_boucle_et_corps_indecodable_n_arretent_pas_les_autres(
    lancer: Lanceur, serveur: ServeurSimule, racine: Path
) -> None:
    """Relecture 1, bloquant 1 : toute erreur httpx finit en ligne d'erreur."""
    serveur.scenariser(SPECIALITES.url, (302, b"", {"Location": SPECIALITES.url}))
    serveur.scenariser(INFOS.url, (200, b"pas du gzip", {"Content-Encoding": "gzip"}))
    bilan = lancer()
    assert bilan.compter(Statut.ERREUR) == 2 and bilan.compter(Statut.NOUVEAU) == 12
    lignes = _par_fichier(racine, bilan.passage_id)
    assert len(lignes) == 14, "aucun passage ne manque"
    specialites, infos = lignes["CIS_bdpm.txt"], lignes["CIS_InfoImportantes.txt"]
    assert str(specialites["erreur"]).startswith("TooManyRedirects") and specialites["essais"] == 1
    assert str(infos["erreur"]).startswith("DecodingError") and infos["chemin_archive"] is None
    assert specialites["date_source_affichee"] == "2026-09-29", "la page a quand même été lue"


def test_exception_imprevue_sur_un_fichier_n_arrete_pas_les_autres(
    lancer: Lanceur,
    racine: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Le filet : une exception hors des cas prévus donne une ligne « inattendue »."""
    from pharmaflux.collecte import passage

    chemin_archive_original = passage.chemin_archive

    def chemin_qui_casse(racine_: Path, entree_: object, debut: object, sha: str) -> Path:
        if entree_ is INFOS:
            raise RuntimeError("boum")
        return chemin_archive_original(racine_, entree_, debut, sha)  # type: ignore[arg-type]

    monkeypatch.setattr(passage, "chemin_archive", chemin_qui_casse)
    with caplog.at_level(logging.ERROR, logger="pharmaflux.collecte"):
        bilan = lancer()
    assert bilan.compter(Statut.ERREUR) == 1 and bilan.compter(Statut.NOUVEAU) == 13
    lignes = _par_fichier(racine, bilan.passage_id)
    assert len(lignes) == 14
    infos = lignes["CIS_InfoImportantes.txt"]
    assert infos["statut"] == "erreur" and infos["erreur"] == "inattendue: RuntimeError: boum"
    assert infos["identifiant"] == INFOS.identifiant and infos["chemin_archive"] is None
    assert "erreur inattendue" in caplog.text and "Traceback" in caplog.text


def test_exception_imprevue_apres_archivage_garde_l_archive(
    lancer: Lanceur, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pharmaflux.collecte import passage

    def liens_qui_cassent(_contenu: bytes) -> None:
        raise RuntimeError("analyse de la page")

    monkeypatch.setattr(passage, "_liens_par_url", liens_qui_cassent)
    bilan = lancer([PAGE, SPECIALITES])
    page, specialites = bilan.enregistrements
    assert page.statut == "erreur" and page.erreur == "inattendue: RuntimeError: analyse de la page"
    assert page.chemin_archive is not None, "l'archive déjà écrite est consignée"
    assert specialites.statut == "nouveau" and specialites.date_source_affichee is None


def test_ressource_datagouv_qui_n_est_pas_un_objet_donne_analyse_impossible(
    lancer: Lanceur, serveur: ServeurSimule
) -> None:
    serveur.remplacer_contenu(OPENMEDIC.url, b'{"resources": [1, 2]}')
    (ligne,) = lancer([OPENMEDIC]).enregistrements
    assert ligne.statut == "erreur" and str(ligne.erreur).startswith("analyse_impossible:")
    assert ligne.chemin_archive is not None, "archivée quand même (C1)"


def test_empreinte_qui_leve_une_exception_imprevue_archive_quand_meme(
    lancer: Lanceur,
    racine: Path,
    horloge: Horloge,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mission 01, décision 9 : l'archive passe avant un défaut du collecteur."""
    from pharmaflux.collecte import passage

    empreinte_originale = passage.empreinte_comparaison

    def empreinte_qui_casse(mode: ModeEmpreinte, contenu: bytes) -> str:
        if mode is ModeEmpreinte.LIGNES_TRIEES:
            raise RuntimeError("boum")
        return empreinte_originale(mode, contenu)

    monkeypatch.setattr(passage, "empreinte_comparaison", empreinte_qui_casse)
    with caplog.at_level(logging.ERROR, logger="pharmaflux.collecte"):
        (ligne,) = lancer([INFOS]).enregistrements
    assert ligne.statut == "erreur" and ligne.erreur == "empreinte_impossible: RuntimeError: boum"
    assert ligne.chemin_archive and lire_archive(racine / ligne.chemin_archive) == contenu_fixture(
        INFOS
    )
    assert ligne.empreinte_comparaison == ligne.sha256, "repli sur les octets"
    assert "Traceback" in caplog.text
    horloge.avancer(hours=1)
    (suivante,) = lancer([INFOS]).enregistrements
    assert suivante.statut == "erreur" and suivante.chemin_archive is None, "l'alerte reste"
    assert len(_archives(racine, INFOS.fichier)) == 1, "même contenu : pas réarchivé"


def test_recherche_des_liens_nouveaux_sous_le_filet(
    lancer: Lanceur, racine: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Mission 01, décision 9 : une exception après la boucle ne perd pas le passage."""
    from pharmaflux.collecte import passage

    def liens_qui_cassent(_liens: object) -> list[object]:
        raise RuntimeError("liens")

    monkeypatch.setattr(passage, "_liens_nouveaux", liens_qui_cassent)
    with caplog.at_level(logging.ERROR, logger="pharmaflux.collecte"):
        bilan = lancer([PAGE, SPECIALITES])
    assert [e.statut for e in bilan.enregistrements] == ["nouveau", "nouveau", "erreur"]
    derniere = bilan.enregistrements[-1]
    assert derniere.identifiant == PAGE.identifiant and derniere.fichier == PAGE.fichier
    assert derniere.erreur == "inattendue: RuntimeError: liens" and derniere.chemin_archive is None
    assert bilan.code_sortie == 1 and len(_lignes(racine)) == 3
    assert "Traceback" in caplog.text


def test_documentation_suit_le_lien_de_la_page(
    lancer: Lanceur, serveur: ServeurSimule, racine: Path
) -> None:
    """Mission 01, décision 9 : un ``_v6.pdf`` est collecté sous son nom, et signalé."""
    serveur.remplacer_contenu(PAGE.url, PAGE_DOC_V6)
    serveur.scenariser(URL_DOC_V6, (200, contenu_fixture(DOCUMENTATION), {}))
    bilan = lancer([PAGE, DOCUMENTATION])
    page, doc = bilan.enregistrements  # pas de troisième ligne : la v6 n'est pas un lien nouveau
    assert page.statut == "nouveau"
    assert doc.identifiant == DOCUMENTATION.identifiant
    assert doc.url == URL_DOC_V6 and doc.fichier == DOC_V6
    assert doc.statut == "erreur"
    assert doc.erreur == f"lien_change: {DOC_V6} (catalogue : {DOCUMENTATION.fichier})"
    assert doc.chemin_archive and f"/{DOC_V6}/" in doc.chemin_archive
    assert lire_archive(racine / doc.chemin_archive) == contenu_fixture(DOCUMENTATION)
    assert serveur.requetes_vers(DOCUMENTATION.url) == 0, "l'ancienne URL n'est plus demandée"
    assert bilan.code_sortie == 1


def test_documentation_changee_collectee_une_fois_par_jour(
    lancer: Lanceur, serveur: ServeurSimule, racine: Path, horloge: Horloge
) -> None:
    """Mission 01, C1 : un ``lien_change`` vaut collecte du jour, le PDF n'est pris qu'une fois."""
    serveur.remplacer_contenu(PAGE.url, PAGE_DOC_V6)
    serveur.scenariser(URL_DOC_V6, (200, contenu_fixture(DOCUMENTATION), {}))
    lancer([PAGE, DOCUMENTATION])
    horloge.avancer(hours=1)
    bilan = lancer([PAGE, DOCUMENTATION])
    assert [e.identifiant for e in bilan.enregistrements] == [PAGE.identifiant], (
        "la documentation est sautée comme toute entrée quotidienne déjà collectée"
    )
    assert serveur.requetes_vers(URL_DOC_V6) == 1
    assert len(_archives(racine, DOC_V6)) == 1
    assert bilan.code_sortie == 0
    etat = calculer_etat(manifeste.parcourir(racine), horloge.maintenant())
    (doc,) = [ligne for ligne in etat.lignes if ligne.identifiant == DOCUMENTATION.identifiant]
    assert doc.dernier_statut == "erreur" and "lien_change:" in str(doc.derniere_erreur), (
        "l'alerte reste visible dans etat"
    )
    horloge.avancer(days=1)
    _, lendemain = lancer([PAGE, DOCUMENTATION]).enregistrements
    assert lendemain.statut == "erreur" and str(lendemain.erreur).startswith("lien_change:")
    assert lendemain.chemin_archive is None, "même contenu le lendemain : pas de réarchivage"
    assert serveur.requetes_vers(URL_DOC_V6) == 2


def test_erreur_de_telechargement_ne_vaut_pas_collecte_meme_avec_un_signalement(
    lancer: Lanceur, serveur: ServeurSimule, horloge: Horloge
) -> None:
    """C1 : ``HTTP 404 ; lien_change`` reste une erreur, l'entrée quotidienne repasse."""
    serveur.remplacer_contenu(PAGE.url, PAGE_DOC_V6)
    serveur.scenariser(URL_DOC_V6, (404, b"", {}))
    _, doc = lancer([PAGE, DOCUMENTATION]).enregistrements
    assert doc.http_statut == 404 and str(doc.erreur).startswith("HTTP 404 ; lien_change:")
    horloge.avancer(hours=1)
    assert lancer([PAGE, DOCUMENTATION]).compter(Statut.ERREUR) == 1, "l'entrée est retentée"
    assert serveur.requetes_vers(URL_DOC_V6) == 2


def test_nouvelle_version_du_pdf_n_est_pas_un_lien_nouveau_a_chaque_passage(
    lancer: Lanceur, serveur: ServeurSimule
) -> None:
    serveur.remplacer_contenu(PAGE.url, PAGE_DOC_V6)
    bilan = lancer([PAGE, SPECIALITES])
    assert [e.statut for e in bilan.enregistrements] == ["nouveau", "nouveau"]


def test_documentation_absente_de_la_page(lancer: Lanceur, serveur: ServeurSimule) -> None:
    """Sans lien au préfixe connu : repli sur l'URL du catalogue, ``lien_absent``."""
    page = contenu_fixture(PAGE).replace(DOCUMENTATION.fichier.encode(), b"Autre_document.pdf")
    serveur.remplacer_contenu(PAGE.url, page)
    bilan = lancer([PAGE, DOCUMENTATION])
    _, doc, nouveau = bilan.enregistrements
    assert doc.url == DOCUMENTATION.url and doc.fichier == DOCUMENTATION.fichier
    assert doc.statut == "erreur" and doc.erreur == "lien_absent" and doc.chemin_archive
    assert nouveau.fichier == "Autre_document.pdf" and nouveau.identifiant is None
    assert str(nouveau.erreur).startswith("lien_nouveau:"), "un PDF inconnu est un lien nouveau"


def test_documentation_absente_collectee_une_fois_par_jour(
    lancer: Lanceur, serveur: ServeurSimule, horloge: Horloge
) -> None:
    """C1 : ``lien_absent`` sur une entrée quotidienne vaut aussi collecte du jour."""
    page = contenu_fixture(PAGE).replace(DOCUMENTATION.fichier.encode(), b"Autre_document.pdf")
    serveur.remplacer_contenu(PAGE.url, page)
    lancer([PAGE, DOCUMENTATION])
    horloge.avancer(hours=1)
    bilan = lancer([PAGE, DOCUMENTATION])
    assert [e.identifiant for e in bilan.enregistrements] == [PAGE.identifiant, None]
    assert serveur.requetes_vers(DOCUMENTATION.url) == 1


def test_deux_versions_du_pdf_sur_la_page(lancer: Lanceur, serveur: ServeurSimule) -> None:
    """La version connue est collectée, l'autre est un lien nouveau."""
    lien_v6 = f'<a href="/download/file/{DOC_V6}">Documentation v6</a></body>'.encode()
    serveur.remplacer_contenu(PAGE.url, contenu_fixture(PAGE).replace(b"</body>", lien_v6))
    bilan = lancer([PAGE, DOCUMENTATION])
    _, doc, nouveau = bilan.enregistrements
    assert doc.statut == "nouveau" and doc.url == DOCUMENTATION.url
    assert nouveau.fichier == DOC_V6 and str(nouveau.erreur).startswith("lien_nouveau:")
