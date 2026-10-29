"""Du SQL sur le gold à un instant : la barrière de ``silver sql``, sans la modifier (I.1).

Les entités typées sont données à DuckDB en Arrow, sous le nom court de
leur silver (``presentations``), avec les trois vues métier
(``fiche_medicament``, ``disponibilite_courante``, ``alternatives``) ;
l'instant est fixé à l'ouverture. La connexion est celle de ``silver.sql``
(aucun accès externe, configuration verrouillée) et ``executer`` n'admet
qu'un ``SELECT``. ``silver sql``, lui,
garde l'histoire entière en chaînes : les mêmes noms y désignent autre chose,
d'où deux commandes.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

import duckdb

from pharmaflux.contrats.modele import Contrat
from pharmaflux.gold.typage import EntiteTypee, etat_type
from pharmaflux.gold.vues import Vues
from pharmaflux.silver.entrepot import Entrepot, identifiant_table
from pharmaflux.silver.sql import connexion_verrouillee


def etats_types(
    entrepot: Entrepot, contrats: Mapping[str, Contrat], instant: datetime
) -> dict[str, EntiteTypee]:
    """L'état typé de chaque entité que l'entrepôt connaît, à ``instant``."""
    return {
        entite: etat_type(entrepot, contrats[entite], instant)
        for entite in entrepot.entites()
        if entite in contrats
    }


def connexion(
    etats: Mapping[str, EntiteTypee], vues: Vues | None = None
) -> duckdb.DuckDBPyConnection:
    """Une connexion verrouillée, une vue par entité typée (son nom court), et les vues métier."""
    con = connexion_verrouillee()
    for entite, etat in etats.items():
        _, nom = identifiant_table(entite)
        con.register(nom, etat.table)
    if vues is not None:
        con.register("fiche_medicament", vues.fiche)
        con.register("disponibilite_courante", vues.disponibilite)
        con.register("alternatives", vues.alternatives)
    return con
