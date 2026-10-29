"""Une première mesure de la recherche, pour la mission 08 (addendum 1 G).

Sur les questions du jeu v0 qui nomment un médicament (leur réponse attendue
a pour clé un CIS ou un CIP13, dans un fichier qu'une section de fragment
couvre) : le rang du premier fragment du bon CIS, puis du bon CIS **et** de
la bonne section, parmi les dix premiers ; le rappel à 1, 5 et 10 et le rang
réciproque moyen. Pour les questions hors périmètre ou médicales, le score du
premier résultat : une donnée pour l'abstention de la mission 08, pas une
règle. Aucun seuil, aucun code d'erreur sur la qualité.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from pharmaflux.evaluation.questions import Jeu
from pharmaflux.index.construction import chercher
from pharmaflux.index.encodeur import Encodeur
from pharmaflux.index.qdrant import Qdrant, filtre_egal

K = 10
SECTION_DU_FICHIER = {
    "bdpm.disponibilite": "disponibilite",
    "bdpm.specialites": "identite",
    "bdpm.generiques": "identite",
    "bdpm.presentations": "presentations",
    "bdpm.smr": "avis",
    "bdpm.asmr": "avis",
}
CATEGORIES_HORS = ("hors_perimetre", "medical")
_CIP13 = re.compile(r"^  - (\d{13}) :", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Ligne:
    question: str
    code_cis: str
    section: str
    rang_cis: int | None  # parmi les K premiers, sinon None
    rang: int | None  # CIS et section
    score_premier: float


@dataclass(frozen=True, slots=True)
class Mesure:
    instant: str
    modele: str
    lignes: tuple[Ligne, ...]
    hors: tuple[tuple[str, float], ...]  # (question, score du premier)

    def rappel(self, k: int, section: bool = True) -> int:
        return sum(1 for x in self.lignes if (r := x.rang if section else x.rang_cis) and r <= k)

    def rang_reciproque(self) -> float:
        return sum(1 / x.rang for x in self.lignes if x.rang) / max(len(self.lignes), 1)


def cis_des_presentations(qdrant: Qdrant) -> dict[str, str]:
    """CIP13 → CIS, lu dans les fragments ``presentations`` de l'index (sans ouvrir le gold)."""
    table: dict[str, str] = {}
    for point in qdrant.parcourir(
        qdrant.alias_fragments,
        filtre_egal("section", "presentations"),
        champs=["code_cis", "texte"],
    ):
        for cip13 in _CIP13.findall(point["payload"]["texte"]):
            table[cip13] = point["payload"]["code_cis"]
    return table


def evaluer(qdrant: Qdrant, encodeur: Encodeur, jeu: Jeu) -> Mesure:
    cip13 = cis_des_presentations(qdrant)
    lignes, hors = [], []
    instant = modele = ""
    for q in jeu.questions:
        etat, resultats = chercher(qdrant, encodeur, q.question, K)
        instant, modele = etat["instant"], etat["empreinte_modele"]
        premier = resultats[0].score if resultats else 0.0
        if q.categorie in CATEGORIES_HORS:
            hors.append((q.id, premier))
            continue
        if q.attendu is None or q.attendu.fichier not in SECTION_DU_FICHIER:
            continue
        cle = q.attendu.cle
        cis = cle.get("code_cis") or cip13.get(cle.get("code_cip13", ""))
        if cis is None:
            continue
        section = SECTION_DU_FICHIER[q.attendu.fichier]
        lignes.append(
            Ligne(
                q.id,
                cis,
                section,
                next((r.rang for r in resultats if r.charge["code_cis"] == cis), None),
                next(
                    (
                        r.rang
                        for r in resultats
                        if (r.charge["code_cis"], r.charge["section"]) == (cis, section)
                    ),
                    None,
                ),
                premier,
            )
        )
    return Mesure(instant, modele, tuple(lignes), tuple(hors))


def formater(mesure: Mesure) -> list[str]:
    n = len(mesure.lignes)

    def rappels(section: bool) -> str:
        return "  ".join(f"@{k} {mesure.rappel(k, section)}/{n}" for k in (1, 5, 10))

    lignes = [
        f"index au {mesure.instant}, modèle {mesure.modele} ; {n} questions nomment un médicament",
        f"bon CIS            {rappels(False)}",
        f"bon CIS + section  {rappels(True)}  rang réciproque moyen {mesure.rang_reciproque():.3f}",
        "score du premier   questions du périmètre : médiane "
        + _mediane([x.score_premier for x in mesure.lignes])
        + " ; hors périmètre et médicales : médiane "
        + _mediane([s for _, s in mesure.hors])
        + f", max {max((s for _, s in mesure.hors), default=0):.3f}",
        "",
        f"{'question':20} {'CIS':9} {'section':14} rang CIS  rang CIS+section",
    ]
    for x in mesure.lignes:
        rangs = f"{_rang(x.rang_cis):>8}  {_rang(x.rang):>8}"
        lignes.append(f"{x.question:20} {x.code_cis:9} {x.section:14} {rangs}")
    return lignes


def _mediane(valeurs: Sequence[float]) -> str:
    return f"{statistics.median(valeurs):.3f}" if valeurs else "—"


def _rang(rang: int | None) -> str:
    return str(rang) if rang else f"> {K}"
