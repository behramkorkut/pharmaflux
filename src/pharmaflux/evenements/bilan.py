"""Bilan par archive lue : les mesures du snapshot, le verdict, l'écart avec le dernier retenu.

Une mesure, jamais une alerte (alertes au Lot 5) : le bilan ne change pas le
code de sortie. Le compte attendu d'anomalies connues de la mission 01 devient
une différence lisible entre deux bilans, sans seuil ni tolérance dans un
contrat. ``en_dict`` donne la forme écrite en JSON par ``rejeu``, sans rien
qui dépende de l'horloge.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from pharmaflux.contrats.modele import Regle
from pharmaflux.evenements.schema import VERSION_SCHEMA
from pharmaflux.evenements.snapshot import BilanSnapshot, Snapshot
from pharmaflux.evenements.volume import Resultat, Verdict


@dataclass(frozen=True, slots=True)
class Ecart:
    """La différence avec le dernier snapshot retenu, quand il y en a un."""

    archive_retenue: str
    lignes: int  # nouveau moins retenu, lignes bien formées
    entites: int
    anomalies: tuple[tuple[Regle, int, int], ...]  # règle, compte retenu, compte nouveau
    evenements: tuple[tuple[str, int], ...]  # type → nombre (vide si le snapshot n'est pas comparé)


@dataclass(frozen=True, slots=True)
class BilanArchive:
    snapshot: BilanSnapshot
    verdict: Verdict
    ecart: Ecart | None


def etablir(resultat: Resultat, comptes: Mapping[str, int] | None = None) -> BilanArchive:
    """Le bilan d'un résultat du garde-fou.

    ``comptes`` : les événements par type, comptés par celui qui les a écrits
    (``rejeu``) ; sans lui, ils sont recomptés en rappelant la comparaison.
    """
    ecart = None
    if resultat.retenu_precedent is not None:
        if comptes is None:
            comptes = Counter(evenement.type.value for evenement in resultat.evenements())
        ecart = _ecart(resultat.retenu_precedent, resultat.snapshot, comptes)
    return BilanArchive(resultat.snapshot.bilan, resultat.verdict, ecart)


def _ecart(retenu: Snapshot, nouveau: Snapshot, comptes: Mapping[str, int]) -> Ecart:
    avant, apres = dict(retenu.bilan.anomalies), dict(nouveau.bilan.anomalies)
    regles = tuple(
        (regle, avant.get(regle, 0), apres.get(regle, 0))
        for regle in Regle
        if avant.get(regle, 0) != apres.get(regle, 0)
    )
    return Ecart(
        archive_retenue=retenu.archive,
        lignes=nouveau.bilan.lignes_bien_formees - retenu.bilan.lignes_bien_formees,
        entites=nouveau.bilan.entites - retenu.bilan.entites,
        anomalies=regles,
        evenements=tuple(sorted((type_, n) for type_, n in comptes.items() if n)),
    )


def en_dict(bilan: BilanArchive) -> dict[str, object]:
    """La forme JSON du bilan (clés triées à l'écriture par ``rejeu``)."""
    s = bilan.snapshot
    ecart = None
    if bilan.ecart is not None:
        ecart = {
            "archive_retenue": bilan.ecart.archive_retenue,
            "lignes": bilan.ecart.lignes,
            "entites": bilan.ecart.entites,
            "anomalies": [
                {"regle": regle.value, "retenu": a, "nouveau": b}
                for regle, a, b in bilan.ecart.anomalies
            ],
            "evenements": dict(bilan.ecart.evenements),
        }
    return {
        "version_schema": VERSION_SCHEMA,
        "archive": s.archive,
        "sha256": s.sha256,
        "version_contrat": s.version_contrat,
        "lignes": s.lignes,
        "lignes_bien_formees": s.lignes_bien_formees,
        "entites": s.entites,
        "occurrences_en_doublon": s.occurrences_en_doublon,
        "anomalies": {regle.value: n for regle, n in s.anomalies},
        "graphies": {colonne: dict(graphies) for colonne, graphies in s.graphies},
        "decision": bilan.verdict.decision.value,
        "motif": bilan.verdict.motif,
        "ecart": ecart,
    }
