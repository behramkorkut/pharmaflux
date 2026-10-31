"""Mission 08, palier 3 : aucune cible du ``Makefile`` n'efface ``data/assistant`` (addendum 1 G3).

Le journal des dépenses et le cache des réponses vivent sous ``data/assistant`` : le journal est
le compte du budget de la mission, et ``make rebatir`` (comme toute autre remise à zéro) ne doit
jamais l'effacer. Le test lit chaque ligne de recette qui efface (``rm``), variables du
``Makefile`` développées, puis simule ``make -n rebatir`` quand ``make`` est là.
``make evaluer`` n'est enchaînée par aucune autre cible.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

MAKEFILE = Path("Makefile")
PROTEGE = "data/assistant"


def _variables(texte: str) -> dict[str, str]:
    return {
        m["nom"]: m["valeur"].strip()
        for m in re.finditer(r"^(?P<nom>[A-Z_]+)[ \t]*\??=[ \t]*(?P<valeur>.*)$", texte, re.M)
    }


def _developper(ligne: str, variables: dict[str, str]) -> str:
    for _ in range(5):  # une variable peut en nommer une autre
        ligne = re.sub(r"\$\((\w+)\)", lambda m: variables.get(m[1], m[0]), ligne)
    return ligne


def _efface(chemin: str) -> bool:
    """Effacer ``chemin`` effacerait-il ``data/assistant`` (lui-même, ou un parent) ?"""
    chemin = chemin.strip("'\"").rstrip("/")
    return chemin in ("", ".", "data", "data/*", PROTEGE) or PROTEGE.startswith(chemin + "/")


def test_aucune_recette_n_efface_data_assistant() -> None:
    texte = MAKEFILE.read_text(encoding="utf-8")
    variables = _variables(texte)
    effacements = [
        _developper(ligne, variables).split()
        for ligne in texte.splitlines()
        if ligne.startswith("\t") and re.search(r"\brm\b", ligne)
    ]
    assert effacements, "le Makefile efface au moins data/demo (make rebatir)"
    for mots in effacements:
        chemins = [m for m in mots[mots.index("rm") + 1 :] if not m.startswith("-")]
        assert not any(_efface(c) for c in chemins), mots
    assert ["rm", "-rf", "data/demo"] in effacements


def test_make_evaluer_n_est_enchainee_par_aucune_cible() -> None:
    texte = MAKEFILE.read_text(encoding="utf-8")
    prerequis = re.findall(r"^[a-z-]+:(.*)$", texte, re.M)
    assert not any("evaluer" in p.split() for p in prerequis)
    assert not re.search(r"^\t.*\$\(MAKE\) evaluer", texte, re.M)


@pytest.mark.skipif(shutil.which("make") is None, reason="make absent")
def test_make_n_rebatir_epargne_data_assistant() -> None:
    simule = subprocess.run(
        ["make", "-n", "rebatir"], capture_output=True, text=True, check=True, timeout=60
    ).stdout
    assert "rm -rf data/demo" in simule
    assert PROTEGE not in simule and not re.search(r"rm -rf data/?(\s|$)", simule)
