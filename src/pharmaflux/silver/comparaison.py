"""Comparer deux entrepôts : mêmes tables, mêmes versions, mêmes validités (E).

Le silver ne dépend pas du chemin (PRD §7.1) : construit depuis le bus ou
depuis les fichiers d'événements, il a le même contenu. Sont comparées
toutes les colonnes de données et de version de chaque table, ligne à ligne
(``EXCEPT ALL`` dans les deux sens, en DuckDB sur des jeux Arrow, sans
accès fichier). Exclus, parce qu'ils ne peuvent pas être égaux : les
identifiants, horodatages et résumés des snapshots, le nombre de snapshots
et de fichiers Parquet, leurs noms, et les propriétés de table (positions,
origine, identifiant de grappe).
"""

from __future__ import annotations

import pyarrow.dataset as ds

from pharmaflux.silver.entrepot import Entrepot, chemins_parquet
from pharmaflux.silver.sql import connexion_verrouillee

EXEMPLES = 3


def comparer(a: Entrepot, b: Entrepot) -> list[str]:
    """Les différences entre ``a`` et ``b`` ; vide quand les deux silvers sont égaux."""
    differences: list[str] = []
    entites_a, entites_b = set(a.entites()), set(b.entites())
    for entite in sorted(entites_a - entites_b):
        differences.append(f"{entite} : table seulement dans {a.dossier}")
    for entite in sorted(entites_b - entites_a):
        differences.append(f"{entite} : table seulement dans {b.dossier}")
    for entite in sorted(entites_a & entites_b):
        table_a, table_b = a.table(entite), b.table(entite)
        assert table_a is not None and table_b is not None
        schema_a, schema_b = table_a.schema().as_arrow(), table_b.schema().as_arrow()
        if schema_a.names != schema_b.names:
            differences.append(
                f"{entite} : colonnes différentes ({', '.join(schema_a.names)} ;"
                f" {', '.join(schema_b.names)})"
            )
            continue
        con = connexion_verrouillee()
        for nom, table, schema in (("a", table_a, schema_a), ("b", table_b, schema_b)):
            chemins = chemins_parquet(table)
            jeu = (
                ds.dataset(chemins, format="parquet", schema=schema)
                if chemins
                else schema.empty_table()
            )
            con.register(nom, jeu)
        for gauche, droite, dossier in (("a", "b", a.dossier), ("b", "a", b.dossier)):
            manquantes = con.sql(
                f"SELECT identite, debut_validite FROM"
                f" (SELECT * FROM {gauche} EXCEPT ALL SELECT * FROM {droite})"
                " ORDER BY identite, debut_validite"
            ).to_arrow_table()
            if manquantes.num_rows:
                exemples = ", ".join(
                    f"{identite} dès {debut:%Y-%m-%dT%H:%M:%SZ}"
                    for identite, debut in zip(
                        manquantes["identite"].to_pylist()[:EXEMPLES],
                        manquantes["debut_validite"].to_pylist()[:EXEMPLES],
                        strict=True,
                    )
                )
                suite = " …" if manquantes.num_rows > EXEMPLES else ""
                differences.append(
                    f"{entite} : {manquantes.num_rows} version(s) seulement dans {dossier} :"
                    f" {exemples}{suite}"
                )
        con.close()
    return differences
