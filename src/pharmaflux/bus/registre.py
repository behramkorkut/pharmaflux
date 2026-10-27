"""Le registre de schémas de Redpanda (API REST compatible Confluent), vu du projet.

Les schémas vivent dans le dépôt (``bus/schemas/``) : l'événement v1
(``evenement.v1.schema.json``, aussi strict que ``deserialiser``) et le
message en échec (``echec.v1.schema.json``). Un sujet par topic
(``<topic>-value``), règle ``BACKWARD_TRANSITIVE`` : les consommateurs du
Lot 2 relisent les topics depuis le début avec leur schéma du jour, il doit
lire toutes les versions passées. ``bus/schemas/historique/`` garde les
versions déjà publiées d'un sujet, enregistrées dans l'ordre avant le schéma
courant, pour qu'un registre neuf (la CI) refuse une évolution incompatible.
Un changement incompatible est une nouvelle ``version_schema``, donc un
nouveau topic, jamais une version de plus du même sujet.

Le registre n'encode rien : la valeur du message est la ligne JSONL nue, et
l'identifiant du schéma voyage dans l'en-tête ``schema_id``. Un outil qui
attend le format Confluent (cinq octets devant la valeur) ne décode pas par
le registre : c'est le prix de garder l'événement à l'octet près.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable

import httpx

from pharmaflux.bus.enveloppe import nom_topic, topic_echecs

REGISTRE_PAR_DEFAUT = "http://127.0.0.1:18081"
VARIABLE_REGISTRE = "PHARMAFLUX_REGISTRE"
COMPATIBILITE = "BACKWARD_TRANSITIVE"
TYPE_CONTENU = "application/vnd.schemaregistry.v1+json"
SCHEMA_EVENEMENT = "evenement.v1.schema.json"
SCHEMA_ECHEC = "echec.v1.schema.json"
DELAI_S = 10.0


class RegistreIndisponible(Exception):  # noqa: N818 (nom français voulu)
    """Le registre ne répond pas, ou répond autre chose que ce que l'API promet."""


class SchemaAbsent(Exception):  # noqa: N818 (nom français voulu)
    """Le sujet n'a aucune version enregistrée : lancer ``pharmaflux schemas enregistrer``."""


class SchemaIncompatible(Exception):  # noqa: N818 (nom français voulu)
    """Le schéma courant du dépôt viole la règle du sujet face aux versions déjà enregistrées
    (code 1) : une évolution incompatible est une nouvelle ``version_schema``, donc un nouveau
    topic (ADR 0007), jamais une version de plus du même sujet. Rien n'est enregistré pour lui."""


def dossier_schemas() -> Traversable:
    return files("pharmaflux.bus") / "schemas"


def charger_schema(nom: str) -> dict[str, object]:
    """Le schéma JSON ``nom`` du dépôt, tel quel."""
    brut = json.loads((dossier_schemas() / nom).read_text(encoding="utf-8"))
    if not isinstance(brut, dict):
        raise ValueError(f"{nom} : un objet JSON est attendu")
    return brut


def historique(nom: str) -> list[dict[str, object]]:
    """Les versions déjà publiées de ``nom``, par numéro croissant (``historique/<nom>.<n>.json``).

    Le tri est numérique : la version 10 vient après la 2, pas après la 1.
    """
    motif = re.compile(rf"^{re.escape(nom.removesuffix('.json'))}\.(\d+)\.json$")
    numerotes: list[tuple[int, Traversable]] = []
    for f in (dossier_schemas() / "historique").iterdir():
        correspondance = motif.match(f.name)
        if correspondance is not None:
            numerotes.append((int(correspondance[1]), f))
    numerotes.sort(key=lambda couple: couple[0])
    return [json.loads(f.read_text(encoding="utf-8")) for _, f in numerotes]


def sujet(topic: str) -> str:
    return f"{topic}-value"


def sujets_du_projet(entites: list[str], prefixe: str | None = None) -> list[tuple[str, str]]:
    """(sujet, fichier de schéma) pour chaque topic du projet : les entités, puis les échecs."""
    args = {} if prefixe is None else {"prefixe": prefixe}
    paires = [(sujet(nom_topic(entite, **args)), SCHEMA_EVENEMENT) for entite in sorted(entites)]
    paires.append((sujet(topic_echecs(**args)), SCHEMA_ECHEC))
    return paires


@dataclass(frozen=True, slots=True)
class Enregistrement:
    sujet: str
    identifiant: int
    nouveau: bool  # faux quand le registre connaissait déjà ce schéma exact


class Registre:
    """Un client du registre ; ``transport`` permet aux tests de le simuler."""

    def __init__(self, url: str, transport: httpx.BaseTransport | None = None) -> None:
        self.url = url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.url,
            transport=transport,
            timeout=DELAI_S,
            headers={"Content-Type": TYPE_CONTENU, "Accept": TYPE_CONTENU},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Registre:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def poser_compatibilite(self, sujet_: str, regle: str = COMPATIBILITE) -> None:
        self._appeler("PUT", f"/config/{sujet_}", {"compatibility": regle})

    def enregistrer(self, sujet_: str, schema: dict[str, object]) -> Enregistrement:
        """Enregistre ``schema`` sous ``sujet_`` ; idempotent, le registre rend le même id."""
        connu = self._identifiant_de(sujet_, schema)
        reponse = self._appeler("POST", f"/subjects/{sujet_}/versions", _corps(schema))
        assert reponse is not None  # sans absent_ok, un 404 lève RegistreIndisponible
        return Enregistrement(sujet_, _entier(reponse, "id"), nouveau=connu is None)

    def identifiant(self, sujet_: str) -> int:
        """L'identifiant de la dernière version du sujet ; ``SchemaAbsent`` s'il n'en a pas."""
        reponse = self._appeler("GET", f"/subjects/{sujet_}/versions/latest", absent_ok=True)
        if reponse is None:
            raise SchemaAbsent(sujet_)
        return _entier(reponse, "id")

    def compatible(self, sujet_: str, schema: dict[str, object]) -> bool:
        """``schema`` respecte-t-il la règle du sujet face à ses versions enregistrées ?"""
        reponse = self._appeler(
            "POST",
            f"/compatibility/subjects/{sujet_}/versions/latest?verbose=true",
            _corps(schema),
            absent_ok=True,
        )
        if reponse is None:
            return True  # aucune version : tout est compatible
        return bool(reponse.get("is_compatible"))

    def supprimer(self, sujet_: str) -> None:
        """Pour les tests d'intégration : efface un sujet à suffixe unique, définitivement."""
        if self._appeler("DELETE", f"/subjects/{sujet_}", absent_ok=True) is not None:
            self._appeler("DELETE", f"/subjects/{sujet_}?permanent=true", absent_ok=True)

    def _identifiant_de(self, sujet_: str, schema: dict[str, object]) -> int | None:
        """L'identifiant si ce schéma exact est déjà enregistré sous le sujet, sinon None."""
        reponse = self._appeler("POST", f"/subjects/{sujet_}", _corps(schema), absent_ok=True)
        return None if reponse is None else _entier(reponse, "id")

    def _appeler(
        self, methode: str, chemin: str, corps: object | None = None, *, absent_ok: bool = False
    ) -> dict[str, object] | None:
        try:
            reponse = self._client.request(methode, chemin, json=corps)
        except httpx.HTTPError as exc:
            raise RegistreIndisponible(f"{self.url}{chemin} : {exc!r}") from exc
        if absent_ok and reponse.status_code == 404:
            return None
        if reponse.status_code >= 400:
            raise RegistreIndisponible(
                f"{methode} {self.url}{chemin} : HTTP {reponse.status_code} {reponse.text[:300]}"
            )
        try:
            brut = reponse.json()
        except ValueError as exc:
            raise RegistreIndisponible(f"{methode} {self.url}{chemin} : réponse non JSON") from exc
        return brut if isinstance(brut, dict) else {"valeur": brut}


def _corps(schema: dict[str, object]) -> dict[str, str]:
    return {"schema": json.dumps(schema, sort_keys=True), "schemaType": "JSON"}


def _entier(reponse: dict[str, object], cle: str) -> int:
    valeur = reponse.get(cle)
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise RegistreIndisponible(f"réponse sans « {cle} » entier : {reponse}")
    return valeur


def enregistrer_tout(
    registre: Registre, entites: list[str], prefixe: str | None = None
) -> list[Enregistrement]:
    """Pose la règle de compatibilité, puis enregistre par sujet l'historique et le courant.

    L'historique s'enregistre sans contrôle : c'est le passé. Le schéma
    courant est d'abord soumis à ``compatible`` ; refusé, ``SchemaIncompatible``
    arrête tout avant de l'enregistrer, avec un message lisible plutôt que le
    HTTP 409 du registre. Les sujets déjà traités restent enregistrés : la
    commande est idempotente, les relancer ne change rien.
    """
    resultats = []
    for sujet_, nom in sujets_du_projet(entites, prefixe):
        registre.poser_compatibilite(sujet_)
        for ancien in historique(nom):
            registre.enregistrer(sujet_, ancien)
        courant = charger_schema(nom)
        if not registre.compatible(sujet_, courant):
            raise SchemaIncompatible(
                f"le schéma du dépôt {nom} est incompatible avec les versions enregistrées de"
                f" {sujet_} ({COMPATIBILITE}) : une évolution incompatible est une nouvelle"
                " version_schema, donc un nouveau topic (ADR 0007) ; rien n'est enregistré pour"
                " ce sujet"
            )
        resultats.append(registre.enregistrer(sujet_, courant))
    return resultats
