"""L'événement, version 1 du schéma : structure typée, identifiant déterministe, JSON stable.

Un événement dit qu'une entité d'un fichier source a été créée, modifiée ou
supprimée entre deux archives retenues (ADR 0006). Toutes les valeurs de
données sont des **chaînes** normalisées (ADR 0005) : rien ne devient un
nombre JSON. Rien ne dépend de l'horloge ni du poste : les dates viennent du
nom de l'archive et du manifeste, les chemins sont relatifs à la racine.

L'identifiant est le sha256 de ``entite``, ``archive``, ``archive_precedente``,
``type`` et ``identite_de_ligne``, joints par ``\\x1f`` : les deux archives y
entrent par leur chemin relatif, pour qu'une oscillation A → B → A → B donne
des identifiants distincts à chaque comparaison.

**Rien ne dépend de l'ordre d'un objet JSON** (contrôle du palier 2) :
``cle``, ``avant`` et ``apres`` sont des objets colonne → valeur, et tout ce
qui en dérive (identité de ligne, ordre de tri, état rejoué) prend les
colonnes dans l'ordre alphabétique de leur nom, qui est aussi l'ordre écrit
par ``serialiser`` (clés triées à tous les niveaux). Un événement relu est
égal à l'événement écrit, et un consommateur qui veut l'ordre des colonnes
du fichier le trouve dans le contrat que ``entite`` et ``version_contrat``
désignent.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from pharmaflux.contrats.modele import Regle
from pharmaflux.evenements.snapshot import SEPARATEUR_EMPREINTE, Identite

VERSION_SCHEMA = 1


class TypeEvenement(StrEnum):
    CREEE = "creee"
    MODIFIEE = "modifiee"
    SUPPRIMEE = "supprimee"


# Pour une même clé, la suppression précède la modification, qui précède la création.
ORDRE_TYPES = {TypeEvenement.SUPPRIMEE: 0, TypeEvenement.MODIFIEE: 1, TypeEvenement.CREEE: 2}


@dataclass(frozen=True, slots=True)
class Evenement:
    """Un événement du schéma v1 ; ``serialiser`` en donne la ligne JSON."""

    id: str  # sha256 hexadécimal, ``identifiant``
    entite: str  # identifiant du catalogue et du contrat (``bdpm.presentations``)
    fichier: str
    version_contrat: str
    type: TypeEvenement
    etat_initial: bool  # vrai pour les ``creee`` du premier snapshot d'un fichier
    identite: Identite
    cle: Mapping[str, str]  # colonnes de la clé déclarée (unique ou non) → valeur normalisée
    empreinte_ligne: str  # de la ligne après, ou avant pour ``supprimee``
    rang: int  # occurrence dans le multiensemble, 1 sauf doublon
    avant: Mapping[str, str] | None  # état normalisé avant, None pour ``creee``
    apres: Mapping[str, str] | None  # état normalisé après, None pour ``supprimee``
    champs_modifies: tuple[str, ...]  # vide sauf ``modifiee``, dans l'ordre du contrat
    anomalies: tuple[tuple[str | None, Regle], ...]  # de la ligne après (avant pour supprimee)
    date_source: str | None  # ``date_source_affichee`` du manifeste, AAAA-MM-JJ
    date_observation: str  # horodatage de l'archive, ISO UTC
    archive: str
    archive_sha256: str
    archive_precedente: str | None
    archive_precedente_sha256: str | None

    @property
    def identite_de_ligne(self) -> str:
        return identite_de_ligne(self.identite, self.cle, self.empreinte_ligne, self.rang)

    def cle_de_tri(self) -> tuple[tuple[str, ...], int, str, int]:
        """Clé normalisée, puis supprimee < modifiee < creee, puis empreinte, puis rang."""
        return (valeurs_de_cle(self.cle), ORDRE_TYPES[self.type], self.empreinte_ligne, self.rang)


def valeurs_de_cle(cle: Mapping[str, str]) -> tuple[str, ...]:
    """Les valeurs de la clé dans l'ordre alphabétique des colonnes : jamais celui de l'objet."""
    return tuple(cle[nom] for nom in sorted(cle))


def identite_de_ligne(identite: Identite, cle: Mapping[str, str], empreinte: str, rang: int) -> str:
    """Ce qui distingue une ligne dans l'identifiant : la clé, ou l'empreinte et le rang."""
    if identite is Identite.CLE:
        return SEPARATEUR_EMPREINTE.join(valeurs_de_cle(cle))
    return f"{empreinte}{SEPARATEUR_EMPREINTE}{rang}"


def identifiant(
    entite: str,
    archive: str,
    archive_precedente: str | None,
    type_: TypeEvenement,
    identite_ligne: str,
) -> str:
    """sha256 de la chaîne canonique ; ``archive_precedente`` vaut ``""`` pour l'état initial."""
    chaine = SEPARATEUR_EMPREINTE.join(
        (entite, archive, archive_precedente or "", type_.value, identite_ligne)
    )
    return hashlib.sha256(chaine.encode("utf-8")).hexdigest()


def en_dict(evenement: Evenement) -> dict[str, object]:
    """Le dictionnaire JSON de l'événement, ``version_schema`` compris."""
    return {
        "id": evenement.id,
        "version_schema": VERSION_SCHEMA,
        "entite": evenement.entite,
        "fichier": evenement.fichier,
        "version_contrat": evenement.version_contrat,
        "type": evenement.type.value,
        "etat_initial": evenement.etat_initial,
        "identite": evenement.identite.value,
        "cle": dict(evenement.cle),
        "empreinte_ligne": evenement.empreinte_ligne,
        "rang": evenement.rang,
        "avant": None if evenement.avant is None else dict(evenement.avant),
        "apres": None if evenement.apres is None else dict(evenement.apres),
        "champs_modifies": list(evenement.champs_modifies),
        "anomalies": [
            {"colonne": colonne, "regle": regle.value} for colonne, regle in evenement.anomalies
        ],
        "date_source": evenement.date_source,
        "date_observation": evenement.date_observation,
        "archive": evenement.archive,
        "archive_sha256": evenement.archive_sha256,
        "archive_precedente": evenement.archive_precedente,
        "archive_precedente_sha256": evenement.archive_precedente_sha256,
    }


def serialiser(evenement: Evenement) -> str:
    """Une ligne JSON : clés triées, séparateurs compacts, UTF-8 tel quel, ``\\n`` final."""
    return (
        json.dumps(en_dict(evenement), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    )


class EvenementInvalide(ValueError):  # noqa: N818 (nom français voulu)
    """Une ligne JSON qui n'est pas un événement du schéma v1."""


def deserialiser(ligne: str) -> Evenement:
    """L'événement d'une ligne JSON écrite par ``serialiser`` ; refuse une autre version."""
    try:
        brut = json.loads(ligne)
    except json.JSONDecodeError as exc:
        raise EvenementInvalide(f"JSON illisible : {exc}") from exc
    if not isinstance(brut, dict) or brut.get("version_schema") != VERSION_SCHEMA:
        raise EvenementInvalide(f"version_schema {VERSION_SCHEMA} attendue")
    try:
        return Evenement(
            id=_texte(brut["id"]),
            entite=_texte(brut["entite"]),
            fichier=_texte(brut["fichier"]),
            version_contrat=_texte(brut["version_contrat"]),
            type=TypeEvenement(_texte(brut["type"])),
            etat_initial=_booleen(brut["etat_initial"]),
            identite=Identite(_texte(brut["identite"])),
            cle=_chaines(brut["cle"]),
            empreinte_ligne=_texte(brut["empreinte_ligne"]),
            rang=_entier(brut["rang"]),
            avant=None if brut["avant"] is None else _chaines(brut["avant"]),
            apres=None if brut["apres"] is None else _chaines(brut["apres"]),
            champs_modifies=tuple(_texte(c) for c in brut["champs_modifies"]),
            anomalies=tuple(
                (None if a["colonne"] is None else _texte(a["colonne"]), Regle(a["regle"]))
                for a in brut["anomalies"]
            ),
            date_source=None if brut["date_source"] is None else _texte(brut["date_source"]),
            date_observation=_texte(brut["date_observation"]),
            archive=_texte(brut["archive"]),
            archive_sha256=_texte(brut["archive_sha256"]),
            archive_precedente=(
                None if brut["archive_precedente"] is None else _texte(brut["archive_precedente"])
            ),
            archive_precedente_sha256=(
                None
                if brut["archive_precedente_sha256"] is None
                else _texte(brut["archive_precedente_sha256"])
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvenementInvalide(f"événement mal formé : {exc!r}") from exc


def _texte(valeur: object) -> str:
    if not isinstance(valeur, str):
        raise TypeError(f"chaîne attendue, reçu {type(valeur).__name__}")
    return valeur


def _booleen(valeur: object) -> bool:
    if not isinstance(valeur, bool):
        raise TypeError(f"booléen attendu, reçu {type(valeur).__name__}")
    return valeur


def _entier(valeur: object) -> int:
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise TypeError(f"entier attendu, reçu {type(valeur).__name__}")
    return valeur


def _chaines(valeur: object) -> dict[str, str]:
    if not isinstance(valeur, dict):
        raise TypeError("objet attendu")
    return {_texte(cle): _texte(v) for cle, v in valeur.items()}
