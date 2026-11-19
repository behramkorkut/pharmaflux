"""Le journal des passages : une ligne JSON par passage de la chaîne, en ajout seul.

C'est de là que se lisent les durées et les codes de chaque étape, sans ouvrir
ni le bus ni l'entrepôt. Aucun format existant ne change : le journal est à la
chaîne, à côté de son verrou.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def ajouter(chemin: Path, passage: dict[str, Any]) -> None:
    """Ajoute une ligne, en une seule écriture : une ligne est entière ou absente."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ligne = json.dumps(passage, ensure_ascii=False, sort_keys=True) + "\n"
    # Une écriture coupée (panne de courant) laisse une ligne sans fin : la suivante ne doit
    # pas s'y coller.
    if _fin_coupee(chemin):
        ligne = "\n" + ligne
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
    try:
        os.write(descripteur, ligne.encode("utf-8"))
    finally:
        os.close(descripteur)


def _fin_coupee(chemin: Path) -> bool:
    try:
        with chemin.open("rb") as fichier:
            fichier.seek(-1, os.SEEK_END)
            return fichier.read(1) != b"\n"
    except OSError:  # fichier absent ou vide
        return False


def lire(chemin: Path) -> Iterator[dict[str, Any]]:
    """Les passages, du plus ancien au plus récent. Une ligne coupée n'est pas un passage."""
    if not chemin.exists():
        return
    with chemin.open("rb") as fichier:  # en octets : une ligne coupée dans un caractère aussi
        for ligne in fichier:
            try:
                passage = json.loads(ligne)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(passage, dict):
                yield passage
