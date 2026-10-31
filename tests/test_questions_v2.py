"""Mission 09 : le jeu v2, les 88 questions de la v1 reprises et les questions neuves figées.

Les questions neuves qui mesurent les correctifs de la mission 08 sont figées avant toute
retouche de l'assistant (addendum 1 G, H) : leur empreinte est fixée ici, et une question
neuve modifiée après coup ferait échouer ce test. Les questions du palier 3 s'ajouteront après
elles, sans les toucher.
"""

from __future__ import annotations

import ast
import hashlib
import json
import tomllib
from pathlib import Path

from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evaluation import questions

DEPOT = Path(__file__).resolve().parent.parent
V1 = DEPOT / "evaluation" / "questions-reference-v1.toml"
V2 = DEPOT / "evaluation" / "questions-reference-v2.toml"
SCRIPT = DEPOT / "evaluation" / "choisir_neuves_v2.py"
NEUVES = (
    [f"avis_has-{n:03d}" for n in range(12, 19)]
    + [f"disponibilite-{n:03d}" for n in range(13, 16)]
    + [f"hors_perimetre-{n:03d}" for n in range(12, 15)]
    + [f"medical-{n:03d}" for n in range(12, 17)]
)
# sha256 du JSON canonique des 18 questions neuves (clés triées, dates en texte), au commit qui
# les fige.
EMPREINTE_NEUVES = "c11886b22076f341478140a5c2d89a29e8d7c1e1bfe066e6c03a5c0a20fb7b22"
# Palier 3 : les questions qui mesurent le changement de la table des sections, tirées par
# evaluation/choisir_neuves_v2_table.py et figées avant lui (controle-palier-2.md, question 1).
TABLE = [f"avis_has-{n:03d}" for n in range(19, 24)]
EMPREINTE_TABLE = "33890d4817f17b46d53288005cc8d6263554787d6425b649f7d9f2f8efc8b93f"


def _brutes(chemin: Path) -> list[dict[str, object]]:
    return list(tomllib.loads(chemin.read_text(encoding="utf-8"))["questions"])


def test_la_v2_se_charge_et_reprend_la_v1_a_l_identique() -> None:
    jeu = questions.charger(V2, charger_tous())
    v1 = questions.charger(V1, charger_tous())
    assert jeu.version == "v2" and jeu.instant == v1.instant
    assert jeu.questions[: len(v1.questions)] == v1.questions
    assert _brutes(V2)[:88] == _brutes(V1)


def test_les_questions_neuves_sont_figees() -> None:
    neuves = _brutes(V2)[88 : 88 + len(NEUVES)]
    assert [q["id"] for q in neuves] == NEUVES
    brut = json.dumps(
        neuves, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")
    )
    assert hashlib.sha256(brut.encode()).hexdigest() == EMPREINTE_NEUVES


def test_les_questions_de_la_table_sont_figees() -> None:
    debut = 88 + len(NEUVES)
    table = _brutes(V2)[debut : debut + len(TABLE)]
    assert [q["id"] for q in table] == TABLE
    brut = json.dumps(table, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    assert hashlib.sha256(brut.encode()).hexdigest() == EMPREINTE_TABLE


def test_le_script_de_choix_n_est_importe_par_aucun_test() -> None:
    for fichier in Path(__file__).parent.rglob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                modules = [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                modules = [noeud.module or ""]
            else:
                continue
            assert not any("choisir_neuves" in m for m in modules), fichier
    assert SCRIPT.is_file() and SCRIPT.with_name("choisir_neuves_v2_table.py").is_file()
