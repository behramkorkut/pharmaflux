"""Les médicaments que la mise à jour de l'index doit recalculer, entre deux instants (ADR 0011).

L'index suit le **silver**, pas le bus (addendum 1 E) : il lit le gold, il ne
peut donc pas être en avance sur le silver, et il n'a pas de position de bus
à garder. Entre l'instant de l'index ``t0`` et la dernière observation du
silver ``t1``, un CIS est touché :

- par une **version** d'une entité de la fiche ouverte ou fermée dans
  ``]t0, t1]`` : son ``code_cis`` (la disponibilité porte le CIS même sans
  CIP13 ; un groupe générique ne touche que le CIS de sa ligne, les
  alternatives n'étant pas dans les fragments) ;
- par un **lien vers un avis de la CT** changé : les CIS dont un avis SMR ou
  ASMR porte ce dossier, à ``t0`` et à ``t1`` ;
- par une **bascule du jour**, sans aucune version (addendum 1 E1) : un
  signalement dont le début annoncé tombe dans ``]jour(t0), jour(t1)]``, une
  information importante qui entre dans sa fenêtre (début dans ``]jour(t0),
  jour(t1)]``) ou en sort (fin dans ``[jour(t0), jour(t1)[``).

Ce module lit le silver (PyArrow, PyIceberg) : il tourne dans le
sous-processus des fragments, jamais dans celui de l'encodage.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

import pyarrow as pa
import pyarrow.compute as pc

from pharmaflux.gold.typage import EntiteTypee
from pharmaflux.gold.vues import ENTITES_FICHE, jour
from pharmaflux.silver.entrepot import Entrepot
from pharmaflux.silver.etat import etat_a
from pharmaflux.silver.expressions import et, inferieur_ou_egal, ou, superieur
from pharmaflux.silver.schema import litteral


@dataclass(frozen=True, slots=True)
class Touches:
    cis: frozenset[str]
    par_version: int  # CIS touchés par une version ouverte ou fermée
    par_bascule: (
        int  # CIS touchés par une bascule du jour (qu'une version ait aussi touchés ou non)
    )


def cis_touches(
    entrepot: Entrepot, etats: Mapping[str, EntiteTypee], t0: datetime, t1: datetime
) -> Touches:
    """Les CIS dont les fragments ont pu changer entre ``t0`` et ``t1`` (``etats`` : à ``t1``)."""
    par_version: set[str] = set()
    for entite in ENTITES_FICHE:
        par_version |= _valeurs(_changees(entrepot, entite, t0, t1), "code_cis")
    dossiers = _valeurs(_changees(entrepot, "bdpm.liens_ct", t0, t1), "code_dossier_has")
    if dossiers:
        for instant in (t0, t1):
            for entite in ("bdpm.smr", "bdpm.asmr"):
                table = entrepot.table(entite)
                assert table is not None
                avis = etat_a(table, instant)
                avis = avis.filter(pc.is_in(avis["code_dossier_has"], pa.array(sorted(dossiers))))
                par_version |= _valeurs(avis, "code_cis")
    par_bascule = bascules_du_jour(etats, jour(t0), jour(t1))
    return Touches(frozenset(par_version | par_bascule), len(par_version), len(par_bascule))


def bascules_du_jour(etats: Mapping[str, EntiteTypee], j0: date, j1: date) -> set[str]:
    """Les CIS dont un signalement commence, ou une information entre ou sort, entre deux jours."""
    if j1 <= j0:
        return set()
    touches = set()
    dispo = etats["bdpm.disponibilite"].table.select(["code_cis", "date_debut"]).to_pylist()
    for ligne in dispo:
        if ligne["date_debut"] is not None and j0 < ligne["date_debut"] <= j1:
            touches.add(str(ligne["code_cis"]))
    infos = etats["bdpm.infos_importantes"].table
    for ligne in infos.select(["code_cis", "date_debut", "date_fin"]).to_pylist():
        entre = ligne["date_debut"] is not None and j0 < ligne["date_debut"] <= j1
        sort = ligne["date_fin"] is not None and j0 <= ligne["date_fin"] < j1
        if entre or sort:
            touches.add(str(ligne["code_cis"]))
    return touches


def _changees(entrepot: Entrepot, entite: str, t0: datetime, t1: datetime) -> pa.Table:
    """Les versions de ``entite`` ouvertes ou fermées dans ``]t0, t1]``."""
    table = entrepot.table(entite)
    assert table is not None, f"aucune table {entite}"
    a, b = litteral(t0), litteral(t1)
    ouvertes = et(superieur("debut_validite", a), inferieur_ou_egal("debut_validite", b))
    fermees = et(superieur("fin_validite", a), inferieur_ou_egal("fin_validite", b))
    return table.scan(row_filter=ou(ouvertes, fermees)).to_arrow()


def _valeurs(table: pa.Table, colonne: str) -> set[str]:
    return {str(v) for v in table[colonne].to_pylist() if v is not None}
