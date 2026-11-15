"""Le passage horaire : ce que la collecte vient d'archiver, porté jusqu'à l'index.

Déclenché à la fin de chaque passage de collecte (``OnSuccess=`` et
``OnFailure=``, quel que soit son code), il lance les cinq étapes de la reprise :
les événements, les schémas, la publication, le silver et la mise à jour de
l'index. Chacune saute ce qu'elle a déjà fait : sans archive nouvelle, le
passage est à vide, et c'est ce qui prouve la reprise à chaque heure.

Il ne construit jamais l'index : sans index, ``index mettre-a-jour`` refuse
(code 2), et le passage nomme le remplissage. Il ne décide jamais sur la sortie
d'une étape (addendum 1, question 7) : le seul échec qui ne l'arrête pas est
``publier`` 3, et seulement quand ``publication.json`` porte les messages de la
file des échecs. ``evenements`` 1 (une archive illisible) n'écrit l'erreur dans
aucun fichier : il arrête le passage.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pharmaflux.chaine import formats, journal
from pharmaflux.chaine.chemins import Chemins
from pharmaflux.chaine.etapes import Etape, Resultat
from pharmaflux.chaine.remplissage import MODELE_PAR_DEFAUT
from pharmaflux.chaine.sante import COURTIER, QDRANT, REGISTRE
from pharmaflux.collecte import manifeste

GENRE = "passage"
# Les variables que systemd passe à l'unité lancée par OnSuccess= ou OnFailure= (systemd.exec).
VARIABLES_DECLENCHEUR = {
    "unite": "MONITOR_UNIT",
    "resultat": "MONITOR_SERVICE_RESULT",
    "code_sortie": "MONITOR_EXIT_CODE",
    "statut_sortie": "MONITOR_EXIT_STATUS",
}
GESTE_SANS_INDEX = (
    "si l'index manque ou a changé de format : relancer le remplissage"
    " (pharmaflux-remplissage.service)"
)


def plan(chemins: Chemins, modele: str = MODELE_PAR_DEFAUT) -> list[Etape]:
    """Les étapes du passage horaire, dans l'ordre."""
    racine, sortie = str(chemins.racine), str(chemins.evenements)
    entrepot = str(chemins.lakehouse)
    return [
        Etape("evenements", ("evenements", "--reprendre", "--racine", racine, "--sortie", sortie)),
        Etape("schemas", ("schemas", "enregistrer"), (REGISTRE,)),
        Etape("publier", ("publier", "--reprendre", "--sortie", sortie), (COURTIER, REGISTRE)),
        Etape("silver", ("silver", "consommer", "--entrepot", entrepot), (COURTIER,)),
        Etape(
            "index",
            (
                "index",
                "mettre-a-jour",
                "--entrepot",
                entrepot,
                "--travail",
                str(chemins.index),
                "--modele",
                modele,
                "--archive-has",
                racine,
            ),
            (QDRANT,),
            geste=GESTE_SANS_INDEX,
        ),
    ]


def echecs_publies(sortie: Path) -> int | None:
    """Les messages de la file des échecs d'après ``publication.json`` ; None s'il est illisible."""
    try:
        etat = json.loads((sortie / "publication.json").read_text(encoding="utf-8"))
        return sum(
            int(fichier["echecs"]) for fichiers in etat.values() for fichier in fichiers.values()
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def circonscrit(chemins: Chemins) -> Callable[[Etape, Resultat], str | None]:
    """L'échec qui n'arrête pas le passage : ``publier`` 3, prouvé par ``publication.json``."""

    def juger(etape: Etape, resultat: Resultat) -> str | None:
        if etape.nom != "publier" or resultat.code != 3:
            return None
        echecs = echecs_publies(chemins.evenements)
        if not echecs:
            return None  # le fichier ne le prouve pas : on s'arrête
        return f"{echecs} message(s) dans la file des échecs, d'après publication.json"

    return juger


def controle(chemins: Chemins, modele: str) -> Callable[[], str | None]:
    """Refuse un passage sur un dérivé bâti avec d'autres formats que le code (§0 G)."""

    def verifier() -> str | None:
        try:
            temoin = formats.lire(chemins.formats)
        except ValueError as exc:
            return str(exc)
        if temoin is None:
            return None  # un dérivé bâti avant le témoin : le premier passage complet l'écrit
        attendu = formats.attendus(modele)
        differents = formats.ecarts(temoin, attendu)
        return formats.refus(differents, temoin, attendu) if differents else None

    return verifier


def declencheur(environnement: dict[str, str] | None = None) -> dict[str, str] | None:
    """L'unité qui a lancé le passage et son résultat, d'après systemd ; None à la main."""
    variables = os.environ if environnement is None else environnement
    valeurs = {
        cle: variables[nom] for cle, nom in VARIABLES_DECLENCHEUR.items() if nom in variables
    }
    return valeurs or None


def _lignes_precedentes(passages: Path) -> tuple[int | None, str | None]:
    """Le nombre de lignes du manifeste au départ du dernier passage horaire, et le départ du
    dernier passage de tout genre (pour le premier passage horaire)."""
    lignes, depart = None, None
    for ancien in journal.lire(passages):
        depart = ancien.get("debut", depart)
        if ancien.get("genre") == GENRE and isinstance(ancien.get("manifeste"), dict):
            lignes = ancien["manifeste"].get("lignes", lignes)
    return lignes, depart


def archives_nouvelles(chemins: Chemins) -> dict[str, Any]:
    """Les archives écrites par la collecte depuis le passage horaire précédent.

    Le critère d'un changement est ``chemin_archive`` non nul (§0 C), pas le statut. Sans
    passage horaire avant lui, ce sont les archives écrites depuis le départ du dernier
    passage de la chaîne (le remplissage).
    """
    precedentes, depart = _lignes_precedentes(chemins.passages)
    archives: list[dict[str, Any]] = []
    rang = 0
    for rang, ligne in enumerate(manifeste.parcourir(chemins.racine), start=1):
        if ligne.chemin_archive is None:
            continue
        if precedentes is not None:
            nouvelle = rang > precedentes
        else:
            nouvelle = depart is not None and _instant(ligne.fin) >= depart
        if nouvelle:
            archives.append(
                {
                    "identifiant": ligne.identifiant,
                    "passage_id": ligne.passage_id,
                    "fin": _instant(ligne.fin),
                    "chemin_archive": ligne.chemin_archive,
                }
            )
    return {"manifeste": {"lignes": rang}, "archives": archives}


def _instant(valeur: str) -> str:
    """``2026-11-15T00:17:28.711578+00:00`` → ``2026-11-15T00:17:28Z``, comme la chaîne."""
    return valeur[:19] + "Z" if valeur.endswith("+00:00") else valeur


def complements(chemins: Chemins) -> Callable[[], dict[str, Any]]:
    def relever() -> dict[str, Any]:
        return {"declencheur": declencheur(), **archives_nouvelles(chemins)}

    return relever


def collections_orphelines() -> list[str] | None:
    """Les collections de fragments que l'alias ne désigne pas (une construction coupée en
    laisse une) ; None si Qdrant ne répond pas. Comptées, jamais effacées (question 31)."""
    from pharmaflux.index.qdrant import (
        ALIAS,
        ESPACE,
        QDRANT_PAR_DEFAUT,
        VARIABLE_QDRANT,
        Qdrant,
        QdrantIndisponible,
    )

    try:
        with Qdrant(os.environ.get(VARIABLE_QDRANT) or QDRANT_PAR_DEFAUT) as client:
            designees = set(client.alias().values())
            return [
                nom
                for nom in client.collections()
                if nom.startswith(f"{ESPACE}-f") and nom != ALIAS and nom not in designees
            ]
    except (QdrantIndisponible, OSError, KeyError, TypeError, ValueError):
        return None


def conclure(
    chemins: Chemins, modele: str, *, orphelines: Callable[[], list[str] | None]
) -> Callable[[str, int], dict[str, Any]]:
    """Après les étapes : les collections orphelines, et le témoin écrit s'il manquait."""

    def finir(issue: str, _code: int) -> dict[str, Any]:
        from pharmaflux.chaine.passage import COMPLET, commit_du_code

        releves: dict[str, Any] = {"collections_orphelines": orphelines()}
        if issue == COMPLET and formats.lire(chemins.formats) is None:
            formats.ecrire(
                chemins.formats,
                formats=formats.attendus(modele),
                commit=commit_du_code(),
                par=GENRE,
            )
            releves["temoin_ecrit"] = True
        return releves

    return finir
