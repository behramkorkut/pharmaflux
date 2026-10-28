"""Construire le silver depuis les fichiers d'événements d'une sortie de ``evenements`` (E).

Les fichiers de ``<sortie>/evenements/<entite>/`` dans l'ordre des noms, qui
est l'ordre des archives ; un lot d'au plus ``lot`` événements par commit,
le nom du fichier dans le résumé du snapshot ; la même ``appliquer_lot`` que
le consommateur du bus. L'entrepôt doit être vide : la commande n'efface
rien, elle nomme le dossier.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pharmaflux.contrats.modele import Contrat
from pharmaflux.evenements import rejeu, schema
from pharmaflux.evenements.schema import Evenement
from pharmaflux.silver import LOT_PAR_DEFAUT, SilverRefuse
from pharmaflux.silver.application import appliquer_lot
from pharmaflux.silver.entrepot import ORIGINE_FICHIERS, Entrepot

Journal = Callable[[str], None]
PROP_FICHIER = "pharmaflux.fichier"


@dataclass(slots=True)
class ResumeEntite:
    identifiant: str
    fichiers: int = 0
    evenements: int = 0
    doublons: int = 0
    ouvertures: int = 0
    fermetures: int = 0
    commits: int = 0


@dataclass(slots=True)
class Rapport:
    entrepot: Path
    resumes: list[ResumeEntite] = field(default_factory=list)
    duree_s: float = 0.0


def construire(
    sortie: Path,
    dossier: Path,
    contrats: dict[str, Contrat],
    selection: list[str],
    *,
    lot: int = LOT_PAR_DEFAUT,
    journal: Journal | None = None,
) -> Rapport:
    """Le silver de ``selection`` dans un entrepôt neuf ; ``SilverRefuse`` ou ``FluxIncoherent``."""
    dire = journal or (lambda _: None)
    evenements_dir = sortie / rejeu.DOSSIER_EVENEMENTS
    if not evenements_dir.is_dir():
        raise SilverRefuse(f"aucun dossier d'événements dans {sortie} ({evenements_dir})")
    if lot < 1:
        raise SilverRefuse(f"--lot {lot} : au moins 1")
    depart = time.monotonic()
    entrepot = Entrepot.creer(dossier)
    rapport = Rapport(dossier)
    for identifiant in selection:
        contrat = contrats[identifiant]
        resume = ResumeEntite(identifiant)
        rapport.resumes.append(resume)
        fichiers = sorted((evenements_dir / identifiant).glob("*.jsonl"))
        if not fichiers:
            dire(f"{identifiant} : aucun fichier d'événements, pas de table")
            continue
        table = entrepot.creer_table(contrat, ORIGINE_FICHIERS)
        for fichier in fichiers:
            resume.fichiers += 1
            relatif = f"{identifiant}/{fichier.name}"
            comptes: Counter[str] = Counter()
            for evenements in _lots(fichier, lot):
                table, resultat = appliquer_lot(
                    table,
                    evenements,
                    proprietes_snapshot={PROP_FICHIER: relatif},
                    origine=relatif,
                )
                comptes.update(
                    evenements=resultat.evenements,
                    doublons=resultat.doublons,
                    ouvertures=resultat.ouvertures,
                    fermetures=resultat.fermetures,
                    commits=int(resultat.commit),
                )
            resume.evenements += comptes["evenements"]
            resume.doublons += comptes["doublons"]
            resume.ouvertures += comptes["ouvertures"]
            resume.fermetures += comptes["fermetures"]
            resume.commits += comptes["commits"]
            dire(
                f"{relatif} : {comptes['evenements']} événement(s), {comptes['ouvertures']}"
                f" ouverture(s), {comptes['fermetures']} fermeture(s), {comptes['doublons']}"
                f" doublon(s), {comptes['commits']} commit(s)"
            )
    rapport.duree_s = time.monotonic() - depart
    return rapport


def _lots(fichier: Path, taille: int) -> Iterator[list[Evenement]]:
    """Les événements d'un fichier par lots d'au plus ``taille``, lus ligne à ligne."""
    lot: list[Evenement] = []
    with fichier.open(encoding="utf-8") as flux:
        for ligne in flux:
            if not ligne.strip():
                continue
            lot.append(schema.deserialiser(ligne))
            if len(lot) >= taille:
                yield lot
                lot = []
    if lot:
        yield lot
