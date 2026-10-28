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

import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from confluent_kafka import (
    OFFSET_BEGINNING,
    OFFSET_END,
    Consumer,
    KafkaError,
    KafkaException,
    Message,
    Producer,
    TopicPartition,
)
from confluent_kafka.admin import AdminClient
from confluent_kafka.admin._config import ConfigResource  # pas réexporté explicitement
from confluent_kafka.cimpl import NewTopic

from pharmaflux.bus.enveloppe import Enveloppe

COURTIER_PAR_DEFAUT = "127.0.0.1:19092"
VARIABLE_COURTIER = "PHARMAFLUX_COURTIER"
PARTITIONS_EVENEMENTS = 3  # figé par l'ADR 0007 : changer redistribue les clés
PARTITIONS_ECHECS = 1
TAILLE_MAX_MESSAGE = 1_048_576  # octets, la limite par défaut de Redpanda et de Kafka
DELAI_LIVRAISON_S = 120
PROPAGATION_TOPIC_MS = 30_000  # défaut de librdkafka : délai avant « topic inconnu »
PRECHARGEMENT_KO = 8_192  # 8 Mo de messages d'avance par consommateur de verifier-bus
DELAI_COURTIER_S = 5.0
DELAI_SUIVI_S = 1.0  # un poll de « suivre » ; entre deux, un topic attendu peut être apparu

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

    def verifier_courtier(self, delai_s: float = DELAI_COURTIER_S) -> list[str]:
        """Les topics du courtier, ou ``CourtierInjoignable`` s'il ne répond pas dans le délai."""

    def preparer_topics(self, definitions: list[DefinitionTopic]) -> None:
        """Crée les topics manquants avec leur configuration ; ceux qui existent sont gardés."""

    def produire(self, enveloppe: Enveloppe, rappel: Rappel) -> None:
        """Met le message en file de départ ; ``rappel`` reçoit sa livraison, plus tard."""

    def attendre(self, delai_s: float) -> int:
        """Attend les livraisons en attente ; rend le nombre de messages encore non livrés."""


def configuration_producteur(
    courtier: str, propagation_topic_ms: int = PROPAGATION_TOPIC_MS
) -> dict[str, object]:
    return {
        "bootstrap.servers": courtier,
        # Un topic inconnu (la création automatique est coupée, décision 5) fait échouer
        # le message après ce délai, au lieu d'attendre qu'il apparaisse.
        "topic.metadata.propagation.max.ms": propagation_topic_ms,
        "enable.idempotence": True,  # acks=all, réessais, ordre conservé par partition
        "compression.type": "zstd",
        "partitioner": "murmur2_random",
        "message.max.bytes": TAILLE_MAX_MESSAGE,
        "linger.ms": 20,
        "delivery.timeout.ms": DELAI_LIVRAISON_S * 1000,
        "socket.connection.setup.timeout.ms": int(DELAI_COURTIER_S * 1000),
    }


@dataclass(frozen=True, slots=True)
class MessageLu:
    """Un message relu : la valeur à l'octet, les en-têtes, l'horodatage du courtier."""

    topic: str
    partition: int
    offset: int
    cle: bytes
    valeur: bytes
    en_tetes: dict[str, bytes]
    horodatage_ms: int


@dataclass(frozen=True, slots=True)
class EtatTopic:
    """Ce que le courtier dit d'un topic : ses partitions et les clés de configuration vérifiées."""

    nom: str
    partitions: int
    configuration: dict[str, str]


CLES_VERIFIEES = tuple(CONFIG_EVENEMENTS)  # ce que le projet pose à la création (décision 5)


class Lecteur(Protocol):
    """Ce que ``verifier-bus`` demande au courtier ; simulé dans les tests unitaires."""

    def decrire_topic(self, nom: str) -> EtatTopic | None:
        """Partitions et configuration du topic ; None s'il n'existe pas."""

    def lire(self, nom: str) -> Iterator[MessageLu]:
        """Tous les messages depuis le début, partition par partition, jusqu'aux offsets de fin."""


def _lister_topics(admin: AdminClient, courtier: str, delai_s: float) -> list[str]:
    try:
        metadonnees = admin.list_topics(timeout=delai_s)
    except KafkaException as exc:
        raise CourtierInjoignable(f"{courtier} : {_texte(exc)}") from exc
    return sorted(metadonnees.topics)


class BusKafka:
    """Le bus réel : un ``Producer`` et un ``AdminClient`` de confluent-kafka."""

    def __init__(self, courtier: str, *, propagation_topic_ms: int = PROPAGATION_TOPIC_MS) -> None:
        self.courtier = courtier
        self._admin = AdminClient({"bootstrap.servers": courtier})
        self._producteur = Producer(configuration_producteur(courtier, propagation_topic_ms))

    def verifier_courtier(self, delai_s: float = DELAI_COURTIER_S) -> list[str]:
        """Les topics du courtier, ou ``CourtierInjoignable`` s'il ne répond pas dans le délai."""
        return _lister_topics(self._admin, self.courtier, delai_s)

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


class LecteurKafka:
    """Relit les topics depuis le début, sans groupe actif ni commit d'offset (décision 8).

    Le consommateur s'assigne lui-même les partitions du topic et s'arrête,
    pour chacune, à l'offset de fin lu avant de commencer : ce que ``publier``
    écrirait pendant la lecture n'est pas compté, et rien n'est laissé sur le
    courtier. L'ordre est celui de chaque partition, donc de chaque clé.
    ``suivre`` (mission 04) lit au fil de l'eau avec le même consommateur.
    """

    def __init__(self, courtier: str, *, delai_s: float = DELAI_COURTIER_S) -> None:
        self.courtier = courtier
        self.delai_s = delai_s
        self._admin = AdminClient({"bootstrap.servers": courtier})
        self._consommateur = Consumer(
            {
                "bootstrap.servers": courtier,
                "group.id": f"pharmaflux-lecteur-{uuid.uuid4().hex[:8]}",  # jamais commis
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
                # Préchargement borné : 64 Mo par défaut, inutile pour relire et appliquer
                "queued.max.messages.kbytes": PRECHARGEMENT_KO,
            }
        )

    def verifier_courtier(self, delai_s: float = DELAI_COURTIER_S) -> list[str]:
        return _lister_topics(self._admin, self.courtier, delai_s)

    def decrire_topic(self, nom: str) -> EtatTopic | None:
        try:
            metadonnees = self._admin.list_topics(timeout=self.delai_s)
        except KafkaException as exc:
            raise CourtierInjoignable(f"{self.courtier} : {_texte(exc)}") from exc
        topic = metadonnees.topics.get(nom)
        if topic is None or topic.error is not None:
            return None
        (avenir,) = self._admin.describe_configs([ConfigResource("topic", nom)]).values()
        try:
            entrees = avenir.result()
        except KafkaException as exc:
            raise CourtierInjoignable(f"configuration de {nom} : {_texte(exc)}") from exc
        configuration = {cle: str(entrees[cle].value) for cle in CLES_VERIFIEES if cle in entrees}
        return EtatTopic(nom, len(topic.partitions), configuration)

    def lire(self, nom: str) -> Iterator[MessageLu]:
        """Toutes les partitions à la fois, chacune dans l'ordre de ses offsets, jusqu'à sa fin."""
        try:
            metadonnees = self._admin.list_topics(timeout=self.delai_s)
            fins: dict[int, int] = {}
            for partition in sorted(metadonnees.topics[nom].partitions):
                debut, fin = self._consommateur.get_watermark_offsets(
                    TopicPartition(nom, partition), timeout=self.delai_s
                )
                if fin > debut:
                    fins[partition] = fin
            if not fins:
                return
            self._consommateur.assign(
                [TopicPartition(nom, partition, OFFSET_BEGINNING) for partition in fins]
            )
            restantes = dict(fins)
            while restantes:
                message = self._consommateur.poll(self.delai_s)
                if message is None:
                    raise CourtierInjoignable(
                        f"{nom} : rien reçu en {self.delai_s} s, partitions encore attendues"
                        f" {sorted(restantes)}"
                    )
                erreur = message.error()
                if erreur is not None:
                    raise CourtierInjoignable(f"{nom} : {erreur.str()}")
                numero, offset = message.partition(), message.offset()
                assert numero is not None and offset is not None
                if offset >= fins[numero]:
                    continue  # publié pendant la lecture : hors de la photo prise au départ
                if offset + 1 >= fins[numero]:
                    restantes.pop(numero, None)
                yield _message_lu(nom, message, numero, offset)
            self._consommateur.unassign()
        except KafkaException as exc:
            raise CourtierInjoignable(f"lecture de {nom} : {_texte(exc)}") from exc

    def suivre(self, topics: list[str], *, depuis_le_debut: bool = False) -> Iterator[MessageLu]:
        """Les messages des ``topics`` au fil de l'eau, sans fin (``pharmaflux suivre``).

        Toutes les partitions de chaque topic, depuis leur fin (ce qui arrive
        après le départ) ou leur début. Un topic qui n'existe pas encore est
        attendu, et assigné dès qu'il apparaît, depuis son début : tout ce qu'il
        contient est postérieur au départ. C'est le cas d'un bus rebâti où
        ``suivre`` est lancé avant ``demo rejouer``. Sans groupe actif ni commit.
        """
        attendus = set(topics)
        derniere_recherche = -1.0
        depart = OFFSET_BEGINNING if depuis_le_debut else OFFSET_END
        try:
            while True:
                if attendus and time.monotonic() - derniere_recherche >= DELAI_SUIVI_S:
                    derniere_recherche = time.monotonic()
                    metadonnees = self._admin.list_topics(timeout=self.delai_s)
                    for nom in sorted(attendus):
                        topic = metadonnees.topics.get(nom)
                        if topic is None or topic.error is not None:
                            continue
                        self._consommateur.incremental_assign(
                            [TopicPartition(nom, p, depart) for p in sorted(topic.partitions)]
                        )
                        attendus.discard(nom)
                    depart = OFFSET_BEGINNING  # un topic apparu après le départ : tout est neuf
                message = self._consommateur.poll(DELAI_SUIVI_S)
                if message is None:
                    continue
                erreur = message.error()
                if erreur is not None:
                    raise CourtierInjoignable(f"{message.topic()} : {erreur.str()}")
                numero, offset = message.partition(), message.offset()
                assert numero is not None and offset is not None
                yield _message_lu(message.topic() or "", message, numero, offset)
        except KafkaException as exc:
            raise CourtierInjoignable(f"suivi de {', '.join(topics)} : {_texte(exc)}") from exc
        finally:
            self._consommateur.unassign()

    # --- Le consommateur du silver (mission 05, palier 2) ---------------------------------------
    # Lire depuis une position par partition, jusqu'aux offsets de fin lus au départ ; relire un
    # seul message ; les bornes d'un topic ; l'identifiant de grappe. Sans groupe actif, sans
    # commit : la position vit dans le commit Iceberg (ADR 0009).

    def identifiant_grappe(self) -> str | None:
        """L'identifiant de grappe du courtier (``redpanda.<uuid>``), None s'il ne le dit pas."""
        try:
            resultat = self._admin.describe_cluster(request_timeout=self.delai_s).result()
        except KafkaException:
            return None
        identifiant = resultat.cluster_id
        return str(identifiant) if identifiant else None

    def bornes(self, nom: str) -> dict[int, tuple[int, int]]:
        """Partition → (premier offset présent, offset de fin), pour toutes les partitions."""
        try:
            metadonnees = self._admin.list_topics(timeout=self.delai_s)
            topic = metadonnees.topics.get(nom)
            if topic is None or topic.error is not None:
                raise CourtierInjoignable(f"{nom} : topic absent du courtier")
            bornes = {}
            for partition in sorted(topic.partitions):
                debut, fin = self._consommateur.get_watermark_offsets(
                    TopicPartition(nom, partition), timeout=self.delai_s
                )
                bornes[partition] = (debut, fin)
            return bornes
        except KafkaException as exc:
            raise CourtierInjoignable(f"bornes de {nom} : {_texte(exc)}") from exc

    def derniers_messages(
        self, nom: str, offsets: Mapping[int, int]
    ) -> dict[int, MessageLu | None]:
        """Le message de chaque partition à l'offset donné, None s'il n'y est pas (ou plus).

        Un consommateur à part, qui n'attend pas le courtier (``fetch.wait.max.ms``
        court) : relire un message par partition en fin de topic coûtait une
        seconde par partition avec le consommateur de ``lire``.
        """
        bornes = self.bornes(nom)
        resultat: dict[int, MessageLu | None] = {p: None for p in offsets}
        attendus = {
            p: o for p, o in offsets.items() if p in bornes and bornes[p][0] <= o < bornes[p][1]
        }
        if not attendus:
            return resultat
        consommateur = Consumer(
            {
                "bootstrap.servers": self.courtier,
                "group.id": f"pharmaflux-controle-{uuid.uuid4().hex[:8]}",  # jamais commis
                "enable.auto.commit": False,
                "fetch.wait.max.ms": 50,
                "queued.max.messages.kbytes": 1_024,
            }
        )
        try:
            consommateur.assign([TopicPartition(nom, p, o) for p, o in sorted(attendus.items())])
            restants = dict(attendus)
            while restants:
                message = consommateur.poll(self.delai_s)
                if message is None:
                    raise CourtierInjoignable(
                        f"{nom} : rien reçu en {self.delai_s} s pour les offsets {sorted(restants)}"
                    )
                erreur = message.error()
                if erreur is not None:
                    raise CourtierInjoignable(f"{nom} : {erreur.str()}")
                numero, lu = message.partition(), message.offset()
                assert numero is not None and lu is not None
                attendu = restants.get(numero)
                if attendu is None or lu < attendu:
                    continue
                resultat[numero] = _message_lu(nom, message, numero, lu) if lu == attendu else None
                del restants[numero]
        except KafkaException as exc:
            raise CourtierInjoignable(f"lecture de {nom} : {_texte(exc)}") from exc
        finally:
            consommateur.close()
        return resultat

    def lire_depuis(
        self, nom: str, debuts: Mapping[int, int], fins: Mapping[int, int]
    ) -> Iterator[MessageLu]:
        """Les messages de chaque partition depuis ``debuts`` (inclus) jusqu'à ``fins`` (exclus).

        Toutes les partitions à la fois, chacune dans l'ordre de ses offsets ;
        ce qui est publié après le départ n'est pas lu. Une partition dont le
        début atteint la fin n'est pas assignée.
        """
        restantes = {p: fins[p] for p in fins if debuts.get(p, 0) < fins[p]}
        if not restantes:
            return
        try:
            self._consommateur.assign(
                [TopicPartition(nom, p, debuts.get(p, 0)) for p in sorted(restantes)]
            )
            while restantes:
                message = self._consommateur.poll(self.delai_s)
                if message is None:
                    raise CourtierInjoignable(
                        f"{nom} : rien reçu en {self.delai_s} s, partitions encore attendues"
                        f" {sorted(restantes)}"
                    )
                erreur = message.error()
                if erreur is not None:
                    raise CourtierInjoignable(f"{nom} : {erreur.str()}")
                numero, offset = message.partition(), message.offset()
                assert numero is not None and offset is not None
                if numero not in restantes or offset >= restantes[numero]:
                    continue  # publié pendant la lecture : hors de la photo prise au départ
                if offset + 1 >= restantes[numero]:
                    restantes.pop(numero, None)
                yield _message_lu(nom, message, numero, offset)
            self._consommateur.unassign()
        except KafkaException as exc:
            raise CourtierInjoignable(f"lecture de {nom} : {_texte(exc)}") from exc

    def close(self) -> None:
        self._consommateur.close()


def _message_lu(nom: str, message: Message, partition: int, offset: int) -> MessageLu:
    brutes = message.headers() or []
    paires = brutes.items() if isinstance(brutes, dict) else brutes
    return MessageLu(
        topic=nom,
        partition=partition,
        offset=offset,
        cle=message.key() or b"",
        valeur=message.value() or b"",
        en_tetes={c: _octets(v) for c, v in paires},
        horodatage_ms=message.timestamp()[1],
    )


def _octets(valeur: str | bytes | None) -> bytes:
    return valeur if isinstance(valeur, bytes) else (valeur or "").encode()


def _texte(exc: KafkaException) -> str:
    erreur = exc.args[0] if exc.args else None
    return erreur.str() if isinstance(erreur, KafkaError) else str(exc)
