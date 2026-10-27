"""Publier les fichiers JSONL sur le bus : dans l'ordre, avec reprise, sans jamais réécrire.

Les fichiers de ``<sortie>/evenements/<entite>/*.jsonl`` sont la référence
(mission 02) ; le bus est alimenté à partir d'eux. ``publication.json``, à
côté d'``etat.json``, garde par entité la liste des fichiers publiés avec
leur sha256 et leurs comptes ; il est réécrit entier puis renommé **après**
l'accusé de réception de tous les messages du fichier. ``--reprendre``
publie, dans l'ordre des noms, chaque fichier absent de l'état. Après une
coupure, le fichier en cours est republié en entier : ses messages déjà
acceptés sont alors en double sur le topic, même identifiant, même contenu,
même horodatage ; les consommateurs dédoublonnent par ``id`` (PRD §6.4).

Un fichier publié dont le sha256 a changé (un rejeu complet a recalculé la
sortie autrement) fait **refuser** la publication, sans option pour forcer :
un événement publié n'est jamais réécrit, la voie documentée est de rebâtir
le bus. Une ligne illisible ou un message trop gros vont dans la file des
messages en échec et la publication continue ; un courtier injoignable ou une
livraison en échec l'arrêtent, l'état n'avance pas.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pharmaflux.bus import enveloppe as env
from pharmaflux.bus.client import (
    Bus,
    DefinitionTopic,
    Livraison,
    MessageTropGros,
    definition_echecs,
    definition_evenements,
)
from pharmaflux.bus.enveloppe import Motif
from pharmaflux.bus.registre import Registre, SchemaAbsent, sujet
from pharmaflux.collecte.empreintes import sha256_hex
from pharmaflux.evenements.rejeu import DOSSIER_EVENEMENTS
from pharmaflux.evenements.schema import EvenementInvalide

VERSION_PUBLICATION = 1
NOM_PUBLICATION = "publication.json"
Journal = Callable[[str], None]


class PublicationRefusee(Exception):  # noqa: N818 (nom français voulu)
    """L'état est illisible, absent alors qu'il faut reprendre, ou un fichier publié a changé
    (code de sortie 2) : le message dit quoi faire, rien n'est publié."""


class LivraisonEchouee(Exception):  # noqa: N818 (nom français voulu)
    """Le courtier n'a pas accusé réception d'un message (code 1) : l'état n'avance pas."""


@dataclass(frozen=True, slots=True)
class FichierPublie:
    sha256: str
    messages: int
    echecs: int


@dataclass(slots=True)
class ResumeEntite:
    identifiant: str
    fichiers: int = 0  # publiés par cette exécution
    deja_publies: int = 0
    messages: int = 0
    echecs: int = 0


@dataclass(slots=True)
class Rapport:
    resumes: list[ResumeEntite]
    duree_s: float
    topics: dict[str, int] = field(default_factory=dict)  # messages par topic, cette exécution

    @property
    def code_sortie(self) -> int:
        """3 si la file des échecs a reçu au moins un message : visible, jamais absorbé."""
        return 3 if any(r.echecs for r in self.resumes) else 0


def executer(
    sortie: Path,
    bus: Bus,
    registre: Registre,
    *,
    reprendre: bool = False,
    prefixe: str = env.PREFIXE_PAR_DEFAUT,
    journal: Journal | None = None,
) -> Rapport:
    """Publie les fichiers de ``sortie`` qui ne le sont pas encore ; rend le résumé."""
    dire = journal or (lambda _: None)
    debut = time.monotonic()
    chemin_etat = sortie / NOM_PUBLICATION
    etat = lire_etat(chemin_etat)
    if etat and not reprendre:
        raise PublicationRefusee(
            f"{chemin_etat} existe : relance avec --reprendre pour publier les nouveaux fichiers ;"
            " pour tout republier, rebâtis le bus (docker compose -p pharmaflux down -v) et"
            f" supprime {NOM_PUBLICATION}"
        )
    fichiers = lister_fichiers(sortie)
    _verifier_inchanges(sortie, etat, fichiers)
    a_publier = [
        (entite, chemin) for entite, chemin in fichiers if chemin not in etat.get(entite, {})
    ]
    resumes = {
        entite: ResumeEntite(entite, deja_publies=len(etat.get(entite, {})))
        for entite in sorted({e for e, _ in fichiers} | set(etat))
    }
    if not a_publier:
        dire("rien à publier : tous les fichiers sont dans l'état")
        return Rapport(list(resumes.values()), time.monotonic() - debut)
    entites = sorted({entite for entite, _ in a_publier})
    identifiants = _identifiants_de_schema(registre, entites, prefixe)
    bus.preparer_topics(_definitions(entites, prefixe))
    rapport = Rapport([], 0.0)
    for entite, chemin in a_publier:
        publie = _publier_fichier(
            sortie, chemin, entite, bus, identifiants, prefixe, rapport.topics
        )
        etat.setdefault(entite, {})[chemin] = publie
        ecrire_etat(chemin_etat, etat)
        resume = resumes[entite]
        resume.fichiers += 1
        resume.messages += publie.messages
        resume.echecs += publie.echecs
        dire(
            f"{entite} {Path(chemin).name} : {publie.messages} message(s), {publie.echecs} échec(s)"
        )
    rapport.resumes = list(resumes.values())
    rapport.duree_s = time.monotonic() - debut
    return rapport


def lister_fichiers(sortie: Path) -> list[tuple[str, str]]:
    """(entité, chemin relatif à la sortie) de chaque JSONL, entités puis noms dans l'ordre."""
    dossier = sortie / DOSSIER_EVENEMENTS
    if not dossier.is_dir():
        return []
    fichiers = []
    for entite in sorted(d for d in dossier.iterdir() if d.is_dir()):
        for fichier in sorted(entite.glob("*.jsonl")):
            fichiers.append((entite.name, fichier.relative_to(sortie).as_posix()))
    return fichiers


def _verifier_inchanges(
    sortie: Path, etat: dict[str, dict[str, FichierPublie]], fichiers: list[tuple[str, str]]
) -> None:
    """Chaque fichier de l'état est toujours là, avec le même sha256 ; sinon refus, sans forçage."""
    presents = {chemin for _, chemin in fichiers}
    for entite, publies in sorted(etat.items()):
        for chemin, publie in sorted(publies.items()):
            if chemin not in presents:
                raise PublicationRefusee(
                    f"{entite} : {chemin} est publié mais n'est plus dans la sortie ;"
                    " un événement publié n'est jamais réécrit : rebâtis le bus"
                )
            if sha256_hex((sortie / chemin).read_bytes()) != publie.sha256:
                raise PublicationRefusee(
                    f"{entite} : {chemin} a changé depuis sa publication (sha256 différent) ;"
                    " un événement publié n'est jamais réécrit : rebâtis le bus"
                    " (docker compose -p pharmaflux down -v, puis publication complète)"
                )


def _identifiants_de_schema(registre: Registre, entites: list[str], prefixe: str) -> dict[str, int]:
    """topic → identifiant du schéma enregistré ; refus si un sujet n'en a pas."""
    topics = [env.nom_topic(entite, prefixe) for entite in entites] + [env.topic_echecs(prefixe)]
    identifiants = {}
    for topic in topics:
        try:
            identifiants[topic] = registre.identifiant(sujet(topic))
        except SchemaAbsent as exc:
            raise PublicationRefusee(
                f"aucun schéma enregistré pour {sujet(topic)} : lance"
                " « pharmaflux schemas enregistrer » d'abord"
            ) from exc
    return identifiants


def _definitions(entites: list[str], prefixe: str) -> list[DefinitionTopic]:
    definitions = [definition_evenements(env.nom_topic(entite, prefixe)) for entite in entites]
    definitions.append(definition_echecs(env.topic_echecs(prefixe)))
    return definitions


def _publier_fichier(
    sortie: Path,
    chemin: str,
    entite: str,
    bus: Bus,
    identifiants: dict[str, int],
    prefixe: str,
    par_topic: dict[str, int],
) -> FichierPublie:
    """Toutes les lignes d'un fichier, dans l'ordre, puis l'attente des accusés de réception."""
    topic = env.nom_topic(entite, prefixe)
    echecs_topic = env.topic_echecs(prefixe)
    erreurs: list[str] = []
    comptes: Counter[str] = Counter()

    def livre(livraison: Livraison) -> None:
        if livraison.erreur is not None:
            erreurs.append(f"{livraison.topic} : {livraison.erreur}")

    def en_echec(motif: Motif, detail: str, numero: int, ligne: bytes) -> None:
        message = env.message_echec(
            motif, detail, entite, chemin, numero, ligne, identifiants[echecs_topic], prefixe
        )
        bus.produire(message, livre)
        comptes["echecs"] += 1

    with (sortie / chemin).open("rb") as flux:
        for numero, ligne in _lignes(flux):
            try:
                enveloppe = env.envelopper(ligne, chemin, identifiants[topic], prefixe)
            except EvenementInvalide as exc:
                en_echec(Motif.ILLISIBLE, str(exc), numero, ligne)
                continue
            try:
                bus.produire(enveloppe, livre)
            except MessageTropGros as exc:
                en_echec(Motif.TROP_GROS, str(exc), numero, ligne)
                continue
            comptes["messages"] += 1
    restants = bus.attendre(120)
    if restants:
        erreurs.append(f"{restants} message(s) sans accusé de réception après 120 s")
    if erreurs:
        raise LivraisonEchouee(
            f"{chemin} : {erreurs[0]}" + (f" (+{len(erreurs) - 1})" if len(erreurs) > 1 else "")
        )
    par_topic[topic] = par_topic.get(topic, 0) + comptes["messages"]
    if comptes["echecs"]:
        par_topic[echecs_topic] = par_topic.get(echecs_topic, 0) + comptes["echecs"]
    return FichierPublie(
        sha256_hex((sortie / chemin).read_bytes()), comptes["messages"], comptes["echecs"]
    )


def _lignes(flux: Iterator[bytes]) -> Iterator[tuple[int, bytes]]:
    """(numéro, ligne) des lignes non vides, numérotées comme dans le fichier."""
    for numero, ligne in enumerate(flux, 1):
        if ligne.strip():
            yield numero, ligne


def lire_etat(chemin: Path) -> dict[str, dict[str, FichierPublie]]:
    """L'état de publication : entité → chemin du fichier → ce qui en a été publié."""
    if not chemin.is_file():
        return {}
    conseil = f"supprime {NOM_PUBLICATION} après avoir rebâti le bus, ou choisis une autre sortie"
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
        if brut["version"] != VERSION_PUBLICATION:
            raise PublicationRefusee(
                f"{chemin} : version {brut['version']}, attendu {VERSION_PUBLICATION} : {conseil}"
            )
        return {
            entite: {
                fichier: FichierPublie(p["sha256"], int(p["messages"]), int(p["echecs"]))
                for fichier, p in publies.items()
            }
            for entite, publies in brut["entites"].items()
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise PublicationRefusee(f"{chemin} : état illisible ({exc!r}) : {conseil}") from exc


def ecrire_etat(chemin: Path, etat: dict[str, dict[str, FichierPublie]]) -> None:
    """Réécrit l'état entier sous un nom temporaire, puis le renomme."""
    contenu = {
        "version": VERSION_PUBLICATION,
        "entites": {
            entite: {
                fichier: {"sha256": p.sha256, "messages": p.messages, "echecs": p.echecs}
                for fichier, p in sorted(publies.items())
            }
            for entite, publies in sorted(etat.items())
        },
    }
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.parent / f".{chemin.name}.partiel"
    temporaire.write_text(json.dumps(contenu, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporaire.replace(chemin)
