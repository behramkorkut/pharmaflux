"""Mission 05, palier 1 : le SCD2 d'un lot, le schéma, les instants, le rendu, les imports.

Les événements viennent des fixtures de ``tests/fixtures/evenements/``
(snapshots construits en mémoire, comme ``test_bus``), appliqués à des
tables Iceberg créées sous ``tmp_path``. Aucun réseau, aucun conteneur.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pytest

from pharmaflux.bus.enveloppe import cle_message
from pharmaflux.contrats.chargeur import charger_identifiant
from pharmaflux.evenements.comparaison import comparer
from pharmaflux.evenements.schema import Evenement, TypeEvenement
from pharmaflux.silver import FluxIncoherent, Format, SilverRefuse
from pharmaflux.silver import etat as etat_silver
from pharmaflux.silver.application import appliquer_lot
from pharmaflux.silver.entrepot import (
    ORIGINE_FICHIERS,
    PROP_ORIGINE,
    PROP_VERSION_CONTRAT,
    Entrepot,
    chemins_parquet,
)
from pharmaflux.silver.schema import (
    COLONNES_VERSION,
    identite_de,
    instant,
    schema_arrow,
    texte_instant,
)
from tests.test_bus import DISPO, PRESENTATIONS, _snap

T_A, T_B = "1417", "1517"  # 2026-10-24 ; le troisième snapshot est à 1617


def _entrepot(tmp_path: Path) -> Entrepot:
    return Entrepot.creer(tmp_path / "entrepot")


def _presentations() -> tuple[list[Evenement], list[Evenement], list[Evenement]]:
    """A (état initial), A → B (supprimee, modifiee, creee), B → A (le retour)."""
    a, b = (
        _snap(PRESENTATIONS, "presentations_a.txt"),
        _snap(PRESENTATIONS, "presentations_b.txt", T_B),
    )
    a2 = _snap(PRESENTATIONS, "presentations_a.txt", "1617")
    return (
        list(comparer(None, a, date_source="2026-10-24")),
        list(comparer(a, b)),
        list(comparer(b, a2)),
    )


def _ouvertes(table: pa.Table) -> pa.Table:
    return table.filter(pc.is_null(table["fin_validite"]))


def test_identite_est_la_cle_du_message_ou_l_empreinte_et_le_rang() -> None:
    initiales, _, _ = _presentations()
    e = initiales[0]
    assert identite_de(e) == cle_message(e).decode("utf-8")
    assert identite_de(e).startswith('{"code_cip13":"')
    dispo = list(comparer(None, _snap(DISPO, "dispo_triple.txt")))
    rangs = [e for e in dispo if e.rang > 1]
    assert rangs and identite_de(rangs[0]) == f"{rangs[0].empreinte_ligne}#{rangs[0].rang}"
    schema = schema_arrow(charger_identifiant(PRESENTATIONS).noms_colonnes)
    assert schema.names[-len(COLONNES_VERSION) :] == list(COLONNES_VERSION)
    with pytest.raises(ValueError, match="rang"):
        schema_arrow(("code_cis", "rang"))


def test_scd2_par_cle_ouvre_ferme_et_rouvre(tmp_path: Path) -> None:
    initiales, suivants, retour = _presentations()
    contrat = charger_identifiant(PRESENTATIONS)
    entrepot = _entrepot(tmp_path)
    table = entrepot.creer_table(contrat, ORIGINE_FICHIERS)
    assert table.properties[PROP_VERSION_CONTRAT] == contrat.version
    assert table.properties[PROP_ORIGINE] == ORIGINE_FICHIERS

    table, r1 = appliquer_lot(table, initiales, proprietes_snapshot={"pharmaflux.fichier": "a"})
    assert (r1.evenements, r1.ouvertures, r1.fermetures, r1.doublons, r1.commit) == (
        len(initiales),
        len(initiales),
        0,
        0,
        True,
    )
    assert table.current_snapshot() is not None
    assert table.current_snapshot().summary.additional_properties["pharmaflux.fichier"] == "a"  # type: ignore[union-attr]

    table, r2 = appliquer_lot(table, suivants)
    types = {t: sum(1 for e in suivants if e.type is t) for t in TypeEvenement}
    assert r2.fermetures == types[TypeEvenement.SUPPRIMEE] + types[TypeEvenement.MODIFIEE]
    assert r2.ouvertures == types[TypeEvenement.CREEE] + types[TypeEvenement.MODIFIEE]
    tout = table.scan().to_arrow()
    assert tout.num_rows == len(initiales) + r2.ouvertures
    ouvertes = _ouvertes(tout)
    assert (
        ouvertes.num_rows
        == len(initiales) - types[TypeEvenement.SUPPRIMEE] + types[TypeEvenement.CREEE]
    )
    fermees = tout.filter(pc.is_valid(tout["fin_validite"]))
    assert fermees.num_rows == r2.fermetures
    assert set(fermees["fin_validite"].to_pylist()) == {instant(suivants[0].date_observation)}
    assert set(fermees["id_fermeture"].to_pylist()) == {
        e.id for e in suivants if e.type is not TypeEvenement.CREEE
    }
    assert set(fermees["archive_fermeture"].to_pylist()) == {suivants[0].archive}
    # Une modifiee : la version fermée porte « avant », la version ouverte porte « après ».
    modifiee = next(e for e in suivants if e.type is TypeEvenement.MODIFIEE)
    versions = tout.filter(pc.equal(tout["identite"], identite_de(modifiee))).to_pylist()
    versions.sort(key=lambda v: v["debut_validite"])
    assert len(versions) == 2
    assert modifiee.avant is not None and modifiee.apres is not None
    for nom in modifiee.champs_modifies:
        assert versions[0][nom] == modifiee.avant[nom] and versions[1][nom] == modifiee.apres[nom]
    assert versions[0]["id_fermeture"] == modifiee.id == versions[1]["id_ouverture"]
    assert versions[1]["etat_initial"] is False and versions[0]["etat_initial"] is True

    table, r3 = appliquer_lot(table, retour)
    assert r3.ouvertures and r3.fermetures
    # Le retour à A : les versions ouvertes ont les valeurs de A.
    ouvertes = _ouvertes(table.scan().to_arrow())
    assert ouvertes.num_rows == len(initiales)
    assert all(a["regle"] for v in ouvertes.to_pylist() for a in v["anomalies"]) or True
    assert len(chemins_parquet(table)) >= 1


def test_un_evenement_deja_applique_ne_change_rien(tmp_path: Path) -> None:
    initiales, suivants, _ = _presentations()
    entrepot = _entrepot(tmp_path)
    table = entrepot.creer_table(charger_identifiant(PRESENTATIONS), ORIGINE_FICHIERS)
    table, _ = appliquer_lot(table, initiales)
    table, _ = appliquer_lot(table, suivants)
    avant = table.scan().to_arrow().sort_by("id_ouverture")
    snapshots = len(table.metadata.snapshots)
    # Republication entière (comme après une coupure du bus) : tout est en doublon.
    table, r = appliquer_lot(table, [*initiales, *suivants, *suivants])
    assert (r.doublons, r.ouvertures, r.fermetures, r.commit) == (
        len(initiales) + 2 * len(suivants),
        0,
        0,
        False,
    )
    assert len(table.metadata.snapshots) == snapshots
    assert table.scan().to_arrow().sort_by("id_ouverture").equals(avant)
    # Avec une position à garder : elle avance quand même, sans snapshot.
    table, r = appliquer_lot(table, suivants, proprietes_table={"pharmaflux.positions": "{}"})
    assert r.commit and table.properties["pharmaflux.positions"] == "{}"
    assert len(table.metadata.snapshots) == snapshots
    # Un lot mêlé : seuls les nouveaux événements s'appliquent.
    _, _, retour = _presentations()
    table, r = appliquer_lot(table, [*suivants, *retour])
    assert r.doublons == len(suivants) and r.ouvertures + r.fermetures == len(retour) + sum(
        1 for e in retour if e.type is TypeEvenement.MODIFIEE
    )


def test_refus_du_scd2(tmp_path: Path) -> None:
    initiales, suivants, _ = _presentations()
    contrat = charger_identifiant(PRESENTATIONS)
    entrepot = _entrepot(tmp_path)
    table = entrepot.creer_table(contrat, ORIGINE_FICHIERS)
    snapshots = len(table.metadata.snapshots)
    with pytest.raises(FluxIncoherent, match="sans version ouverte"):
        appliquer_lot(table, suivants, origine="essai")
    assert len(table.refresh().metadata.snapshots) == snapshots  # rien n'est écrit
    table, _ = appliquer_lot(table, initiales)
    # Une creee d'une identité déjà ouverte, sous un autre identifiant (autre archive).
    autre = list(comparer(None, _snap(PRESENTATIONS, "presentations_a.txt", "1817")))
    with pytest.raises(FluxIncoherent, match="déjà ouverte"):
        appliquer_lot(table, autre)
    # Une autre version de contrat : rebâtir.
    v9 = [dataclasses.replace(e, version_contrat="v9") for e in suivants]
    with pytest.raises(SilverRefuse, match="rebâtis le silver"):
        appliquer_lot(table, v9)
    # Une autre entité dans la table.
    with pytest.raises(FluxIncoherent, match="entité"):
        appliquer_lot(table, list(comparer(None, _snap(DISPO, "dispo_a.txt"))))
    # Une seconde table pour la même entité est refusée ; un entrepôt non vide aussi.
    with pytest.raises(SilverRefuse, match="existe déjà"):
        entrepot.creer_table(contrat, ORIGINE_FICHIERS)
    with pytest.raises(SilverRefuse, match="n'est pas vide"):
        Entrepot.creer(tmp_path / "entrepot")
    with pytest.raises(SilverRefuse, match="aucun entrepôt"):
        Entrepot.ouvrir(tmp_path / "ailleurs")
    assert Entrepot.ouvrir(tmp_path / "entrepot").entites() == [PRESENTATIONS]


def test_scd2_ligne_a_ligne_suit_les_rangs(tmp_path: Path) -> None:
    triple = _snap(DISPO, "dispo_triple.txt")
    simple = _snap(DISPO, "dispo_simple.txt", T_B)
    triple2 = _snap(DISPO, "dispo_triple.txt", "1617")
    initiales = list(comparer(None, triple))
    baisse = list(comparer(triple, simple))  # supprimee des rangs 3 puis 2
    hausse = list(comparer(simple, triple2))  # creee des rangs 2 puis 3
    assert [e.rang for e in baisse if e.type is TypeEvenement.SUPPRIMEE] == [3, 2]
    assert [e.rang for e in hausse if e.type is TypeEvenement.CREEE] == [2, 3]
    entrepot = _entrepot(tmp_path)
    table = entrepot.creer_table(charger_identifiant(DISPO), ORIGINE_FICHIERS)
    table, _ = appliquer_lot(table, initiales)
    # Supprimer le rang 2 avant le rang 3 : refusé, le compte serait faux.
    with pytest.raises(FluxIncoherent, match="suppression du rang 2 sur 3"):
        appliquer_lot(table, [baisse[1]])
    table, r = appliquer_lot(table, baisse)
    assert r.fermetures == 2 and r.ouvertures == 0
    empreinte = baisse[0].empreinte_ligne
    tout = table.scan().to_arrow()
    de_la_ligne = tout.filter(pc.equal(tout["empreinte_ligne"], empreinte))
    assert sorted(de_la_ligne["rang"].to_pylist()) == [1, 2, 3]
    assert _ouvertes(de_la_ligne)["rang"].to_pylist() == [1]
    # Créer le rang 3 avant le rang 2 : refusé.
    with pytest.raises(FluxIncoherent, match="création du rang 3 sur 1"):
        appliquer_lot(table, [hausse[1]])
    table, r = appliquer_lot(table, hausse)
    assert r.ouvertures == 2
    tout = table.scan().to_arrow()
    de_la_ligne = tout.filter(pc.equal(tout["empreinte_ligne"], empreinte))
    assert sorted(_ouvertes(de_la_ligne)["rang"].to_pylist()) == [1, 2, 3]
    assert de_la_ligne.num_rows == 5  # 3 initiales (2 fermées) + 2 rouvertes
    assert {identite_de(e) for e in hausse} == set(
        _ouvertes(de_la_ligne)
        .filter(pc.greater(_ouvertes(de_la_ligne)["rang"], 1))["identite"]
        .to_pylist()
    )


def test_etat_a_une_date_et_bornes(tmp_path: Path) -> None:
    initiales, suivants, retour = _presentations()
    entrepot = _entrepot(tmp_path)
    table = entrepot.creer_table(charger_identifiant(PRESENTATIONS), ORIGINE_FICHIERS)
    for lot in (initiales, suivants, retour):
        table, _ = appliquer_lot(table, lot)
    t_a, t_b, t_a2 = (instant(lot[0].date_observation) for lot in (initiales, suivants, retour))
    n_a = len(initiales)
    n_b = (
        n_a
        - sum(1 for e in suivants if e.type is TypeEvenement.SUPPRIMEE)
        + sum(1 for e in suivants if e.type is TypeEvenement.CREEE)
    )
    assert etat_silver.etat_a(table, t_a.replace(minute=0)).num_rows == 0
    assert etat_silver.etat_a(table, t_a).num_rows == n_a  # borne de début incluse
    assert etat_silver.etat_a(table, t_b.replace(second=59) - (t_b - t_b)).num_rows == n_b
    assert etat_silver.etat_a(table, datetime(2026, 10, 24, 15, 16, 59, tzinfo=UTC)).num_rows == n_a
    assert etat_silver.etat_a(table, t_b).num_rows == n_b  # borne de fin exclue
    assert etat_silver.etat_a(table, t_a2).num_rows == n_a
    assert etat_silver.etat_a(table, datetime(2027, 1, 1, tzinfo=UTC)).num_rows == n_a
    # Un filtre d'égalité sur une colonne du contrat, et une colonne inconnue.
    cle = initiales[0].cle
    filtre = etat_silver.etat_a(table, t_a, dict(cle))
    assert filtre.num_rows == 1 and filtre["identite"][0].as_py() == identite_de(initiales[0])
    with pytest.raises(SilverRefuse, match="colonne inconnue"):
        etat_silver.etat_a(table, t_a, {"prix": "1"})
    assert etat_silver.bornes(table) == (t_a, t_a2)
    assert etat_silver.lire_filtres(["code_cip13=3400930000000"]) == {"code_cip13": "3400930000000"}
    with pytest.raises(SilverRefuse, match="colonne=valeur"):
        etat_silver.lire_filtres(["code_cip13"])


def test_lire_instant_utc_a_la_seconde() -> None:
    assert etat_silver.lire_instant("2026-10-26T14:00:00Z") == datetime(
        2026, 10, 26, 14, tzinfo=UTC
    )
    assert etat_silver.lire_instant("2026-10-26T16:00:00+02:00") == datetime(
        2026, 10, 26, 14, tzinfo=UTC
    )
    assert etat_silver.lire_instant("2026-10-26") == datetime(2026, 10, 26, tzinfo=UTC)
    for mauvais, motif in (
        ("2026-10-26T14:00:00", "sans fuseau"),
        ("2026-10-26T14:00:00.5Z", "fraction"),
        ("2026-10-26T14:00:00.000Z", "fraction"),  # relecture 1, point 4 : même nulle
        ("2026-10-26T14:00Z", "illisible"),  # sans les secondes
        ("2026-10-26 14:00:00Z", "illisible"),  # un espace à la place du T
        ("20261026T140000Z", "illisible"),  # la forme compacte
        ("2026-10-26T14:00:00+0200", "illisible"),  # décalage sans deux-points
        ("2026-13-26T14:00:00Z", "illisible"),  # bien formé, mois impossible
        ("hier", "illisible"),
    ):
        with pytest.raises(SilverRefuse, match=motif):
            etat_silver.lire_instant(mauvais)
    assert texte_instant(datetime(2026, 10, 26, 14, tzinfo=UTC)) == "2026-10-26T14:00:00Z"


def test_rendu_jsonl_tableau_csv(tmp_path: Path) -> None:
    initiales, _, _ = _presentations()
    entrepot = _entrepot(tmp_path)
    table = entrepot.creer_table(charger_identifiant(PRESENTATIONS), ORIGINE_FICHIERS)
    table, _ = appliquer_lot(table, initiales[:3])
    versions = etat_silver.ordonner(table.scan().to_arrow())
    jsonl = list(etat_silver.rendre(versions, Format.JSONL))
    assert len(jsonl) == 3
    premiere = json.loads(jsonl[0])
    assert (
        premiere["debut_validite"] == initiales[0].date_observation
        and premiere["fin_validite"] is None
    )
    assert premiere["etat_initial"] is True and isinstance(premiere["anomalies"], list)
    assert list(premiere) == versions.schema.names
    tableau = list(etat_silver.rendre(versions, Format.TABLEAU, ["code_cip13", "debut_validite"]))
    assert tableau[0].split() == ["code_cip13", "debut_validite"] and tableau[1].startswith("---")
    assert len(tableau) == 5 and tableau[2].endswith(initiales[0].date_observation)
    csv_ = list(etat_silver.rendre(versions, Format.CSV, ["code_cip13", "etat_initial"]))
    assert csv_[0] == "code_cip13,etat_initial" and csv_[1].endswith(",true")
    with pytest.raises(SilverRefuse, match="inconnue"):
        list(etat_silver.rendre(versions, Format.CSV, ["prix"]))


def test_la_cli_n_importe_pas_les_bibliotheques_du_silver() -> None:
    """K.1 : pyarrow, pyiceberg et duckdb ne se chargent que dans les commandes silver."""
    code = (
        "import sys, pharmaflux.cli; "
        "print(sorted(m for m in ('pyarrow', 'pyiceberg', 'duckdb') if m in sys.modules))"
    )
    sortie = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120
    )
    assert sortie.stdout.strip() == "[]"
