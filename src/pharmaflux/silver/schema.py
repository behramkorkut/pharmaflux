"""Le schéma d'une table du silver et la fabrique d'une version depuis un événement (B).

Une table par entité : les colonnes du contrat, dans l'ordre du contrat,
toutes en chaînes (la valeur de l'événement, forme canonique ou brute :
le silver ne type rien, c'est le travail du gold), puis les colonnes de
version. ``identite`` est la clé du message du bus pour un fichier à clé
(l'objet JSON ``cle`` compact à clés triées), ``<empreinte>#<rang>`` pour un
fichier ligne à ligne. Les instants sont des ``timestamptz`` à la seconde,
en UTC, lus dans ``date_observation`` ; rien ne vient de l'horloge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

import pyarrow as pa

from pharmaflux.bus.enveloppe import cle_message
from pharmaflux.contrats.modele import Contrat
from pharmaflux.evenements.schema import Evenement
from pharmaflux.evenements.snapshot import Identite

COLONNES_VERSION = (
    "identite",
    "empreinte_ligne",
    "rang",
    "date_source",
    "debut_validite",
    "fin_validite",
    "id_ouverture",
    "id_fermeture",
    "archive_ouverture",
    "archive_fermeture",
    "version_contrat",
    "etat_initial",
    "anomalies",
)
TYPE_INSTANT = pa.timestamp("us", tz="UTC")
TYPE_ANOMALIES = pa.list_(
    pa.struct([pa.field("colonne", pa.string()), pa.field("regle", pa.string(), nullable=False)])
)
FORMAT_INSTANT = "%Y-%m-%dT%H:%M:%SZ"
SEPARATEUR_RANG = "#"

# Une version, telle que le code la manipule : colonne → valeur (chaînes, instants, liste).
Version = dict[str, object]


def schema_arrow(colonnes: Sequence[str]) -> pa.Schema:
    """Le schéma Arrow d'une table : les colonnes du contrat, puis celles de version."""
    for nom in colonnes:
        if nom in COLONNES_VERSION:
            raise ValueError(f"la colonne {nom} du contrat porte le nom d'une colonne de version")
    champs: list[Any] = [pa.field(nom, pa.string()) for nom in colonnes]
    champs += [
        pa.field("identite", pa.string(), nullable=False),
        pa.field("empreinte_ligne", pa.string(), nullable=False),
        pa.field("rang", pa.int32(), nullable=False),
        pa.field("date_source", pa.string()),
        pa.field("debut_validite", TYPE_INSTANT, nullable=False),
        pa.field("fin_validite", TYPE_INSTANT),
        pa.field("id_ouverture", pa.string(), nullable=False),
        pa.field("id_fermeture", pa.string()),
        pa.field("archive_ouverture", pa.string(), nullable=False),
        pa.field("archive_fermeture", pa.string()),
        pa.field("version_contrat", pa.string(), nullable=False),
        pa.field("etat_initial", pa.bool_(), nullable=False),
        pa.field("anomalies", TYPE_ANOMALIES, nullable=False),
    ]
    return pa.schema(champs)


def schema_du_contrat(contrat: Contrat) -> pa.Schema:
    return schema_arrow(contrat.noms_colonnes)


def colonnes_du_contrat(schema: pa.Schema) -> list[str]:
    """Les colonnes de données d'une table : tout ce qui n'est pas une colonne de version."""
    return [nom for nom in schema.names if nom not in COLONNES_VERSION]


def identite_de(evenement: Evenement) -> str:
    """La clé du message pour un fichier à clé, ``<empreinte>#<rang>`` sinon (B.1)."""
    if evenement.identite is Identite.CLE:
        return cle_message(evenement).decode("utf-8")
    return f"{evenement.empreinte_ligne}{SEPARATEUR_RANG}{evenement.rang}"


def instant(date_observation: str) -> datetime:
    """``2026-10-24T19:41:46Z`` → datetime UTC."""
    return datetime.strptime(date_observation, FORMAT_INSTANT).replace(tzinfo=UTC)


def texte_instant(valeur: datetime) -> str:
    """Un instant écrit comme les événements l'écrivent : ``…Z``, à la seconde."""
    return valeur.astimezone(UTC).strftime(FORMAT_INSTANT)


def litteral(valeur: datetime) -> str:
    """Le littéral qu'une expression PyIceberg accepte pour un ``timestamptz`` : ``+00:00``, pas
    ``Z``."""
    return valeur.astimezone(UTC).isoformat()


def version_ouverte(evenement: Evenement, colonnes: Sequence[str]) -> Version:
    """La version qu'une ``creee`` ou une ``modifiee`` ouvre, ``fin_validite`` nulle."""
    assert evenement.apres is not None
    apres = evenement.apres
    version: Version = {nom: apres.get(nom) for nom in colonnes}
    version.update(
        identite=identite_de(evenement),
        empreinte_ligne=evenement.empreinte_ligne,
        rang=evenement.rang,
        date_source=evenement.date_source,
        debut_validite=instant(evenement.date_observation),
        fin_validite=None,
        id_ouverture=evenement.id,
        id_fermeture=None,
        archive_ouverture=evenement.archive,
        archive_fermeture=None,
        version_contrat=evenement.version_contrat,
        etat_initial=evenement.etat_initial,
        anomalies=[
            {"colonne": colonne, "regle": regle.value} for colonne, regle in evenement.anomalies
        ],
    )
    return version


def fermer(version: Version, evenement: Evenement) -> None:
    """Ferme ``version`` par une ``modifiee`` ou une ``supprimee`` : borne de fin exclue."""
    version["fin_validite"] = instant(evenement.date_observation)
    version["id_fermeture"] = evenement.id
    version["archive_fermeture"] = evenement.archive


def table_arrow(versions: Sequence[Mapping[str, object]], schema: pa.Schema) -> pa.Table:
    return pa.Table.from_pylist(list(versions), schema=schema)


class ColonnesVersion:
    """Des versions ouvertes accumulées colonne par colonne : aucun dictionnaire par version.

    Pour l'état initial (32 000 ``creee`` d'un coup), les dictionnaires
    pesaient plus que les événements eux-mêmes. ``ouvrir`` rend ``marque``,
    un jeton qui tient la place de la version dans l'index des ouvertes.
    """

    marque: ClassVar[Version] = {"directe": True}

    def __init__(self, schema: pa.Schema, colonnes: Sequence[str]) -> None:
        self.schema = schema
        self.colonnes = tuple(colonnes)
        self.listes: dict[str, list[object]] = {nom: [] for nom in schema.names}

    def ouvrir(self, evenement: Evenement) -> Version:
        assert evenement.apres is not None
        apres = evenement.apres
        listes = self.listes
        for nom in self.colonnes:
            listes[nom].append(apres.get(nom))
        listes["identite"].append(identite_de(evenement))
        listes["empreinte_ligne"].append(evenement.empreinte_ligne)
        listes["rang"].append(evenement.rang)
        listes["date_source"].append(evenement.date_source)
        listes["debut_validite"].append(instant(evenement.date_observation))
        listes["fin_validite"].append(None)
        listes["id_ouverture"].append(evenement.id)
        listes["id_fermeture"].append(None)
        listes["archive_ouverture"].append(evenement.archive)
        listes["archive_fermeture"].append(None)
        listes["version_contrat"].append(evenement.version_contrat)
        listes["etat_initial"].append(evenement.etat_initial)
        listes["anomalies"].append(
            [{"colonne": colonne, "regle": regle.value} for colonne, regle in evenement.anomalies]
        )
        return self.marque

    def table(self) -> pa.Table:
        return pa.table(self.listes, schema=self.schema)
