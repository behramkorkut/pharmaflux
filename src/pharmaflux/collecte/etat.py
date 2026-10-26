"""État de l'archive, calculé depuis le manifeste.

Pour chaque fichier : identifiant du catalogue, dernière archive écrite
(quel que soit le statut de la ligne : une ``lien_absent`` ou une
``analyse_impossible`` archive aussi), dernier changement observé (une
archive écrite alors qu'une autre existait déjà), date de mise à jour
affichée par la source, dernière erreur, passages des dernières 24 h. Le
manifeste est lu en flux : une ligne à la fois, quel que soit son âge.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pharmaflux.collecte.manifeste import Enregistrement, Statut


@dataclass(slots=True)
class LigneEtat:
    source: str
    fichier: str
    identifiant: str | None = None
    derniere_archive: str | None = None
    dernier_changement: str | None = None
    date_source: str | None = None
    derniere_erreur: str | None = None
    passages_24h: int = 0
    dernier_statut: str | None = None


@dataclass(slots=True)
class Etat:
    """Le résultat d'un parcours du manifeste : les lignes par fichier, et le total."""

    lignes: list[LigneEtat] = field(default_factory=list)
    nombre_enregistrements: int = 0
    dernier_passage: str | None = None


def calculer_etat(enregistrements: Iterable[Enregistrement], maintenant: datetime) -> Etat:
    """Une ligne par (source, fichier), dans l'ordre de première apparition.

    ``enregistrements`` peut être un itérateur (``manifeste.parcourir``) : rien
    n'est gardé au-delà d'une ligne par fichier.
    """
    lignes: dict[tuple[str, str], LigneEtat] = {}
    etat = Etat()
    seuil = (maintenant - timedelta(hours=24)).isoformat()
    for e in enregistrements:
        etat.nombre_enregistrements += 1
        etat.dernier_passage = e.passage_id
        cle = (e.source, e.fichier)
        ligne = lignes.get(cle)
        if ligne is None:
            ligne = lignes[cle] = LigneEtat(e.source, e.fichier)
        if e.identifiant:
            ligne.identifiant = e.identifiant
        ligne.dernier_statut = e.statut
        if e.debut >= seuil:
            ligne.passages_24h += 1
        if e.chemin_archive:
            # Une archive de plus, alors qu'une existait : le contenu a changé
            # (un contenu identique n'est jamais réarchivé, voir dernieres_empreintes).
            if ligne.derniere_archive is not None:
                ligne.dernier_changement = _heure(e.fin)
            ligne.derniere_archive = _heure(e.fin)
        if e.statut == Statut.ERREUR:
            ligne.derniere_erreur = f"{_heure(e.fin)} {e.erreur or ''}".strip()
        if e.date_source_affichee:
            ligne.date_source = e.date_source_affichee
    etat.lignes = list(lignes.values())
    return etat


def formater_etat(lignes: list[LigneEtat]) -> str:
    """Un tableau texte, lisible dans un terminal ou un journal systemd."""
    colonnes = (
        "identifiant",
        "fichier",
        "dernière archive",
        "dernier changement",
        "date source",
        "24 h",
        "dernière erreur",
    )
    rangees = [
        (
            ligne.identifiant or f"— ({ligne.source})",
            ligne.fichier,
            ligne.derniere_archive or "—",
            ligne.dernier_changement or "—",
            ligne.date_source or "—",
            str(ligne.passages_24h),
            ligne.derniere_erreur or "—",
        )
        for ligne in lignes
    ]
    largeurs = [
        max(len(colonne), *(len(rangee[i]) for rangee in rangees))
        for i, colonne in enumerate(colonnes)
    ]
    separateur = "  "
    sortie = [
        separateur.join(colonne.ljust(largeurs[i]) for i, colonne in enumerate(colonnes)),
        separateur.join("-" * largeur for largeur in largeurs),
    ]
    sortie.extend(
        separateur.join(valeur.ljust(largeurs[i]) for i, valeur in enumerate(rangee))
        for rangee in rangees
    )
    return "\n".join(sortie)


def _heure(iso: str) -> str:
    """``2026-10-24T14:17:03+00:00`` → ``2026-10-24 14:17Z``."""
    return iso[:16].replace("T", " ") + "Z"
