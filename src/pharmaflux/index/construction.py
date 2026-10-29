"""Construire l'index, le lire, le décrire (ADR 0011).

Deux processus, chacun sous 512 Mo (addendum 1 J) : les fragments se
calculent dans un sous-processus (``python -m pharmaflux index fragments``,
le gold, PyArrow, DuckDB), qui les écrit en JSON Lines ; ce processus-ci,
qui n'importe ni PyArrow ni DuckDB, les lit par lots, les encode et les écrit
dans Qdrant.

Un fragment dont le texte a déjà été encodé par le même modèle n'est pas
réencodé (PRD §7.5) : le **cache des vecteurs**, clé (modèle, révision,
sha256 du texte), vit dans le dossier de travail de l'index, hors de
``data/demo`` (addendum 1 C3), avec le **verrou** qui empêche deux écritures
de l'index à la fois.
"""

from __future__ import annotations

import fcntl
import json
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pharmaflux.index.encodeur import Encodeur, Vecteurs
from pharmaflux.index.fragments import FORMAT
from pharmaflux.index.qdrant import Point, Qdrant

LOT = 256  # fragments encodés et écrits à la fois
JOURNAL_TOUS = LOT * 8  # fragments entre deux lignes de journal (2 048)
NOM_CACHE = "cache-vecteurs.sqlite"
NOM_VERROU = "verrou"


class IndexRefuse(Exception):  # noqa: N818 (nom français voulu)
    """L'opération ne peut pas se faire : verrou tenu, pas d'index, modèle différent…"""


# --- verrou et cache ---------------------------------------------------------------------------


@contextmanager
def verrou(travail: Path) -> Iterator[None]:
    """Un seul processus écrit l'index à la fois ; le verrou tombe avec le processus."""
    travail.mkdir(parents=True, exist_ok=True)
    with (travail / NOM_VERROU).open("w") as fichier:
        try:
            fcntl.flock(fichier, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise IndexRefuse(
                f"un autre processus écrit l'index (verrou {travail / NOM_VERROU})"
            ) from exc
        yield


class Cache:
    """Les vecteurs déjà calculés, par (empreinte du modèle, sha256 du texte encodé)."""

    def __init__(self, travail: Path, empreinte_modele: str) -> None:
        travail.mkdir(parents=True, exist_ok=True)
        self.modele = empreinte_modele
        self._base = sqlite3.connect(travail / NOM_CACHE)
        self._base.execute(
            "CREATE TABLE IF NOT EXISTS vecteurs ("
            " modele TEXT NOT NULL, texte TEXT NOT NULL, vecteur BLOB NOT NULL,"
            " PRIMARY KEY (modele, texte))"
        )

    def close(self) -> None:
        self._base.close()

    def lire(self, empreintes: Sequence[str]) -> dict[str, Vecteurs]:
        trouves: dict[str, Vecteurs] = {}
        for debut in range(0, len(empreintes), 500):
            morceau = list(empreintes[debut : debut + 500])
            marques = ",".join("?" * len(morceau))
            for texte, octets in self._base.execute(
                f"SELECT texte, vecteur FROM vecteurs WHERE modele = ? AND texte IN ({marques})",
                [self.modele, *morceau],
            ):
                trouves[texte] = np.frombuffer(octets, np.float32)
        return trouves

    def ecrire(self, vecteurs: dict[str, Vecteurs]) -> None:
        with self._base:
            self._base.executemany(
                "INSERT OR REPLACE INTO vecteurs VALUES (?, ?, ?)",
                [(self.modele, t, v.astype(np.float32).tobytes()) for t, v in vecteurs.items()],
            )


def vecteurs_de(
    encodeur: Encodeur, cache: Cache, fragments: Sequence[dict[str, Any]]
) -> tuple[list[Vecteurs], int]:
    """Le vecteur de chaque fragment, du cache ou de l'encodeur ; et combien ont été encodés."""
    empreintes = [str(f["empreinte_texte"]) for f in fragments]
    connus = cache.lire(sorted(set(empreintes)))
    a_encoder = {
        e: f["texte"] for e, f in zip(empreintes, fragments, strict=True) if e not in connus
    }
    if a_encoder:
        nouveaux = encodeur.passages(list(a_encoder.values()))
        calcules = dict(zip(a_encoder, nouveaux, strict=True))
        cache.ecrire(calcules)
        connus |= calcules
    return [connus[e] for e in empreintes], len(a_encoder)


# --- les fragments, par le sous-processus du gold ----------------------------------------------


@dataclass(frozen=True, slots=True)
class Fragments:
    fichier: Path
    instant: str
    fiches: int
    nombre: int

    def lire(self) -> Iterator[dict[str, Any]]:
        with self.fichier.open(encoding="utf-8") as entree:
            for ligne in entree:
                yield json.loads(ligne)


def calculer_fragments(entrepot: Path, travail: Path, cis: Sequence[str] = ()) -> Fragments:
    """Les fragments à la dernière observation du silver, calculés dans un sous-processus."""
    travail.mkdir(parents=True, exist_ok=True)
    sortie = travail / "fragments.jsonl"
    commande = [
        sys.executable, "-m", "pharmaflux", "index", "fragments",
        "--entrepot", str(entrepot), "--sortie", str(sortie),
        *(x for c in cis for x in ("--cis", c)),
    ]  # fmt: skip
    resultat = subprocess.run(commande, capture_output=True, text=True, check=False)
    if resultat.returncode != 0:
        raise IndexRefuse(f"calcul des fragments (code {resultat.returncode}) : {resultat.stderr}")
    bilan = json.loads(sortie.with_name(sortie.name + ".bilan.json").read_text(encoding="utf-8"))
    if bilan["format"] != FORMAT:
        raise IndexRefuse(f"fragments au format {bilan['format']}, ce code écrit le {FORMAT}")
    return Fragments(sortie, bilan["instant"], bilan["fiches"], bilan["fragments"])


def charge(fragment: dict[str, Any]) -> dict[str, object]:
    """Ce que Qdrant garde d'un fragment : tout, sauf son identifiant (celui du point)."""
    return {cle: valeur for cle, valeur in fragment.items() if cle != "identifiant"}


# --- construire --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BilanConstruction:
    collection: str
    instant: str
    fiches: int
    fragments: int
    encodes: int
    duree_s: float


def nom_collection(espace: str, encodeur: Encodeur, instant: str) -> str:
    compact = instant.replace("-", "").replace(":", "")
    return f"{espace}-f{FORMAT}-{encodeur.nom}-{compact}"


def construire(
    qdrant: Qdrant,
    encodeur: Encodeur,
    fragments: Fragments,
    cache: Cache,
    journal: Any = None,
) -> BilanConstruction:
    """Une collection neuve avec tous les fragments, puis l'alias basculé, puis l'état.

    Jusqu'à la bascule, l'index qu'on lit est l'ancien, entier. Une coupure laisse une
    collection hors de l'alias, effacée par la construction suivante au même nom ; reconstruire
    au même instant écrit sous le nom « -bis », pour ne jamais effacer la collection lue.
    """
    debut = time.monotonic()
    ancienne = qdrant.alias().get(qdrant.alias_fragments)
    collection = nom_collection(qdrant.espace, encodeur, fragments.instant)
    if collection == ancienne:  # reconstruire au même instant : l'autre nom, l'index reste lisible
        collection += "-bis"
    qdrant.supprimer_collection(collection)
    qdrant.creer_collection(collection, encodeur.dimension)
    encodes = ecrits = 0
    lot: list[dict[str, Any]] = []
    for fragment in fragments.lire():
        lot.append(fragment)
        if len(lot) == LOT:
            encodes += _ecrire_lot(qdrant, collection, encodeur, cache, lot)
            ecrits += len(lot)
            lot = []
            if journal is not None and ecrits % JOURNAL_TOUS == 0:
                journal(f"{ecrits}/{fragments.nombre} fragments, {time.monotonic() - debut:.0f} s")
    encodes += _ecrire_lot(qdrant, collection, encodeur, cache, lot)
    ecrits += len(lot)
    if ecrits != fragments.nombre or qdrant.compter(collection) != ecrits:
        raise IndexRefuse(f"{collection} : {ecrits} fragments écrits sur {fragments.nombre}")
    qdrant.basculer_alias(qdrant.alias_fragments, collection)
    qdrant.ecrire_etat(
        {
            "collection": collection,
            "instant": fragments.instant,
            "vise": None,
            "format": FORMAT,
            "modele": encodeur.nom,
            "empreinte_modele": encodeur.empreinte,
            "dimension": encodeur.dimension,
            "fiches": fragments.fiches,
            "fragments": ecrits,
        }
    )
    if ancienne is not None and ancienne != collection:
        qdrant.supprimer_collection(ancienne)
    return BilanConstruction(
        collection, fragments.instant, fragments.fiches, ecrits, encodes, time.monotonic() - debut
    )


def _ecrire_lot(
    qdrant: Qdrant,
    collection: str,
    encodeur: Encodeur,
    cache: Cache,
    lot: Sequence[dict[str, Any]],
) -> int:
    if not lot:
        return 0
    vecteurs, encodes = vecteurs_de(encodeur, cache, lot)
    qdrant.ecrire(
        collection,
        [
            Point(str(f["identifiant"]), v.tolist(), charge(f))
            for f, v in zip(lot, vecteurs, strict=True)
        ],
    )
    return encodes


# --- lire --------------------------------------------------------------------------------------


def etat_exige(qdrant: Qdrant) -> dict[str, Any]:
    etat = qdrant.lire_etat()
    if etat is None or qdrant.alias_fragments not in qdrant.alias():
        raise IndexRefuse("aucun index : lancer « pharmaflux index construire »")
    return etat


def encodeur_de_l_index(etat: dict[str, Any], encodeur: Encodeur) -> None:
    """Refuse de chercher avec un autre modèle que celui qui a encodé l'index."""
    if etat["empreinte_modele"] != encodeur.empreinte:
        raise IndexRefuse(
            f"l'index est encodé par {etat['empreinte_modele']}, pas par {encodeur.empreinte}"
        )


@dataclass(frozen=True, slots=True)
class Resultat:
    rang: int
    score: float
    charge: dict[str, Any]


def chercher(
    qdrant: Qdrant,
    encodeur: Encodeur,
    question: str,
    k: int,
    filtre: dict[str, object] | None = None,
) -> tuple[dict[str, Any], list[Resultat]]:
    """L'état de l'index et les ``k`` fragments les plus proches de la question."""
    etat = etat_exige(qdrant)
    encodeur_de_l_index(etat, encodeur)
    points = qdrant.chercher(qdrant.alias_fragments, encodeur.requete(question).tolist(), k, filtre)
    return etat, [
        Resultat(rang, float(p["score"]), p["payload"]) for rang, p in enumerate(points, start=1)
    ]


def citer(charge_: dict[str, Any]) -> str:
    """Les sources d'un fragment : « fichier, source du …, observée depuis … » ; « ; » entre."""
    morceaux = []
    for s in charge_["sources"]:
        date = f"source du {s['date_source']}" if s["date_source"] else "source non datée"
        depuis = f", observée depuis le {s['observee_depuis']}" if s["observee_depuis"] else ""
        morceaux.append(f"{s['fichier']} ({date}{depuis})")
    return " ; ".join(morceaux)
