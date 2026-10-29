"""Mission 07, palier 1 : les fragments de la fiche médicament, depuis le gold.

D'abord sur des fiches écrites à la main (une règle par test, chaque règle de
prudence a le sien), puis sur le jeu de démo : le silver de ``demo_silver``
(``conftest``), construit une fois par session dans un dossier jetable. Les
chiffres attendus sont ceux mesurés pour le rapport du palier 1. Aucun
réseau, aucun conteneur, aucun modèle.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.gold import vues as vues_gold
from pharmaflux.gold.sql import etats_types
from pharmaflux.gold.typage import derniere_observation
from pharmaflux.index import fragments as fr
from pharmaflux.index.fragments import AUCUN_SIGNALEMENT, PORTEE_SPECIALITE, Fragment, fragments
from pharmaflux.silver.entrepot import Entrepot

INSTANT = datetime(2026, 10, 27, 0, 17, 12, tzinfo=UTC)
LIEN_INFO = (
    "<a target='_blank'  title=\"Lien direct vers l'information importante sur le site de"
    " l'ANSM - Nouvelle fen&ecirc;tre\" href='https://ansm.sante.fr/actualites/x'>"
    "Retour d'information sur le PRAC : r&eacute;sum&eacute;</a>"
)


def fiche(**surcharges: Any) -> dict[str, Any]:
    """Une fiche du gold (une ligne de la vue, ``to_pylist``), dans le référentiel, sans liste."""
    base: dict[str, Any] = {
        "code_cis": "60000001",
        "dans_referentiel": True,
        "denomination": "AMOXICILLINE TEST 500 mg, gélule",
        "forme_pharmaceutique": "gélule",
        "voies_administration": ["orale"],
        "statut_amm": "Autorisation active",
        "type_procedure_amm": "Procédure nationale",
        "etat_commercialisation": "Commercialisée",
        "date_amm": date(2001, 2, 3),
        "statut_bdm": None,
        "numero_autorisation_europeenne": None,
        "titulaires": ["LABO TEST"],
        "surveillance_renforcee": False,
        "mitm": False,
        "code_atc": None,
        "date_publication_mitm": None,
        "presentations": None,
        "composition": None,
        "groupes_generiques": None,
        "conditions_prescription": None,
        "avis_smr": None,
        "avis_asmr": None,
        "disponibilite": None,
        "infos_importantes": None,
        "provenance": [
            _provenance("bdpm.specialites", "CIS_bdpm.txt"),
            _provenance("bdpm.presentations", "CIS_CIP_bdpm.txt"),
        ],
        "colonnes_illisibles": [],
        "instant": INSTANT,
    }
    return base | surcharges


def _provenance(entite: str, fichier: str) -> dict[str, Any]:
    return {
        "entite": entite,
        "fichier": fichier,
        "date_source": "2026-09-29",
        "connu_depuis": datetime(2026, 10, 24, 19, 41, 43, tzinfo=UTC),
    }


def presentation(cip13: str, **surcharges: Any) -> dict[str, Any]:
    return {
        "code_cip13": cip13,
        "libelle_presentation": f"plaquette de {cip13[-2:]} gélule(s)",
        "etat_commercialisation": "Déclaration de commercialisation",
        "taux_remboursement": ["65%"],
        "prix_public": Decimal("7.06"),
    } | surcharges


def signalement(**surcharges: Any) -> dict[str, Any]:
    return {
        "code_cip13": None,
        "code_statut": "2",
        "libelle_statut": "Tension d'approvisionnement",
        "date_debut": date(2026, 7, 15),
        "date_mise_a_jour": date(2026, 7, 16),
        "date_remise_a_disposition": None,
        "lien_ansm": "https://ansm.sante.fr/disponibilites/x",
        "portee": "specialite",
        "occurrences": 1,
        "debut_a_venir": False,
    } | surcharges


def par_section(liste: list[Fragment]) -> dict[str, Fragment]:
    assert all(f.parties == 1 for f in liste), "une partie par section dans ces tests"
    return {f.section: f for f in liste}


# --- les règles, sur des fiches écrites à la main ----------------------------------------------


def test_une_fiche_sans_liste_donne_identite_et_disponibilite_seulement() -> None:
    sections = par_section(fragments(fiche()))
    assert list(sections) == ["identite", "disponibilite"]
    identite = sections["identite"].texte
    assert identite.splitlines()[0] == "CIS 60000001 — AMOXICILLINE TEST 500 mg, gélule"
    assert (
        "Spécialité : gélule ; voie(s) orale ; Autorisation active depuis le 2001-02-03"
        " (Procédure nationale) ; Commercialisée ; titulaire(s) LABO TEST" in identite
    )
    assert "Composition : aucun élément dans la source." in identite
    assert [s.fichier for s in sections["identite"].sources] == ["CIS_bdpm.txt"]


def test_les_memes_fiches_donnent_les_memes_fragments_et_l_identifiant_ignore_le_texte() -> None:
    une = fiche(presentations=[presentation("3400930000001")])
    assert fragments(une) == fragments(dict(une)), "à l'octet, et les mêmes identifiants"
    autre_prix = fiche(presentations=[presentation("3400930000001", prix_public=Decimal("9"))])
    avant, apres = par_section(fragments(une)), par_section(fragments(autre_prix))
    assert avant["presentations"].identifiant == apres["presentations"].identifiant
    assert avant["presentations"].empreinte_texte != apres["presentations"].empreinte_texte
    assert avant["presentations"].identifiant == fr.identifiant("60000001", "presentations", 1)
    assert len({f.identifiant for f in fragments(une)}) == len(fragments(une))


def test_l_instant_de_l_etat_n_est_pas_dans_le_texte() -> None:
    """Addendum 1 D2 : l'index tient l'instant ; sinon chaque observation changerait tout."""
    autre_instant = fiche(instant=datetime(2027, 1, 1, tzinfo=UTC))
    assert [f.texte for f in fragments(fiche())] == [f.texte for f in fragments(autre_instant)]
    assert not any("2026-10-27" in f.texte for f in fragments(fiche()))


def test_aucun_signalement_ne_devient_jamais_disponible() -> None:
    dispo = par_section(fragments(fiche()))["disponibilite"]
    assert dispo.texte.splitlines()[1:] == [AUCUN_SIGNALEMENT]
    assert "« disponible »" in AUCUN_SIGNALEMENT and "ne veut pas dire" in AUCUN_SIGNALEMENT
    assert not re.search(r"\bdisponible", dispo.texte.replace(AUCUN_SIGNALEMENT, ""), re.I)
    assert [(s.fichier, s.date_source) for s in dispo.sources] == [
        ("CIS_CIP_Dispo_Spec.txt", None)
    ], "le fichier qui ne cite pas ce CIS, sans date à lui"


def test_une_ligne_sans_cip13_vise_la_specialite_entiere() -> None:
    avec = fiche(
        presentations=[presentation("3400930000001")],
        disponibilite=[
            signalement(),
            signalement(code_cip13="3400930000001", libelle_statut="Rupture de stock"),
        ],
    )
    texte = par_section(fragments(avec))["disponibilite"].texte
    lignes = texte.splitlines()
    assert lignes[1] == "Disponibilité, signalements en cours dans le fichier de l'ANSM (2) :"
    assert lignes[2] == (
        "  - Tension d'approvisionnement depuis le 2026-07-15 ; mis à jour le 2026-07-16 ; "
        + PORTEE_SPECIALITE
    )
    assert lignes[3].endswith("vise la présentation 3400930000001 (plaquette de 01 gélule(s))")
    assert AUCUN_SIGNALEMENT not in texte
    assert par_section(fragments(avec))["disponibilite"].liens == (
        "https://ansm.sante.fr/disponibilites/x",
    ), "le lien en métadonnée, une fois, pas dans le texte"
    assert "https://" not in texte


def test_un_debut_a_venir_est_dit_annonce_pas_commence() -> None:
    annonce = signalement(
        libelle_statut="Arrêt de commercialisation",
        date_debut=date(2027, 7, 1),
        debut_a_venir=True,
    )
    texte = par_section(fragments(fiche(disponibilite=[annonce])))["disponibilite"].texte
    assert (
        "Arrêt de commercialisation annoncé à partir du 2027-07-01, pas encore commencé au jour"
        " de l'état" in texte
    )
    assert "depuis le 2027-07-01" not in texte


def test_une_fiche_partielle_dit_que_le_referentiel_ne_connait_pas_ce_cis() -> None:
    partielle = fiche(
        dans_referentiel=False,
        denomination=None,
        **{c: None for c in ("forme_pharmaceutique", "voies_administration", "statut_amm")},
        infos_importantes=[
            {"date_debut": date(2024, 1, 1), "date_fin": None, "texte_et_lien": LIEN_INFO}
        ],
        provenance=[_provenance("bdpm.infos_importantes", "CIS_InfoImportantes.txt")],
    )
    sections = par_section(fragments(partielle))
    identite = sections["identite"]
    assert identite.texte.splitlines()[:2] == [
        "CIS 60000001 — (dénomination inconnue)",
        "Absent du référentiel des spécialités (CIS_bdpm.txt) : fiche partielle, faite des seuls"
        " fichiers qui citent ce CIS (CIS_InfoImportantes.txt).",
    ]
    assert "Spécialité" not in identite.texte and "None" not in identite.texte
    assert [(s.fichier, s.date_source) for s in identite.sources] == [
        ("CIS_InfoImportantes.txt", "2026-09-29"),
        ("CIS_bdpm.txt", None),
    ]
    assert not identite.dans_referentiel
    assert list(sections) == ["identite", "disponibilite", "informations"]


def test_une_valeur_illisible_ne_s_ecrit_pas_et_le_texte_le_dit() -> None:
    illisible = fiche(
        forme_pharmaceutique=None,
        colonnes_illisibles=["specialites.forme_pharmaceutique", "infos_importantes.date_fin"],
    )
    identite = par_section(fragments(illisible))["identite"].texte
    assert "Spécialité : voie(s) orale ;" in identite, "la valeur absente est omise, pas devinée"
    assert identite.splitlines()[-1] == (
        "Valeurs illisibles dans la source, non reprises : specialites.forme_pharmaceutique,"
        " infos_importantes.date_fin"
    ), "sans fragment « informations », l'illisible va dans « identite »"


def test_un_prix_absent_n_est_pas_un_prix() -> None:
    sans_prix = fiche(presentations=[presentation("3400930000001", prix_public=None)])
    texte = par_section(fragments(sans_prix))["presentations"].texte
    assert texte.splitlines()[-1] == (
        "  - 3400930000001 : plaquette de 01 gélule(s) ; Déclaration de commercialisation ;"
        " taux 65% ; prix public non renseigné"
    )


def test_le_titre_d_une_information_est_repris_mot_pour_mot_et_le_lien_va_en_metadonnee() -> None:
    assert fr.titre_et_lien(LIEN_INFO) == (
        "Retour d'information sur le PRAC : résumé",
        "https://ansm.sante.fr/actualites/x",
    )
    assert fr.titre_et_lien("Texte &amp; <b>gras</b> sans lien") == ("Texte & gras sans lien", None)
    info = {
        "date_debut": date(2024, 1, 1),
        "date_fin": date(2027, 1, 1),
        "texte_et_lien": LIEN_INFO,
    }
    fragment = par_section(fragments(fiche(infos_importantes=[info])))["informations"]
    assert fragment.texte.splitlines()[1:] == [
        "Informations importantes en cours (1) :",
        "  - du 2024-01-01 au 2027-01-01 : Retour d'information sur le PRAC : résumé",
    ]
    assert fragment.liens == ("https://ansm.sante.fr/actualites/x",)


def test_un_fragment_trop_long_se_decoupe_par_element() -> None:
    infos = [
        {
            "date_debut": date(2024, 1, 1),
            "date_fin": None,
            "texte_et_lien": f"<a href='https://ansm.sante.fr/{i}'>Actualité numéro {i:02d} "
            + "x" * 80
            + "</a>",
        }
        for i in range(40)
    ]
    parties = [f for f in fragments(fiche(infos_importantes=infos)) if f.section == "informations"]
    assert len(parties) > 1
    assert [(f.partie, f.parties) for f in parties] == [
        (k, len(parties)) for k in range(1, len(parties) + 1)
    ]
    assert len({f.identifiant for f in parties}) == len(parties)
    for f in parties:
        lignes = f.texte.splitlines()
        assert len(f.texte) <= fr.BORNE_CARACTERES
        assert lignes[0] == "CIS 60000001 — AMOXICILLINE TEST 500 mg, gélule"
        assert lignes[1] == (
            f"(partie 1 sur {len(parties)})"
            if f.partie == 1
            else f"(suite, partie {f.partie} sur {len(parties)})"
        )
        attendu = "(40) :" if f.partie == 1 else "(40) (suite) :"
        assert lignes[2] == f"Informations importantes en cours {attendu}"
    elements = [x for f in parties for x in f.texte.splitlines() if x.startswith("  - ")]
    assert elements == [
        f"  - du 2024-01-01 sans date de fin : Actualité numéro {i:02d} " + "x" * 80
        for i in range(40)
    ], "chaque élément une fois, dans l'ordre, entier"


def test_un_fragment_s_ecrit_en_json_cles_dans_l_ordre() -> None:
    fragment = par_section(fragments(fiche()))["identite"]
    ligne = fragment.en_jsonl()
    assert list(json.loads(ligne)) == [
        "identifiant",
        "format",
        "code_cis",
        "section",
        "partie",
        "parties",
        "denomination",
        "dans_referentiel",
        "texte",
        "empreinte_texte",
        "sources",
        "liens",
    ]
    assert json.loads(ligne)["sources"] == [
        {
            "fichier": "CIS_bdpm.txt",
            "date_source": "2026-09-29",
            "observee_depuis": "2026-10-24T19:41:43Z",
        }
    ]
    assert json.loads(ligne)["format"] == fr.FORMAT == 1


# --- le jeu de démo ----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fragments_du_jeu(demo_silver: tuple[Path, Path]) -> list[Fragment]:
    _, dossier = demo_silver
    entrepot = Entrepot.ouvrir(dossier)
    instant = derniere_observation(entrepot)
    assert instant is not None
    contrats = charger_tous()
    etats = etats_types(entrepot, contrats, instant)
    vues = vues_gold.vues(entrepot, contrats, etats, instant)
    return list(fr.fragments_des_fiches(vues.fiche))


def test_les_fragments_du_jeu(fragments_du_jeu: list[Fragment]) -> None:
    """Palier 2, borne de 1 200 : 21 445 fiches, 72 296 fragments, aucun au-delà de la borne."""
    par_section_: dict[str, int] = {}
    for f in fragments_du_jeu:
        par_section_[f.section] = par_section_.get(f.section, 0) + 1
    assert par_section_ == {
        "identite": 21584,
        "presentations": 14735,
        "avis": 9237,
        "disponibilite": 21445,
        "informations": 5295,
    }
    assert len({f.code_cis for f in fragments_du_jeu}) == 21445
    assert len({f.identifiant for f in fragments_du_jeu}) == len(fragments_du_jeu) == 72296
    assert max(len(f.texte) for f in fragments_du_jeu) <= fr.BORNE_CARACTERES
    premieres = {(f.code_cis, f.section) for f in fragments_du_jeu if f.partie == 1}
    assert all(
        (c, s) in premieres
        for c in {f.code_cis for f in fragments_du_jeu}
        for s in (
            "identite",
            "disponibilite",
        )
    ), "toute fiche a son identité et sa disponibilité"


def test_disponible_n_apparait_que_dans_la_phrase_de_prudence_ou_cite_de_la_source(
    fragments_du_jeu: list[Fragment],
) -> None:
    """Addendum 1 D : sur tout le jeu, le mot ne vient jamais du texte que nous écrivons.

    Hors de la phrase « aucun signalement », il n'apparaît que dans un élément cité mot pour
    mot de la source : un titre d'information importante, un libellé de présentation.
    """
    hors_prudence = []
    for f in fragments_du_jeu:
        for ligne in f.texte.replace(AUCUN_SIGNALEMENT, "").splitlines():
            if re.search(r"\bdisponible", ligne, re.I):
                hors_prudence.append((f.section, ligne.startswith("  - ")))
    assert set(hors_prudence) <= {("informations", True), ("presentations", True)}
    assert len(hors_prudence) == 95
    disponibilites = [f for f in fragments_du_jeu if f.section == "disponibilite"]
    assert sum(AUCUN_SIGNALEMENT in f.texte for f in disponibilites) == 21445 - 679


def test_les_cas_de_prudence_reels_du_jeu(fragments_du_jeu: list[Fragment]) -> None:
    def texte(cis: str, section: str) -> str:
        return next(f.texte for f in fragments_du_jeu if (f.code_cis, f.section) == (cis, section))

    assert PORTEE_SPECIALITE in texte("60016589", "disponibilite"), "LEVOCARNIL, sans CIP13"
    assert "annoncé à partir du 2027-07-01, pas encore commencé" in texte(
        "66890524", "disponibilite"
    ), "NEVIRAPINE TEVA, le seul début à venir du jeu"
    assert "fiche partielle" in texte("60000229", "identite")
    assert AUCUN_SIGNALEMENT in texte("60002283", "disponibilite"), "ANASTROZOLE ACCORD"
    assert texte("61096104", "identite").endswith(
        "non reprises : specialites.numero_autorisation_europeenne"
    ), "ZEJULA, la seule valeur illisible du jeu"
    sans_cip13 = [
        f for f in fragments_du_jeu if f.section == "disponibilite" and PORTEE_SPECIALITE in f.texte
    ]
    assert sum(f.texte.count(PORTEE_SPECIALITE) for f in sans_cip13) == 662


def test_index_fragments_en_ligne_de_commande(
    demo_silver: tuple[Path, Path], tmp_path: Path
) -> None:
    _, dossier = demo_silver
    sortie = tmp_path / "fragments.jsonl"
    resultat = CliRunner().invoke(
        application,
        [
            "index",
            "fragments",
            "--entrepot",
            str(dossier),
            "--cis",
            "60016589",
            "--sortie",
            str(sortie),
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    lignes = [json.loads(x) for x in sortie.read_text(encoding="utf-8").splitlines()]
    assert [x["section"] for x in lignes] == ["identite", "presentations", "avis", "disponibilite"]
    assert "4 fragment(s) de 1 fiche(s), format 1, état au 2026-10-27T00:17:12Z" in resultat.output
    assert not (tmp_path / "fragments.jsonl.partiel").exists()
    inconnu = CliRunner().invoke(
        application, ["index", "fragments", "--entrepot", str(dossier), "--cis", "99999999"]
    )
    assert inconnu.exit_code == 2
    assert "aucun fichier ne cite le(s) CIS 99999999" in inconnu.output
