"""Rejeu du jeu de questions : chaque attendu est recalculé depuis l'archive qu'il cite.

Pour chaque question qui a un ``attendu`` : l'archive est lue sous la racine
(jamais écrite), son sha256 est comparé à celui du jeu, le fichier est
vérifié contre son contrat (une anomalie bloquante arrête là : les colonnes
n'auraient pas de sens), puis les lignes qui portent la clé sont projetées
sur les colonnes lues et comparées, dans l'ordre du fichier, aux lignes
attendues. Une question sans attendu est seulement comptée (« non
calculable » si un lot doit l'apporter, « sans attendu » sinon).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from pharmaflux import bronze
from pharmaflux.collecte.empreintes import sha256_hex
from pharmaflux.contrats.modele import Contrat
from pharmaflux.contrats.verification import Lecture, verifier
from pharmaflux.evaluation.questions import Attendu, Jeu, Question


class Verdict(StrEnum):
    CONFORME = "conforme"
    ECART = "écart"
    ARCHIVE_INTROUVABLE = "archive introuvable"
    SHA256_DIFFERENT = "sha256 différent"
    ARCHIVE_NON_CONFORME = "archive non conforme au contrat"
    NON_CALCULABLE = "non calculable"
    SANS_ATTENDU = "sans attendu"


ECHECS = frozenset(
    {
        Verdict.ECART,
        Verdict.ARCHIVE_INTROUVABLE,
        Verdict.SHA256_DIFFERENT,
        Verdict.ARCHIVE_NON_CONFORME,
    }
)


@dataclass(frozen=True, slots=True)
class Resultat:
    question: Question
    verdict: Verdict
    detail: str = ""

    @property
    def echec(self) -> bool:
        return self.verdict in ECHECS


@dataclass(slots=True)
class Bilan:
    resultats: list[Resultat] = field(default_factory=list)

    @property
    def echecs(self) -> list[Resultat]:
        return [resultat for resultat in self.resultats if resultat.echec]

    @property
    def code_sortie(self) -> int:
        return 1 if self.echecs else 0

    def nombre(self, verdict: Verdict) -> int:
        return sum(1 for resultat in self.resultats if resultat.verdict is verdict)

    def resume(self) -> str:
        parts = [f"{len(self.resultats)} question(s)"]
        for verdict in Verdict:
            if nombre := self.nombre(verdict):
                parts.append(f"{nombre} {verdict.value}")
        return " : ".join([parts[0], ", ".join(parts[1:])]) + "."


def verifier_jeu(jeu: Jeu, racine: Path, contrats: Mapping[str, Contrat]) -> Bilan:
    """Rejoue chaque attendu sur ``racine`` ; chaque archive n'est lue et vérifiée qu'une fois."""
    lectures: dict[str, Resultat | Lecture] = {}
    bilan = Bilan()
    for question in jeu.questions:
        attendu = question.attendu
        if attendu is None:
            verdict = Verdict.NON_CALCULABLE if question.calculable_au else Verdict.SANS_ATTENDU
            bilan.resultats.append(Resultat(question, verdict, question.calculable_au or ""))
            continue
        if attendu.archive not in lectures:
            lectures[attendu.archive] = _lire(question, attendu, racine, contrats[attendu.fichier])
        lecture = lectures[attendu.archive]
        if isinstance(lecture, Resultat):
            bilan.resultats.append(Resultat(question, lecture.verdict, lecture.detail))
        else:
            bilan.resultats.append(_comparer(question, attendu, lecture))
    return bilan


def _lire(
    question: Question, attendu: Attendu, racine: Path, contrat: Contrat
) -> Resultat | Lecture:
    chemin = racine / attendu.archive
    if not chemin.is_file():
        return Resultat(question, Verdict.ARCHIVE_INTROUVABLE, str(chemin))
    octets = bronze.lire_archive(chemin)
    sha256 = sha256_hex(octets)
    if sha256 != attendu.sha256:
        return Resultat(question, Verdict.SHA256_DIFFERENT, f"lu {sha256}")
    lecture = verifier(contrat, octets, fichier=attendu.archive)
    if bloquantes := lecture.bloquantes:
        regles = ", ".join(sorted({anomalie.regle.value for anomalie in bloquantes}))
        return Resultat(question, Verdict.ARCHIVE_NON_CONFORME, regles)
    return lecture


def _comparer(question: Question, attendu: Attendu, lecture: Lecture) -> Resultat:
    noms = lecture.contrat.noms_colonnes
    index_cle = [(noms.index(nom), valeur) for nom, valeur in attendu.cle.items()]
    index_lues = [noms.index(nom) for nom in attendu.colonnes]
    trouvees = [
        {nom: valeurs[i] for nom, i in zip(attendu.colonnes, index_lues, strict=True)}
        for _, valeurs in lecture.lignes
        if all(valeurs[i] == valeur for i, valeur in index_cle)
    ]
    attendues = [dict(ligne) for ligne in attendu.valeurs]
    if trouvees == attendues:
        return Resultat(question, Verdict.CONFORME, f"{len(trouvees)} ligne(s)")
    if len(trouvees) != len(attendues):
        detail = f"{len(attendues)} ligne(s) attendue(s), {len(trouvees)} trouvée(s)"
        return Resultat(question, Verdict.ECART, detail)
    for numero, (trouvee, attendue) in enumerate(zip(trouvees, attendues, strict=True), 1):
        for nom in attendu.colonnes:
            if trouvee[nom] != attendue[nom]:
                detail = (
                    f"ligne {numero}, {nom} : attendu « {attendue[nom]} », lu « {trouvee[nom]} »"
                )
                return Resultat(question, Verdict.ECART, detail)
    raise AssertionError("listes différentes sans différence")  # pragma: no cover


def formater_bilan(bilan: Bilan) -> str:
    """Une ligne par question (verdict, id, détail), puis le résumé."""
    largeur = max((len(r.verdict.value) for r in bilan.resultats), default=0)
    lignes = [
        f"{r.verdict.value:<{largeur}}  {r.question.id:<20} {r.detail}".rstrip()
        for r in bilan.resultats
    ]
    lignes.append(bilan.resume())
    return "\n".join(lignes)
