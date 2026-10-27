"""Vérifier le bus : relire, dédoublonner, appliquer, comparer (décisions 5 et 8 de la mission 03).

Pour chaque entité, ``verifier-bus`` relit son topic depuis le début, partition
par partition, sans commit d'offset ; il dédoublonne par ``id`` (le premier
message gagne, les suivants sont comptés avec le fichier qu'ils citent) ;
il applique les événements au vide, réduit l'état obtenu à une empreinte
par identité de ligne, et le compare à une **référence** réduite de même :

- par défaut, les fichiers d'événements de la sortie, appliqués dans l'ordre
  des noms : ce que la CI sait faire avec les fixtures ;
- avec ``--racine``, le dernier snapshot retenu d'après ``etat.json``,
  recalculé depuis l'archive : une référence indépendante des fichiers, pour
  la démonstration sur la copie du Mac.

Il vérifie aussi ce que la décision 5 exige du courtier : rétention sans
limite (``retention.ms`` et ``retention.bytes`` à -1), ``cleanup.policy``
``delete``, et le nombre de partitions figé. Toute différence, d'état ou de
configuration, donne le code de sortie 2 ; un courtier injoignable, 1. Les
doublons sont rapportés, pas comptés comme une différence : après une reprise,
ils sont attendus, et ils viennent tous du fichier republié.

Mémoire : un seul état complet à la fois. Celui du bus est construit puis
réduit à ses empreintes (32 octets par ligne) avant que la référence ne soit
calculée ; ``appliquer`` reçoit des lots, parce qu'il copie l'état à chaque
appel.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pharmaflux.bus import enveloppe as env
from pharmaflux.bus.client import (
    CLES_VERIFIEES,
    DefinitionTopic,
    EtatTopic,
    Lecteur,
    MessageLu,
    definition_echecs,
    definition_evenements,
)
from pharmaflux.contrats.modele import Contrat
from pharmaflux.evenements import rejeu, schema
from pharmaflux.evenements.comparaison import Etat, appliquer, etat_du_snapshot

Journal = Callable[[str], None]
Reference = Callable[[str], Etat]  # entité → l'état attendu
Empreintes = dict[str, bytes]  # identité de ligne → empreinte de (valeurs, occurrences)
LOT_APPLICATION = 5_000  # ``appliquer`` copie l'état à chaque appel : on lui donne des lots
EXEMPLES = 3  # identités citées par différence


@dataclass(frozen=True, slots=True)
class VerificationTopic:
    """Un topic relu et comparé ; ``differences`` vide quand tout est conforme."""

    entite: str  # l'entité, ou « echecs » pour la file
    topic: str
    messages: int
    doublons: int
    doublons_par_fichier: dict[str, int]
    lignes_bus: int
    lignes_reference: int
    configuration: dict[str, str]
    partitions: int
    differences: tuple[str, ...]
    duree_s: float

    @property
    def conforme(self) -> bool:
        return not self.differences


@dataclass(slots=True)
class Rapport:
    reference: str  # ce à quoi le bus a été comparé, lisible
    topics: list[VerificationTopic] = field(default_factory=list)
    duree_s: float = 0.0

    @property
    def code_sortie(self) -> int:
        """2 sur toute différence, d'état ou de configuration ; 0 sinon."""
        return 2 if any(not t.conforme for t in self.topics) else 0

    @property
    def doublons(self) -> int:
        return sum(t.doublons for t in self.topics)


def reference_fichiers(sortie: Path) -> Reference:
    """Le flux de fichiers de la sortie, appliqué au vide (la référence par défaut)."""

    def etat(entite: str) -> Etat:
        return _appliquer_par_lots({}, rejeu.lire_evenements(sortie, entite))

    return etat


def reference_archive(sortie: Path, racine: Path, contrats: dict[str, Contrat]) -> Reference:
    """Le dernier snapshot retenu (``etat.json``), recalculé depuis l'archive (``--racine``)."""

    def etat(entite: str) -> Etat:
        snapshot = rejeu.dernier_retenu(racine, sortie, contrats[entite])
        return {} if snapshot is None else etat_du_snapshot(snapshot)

    return etat


def verifier(
    lecteur: Lecteur,
    entites: Iterable[str],
    reference: Reference,
    *,
    description_reference: str,
    prefixe: str = env.PREFIXE_PAR_DEFAUT,
    journal: Journal | None = None,
) -> Rapport:
    """Chaque entité, dans l'ordre donné, puis la file des échecs (configuration et compte)."""
    dire = journal or (lambda _: None)
    depart = time.monotonic()
    rapport = Rapport(description_reference)
    for entite in entites:
        definition = definition_evenements(env.nom_topic(entite, prefixe))
        dire(f"{definition.nom} : relecture")
        rapport.topics.append(_verifier_topic(lecteur, entite, definition, reference))
    definition = definition_echecs(env.topic_echecs(prefixe))
    rapport.topics.append(_verifier_topic(lecteur, "echecs", definition, None))
    rapport.duree_s = time.monotonic() - depart
    return rapport


def _verifier_topic(
    lecteur: Lecteur, entite: str, definition: DefinitionTopic, reference: Reference | None
) -> VerificationTopic:
    """``reference`` None : la file des échecs, comptée et vérifiée, sans état à comparer."""
    depart = time.monotonic()
    description = lecteur.decrire_topic(definition.nom)
    differences: list[str] = []
    messages = doublons = 0
    par_fichier: Counter[str] = Counter()
    bus: Empreintes = {}
    attendu: Empreintes = {}
    configuration: dict[str, str] = {}
    partitions = 0
    if description is None:
        differences.append("topic absent du courtier")
    else:
        configuration, partitions = description.configuration, description.partitions
        differences.extend(_ecarts_configuration(description, definition))
        if reference is None:
            messages = sum(1 for _ in lecteur.lire(definition.nom))
        else:
            try:
                etat_bus, messages, doublons, par_fichier = _rejouer(lecteur.lire(definition.nom))
            except ValueError as exc:
                differences.append(f"flux incohérent : {exc}")
            else:
                bus = _empreintes(etat_bus)
                del etat_bus  # un seul état complet à la fois : la référence vient après
    if reference is not None:
        attendu = _empreintes(reference(entite))
        if not differences:
            differences.extend(_comparer(bus, attendu))
    return VerificationTopic(
        entite=entite,
        topic=definition.nom,
        messages=messages,
        doublons=doublons,
        doublons_par_fichier=dict(sorted(par_fichier.items())),
        lignes_bus=len(bus),
        lignes_reference=len(attendu),
        configuration=configuration,
        partitions=partitions,
        differences=tuple(differences),
        duree_s=time.monotonic() - depart,
    )


def _ecarts_configuration(description: EtatTopic, definition: DefinitionTopic) -> list[str]:
    """Rétention et politique telles que le projet les pose (décision 5), partitions figées."""
    ecarts = []
    for cle in CLES_VERIFIEES:
        attendue = definition.configuration[cle]
        lue = description.configuration.get(cle)
        if lue != attendue:
            ecarts.append(
                f"configuration : {cle}={lue if lue is not None else 'absent'} (attendu {attendue})"
            )
    if description.partitions != definition.partitions:
        ecarts.append(f"partitions : {description.partitions} (attendu {definition.partitions})")
    return ecarts


def _rejouer(messages: Iterator[MessageLu]) -> tuple[Etat, int, int, Counter[str]]:
    """Applique les messages au vide ; ``ValueError`` si le flux est incohérent."""
    vus: set[str] = set()
    etat: Etat = {}
    lot: list[schema.Evenement] = []
    total = doublons = 0
    par_fichier: Counter[str] = Counter()
    for message in messages:
        total += 1
        evenement = schema.deserialiser(message.valeur.decode("utf-8"))
        if evenement.id in vus:
            doublons += 1
            par_fichier[message.en_tetes.get("fichier", b"?").decode("utf-8", "replace")] += 1
            continue
        vus.add(evenement.id)
        lot.append(evenement)
        if len(lot) >= LOT_APPLICATION:
            etat = appliquer(etat, lot)
            lot = []
    etat = appliquer(etat, lot)
    return etat, total, doublons, par_fichier


def _appliquer_par_lots(etat: Etat, evenements: Iterable[schema.Evenement]) -> Etat:
    lot: list[schema.Evenement] = []
    for evenement in evenements:
        lot.append(evenement)
        if len(lot) >= LOT_APPLICATION:
            etat = appliquer(etat, lot)
            lot = []
    return appliquer(etat, lot)


def _empreintes(etat: Etat) -> Empreintes:
    """Chaque ligne réduite à 32 octets : (colonnes triées, valeurs, occurrences) hachés."""
    empreintes = {}
    for identite, (valeurs, occurrences) in etat.items():
        contenu = json.dumps([sorted(valeurs.items()), occurrences], ensure_ascii=False)
        empreintes[identite] = hashlib.sha256(contenu.encode("utf-8")).digest()
    return empreintes


def _comparer(bus: Empreintes, attendu: Empreintes) -> list[str]:
    """Les différences entre l'état du bus et la référence, avec quelques identités citées."""
    differences = []
    seulement_bus = sorted(bus.keys() - attendu.keys())
    seulement_reference = sorted(attendu.keys() - bus.keys())
    autres = sorted(k for k in bus.keys() & attendu.keys() if bus[k] != attendu[k])
    for libelle, identites in (
        ("seulement sur le bus", seulement_bus),
        ("seulement dans la référence", seulement_reference),
        ("valeurs ou occurrences différentes", autres),
    ):
        if identites:
            exemples = ", ".join(identites[:EXEMPLES]) + (" …" if len(identites) > EXEMPLES else "")
            differences.append(f"{len(identites)} identité(s) {libelle} : {exemples}")
    return differences
