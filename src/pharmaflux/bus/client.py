"""Le courtier vu du projet : producteur idempotent, création des topics, un bus simulable.

``Bus`` est ce que ``publication`` utilise ; ``BusKafka`` le réalise avec
``confluent-kafka`` (librdkafka), et les tests unitaires le remplacent par un
bus en mémoire. Le producteur est **idempotent** (``acks=all``, réessais,
ordre conservé par partition), compresse en zstd, partitionne en
``murmur2_random`` (la même partition que les clients Java, ``rpk`` et la
console : le défaut de librdkafka, ``consistent_random``, ne l'est pas), et
vérifie la taille des messages **avant l'envoi** (``message.max.bytes`` à
1 Mo, la limite par défaut du courtier) : un message trop gros est refusé à
``produire``, jamais à la livraison. Les topics sont créés par le projet avec
leur configuration : **rétention sans limite**, jamais de compactage,
``CreateTime`` pour les événements, ``LogAppendTime`` pour la file des
échecs. Une rétention par défaut effacerait un jour des événements d'octobre
2026 sans bruit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from confluent_kafka import KafkaError, KafkaException, Message, Producer
from confluent_kafka.admin import AdminClient
from confluent_kafka.cimpl import NewTopic

from pharmaflux.bus.enveloppe import Enveloppe

COURTIER_PAR_DEFAUT = "127.0.0.1:19092"
VARIABLE_COURTIER = "PHARMAFLUX_COURTIER"
PARTITIONS_EVENEMENTS = 3  # figé par l'ADR 0007 : changer redistribue les clés
PARTITIONS_ECHECS = 1
TAILLE_MAX_MESSAGE = 1_048_576  # octets, la limite par défaut de Redpanda et de Kafka
DELAI_LIVRAISON_S = 120
DELAI_COURTIER_S = 5.0

RETENTION_SANS_LIMITE = {
    "retention.ms": "-1",
    "retention.bytes": "-1",
    "cleanup.policy": "delete",
}
CONFIG_EVENEMENTS = {**RETENTION_SANS_LIMITE, "message.timestamp.type": "CreateTime"}
CONFIG_ECHECS = {**RETENTION_SANS_LIMITE, "message.timestamp.type": "LogAppendTime"}


class CourtierInjoignable(Exception):  # noqa: N818 (nom français voulu)
    """Le courtier ne répond pas, ou refuse une opération d'administration."""


class MessageTropGros(Exception):  # noqa: N818 (nom français voulu)
    """Le message dépasse ``message.max.bytes`` : il n'est pas envoyé."""


@dataclass(frozen=True, slots=True)
class DefinitionTopic:
    nom: str
    partitions: int
    configuration: dict[str, str] = field(default_factory=dict)


def definition_evenements(nom: str) -> DefinitionTopic:
    return DefinitionTopic(nom, PARTITIONS_EVENEMENTS, dict(CONFIG_EVENEMENTS))


def definition_echecs(nom: str) -> DefinitionTopic:
    return DefinitionTopic(nom, PARTITIONS_ECHECS, dict(CONFIG_ECHECS))


@dataclass(frozen=True, slots=True)
class Livraison:
    """Le rapport de livraison d'un message : où il est allé, ou pourquoi il n'y est pas."""

    topic: str
    partition: int
    offset: int
    erreur: str | None


Rappel = Callable[[Livraison], None]


class Bus(Protocol):
    """Ce que la publication demande au courtier."""

    def preparer_topics(self, definitions: list[DefinitionTopic]) -> None:
        """Crée les topics manquants avec leur configuration ; ceux qui existent sont gardés."""

    def produire(self, enveloppe: Enveloppe, rappel: Rappel) -> None:
        """Met le message en file de départ ; ``rappel`` reçoit sa livraison, plus tard."""

    def attendre(self, delai_s: float) -> int:
        """Attend les livraisons en attente ; rend le nombre de messages encore non livrés."""


def configuration_producteur(courtier: str) -> dict[str, object]:
    return {
        "bootstrap.servers": courtier,
        "enable.idempotence": True,  # acks=all, réessais, ordre conservé par partition
        "compression.type": "zstd",
        "partitioner": "murmur2_random",
        "message.max.bytes": TAILLE_MAX_MESSAGE,
        "linger.ms": 20,
        "delivery.timeout.ms": DELAI_LIVRAISON_S * 1000,
        "socket.connection.setup.timeout.ms": int(DELAI_COURTIER_S * 1000),
    }


class BusKafka:
    """Le bus réel : un ``Producer`` et un ``AdminClient`` de confluent-kafka."""

    def __init__(self, courtier: str) -> None:
        self.courtier = courtier
        self._admin = AdminClient({"bootstrap.servers": courtier})
        self._producteur = Producer(configuration_producteur(courtier))

    def verifier_courtier(self, delai_s: float = DELAI_COURTIER_S) -> list[str]:
        """Les topics du courtier, ou ``CourtierInjoignable`` s'il ne répond pas dans le délai."""
        try:
            metadonnees = self._admin.list_topics(timeout=delai_s)
        except KafkaException as exc:
            raise CourtierInjoignable(f"{self.courtier} : {_texte(exc)}") from exc
        return sorted(metadonnees.topics)

    def preparer_topics(self, definitions: list[DefinitionTopic]) -> None:
        existants = set(self.verifier_courtier())
        nouveaux = [
            NewTopic(d.nom, num_partitions=d.partitions, config=d.configuration)
            for d in definitions
            if d.nom not in existants
        ]
        if not nouveaux:
            return
        for nom, avenir in self._admin.create_topics(nouveaux).items():
            try:
                avenir.result()
            except KafkaException as exc:
                erreur = exc.args[0]
                if erreur.code() != KafkaError.TOPIC_ALREADY_EXISTS:
                    raise CourtierInjoignable(f"création du topic {nom} : {_texte(exc)}") from exc

    def produire(self, enveloppe: Enveloppe, rappel: Rappel) -> None:
        def rapport(erreur: KafkaError | None, message: Message) -> None:
            partition, offset = message.partition(), message.offset()
            rappel(
                Livraison(
                    topic=message.topic() or enveloppe.topic,
                    partition=-1 if partition is None else partition,
                    offset=-1 if offset is None else offset,
                    erreur=None if erreur is None else f"{erreur.str()} ({erreur.code()})",
                )
            )

        en_tetes: list[tuple[str, str | bytes | None]] = list(enveloppe.en_tetes)

        while True:
            try:
                self._producteur.produce(
                    enveloppe.topic,
                    value=enveloppe.valeur,
                    key=enveloppe.cle,
                    headers=en_tetes,
                    timestamp=enveloppe.horodatage_ms,
                    on_delivery=rapport,
                )
            except BufferError:
                self._producteur.poll(0.5)  # la file de départ est pleine : laisser partir
                continue
            except KafkaException as exc:
                erreur = exc.args[0]
                if erreur.code() == KafkaError.MSG_SIZE_TOO_LARGE:
                    raise MessageTropGros(
                        f"{len(enveloppe.valeur)} octets : {erreur.str()}"
                    ) from exc
                raise CourtierInjoignable(f"{enveloppe.topic} : {_texte(exc)}") from exc
            break
        self._producteur.poll(0)

    def attendre(self, delai_s: float = DELAI_LIVRAISON_S) -> int:
        return self._producteur.flush(delai_s)

    def supprimer_topics(self, noms: list[str]) -> None:
        """Pour les tests d'intégration : efface leurs topics à suffixe unique."""
        for nom, avenir in self._admin.delete_topics(noms, operation_timeout=30).items():
            try:
                avenir.result()
            except KafkaException as exc:
                if exc.args[0].code() != KafkaError.UNKNOWN_TOPIC_OR_PART:
                    raise CourtierInjoignable(
                        f"suppression du topic {nom} : {_texte(exc)}"
                    ) from exc


def _texte(exc: KafkaException) -> str:
    erreur = exc.args[0] if exc.args else None
    return erreur.str() if isinstance(erreur, KafkaError) else str(exc)
