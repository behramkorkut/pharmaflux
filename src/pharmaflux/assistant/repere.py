"""Repérer le médicament visé par une question (addendum 1 B), règle écrite et testée.

D'abord un CIS (8 chiffres) ou un CIP13 (13 chiffres) **explicite** dans la question ; sinon
les **dénominations de l'index dont le premier mot significatif** paraît dans la question (un
dictionnaire ``mot → CIS``, tiré une fois des fragments ``identite``). Un CIP13 se ramène à
son CIS par le dictionnaire des présentations.

**Les mots de forme ne nomment pas un médicament.** Une dénomination BDPM s'écrit « NOM dosage,
forme » : ce qui suit la dernière « , » est la forme pharmaceutique (« comprimé enrobé »,
« solution injectable »). Le vocabulaire de ces formes est tiré des dénominations elles-mêmes, et
ses mots ne sont jamais « significatifs » : sans cela, « B O P, comprimé enrobé » (dont les lettres
sont trop courtes) ferait de « comprime » le nom d'un médicament, et toute question qui dit
« comprimé enrobé » viserait deux médicaments.

**Deux médicaments** (abstention « un à la fois ») : un médicament est **nommé** quand tous les
mots significatifs de son nom (la dénomination avant sa forme) sont dans la question, et un nom
contenu dans un autre nom nommé ne compte pas à part (« SUNITINIB EG » dans « SUNITINIB
BIOGARAN », « NEBIVOLOL BIOGARAN » dans « NEBIVOLOL/HYDROCHLOROTHIAZIDE BIOGARAN »). Une question
sur un **groupe générique** nomme par construction la DCI et le princeps (« EZETIMIBE 10 mg -
EZETROL 10 mg ») : elle compte pour un, mais seulement si les noms nommés tiennent tous dans le
libellé d'un même groupe générique de l'index. Ces règles sont éprouvées sur 200 médicaments tirés
au hasard des dénominations du jeu de démo, seuls puis deux par deux (``tests/test_assistant.py``).

Le repérage nourrit la **porte structurelle** du chemin (B6) : si un médicament est visé mais
qu'aucun fragment rendu ne lui appartient, l'assistant s'abstient (« le référentiel ne répond
pas à cette question »). Le même tokenizer que l'index (``index.lexical``) sert ici, pour que
« DOLIPRANE » de la question et « DOLIPRANE » d'une dénomination se reconnaissent.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import pairwise

from pharmaflux.index import lexical

# Un mot significatif : au moins trois lettres, pas un mot vide. Les dénominations commencent
# par le nom du médicament (« DOLIPRANE 1000 mg… ») ; les mots vides n'en sont jamais la cible.
_MOT = re.compile(r"[a-z]{3,}$")
_MOTS_VIDES = (
    "les des une pour par sur quel quelle quels quelles est sont ont mon mes son ses nos vos"
    " leur leurs dans avec sans cette ces que qui quoi dont"
)
MOTS_VIDES = frozenset(_MOTS_VIDES.split())
# Les mots courants (mission 09, addendum 1 G) : premiers mots de dénominations du jeu qui sont
# aussi des mots de tous les jours ou de chimie (« eau » 13 dénominations, « fer » 5, « huile » 6,
# « vitamine » 25, « acide » 83, « chlorure » 35…). Seuls, ils ne visent pas un médicament : il
# faut les deux premiers mots significatifs du nom (« EAU OXYGENEE », « CHLORURE DE SODIUM »).
# Liste écrite et committée avant les questions neuves de la v2 qui la mesurent (07ac561), branchée
# sur le repérage après leur commit (bbb9809), et éprouvée comme « deux médicaments ».
MOTS_COURANTS = frozenset(
    [
        "eau",
        "fer",
        "gel",
        "huile",
        "alcool",
        "charbon",
        "cuivre",
        "zinc",
        "calcium",
        "magnesium",
        "vitamine",
        "acide",
        "chlorure",
        "sulfate",
        "citrate",
        "glycerine",
        "vaseline",
    ]
)
# Un groupe générique dans le texte d'un fragment ``identite`` : « - groupe 793 (libellé), type 0 ».
_GROUPE = re.compile(r"^\s*- groupe \d+ \((.*)\)(?:, type \S+)?$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Dictionnaire:
    """Ce que le repérage consulte, tiré une fois des fragments de l'index."""

    mot_vers_cis: Mapping[str, frozenset[str]]  # premier mot significatif d'une dénomination → CIS
    cip_vers_cis: Mapping[str, str]  # un CIP13 → son CIS
    denomination_par_cis: Mapping[str, str]  # CIS → sa dénomination (pour « deux médicaments »)
    mots_de_forme: frozenset[str] = frozenset()  # le vocabulaire des formes pharmaceutiques
    groupes: frozenset[frozenset[str]] = frozenset()  # les mots de chaque libellé de groupe


@dataclass(frozen=True, slots=True)
class Repere:
    """Le résultat du repérage : ce qui est nommé, et l'ensemble des CIS visés."""

    cis_explicites: tuple[str, ...]
    cip13: tuple[str, ...]
    noms: tuple[str, ...]  # les mots de dénomination reconnus dans la question
    vises: frozenset[str]  # tous les CIS visés (explicites, par CIP, par nom)

    @property
    def un_medicament_est_vise(self) -> bool:
        return bool(self.vises)


def _significatifs(denomination: str | None, mots_de_forme: frozenset[str]) -> list[str]:
    """Les mots significatifs d'une dénomination, dans l'ordre : trois lettres au moins, ni mot
    vide, ni mot de forme."""
    if not denomination:
        return []
    return [
        j
        for j in lexical.jetons(denomination)
        if _MOT.match(j) and j not in MOTS_VIDES and j not in mots_de_forme
    ]


def premier_mot(
    denomination: str | None, mots_de_forme: frozenset[str] = frozenset()
) -> str | None:
    """Le premier mot significatif d'une dénomination (le nom du médicament), ou rien."""
    mots = _significatifs(denomination, mots_de_forme)
    return mots[0] if mots else None


def cle_du_nom(denomination: str | None, mots_de_forme: frozenset[str] = frozenset()) -> str | None:
    """Ce qu'une question doit porter pour viser la dénomination : son premier mot significatif,
    ou ses deux premiers, joints par une espace, si le premier est un mot courant (mission 09)."""
    mots = _significatifs(denomination, mots_de_forme)
    if not mots:
        return None
    return " ".join(mots[:2]) if mots[0] in MOTS_COURANTS else mots[0]


def nom(denomination: str) -> str:
    """Le nom d'une dénomination « NOM dosage, forme » : ce qui précède la dernière « , »."""
    debut, separateur, _ = denomination.rpartition(", ")
    return debut if separateur else denomination


def mots_du_nom(denomination: str | None, mots_de_forme: frozenset[str]) -> frozenset[str]:
    """Les mots significatifs du nom d'une dénomination : ceux qu'une question doit tous porter
    pour nommer ce médicament."""
    return (
        frozenset(_significatifs(nom(denomination), mots_de_forme)) if denomination else frozenset()
    )


def forme(denomination: str) -> str:
    """La forme pharmaceutique d'une dénomination « NOM dosage, forme » : ce qui suit la dernière
    « , » (une virgule décimale, « 37,5 mg », n'est pas suivie d'une espace), sans ses
    parenthèses, qui précisent la forme par des noms de substances (« comprimé pelliculé
    (rapport amoxicilline/acide clavulanique : 8/1) »)."""
    _, separateur, reste = denomination.rpartition(", ")
    return re.sub(r"\([^)]*\)", " ", reste) if separateur else ""


def mots_de_forme(denominations: Iterable[str]) -> frozenset[str]:
    """Le vocabulaire des formes pharmaceutiques, tiré des dénominations elles-mêmes."""
    return frozenset(j for d in denominations for j in lexical.jetons(forme(d)))


def construire_dictionnaire(
    identite: Iterable[Mapping[str, object]],
    presentations: Iterable[Mapping[str, object]] = (),
) -> Dictionnaire:
    """Le dictionnaire du repérage, depuis les charges des fragments ``identite`` (``code_cis``,
    ``denomination``, et les libellés des groupes génériques cités dans le ``texte``) et
    ``presentations`` (les CIP13 cités dans le ``texte``)."""
    denomination_par_cis: dict[str, str] = {}
    libelles: set[str] = set()
    for charge in identite:
        denomination = charge.get("denomination")
        if isinstance(denomination, str):
            denomination_par_cis.setdefault(str(charge["code_cis"]), denomination)
        libelles.update(_GROUPE.findall(str(charge.get("texte", ""))))
    formes = mots_de_forme(denomination_par_cis.values())
    mot_vers_cis: dict[str, set[str]] = {}
    for cis, denomination in denomination_par_cis.items():
        mot = cle_du_nom(denomination, formes)
        if mot is not None:
            mot_vers_cis.setdefault(mot, set()).add(cis)
    cip_vers_cis: dict[str, str] = {}
    for charge in presentations:
        cis = str(charge["code_cis"])
        for cip in re.findall(r"\b(\d{13})\b", str(charge.get("texte", ""))):
            cip_vers_cis.setdefault(cip, cis)
    return Dictionnaire(
        {mot: frozenset(cis) for mot, cis in mot_vers_cis.items()},
        cip_vers_cis,
        denomination_par_cis,
        formes,
        frozenset(frozenset(_significatifs(libelle, formes)) for libelle in libelles),
    )


def medicaments_nommes(repere_: Repere, question: str, dictionnaire: Dictionnaire) -> int:
    """Combien de médicaments distincts la question nomme (addendum 1 B3, « deux médicaments »).

    Un médicament est nommé quand tous les mots significatifs de son nom sont dans la question ;
    seuls comptent les noms qu'aucun autre nom nommé ne contient. Une question qui dit
    « groupe » et dont les noms nommés tiennent tous dans le libellé d'un même groupe générique
    compte pour un. Un CIS ou un CIP13 explicite compte pour un, sauf s'il désigne un médicament
    déjà nommé.
    L'abstention « un à la fois » se décide sur deux ou plus.
    """
    mots = set(lexical.jetons(question))
    nommes: dict[frozenset[str], set[str]] = {}
    for cis in repere_.vises:
        mots_nom = mots_du_nom(
            dictionnaire.denomination_par_cis.get(cis), dictionnaire.mots_de_forme
        )
        if mots_nom and mots_nom <= mots:
            nommes.setdefault(mots_nom, set()).add(cis)
    maximaux = [m for m in nommes if not any(m < autre for autre in nommes)]
    entites = [nommes[m] for m in maximaux]
    if len(entites) >= 2 and "groupe" in mots:
        tous = frozenset().union(*maximaux)
        if any(tous <= libelle for libelle in dictionnaire.groupes):
            entites = [set().union(*entites)]
    explicites = [*repere_.cis_explicites]
    explicites += [dictionnaire.cip_vers_cis.get(cip, f"cip:{cip}") for cip in repere_.cip13]
    for cis in explicites:
        if not any(cis in entite for entite in entites):
            entites.append({cis})
    return len(entites)


def reperer(question: str, dictionnaire: Dictionnaire) -> Repere:
    """Les CIS visés par la question : CIS et CIP13 explicites, puis dénominations reconnues."""
    jetons = lexical.jetons(question)
    cis_explicites = tuple(dict.fromkeys(j for j in jetons if re.fullmatch(r"\d{8}", j)))
    cip13 = tuple(dict.fromkeys(j for j in jetons if re.fullmatch(r"\d{13}", j)))
    noms = []
    vises: set[str] = set(cis_explicites)
    vises.update(dictionnaire.cip_vers_cis[c] for c in cip13 if c in dictionnaire.cip_vers_cis)
    formes = dictionnaire.mots_de_forme  # le même filtre que la clé du nom (cle_du_nom)
    significatifs = [j for j in jetons if _MOT.match(j) and j not in MOTS_VIDES | formes]
    paires = [f"{a} {b}" for a, b in pairwise(significatifs)]
    for cle in [*jetons, *paires]:  # un mot courant ne vise qu'avec le mot qui le suit
        if cle in dictionnaire.mot_vers_cis:
            noms.append(cle)
            vises.update(dictionnaire.mot_vers_cis[cle])
    return Repere(cis_explicites, cip13, tuple(dict.fromkeys(noms)), frozenset(vises))
