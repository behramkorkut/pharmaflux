"""L'évaluation de l'assistant sur le jeu v1 (décision 4) : préparer, chiffrer, appeler, noter.

1. **Les préconditions** (addendum 1 E1) : le jeu est une v1 ; l'index est à l'instant que le jeu
   déclare, et il n'est pas réduit. Sinon, rien ne part.
2. **Préparer** toutes les questions sans rien appeler (``chemin.preparer``) : les décisions des
   règles et des portes, et les appels à faire. Le dictionnaire du repérage est chargé une fois.
3. **La porte budgétaire, avant le premier appel** (addendum 1 G2) : la somme des estimations des
   appels qui ne sont pas au cache (entrée au caractère, ``max_tokens`` entier en sortie). Si le
   total déjà dépensé plus cette somme dépasse le plafond, rien ne part : aucune évaluation ne
   s'arrête au milieu faute de budget.
4. **Conclure** chaque appel (cache, appel, journal, contrôle), puis **noter** chaque question
   (``notation``). Une erreur de l'API arrête l'évaluation (code 2) ; les réponses déjà obtenues
   sont au cache, et une reprise ne les repaie pas.

``estimer`` s'arrête après l'étape 3 : il chiffre l'évaluation sans clé et sans appel.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pharmaflux.assistant import chemin, notation
from pharmaflux.assistant.budget import PLAFOND, BudgetDepasse, Journal
from pharmaflux.assistant.cache import CacheReponses
from pharmaflux.assistant.client import EFFORT_DEFAUT, ClientLLM
from pharmaflux.evaluation.questions import Jeu, Question
from pharmaflux.index import construction
from pharmaflux.index.encodeur import Encodeur
from pharmaflux.index.qdrant import Qdrant


class EvaluationRefusee(Exception):  # noqa: N818 (nom français voulu)
    """Une précondition de l'évaluation manque (jeu, instant de l'index, index réduit)."""


Prepare = tuple[Question, chemin.Reponse | chemin.Appel]


@dataclass(frozen=True, slots=True)
class Estimation:
    """Ce que l'évaluation coûtera, chiffré avant le premier appel."""

    questions: int
    hors_llm: int  # décidées par les règles ou les portes, sans LLM
    en_cache: int  # le LLM a déjà répondu sur ce même index : relues, sans coût
    a_appeler: int
    estimation: float  # prudente : entrée au caractère, max_tokens entier en sortie
    deja: float  # déjà dépensé pour la mission (journal)
    cout_moyen_constate: float | None  # moyenne des appels déjà journalisés

    @property
    def reste(self) -> float:
        return PLAFOND - self.deja

    @property
    def accordee(self) -> bool:
        return self.deja + self.estimation <= PLAFOND

    @property
    def probable(self) -> float | None:
        """Le coût probable, au coût moyen des appels déjà payés (rien si aucun ne l'a été)."""
        if self.cout_moyen_constate is None:
            return None
        return self.a_appeler * self.cout_moyen_constate


def verifier_preconditions(jeu: Jeu, etat: dict[str, Any]) -> None:
    """Le jeu est une v1, l'index est à son instant et complet (addendum 1 E1)."""
    if jeu.version != "v1" or jeu.instant is None:
        raise EvaluationRefusee(f"le jeu est une {jeu.version} : l'assistant se note sur la v1")
    if etat["instant"] != jeu.instant:
        raise EvaluationRefusee(
            f"l'index est à l'instant {etat['instant']}, le jeu attend {jeu.instant} : relancer"
            " la séquence du jeu de démo jusqu'à « make index »"
        )
    if etat.get("cis_reduits"):
        raise EvaluationRefusee(
            f"l'index est réduit à {len(etat['cis_reduits'])} CIS : l'évaluation demande l'index"
            " entier"
        )


def preparer_jeu(
    qdrant: Qdrant, encodeur: Encodeur, jeu: Jeu, *, effort: str = EFFORT_DEFAUT
) -> list[Prepare]:
    """Chaque question jusqu'au seuil du LLM, sans rien appeler ni dépenser."""
    etat = construction.etat_exige(qdrant)
    construction.encodeur_de_l_index(etat, encodeur)
    verifier_preconditions(jeu, etat)
    dictionnaire = chemin.charger_dictionnaire(qdrant)
    return [
        (
            question,
            chemin.preparer(
                qdrant,
                encodeur,
                question.question,
                identifiant=question.id,
                effort=effort,
                dictionnaire=dictionnaire,
            ),
        )
        for question in jeu.questions
    ]


def estimer(prepares: Sequence[Prepare], journal: Journal, cache: CacheReponses) -> Estimation:
    """La porte budgétaire de l'évaluation entière, chiffrée avant tout appel (addendum 1 G2)."""
    appels = [p for _, p in prepares if isinstance(p, chemin.Appel)]
    a_appeler = [a for a in appels if cache.lire(a.cle) is None]
    payes = journal.lignes()
    return Estimation(
        questions=len(prepares),
        hors_llm=len(prepares) - len(appels),
        en_cache=len(appels) - len(a_appeler),
        a_appeler=len(a_appeler),
        estimation=sum(a.estimation for a in a_appeler),
        deja=journal.total(),
        cout_moyen_constate=(sum(x.cout for x in payes) / len(payes)) if payes else None,
    )


def evaluer(
    prepares: Sequence[Prepare],
    estimation: Estimation,
    client: Callable[[], ClientLLM],
    journal: Journal,
    cache: CacheReponses,
    au_fil: Callable[[notation.Note, chemin.Reponse], None] | None = None,
) -> list[notation.Note]:
    """Joue les appels et note chaque question, si la porte est accordée. ``client`` ne se
    construit que s'il reste un appel à faire (une évaluation toute en cache n'en demande
    pas) ; ``au_fil`` reçoit chaque note dès qu'elle est prise (la sortie de la commande)."""
    if not estimation.accordee:
        raise BudgetDepasse(
            f"estimation {estimation.estimation:.4f} $ pour {estimation.a_appeler} appel(s) +"
            f" déjà dépensé {estimation.deja:.4f} $ dépasse le plafond de {PLAFOND:.2f} $"
            f" (reste {estimation.reste:.4f} $) : aucun appel lancé"
        )
    llm = client() if estimation.a_appeler else None
    notes = []
    for question, prepare in prepares:
        if isinstance(prepare, chemin.Appel):
            if llm is None:  # tout est au cache : aucun client n'est construit
                llm = _ClientInterdit()
            reponse = chemin.conclure(prepare, llm, journal, cache)
        else:
            reponse = prepare
        note = notation.noter(question, reponse)
        notes.append(note)
        if au_fil is not None:
            au_fil(note, reponse)
    return notes


class _ClientInterdit:
    """Le client d'une évaluation toute en cache : un appel serait un défaut du cache."""

    def repondre(self, systeme: str, contenu: str, *, effort: str, max_tokens: int) -> Any:  # noqa: ARG002
        raise AssertionError("évaluation toute en cache : aucun appel ne devait partir")
