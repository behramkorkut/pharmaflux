"""Du SQL libre sur le silver, en lecture seule et verrouillé (F.2, addendum 1).

DuckDB ne touche **aucun fichier** : chaque table du catalogue lui est donnée
comme un jeu de données Arrow (``pyarrow.dataset`` sur les Parquet de la
table, lus par Arrow, filtres poussés), et la connexion naît avec
``enable_external_access = false`` (plus aucune lecture ni écriture de
fichier, ni ``ATTACH``, ni ``INSTALL``), ``autoinstall_known_extensions`` et
``autoload_known_extensions`` à faux, ``TimeZone = UTC``, puis
``lock_configuration = true`` : un ``SET`` est refusé. Il n'y a pas
d'``allowed_directories`` : avec un dossier autorisé, DuckDB aurait pu
écrire dedans (``COPY … TO``), ce que la mesure du §0 a montré. Enfin, une
seule requête à la fois, et seulement un ``SELECT`` (ou ``EXPLAIN``) :
``CREATE``, ``COPY``, ``SET``… sont refusés avant d'être exécutés.
"""

from __future__ import annotations

import duckdb
import pyarrow as pa
import pyarrow.dataset as ds

from pharmaflux.silver import SilverRefuse
from pharmaflux.silver.entrepot import Entrepot, chemins_parquet, identifiant_table

CONFIGURATION: dict[str, str | bool | int | float | list[str]] = {
    "autoinstall_known_extensions": False,
    "autoload_known_extensions": False,
    "enable_external_access": False,
}
REGLAGES = ("SET TimeZone = 'UTC'", "SET lock_configuration = true")  # dans cet ordre
TYPES_PERMIS = (duckdb.StatementType.SELECT, duckdb.StatementType.EXPLAIN)


def connexion_verrouillee() -> duckdb.DuckDBPyConnection:
    """Une connexion en mémoire sans accès externe, en UTC, puis verrouillée."""
    con = duckdb.connect(config=CONFIGURATION)
    for reglage in REGLAGES:
        con.execute(reglage)
    return con


def connexion(entrepot: Entrepot) -> duckdb.DuckDBPyConnection:
    """Une connexion en mémoire, verrouillée, avec une vue par table : son nom court."""
    con = connexion_verrouillee()
    for entite in entrepot.entites():
        table = entrepot.table(entite)
        assert table is not None
        _, nom = identifiant_table(entite)
        chemins = chemins_parquet(table)
        schema = table.schema().as_arrow()
        jeu = ds.dataset(chemins, format="parquet", schema=schema) if chemins else _vide(schema)
        con.register(nom, jeu)
    return con


def executer(con: duckdb.DuckDBPyConnection, requete: str) -> pa.Table:
    """Le résultat d'une requête ``SELECT`` ; ``SilverRefuse`` pour tout autre énoncé."""
    try:
        enonces = duckdb.extract_statements(requete)
    except duckdb.Error as exc:
        raise SilverRefuse(f"requête illisible : {exc}") from exc
    if len(enonces) != 1:
        raise SilverRefuse(f"une seule requête à la fois ({len(enonces)} reçue(s))")
    if enonces[0].type not in TYPES_PERMIS:
        raise SilverRefuse(f"lecture seule : {enonces[0].type.name} refusé, seul SELECT est permis")
    try:
        return con.sql(requete).to_arrow_table()
    except duckdb.Error as exc:
        raise SilverRefuse(f"requête refusée : {exc}") from exc


def _vide(schema: pa.Schema) -> pa.Table:
    return schema.empty_table()
