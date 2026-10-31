"""Mission 09 : la table des sections et la liste des mots courants (addendum 1 G).

Écrites avant les questions neuves de la v2 (07ac561), branchées après leur commit (bbb9809) :
ces tests fixent ce qu'elles disent, et ce que le repérage en fait.
"""

from __future__ import annotations

import pytest

from pharmaflux.assistant import repere
from pharmaflux.assistant.sections import TABLE, sections_demandees
from pharmaflux.evaluation.questions import SECTIONS_FRAGMENT
from pharmaflux.index.fragments import SECTIONS_INDEX


@pytest.mark.parametrize(
    ("question", "sections"),
    [
        ("Quel est le SMR de KALYDECO ?", ("avis",)),
        ("Quel est le dernier avis de SMR rendu sur OZEMPIC ?", ("avis",)),
        ("Que dit l'avis de la Commission de la transparence sur MOUNJARO ?", ("avis_has", "avis")),
        ("Que dit l'avis sur MOUNJARO ?", ()),
        ("OZEMPIC est-il en rupture de stock ?", ("disponibilite",)),
        ("LARIAM est-il d'intérêt thérapeutique majeur ?", ("disponibilite",)),
        ("Quel est le prix de la boîte de DOLIPRANE ?", ("presentations",)),
        ("Y a-t-il une information importante sur la DEPAKINE ?", ("informations",)),
        ("Qui est le titulaire de LARIAM ?", ("identite",)),
        ("Le prix et le SMR de KALYDECO ?", ("avis", "presentations")),
        ("Bonjour", ()),
    ],
)
def test_sections_demandees(question: str, sections: tuple[str, ...]) -> None:
    assert sections_demandees(question) == sections


def test_une_expression_se_lit_mots_consecutifs() -> None:
    """« remise à disposition » demande la disponibilité ; ses mots épars, non."""
    assert sections_demandees("Date de remise à disposition de LARIAM ?") == ("disponibilite",)
    assert sections_demandees("La remise du dossier à disposition de qui ?") == ()


def test_la_table_ne_nomme_que_des_sections_de_l_index() -> None:
    nommees = {s for _, sections in TABLE for s in sections}
    assert nommees <= set(SECTIONS_INDEX) == set(SECTIONS_FRAGMENT)


def test_les_mots_courants_sont_des_mots_significatifs() -> None:
    """Chacun peut être le premier mot significatif d'une dénomination (trois lettres au moins,
    pas un mot vide) : sans cela, la liste ne changerait rien au repérage."""
    for mot in repere.MOTS_COURANTS:
        assert len(mot) >= 3 and mot not in repere.MOTS_VIDES and mot == mot.lower()


def _dictionnaire() -> repere.Dictionnaire:
    denominations = {
        "1": "EAU OXYGENEE GILBERT 10 volumes, solution pour application cutanée",
        "2": "FERRUM HAUSMANN 50 mg/5 ml, sirop",
        "3": "FER ARROW 80 mg, comprimé",
        "4": "CHLORURE DE SODIUM LAVOISIER 0,9 %, solution injectable",
        "5": "LARIAM 250 mg, comprimé sécable",
    }
    return repere.construire_dictionnaire(
        {"code_cis": cis, "denomination": d, "texte": ""} for cis, d in denominations.items()
    )


@pytest.mark.parametrize(
    ("question", "vises"),
    [
        ("L'eau du robinet est-elle remboursée ?", set()),
        ("Combien coûte un fer à lisser en pharmacie ?", set()),
        ("L'EAU OXYGENEE GILBERT est-elle remboursée ?", {"1"}),
        ("FER ARROW 80 mg est-il en rupture ?", {"3"}),
        ("FERRUM HAUSMANN est-il remboursé ?", {"2"}),
        ("Le chlorure de sodium Lavoisier est-il en tension ?", {"4"}),
        ("LARIAM est-il en rupture ?", {"5"}),
    ],
)
def test_un_mot_courant_ne_vise_qu_avec_le_mot_qui_le_suit(question: str, vises: set[str]) -> None:
    assert repere.reperer(question, _dictionnaire()).vises == vises
