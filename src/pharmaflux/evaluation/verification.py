"""Rejeu du jeu de questions : chaque attendu est recalculé depuis l'archive qu'il cite.

Pour chaque question qui a un ``attendu`` : l'archive est lue sous la racine
(jamais écrite), son sha256 est comparé à celui du jeu, le fichier est
vérifié contre son contrat (une anomalie bloquante arrête là : les colonnes
n'auraient pas de sens), puis les lignes qui portent la clé sont projetées
sur les colonnes lues et comparées, dans l'ordre du fichier, aux lignes
attendues. Une question sans attendu est seulement comptée (« non
calculable » si un lot doit l'apporter, « sans attendu » sinon).

Un attendu de page d'avis de la HAS (``attendu_has``, mission 09) se vérifie sans gold : la page
est relue dans l'archive HAS de la racine (sha256), le bronze des liens de la BDPM doit lier son
URL au dossier nommé, et l'extraction (``has.extraction``) doit redonner la date de l'avis, la
mise en ligne, la nature de la demande et l'extrait, en mots entiers.
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
from pharmaflux.evaluation.questions import Attendu, AttenduHas, Jeu, Question
from pharmaflux.has import extraction
from pharmaflux.index import lexical


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
    lectures: dict[tuple[str, str], Resultat | Lecture] = {}  # (archive, contrat) → lecture
    liens: dict[str, set[str]] | None = None  # URL → dossiers, lu une fois s'il en faut
    bilan = Bilan()
    for question in jeu.questions:
        if question.attendu_has is not None:
            liens = liens if liens is not None else _liens_bdpm(racine, contrats)
            bilan.resultats.append(_verifier_has(question, question.attendu_has, racine, liens))
            continue
        attendu = question.attendu
        if attendu is None:
            verdict = Verdict.NON_CALCULABLE if question.calculable_au else Verdict.SANS_ATTENDU
            bilan.resultats.append(Resultat(question, verdict, question.calculable_au or ""))
            continue
        cle = (attendu.archive, attendu.fichier)
        if cle not in lectures:
            lectures[cle] = _lire(question, attendu, racine, contrats[attendu.fichier])
        lecture = lectures[cle]
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


def _liens_bdpm(racine: Path, contrats: Mapping[str, Contrat]) -> dict[str, set[str]]:
    """Les dossiers qui lient chaque page d'avis, d'après la dernière archive des liens."""
    contrat = contrats["bdpm.liens_ct"]
    archive = bronze.derniere(racine, "bdpm", "HAS_LiensPageCT_bdpm.txt")
    if archive is None:
        return {}
    lecture = verifier(contrat, archive.lire(), fichier=archive.relatif(racine))
    i_dossier, i_lien = contrat.index("code_dossier_has"), contrat.index("lien_avis")
    liens: dict[str, set[str]] = {}
    for _, valeurs in lecture.lignes:
        liens.setdefault(valeurs[i_lien], set()).add(valeurs[i_dossier])
    return liens


def _verifier_has(
    question: Question, attendu: AttenduHas, racine: Path, liens: Mapping[str, set[str]]
) -> Resultat:
    chemin = racine / attendu.archive
    if not chemin.is_file():
        return Resultat(question, Verdict.ARCHIVE_INTROUVABLE, str(chemin))
    octets = bronze.lire_archive(chemin)
    if (sha256 := sha256_hex(octets)) != attendu.sha256:
        return Resultat(question, Verdict.SHA256_DIFFERENT, f"lu {sha256}")
    if attendu.dossier not in liens.get(attendu.url, set()):
        detail = f"la BDPM ne lie pas {attendu.url} au dossier {attendu.dossier}"
        return Resultat(question, Verdict.ECART, detail)
    try:
        extrait = extraction.extraire(octets, dossiers=(attendu.dossier,))
    except extraction.PageRejetee as exc:
        return Resultat(question, Verdict.ECART, f"page rejetée ({exc.motif})")
    lus = {
        "date_avis": extrait.date_avis.isoformat(),
        "mis_en_ligne": extrait.mis_en_ligne.isoformat(),
    }
    if attendu.nature_demande is not None:
        lus["nature_demande"] = extrait.nature_demande
    for nom, lu in lus.items():
        if getattr(attendu, nom) != lu:
            return Resultat(
                question, Verdict.ECART, f"{nom} : attendu « {getattr(attendu, nom)} », lu « {lu} »"
            )
    if attendu.extrait is not None:
        cherche = lexical.jetons(attendu.extrait)
        lignes = [lexical.jetons(ligne) for ligne in extrait.lignes_rendues()]
        if not any(_suite(ligne, cherche) for ligne in lignes):
            return Resultat(question, Verdict.ECART, f"extrait introuvable : « {attendu.extrait} »")
    return Resultat(
        question, Verdict.CONFORME, f"page d'avis, extracteur v{extraction.VERSION_EXTRACTEUR}"
    )


def _suite(meule: list[str], aiguille: list[str]) -> bool:
    n = len(aiguille)
    return n > 0 and any(meule[i : i + n] == aiguille for i in range(len(meule) - n + 1))


def formater_bilan(bilan: Bilan) -> str:
    """Une ligne par question (verdict, id, détail), puis le résumé."""
    largeur = max((len(r.verdict.value) for r in bilan.resultats), default=0)
    lignes = [
        f"{r.verdict.value:<{largeur}}  {r.question.id:<20} {r.detail}".rstrip()
        for r in bilan.resultats
    ]
    lignes.append(bilan.resume())
    return "\n".join(lignes)
