"""Mission 09, palier 3 : l'attendu de page d'avis, le lien attendu, et leur notation (H2).

L'attendu ``attendu_has`` se lit dans le jeu, se vérifie sans gold (l'archive HAS du jeu, le
bronze des liens, l'extraction), et se note : la date de l'avis et l'extrait sont dus, la page
doit être rendue par le code sous la réponse.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from pharmaflux.assistant import chemin, notation
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evaluation import questions
from pharmaflux.evaluation.questions import JeuInvalide
from pharmaflux.evaluation.verification import Verdict, verifier_jeu

DEPOT = Path(__file__).resolve().parent.parent
V2 = DEPOT / "evaluation" / "questions-reference-v2.toml"
JEU = DEPOT / "demo" / "archive"
URL = "https://www.has-sante.fr/jcms/p_3741668"

QUESTION = f"""
version = "v2"
description = "essai"
instant = "2026-10-27T00:17:12Z"

[[questions]]
id = "avis_has-043"
categorie = "avis_has"
question = "Quelle est la décision la plus récente dans le dossier CT-20568 d'ADEMPAS ?"
comportement = "reponse"
cis_attendu = "64832942"
section_attendue = "avis_has"
lien_attendu = "{URL}"

[questions.attendu_has]
archive = "bronze/has/pages/p_3741668/20261031T130557Z__3dc3eaa3d6d3.html.gz"
sha256 = "3dc3eaa3d6d34931149cbb4d925a83b65f6e8377dabab543871c830cf6cc8821"
url = "{URL}"
dossier = "CT-20568"
date_avis = "2025-11-10"
mis_en_ligne = "2025-11-21"
nature_demande = "Extension d'indication non sollicitée"
extrait = "Le laboratoire a informé la HAS de sa demande de non remboursement"
"""


def _charger(texte: str) -> questions.Jeu:
    return questions.charger_octets(texte.encode(), "essai.toml", charger_tous())


def test_un_attendu_de_page_d_avis_se_lit() -> None:
    (question,) = _charger(QUESTION).questions
    assert question.attendu is None and question.attendu_has is not None
    assert question.attendu_has.date_avis == "2025-11-10"
    assert question.lien_attendu == URL


@pytest.mark.parametrize(
    ("ancien", "nouveau", "message"),
    [
        (
            'comportement = "reponse"',
            'comportement = "abstention"\nmotif = "x"',
            "réponse seulement",
        ),
        (
            f'lien_attendu = "{URL}"',
            'lien_attendu = "https://exemple.fr/x"',
            "URL d'une page d'avis",
        ),
        ("p_3741668/20261031", "p_3741669/20261031", "nomment la même page"),
        ('dossier = "CT-20568"', 'dossier = "20568"', "CT-NNNNN"),
        ('date_avis = "2025-11-10"', 'date_avis = "10/11/2025"', "AAAA-MM-JJ"),
        (
            "de non remboursement",
            "de non remboursement dans une indication du médicament",
            "12 mots au plus",
        ),
        (
            f'lien_attendu = "{URL}"',
            'lien_attendu = "https://www.has-sante.fr/jcms/p_1"',
            "pas l'URL",
        ),
    ],
)
def test_un_attendu_de_page_mal_forme_est_refuse(ancien: str, nouveau: str, message: str) -> None:
    assert ancien in QUESTION
    with pytest.raises(JeuInvalide, match=message):
        _charger(QUESTION.replace(ancien, nouveau, 1))


@pytest.fixture(scope="module")
def jeu_v2() -> questions.Jeu:
    return questions.charger(V2, charger_tous())


def test_les_pages_d_avis_de_la_v2_se_verifient_sans_gold(jeu_v2: questions.Jeu) -> None:
    avec_page = replace(jeu_v2, questions=tuple(q for q in jeu_v2.questions if q.attendu_has))
    bilan = verifier_jeu(avec_page, JEU, charger_tous())
    assert len(bilan.resultats) == 20
    assert {r.verdict for r in bilan.resultats} == {Verdict.CONFORME}, bilan.echecs


def _variante(jeu: questions.Jeu, **attendu: Any) -> questions.Jeu:
    (question,) = [q for q in jeu.questions if q.id == "avis_has-043"]
    assert question.attendu_has is not None
    modifiee = replace(question, attendu_has=replace(question.attendu_has, **attendu))
    return replace(jeu, questions=(modifiee,))


@pytest.mark.parametrize(
    ("changement", "verdict", "detail"),
    [
        ({"date_avis": "2024-02-28"}, Verdict.ECART, "date_avis"),
        ({"extrait": "Le laboratoire a demandé le remboursement"}, Verdict.ECART, "extrait"),
        ({"dossier": "CT-21030"}, Verdict.ECART, "ne lie pas"),
        ({"sha256": "0" * 64}, Verdict.SHA256_DIFFERENT, "lu "),
    ],
)
def test_un_ecart_a_la_page_se_voit(
    jeu_v2: questions.Jeu, changement: dict[str, str], verdict: Verdict, detail: str
) -> None:
    (resultat,) = verifier_jeu(_variante(jeu_v2, **changement), JEU, charger_tous()).resultats
    assert resultat.verdict is verdict and detail in resultat.detail


def test_la_page_rejetee_de_pedmarqsi_n_est_jamais_conforme(jeu_v2: questions.Jeu) -> None:
    jeu = _variante(
        jeu_v2,
        archive="bronze/has/pages/p_3608587/20261031T125502Z__5dcbbf911954.html.gz",
        sha256="5dcbbf91195414929f73de2ac4571beee749e4350ee956513b501d300c3b5fad",
        url="https://www.has-sante.fr/jcms/p_3608587",
        dossier="CT-21223",
    )
    (resultat,) = verifier_jeu(jeu, JEU, charger_tous()).resultats
    assert (
        resultat.verdict is Verdict.ECART and "page rejetée (dossier_incoherent)" in resultat.detail
    )


# --- la notation ---------------------------------------------------------------------------------


def _reponse(
    texte: str, page: dict[str, Any] | None, liens: tuple[str, ...] = ()
) -> chemin.Reponse:
    citation = chemin.Citation(
        1, "64832942", "avis_has", "ADEMPAS 0,5 mg", True, "has.avis", True, liens, page
    )
    return chemin.Reponse(
        comportement="reponse",
        texte=texte,
        motif=None,
        orientation=None,
        reserve=False,
        citations=(citation,),
        instant_index="2026-10-27T00:17:12Z",
        decision="llm",
        depuis_cache=False,
        cout=0.01,
        usage=None,
        effort="low",
        trace={"fragments": [{"etiquette": 1, "code_cis": "64832942", "section": "avis_has"}]},
    )


JUSTE = (
    "Selon la décision de la Commission de la transparence du 10 novembre 2025 [1], le"
    " laboratoire a informé la HAS de sa demande de non remboursement dans cette indication."
)


def test_le_lien_la_date_et_l_extrait_se_notent(jeu_v2: questions.Jeu) -> None:
    (question,) = [q for q in jeu_v2.questions if q.id == "avis_has-043"]
    note = notation.noter(question, _reponse(JUSTE, {"url": URL}, (URL,)))
    assert note.correcte and note.lien_rendu and note.manques == ()
    sans_lien = notation.noter(question, _reponse(JUSTE, None))
    assert sans_lien.lien_rendu is False and not sans_lien.correcte
    paraphrase = notation.noter(
        question,
        _reponse("En 2025, le laboratoire ne demande pas le remboursement [1].", {"url": URL}),
    )
    assert set(paraphrase.manques) == {
        "date_avis = 2025-11-10",
        "extrait = Le laboratoire a informé la HAS de sa demande de non remboursement",
    }
    indicateurs = notation.indicateurs([note, sans_lien])
    assert (indicateurs.liens_attendus, indicateurs.liens_rendus) == (2, 1)


def test_un_lien_de_fiche_se_note_aussi(jeu_v2: questions.Jeu) -> None:
    """avis_has-009 : la page de l'avis vient des liens du fragment « avis » de la fiche."""
    (question,) = [q for q in jeu_v2.questions if q.id == "avis_has-009"]
    kalydeco = "https://www.has-sante.fr/jcms/p_3577036"
    citation = chemin.Citation(1, "67851912", "avis", "KALYDECO", True, "f", True, (kalydeco,))
    reponse = replace(
        _reponse("La page de l'avis est rendue sous la réponse [1].", None),
        citations=(citation,),
        trace={"fragments": [{"etiquette": 1, "code_cis": "67851912", "section": "avis"}]},
    )
    note = notation.noter(question, reponse)
    assert note.lien_rendu and note.correcte
