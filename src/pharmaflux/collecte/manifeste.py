"""Manifeste de collecte : une ligne JSON par fichier et par passage, en ajout seul.

``<racine>/manifeste/collecte.jsonl``. C'est la base des mesures de
fraîcheur : aucun passage ne doit y manquer, même en erreur. Le chemin
d'archive y est relatif à la racine, pour que la copie rapatriée sur un
autre poste reste lisible.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path

journal = logging.getLogger("pharmaflux.collecte")

# Ajouté à la fin d'une ligne tronquée (fichier sans ``\n`` final) avant d'écrire la
# suivante : la ligne reste ignorée par ``lire`` sans passer pour une corruption.
MARQUE_TRONCATURE = b"\t# ligne tronquee par une coupure, ignoree"


class ManifesteCorrompu(ValueError):  # noqa: N818 (nom français voulu)
    """Une ligne illisible au milieu du manifeste : ce n'est pas une simple coupure."""


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
    """Ajoute une ligne en fin de manifeste et la force sur le disque.

    Si une coupure a laissé le fichier sans ``\\n`` final (ligne tronquée), la
    marque de troncature puis un ``\\n`` sont écrits d'abord : la nouvelle
    ligne commence toujours sur une ligne propre, et la ligne tronquée, ainsi
    marquée, reste ignorée par ``lire`` même quand d'autres lignes la suivent.
    Rien n'est jamais réécrit : on n'ajoute qu'en fin de fichier.
    """
    chemin = chemin_manifeste(racine)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ligne = json.dumps(asdict(enregistrement), ensure_ascii=False) + "\n"
    prefixe = b""
    if _fin_sans_retour_ligne(chemin):
        journal.warning("%s : fin de fichier tronquée, la ligne est marquée et isolée", chemin)
        prefixe = MARQUE_TRONCATURE + b"\n"
    with chemin.open("ab") as fichier:
        fichier.write(prefixe + ligne.encode("utf-8"))
        fichier.flush()
        os.fsync(fichier.fileno())


def _fin_sans_retour_ligne(chemin: Path) -> bool:
    if not chemin.exists() or chemin.stat().st_size == 0:
        return False
    with chemin.open("rb") as fichier:
        fichier.seek(-1, os.SEEK_END)
        return fichier.read(1) != b"\n"


def lire(racine: Path) -> list[Enregistrement]:
    """Toutes les lignes du manifeste, dans l'ordre. Vide s'il n'existe pas.

    Une dernière ligne illisible (coupure pendant ``ajouter``), ou une ligne
    que ``ajouter`` a marquée tronquée, est ignorée avec un avertissement : la
    collecte doit continuer sans surveillance. Toute autre ligne illisible lève
    ``ManifesteCorrompu`` : c'est un signe de corruption, pas une coupure.
    """
    chemin = chemin_manifeste(racine)
    if not chemin.exists():
        return []
    lignes = [ligne for ligne in chemin.read_bytes().split(b"\n") if ligne.strip()]
    enregistrements = []
    for numero, ligne in enumerate(lignes, start=1):
        try:
            enregistrements.append(_decoder(ligne))
        except (ValueError, TypeError) as exc:
            if ligne.endswith(MARQUE_TRONCATURE):
                journal.warning("%s : ligne %d tronquée par une coupure, ignorée", chemin, numero)
            elif numero == len(lignes):
                journal.warning(
                    "%s : dernière ligne (%d) illisible, ignorée : %s", chemin, numero, exc
                )
            else:
                raise ManifesteCorrompu(f"{chemin} : ligne {numero} illisible ({exc})") from exc
    return enregistrements


def _decoder(ligne: bytes) -> Enregistrement:
    valeurs = json.loads(ligne)
    # Les champs inconnus d'une version future sont ignorés, les absents valent None.
    connus = {champ: valeurs.get(champ) for champ in CHAMPS if champ in valeurs}
    return Enregistrement(**connus)


def dernieres_empreintes(enregistrements: list[Enregistrement]) -> dict[str, str]:
    """La dernière empreinte de comparaison connue, par identifiant du catalogue.

    Toute ligne qui a écrit une archive compte, quel que soit son statut (un
    ``lien_absent`` ou une ``analyse_impossible`` archive en erreur) : sinon le
    même contenu serait réarchivé à chaque passage tant que l'alerte dure.
    """
    empreintes: dict[str, str] = {}
    for enregistrement in enregistrements:
        if (
            enregistrement.identifiant
            and enregistrement.empreinte_comparaison
            and (
                enregistrement.chemin_archive
                or enregistrement.statut in (Statut.NOUVEAU, Statut.INCHANGE)
            )
        ):
            empreintes[enregistrement.identifiant] = enregistrement.empreinte_comparaison
    return empreintes
