"""Le silver : une table Iceberg par entité, versions SCD2 sur la date d'observation (mission 05).

Ce module-ci ne tient que des constantes et des exceptions : PyArrow,
PyIceberg et DuckDB s'importent dans les sous-modules, et la ligne de
commande ne les importe que dans les commandes ``silver`` (imports
paresseux, addendum 1 K.1). Les constantes de chemin sont ici pour que la
CLI les lise sans charger les bibliothèques.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

# L'allocateur système d'Arrow (K.4) : 100 à 250 Mo résidents de moins que jemalloc sur le jeu
# de démo (§0 J). La variable doit exister avant le premier import de pyarrow, d'où sa place
# ici, dans le module léger que la CLI importe au démarrage ; ``setdefault`` laisse le choix
# à qui l'a déjà posée.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

ENTREPOT_PAR_DEFAUT = Path("data/lakehouse")  # hors git ; la démo prend data/demo/lakehouse
LOT_PAR_DEFAUT = 10_000  # événements par commit Iceberg (addendum 1, C.1)


class Format(StrEnum):
    """Les sorties d'« état à une date » et de « sql »."""

    JSONL = "jsonl"
    TABLEAU = "tableau"
    CSV = "csv"


class SilverRefuse(Exception):  # noqa: N818 (nom français voulu)
    """Un refus avant toute écriture : entrepôt, instant, requête, contrat (code 2)."""


class FluxIncoherent(SilverRefuse):
    """Un événement que le SCD2 ne peut pas appliquer : rien de son lot n'est écrit (code 2)."""
