"""L'entrepôt local : un catalogue SQL de PyIceberg sur SQLite, une table Iceberg par entité (A).

Un dossier sous ``data/``, hors de git, aucun service : ``catalogue.sqlite``
à sa racine, les tables dessous (``bdpm/presentations/…``). Le commit du
catalogue est atomique (le nouveau ``metadata.json`` est écrit, puis la
ligne SQLite est mise à jour si elle pointe encore vers l'ancien). PyIceberg
veut un entrepôt ``file://`` absolu, qu'il écrit dans chaque métadonnée : un
entrepôt déplacé ne se relit pas, on le rebâtit. Chaque table porte dans ses
propriétés l'entité, la version du contrat et l'origine de ses événements
(``fichiers`` ou ``bus``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NoSuchNamespaceError, NoSuchTableError
from pyiceberg.table import Table

from pharmaflux.contrats.modele import Contrat
from pharmaflux.silver import SilverRefuse
from pharmaflux.silver.schema import schema_du_contrat

NOM_CATALOGUE = "catalogue.sqlite"
PROP_ENTITE = "pharmaflux.entite"
PROP_VERSION_CONTRAT = "pharmaflux.version_contrat"
PROP_ORIGINE = "pharmaflux.origine"
PROP_POSITIONS = "pharmaflux.positions"  # consommateur du bus (mission 05, palier 2)
ORIGINE_FICHIERS = "fichiers"
ORIGINE_BUS = "bus"


def allocateur_systeme() -> None:
    """L'allocateur système d'Arrow : 100 à 250 Mo résidents de moins que jemalloc (§0 J)."""
    pa.set_memory_pool(pa.system_memory_pool())


def identifiant_table(entite: str) -> tuple[str, str]:
    """``bdpm.presentations`` → espace de noms ``bdpm``, table ``presentations``."""
    source, _, nom = entite.partition(".")
    if not source or not nom:
        raise ValueError(f"entité {entite!r} : <source>.<nom> attendu")
    return source, nom


@dataclass(frozen=True, slots=True)
class Entrepot:
    dossier: Path
    catalogue: SqlCatalog

    @classmethod
    def creer(cls, dossier: Path) -> Entrepot:
        """Un entrepôt neuf ; refusé si le dossier existe et n'est pas vide (rien n'est effacé)."""
        if dossier.exists() and any(dossier.iterdir()):
            raise SilverRefuse(
                f"{dossier} n'est pas vide : supprime-le ou choisis un autre --entrepot"
            )
        dossier.mkdir(parents=True, exist_ok=True)
        return cls(dossier, _catalogue(dossier))

    @classmethod
    def ouvrir(cls, dossier: Path) -> Entrepot:
        """Un entrepôt existant ; refusé sans catalogue."""
        if not (dossier / NOM_CATALOGUE).is_file():
            raise SilverRefuse(f"aucun entrepôt dans {dossier} ({NOM_CATALOGUE} absent)")
        return cls(dossier, _catalogue(dossier))

    def entites(self) -> list[str]:
        """Les entités qui ont une table, triées."""
        entites = []
        for espace in self.catalogue.list_namespaces():
            for identifiant in self.catalogue.list_tables(espace):
                entites.append(".".join(identifiant))
        return sorted(entites)

    def table(self, entite: str) -> Table | None:
        try:
            return self.catalogue.load_table(identifiant_table(entite))
        except (NoSuchTableError, NoSuchNamespaceError):
            return None

    def creer_table(self, contrat: Contrat, origine: str) -> Table:
        """La table d'une entité, vide, au schéma du contrat ; refusée si elle existe."""
        source, nom = identifiant_table(contrat.identifiant)
        self.catalogue.create_namespace_if_not_exists(source)
        if self.table(contrat.identifiant) is not None:
            raise SilverRefuse(f"la table {contrat.identifiant} existe déjà dans {self.dossier}")
        return self.catalogue.create_table(
            (source, nom),
            schema=schema_du_contrat(contrat),
            properties={
                PROP_ENTITE: contrat.identifiant,
                PROP_VERSION_CONTRAT: contrat.version,
                PROP_ORIGINE: origine,
            },
        )


def _catalogue(dossier: Path) -> SqlCatalog:
    absolu = dossier.resolve()
    return SqlCatalog(
        "pharmaflux",
        uri=f"sqlite:///{absolu / NOM_CATALOGUE}",
        warehouse=absolu.as_uri(),
    )


def verifier_contrat(table: Table, contrat: Contrat) -> None:
    """La table et le contrat ont la même version, sinon refus : le silver se rebâtit."""
    version = table.properties.get(PROP_VERSION_CONTRAT)
    if version != contrat.version:
        raise SilverRefuse(
            f"le contrat {contrat.identifiant} est passé de {version} à {contrat.version} :"
            " rebâtis le silver"
        )


def chemins_parquet(table: Table) -> list[str]:
    """Les fichiers de données de la table courante ; refus s'il existe un fichier de suppression.

    PyIceberg écrit en copie à l'écriture : il n'y a pas de fichier de
    suppression. S'il en apparaissait un (une autre bibliothèque a écrit),
    lire les Parquet seuls rendrait des lignes supprimées : on refuse.
    """
    chemins = []
    for tache in table.scan().plan_files():
        if tache.delete_files:
            raise SilverRefuse(
                f"{table.name()} : un fichier de suppression Iceberg existe, la lecture directe"
                " des Parquet est refusée"
            )
        chemins.append(tache.file.file_path.removeprefix("file://"))
    return sorted(chemins)
