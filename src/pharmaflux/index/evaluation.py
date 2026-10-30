"""La mesure de la recherche : dense seul, creux seul, hybride, côte à côte (addendum 1 A).

Sur les questions d'un jeu qui nomment un médicament (leur réponse attendue a
pour clé un CIS ou un CIP13, dans un fichier qu'une section de fragment
couvre) : le rang du premier fragment du bon CIS, puis du bon CIS **et** de la
bonne section, parmi les dix premiers ; le rappel à 1, 5 et 10 et le rang
réciproque moyen, pour chacun des trois modes. Pour les questions hors
périmètre ou médicales, le score dense du premier résultat : une donnée pour
l'abstention, pas une règle. Aucun seuil, aucun code d'erreur sur la qualité.

La cible (addendum 1 A) : l'hybride au moins égal au dense pour le bon CIS à 5
et à 10, et meilleur sur les questions dont la réponse est dans ``identite``.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from pharmaflux.evaluation.questions import Jeu
from pharmaflux.index.construction import (
    MODE_DENSE,
    MODE_HYBRIDE,
    MODE_LEXICAL,
    Resultat,
    chercher,
)
from pharmaflux.index.encodeur import Encodeur
from pharmaflux.index.qdrant import Qdrant, filtre_egal

K = 10
MODES = (MODE_DENSE, MODE_LEXICAL, MODE_HYBRIDE)
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
    rangs_cis: dict[str, int | None]  # mode → rang du bon CIS parmi les K premiers (sinon None)
    rangs: dict[str, int | None]  # mode → rang du bon CIS et de la bonne section
    score_dense_premier: float


@dataclass(frozen=True, slots=True)
class Mesure:
    instant: str
    modele: str
    lignes: tuple[Ligne, ...]
    hors: tuple[tuple[str, float], ...]  # (question, score dense du premier)

    def rappel(self, mode: str, k: int, section: bool = True) -> int:
        rangs = (x.rangs if section else x.rangs_cis for x in self.lignes)
        return sum(1 for r in rangs if (v := r[mode]) and v <= k)

    def rang_reciproque(self, mode: str) -> float:
        somme = sum(1 / r for x in self.lignes if (r := x.rangs[mode]))
        return somme / max(len(self.lignes), 1)


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


def _rang_de(resultats: Sequence[Resultat], **egal: str) -> int | None:
    """Le rang (1..K) du premier résultat dont la charge vérifie toutes les égalités."""
    for r in resultats:
        if all(r.charge.get(cle) == valeur for cle, valeur in egal.items()):
            return r.rang
    return None


def evaluer(qdrant: Qdrant, encodeur: Encodeur, jeu: Jeu) -> Mesure:
    cip13 = cis_des_presentations(qdrant)
    lignes, hors = [], []
    instant = modele = ""
    for q in jeu.questions:
        par_mode = {mode: chercher(qdrant, encodeur, q.question, K, mode=mode) for mode in MODES}
        etat, denses = par_mode[MODE_DENSE]
        instant, modele = etat["instant"], etat["empreinte_modele"]
        premier = denses[0].score if denses else 0.0
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
        rangs_cis = {mode: _rang_de(par_mode[mode][1], code_cis=cis) for mode in MODES}
        rangs = {mode: _rang_de(par_mode[mode][1], code_cis=cis, section=section) for mode in MODES}
        lignes.append(Ligne(q.id, cis, section, rangs_cis, rangs, premier))
    return Mesure(instant, modele, tuple(lignes), tuple(hors))


def formater(mesure: Mesure) -> list[str]:
    n = len(mesure.lignes)
    lignes = [
        f"index au {mesure.instant}, modèle {mesure.modele} ; {n} questions nomment un médicament",
        "",
        f"{'mode':9} {'bon CIS @1/5/10':22} {'bon CIS+section @1/5/10':26} rang réciproque moyen",
    ]
    for mode in MODES:

        def rappels(section: bool, mode: str = mode) -> str:
            return "  ".join(f"@{k} {mesure.rappel(mode, k, section)}/{n}" for k in (1, 5, 10))

        lignes.append(
            f"{mode:9} {rappels(False):22} {rappels(True):26} {mesure.rang_reciproque(mode):.3f}"
        )
    lignes += [
        "",
        "score dense du premier   questions du périmètre : médiane "
        + _mediane([x.score_dense_premier for x in mesure.lignes])
        + " ; hors périmètre et médicales : médiane "
        + _mediane([s for _, s in mesure.hors])
        + f", max {max((s for _, s in mesure.hors), default=0):.3f}",
        "",
        f"{'question':20} {'CIS':9} {'section':14} rang CIS+section (dense / creux / hybride)",
    ]
    for x in mesure.lignes:
        rangs = " / ".join(_rang(x.rangs[mode]) for mode in MODES)
        lignes.append(f"{x.question:20} {x.code_cis:9} {x.section:14} {rangs}")
    return lignes


def _mediane(valeurs: Sequence[float]) -> str:
    return f"{statistics.median(valeurs):.3f}" if valeurs else "—"


def _rang(rang: int | None) -> str:
    return str(rang) if rang else f">{K}"
