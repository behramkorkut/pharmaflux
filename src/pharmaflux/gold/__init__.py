"""Le gold : l'état typé du silver à un instant, ses vues métier et ses contrôles (mission 06).

Le gold n'est pas stocké : c'est une fonction du silver et d'un instant
(PRD §6.5, addendum 1 B). Il ne lit ni le bus, ni les événements, ni le
bronze. Comme pour le silver, ce module-ci ne tient que des constantes :
PyArrow, PyIceberg et DuckDB s'importent dans les sous-modules, que la ligne
de commande n'importe que dans les commandes ``gold``.
"""

from __future__ import annotations

from enum import StrEnum

import pharmaflux.silver  # noqa: F401  (l'allocateur d'Arrow, posé avant tout import de PyArrow)

# Les colonnes de version que le gold garde, après celles du contrat (addendum 1, C.1) :
# assez pour dater et sourcer une réponse, rien de ce qu'on a appris après l'instant
# (``fin_validite``, ``id_fermeture``, ``archive_fermeture`` en sont écartées).
COLONNES_VERSION_GOLD = (
    "identite",
    "rang",
    "date_source",
    "debut_validite",
    "archive_ouverture",
    "version_contrat",
    "anomalies",
)
COLONNES_ILLISIBLES = "colonnes_illisibles"  # les colonnes vidées par une règle de lisibilité


class Classe(StrEnum):
    """Bloquant : un invariant de la chaîne est rompu. Mesuré : un fait de la source."""

    BLOQUANT = "bloquant"
    MESURE = "mesuré"
