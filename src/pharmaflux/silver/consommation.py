"""Le consommateur du bus : du topic d'une entité à sa table du silver (D et H, décision 3).

Chaque topic est lu depuis la **position** gardée dans les propriétés de sa
table (``pharmaflux.positions`` : par partition, l'offset suivant à lire et
l'``id`` du dernier message appliqué), toutes les partitions à la fois,
chacune dans l'ordre de ses offsets, jusqu'aux offsets de fin lus au départ.
Les messages sont appliqués par lots (``appliquer_lot``, la même fonction que
pour les fichiers) ; la position avance **dans le commit du lot**, et le
résumé des snapshots porte la plage d'offsets appliquée. Il n'y a donc
aucune fenêtre entre le silver et sa position : après une coupure à
n'importe quel point, la reprise relit le lot interrompu, et les doublons
(républication après une coupure du publieur) sont reconnus à leur ``id``.
Aucun groupe de consommateurs, aucun commit sur le courtier, rien n'est
écrit sur le bus.

Refus (``SilverRefuse``, code 2, avant toute écriture) : un silver construit
depuis les fichiers (il n'a pas de position) ; une position au-delà de la fin
d'une partition ou en deçà de son début ; un message à ``offset - 1`` qui ne
porte pas l'``id`` gardé (le bus n'est pas celui qui a construit le silver) ;
une autre version de contrat ; aucun topic de la sélection sur le courtier
(``make demo`` d'abord). Un identifiant de grappe différent de celui gardé
à la création donne un **avertissement**, pas un refus : un bus rebâti à
l'identique passe le contrôle des ``id``, et le silver est juste. Un message
qui n'est pas un événement v1 lisible arrête tout (``FluxIncoherent``) : rien
de son lot n'est écrit, la position ne bouge pas, et il n'est jamais sauté.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pyiceberg.table import Table

from pharmaflux.bus import enveloppe as env
from pharmaflux.bus.client import EtatTopic, MessageLu
from pharmaflux.contrats.modele import Contrat
from pharmaflux.evenements import schema
from pharmaflux.evenements.schema import Evenement, EvenementInvalide
from pharmaflux.silver import LOT_PAR_DEFAUT, FluxIncoherent, SilverRefuse
from pharmaflux.silver.application import appliquer_lot
from pharmaflux.silver.entrepot import (
    ORIGINE_BUS,
    PROP_GRAPPE,
    PROP_ORIGINE,
    PROP_POSITIONS,
    Entrepot,
    verifier_contrat,
)

Journal = Callable[[str], None]
PROP_OFFSETS = "pharmaflux.offsets"  # résumé d'un snapshot : partition → [premier, dernier]


class LecteurSilver(Protocol):
    """Ce que le consommateur demande au courtier ; simulé dans les tests unitaires."""

    def identifiant_grappe(self) -> str | None:
        """L'identifiant de grappe, None s'il n'est pas connu."""

    def decrire_topic(self, nom: str) -> EtatTopic | None:
        """Partitions et configuration du topic ; None s'il n'existe pas."""

    def bornes(self, nom: str) -> dict[int, tuple[int, int]]:
        """Partition → (premier offset présent, offset de fin)."""

    def derniers_messages(
        self, nom: str, offsets: Mapping[int, int]
    ) -> dict[int, MessageLu | None]:
        """Partition → le message à l'offset donné, None s'il n'y est pas."""

    def lire_depuis(
        self, nom: str, debuts: Mapping[int, int], fins: Mapping[int, int]
    ) -> Iterator[MessageLu]:
        """Les messages depuis ``debuts`` (inclus) jusqu'à ``fins`` (exclus), par partition."""


@dataclass(frozen=True, slots=True)
class Position:
    suivant: int  # le prochain offset à lire
    dernier_id: str | None  # l'id du dernier message appliqué (offset suivant - 1)


def lire_positions(table: Table) -> dict[int, Position]:
    brut = table.properties.get(PROP_POSITIONS)
    if not brut:
        return {}
    try:
        charge = json.loads(brut)
        return {int(p): Position(int(v["suivant"]), v.get("dernier_id")) for p, v in charge.items()}
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SilverRefuse(f"{table.name()} : positions illisibles ({brut!r}) : {exc}") from exc


def ecrire_positions(positions: Mapping[int, Position]) -> str:
    return json.dumps(
        {
            str(p): {"suivant": v.suivant, "dernier_id": v.dernier_id}
            for p, v in sorted(positions.items())
        },
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(slots=True)
class ResumeEntite:
    identifiant: str
    topic: str
    messages: int = 0
    doublons: int = 0
    ouvertures: int = 0
    fermetures: int = 0
    commits: int = 0
    positions: dict[int, Position] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)  # topic absent, rien de nouveau


@dataclass(slots=True)
class Rapport:
    entrepot: Path
    grappe: str | None
    resumes: list[ResumeEntite] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)
    duree_s: float = 0.0

    @property
    def messages(self) -> int:
        return sum(r.messages for r in self.resumes)


def consommer(
    lecteur: LecteurSilver,
    dossier: Path,
    contrats: dict[str, Contrat],
    selection: list[str],
    *,
    lot: int = LOT_PAR_DEFAUT,
    prefixe: str = env.PREFIXE_PAR_DEFAUT,
    journal: Journal | None = None,
) -> Rapport:
    """Les topics de ``selection`` appliqués au silver de ``dossier`` (créé s'il n'existe pas)."""
    dire = journal or (lambda _: None)
    if lot < 1:
        raise SilverRefuse(f"--lot {lot} : au moins 1")
    depart = time.monotonic()
    topics = {identifiant: env.nom_topic(identifiant, prefixe) for identifiant in selection}
    presents = {i: t for i, t in topics.items() if lecteur.decrire_topic(t) is not None}
    if not presents:
        raise SilverRefuse(
            "aucun topic de la sélection sur le courtier : le bus est vide (make demo d'abord)"
        )
    entrepot = Entrepot.ouvrir_ou_creer(dossier)
    grappe = lecteur.identifiant_grappe()
    rapport = Rapport(dossier, grappe)
    for identifiant in selection:
        topic = topics[identifiant]
        resume = ResumeEntite(identifiant, topic)
        rapport.resumes.append(resume)
        if identifiant not in presents:
            resume.notes.append("topic absent du courtier")
            dire(f"{identifiant} : {topic} absent du courtier")
            continue
        table = _table(entrepot, contrats[identifiant], grappe, rapport)
        positions = lire_positions(table)
        bornes = lecteur.bornes(topic)
        _controler_positions(lecteur, topic, positions, bornes)
        fins = {p: fin for p, (_, fin) in bornes.items()}
        debuts = {p: positions.get(p, Position(0, None)).suivant for p in bornes}
        a_lire = sum(fins[p] - debuts[p] for p in bornes)
        dire(f"{identifiant} : {topic}, {a_lire} message(s) à lire, lots de {lot}")
        if not a_lire:
            resume.notes.append("rien de nouveau")
        for evenements, plages in _lots(lecteur, topic, identifiant, debuts, fins, lot):
            suivantes = dict(positions)
            for partition, (_, dernier, dernier_id) in plages.items():
                suivantes[partition] = Position(dernier + 1, dernier_id)
            table, resultat = appliquer_lot(
                table,
                evenements,
                proprietes_table={PROP_POSITIONS: ecrire_positions(suivantes)},
                proprietes_snapshot={
                    PROP_OFFSETS: json.dumps(
                        {
                            str(p): [premier, dernier]
                            for p, (premier, dernier, _) in sorted(plages.items())
                        },
                        separators=(",", ":"),
                    )
                },
                origine=f"{topic} offsets {_texte_plages(plages)}",
            )
            positions = suivantes
            resume.messages += resultat.evenements
            resume.doublons += resultat.doublons
            resume.ouvertures += resultat.ouvertures
            resume.fermetures += resultat.fermetures
            resume.commits += int(resultat.commit)
            dire(
                f"{identifiant} : lot de {resultat.evenements} ({_texte_plages(plages)}) :"
                f" {resultat.ouvertures} ouverture(s), {resultat.fermetures} fermeture(s),"
                f" {resultat.doublons} doublon(s)"
            )
        resume.positions = positions
    rapport.duree_s = time.monotonic() - depart
    return rapport


def _table(entrepot: Entrepot, contrat: Contrat, grappe: str | None, rapport: Rapport) -> Table:
    """La table de l'entité : créée (origine ``bus``, grappe gardée) ou contrôlée."""
    table = entrepot.table(contrat.identifiant)
    if table is None:
        proprietes = {PROP_GRAPPE: grappe} if grappe else {}
        return entrepot.creer_table(contrat, ORIGINE_BUS, proprietes)
    origine = table.properties.get(PROP_ORIGINE)
    if origine != ORIGINE_BUS:
        raise SilverRefuse(
            f"{contrat.identifiant} : silver construit depuis les {origine} : il n'a pas de"
            " position de bus ; choisis un autre --entrepot"
        )
    verifier_contrat(table, contrat)
    connue = table.properties.get(PROP_GRAPPE)
    if grappe and connue and grappe != connue:
        rapport.avertissements.append(
            f"{contrat.identifiant} : la table a été construite sur la grappe {connue}, le"
            f" courtier est {grappe} ; le contrôle des identifiants décide"
        )
    return table


def _controler_positions(
    lecteur: LecteurSilver,
    topic: str,
    positions: Mapping[int, Position],
    bornes: Mapping[int, tuple[int, int]],
) -> None:
    """La position de chaque partition est dans ses bornes, et le dernier message appliqué est
    bien là : sinon le bus n'est pas celui qui a construit le silver."""
    a_relire = {p: v.suivant - 1 for p, v in positions.items() if v.suivant > 0 and v.dernier_id}
    messages = lecteur.derniers_messages(topic, a_relire) if a_relire else {}
    for partition, position in sorted(positions.items()):
        if partition not in bornes:
            raise SilverRefuse(f"{topic} : la partition {partition} n'existe plus sur le courtier")
        debut, fin = bornes[partition]
        if position.suivant > fin:
            raise SilverRefuse(
                f"{topic} partition {partition} : position {position.suivant} au-delà de la fin"
                f" {fin} : le bus a été rebâti après le silver ; rebâtis le silver"
            )
        if position.suivant < debut:
            raise SilverRefuse(
                f"{topic} partition {partition} : position {position.suivant} avant le premier"
                f" offset {debut} : le bus a perdu des messages ; rebâtis le silver"
            )
        if partition in a_relire:
            message = messages.get(partition)
            lu = None if message is None else _identifiant(message)
            if lu != position.dernier_id:
                raise SilverRefuse(
                    f"{topic} partition {partition} : le message {position.suivant - 1} porte"
                    f" l'identifiant {lu}, le silver attend {position.dernier_id} : le bus n'est"
                    " pas celui qui a construit le silver ; rebâtis le silver"
                )


def _identifiant(message: MessageLu) -> str | None:
    """L'``id`` de l'événement : l'en-tête, sinon la valeur."""
    en_tete = message.en_tetes.get("id")
    if en_tete:
        return en_tete.decode("utf-8", "replace")
    try:
        return schema.deserialiser(message.valeur.decode("utf-8")).id
    except (UnicodeDecodeError, EvenementInvalide):
        return None


# partition → (premier offset du lot, dernier offset du lot, id du dernier message)
Plages = dict[int, tuple[int, int, str]]


def _lots(
    lecteur: LecteurSilver,
    topic: str,
    entite: str,
    debuts: Mapping[int, int],
    fins: Mapping[int, int],
    taille: int,
) -> Iterator[tuple[list[Evenement], Plages]]:
    """Les messages lus, désérialisés et groupés par lots d'au plus ``taille``."""
    evenements: list[Evenement] = []
    plages: Plages = {}
    for message in lecteur.lire_depuis(topic, debuts, fins):
        evenement = _evenement(message, entite)
        evenements.append(evenement)
        premier = plages[message.partition][0] if message.partition in plages else message.offset
        plages[message.partition] = (premier, message.offset, evenement.id)
        if len(evenements) >= taille:
            yield evenements, plages
            evenements, plages = [], {}
    if evenements:
        yield evenements, plages


def _evenement(message: MessageLu, entite: str) -> Evenement:
    ou = f"{message.topic} partition {message.partition} offset {message.offset}"
    try:
        evenement = schema.deserialiser(message.valeur.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise FluxIncoherent(
            f"{ou} : valeur illisible en UTF-8 ({exc}) ; rien n'est écrit"
        ) from exc
    except EvenementInvalide as exc:
        apercu = message.valeur[:80].decode("utf-8", "replace")
        raise FluxIncoherent(
            f"{ou} : pas un événement v1 ({exc}) : {apercu!r} ; rien du lot n'est écrit, la"
            " position ne bouge pas ; rebâtis le bus depuis les fichiers"
        ) from exc
    if evenement.entite != entite:
        raise FluxIncoherent(
            f"{ou} : l'événement {evenement.id} dit l'entité {evenement.entite}, le topic porte"
            f" {entite} ; rien du lot n'est écrit"
        )
    return evenement


def _texte_plages(plages: Plages) -> str:
    return ", ".join(
        f"p{p} {premier}-{dernier}" for p, (premier, dernier, _) in sorted(plages.items())
    )
