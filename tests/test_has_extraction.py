"""L'extraction des pages d'avis de la HAS (mission 09, palier 1) : sur les six pages réelles du §0.

Chaque page est celle reçue le 31/10/2026 (``tests/fixtures/has/``) : six au §0, quatre reprises
de la collecte de la première étape (les rejets de la v1, en fin de fichier). Les rejets se
provoquent en retouchant une copie d'une page réelle, jamais en fabriquant une page : la
structure éprouvée est celle du site.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from pharmaflux.has import extraction, verification
from pharmaflux.has.extraction import PageRejetee, date_francaise, extraire, texte_principal
from tests.conftest import FIXTURES

PAGES = FIXTURES / "has"


def page(nom: str) -> bytes:
    return (PAGES / f"{nom}.html").read_bytes()


# (page, titre, date de l'avis, mise en ligne, nature, SMR, ASMR, dossier du document, CIP13)
ATTENDUS = [
    ("p_4072400", "MOUNJARO (tirzépatide) - Diabète de type 2", date(2026, 5, 6),
     date(2026, 6, 12), "Inscription", ("Modéré", "Insuffisant"), ("V (absence)", "Sans objet"),
     ("CT-21681",), 12),
    ("p_3590639", "IMFINZI - LYNPARZA (durvalumab/olaparib) - Cancer de l’endomètre",  # noqa: RUF001 (apostrophe typographique de la page)
     date(2025, 1, 15), date(2025, 2, 19), "Extension d'indication", ("Important",),
     ("IV (mineur)",), ("CT-21088",), 4),
    ("p_3577036", "KALYDECO (ivacaftor) - Mucoviscidose", date(2024, 12, 18), date(2025, 1, 10),
     "Inscription", ("Important", "Insuffisant"), ("II (important)",), ("CT-21030",), 7),
    ("p_3500927", "ADEMPAS (riociguat) - Hypertension artérielle pulmonaire (HTAP)",
     date(2024, 2, 28), date(2024, 3, 15), "Extension d'indication", ("Modéré",),
     ("V (absence)",), ("CT-20568",), 14),
    ("p_3741668", "ADEMPAS (riociguat) - Hypertension artérielle pulmonaire (HTAP)",
     date(2025, 11, 10), date(2025, 11, 21), "Extension d'indication non sollicitée", (), (), (),
     1),
    ("c_2027377", "DOLIPRANE - GELUPRANE - PARACETAMOL ZENTIVA (paracétamol)", date(2015, 4, 1),
     date(2015, 5, 7), "Renouvellement d'inscription", ("Important",), (), ("CT-14040",), 20),
]  # fmt: skip


@pytest.mark.parametrize(
    ("nom", "titre", "date_avis", "mis_en_ligne", "nature", "smr", "asmr", "dossiers", "cip13"),
    ATTENDUS,
)
def test_les_six_pages_reelles(
    nom: str,
    titre: str,
    date_avis: date,
    mis_en_ligne: date,
    nature: str,
    smr: tuple[str, ...],
    asmr: tuple[str, ...],
    dossiers: tuple[str, ...],
    cip13: int,
) -> None:
    extrait = extraire(page(nom), dossiers=dossiers or None)
    assert extrait.titre == titre
    assert extrait.date_avis == date_avis
    assert extrait.mis_en_ligne == mis_en_ligne
    assert extrait.mis_a_jour is None
    assert extrait.date_mise_a_jour == mis_en_ligne  # la date de la licence (addendum 1, A1)
    assert extrait.nature_demande == nature
    assert extrait.niveaux("smr") == smr
    assert extrait.niveaux("asmr") == asmr
    assert extrait.dossiers_documents == dossiers
    assert len(extrait.cip13) == cip13
    assert extrait.url_canonique is not None
    assert extrait.url_canonique.startswith(f"https://www.has-sante.fr/jcms/{nom}/fr/")


def test_les_metadonnees_sont_hors_du_texte() -> None:
    extrait = extraire(page("p_4072400"))
    assert extrait.pdf_avis == (
        "https://www.has-sante.fr/upload/docs/evamed/CT-21681_MOUNJARO_PIC_INS_AvisDef_CT21681.pdf"
    )
    assert extrait.atc == "A10BX16"
    texte = "\n".join(extrait.lignes_rendues())
    for absent in ("upload/docs", "A10BX16", "3400930261620", "Nous contacter", "Partager"):
        assert absent not in texte


def test_les_sections_dans_l_ordre_de_la_page() -> None:
    extrait = extraire(page("p_3577036"))
    rubriques = list(dict.fromkeys(ligne.rubrique for ligne in extrait.lignes))
    assert rubriques == [
        "demande",
        "L'essentiel",
        "Quel progrès ?",
        "Quelle place dans la stratégie thérapeutique ?",
        "Recommandations particulières",
        "smr",
        "asmr",
    ]
    # Toutes les sections sont gardées, la stratégie thérapeutique comprise (addendum 1, D1).
    assert any("durée de traitement optimale" in ligne.texte for ligne in extrait.lignes)


@pytest.mark.parametrize("nom", ["p_4072400", "c_2027377"])
def test_extraction_figee(nom: str) -> None:
    """Les mêmes octets donnent le même texte : l'extraction de référence, relue à la main."""
    attendu = json.loads((PAGES / f"{nom}.extrait.json").read_text(encoding="utf-8"))
    extrait = extraire(page(nom))
    assert attendu["extracteur"] == extraction.VERSION_EXTRACTEUR
    assert [[ligne.rubrique, ligne.genre, ligne.texte] for ligne in extrait.lignes] == attendu[
        "lignes"
    ]
    assert extrait.titre == attendu["titre"]
    assert extrait.empreinte() == attendu["empreinte"]


@pytest.mark.parametrize("nom", [attendu[0] for attendu in ATTENDUS])
def test_non_alteration_par_le_second_lecteur(nom: str) -> None:
    octets = page(nom)
    assert verification.ecarts(octets, extraire(octets)) == []


def test_une_alteration_se_voit() -> None:
    octets = page("p_3577036")
    extrait = extraire(octets)
    retouchee = octets.replace(
        "Un progrès thérapeutique dans la prise en charge.".encode(),
        "Un progrès thérapeutique majeur dans la prise en charge.".encode(),
    )
    assert retouchee != octets
    ecarts = verification.ecarts(retouchee, extrait)
    assert [ecart.texte for ecart in ecarts] == [
        "Un progrès thérapeutique dans la prise en charge."
    ]


def test_un_ordre_change_se_voit() -> None:
    octets = page("c_2027377")
    extrait = extraire(octets)
    inverse = extraction.AvisExtrait(
        **{
            **{champ: getattr(extrait, champ) for champ in extrait.__slots__},
            "lignes": tuple(reversed(extrait.lignes)),
        }
    )
    assert verification.ecarts(octets, inverse)


def test_l_empreinte_ignore_ce_qui_change_a_chaque_reponse() -> None:
    """Le jeton CSRF et l'horodatage changent à chaque réponse ; le texte, non (addendum 1, C2)."""
    octets = page("p_4072400")
    autre_reponse = octets.replace(b"Qe3zcFg50exPDnPF", b"ZZZZZZZZZZZZZZZZ").replace(
        b"1793443289907", b"1793500000000"
    )
    assert autre_reponse != octets
    assert extraire(autre_reponse).empreinte() == extraire(octets).empreinte()
    assert texte_principal(autre_reponse) == texte_principal(octets)
    corrigee = octets.replace("reste modéré".encode(), b"reste important")
    assert extraire(corrigee).empreinte() != extraire(octets).empreinte()


def test_texte_principal_des_mentions() -> None:
    """Les mentions légales n'ont pas été demandées au §0 : une page du même gabarit en tient
    lieu. Le texte de ``<main>`` change avec la page, et une page sans ``<main>`` n'en a pas."""
    texte = texte_principal(page("p_3741668"))
    assert texte is not None
    assert "Extension d'indication non sollicitée" in texte
    assert "CSRF" not in texte and "Qe3zcFg50exPDnPF" not in texte
    assert texte_principal(b"<html><body><p>sans main</p></body></html>") is None
    assert texte_principal(b"\xff\xfe") is None


def test_mis_a_jour_le_l_emporte() -> None:
    octets = page("p_3577036").replace(
        b"10 janv. 2025", "10 janv. 2025 - Mis à jour le 3 févr. 2026".encode()
    )
    extrait = extraire(octets)
    assert extrait.mis_en_ligne == date(2025, 1, 10)
    assert extrait.mis_a_jour == date(2026, 2, 3)
    assert extrait.date_mise_a_jour == date(2026, 2, 3)


@pytest.mark.parametrize(
    ("texte", "attendue"),
    [
        ("12 juin 2026", date(2026, 6, 12)),
        ("10 janv. 2025", date(2025, 1, 10)),
        ("19 févr. 2025", date(2025, 2, 19)),
        ("15 mars 2024", date(2024, 3, 15)),
        ("1 avr. 2024", date(2024, 4, 1)),
        ("07 mai 2015", date(2015, 5, 7)),
        ("4 juil. 2024", date(2024, 7, 4)),
        ("31 août 2023", date(2023, 8, 31)),
        ("30 sept. 2023", date(2023, 9, 30)),
        ("2 oct. 2023", date(2023, 10, 2)),
        ("21 nov. 2025", date(2025, 11, 21)),
        ("1er déc. 2022", date(2022, 12, 1)),
        ("3 décembre 2022", date(2022, 12, 3)),
    ],
)
def test_date_francaise(texte: str, attendue: date) -> None:
    assert date_francaise(texte) == attendue


@pytest.mark.parametrize("texte", ["12 juinn 2026", "juin 2026", "32 juin 2026", ""])
def test_date_francaise_illisible(texte: str) -> None:
    with pytest.raises(ValueError):
        date_francaise(texte)


def _rejet(octets: bytes, dossiers: tuple[str, ...] | None = None) -> str:
    with pytest.raises(PageRejetee) as erreur:
        extraire(octets, dossiers=dossiers)
    return erreur.value.motif


def test_rejets_motives() -> None:
    kalydeco = page("p_3577036")
    sans_jsonld = kalydeco.replace(b'type="application/ld+json"', b'type="text/plain"')
    assert _rejet(sans_jsonld) == extraction.REJET_JSONLD_ABSENT
    assert _rejet(kalydeco.replace(b'"@context"', b'"@context" ,,')) == (
        extraction.REJET_JSONLD_ILLISIBLE
    )
    assert _rejet(kalydeco.replace(b'"Review"', b'"Article"')) == extraction.REJET_JSONLD_ABSENT
    assert _rejet(kalydeco.replace(b"2024-12-18T00:00:00+01:00", b"18/12/2024")) == (
        extraction.REJET_DATE_AVIS
    )
    assert _rejet(kalydeco.replace(b"<h1>", b"<h2>").replace(b"</h1>", b"</h2>")) == (
        extraction.REJET_TITRE
    )
    assert _rejet(kalydeco.replace("Avis sur les Médicaments".encode(), b"Recommandation")) == (
        extraction.REJET_RUBRIQUE
    )
    assert _rejet(kalydeco.replace(b"Mis en ligne le", b"Publi\xc3\xa9 le")) == (
        extraction.REJET_MISE_EN_LIGNE
    )
    assert _rejet(kalydeco.replace(b"<h4>Nature de la demande</h4>", b"")) == (
        extraction.REJET_NATURE
    )
    assert _rejet(
        kalydeco.replace(b'"name": "Avis sur KALYDECO', b'"name": "Avis sur KALYDEKO')
    ) == (extraction.REJET_NOM)
    assert _rejet(kalydeco.replace(b'<td width="20%">Insuffisant', b'<td width="20%">Faible')) == (
        extraction.REJET_NIVEAUX
    )
    assert _rejet(kalydeco, dossiers=("CT-99999",)) == extraction.REJET_DOSSIER
    assert _rejet(kalydeco.replace("é".encode(), b"\xe9")) == extraction.REJET_ENCODAGE


def test_corps_vide() -> None:
    adempas = page("p_3741668")
    debut = adempas.index(b'<div class="jcms-message')
    fin = adempas.index(b"</div>", debut) + len(b"</div>")
    assert _rejet(adempas[:debut] + adempas[fin:]) == extraction.REJET_CORPS_VIDE


def test_une_page_qui_n_est_pas_un_avis() -> None:
    """La page de mesure d'audience du document de MOUNJARO (requête 10 du §0)."""
    assert _rejet((PAGES / "doc1-saut3-doXiti.html").read_bytes()) == (
        extraction.REJET_JSONLD_ABSENT
    )


def test_un_document_qui_nomme_le_bon_dossier() -> None:
    extrait = extraire(page("p_3590639"), dossiers=("CT-21088",))
    # La transcription nomme deux dossiers (« CT21088&21117 ») : seul le document d'avis compte.
    assert extrait.dossiers_documents == ("CT-21088",)


def test_les_pages_restent_dans_le_depot_telles_que_recues() -> None:
    """Le sha256 de chaque page est celui du journal des douze requêtes."""
    import hashlib

    journal = [
        json.loads(ligne)
        for ligne in (PAGES / "journal-s0.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    for ligne in journal:
        if ligne["methode"] == "GET":
            octets = (PAGES / ligne["fichier"]).read_bytes()
            assert hashlib.sha256(octets).hexdigest() == ligne["sha256"]


def test_genres_et_espaces_des_lignes() -> None:
    """Chaque ligne du corps a une rubrique et un genre connus."""
    for nom, *_ in ATTENDUS:
        for ligne in extraire(page(nom)).lignes:
            assert ligne.genre in {"nature", "intertitre", "paragraphe", "element", "niveau"}
            assert ligne.texte == ligne.texte.strip()
            assert "  " not in ligne.texte


# --- v2 : les rejets de la v1 à la collecte de la première étape --------------------------------
# Quatre pages reprises à l'octet de l'archive du Mac (passage 20261031T124148Z, analyse :
# docs/rapports/mission-09/collecte-premiere-etape.md).

MENINGOCOQUES = ("CT-21402", "CT-21424", "CT-21540", "CT-21541", "CT-21567")
NICORANDIL = ("CT-21823", "CT-21827", "CT-21832", "CT-21871", "CT-21883")


def test_un_nom_json_ld_garde_ses_entites() -> None:
    """KEPPRA : le JSON-LD écrit « &lt; 4 ans », le <h1> décodé « < 4 ans » ; rejetée en v1."""
    keppra = page("p_3638197")
    assert b"(&lt; 4 ans)" in keppra
    extrait = extraire(keppra, dossiers=("CT-21259",))
    assert extrait.titre.startswith("KEPPRA (lévétiracétam) - Epilepsie chez l'enfant (< 4 ans)")
    # Le décodage ne relâche pas le contrôle : un JSON-LD qui décrit un autre avis est refusé.
    autre = keppra.replace(b'"name": "Avis sur KEPPRA', b'"name": "Avis sur KEPRA')
    assert _rejet(autre) == extraction.REJET_NOM


@pytest.mark.parametrize(
    ("nom", "dossier", "nommes"),
    [
        # « …_10092025_AVIS_CT21541&21424&21540&21402&21567 » (cinq vaccins méningococciques)
        ("p_3687274", "CT-21402", MENINGOCOQUES),
        # « NICORANDIL_08072026_AVIS_CT21823_21827_21832_21871_21883 » : non lu du tout en v1
        ("p_4335961", "CT-21823", NICORANDIL),
    ],
)
def test_un_avis_commun_nomme_tous_ses_dossiers(
    nom: str, dossier: str, nommes: tuple[str, ...]
) -> None:
    extrait = extraire(page(nom), dossiers=(dossier,))
    assert extrait.dossiers_documents == nommes
    for voisin in nommes:  # l'avis commun couvre chacun de ses dossiers
        assert extraire(page(nom), dossiers=(voisin,)).dossiers_documents == nommes


@pytest.mark.parametrize(
    ("nom", "nommes"), [("p_3687274", MENINGOCOQUES), ("p_4335961", NICORANDIL)]
)
def test_un_faux_rattachement_a_un_avis_commun_est_refuse(
    nom: str, nommes: tuple[str, ...]
) -> None:
    # CT-21681 (MOUNJARO) : un dossier qu'aucun des deux avis ne nomme.
    with pytest.raises(PageRejetee) as erreur:
        extraire(page(nom), dossiers=("CT-21681",))
    assert erreur.value.motif == extraction.REJET_DOSSIER
    assert erreur.value.detail == f"le document d'avis nomme {', '.join(nommes)}, pas CT-21681"
    # Un dossier nommé ne couvre pas un second qui ne l'est pas.
    assert _rejet(page(nom), dossiers=(nommes[0], "CT-21681")) == extraction.REJET_DOSSIER


def test_un_document_d_avis_qui_nomme_un_autre_dossier() -> None:
    """PEDMARQSI : le libellé de l'avis dit CT21123 ; son fichier, les deux transcriptions et la
    synthèse disent CT21223, et CT-21123 n'est pas dans la BDPM. La page se contredit : rejetée,
    c'est la question piège « page rejetée » du jeu v2."""
    pedmarqsi = page("p_3608587")
    with pytest.raises(PageRejetee) as erreur:
        extraire(pedmarqsi, dossiers=("CT-21223",))
    assert erreur.value.motif == extraction.REJET_DOSSIER
    assert erreur.value.detail == "le document d'avis nomme CT-21123, pas CT-21223"
    # Seul le rattachement est en cause : sans dossier à contrôler, le texte se lit.
    assert extraire(pedmarqsi).nature_demande == "Inscription"


def test_un_document_sans_numero_ne_permet_pas_le_controle() -> None:
    """ADEMPAS, second lien : aucun document ; la page est acceptée, l'appelant le compte."""
    extrait = extraire(page("p_3741668"), dossiers=("CT-20568",))
    assert extrait.dossiers_documents == ()


def test_l_empreinte_se_compare_d_une_version_a_l_autre() -> None:
    """Le texte des pages acceptées en v1 est inchangé : sous v1, l'empreinte est celle de v1."""
    extrait = extraire(page("p_4072400"))
    assert extrait.empreinte(1) == (
        "7b0c06f8f57b699a669961284411ecdd10fe56a132c8c43cab4ebdd3cfbec46b"  # golden v1
    )
    assert extrait.empreinte() != extrait.empreinte(1)


def test_les_pages_de_la_collecte_restent_telles_que_recues() -> None:
    """Le sha256 de chacune est celui que le manifeste du passage de beko a consigné."""
    import hashlib

    consignes = {
        "p_3638197": "3b8a6def17f9cdb8897e443043901a7810cf346f66b629a2c066f8f9e2dbd422",
        "p_3687274": "7fdeb90b920a5bcad66e21f96e47e4b2b5561989301a4d35a37985d38aef3da9",
        "p_4335961": "17ca292c03e39173a0eaca945479a3a3d817509e0fc340e762a95c1e759dfd5b",
        "p_3608587": "5dcbbf91195414929f73de2ac4571beee749e4350ee956513b501d300c3b5fad",
    }
    for nom, sha256 in consignes.items():
        assert hashlib.sha256(page(nom)).hexdigest() == sha256
