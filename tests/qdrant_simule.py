"""Un Qdrant en mémoire : l'API REST réduite aux appels de ``pharmaflux.index.qdrant``.

Il résout les alias, évalue les filtres de l'index (``must`` : égalité ou
« l'une des valeurs » sur un champ ; ``must_not`` : ``has_id``), trie le
parcours par identifiant et cherche par cosinus exact. Les tests d'intégration
vérifient le même comportement contre le vrai Qdrant.
"""

from __future__ import annotations

import bisect
import json
import math
from typing import Any

import httpx


class QdrantSimule:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, Any]] = {}  # nom → {"dimension", "points"}
        self.alias: dict[str, str] = {}
        self.appels: list[str] = []
        self.ecritures = 0  # invalide le tri mis en cache du parcours
        self._cache_tries: tuple[object, list[str]] = (None, [])
        self._coupures: list[tuple[str, int]] = []  # (début de « METHODE chemin », rang restant)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._repondre)

    def couper(self, prefixe: str, rang: int = 1) -> None:
        """Une coupure de connexion avant le ``rang``-ième appel qui commence par ``prefixe``."""
        self._coupures.append((prefixe, rang))

    def _tries(self, nom: str, filtre: dict[str, Any] | None) -> list[str]:
        """Les identifiants gardés par le filtre, triés ; mis en cache tant que rien ne change."""
        points = self.collections[nom]["points"]
        cle = (nom, json.dumps(filtre, sort_keys=True), len(points), self.ecritures)
        if self._cache_tries[0] != cle:
            self._cache_tries = (cle, sorted(i for i, p in points.items() if _garde(p, filtre)))
        return self._cache_tries[1]

    def points(self, nom: str) -> dict[str, dict[str, Any]]:
        return self.collections[self.alias.get(nom, nom)]["points"]

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        methode, morceaux = requete.method, requete.url.path.strip("/").split("/")
        corps = json.loads(requete.content) if requete.content else {}
        self.appels.append(f"{methode} {requete.url.path}")
        appel = f"{methode} {requete.url.path}"
        for rang, (prefixe, reste_) in enumerate(self._coupures):
            if appel.startswith(prefixe):
                if reste_ == 1:
                    del self._coupures[rang]
                    raise httpx.ConnectError(f"coupure simulée avant {appel}", request=requete)
                self._coupures[rang] = (prefixe, reste_ - 1)
                break
        if methode in ("PUT", "POST", "DELETE") and not requete.url.path.endswith(
            ("/scroll", "/count", "/query")
        ):
            self.ecritures += 1
        if morceaux == ["collections"] and methode == "GET":
            return _ok({"collections": [{"name": n} for n in self.collections]})
        if morceaux == ["aliases"]:
            return _ok(
                {
                    "aliases": [
                        {"alias_name": a, "collection_name": c} for a, c in self.alias.items()
                    ]
                }
            )
        if morceaux == ["collections", "aliases"]:
            for action in corps["actions"]:
                if "delete_alias" in action:
                    del self.alias[action["delete_alias"]["alias_name"]]
                else:
                    cree = action["create_alias"]
                    assert cree["collection_name"] in self.collections
                    self.alias[cree["alias_name"]] = cree["collection_name"]
            return _ok(True)
        nom = self.alias.get(morceaux[1], morceaux[1])
        reste = morceaux[2:]
        if not reste:
            if methode == "PUT":
                assert nom not in self.collections, "collection déjà créée"
                vecteurs = corps["vectors"]
                dimension = vecteurs["dense"]["size"] if vecteurs else None
                self.collections[nom] = {"dimension": dimension, "points": {}}
                return _ok(True)
            if methode == "DELETE":
                if nom not in self.collections:
                    return httpx.Response(404, json={"status": {"error": "Not found"}})
                del self.collections[nom]
                self.alias = {a: c for a, c in self.alias.items() if c != nom}
                return _ok(True)
        if nom not in self.collections:
            return httpx.Response(404, json={"status": {"error": f"{nom} absente"}})
        points = self.collections[nom]["points"]
        if reste == ["index"]:
            return _ok({"status": "completed"})
        if reste == ["points"] and methode == "PUT":
            for p in corps["points"]:
                points[p["id"]] = {"id": p["id"], "vector": p["vector"], "payload": p["payload"]}
            return _ok({"status": "completed"})
        if reste == ["points"] and methode == "POST":
            return _ok([_vu(points[i], True, False) for i in corps["ids"] if i in points])
        if reste == ["points", "delete"]:
            if "points" in corps:
                for i in corps["points"]:
                    points.pop(i, None)
            else:
                for i in [i for i, p in points.items() if _garde(p, corps["filter"])]:
                    del points[i]
            return _ok({"status": "completed"})
        if reste == ["points", "count"]:
            filtre = corps.get("filter")
            return _ok({"count": sum(1 for p in points.values() if _garde(p, filtre))})
        if reste == ["points", "scroll"]:
            tries = self._tries(nom, corps.get("filter"))
            debut = bisect.bisect_left(tries, corps["offset"]) if "offset" in corps else 0
            page = tries[debut : debut + corps["limit"]]
            suivant = tries[debut + corps["limit"]] if debut + corps["limit"] < len(tries) else None
            return _ok(
                {
                    "points": [
                        _vu(points[i], corps["with_payload"], bool(corps["with_vector"]))
                        for i in page
                    ],
                    "next_page_offset": suivant,
                }
            )
        if reste == ["points", "query"]:
            candidats = [p for p in points.values() if _garde(p, corps.get("filter"))]
            notes = sorted(
                ((_cosinus(corps["query"], p["vector"]["dense"]), p["id"]) for p in candidats),
                key=lambda x: (-x[0], x[1]),
            )[: corps["limit"]]
            return _ok(
                {
                    "points": [
                        {"id": i, "score": s, "payload": points[i]["payload"]} for s, i in notes
                    ]
                }
            )
        return httpx.Response(500, json={"status": {"error": f"inattendu : {methode} {morceaux}"}})


def _ok(resultat: object) -> httpx.Response:
    return httpx.Response(200, json={"result": resultat, "status": "ok"})


def _vu(point: dict[str, Any], charge: object, vecteur: bool) -> dict[str, Any]:
    vu: dict[str, Any] = {"id": point["id"]}
    if charge is True:
        vu["payload"] = point["payload"]
    elif isinstance(charge, list):
        vu["payload"] = {c: point["payload"][c] for c in charge if c in point["payload"]}
    if vecteur:
        vu["vector"] = point["vector"]
    return vu


def _garde(point: dict[str, Any], filtre: dict[str, Any] | None) -> bool:
    if filtre is None:
        return True
    for condition in filtre.get("must", []):
        valeur = point["payload"].get(condition["key"])
        correspondance = condition["match"]
        if "value" in correspondance and valeur != correspondance["value"]:
            return False
        if "any" in correspondance and valeur not in correspondance["any"]:
            return False
    for condition in filtre.get("must_not", []):
        if point["id"] in condition.get("has_id", []):
            return False
    return True


def _cosinus(a: list[float], b: list[float]) -> float:
    produit = sum(x * y for x, y in zip(a, b, strict=True))
    return produit / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))
