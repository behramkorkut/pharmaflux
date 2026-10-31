"""Le cache des réponses du LLM (addendum 1 G3) : une question déjà posée sur le même index ne
repaie pas — c'est ce qui rend les reprises d'évaluation gratuites.

La clé est l'empreinte de tout ce qui change la réponse : le prompt système, le contenu (les
fragments et la question, donc l'instant de l'index), le modèle, l'effort, ``max_tokens`` et
le schéma de sortie. Le cache vit sous ``data/assistant/`` (hors git) et ``make rebatir`` ne
l'efface jamais (contrôlé au palier 3). La rédaction n'étant pas reproductible à l'octet
(``temperature`` refusée depuis le 21/10/2026), le cache fige **une** rédaction par clé.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

NOM_CACHE = "cache-reponses.sqlite"


def cle(
    systeme: str, contenu: str, modele: str, effort: str, max_tokens: int, schema: dict[str, Any]
) -> str:
    """L'empreinte d'un appel : tout ce qui, s'il changeait, changerait la réponse."""
    brut = json.dumps(
        [systeme, contenu, modele, effort, max_tokens, schema],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


class CacheReponses:
    """Un petit magasin clé → réponse (JSON), en SQLite, dans le dossier de l'assistant."""

    def __init__(self, dossier: Path) -> None:
        dossier.mkdir(parents=True, exist_ok=True)
        self._base = sqlite3.connect(dossier / NOM_CACHE)
        self._base.execute(
            "CREATE TABLE IF NOT EXISTS reponses (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL)"
        )

    def close(self) -> None:
        self._base.close()

    def lire(self, cle_: str) -> dict[str, Any] | None:
        ligne = self._base.execute("SELECT valeur FROM reponses WHERE cle = ?", (cle_,)).fetchone()
        return None if ligne is None else json.loads(ligne[0])

    def ecrire(self, cle_: str, valeur: dict[str, Any]) -> None:
        with self._base:
            self._base.execute(
                "INSERT OR REPLACE INTO reponses VALUES (?, ?)",
                (cle_, json.dumps(valeur, ensure_ascii=False)),
            )
