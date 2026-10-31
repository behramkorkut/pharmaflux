"""Mission 09, palier 2 : les liens et les horloges rendus par le code, aucune adresse au LLM.

Le LLM ne voit aucune URL, le code rend les liens : la page d'avis avec ses trois dates (avis,
mise en ligne ou mise à jour, consultation, la licence de la HAS), les liens d'une fiche tels
quels, et les deux horloges de l'index. Une adresse écrite par le LLM rend son texte non
vérifiable.
"""

from __future__ import annotations

from typing import Any

from pharmaflux.assistant import chemin, controle
from pharmaflux.index.construction import Resultat

INSTANT = "2026-10-27T00:17:12Z"
URL = "https://www.has-sante.fr/jcms/p_3577036"
PAGE = {
    "url": URL,
    "page_id": "p_3577036",
    "date_avis": "2024-12-18",
    "mis_en_ligne": "2025-01-10",
    "mis_a_jour": None,
    "collectee_le": "2026-10-31T12:47:41Z",
}


def citation(**kw: Any) -> chemin.Citation:
    valeurs: dict[str, Any] = {
        "etiquette": 1,
        "code_cis": "67851912",
        "section": "avis_has",
        "denomination": "KALYDECO 13,4 mg, granulés en sachet",
        "dans_referentiel": True,
        "sources": "has.avis (source du 2024-12-18, observée depuis le 2026-10-31T12:47:41Z)",
        "source_datee": True,
        "liens": (URL,),
        "page": PAGE,
    }
    return chemin.Citation(**(valeurs | kw))


def test_une_page_d_avis_se_rend_avec_ses_trois_dates() -> None:
    assert citation().liens_rendus() == [
        "avis de la Commission de la transparence du 2024-12-18 : " + URL
        + " (page mise en ligne le 2025-01-10, consultée le 2026-10-31)"
    ]  # fmt: skip
    mise_a_jour = citation(page=PAGE | {"mis_a_jour": "2025-03-02"})
    assert (
        "(page mise à jour le 2025-03-02, consultée le 2026-10-31)"
        in (mise_a_jour.liens_rendus()[0])
    )


def test_les_liens_d_une_fiche_se_rendent_tels_quels() -> None:
    fiche = citation(section="avis", page=None, liens=(URL, "https://www.has-sante.fr/jcms/c_1"))
    assert fiche.liens_rendus() == [URL, "https://www.has-sante.fr/jcms/c_1"]
    assert citation(section="identite", page=None, liens=()).liens_rendus() == []


def _reponse(**kw: Any) -> chemin.Reponse:
    valeurs: dict[str, Any] = {
        "comportement": "reponse",
        "texte": "",
        "motif": None,
        "orientation": None,
        "reserve": False,
        "citations": (),
        "instant_index": INSTANT,
        "decision": "llm",
        "depuis_cache": False,
        "cout": 0.0,
        "usage": None,
        "effort": "low",
    }
    return chemin.Reponse(**(valeurs | kw))


def test_les_deux_horloges_de_l_index() -> None:
    assert _reponse().horloges() == f"état de l'index au {INSTANT}"
    assert _reponse(collecte_has="2026-10-31T13:07:40Z").horloges() == (
        f"état de l'index : BDPM au {INSTANT} ; pages d'avis de la HAS collectées jusqu'au"
        " 2026-10-31T13:07:40Z"
    )


def test_une_adresse_ecrite_par_le_llm_n_est_pas_verifiable() -> None:
    for texte in (f"Voir {URL}.", "Sur has-sante.fr, l'avis dit…", "www.ansm.sante.fr"):
        echec = controle.controler(texte, [], "Que dit l'avis ?")
        assert echec is not None and "seul le code rend les liens" in echec
    assert controle.controler("Le SMR est important.", [], "Que dit l'avis ?") is None


def test_le_llm_ne_voit_aucune_adresse() -> None:
    """Le texte d'un avis en cite parfois une : elle est masquée dans ce que reçoit le LLM."""
    charge = {
        "code_cis": "67851912",
        "section": "avis_has",
        "denomination": "KALYDECO",
        "dans_referentiel": True,
        "texte": "CIS 67851912 — KALYDECO\nVoir le site du CRAT (http://lecrat.fr/).",
        "liens": [URL],
        "sources": [],
    }
    contenu = chemin._contenu(INSTANT, [Resultat(1, 0.9, charge)], "Que dit l'avis ?")
    assert "http" not in contenu and "lecrat.fr" not in contenu and "has-sante" not in contenu
    assert f"Voir le site du CRAT ({chemin.ADRESSE_MASQUEE})." in contenu
