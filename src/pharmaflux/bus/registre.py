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

Un appel coupé **sans réponse** (connexion refusée, fermée avant la réponse)
est réessayé deux fois, après 0,2 puis 0,8 s (mission 07, addendum 1 A2) :
le registre de Redpanda coupe parfois un ``POST …/versions`` pendant qu'il
efface des topics. Tous les appels du client sont sûrs à rejouer (lectures,
``PUT`` de la règle, enregistrement du même schéma, suppressions). Une
réponse, même 5xx, n'est jamais réessayée, ni un délai dépassé : c'est un
fait du registre, pas une coupure. Chaque réessai écrit une ligne horodatée
sur la sortie d'erreur et s'ajoute à ``REESSAIS``, que les tests
d'intégration exigent vide.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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
ATTENTES_S = (0.2, 0.8)  # avant le 2ᵉ et le 3ᵉ essai ; trois essais en tout
SANS_REPONSE = (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError, httpx.WriteError)

# Les lignes des réessais qui ont servi dans ce processus (``schemas enregistrer`` en donne le
# total, la session des tests d'intégration échoue s'il en reste).
REESSAIS: list[str] = []


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
    """Un client du registre ; ``transport`` et ``dormir`` permettent aux tests de le simuler."""

    def __init__(
        self,
        url: str,
        transport: httpx.BaseTransport | None = None,
        *,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.url = url.rstrip("/")
        self.reessais = 0  # ceux de ce client ; REESSAIS garde ceux du processus
        self._dormir = dormir
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
        """Pour les tests d'intégration : efface un sujet à suffixe unique, définitivement.

        La suppression définitive est tentée même quand la douce répond 404 : un sujet déjà
        effacé en douceur (une coupure, un nettoyage interrompu) répond 404 à la douce, et
        resterait sinon pour toujours dans le registre.
        """
        self._appeler("DELETE", f"/subjects/{sujet_}", absent_ok=True)
        self._appeler("DELETE", f"/subjects/{sujet_}?permanent=true", absent_ok=True)

    def _identifiant_de(self, sujet_: str, schema: dict[str, object]) -> int | None:
        """L'identifiant si ce schéma exact est déjà enregistré sous le sujet, sinon None."""
        reponse = self._appeler("POST", f"/subjects/{sujet_}", _corps(schema), absent_ok=True)
        return None if reponse is None else _entier(reponse, "id")

    def _appeler(
        self, methode: str, chemin: str, corps: object | None = None, *, absent_ok: bool = False
    ) -> dict[str, object] | None:
        reponse = self._envoyer(methode, chemin, corps)
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

    def _envoyer(self, methode: str, chemin: str, corps: object | None) -> httpx.Response:
        """La réponse du registre, après au plus deux réessais d'un appel coupé sans réponse."""
        for essai in range(len(ATTENTES_S) + 1):
            try:
                return self._client.request(methode, chemin, json=corps)
            except SANS_REPONSE as exc:
                if essai == len(ATTENTES_S):
                    raise RegistreIndisponible(
                        f"{self.url}{chemin} : {exc!r} ({essai + 1} essais)"
                    ) from exc
                attente = ATTENTES_S[essai]
                ligne = (
                    f"registre : {methode} {chemin} coupé sans réponse ({type(exc).__name__}),"
                    f" essai {essai + 2}/{len(ATTENTES_S) + 1} dans {attente} s"
                    f" ({_horodatage()})"
                )
                print(ligne, file=sys.stderr, flush=True)
                REESSAIS.append(ligne)
                self.reessais += 1
                self._dormir(attente)
            except httpx.HTTPError as exc:
                raise RegistreIndisponible(f"{self.url}{chemin} : {exc!r}") from exc
        raise AssertionError("inatteignable")  # la boucle rend ou lève


def _horodatage() -> str:
    """L'instant en UTC à la milliseconde, pour recouper avec le journal du courtier."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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
