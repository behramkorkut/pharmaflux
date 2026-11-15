"""Le témoin des formats : ce avec quoi le dérivé a été bâti, comparé au code qui tourne.

``<derive>/chaine/formats.json`` garde, depuis le dernier remplissage, le
format de l'index, la version de l'extracteur des pages d'avis, le modèle, le
format du silver et la version de chaque contrat. Au départ d'un passage, la
chaîne le compare à ce que porte le code : si un format a changé, elle refuse
avant toute écriture et nomme ce qu'il faut rebâtir. Si seul le commit a
changé, elle passe, et ``chaine etat`` montre les deux commits.

Le silver n'avait pas de numéro de format (§0 G, question 18) : ``FORMAT_SILVER``
le lui donne, hors du silver, sans rien changer à son calcul. Un test échoue
quand le schéma des tables change sans que ce numéro change (``EMPREINTE_SILVER``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.has.extraction import VERSION_EXTRACTEUR
from pharmaflux.index.fragments import FORMAT as FORMAT_INDEX

NOM_TEMOIN = "formats.json"
# Le format des tables du silver. À incrémenter quand leur schéma change (colonnes, types,
# colonnes de version), ou leur façon d'appliquer un événement, à contrat égal.
FORMAT_SILVER = 1
# L'empreinte du schéma des tables au format FORMAT_SILVER, que vérifie
# tests/test_chaine_horaire.py::test_le_numero_du_silver_suit_son_schema.
EMPREINTE_SILVER = "823d617ef4aee4fbbdafbef30f1f22c146338aaaf0411d64cad57bd3b50f88e7"

# Ce qu'un format changé oblige à rebâtir, du plus petit au plus grand.
REBATIR_INDEX = (
    "l'index : relancer le remplissage (pharmaflux-remplissage.service), qui le reconstruit"
)
REBATIR_SILVER = (
    "le silver et l'index : effacer <derive>/lakehouse et <derive>/chaine/formats.json, puis"
    " relancer le remplissage"
)
REBATIR_TOUT = (
    "tout le dérivé et le bus : effacer le dérivé et rebâtir le bus (infra/vps/README.md),"
    " puis relancer le remplissage"
)
_REBATIR = {
    "index": REBATIR_INDEX,
    "extracteur_has": REBATIR_INDEX,
    "modele": REBATIR_INDEX,
    "silver": REBATIR_SILVER,
    "contrats": REBATIR_TOUT,
}
# Ce que le remplissage rebâtit de lui-même : l'index, toujours reconstruit.
REBATIS_PAR_LE_REMPLISSAGE = frozenset({"index", "extracteur_has", "modele"})


def attendus(modele: str) -> dict[str, Any]:
    """Les formats que porte le code qui tourne, pour un index bâti avec ``modele``."""
    return {
        "index": FORMAT_INDEX,
        "extracteur_has": VERSION_EXTRACTEUR,
        "modele": modele,
        "silver": FORMAT_SILVER,
        "contrats": {i: c.version for i, c in sorted(charger_tous().items())},
    }


def lire(chemin: Path) -> dict[str, Any] | None:
    """Le témoin, ou None s'il n'existe pas encore. Un témoin illisible lève ``ValueError``."""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    contenu = json.loads(texte)
    if not isinstance(contenu, dict) or not isinstance(contenu.get("formats"), dict):
        raise ValueError(f"{chemin} : témoin des formats illisible")
    return contenu


def ecrire(chemin: Path, *, formats: dict[str, Any], commit: str | None, par: str) -> None:
    """Écrit le témoin entier, puis le renomme : il est complet ou absent, jamais à moitié."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    contenu = {"commit": commit, "par": par, "formats": formats}
    temporaire = chemin.with_name(chemin.name + ".neuf")
    temporaire.write_text(json.dumps(contenu, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporaire.replace(chemin)


def ecarts(temoin: dict[str, Any], attendu: dict[str, Any]) -> list[str]:
    """Les formats qui diffèrent entre le dérivé et le code, dans l'ordre de ``attendu``."""
    bati = temoin.get("formats", {})
    return [cle for cle in attendu if bati.get(cle) != attendu[cle]]


def refus(differents: list[str], temoin: dict[str, Any], attendu: dict[str, Any]) -> str:
    """La phrase du refus : ce qui diffère, et le plus grand geste qu'il demande."""
    bati = temoin.get("formats", {})
    detail = " ; ".join(f"{cle} {bati.get(cle)!r} → {attendu[cle]!r}" for cle in differents)
    ordre = list(_REBATIR.values())
    geste = max((_REBATIR[cle] for cle in differents), key=ordre.index)
    return f"le dérivé a été bâti avec d'autres formats ({detail}) ; à rebâtir : {geste}"
