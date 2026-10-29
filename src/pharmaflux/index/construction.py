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
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from pharmaflux.index.encodeur import Encodeur, Vecteurs
from pharmaflux.index.fragments import FORMAT
from pharmaflux.index.qdrant import LOT_PARCOURS, Point, Qdrant, filtre_egal

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
    fiches_total: int = 0  # toutes les fiches à l'instant, même hors du fichier
    touches: tuple[str, ...] | None = None  # les CIS touchés, pour une mise à jour
    par_version: int = 0
    par_bascule: int = 0

    def lire(self) -> Iterator[dict[str, Any]]:
        with self.fichier.open(encoding="utf-8") as entree:
            for ligne in entree:
                yield json.loads(ligne)


def calculer_fragments(
    entrepot: Path,
    travail: Path,
    cis: Sequence[str] = (),
    *,
    a: str | None = None,
    depuis: str | None = None,
) -> Fragments:
    """Les fragments, calculés dans un sous-processus (le gold) : tous, ou ceux des CIS touchés
    depuis ``depuis`` ; à l'instant ``a``, par défaut la dernière observation du silver."""
    travail.mkdir(parents=True, exist_ok=True)
    sortie = travail / "fragments.jsonl"
    commande = [
        sys.executable, "-m", "pharmaflux", "index", "fragments",
        "--entrepot", str(entrepot), "--sortie", str(sortie),
        *(x for c in cis for x in ("--cis", c)),
        *(("--a", a) if a else ()),
        *(("--depuis", depuis) if depuis else ()),
    ]  # fmt: skip
    resultat = subprocess.run(commande, capture_output=True, text=True, check=False)
    if resultat.returncode != 0:
        raise IndexRefuse(f"calcul des fragments (code {resultat.returncode}) : {resultat.stderr}")
    bilan = json.loads(sortie.with_name(sortie.name + ".bilan.json").read_text(encoding="utf-8"))
    if bilan["format"] != FORMAT:
        raise IndexRefuse(f"fragments au format {bilan['format']}, ce code écrit le {FORMAT}")
    touches = bilan.get("cis_touches")
    return Fragments(
        sortie,
        bilan["instant"],
        bilan["fiches"],
        bilan["fragments"],
        bilan["fiches_total"],
        None if touches is None else tuple(touches),
        bilan.get("par_version", 0),
        bilan.get("par_bascule", 0),
    )


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
            "fiches": fragments.fiches_total or fragments.fiches,
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
    """L'état de l'index, s'il décrit bien la collection que l'alias désigne.

    Une coupure entre la bascule de l'alias et l'écriture de l'état laisserait l'alias sur
    la nouvelle collection et l'état sur l'ancienne, avec son instant : on refuserait alors
    d'annoncer un instant qui n'est pas celui des fragments (contrôle du palier 2).
    """
    etat = qdrant.lire_etat()
    alias = qdrant.alias().get(qdrant.alias_fragments)
    if etat is None or alias is None:
        raise IndexRefuse("aucun index : lancer « pharmaflux index construire »")
    if alias != etat["collection"]:
        raise IndexRefuse(
            f"l'alias {qdrant.alias_fragments} désigne {alias}, mais l'état de l'index décrit"
            f" {etat['collection']} : une construction a été coupée entre la bascule de l'alias"
            " et l'écriture de l'état ; relancer « pharmaflux index construire »"
        )
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


# --- mettre à jour -----------------------------------------------------------------------------

LOT_CIS = 256  # CIS traités à la fois par la mise à jour


def canonique(charge_: dict[str, Any]) -> str:
    """La charge d'un point en JSON canonique : deux charges égales ont le même texte."""
    return json.dumps(charge_, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class BilanMiseAJour:
    depuis: str
    instant: str
    reprise: bool  # une mise à jour précédente avait été coupée
    cis_touches: int
    par_version: int
    par_bascule: int
    ajoutes: int
    remplaces: int
    retires: int
    inchanges: int
    encodes: int
    fragments: int  # dans l'index, après
    duree_s: float


def mettre_a_jour(
    qdrant: Qdrant,
    encodeur: Encodeur,
    fragments: Fragments,
    cache: Cache,
) -> BilanMiseAJour:
    """Les fragments des CIS touchés remplacés, ceux qui ont disparu retirés, puis l'instant.

    L'état reçoit d'abord ``vise`` (l'instant visé), puis, à la fin seulement, le nouvel
    instant : une coupure laisse l'ancien, et la commande suivante refait l'intervalle.
    Chaque étape est idempotente (écriture par identifiant, suppression par différence), et un
    CIS n'est jamais vide entre deux étapes : on écrit d'abord, on retire ensuite.
    """
    debut = time.monotonic()
    etat = etat_exige(qdrant)
    encodeur_de_l_index(etat, encodeur)
    if etat["format"] != FORMAT:
        raise IndexRefuse(f"l'index est au format {etat['format']}, ce code écrit le {FORMAT}")
    if fragments.touches is None:
        raise IndexRefuse("une mise à jour demande les CIS touchés (index fragments --depuis)")
    if fragments.instant < etat["instant"]:
        raise IndexRefuse(f"le silver ({fragments.instant}) est en arrière de l'index")
    collection, depuis, reprise = etat["collection"], etat["instant"], etat["vise"] is not None
    qdrant.ecrire_etat(etat | {"vise": fragments.instant})
    comptes = {"ajoutes": 0, "remplaces": 0, "retires": 0, "inchanges": 0, "encodes": 0}
    touches = set(fragments.touches)
    vus: set[str] = set()
    lot: dict[str, list[dict[str, Any]]] = {}
    for fragment in fragments.lire():
        cis = fragment["code_cis"]
        if cis not in lot and len(lot) == LOT_CIS:
            _remplacer(qdrant, collection, encodeur, cache, lot, comptes)
            lot = {}
        lot.setdefault(cis, []).append(fragment)
        vus.add(cis)
    _remplacer(qdrant, collection, encodeur, cache, lot, comptes)
    disparus = sorted(touches - vus)  # touchés, mais plus aucune fiche à cet instant
    for rang in range(0, len(disparus), LOT_CIS):
        vides: dict[str, list[dict[str, Any]]] = {c: [] for c in disparus[rang : rang + LOT_CIS]}
        _remplacer(qdrant, collection, encodeur, cache, vides, comptes)
    total = qdrant.compter(collection)
    qdrant.ecrire_etat(
        etat
        | {
            "instant": fragments.instant,
            "vise": None,
            "fiches": fragments.fiches_total,
            "fragments": total,
        }
    )
    return BilanMiseAJour(
        depuis,
        fragments.instant,
        reprise,
        len(touches),
        fragments.par_version,
        fragments.par_bascule,
        fragments=total,
        duree_s=time.monotonic() - debut,
        **comptes,
    )


def _remplacer(
    qdrant: Qdrant,
    collection: str,
    encodeur: Encodeur,
    cache: Cache,
    par_cis: dict[str, list[dict[str, Any]]],
    comptes: dict[str, int],
) -> None:
    """Pour un lot de CIS : écrire les fragments nouveaux ou changés, puis retirer les autres."""
    if not par_cis:
        return
    existants = {
        str(p["id"]): canonique(p["payload"])
        for p in qdrant.parcourir(collection, filtre_egal("code_cis", sorted(par_cis)))
    }
    nouveaux = [f for liste in par_cis.values() for f in liste]
    a_ecrire = []
    for f in nouveaux:
        avant = existants.get(f["identifiant"])
        if avant is None:
            comptes["ajoutes"] += 1
            a_ecrire.append(f)
        elif avant != canonique(charge(f)):
            comptes["remplaces"] += 1
            a_ecrire.append(f)
        else:
            comptes["inchanges"] += 1
    comptes["encodes"] += _ecrire_lot(qdrant, collection, encodeur, cache, a_ecrire)
    retires = sorted(set(existants) - {f["identifiant"] for f in nouveaux})
    qdrant.supprimer_ids(collection, retires)
    comptes["retires"] += len(retires)


# --- vérifier ----------------------------------------------------------------------------------

ECHANTILLON = 100  # fragments réencodés par la vérification, tirés de façon fixe
COSINUS_MINIMAL = 0.99  # le vrai modèle : le voisinage de lot change un peu le vecteur
MONTRES = 20  # identifiants cités au plus par catégorie d'écart


@dataclass(slots=True)
class Verification:
    instant: str
    collection: str
    attendus: int = 0
    points: int = 0
    manquants: list[str] = field(default_factory=list)
    orphelins: list[str] = field(default_factory=list)
    differents: list[str] = field(default_factory=list)  # texte ou métadonnées
    vecteurs_differents: list[str] = field(default_factory=list)  # du cache (ou de l'encodeur)
    sans_cache: list[str] = field(default_factory=list)
    echantillon: int = 0
    cosinus_minimal: float = 1.0
    suspens: str | None = None  # une mise à jour coupée

    @property
    def conforme(self) -> bool:
        return not (
            self.manquants
            or self.orphelins
            or self.differents
            or self.vecteurs_differents
            or self.sans_cache
            or self.suspens
            or self.cosinus_minimal < COSINUS_MINIMAL
        )


def verifier(
    qdrant: Qdrant, encodeur: Encodeur, fragments: Fragments, cache: Cache
) -> Verification:
    """L'index comparé à sa reconstruction complète depuis le gold au même instant (F).

    Mêmes identifiants (ni manquant, ni orphelin), mêmes charges (texte et métadonnées, en
    JSON canonique), chaque vecteur égal à l'octet à l'entrée du cache pour son texte, et un
    échantillon fixe réencodé à un cosinus d'au moins 0,99 (le vrai modèle). Avec l'encodeur de
    test, chaque vecteur est aussi réencodé et doit être égal à l'octet.
    """
    etat = etat_exige(qdrant)
    encodeur_de_l_index(etat, encodeur)
    if fragments.instant != etat["instant"]:
        raise IndexRefuse(f"fragments à {fragments.instant}, index à {etat['instant']}")
    rapport = Verification(etat["instant"], etat["collection"])
    if etat["vise"]:
        rapport.suspens = etat["vise"]
    attendus = {f["identifiant"]: _empreinte(canonique(charge(f))) for f in fragments.lire()}
    rapport.attendus = len(attendus)
    tries = sorted(attendus)
    pas = max(1, len(tries) // ECHANTILLON)
    echantillon = set(tries[::pas][:ECHANTILLON])
    a_reencoder: list[tuple[str, Vecteurs]] = []
    vus: set[str] = set()
    page: list[dict[str, Any]] = []
    for point in qdrant.parcourir(etat["collection"], vecteurs=True):
        page.append(point)
        if len(page) == LOT_PARCOURS:
            _verifier_page(page, attendus, encodeur, cache, echantillon, a_reencoder, vus, rapport)
            page = []
    _verifier_page(page, attendus, encodeur, cache, echantillon, a_reencoder, vus, rapport)
    rapport.manquants = sorted(set(attendus) - vus)
    if a_reencoder:
        textes = [t for t, _ in a_reencoder]
        nouveaux = encodeur.passages(textes)
        indexes = np.stack([v for _, v in a_reencoder])
        rapport.cosinus_minimal = float((nouveaux * indexes).sum(axis=1).min())
        rapport.echantillon = len(textes)
    return rapport


def _verifier_page(
    page: Sequence[dict[str, Any]],
    attendus: dict[str, bytes],
    encodeur: Encodeur,
    cache: Cache,
    echantillon: set[str],
    a_reencoder: list[tuple[str, Vecteurs]],
    vus: set[str],
    rapport: Verification,
) -> None:
    if not page:
        return
    connus = cache.lire(sorted({str(p["payload"]["empreinte_texte"]) for p in page}))
    textes_test = [p["payload"]["texte"] for p in page] if encodeur.nom == "test" else []
    reencodes = encodeur.passages(textes_test) if textes_test else None
    for rang, point in enumerate(page):
        identifiant = str(point["id"])
        rapport.points += 1
        vus.add(identifiant)
        attendu = attendus.get(identifiant)
        if attendu is None:
            rapport.orphelins.append(identifiant)
            continue
        if _empreinte(canonique(point["payload"])) != attendu:
            rapport.differents.append(identifiant)
        vecteur = np.asarray(point["vector"]["dense"], np.float32)
        en_cache = connus.get(point["payload"]["empreinte_texte"])
        if en_cache is None:
            rapport.sans_cache.append(identifiant)
        elif not np.array_equal(vecteur, en_cache):
            rapport.vecteurs_differents.append(identifiant)
        if reencodes is not None and not np.array_equal(vecteur, reencodes[rang]):
            rapport.vecteurs_differents.append(identifiant)
        if identifiant in echantillon:
            a_reencoder.append((point["payload"]["texte"], vecteur))


def _empreinte(texte: str) -> bytes:
    """32 octets par fragment attendu, au lieu de sa charge entière (185 Mo sur le jeu)."""
    return hashlib.sha256(texte.encode("utf-8")).digest()


def formater_verification(rapport: Verification) -> list[str]:
    lignes = [
        f"index au {rapport.instant}, collection {rapport.collection} : {rapport.points} points,"
        f" {rapport.attendus} fragments attendus (reconstruction depuis le gold)"
    ]
    for nom, liste in (
        ("manquants", rapport.manquants),
        ("orphelins", rapport.orphelins),
        ("texte ou métadonnées différents", rapport.differents),
        ("vecteurs différents", rapport.vecteurs_differents),
        ("vecteurs absents du cache", rapport.sans_cache),
    ):
        montres = ", ".join(liste[:MONTRES]) + (" …" if len(liste) > MONTRES else "")
        lignes.append(f"{nom:32} {len(liste)}" + (f" : {montres}" if liste else ""))
    lignes.append(
        f"{'échantillon réencodé':32} {rapport.echantillon}, cosinus minimal"
        f" {rapport.cosinus_minimal:.4f} (au moins {COSINUS_MINIMAL})"
    )
    if rapport.suspens:
        lignes.append(f"mise à jour en suspens vers {rapport.suspens} : relancer mettre-a-jour")
    lignes.append("conforme" if rapport.conforme else "NON CONFORME")
    return lignes
