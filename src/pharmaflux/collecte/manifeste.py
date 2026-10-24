"""Manifeste de collecte : une ligne JSON par fichier et par passage, en ajout seul.

``<racine>/manifeste/collecte.jsonl``. C'est la base des mesures de
fraîcheur : aucun passage ne doit y manquer, même en erreur. Le chemin
d'archive y est relatif à la racine, pour que la copie rapatriée sur un
autre poste reste lisible.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path


class Statut(StrEnum):
    NOUVEAU = "nouveau"
    INCHANGE = "inchange"
    NON_MODIFIE_304 = "non_modifie_304"
    ERREUR = "erreur"


@dataclass(slots=True)
class Enregistrement:
    """Une ligne du manifeste."""

    passage_id: str
    identifiant: str | None
    source: str
    fichier: str
    url: str
    debut: str
    fin: str
    statut: str
    version_collecteur: str
    essais: int = 0
    http_statut: int | None = None
    sha256: str | None = None
    empreinte_comparaison: str | None = None
    taille_octets: int | None = None
    last_modified: str | None = None
    etag: str | None = None
    date_source_affichee: str | None = None
    taille_affichee_ko: int | None = None
    content_disposition_nom: str | None = None
    chemin_archive: str | None = None
    erreur: str | None = None


CHAMPS = tuple(champ.name for champ in fields(Enregistrement))


def chemin_manifeste(racine: Path) -> Path:
    return racine / "manifeste" / "collecte.jsonl"


def ajouter(racine: Path, enregistrement: Enregistrement) -> None:
    """Ajoute une ligne en fin de manifeste et la force sur le disque."""
    chemin = chemin_manifeste(racine)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ligne = json.dumps(asdict(enregistrement), ensure_ascii=False) + "\n"
    with chemin.open("ab") as fichier:
        fichier.write(ligne.encode("utf-8"))
        fichier.flush()
        os.fsync(fichier.fileno())


def lire(racine: Path) -> list[Enregistrement]:
    """Toutes les lignes du manifeste, dans l'ordre. Vide s'il n'existe pas."""
    chemin = chemin_manifeste(racine)
    if not chemin.exists():
        return []
    enregistrements = []
    with chemin.open("rb") as fichier:
        for brut in fichier:
            ligne = brut.strip()
            if not ligne:
                continue
            valeurs = json.loads(ligne)
            # Les champs inconnus d'une version future sont ignorés, les absents valent None.
            connus = {champ: valeurs.get(champ) for champ in CHAMPS if champ in valeurs}
            enregistrements.append(Enregistrement(**connus))
    return enregistrements


def dernieres_empreintes(enregistrements: list[Enregistrement]) -> dict[str, str]:
    """La dernière empreinte de comparaison connue, par identifiant du catalogue."""
    empreintes: dict[str, str] = {}
    for enregistrement in enregistrements:
        if (
            enregistrement.identifiant
            and enregistrement.empreinte_comparaison
            and enregistrement.statut in (Statut.NOUVEAU, Statut.INCHANGE)
        ):
            empreintes[enregistrement.identifiant] = enregistrement.empreinte_comparaison
    return empreintes
