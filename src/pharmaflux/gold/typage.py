"""L'état typé d'une entité à un instant : chaque colonne au type de son contrat (addendum 1, A).

Le typage part de la valeur du silver **et de ses anomalies**, jamais de la
valeur seule :

1. une valeur vide est typée vide (nulle) ;
2. une valeur dont la version porte, pour cette colonne, une règle de
   lisibilité (``REGLES_DE_LISIBILITE``) est brute : elle est typée vide, on ne
   la relit pas. Un prix écrit ``12.50`` dans la source est illisible pour le
   contrat (virgule attendue) et voyage brut ; un ``CAST`` le lirait comme
   12,50 € : ce serait deviner ;
3. sinon la valeur est canonique (PRD §6.2) et se convertit par une règle
   stricte sur la forme canonique. Une valeur sans règle de lisibilité que
   cette règle refuse n'est pas typée vide en silence : elle est comptée
   (``non_typables``), et le contrôle de qualité n° 3 la tient pour bloquante.

Les types : ``texte``, ``code``, ``url``, ``enumeration`` → ``string`` ;
``entier`` → ``int64`` ; ``decimal`` → ``decimal128(18, d)`` (``d`` du contrat :
un prix reste exact) ; ``date`` → ``date32`` ; ``booleen`` → ``bool`` ;
``liste`` → ``list<T>``, découpée sur le séparateur du contrat, un élément non
typable rendant toute la liste vide. Une liste vide dans la source est nulle,
pas vide : la source ne dit pas « aucun taux », elle ne dit rien.

L'état garde les colonnes de version de ``COLONNES_VERSION_GOLD`` et ajoute
``colonnes_illisibles`` : les colonnes vidées par une règle de lisibilité, pour
qu'un vide se distingue d'une absence.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import pyarrow as pa
import pyarrow.compute as pc

from pharmaflux.contrats.modele import Contrat, TypeNom, TypeValeur
from pharmaflux.contrats.normalisation import REGLES_DE_LISIBILITE
from pharmaflux.gold import COLONNES_ILLISIBLES, COLONNES_VERSION_GOLD
from pharmaflux.silver import SilverRefuse
from pharmaflux.silver.entrepot import Entrepot
from pharmaflux.silver.etat import bornes, etat_a

# DuckDB range une précision 18 sur 64 bits ; le plus grand prix du jeu a 5 chiffres entiers.
PRECISION_DECIMALE = 18
type Tableau = pa.Array[Any]  # alias paresseux : pa.Array ne s'indice pas à l'exécution
_LISIBILITE = frozenset(regle.value for regle in REGLES_DE_LISIBILITE)

# Les formes canoniques admises, par type (``normalisation._canonique``). Les bornes de longueur
# gardent la conversion dans son type : 18 chiffres pour un ``int64``, 16 avant la virgule pour
# un ``decimal128(18, 2)``.
_ENTIER = r"^-?(0|[1-9][0-9]{0,17})$"
_DATE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
_TYPES_CHAINE = frozenset({TypeNom.TEXTE, TypeNom.CODE, TypeNom.URL, TypeNom.ENUMERATION})
_TYPES_ARROW: dict[TypeNom, pa.DataType] = {
    TypeNom.ENTIER: pa.int64(),
    TypeNom.DATE: pa.date32(),
    TypeNom.BOOLEEN: pa.bool_(),
}


def type_arrow(type_: TypeValeur) -> pa.DataType:
    """Le type Arrow d'une colonne du gold, donné par son type de contrat."""
    if type_.nom in _TYPES_CHAINE:
        return pa.string()
    if type_.nom is TypeNom.DECIMAL:
        return pa.decimal128(PRECISION_DECIMALE, type_.decimales)
    if type_.nom is TypeNom.LISTE:
        assert type_.de is not None
        return pa.list_(type_arrow(type_.de))
    return _TYPES_ARROW[type_.nom]


@dataclass(frozen=True, slots=True)
class EntiteTypee:
    """L'état typé d'une entité, et ce que le typage a compté en chemin."""

    entite: str
    contrat: Contrat
    table: pa.Table
    illisibles: dict[tuple[str, str], int]  # (colonne, règle de lisibilité) → versions
    autres_anomalies: dict[tuple[str, str], int]  # (colonne, autre règle) → versions
    non_typables: dict[str, int]  # colonne → valeurs canoniques que le type refuse
    doublons_cle: int | None  # lignes en trop sur la clé déclarée unique ; None sinon
    doublons_identite: int  # versions en trop sur l'identité


def typer_valeurs(valeurs: Tableau, type_: TypeValeur) -> tuple[Tableau, pa.BooleanArray]:
    """Les valeurs typées, et le masque des valeurs non nulles que la forme canonique refuse.

    ``valeurs`` est une colonne de chaînes où le vide et l'illisible sont déjà nuls.
    """
    if type_.nom in _TYPES_CHAINE:
        return valeurs.cast(pa.string()), _masque([False] * len(valeurs))
    if type_.nom is TypeNom.LISTE:
        return _typer_liste(valeurs, type_)
    lisible: pa.BooleanArray
    typees: Tableau
    if type_.nom is TypeNom.BOOLEEN:
        lisible = pc.is_in(valeurs, value_set=pa.array(["true", "false"]))
        typees = _garder(pc.equal(valeurs, pa.scalar("true")), lisible)
    elif type_.nom is TypeNom.ENTIER:
        lisible = pc.match_substring_regex(valeurs, _ENTIER)
        typees = _garder(valeurs, lisible).cast(pa.int64())
    elif type_.nom is TypeNom.DECIMAL:
        entiers = PRECISION_DECIMALE - type_.decimales
        motif = rf"^-?(0|[1-9][0-9]{{0,{entiers - 1}}})\.[0-9]{{{type_.decimales}}}$"
        lisible = pc.match_substring_regex(valeurs, motif)
        typees = _garder(valeurs, lisible).cast(type_arrow(type_))
    else:  # date : la forme ISO, puis le calendrier (un 30 février est refusé)
        assert type_.nom is TypeNom.DATE
        bien_formees = _garder(valeurs, pc.match_substring_regex(valeurs, _DATE))
        instants = pc.strptime(bien_formees, format="%Y-%m-%d", unit="s", error_is_null=True)
        # strptime d'Arrow est indulgent (« 2026-02-30 » donne le 2 mars) : la date relue doit
        # redonner la chaîne, sinon elle n'existe pas au calendrier.
        lisible = pc.equal(pc.strftime(instants, format="%Y-%m-%d"), bien_formees)
        typees = _garder(instants.cast(pa.date32()), lisible)
    refusees = pc.and_(pc.is_valid(valeurs), pc.invert(_sans_nul(lisible)))
    return typees, refusees


def _masque(valeurs: list[bool]) -> pa.BooleanArray:
    return pa.array(valeurs, pa.bool_())


def _sans_nul(masque: pa.BooleanArray) -> pa.BooleanArray:
    """Un masque où nul vaut faux."""
    return cast(pa.BooleanArray, pc.fill_null(masque, pa.scalar(False)))


def _garder(valeurs: Tableau, masque: pa.BooleanArray) -> Tableau:
    """Les valeurs où le masque est vrai, nulles ailleurs."""
    return cast(Tableau, pc.if_else(_sans_nul(masque), valeurs, pa.scalar(None, valeurs.type)))


def _typer_liste(valeurs: Tableau, type_: TypeValeur) -> tuple[Tableau, pa.BooleanArray]:
    """Découpe sur le séparateur du contrat, type chaque élément ; un refus vide la liste."""
    assert type_.de is not None and type_.separateur is not None
    decalages, morceaux, parents = [0], [], []
    for ligne, valeur in enumerate(valeurs.to_pylist()):
        if valeur is not None:
            elements = valeur.split(type_.separateur)
            morceaux += elements
            parents += [ligne] * len(elements)
        decalages.append(len(morceaux))
    elements_types, refuses = typer_valeurs(pa.array(morceaux, pa.string()), type_.de)
    lignes_refusees = {parents[i] for i, refuse in enumerate(refuses.to_pylist()) if refuse}
    refusees = _masque([i in lignes_refusees for i in range(len(valeurs))])
    masque = pc.or_(pc.is_null(valeurs), refusees)
    typees = pa.ListArray.from_arrays(
        pa.array(decalages, pa.int32()),
        elements_types.cast(type_arrow(type_.de)),
        type=type_arrow(type_),
        mask=masque,
    )
    return typees, refusees


def typer_etat(entite: str, contrat: Contrat, etat: pa.Table) -> EntiteTypee:
    """L'état typé, depuis l'état du silver (chaînes et anomalies) d'une entité."""
    nombre = etat.num_rows
    illisibles: Counter[tuple[str, str]] = Counter()
    autres: Counter[tuple[str, str]] = Counter()
    videes: dict[str, set[int]] = {}  # colonne → lignes vidées par une règle de lisibilité
    par_ligne: list[list[str]] = []
    for ligne, anomalies in enumerate(etat["anomalies"].to_pylist()):
        illisibles_ligne = []
        for anomalie in anomalies or []:
            colonne, regle = anomalie["colonne"], anomalie["regle"]
            if colonne is None:
                continue
            if regle in _LISIBILITE:
                illisibles[(colonne, regle)] += 1
                videes.setdefault(colonne, set()).add(ligne)
                illisibles_ligne.append(colonne)
            else:
                autres[(colonne, regle)] += 1
        par_ligne.append(illisibles_ligne)

    colonnes: dict[str, Tableau | pa.ChunkedArray[Any]] = {}
    non_typables: dict[str, int] = {}
    for colonne in contrat.colonnes:
        brutes = etat[colonne.nom].combine_chunks().cast(pa.string())
        lignes_videes = videes.get(colonne.nom, set())
        vides = pc.or_(
            pc.equal(brutes, pa.scalar("")), _masque([i in lignes_videes for i in range(nombre)])
        )
        valeurs = _garder(brutes, pc.invert(vides))
        typees, refusees = typer_valeurs(valeurs, colonne.type)
        if refuses := sum(1 for refusee in refusees.to_pylist() if refusee):
            non_typables[colonne.nom] = refuses
            typees = _garder(typees, pc.invert(refusees))
        colonnes[colonne.nom] = typees
    for nom in COLONNES_VERSION_GOLD:
        colonnes[nom] = etat[nom]
    colonnes[COLONNES_ILLISIBLES] = pa.array(par_ligne, pa.list_(pa.string()))

    doublons_cle = None
    if contrat.cle.unique:
        cles = list(contrat.cle.colonnes)
        doublons_cle = nombre - etat.select(cles).group_by(cles).aggregate([]).num_rows
    identites = len(set(etat["identite"].to_pylist()))
    return EntiteTypee(
        entite=entite,
        contrat=contrat,
        table=pa.table(colonnes),
        illisibles=dict(illisibles),
        autres_anomalies=dict(autres),
        non_typables=non_typables,
        doublons_cle=doublons_cle,
        doublons_identite=nombre - identites,
    )


def etat_type(
    entrepot: Entrepot,
    contrat: Contrat,
    instant: datetime,
    filtres: Mapping[str, str] | None = None,
) -> EntiteTypee:
    """L'état typé d'une entité à ``instant`` ; ``filtres`` : égalité sur la valeur du silver."""
    table = entrepot.table(contrat.identifiant)
    if table is None:
        raise SilverRefuse(f"aucune table {contrat.identifiant} dans {entrepot.dossier}")
    return typer_etat(contrat.identifiant, contrat, etat_a(table, instant, filtres))


def derniere_observation(entrepot: Entrepot) -> datetime | None:
    """L'instant par défaut du gold : la dernière observation que le silver connaît."""
    dernieres = []
    for entite in entrepot.entites():
        table = entrepot.table(entite)
        assert table is not None
        _, derniere = bornes(table)
        if derniere is not None:
            dernieres.append(derniere)
    return max(dernieres, default=None)


__all__ = [
    "EntiteTypee",
    "derniere_observation",
    "etat_type",
    "type_arrow",
    "typer_etat",
    "typer_valeurs",
]
