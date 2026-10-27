"""L'enveloppe d'un message : topic, clé, valeur, en-têtes, horodatage (ADR 0007).

Le bus transporte l'événement de la mission 02 **sans le transformer** : la
valeur est la ligne JSONL telle qu'elle est sur le disque, sans son ``\\n``
final, à l'octet près. Tout ce que le bus ajoute est dans l'enveloppe : le
topic (``pharmaflux.<entite>.v<version_schema>``), la clé (l'objet JSON
``cle`` de l'événement, compact et à clés triées, la même partition pour
tous les événements d'un même médicament), l'horodatage (``date_observation``
de l'événement, jamais l'horloge du poste : deux publications du même fichier
donnent le même message), et des en-têtes de repère (``id``, ``entite``,
``type``, ``archive``, ``fichier``, ``schema_id``, ``producteur``).

Une ligne que ``deserialiser`` refuse, ou qu'un courtier refuse pour sa
taille, part dans la **file des messages en échec** (``pharmaflux.echecs.v1``)
sous la forme d'un message qui dit le motif, le fichier, la ligne et porte la
ligne brute (tronquée à 64 Ko s'il le faut).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from importlib.metadata import version as version_du_paquet

from pharmaflux.evenements import schema
from pharmaflux.evenements.schema import VERSION_SCHEMA, Evenement, EvenementInvalide

PREFIXE_PAR_DEFAUT = "pharmaflux"
VERSION_ECHEC = 1
TRONCATURE_ECHEC = 64 * 1024  # octets de ligne brute gardés dans un message en échec
EnTetes = list[tuple[str, bytes]]


def nom_topic(entite: str, prefixe: str = PREFIXE_PAR_DEFAUT) -> str:
    """``pharmaflux.bdpm.presentations.v1`` : l'entité telle que l'événement la porte."""
    return f"{prefixe}.{entite}.v{VERSION_SCHEMA}"


def topic_echecs(prefixe: str = PREFIXE_PAR_DEFAUT) -> str:
    return f"{prefixe}.echecs.v{VERSION_ECHEC}"


def producteur() -> str:
    return f"pharmaflux/{version_du_paquet('pharmaflux')}"


@dataclass(frozen=True, slots=True)
class Enveloppe:
    """Un message prêt à partir."""

    topic: str
    cle: bytes
    valeur: bytes
    en_tetes: EnTetes
    horodatage_ms: int  # ``CreateTime`` ; 0 laisse le courtier poser le sien (file des échecs)


def cle_message(evenement: Evenement) -> bytes:
    """L'objet JSON ``cle``, compact, clés triées, UTF-8 : lisible, et stable par construction."""
    return json.dumps(
        dict(evenement.cle), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def horodatage_ms(date_observation: str) -> int:
    """``2026-10-24T19:41:46Z`` → millisecondes depuis l'époque, UTC."""
    instant = datetime.strptime(date_observation, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return int(instant.timestamp()) * 1000


def envelopper(
    ligne: bytes, fichier: str, schema_id: int, prefixe: str = PREFIXE_PAR_DEFAUT
) -> Enveloppe:
    """L'enveloppe d'une ligne JSONL (``\\n`` final retiré) ; ``EvenementInvalide`` sinon.

    ``fichier`` est le chemin du JSONL sous la sortie : l'unité de
    republication, pour qu'un consommateur sache d'où vient un doublon.
    """
    valeur = ligne[:-1] if ligne.endswith(b"\n") else ligne
    try:
        texte = valeur.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvenementInvalide(f"octets illisibles en UTF-8 : {exc}") from exc
    evenement = schema.deserialiser(texte)
    en_tetes: EnTetes = [
        ("id", evenement.id.encode()),
        ("version_schema", str(VERSION_SCHEMA).encode()),
        ("schema_id", str(schema_id).encode()),
        ("entite", evenement.entite.encode()),
        ("type", evenement.type.value.encode()),
        ("archive", evenement.archive.encode()),
        ("fichier", fichier.encode()),
        ("producteur", producteur().encode()),
    ]
    return Enveloppe(
        topic=nom_topic(evenement.entite, prefixe),
        cle=cle_message(evenement),
        valeur=valeur,
        en_tetes=en_tetes,
        horodatage_ms=horodatage_ms(evenement.date_observation),
    )


class Motif(StrEnum):
    ILLISIBLE = "illisible"  # ``deserialiser`` refuse la ligne
    TROP_GROS = "trop_gros"  # le courtier refuserait le message pour sa taille


def message_echec(
    motif: Motif,
    detail: str,
    entite: str,
    fichier: str,
    numero: int,
    ligne: bytes,
    schema_id: int,
    prefixe: str = PREFIXE_PAR_DEFAUT,
) -> Enveloppe:
    """Le message de la file des échecs pour la ligne ``numero`` de ``fichier``.

    Clé : l'entité. Valeur : un objet JSON ``version_echec`` 1 avec le motif,
    le détail, la ligne brute (tronquée à 64 Ko, ``tronquee`` vrai), sa
    taille réelle et son sha256 entier, et l'identifiant de l'événement
    quand la ligne se lit. Horodatage laissé au courtier (``LogAppendTime``
    sur ce topic) : l'heure de l'échec est une information, et une ligne
    cassée n'a pas de date de source.
    """
    brute = ligne[:-1] if ligne.endswith(b"\n") else ligne
    tronquee = len(brute) > TRONCATURE_ECHEC
    identifiant = None
    if motif is not Motif.ILLISIBLE:
        try:
            identifiant = schema.deserialiser(brute.decode("utf-8")).id
        except (EvenementInvalide, UnicodeDecodeError):
            identifiant = None
    contenu = {
        "version_echec": VERSION_ECHEC,
        "motif": motif.value,
        "detail": detail,
        "entite": entite,
        "fichier": fichier,
        "ligne": numero,
        "id": identifiant,
        "taille": len(brute),
        "sha256_ligne": hashlib.sha256(brute).hexdigest(),
        "ligne_brute": brute[:TRONCATURE_ECHEC].decode("utf-8", errors="replace"),
        "tronquee": tronquee,
    }
    valeur = json.dumps(contenu, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    en_tetes: EnTetes = [
        ("version_echec", str(VERSION_ECHEC).encode()),
        ("schema_id", str(schema_id).encode()),
        ("entite", entite.encode()),
        ("fichier", fichier.encode()),
        ("motif", motif.value.encode()),
        ("producteur", producteur().encode()),
    ]
    return Enveloppe(topic_echecs(prefixe), entite.encode(), valeur.encode("utf-8"), en_tetes, 0)
