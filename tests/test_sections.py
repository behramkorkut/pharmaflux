"""Mission 09 : la table des sections et la liste des mots courants, écrites avant les questions.

Elles ne sont pas encore branchées sur le chemin (addendum 1 G) : ces tests fixent ce qu'elles
disent, et que les sections nommées sont celles de l'index.
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
        ("Quel est le SMR de KALYDECO ?", ("avis", "avis_has")),
        ("Que dit l'avis de la Commission de la transparence sur MOUNJARO ?", ("avis", "avis_has")),
        ("OZEMPIC est-il en rupture de stock ?", ("disponibilite",)),
        ("LARIAM est-il d'intérêt thérapeutique majeur ?", ("disponibilite",)),
        ("Quel est le prix de la boîte de DOLIPRANE ?", ("presentations",)),
        ("Y a-t-il une information importante sur la DEPAKINE ?", ("informations",)),
        ("Qui est le titulaire de LARIAM ?", ("identite",)),
        ("Le prix et le SMR de KALYDECO ?", ("avis", "avis_has", "presentations")),
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
