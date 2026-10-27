"""Regarder le bus en direct : une ligne lisible par événement (``pharmaflux suivre``, mission 04).

Un consommateur minimal pour un second terminal pendant la démo : il
s'assigne lui-même les partitions des topics d'événements (sans groupe actif
ni commit d'offset, comme ``verifier-bus``), part de leur fin (ou de leur
début avec ``depuis_le_debut``), et dit chaque message en une ligne : heure
observée, entité, type, clé, colonnes changées. L'heure est celle de
l'événement (``date_observation``), jamais l'horloge du poste.

``suivre`` regarde, ``verifier-bus`` juge : un message qui n'est pas un
événement v1 (valeur illisible, autre ``version_schema``) va sur la sortie
d'erreur, compté dans le résumé, et la lecture continue ; le code de sortie
reste 0. ``nombre`` arrête après N messages (les tests, la CI) ; sans lui,
``Ctrl-C`` arrête proprement avec le résumé.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from pharmaflux.bus.client import MessageLu
from pharmaflux.evenements import schema
from pharmaflux.evenements.schema import EvenementInvalide, TypeEvenement
from pharmaflux.evenements.snapshot import Identite

LARGEUR_ENTITE = 28
LARGEUR_TYPE = 9  # « supprimee »
Journal = Callable[[str], None]


class Suiveur(Protocol):
    """Ce que ``suivre`` demande au courtier ; simulé dans les tests unitaires."""

    def suivre(self, topics: list[str], *, depuis_le_debut: bool = False) -> Iterator[MessageLu]:
        """Les messages des topics au fil de l'eau, sans fin ; depuis leur fin ou leur début."""


class MessageIllisible(Exception):  # noqa: N818 (nom français voulu)
    """La valeur du message n'est pas un événement v1 : dit sur la sortie d'erreur, compté."""


@dataclass(slots=True)
class Resume:
    lus: int = 0  # tous les messages reçus, illisibles compris
    illisibles: int = 0
    par_topic: Counter[str] = field(default_factory=Counter)
    interrompu: bool = False  # Ctrl-C


def formater(message: MessageLu) -> str:
    """``24/10 23:17:12  bdpm.presentations  supprimee  cip7=3400930000000 cis=60000000``.

    Pour une ``modifiee``, les noms de ``champs_modifies`` suivent la clé ;
    pour une identité ``ligne``, l'empreinte (12 caractères) et le rang
    tiennent lieu de clé. ``MessageIllisible`` si la valeur n'est pas un
    événement v1.
    """
    try:
        evenement = schema.deserialiser(message.valeur.decode("utf-8"))
        instant = datetime.strptime(evenement.date_observation, "%Y-%m-%dT%H:%M:%SZ")
    except (UnicodeDecodeError, EvenementInvalide, ValueError) as exc:
        raise MessageIllisible(str(exc)) from exc
    if evenement.identite is Identite.CLE:
        cle = " ".join(f"{colonne}={valeur}" for colonne, valeur in sorted(evenement.cle.items()))
    else:
        cle = f"empreinte={evenement.empreinte_ligne[:12]} rang={evenement.rang}"
    detail = ""
    if evenement.type is TypeEvenement.MODIFIEE:
        detail = "  → " + ", ".join(evenement.champs_modifies)
    return (
        f"{instant:%d/%m %H:%M:%S}  {evenement.entite:{LARGEUR_ENTITE}} "
        f"{evenement.type.value:{LARGEUR_TYPE}} {cle}{detail}"
    )


def suivre(
    suiveur: Suiveur,
    topics: list[str],
    *,
    depuis_le_debut: bool = False,
    nombre: int | None = None,
    dire: Journal,
    dire_erreur: Journal,
) -> Resume:
    """Affiche les messages des topics au fil de l'eau ; s'arrête après ``nombre`` ou au Ctrl-C."""
    resume = Resume()
    if nombre is not None and nombre <= 0:
        return resume
    try:
        for message in suiveur.suivre(topics, depuis_le_debut=depuis_le_debut):
            resume.lus += 1
            resume.par_topic[message.topic] += 1
            try:
                dire(formater(message))
            except MessageIllisible as exc:
                resume.illisibles += 1
                dire_erreur(
                    f"message illisible {message.topic}/{message.partition}@{message.offset} :"
                    f" {exc}"
                )
            if nombre is not None and resume.lus >= nombre:
                break
    except KeyboardInterrupt:
        resume.interrompu = True
    return resume


def formater_resume(resume: Resume) -> list[str]:
    lignes = [
        f"{resume.lus} message(s) lu(s), {resume.illisibles} illisible(s)"
        + (" ; arrêté au clavier" if resume.interrompu else "")
    ]
    lignes.extend(f"  {topic} : {n} message(s)" for topic, n in sorted(resume.par_topic.items()))
    return lignes
