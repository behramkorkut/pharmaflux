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
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field, fields
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


def parcourir(racine: Path) -> Iterator[Enregistrement]:
    """Les lignes du manifeste, une à une et dans l'ordre, sans tout charger.

    La mémoire ne dépend pas de l'âge du manifeste : une ligne à la fois, plus
    au plus une ligne illisible gardée en attente, le temps de savoir si elle
    est la dernière. Une dernière ligne illisible (coupure pendant
    ``ajouter``), ou une ligne que ``ajouter`` a marquée tronquée, est ignorée
    avec un avertissement : la collecte doit continuer sans surveillance.
    Toute autre ligne illisible lève ``ManifesteCorrompu`` : c'est un signe de
    corruption, pas une coupure. Rien n'est produit si le fichier n'existe pas.
    """
    chemin = chemin_manifeste(racine)
    if not chemin.exists():
        return
    numero = 0
    en_attente: tuple[int, Exception] | None = None
    with chemin.open("rb") as fichier:
        for brute in fichier:
            ligne = brute.rstrip(b"\n")
            if not ligne.strip():
                continue
            numero += 1
            if en_attente is not None:
                numero_illisible, exc = en_attente
                raise ManifesteCorrompu(
                    f"{chemin} : ligne {numero_illisible} illisible ({exc})"
                ) from exc
            try:
                enregistrement = _decoder(ligne)
            except (ValueError, TypeError) as exc:
                if ligne.endswith(MARQUE_TRONCATURE):
                    journal.warning(
                        "%s : ligne %d tronquée par une coupure, ignorée", chemin, numero
                    )
                else:
                    en_attente = (numero, exc)
                continue
            yield enregistrement
    if en_attente is not None:
        journal.warning(
            "%s : dernière ligne (%d) illisible, ignorée : %s", chemin, en_attente[0], en_attente[1]
        )


def lire(racine: Path) -> list[Enregistrement]:
    """Toutes les lignes du manifeste, en mémoire : pour ``etat``, pas pour un passage."""
    return list(parcourir(racine))


def _decoder(ligne: bytes) -> Enregistrement:
    valeurs = json.loads(ligne)
    # Les champs inconnus d'une version future sont ignorés, les absents valent None.
    connus = {champ: valeurs.get(champ) for champ in CHAMPS if champ in valeurs}
    return Enregistrement(**connus)


@dataclass(slots=True)
class EtatConnu:
    """Ce qu'un passage retient du manifeste, borné par le catalogue, pas par son âge.

    ``empreintes`` : la dernière empreinte de comparaison connue, par identifiant.
    ``collectes_du_jour`` : les identifiants qui ont déjà une ligne sans erreur
    ce jour-là (les entrées quotidiennes ne repassent pas).
    """

    empreintes: dict[str, str] = field(default_factory=dict)
    collectes_du_jour: set[str] = field(default_factory=set)


def etat_connu(racine: Path, jour: str) -> EtatConnu:
    """Un seul parcours du manifeste, en flux, pour le jour ``AAAA-MM-JJ`` donné."""
    etat = EtatConnu()
    for enregistrement in parcourir(racine):
        _retenir_empreinte(etat.empreintes, enregistrement)
        if (
            enregistrement.identifiant
            and enregistrement.statut != Statut.ERREUR
            and enregistrement.debut.startswith(jour)
        ):
            etat.collectes_du_jour.add(enregistrement.identifiant)
    return etat


def dernieres_empreintes(enregistrements: Iterable[Enregistrement]) -> dict[str, str]:
    """La dernière empreinte de comparaison connue, par identifiant du catalogue.

    Toute ligne qui a écrit une archive compte, quel que soit son statut (un
    ``lien_absent`` ou une ``analyse_impossible`` archive en erreur) : sinon le
    même contenu serait réarchivé à chaque passage tant que l'alerte dure.
    """
    empreintes: dict[str, str] = {}
    for enregistrement in enregistrements:
        _retenir_empreinte(empreintes, enregistrement)
    return empreintes


def _retenir_empreinte(empreintes: dict[str, str], enregistrement: Enregistrement) -> None:
    if (
        enregistrement.identifiant
        and enregistrement.empreinte_comparaison
        and (
            enregistrement.chemin_archive
            or enregistrement.statut in (Statut.NOUVEAU, Statut.INCHANGE)
        )
    ):
        empreintes[enregistrement.identifiant] = enregistrement.empreinte_comparaison
