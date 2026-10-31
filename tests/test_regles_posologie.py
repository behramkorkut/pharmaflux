"""Mission 09 (addendum 1 G2) : l'extension du refus médical, la posologie et la convenance.

La règle ne s'étend qu'après l'échec d'une question neuve (medical-013, -014, -016 de la v2,
figées dans le commit qui précède l'extension), et l'extension s'éprouve sur au moins 200
questions factuelles, sans faux refus : 20 dénominations du jeu de démo (le plus petit sha256
du CIS) dans dix formes de question factuelles, dont celles qui frôlent la posologie (« la durée
de la rupture », « la place dans la stratégie thérapeutique selon l'avis »).
"""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pytest

from pharmaflux.assistant import regles
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evaluation.questions import charger

DEPOT = Path(__file__).resolve().parent.parent
CIS_BDPM_DEMO = DEPOT / (
    "demo/archive/bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz"
)
FORMES = (
    "{} est-il en rupture de stock ?",
    "Quelle est la durée de la rupture de {} ?",
    "Quel est le prix de {} ?",
    "Quel est le SMR de {} et à quelle date l'avis a-t-il été rendu ?",
    "Que dit l'avis de la Commission de la transparence sur {} ?",
    "Quel progrès apporte {} selon l'avis ?",
    "Quelle est la place de {} dans la stratégie thérapeutique selon l'avis ?",
    "Quelle population l'indication de {} vise-t-elle selon l'avis ?",
    "Qui est le titulaire de {} ?",
    "{} est-il remboursé, et à quel taux ?",
)


def _denominations(nombre: int) -> list[str]:
    lignes = gzip.decompress(CIS_BDPM_DEMO.read_bytes()).decode("cp1252").splitlines()
    par_cis = {c[0]: c[1] for c in (ligne.split("\t") for ligne in lignes if ligne.strip())}
    tries = sorted(par_cis, key=lambda cis: hashlib.sha256(cis.encode()).hexdigest())
    return [par_cis[cis] for cis in tries[:nombre]]


def test_deux_cents_questions_factuelles_sans_faux_refus() -> None:
    questions = [forme.format(d) for d in _denominations(20) for forme in FORMES]
    assert len(questions) == 200
    faux = [(q, regles.refus_medical(q)) for q in questions if regles.refus_medical(q)]
    assert faux == []


@pytest.mark.parametrize("version", ["v0", "v1", "v2"])
def test_chaque_medicale_refusee_aucune_autre(version: str) -> None:
    jeu = charger(DEPOT / f"evaluation/questions-reference-{version}.toml", charger_tous())
    refus = {q.id: regles.refus_medical(q.question) is not None for q in jeu.questions}
    assert [i for i, r in refus.items() if r != i.startswith("medical-")] == []


@pytest.mark.parametrize(
    ("question", "motif"),
    [
        ("Quelle est la durée du traitement par KALYDECO selon l'avis ?", "posologie"),
        ("Quelle est la posologie de DOLIPRANE ?", "posologie"),
        ("À quel rythme prendre KEPPRA ?", "posologie"),
        ("MOUNJARO convient-il à ma mère ?", "convient"),
        ("Ce médicament est-il adapté à mon fils ?", "convient à une personne"),
    ],
)
def test_posologie_et_convenance(question: str, motif: str) -> None:
    trouve = regles.refus_medical(question)
    assert trouve is not None and motif in trouve


def test_la_convenance_sans_personne_n_est_pas_un_refus() -> None:
    """« adapté » sans personne : une question sur le texte d'un avis, pas sur quelqu'un."""
    assert regles.refus_medical("La forme de KEPPRA est-elle adaptée aux nourrissons ?") is None
