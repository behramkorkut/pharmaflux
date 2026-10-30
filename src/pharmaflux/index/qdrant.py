"""Qdrant, vu du projet : un client de son API REST, sur ``httpx`` (ADR 0011, addendum 1 B1).

Une dizaine d'appels suffisent à l'index ; ``qdrant-client`` aurait apporté
gRPC et protobuf pour eux. Comme pour le registre de schémas, ``transport``
permet aux tests de simuler le serveur.

Les fragments vivent dans une collection par (format, modèle, construction),
désignée par l'alias ``pharmaflux-fragments`` : une construction remplit une
collection neuve, puis bascule l'alias d'un coup. Chaque point porte deux
vecteurs **nommés** : ``dense`` (le modèle d'embeddings) et ``lexical`` (le
vecteur creux BM25, format 2, mission 08), ce dernier avec le modificateur
``idf`` pour que Qdrant apporte l'IDF du corpus à la requête (``index.lexical``).
L'état de l'index (instant, modèle, format) est un point sans vecteur dans
la collection ``pharmaflux-index-etat`` : un ``down -v`` efface l'index et
son état ensemble.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

QDRANT_PAR_DEFAUT = "http://127.0.0.1:16333"
VARIABLE_QDRANT = "PHARMAFLUX_QDRANT"
ESPACE = "pharmaflux"  # les tests d'intégration prennent un espace à eux, jamais celui-ci
ALIAS = f"{ESPACE}-fragments"
COLLECTION_ETAT = f"{ESPACE}-index-etat"
VECTEUR = "dense"
VECTEUR_CREUX = "lexical"  # le vecteur creux BM25 (format 2) ; l'IDF est au serveur (modifier idf)
CHAMPS_INDEXES = ("code_cis", "section")  # filtres de chercher, de la mise à jour, de l'état
DELAI_S = 60.0
# Points par page du parcours. Mesuré au palier 3 sur l'index du jeu, vecteurs compris : 82 Mo
# résidents au plus par pages de 100, 446 Mo par pages de 1 000 (l'allocateur garde les gros
# blocs des grandes réponses).
LOT_PARCOURS = 100
ID_ETAT = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/behramkorkut/pharmaflux/etat"))


class QdrantIndisponible(Exception):  # noqa: N818 (nom français voulu)
    """Qdrant ne répond pas, ou répond autre chose que ce que l'API promet."""


@dataclass(frozen=True, slots=True)
class Point:
    identifiant: str
    vecteur: Sequence[float]
    charge: dict[str, object]
    creux: dict[str, object] | None = None  # vecteur creux {indices, values} (format 2)


class Qdrant:
    """Le client ; ``espace`` préfixe l'alias, la collection d'état et les collections."""

    def __init__(
        self, url: str, transport: httpx.BaseTransport | None = None, espace: str = ESPACE
    ) -> None:
        self.url = url.rstrip("/")
        self.espace = espace
        self.alias_fragments = f"{espace}-fragments"
        self.collection_etat = f"{espace}-index-etat"
        self._client = httpx.Client(base_url=self.url, transport=transport, timeout=DELAI_S)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Qdrant:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- collections et alias ---

    def collections(self) -> list[str]:
        resultat = self._appeler("GET", "/collections")
        return sorted(c["name"] for c in resultat["collections"])

    def creer_collection(self, nom: str, dimension: int | None) -> None:
        """Une collection aux vecteurs ``dense`` (cosinus) et ``lexical`` (creux, IDF au serveur)
        et ses index de charge ; sans vecteur si ``dimension`` est None (l'état)."""
        vecteurs = {} if dimension is None else {VECTEUR: {"size": dimension, "distance": "Cosine"}}
        corps: dict[str, object] = {"vectors": vecteurs}
        if dimension is not None:
            corps["sparse_vectors"] = {VECTEUR_CREUX: {"modifier": "idf"}}
        self._appeler("PUT", f"/collections/{nom}", corps)
        if dimension is not None:
            for champ in CHAMPS_INDEXES:
                self._appeler(
                    "PUT",
                    f"/collections/{nom}/index?wait=true",
                    {"field_name": champ, "field_schema": "keyword"},
                )

    def supprimer_collection(self, nom: str) -> None:
        self._appeler("DELETE", f"/collections/{nom}", absent_ok=True)

    def alias(self) -> dict[str, str]:
        resultat = self._appeler("GET", "/aliases")
        return {a["alias_name"]: a["collection_name"] for a in resultat["aliases"]}

    def basculer_alias(self, alias: str, collection: str) -> None:
        """L'alias désigne ``collection``, d'un seul appel : jamais d'instant sans alias."""
        actions: list[dict[str, object]] = []
        if alias in self.alias():
            actions.append({"delete_alias": {"alias_name": alias}})
        actions.append({"create_alias": {"collection_name": collection, "alias_name": alias}})
        self._appeler("POST", "/collections/aliases", {"actions": actions})

    # --- points ---

    def ecrire(self, collection: str, points: Sequence[Point]) -> None:
        if not points:
            return
        corps = {"points": [self._point(p) for p in points]}
        self._appeler("PUT", f"/collections/{collection}/points?wait=true", corps)

    @staticmethod
    def _point(p: Point) -> dict[str, object]:
        vecteur: dict[str, object] = {VECTEUR: list(p.vecteur)}
        if p.creux is not None:
            vecteur[VECTEUR_CREUX] = p.creux
        return {"id": p.identifiant, "vector": vecteur, "payload": p.charge}

    def supprimer(self, collection: str, filtre: dict[str, object]) -> None:
        """Par filtre : seuls les tests d'intégration s'en servent (la mise à jour retire par
        identifiants, ``supprimer_ids``)."""
        self._appeler(
            "POST", f"/collections/{collection}/points/delete?wait=true", {"filter": filtre}
        )

    def supprimer_ids(self, collection: str, identifiants: Sequence[str]) -> None:
        if identifiants:
            self._appeler(
                "POST",
                f"/collections/{collection}/points/delete?wait=true",
                {"points": list(identifiants)},
            )

    def compter(self, collection: str, filtre: dict[str, object] | None = None) -> int:
        corps: dict[str, object] = {"exact": True}
        if filtre is not None:
            corps["filter"] = filtre
        return int(self._appeler("POST", f"/collections/{collection}/points/count", corps)["count"])

    def parcourir(
        self,
        collection: str,
        filtre: dict[str, object] | None = None,
        *,
        vecteurs: bool = False,
        champs: Sequence[str] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Tous les points (identifiant, charge, vecteur si demandé), par identifiant croissant."""
        suivant: object = None
        while True:
            corps: dict[str, object] = {
                "limit": LOT_PARCOURS,
                "with_payload": list(champs) if champs is not None else True,
                "with_vector": [VECTEUR, VECTEUR_CREUX] if vecteurs else False,
            }
            if filtre is not None:
                corps["filter"] = filtre
            if suivant is not None:
                corps["offset"] = suivant
            resultat = self._appeler("POST", f"/collections/{collection}/points/scroll", corps)
            yield from resultat["points"]
            suivant = resultat.get("next_page_offset")
            if suivant is None:
                return

    def chercher(
        self,
        collection: str,
        vecteur: Sequence[float],
        k: int,
        filtre: dict[str, object] | None = None,
    ) -> list[dict[str, Any]]:
        """Les ``k`` points les plus proches (cosinus, recherche exacte), score et charge."""
        corps: dict[str, object] = {
            "query": list(vecteur),
            "using": VECTEUR,
            "limit": k,
            "with_payload": True,
            # Exacte : sur le jeu, l'index HNSW par défaut ne rendait que 82 % des dix premiers
            # (91 % avec hnsw_ef 256), pour 3 ms ; l'exacte en prend 7 (mesuré au palier 2).
            "params": {"exact": True},
        }
        if filtre is not None:
            corps["filter"] = filtre
        resultat = self._appeler("POST", f"/collections/{collection}/points/query", corps)
        points: list[dict[str, Any]] = resultat["points"]
        return points

    def chercher_creux(
        self,
        collection: str,
        creux: dict[str, object],
        k: int,
        filtre: dict[str, object] | None = None,
    ) -> list[dict[str, Any]]:
        """Les ``k`` points par score BM25 (vecteur creux ``lexical``, IDF appliquée au serveur)."""
        corps: dict[str, object] = {
            "query": creux,
            "using": VECTEUR_CREUX,
            "limit": k,
            "with_payload": True,
        }
        if filtre is not None:
            corps["filter"] = filtre
        resultat = self._appeler("POST", f"/collections/{collection}/points/query", corps)
        points: list[dict[str, Any]] = resultat["points"]
        return points

    # --- l'état de l'index ---

    def lire_etat(self) -> dict[str, Any] | None:
        if self.collection_etat not in self.collections():
            return None
        points = self._appeler(
            "POST",
            f"/collections/{self.collection_etat}/points",
            {"ids": [ID_ETAT], "with_payload": True},
        )
        if not isinstance(points, list) or not points:
            return None
        charge: dict[str, Any] = points[0]["payload"]
        return charge

    def ecrire_etat(self, etat: dict[str, object]) -> None:
        """Remplace l'état (un point sans vecteur) ; la collection est créée au premier appel."""
        if self.collection_etat not in self.collections():
            self.creer_collection(self.collection_etat, None)
        corps = {"points": [{"id": ID_ETAT, "vector": {}, "payload": etat}]}
        self._appeler("PUT", f"/collections/{self.collection_etat}/points?wait=true", corps)

    # ---

    def _appeler(
        self, methode: str, chemin: str, corps: object | None = None, *, absent_ok: bool = False
    ) -> Any:
        try:
            reponse = self._client.request(methode, chemin, json=corps)
        except httpx.HTTPError as exc:
            raise QdrantIndisponible(f"{self.url}{chemin} : {exc!r}") from exc
        if absent_ok and reponse.status_code == 404:
            return None
        if reponse.status_code >= 400:
            raise QdrantIndisponible(
                f"{methode} {self.url}{chemin} : HTTP {reponse.status_code} {reponse.text[:300]}"
            )
        try:
            return reponse.json()["result"]
        except (ValueError, KeyError) as exc:
            raise QdrantIndisponible(f"{methode} {self.url}{chemin} : réponse inattendue") from exc


def filtre_egal(champ: str, valeurs: str | Sequence[str]) -> dict[str, object]:
    """``champ`` égal à une valeur, ou à l'une des valeurs."""
    if isinstance(valeurs, str):
        return {"must": [{"key": champ, "match": {"value": valeurs}}]}
    return {"must": [{"key": champ, "match": {"any": list(valeurs)}}]}
