"""Mission 07, palier 3 : le jeu de démo publié en tranches, l'index mis à jour après chacune.

Le silver se construit archive par archive, depuis les fichiers d'événements du
jeu (``demo_silver``), en quatre tranches : l'état initial du 24/10, la
soirée du 24, le 26, le 27. Après la première, ``index construire`` ; après
chacune des suivantes, ``index mettre-a-jour`` puis ``index verifier``, qui
compare l'index à sa reconstruction complète depuis le gold au même instant
(décision 4). À la fin, l'index mis à jour pas à pas est aussi égal, point
pour point, à l'index construit en une fois. Le Qdrant simulé et l'encodeur
de test : la mécanique, en deux processus comme sur le Mac.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evenements import rejeu
from pharmaflux.silver.application import appliquer_lot
from pharmaflux.silver.construction import PROP_FICHIER, _lots
from pharmaflux.silver.entrepot import ORIGINE_FICHIERS, Entrepot
from tests.qdrant_simule import QdrantSimule

TRANCHES = (  # la dernière archive de chaque tranche
    "20261024T194206Z",
    "20261024T231712Z",
    "20261026T151731Z",
    "20261027T131731Z",
)


def publier_jusqu_a(sortie: Path, entrepot: Entrepot, borne: str, faits: set[str]) -> None:
    """Applique au silver les fichiers d'événements dont l'archive vient au plus à ``borne``."""
    contrats = charger_tous()
    for dossier in sorted((sortie / rejeu.DOSSIER_EVENEMENTS).iterdir()):
        entite = dossier.name
        table = entrepot.table(entite) or entrepot.creer_table(contrats[entite], ORIGINE_FICHIERS)
        for fichier in sorted(dossier.glob("*.jsonl")):
            relatif = f"{entite}/{fichier.name}"
            if fichier.name[:16] > borne or relatif in faits:
                continue
            for evenements in _lots(fichier, 5000):
                table, _ = appliquer_lot(
                    table, evenements, proprietes_snapshot={PROP_FICHIER: relatif}, origine=relatif
                )
            faits.add(relatif)


def invoquer(*arguments: str) -> str:
    resultat = CliRunner().invoke(application, list(arguments))
    assert resultat.exit_code == 0, resultat.output
    return resultat.output


def test_le_jeu_en_quatre_tranches_l_index_egal_a_sa_reconstruction(
    demo_silver: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sortie, _ = demo_silver
    dossier = tmp_path / "lakehouse"
    entrepot = Entrepot.creer(dossier)
    simule = QdrantSimule()
    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", simule.transport)
    options = ["--entrepot", str(dossier), "--modele", "test", "--travail", str(tmp_path / "ix")]
    faits: set[str] = set()
    sorties = []
    for rang, borne in enumerate(TRANCHES):
        publier_jusqu_a(sortie, entrepot, borne, faits)
        commande = "construire" if rang == 0 else "mettre-a-jour"
        sorties.append(invoquer("index", commande, *options))
        print(f"tranche {rang + 1} ({borne}) : {sorties[-1].splitlines()[0]}")  # avec -s
        verification = invoquer("index", "verifier", *options)
        assert "conforme" in verification.splitlines(), verification
    assert len(faits) == 18, "les 18 archives du jeu, chacune une fois"
    assert "index construit : " in sorties[0]
    assert all(
        s.startswith(("index mis à jour de", "index à jour : rien à faire")) for s in sorties[1:]
    )
    assert any(s.startswith("index mis à jour de") for s in sorties[1:]), (
        "au moins une tranche change"
    )
    pas_a_pas = {
        i: (p["payload"], p["vector"]) for i, p in simule.points("pharmaflux-fragments").items()
    }
    reference = QdrantSimule()
    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", reference.transport)
    invoquer("index", "construire", *options[:4], "--travail", str(tmp_path / "ref"))
    en_une_fois = {
        i: (p["payload"], p["vector"]) for i, p in reference.points("pharmaflux-fragments").items()
    }
    assert pas_a_pas == en_une_fois, "mêmes identifiants, mêmes charges, mêmes vecteurs"
    assert len(pas_a_pas) == 72296
