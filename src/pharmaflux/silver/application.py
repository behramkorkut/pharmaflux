"""Appliquer un lot d'événements à une table du silver : le SCD2 sur la date d'observation (C).

Une ``creee`` ouvre une version ; une ``modifiee`` ferme la version ouverte de
son identité et en ouvre une autre ; une ``supprimee`` ferme. La borne de fin
est exclue. Le lot est appliqué dans l'ordre reçu, qui est l'ordre d'une
partition du bus ou d'un fichier d'événements : l'ordre par identité suffit
(§0 C). La même fonction sert au bus et aux fichiers.

Idempotence : un événement dont l'``id`` est déjà une ouverture ou une
fermeture de la table ne change rien, il est compté. Refus
(``FluxIncoherent``, rien du lot n'est écrit) : ``modifiee`` ou ``supprimee``
sans version ouverte, ``creee`` sur une identité ouverte, rang incohérent
pour un fichier ligne à ligne, plusieurs versions ouvertes pour une identité,
version de contrat différente de celle de la table.

Écriture : **une** transaction Iceberg par lot, dans l'ordre
``set_properties`` (la position du consommateur, s'il y en a une),
``delete`` des versions fermées (par leur ``id_ouverture``), ``append`` des
versions fermées réécrites et des versions ouvertes. PyIceberg écrit en
copie : le fichier Parquet qui portait une version fermée est réécrit sans
elle. Un commit produit un ``metadata.json`` et, quand il ferme, deux
snapshots (``delete`` puis ``append``) : c'est la façon d'écrire de
PyIceberg, et l'atomicité est celle du commit.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pyarrow as pa
from pyiceberg.expressions import BooleanExpression
from pyiceberg.table import Table

from pharmaflux.evenements.schema import Evenement, TypeEvenement
from pharmaflux.evenements.snapshot import Identite
from pharmaflux.silver import FluxIncoherent
from pharmaflux.silver.entrepot import PROP_ENTITE, PROP_VERSION_CONTRAT
from pharmaflux.silver.expressions import dans, est_nul, et, ou
from pharmaflux.silver.schema import (
    ColonnesVersion,
    Version,
    colonnes_du_contrat,
    fermer,
    identite_de,
    table_arrow,
    version_ouverte,
)


@dataclass(frozen=True, slots=True)
class ResultatLot:
    """Ce qu'un lot a fait : comptes, et si un commit a eu lieu."""

    evenements: int
    doublons: int
    ouvertures: int
    fermetures: int
    commit: bool


def appliquer_lot(
    table: Table,
    evenements: Sequence[Evenement],
    *,
    proprietes_table: Mapping[str, str] | None = None,
    proprietes_snapshot: Mapping[str, str] | None = None,
    origine: str = "",
) -> tuple[Table, ResultatLot]:
    """Applique ``evenements`` à ``table`` ; rend la table rechargée et le résultat.

    ``proprietes_table`` est posé dans la même transaction que les données
    (la position du consommateur) ; il est posé même quand le lot n'écrit
    rien (tout en doublon). ``proprietes_snapshot`` va dans le résumé des
    snapshots du lot. ``origine`` nomme le lot dans les messages de refus
    (un fichier, ou un topic et des offsets).
    """
    proprietes_table = dict(proprietes_table or {})
    proprietes_snapshot = dict(proprietes_snapshot or {})
    schema = table.schema().as_arrow()
    colonnes = colonnes_du_contrat(schema)
    entite = table.properties.get(PROP_ENTITE, "")
    version_contrat = table.properties.get(PROP_VERSION_CONTRAT)
    for evenement in evenements:
        if evenement.entite != entite:
            raise FluxIncoherent(
                _ou(origine, evenement, f"entité {evenement.entite}, table {entite}")
            )
        if evenement.version_contrat != version_contrat:
            raise FluxIncoherent(
                _ou(
                    origine,
                    evenement,
                    f"version de contrat {evenement.version_contrat}, table en"
                    f" {version_contrat} : rebâtis le silver",
                )
            )

    # Doublons : dans le lot, puis contre la table (un id déjà en ouverture ou en fermeture).
    uniques: list[Evenement] = []
    vus: set[str] = set()
    for evenement in evenements:
        if evenement.id not in vus:
            vus.add(evenement.id)
            uniques.append(evenement)
    ids = [evenement.id for evenement in uniques]
    if ids:
        connus = table.scan(
            row_filter=ou(dans("id_ouverture", ids), dans("id_fermeture", ids)),
            selected_fields=("id_ouverture", "id_fermeture"),
        ).to_arrow()
        deja = set(connus["id_ouverture"].to_pylist()) | set(connus["id_fermeture"].to_pylist())
        uniques = [evenement for evenement in uniques if evenement.id not in deja]
    doublons = len(evenements) - len(uniques)
    if not uniques:
        if proprietes_table:
            with table.transaction() as transaction:
                transaction.set_properties(proprietes_table)
            table = table.refresh()
        return table, ResultatLot(len(evenements), doublons, 0, 0, bool(proprietes_table))

    # Les versions ouvertes que le lot peut toucher : par identité, ou par empreinte pour un
    # fichier ligne à ligne (le rang d'une occurrence se compte sur toutes celles de l'empreinte).
    par_ligne = uniques[0].identite is Identite.LIGNE
    if par_ligne:
        filtre: BooleanExpression = dans(
            "empreinte_ligne", sorted({evenement.empreinte_ligne for evenement in uniques})
        )
    else:
        filtre = dans("identite", sorted({identite_de(evenement) for evenement in uniques}))
    lignes = table.scan(row_filter=et(filtre, est_nul("fin_validite"))).to_arrow().to_pylist()
    ouvertes: dict[str, Version] = {}
    for ligne in lignes:
        identite = str(ligne["identite"])
        if identite in ouvertes:
            raise FluxIncoherent(
                f"{entite} : plusieurs versions ouvertes pour l'identité {identite}"
                f" ({ouvertes[identite]['id_ouverture']}, {ligne['id_ouverture']}) : le silver"
                " est incohérent, rebâtis-le"
            )
        ouvertes[identite] = ligne
    depuis_table = set(ouvertes)
    occurrences: Counter[str] = Counter(str(v["empreinte_ligne"]) for v in ouvertes.values())

    # Les identités que le lot ferme : une version ouverte dans le lot pour l'une d'elles reste
    # un dictionnaire (elle peut être refermée) ; les autres vont droit en colonnes Arrow.
    fermees_dans_le_lot = {
        identite_de(evenement)
        for evenement in uniques
        if evenement.type in (TypeEvenement.MODIFIEE, TypeEvenement.SUPPRIMEE)
    }
    directes = ColonnesVersion(schema, colonnes)
    a_supprimer: list[str] = []  # id_ouverture des versions de la table que le lot ferme
    fermees: list[Version] = []
    ouvertures = fermetures = 0
    for evenement in uniques:
        identite = identite_de(evenement)
        empreinte = evenement.empreinte_ligne
        if evenement.type in (TypeEvenement.MODIFIEE, TypeEvenement.SUPPRIMEE):
            version = ouvertes.pop(identite, None)
            if version is None:
                raise FluxIncoherent(
                    _ou(origine, evenement, f"{evenement.type.value} sans version ouverte")
                )
            if par_ligne and occurrences[empreinte] != evenement.rang:
                raise FluxIncoherent(
                    _ou(
                        origine,
                        evenement,
                        f"suppression du rang {evenement.rang} sur {occurrences[empreinte]}"
                        " occurrence(s) ouverte(s)",
                    )
                )
            occurrences[empreinte] -= 1
            fermer(version, evenement)
            if identite in depuis_table:
                depuis_table.discard(identite)
                a_supprimer.append(str(version["id_ouverture"]))
            fermees.append(version)
            fermetures += 1
        if evenement.type in (TypeEvenement.CREEE, TypeEvenement.MODIFIEE):
            if identite in ouvertes:
                raise FluxIncoherent(
                    _ou(origine, evenement, "création d'une identité déjà ouverte")
                )
            if par_ligne and occurrences[empreinte] + 1 != evenement.rang:
                raise FluxIncoherent(
                    _ou(
                        origine,
                        evenement,
                        f"création du rang {evenement.rang} sur {occurrences[empreinte]}"
                        " occurrence(s) ouverte(s)",
                    )
                )
            occurrences[empreinte] += 1
            ouvertures += 1
            if identite in fermees_dans_le_lot:
                ouvertes[identite] = version_ouverte(evenement, colonnes)
            else:
                ouvertes[identite] = directes.ouvrir(evenement)

    nouvelles = [
        v
        for identite, v in ouvertes.items()
        if identite not in depuis_table and v is not directes.marque
    ]
    a_ecrire = pa.concat_tables([table_arrow([*fermees, *nouvelles], schema), directes.table()])
    with table.transaction() as transaction:
        if proprietes_table:
            transaction.set_properties(proprietes_table)
        if a_supprimer:
            transaction.delete(
                dans("id_ouverture", a_supprimer), snapshot_properties=proprietes_snapshot
            )
        if a_ecrire.num_rows:
            transaction.append(a_ecrire, snapshot_properties=proprietes_snapshot)
    return table.refresh(), ResultatLot(len(evenements), doublons, ouvertures, fermetures, True)


def _ou(origine: str, evenement: Evenement, motif: str) -> str:
    """Le message d'un refus : où, quel événement, pourquoi."""
    tete = f"{origine} : " if origine else ""
    return (
        f"{tete}{evenement.entite} {evenement.type.value} {evenement.id} (identité"
        f" {identite_de(evenement)}, archive {evenement.archive}, observée"
        f" {evenement.date_observation}) : {motif}"
    )
