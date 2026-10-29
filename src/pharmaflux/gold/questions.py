"""Le jeu de questions recalculé depuis le gold, à l'instant de chaque archive citée (H).

Pour chaque question qui a un attendu : l'instant est l'horodatage de son
archive (``AAAAMMJJThhmmssZ`` dans son nom, comme ``silver verifier``). Les
lignes attendues, **brutes**, passent par la normalisation du contrat puis
par le typage du gold ; la clé de la question aussi. Le gold rend, à cet
instant, les lignes qui portent la clé, par la vue qui sert le Lot 3 quand la
clé s'y prête :

- **fiche médicament, par CIS** : la spécialité elle-même (une ligne si le CIS
  est au référentiel, aucune sinon : c'est ce que vérifient les deux
  abstentions), ou la section de la fiche (présentations, groupes, avis,
  signalements), dépliée selon ``occurrences`` ;
- **fiche médicament, par CIP13** : la présentation, retrouvée dans la section
  ``presentations`` des fiches ;
- **alternatives, par groupe** : une ligne par spécialité du groupe ;
- sinon, **les colonnes typées** de l'entité.

Les deux ensembles se comparent **en multiensemble** (le gold ne connaît pas
l'ordre du fichier ; le bronze, lui, le vérifie). Une question dont l'instant
précède la première observation de son entité, ou suit la dernière du
silver, est « non calculable depuis le gold », jamais comptée conforme.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from pharmaflux.contrats.modele import Contrat, TypeValeur
from pharmaflux.contrats.normalisation import REGLES_DE_LISIBILITE, normaliser_valeur
from pharmaflux.evaluation.questions import Attendu, Jeu, Question
from pharmaflux.gold.qualite import ENTITES_GOLD
from pharmaflux.gold.rendu import en_json
from pharmaflux.gold.sql import etats_types
from pharmaflux.gold.typage import derniere_observation, typer_valeurs
from pharmaflux.gold.vues import Vues, vues
from pharmaflux.silver import SilverRefuse
from pharmaflux.silver.entrepot import Entrepot
from pharmaflux.silver.etat import bornes
from pharmaflux.silver.schema import texte_instant

# Les sections de la fiche, par entité ; les autres colonnes de la ligne : ``code_cis``.
SECTIONS = {
    "bdpm.disponibilite": "disponibilite",
    "bdpm.generiques": "groupes_generiques",
    "bdpm.presentations": "presentations",
    "bdpm.smr": "avis_smr",
    "bdpm.asmr": "avis_asmr",
}

Ligne = dict[str, Any]


class VerdictGold(StrEnum):
    CONCORDE = "concorde"
    DISCORDE = "discorde"
    NON_CALCULABLE = "non calculable depuis le gold"


@dataclass(frozen=True, slots=True)
class ResultatGold:
    question: Question
    verdict: VerdictGold
    route: str
    detail: str = ""
    attendues: list[Ligne] = field(default_factory=list)
    calculees: list[Ligne] = field(default_factory=list)


@dataclass(slots=True)
class BilanGold:
    resultats: list[ResultatGold] = field(default_factory=list)

    @property
    def echecs(self) -> list[ResultatGold]:
        return [r for r in self.resultats if r.verdict is not VerdictGold.CONCORDE]

    @property
    def code_sortie(self) -> int:
        return 2 if self.echecs else 0

    def resume(self) -> str:
        comptes = Counter(r.verdict for r in self.resultats)
        parts = [f"{comptes[v]} {v.value}" for v in VerdictGold if comptes[v]]
        return f"{len(self.resultats)} question(s) depuis le gold : {', '.join(parts) or 'aucune'}."


def instant_de_l_archive(archive: str) -> datetime:
    """L'horodatage d'une archive, lu dans son nom (``20261024T194201Z__….txt.gz``)."""
    return datetime.strptime(PurePosixPath(archive).name[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def valeur_typee(type_: TypeValeur, brute: str) -> object:
    """Une valeur brute du fichier, normalisée par le contrat, puis typée comme le gold."""
    normalisee = normaliser_valeur(type_, brute)
    if normalisee.valeur == "" or normalisee.regle in REGLES_DE_LISIBILITE:
        return None
    typees, _ = typer_valeurs(pa.array([normalisee.valeur], pa.string()), type_)
    return typees.to_pylist()[0]


def verifier_gold(jeu: Jeu, entrepot: Entrepot, contrats: Mapping[str, Contrat]) -> BilanGold:
    """Chaque attendu recalculé depuis le gold ; les vues sont calculées une fois par instant."""
    manquantes = [e for e in ENTITES_GOLD if entrepot.table(e) is None]
    if manquantes:
        raise SilverRefuse(f"le gold demande les onze entités ; absentes : {', '.join(manquantes)}")
    derniere = derniere_observation(entrepot)
    premieres = {e: bornes(t)[0] for e in ENTITES_GOLD if (t := entrepot.table(e)) is not None}
    bilan = BilanGold()
    cache: dict[datetime, _Gold] = {}
    for question in jeu.questions:
        attendu = question.attendu
        if attendu is None:
            continue
        instant = instant_de_l_archive(attendu.archive)
        premiere = premieres[attendu.fichier]
        if premiere is None or derniere is None or not premiere <= instant <= derniere:
            bilan.resultats.append(
                ResultatGold(
                    question,
                    VerdictGold.NON_CALCULABLE,
                    "—",
                    f"{texte_instant(instant)} hors de la fenêtre du silver",
                )
            )
            continue
        if instant not in cache:
            cache.clear()  # une seule série de vues en mémoire à la fois
            etats = etats_types(entrepot, contrats, instant)
            cache[instant] = _Gold(etats, vues(entrepot, contrats, etats, instant))
        bilan.resultats.append(
            _comparer(question, attendu, contrats[attendu.fichier], cache[instant])
        )
    return bilan


@dataclass(frozen=True, slots=True)
class _Gold:
    etats: Mapping[str, Any]
    vues: Vues


def _comparer(question: Question, attendu: Attendu, contrat: Contrat, gold: _Gold) -> ResultatGold:
    types = {c.nom: c.type for c in contrat.colonnes}
    cle = {nom: valeur_typee(types[nom], brute) for nom, brute in attendu.cle.items()}
    attendues = [
        {nom: valeur_typee(types[nom], ligne[nom]) for nom in attendu.colonnes}
        for ligne in attendu.valeurs
    ]
    route, candidates = _candidates(attendu.fichier, cle, gold)
    calculees = [
        {nom: ligne.get(nom) for nom in attendu.colonnes}
        for ligne in candidates
        if all(ligne.get(nom) == valeur for nom, valeur in cle.items())
    ]
    if _multiensemble(calculees) == _multiensemble(attendues):
        return ResultatGold(question, VerdictGold.CONCORDE, route, f"{len(calculees)} ligne(s)")
    return ResultatGold(
        question,
        VerdictGold.DISCORDE,
        route,
        f"{len(attendues)} ligne(s) attendue(s), {len(calculees)} calculée(s)",
        attendues,
        calculees,
    )


def _multiensemble(lignes: list[Ligne]) -> Counter[str]:
    return Counter(
        json.dumps(en_json(ligne), sort_keys=True, ensure_ascii=False) for ligne in lignes
    )


def _candidates(entite: str, cle: Mapping[str, object], gold: _Gold) -> tuple[str, list[Ligne]]:
    """La route d'une question et les lignes qu'elle donne, avant le filtre sur la clé."""
    fiche = gold.vues.fiche
    if "code_cis" in cle and (entite == "bdpm.specialites" or entite in SECTIONS):
        indices = pc.index_in(pa.array([cle["code_cis"]], pa.string()), value_set=fiche["code_cis"])
        position = indices.to_pylist()[0]
        if position is None:
            return "fiche (code_cis)", []
        ligne = fiche.slice(position, 1).to_pylist()[0]
        if entite == "bdpm.specialites":
            return "fiche (code_cis)", [ligne] if ligne["dans_referentiel"] else []
        return "fiche (code_cis)", _section(ligne, SECTIONS[entite])
    if entite == "bdpm.presentations" and "code_cip13" in cle:
        listes = fiche["presentations"].combine_chunks()
        codes = pc.struct_field(pc.list_flatten(listes), "code_cip13")
        parents = pc.list_parent_indices(listes)
        lignes = []
        trouvees = pc.filter(parents, pc.equal(codes, pa.scalar(str(cle["code_cip13"]))))
        for position in trouvees.to_pylist():
            assert position is not None
            lignes += _section(fiche.slice(position, 1).to_pylist()[0], "presentations")
        return "fiche (code_cip13)", lignes
    if entite == "bdpm.generiques" and "identifiant_groupe" in cle:
        alternatives = gold.vues.alternatives
        groupe = alternatives.filter(
            pc.equal(alternatives["identifiant_groupe"], pa.scalar(str(cle["identifiant_groupe"])))
        )
        colonnes = [
            "identifiant_groupe",
            "libelle_groupe",
            "code_cis",
            "type_generique",
            "numero_tri",
        ]
        distinctes = {
            json.dumps(en_json(r), sort_keys=True): r for r in groupe.select(colonnes).to_pylist()
        }
        return "alternatives (identifiant_groupe)", list(distinctes.values())
    return "colonnes typées", gold.etats[entite].table.to_pylist()


def _section(fiche: Ligne, section: str) -> list[Ligne]:
    """Les éléments d'une section de la fiche, avec le CIS, dépliés selon ``occurrences``."""
    lignes = []
    for element in fiche[section] or ():
        lignes += [{"code_cis": fiche["code_cis"], **element}] * int(
            element.get("occurrences") or 1
        )
    return lignes


def formater(bilan: BilanGold) -> list[str]:
    """Une ligne par question (verdict, id, route, détail) ; les deux calculs d'une discordance."""
    largeur = max((len(r.verdict.value) for r in bilan.resultats), default=0)
    lignes = []
    for r in bilan.resultats:
        lignes.append(
            f"gold {r.verdict.value:<{largeur}}  {r.question.id:<20} {r.route} : {r.detail}"
        )
        if r.verdict is VerdictGold.DISCORDE:
            lignes.append(
                f"     attendu (bronze) : {json.dumps(en_json(r.attendues), ensure_ascii=False)}"
            )
            lignes.append(
                f"     calculé (gold)   : {json.dumps(en_json(r.calculees), ensure_ascii=False)}"
            )
    lignes.append(bilan.resume())
    return lignes
