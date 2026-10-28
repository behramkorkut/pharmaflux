"""Les prédicats PyIceberg que le silver emploie, en fonctions typées.

Les prédicats de PyIceberg (``In``, ``IsNull``, ``LessThanOrEqual``…) sont des
modèles pydantic construits par un ``__init__`` positionnel
(``In("colonne", valeurs)``) que mypy ne voit pas : il ne connaît que l'init
synthétisé des champs du modèle. Ces fonctions font l'appel une fois pour
toutes, et le reste du silver reste typé sans ``type: ignore``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from pyiceberg import expressions as _expressions
from pyiceberg.expressions import And, BooleanExpression, Or

_In: Any = _expressions.In
_IsNull: Any = _expressions.IsNull
_EqualTo: Any = _expressions.EqualTo
_LessThanOrEqual: Any = _expressions.LessThanOrEqual
_GreaterThan: Any = _expressions.GreaterThan


def dans(colonne: str, valeurs: Iterable[str]) -> BooleanExpression:
    """``colonne IN (valeurs)``."""
    return cast(BooleanExpression, _In(colonne, list(valeurs)))


def est_nul(colonne: str) -> BooleanExpression:
    return cast(BooleanExpression, _IsNull(colonne))


def egal(colonne: str, valeur: str) -> BooleanExpression:
    return cast(BooleanExpression, _EqualTo(colonne, valeur))


def inferieur_ou_egal(colonne: str, litteral: str) -> BooleanExpression:
    """``colonne <= litteral`` ; un ``timestamptz`` s'écrit ``…+00:00``, jamais ``…Z``."""
    return cast(BooleanExpression, _LessThanOrEqual(colonne, litteral))


def superieur(colonne: str, litteral: str) -> BooleanExpression:
    return cast(BooleanExpression, _GreaterThan(colonne, litteral))


def et(gauche: BooleanExpression, droite: BooleanExpression) -> BooleanExpression:
    return And(gauche, droite)


def ou(gauche: BooleanExpression, droite: BooleanExpression) -> BooleanExpression:
    return Or(gauche, droite)
