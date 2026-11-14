"""Les chemins de la chaîne : l'archive, qu'elle lit, et le dérivé, qu'elle écrit.

Tout est absolu. Un chemin relatif dépendrait du dossier d'où la commande est
lancée, et l'entrepôt Iceberg grave le sien dans ses métadonnées (ADR 0009) :
le chemin du dérivé se choisit une fois.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VARIABLE_DERIVE = "PHARMAFLUX_DERIVE"


class CheminsRefuses(Exception):  # noqa: N818 (nom français voulu)
    """Les chemins donnés ne permettent pas de lancer la chaîne."""


@dataclass(frozen=True, slots=True)
class Chemins:
    """L'archive (lecture) et le dérivé (écriture), avec ce que chaque étape y range."""

    racine: Path
    derive: Path
    modeles: Path | None = None

    @property
    def evenements(self) -> Path:
        """La sortie de « evenements » : fichiers JSONL, bilans, états."""
        return self.derive / "evenements"

    @property
    def lakehouse(self) -> Path:
        """L'entrepôt Iceberg du silver."""
        return self.derive / "lakehouse"

    @property
    def index(self) -> Path:
        """Le dossier de travail de l'index : cache des vecteurs, fragments, son verrou."""
        return self.derive / "index"

    @property
    def chaine(self) -> Path:
        """Ce que la chaîne tient elle-même : son verrou et le journal des passages."""
        return self.derive / "chaine"

    @property
    def tmp(self) -> Path:
        """Les fichiers temporaires des étapes, sur le disque (TMPDIR de l'unité, sur le VPS)."""
        return self.derive / "tmp"

    @property
    def verrou(self) -> Path:
        return self.chaine / "verrou"

    @property
    def passages(self) -> Path:
        return self.chaine / "passages.jsonl"


def _contient(parent: Path, enfant: Path) -> bool:
    return enfant == parent or parent in enfant.parents


def resoudre(racine: Path, derive: Path | None, modeles: Path | None = None) -> Chemins:
    """Les chemins vérifiés, ou ``CheminsRefuses`` avec la raison."""
    if derive is None:
        raise CheminsRefuses(
            f"le dossier du dérivé manque : --derive, ou la variable {VARIABLE_DERIVE}"
        )
    for nom, chemin in (("--racine", racine), ("--derive", derive), ("--modeles", modeles)):
        if chemin is not None and not chemin.is_absolute():
            raise CheminsRefuses(f"{nom} doit être un chemin absolu : {chemin}")
    # Résolus : ni « .. » ni lien ne font passer le dérivé pour séparé de l'archive.
    racine, derive = racine.resolve(), derive.resolve()
    if not racine.is_dir():
        raise CheminsRefuses(f"l'archive est introuvable : {racine}")
    # L'archive est irremplaçable : rien de dérivé ne s'écrit dedans, ni autour.
    if _contient(racine, derive) or _contient(derive, racine):
        raise CheminsRefuses(f"le dérivé ({derive}) et l'archive ({racine}) doivent être séparés")
    if modeles is not None and not modeles.is_dir():
        raise CheminsRefuses(f"le dossier des modèles est introuvable : {modeles}")
    return Chemins(racine=racine, derive=derive, modeles=modeles)
