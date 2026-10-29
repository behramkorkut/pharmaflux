"""Mission 06, palier 1 : le gold du jeu de démo ``demo/archive`` (état typé, contrôles).

Le silver est celui de ``demo_silver`` (``conftest``), construit une fois par
session dans un dossier jetable. Les chiffres attendus sont ceux mesurés au
§0 (``docs/rapports/mission-06/points-a-trancher.md``). Aucun réseau, aucun
conteneur.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_identifiant, charger_tous
from pharmaflux.gold import COLONNES_ILLISIBLES
from pharmaflux.gold import qualite as qualite_gold
from pharmaflux.gold.typage import derniere_observation, etat_type
from pharmaflux.silver import etat as etat_silver
from pharmaflux.silver.entrepot import Entrepot

DERNIERE = "2026-10-27T00:17:12Z"


def test_controles_du_jeu_a_la_derniere_observation(demo_silver: tuple[Path, Path]) -> None:
    _, dossier = demo_silver
    entrepot = Entrepot.ouvrir(dossier)
    instant = derniere_observation(entrepot)
    assert instant == etat_silver.lire_instant(DERNIERE)
    rapport = qualite_gold.controler(entrepot, charger_tous(), instant)
    assert rapport.code_sortie == 0
    valeurs = {c.numero: c.valeur for c in rapport.controles}
    assert valeurs == {
        1: 0,
        2: 0,
        3: 0,
        4: 0,
        5: 4,
        6: 5562,
        7: 1268,
        8: 1,
        9: 23,
        10: 2375,
        11: 5,
        12: 1,
        13: 18_383,
        14: 164_086,
    }
    detail = {c.numero: c.detail for c in rapport.controles}
    assert detail[6] == {
        "asmr": 1662,
        "compositions": 0,
        "conditions_prescription": 0,
        "disponibilite": 23,
        "generiques": 2470,
        "infos_importantes": 1138,
        "mitm": 0,
        "presentations": 4,
        "smr": 2938,
    }
    assert detail[10] == {"smr_plus_asmr": 2375, "smr": 1023, "asmr": 1352}
    assert detail[12] == {"bdpm.specialites.numero_autorisation_europeenne (code_illisible)": 1}
    assert detail[14]["bdpm.presentations"] == {
        "lignes": 20_888,
        "avant": 20_895,
        "ecart": -7,
        "ecart_pct": -0.03,
        "depuis": DERNIERE,
    }


def test_etat_type_du_jeu(demo_silver: tuple[Path, Path]) -> None:
    _, dossier = demo_silver
    entrepot = Entrepot.ouvrir(dossier)
    instant = etat_silver.lire_instant(DERNIERE)
    presentation = etat_type(
        entrepot,
        charger_identifiant("bdpm.presentations"),
        instant,
        {"code_cip13": "3400935955838"},  # remboursement-001
    ).table.to_pylist()[0]
    assert presentation["taux_remboursement"] == ["65%"]
    assert (
        presentation["prix_medicament"],
        presentation["prix_public"],
        presentation["honoraires_dispensation"],
    ) == (Decimal("1.16"), Decimal("2.18"), Decimal("1.02"))
    assert presentation["date_declaration_commercialisation"] == date(2003, 1, 2)
    # La seule valeur illisible du jeu : vide en typé, nommée, jamais devinée.
    specialite = etat_type(
        entrepot, charger_identifiant("bdpm.specialites"), instant, {"code_cis": "61096104"}
    ).table.to_pylist()[0]
    assert specialite["numero_autorisation_europeenne"] is None
    assert specialite[COLONNES_ILLISIBLES] == ["numero_autorisation_europeenne"]
    # Toutes les valeurs canoniques du jeu se typent, et l'état typé a les lignes du silver.
    for entite, contrat in charger_tous().items():
        table = entrepot.table(entite)
        assert table is not None
        for a in ("2026-10-24T20:00:00Z", DERNIERE):
            typee = etat_type(entrepot, contrat, etat_silver.lire_instant(a))
            assert typee.non_typables == {}, entite
            assert (
                typee.table.num_rows
                == etat_silver.etat_a(table, etat_silver.lire_instant(a)).num_rows
            )


def test_gold_qualite_du_jeu_en_ligne_de_commande(demo_silver: tuple[Path, Path]) -> None:
    _, dossier = demo_silver
    resultat = CliRunner().invoke(application, ["gold", "qualite", "--entrepot", str(dossier)])
    assert resultat.exit_code == 0, resultat.output
    assert resultat.stdout.splitlines()[-1] == (
        f"14 contrôles à {DERNIERE} : 4 bloquants, 10 mesurés ; aucun bloquant ne tombe."
    )
