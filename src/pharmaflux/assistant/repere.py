"""Repérer le médicament visé par une question (addendum 1 B), règle écrite et testée.

D'abord un CIS (8 chiffres) ou un CIP13 (13 chiffres) **explicite** dans la question ; sinon
les **dénominations de l'index dont le premier mot significatif** paraît dans la question (un
dictionnaire ``mot → CIS``, tiré une fois des fragments ``identite``). Un CIP13 se ramène à
son CIS par le dictionnaire des présentations.

Le repérage nourrit la **porte structurelle** du chemin (B6) : si un médicament est visé mais
qu'aucun fragment rendu ne lui appartient, l'assistant s'abstient (« le référentiel ne répond
pas à cette question »). Le même tokenizer que l'index (``index.lexical``) sert ici, pour que
« DOLIPRANE » de la question et « DOLIPRANE » d'une dénomination se reconnaissent.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from pharmaflux.index import lexical

# Un mot significatif : au moins trois lettres, pas un mot vide. Les dénominations commencent
# par le nom du médicament (« DOLIPRANE 1000 mg… ») ; les mots vides n'en sont jamais la cible.
_MOT = re.compile(r"[a-z]{3,}$")
_MOTS_VIDES = (
    "les des une pour par sur quel quelle quels quelles est sont ont mon mes son ses nos vos"
    " leur leurs dans avec sans cette ces que qui quoi dont"
)
MOTS_VIDES = frozenset(_MOTS_VIDES.split())


@dataclass(frozen=True, slots=True)
class Dictionnaire:
    """Ce que le repérage consulte, tiré une fois des fragments de l'index."""

    mot_vers_cis: Mapping[str, frozenset[str]]  # premier mot significatif d'une dénomination → CIS
    cip_vers_cis: Mapping[str, str]  # un CIP13 → son CIS
    denomination_par_cis: Mapping[str, str]  # CIS → sa dénomination (pour « deux médicaments »)


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


def premier_mot(denomination: str | None) -> str | None:
    """Le premier mot significatif d'une dénomination (le nom du médicament), ou rien."""
    if not denomination:
        return None
    for jeton in lexical.jetons(denomination):
        if _MOT.match(jeton) and jeton not in MOTS_VIDES:
            return jeton
    return None


def construire_dictionnaire(
    identite: Iterable[Mapping[str, object]],
    presentations: Iterable[Mapping[str, object]] = (),
) -> Dictionnaire:
    """Le dictionnaire du repérage, depuis les charges des fragments ``identite`` et
    ``presentations`` (``denomination``, ``code_cis``, et les CIP13 cités dans le texte)."""
    mot_vers_cis: dict[str, set[str]] = {}
    denomination_par_cis: dict[str, str] = {}
    for charge in identite:
        cis = str(charge["code_cis"])
        denomination = charge.get("denomination")
        if isinstance(denomination, str):
            denomination_par_cis.setdefault(cis, denomination)
        mot = premier_mot(denomination)  # type: ignore[arg-type]
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
    )


def _signature(denomination: str | None) -> tuple[str, ...]:
    """Les deux premiers mots significatifs d'une dénomination (nom + marque), pour distinguer
    deux produits qui partagent la DCI (« SUNITINIB BIOGARAN » et « SUNITINIB ZENTIVA »)."""
    if not denomination:
        return ()
    mots = [j for j in lexical.jetons(denomination) if _MOT.match(j) and j not in MOTS_VIDES]
    return tuple(mots[:2])


def medicaments_nommes(repere_: Repere, question: str, dictionnaire: Dictionnaire) -> int:
    """Combien de médicaments distincts la question nomme (addendum 1 B3, « deux médicaments »).

    Une dénomination est nommée quand ses deux premiers mots significatifs sont tous les deux
    dans la question ; chaque CIS et chaque CIP13 explicite compte pour un. L'abstention « un à
    la fois » se décide sur deux ou plus.
    """
    mots = set(lexical.jetons(question))
    distincts: set[tuple[str, ...]] = set()
    for cis in repere_.vises:
        signature = _signature(dictionnaire.denomination_par_cis.get(cis))
        if signature and all(mot in mots for mot in signature):
            distincts.add(signature)
    distincts |= {("cis", c) for c in repere_.cis_explicites}
    distincts |= {("cip", c) for c in repere_.cip13}
    return len(distincts)


def reperer(question: str, dictionnaire: Dictionnaire) -> Repere:
    """Les CIS visés par la question : CIS et CIP13 explicites, puis dénominations reconnues."""
    jetons = lexical.jetons(question)
    cis_explicites = tuple(dict.fromkeys(j for j in jetons if re.fullmatch(r"\d{8}", j)))
    cip13 = tuple(dict.fromkeys(j for j in jetons if re.fullmatch(r"\d{13}", j)))
    noms = []
    vises: set[str] = set(cis_explicites)
    vises.update(dictionnaire.cip_vers_cis[c] for c in cip13 if c in dictionnaire.cip_vers_cis)
    for jeton in jetons:
        if jeton in dictionnaire.mot_vers_cis:
            noms.append(jeton)
            vises.update(dictionnaire.mot_vers_cis[jeton])
    return Repere(cis_explicites, cip13, tuple(dict.fromkeys(noms)), frozenset(vises))
