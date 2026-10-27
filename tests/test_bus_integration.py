"""Mission 03, décisions 4 et 6 : la publication contre le Redpanda local (intégration).

Marqués ``integration`` : sautés, et dit, quand aucun courtier ne répond sur
``PHARMAFLUX_COURTIER`` (défaut ``127.0.0.1:19092``, celui de
``docker compose -p pharmaflux up -d``). Les topics et les sujets du registre
portent un suffixe unique par test et sont supprimés à la fin. Seules les
fixtures sont lues, jamais ``~/pharmaflux-data``, pour que la CI ait le même
jeu que le Mac.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from confluent_kafka import Consumer, TopicPartition

from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import publication
from pharmaflux.bus.client import (
    COURTIER_PAR_DEFAUT,
    VARIABLE_COURTIER,
    BusKafka,
    CourtierInjoignable,
    Livraison,
)
from pharmaflux.bus.registre import (
    REGISTRE_PAR_DEFAUT,
    VARIABLE_REGISTRE,
    Registre,
    enregistrer_tout,
    sujets_du_projet,
)
from pharmaflux.bus.registre import sujet as sujet_de
from pharmaflux.evenements import schema
from pharmaflux.evenements.comparaison import appliquer, etat_du_snapshot
from tests.test_bus import DISPO, PRESENTATIONS, _snap, _sortie

pytestmark = pytest.mark.integration

COURTIER = os.environ.get(VARIABLE_COURTIER, COURTIER_PAR_DEFAUT)
REGISTRE = os.environ.get(VARIABLE_REGISTRE, REGISTRE_PAR_DEFAUT)


@pytest.fixture(scope="session")
def bus() -> Iterator[BusKafka]:
    """Le courtier, ou le saut de tous les tests d'intégration avec le motif."""
    bus_ = BusKafka(COURTIER)
    try:
        bus_.verifier_courtier(delai_s=5)
    except CourtierInjoignable as exc:
        pytest.skip(f"aucun courtier sur {COURTIER} (docker compose -p pharmaflux up -d) : {exc}")
    yield bus_
    bus_.attendre(10)


@pytest.fixture
def prefixe() -> str:
    """Un préfixe par test : chaque test relit des topics qu'il est seul à remplir."""
    return f"pharmaflux.test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def registre(bus: BusKafka, prefixe: str) -> Iterator[Registre]:
    """Les schémas enregistrés sous les sujets du test ; sujets et topics effacés à la fin."""
    registre_ = Registre(REGISTRE)
    sujets = [s for s, _ in sujets_du_projet([PRESENTATIONS, DISPO], prefixe)]
    enregistrer_tout(registre_, [PRESENTATIONS, DISPO], prefixe)
    yield registre_
    for sujet_ in sujets:
        registre_.supprimer(sujet_)
    registre_.close()
    topics = [
        env.nom_topic(PRESENTATIONS, prefixe),
        env.nom_topic(DISPO, prefixe),
        env.topic_echecs(prefixe),
    ]
    bus.supprimer_topics(topics)


def _relire(topic: str) -> list[dict[str, object]]:
    """Tous les messages du topic depuis le début, partition par partition, sans commit."""
    consommateur = Consumer(
        {
            "bootstrap.servers": COURTIER,
            "group.id": f"pharmaflux-test-{uuid.uuid4().hex[:8]}",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    try:
        metadonnees = consommateur.list_topics(topic, timeout=10)
        partitions = sorted(metadonnees.topics[topic].partitions)
        messages = []
        for partition in partitions:
            tp = TopicPartition(topic, partition)
            _, fin = consommateur.get_watermark_offsets(tp, timeout=10)
            consommateur.assign([TopicPartition(topic, partition, 0)])
            position = 0
            while position < fin:
                message = consommateur.poll(10.0)
                assert message is not None and message.error() is None, (partition, position)
                position = (message.offset() or 0) + 1
                en_tetes = dict(message.headers() or [])
                messages.append(
                    {
                        "partition": partition,
                        "offset": message.offset(),
                        "cle": message.key(),
                        "valeur": message.value(),
                        "en_tetes": {k: v for k, v in en_tetes.items()},
                        "horodatage": message.timestamp(),
                    }
                )
            consommateur.unassign()
        return messages
    finally:
        consommateur.close()


def test_publication_complete_sur_le_courtier(
    bus: BusKafka, registre: Registre, prefixe: str, tmp_path: Path
) -> None:
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    rapport = publication.executer(sortie, bus, registre, prefixe=prefixe)
    assert rapport.code_sortie == 0
    assert rapport.topics == {
        env.nom_topic(DISPO, prefixe): n_dispo,
        env.nom_topic(PRESENTATIONS, prefixe): n_pres,
    }
    messages = _relire(env.nom_topic(PRESENTATIONS, prefixe))
    assert len(messages) == n_pres
    # La valeur est la ligne du fichier à l'octet ; les en-têtes disent d'où elle vient.
    lignes = {
        ligne
        for fichier in sorted((sortie / "evenements" / PRESENTATIONS).glob("*.jsonl"))
        for ligne in fichier.read_bytes().splitlines()
    }
    assert {m["valeur"] for m in messages} == lignes
    identifiants = [m["en_tetes"]["id"] for m in messages]
    assert len(set(identifiants)) == n_pres, "aucun doublon après une publication propre"
    assert {m["en_tetes"]["schema_id"] for m in messages} == {
        str(registre.identifiant(sujet_de(env.nom_topic(PRESENTATIONS, prefixe)))).encode()
    }
    # Trois partitions, la clé est l'objet JSON cle, le même médicament toujours sur la même.
    assert {m["partition"] for m in messages} == {0, 1, 2}
    par_cle: dict[bytes, set[int]] = {}
    for m in messages:
        assert isinstance(m["cle"], bytes) and json.loads(m["cle"])
        par_cle.setdefault(m["cle"], set()).add(int(m["partition"]))  # type: ignore[arg-type]
    assert all(len(partitions) == 1 for partitions in par_cle.values())
    # L'horodatage est date_observation, pas l'horloge.
    for m in messages:
        e = schema.deserialiser(m["valeur"].decode())  # type: ignore[union-attr]
        assert m["horodatage"] == (
            1,
            env.horodatage_ms(e.date_observation),
        )  # TIMESTAMP_CREATE_TIME
    # Dans l'ordre du topic, partition après partition, appliquer redonne le dernier snapshot.
    evenements = [schema.deserialiser(m["valeur"].decode()) for m in messages]  # type: ignore[union-attr]
    b = _snap(PRESENTATIONS, "presentations_b.txt", "1517")
    assert appliquer({}, evenements) == etat_du_snapshot(b)
    assert _relire(env.topic_echecs(prefixe)) == []


def test_un_message_impubliable_va_dans_la_file_et_la_suite_est_publiee(
    bus: BusKafka, registre: Registre, prefixe: str, tmp_path: Path
) -> None:
    sortie, _, n_dispo = _sortie(tmp_path)
    fichier = sortie / "evenements" / DISPO / "20261024T141700Z__cccccccccccc.jsonl"
    lignes = fichier.read_bytes().splitlines(keepends=True)
    enorme = lignes[1][:-1] + b" " * (2 * 1024 * 1024) + b"\n"  # 2 Mo : le courtier refuserait
    lignes[1] = enorme
    lignes[3] = b"{cassee\n"
    fichier.write_bytes(b"".join(lignes))
    rapport = publication.executer(sortie, bus, registre, prefixe=prefixe)
    assert rapport.code_sortie == 3
    echecs = _relire(env.topic_echecs(prefixe))
    contenus = sorted((json.loads(m["valeur"]) for m in echecs), key=lambda c: c["ligne"])  # type: ignore[arg-type]
    assert [(c["motif"], c["ligne"], c["tronquee"]) for c in contenus] == [
        ("trop_gros", 2, True),
        ("illisible", 4, False),
    ]
    assert contenus[0]["taille"] == len(enorme) - 1 and contenus[0]["id"]
    assert all(m["horodatage"][0] == 2 for m in echecs), (
        "LogAppendTime sur la file"
    )  # TIMESTAMP_LOG_APPEND_TIME
    assert len(_relire(env.nom_topic(DISPO, prefixe))) == n_dispo - 2, "la suite est publiée"


@pytest.mark.usefixtures("bus")
def test_un_produce_vers_un_topic_non_prepare_echoue_sans_le_creer(prefixe: str) -> None:
    """Décision 5 : la création automatique est coupée, la rétention vient toujours du projet."""
    bus = BusKafka(COURTIER, propagation_topic_ms=2_000)  # 30 s par défaut, trop pour un test
    topic = env.nom_topic("bdpm.inconnu", prefixe)
    livraisons: list[Livraison] = []
    enveloppe = env.Enveloppe(topic=topic, cle=b"cle", valeur=b"{}", en_tetes=[], horodatage_ms=0)
    bus.produire(enveloppe, livraisons.append)
    assert bus.attendre(30) == 0, "le message est tranché, pas en attente"
    assert [x.erreur for x in livraisons] == ["Broker: Unknown topic or partition (3)"]
    assert topic not in bus.verifier_courtier(), "le courtier n'a créé aucun topic"
