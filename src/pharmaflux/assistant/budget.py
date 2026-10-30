"""Le budget de la mission : grille de prix, estimation locale, journal, plafond (addendum 1 G).

Opus 5.5, grille du 2026-10 (documentation de l'API Claude) : 4,00 $/Mt en entrée,
20,00 $/Mt en sortie, 0,20 $/Mt en lecture de cache ; l'écriture de cache éphémère coûte
1,25 fois l'entrée (5,00 $/Mt). Le plafond de la mission est **20 $** (PRD §7.5).

Avant chaque appel, une **estimation locale** (jamais ``count_tokens``, qui est une requête
payante) : les jetons d'entrée estimés par le compte de caractères, **plus ``max_tokens``
entier** en sortie — prudent, pour qu'aucune évaluation ne s'arrête faute de budget au
milieu. Si le total déjà dépensé plus l'estimation dépasse le plafond, l'appel est refusé et
rien n'est appelé. Après l'appel, le coût **réel** est lu dans ``response.usage`` (déjà payé,
exact) et journalisé dans ``data/assistant/depenses.jsonl`` (hors git), une ligne par appel,
chaque ligne portant le numéro de la mission. ``make rebatir`` n'efface jamais ce journal
(contrôlé au palier 3).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

MISSION = 8
MODELE = "claude-opus-5-5"
PLAFOND = 20.0  # $, constante de la mission (PRD §7.5, sur les 100 $ du Lot 3)

# Grille du 2026-10, vérifiée dans la documentation de l'API (addendum 1). Dollars par million
# de jetons. L'écriture de cache (5,00) est le tarif standard 1,25 fois l'entrée du cache
# éphémère de 5 minutes ; l'addendum ne chiffre que la lecture, la plus fréquente.
GRILLE_DATE = "2026-10"
GRILLE_SOURCE = "documentation de l'API Claude (tarifs Opus 5.5)"
PRIX_ENTREE = 4.00
PRIX_SORTIE = 20.00
PRIX_CACHE_LECTURE = 0.20
PRIX_CACHE_ECRITURE = 5.00

# Un fragment français pèse ≈ 3,8 caractères par jeton (mesuré au §0). L'estimation d'entrée
# est volontairement prudente : elle majore plutôt qu'elle ne minore.
CARACTERES_PAR_JETON = 3.8

NOM_JOURNAL = "depenses.jsonl"


class BudgetDepasse(Exception):  # noqa: N818 (nom français voulu)
    """L'estimation d'un appel ferait dépasser le plafond : rien n'est appelé."""


@dataclass(frozen=True, slots=True)
class Usage:
    """Les jetons d'un appel, tels que ``response.usage`` les donne (aucun recalcul)."""

    jetons_entree: int
    jetons_sortie: int
    jetons_cache_lecture: int = 0  # cache_read_input_tokens
    jetons_cache_ecriture: int = 0  # cache_creation_input_tokens


def cout(usage: Usage) -> float:
    """Le coût réel en dollars, d'après les jetons et la grille."""
    return (
        usage.jetons_entree * PRIX_ENTREE
        + usage.jetons_sortie * PRIX_SORTIE
        + usage.jetons_cache_lecture * PRIX_CACHE_LECTURE
        + usage.jetons_cache_ecriture * PRIX_CACHE_ECRITURE
    ) / 1_000_000


def jetons_estimes(texte: str) -> int:
    """Une estimation prudente du nombre de jetons d'un texte d'entrée (au caractère)."""
    return int(len(texte) / CARACTERES_PAR_JETON) + 1


def cout_estime(texte_entree: str, max_tokens: int) -> float:
    """L'estimation d'un appel, **avant** de le lancer : entrée au caractère, sortie entière.

    La sortie est comptée à ``max_tokens`` entier (la pensée adaptative comprise), jamais
    moins : la porte budgétaire ne laisse passer que ce qui tient à coup sûr.
    """
    return (jetons_estimes(texte_entree) * PRIX_ENTREE + max_tokens * PRIX_SORTIE) / 1_000_000


@dataclass(frozen=True, slots=True)
class Ligne:
    """Une ligne du journal : un appel réel, son coût déjà payé."""

    instant: str
    mission: int
    question: str  # l'identifiant de la question, ou la question posée en clair
    modele: str
    effort: str
    jetons_entree: int
    jetons_sortie: int
    jetons_cache_lecture: int
    jetons_cache_ecriture: int
    cout: float


class Journal:
    """Le journal des dépenses (``data/assistant/depenses.jsonl``), lu et complété ligne à ligne.

    Rien n'est gardé en mémoire : le total se recalcule en relisant le fichier, et chaque
    appel ajoute une ligne. Un fichier absent vaut un total nul.
    """

    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin

    def lignes(self) -> list[Ligne]:
        if not self.chemin.exists():
            return []
        lues = []
        for ligne in self.chemin.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                lues.append(Ligne(**json.loads(ligne)))
        return lues

    def total(self, mission: int = MISSION) -> float:
        """Le total dépensé pour une mission, lu dans le journal."""
        return sum(ligne.cout for ligne in self.lignes() if ligne.mission == mission)

    def reste(self, mission: int = MISSION) -> float:
        return PLAFOND - self.total(mission)

    def ajouter(self, ligne: Ligne) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with self.chemin.open("a", encoding="utf-8") as sortie:
            sortie.write(json.dumps(asdict(ligne), ensure_ascii=False) + "\n")


def exiger_budget(journal: Journal, estimation: float, *, mission: int = MISSION) -> None:
    """Refuse l'appel si le total déjà dépensé plus l'estimation dépasse le plafond."""
    deja = journal.total(mission)
    if deja + estimation > PLAFOND:
        raise BudgetDepasse(
            f"estimation {estimation:.4f} $ + déjà dépensé {deja:.4f} $ dépasse le plafond"
            f" de {PLAFOND:.2f} $ (reste {PLAFOND - deja:.4f} $) : aucun appel lancé"
        )
