"""Mission 06, palier 2 : les vues métier du gold, leurs références DuckDB, la priorité des états.

Le bronze est fait des extraits réels de ``tests/fixtures/bdpm/`` à 14:17 (le
24/10/2026), sauf la disponibilité : un fichier **synthétique**, construit en
mémoire et jamais écrit sous ``tests/fixtures/``, qui couvre chaque branche
de la priorité (addendum 1, exigence 2) sur des CIS des extraits :

- A (six présentations) : une ligne sans CIP13 (dépliée sur les six), retirée
  à 15:17 → ``declare`` puis ``fin_de_publication`` ;
- B (deux présentations) : une ligne directe sur sa première présentation et
  une ligne sans CIP13 ; la seconde est retirée à 15:17 → la première
  présentation reste ``declare`` (la ligne directe l'emporte sur la
  fermeture), la seconde passe en ``fin_de_publication`` ;
- C : jamais signalée → ``aucun_signalement`` ;
- D : la même ligne deux fois → ``occurrences = 2`` ;
- un CIS sans présentation, arrêt annoncé pour 2027 → ``presentation_connue``
  faux, ``debut_a_venir`` vrai.

La perte de deux lignes sur six met l'archive de 15:17 en attente ; celle de
16:17, identique, la confirme (garde-fou de volume, ADR 0006). Chaque vue est
comparée à sa requête DuckDB de référence (``references_gold``) à trois
instants. Aucun réseau, aucun conteneur.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_identifiant, charger_tous
from pharmaflux.evenements import rejeu
from pharmaflux.gold import vues as vues_gold
from pharmaflux.gold.rendu import fiche_en_texte
from pharmaflux.gold.sql import etats_types
from pharmaflux.gold.typage import EntiteTypee
from pharmaflux.silver import construction
from pharmaflux.silver import etat as etat_silver
from pharmaflux.silver.entrepot import Entrepot
from tests import references_gold as ref
from tests.conftest import FIXTURES, entrees_bdpm_txt
from tests.test_gold import T0, T1, _archiver

T2 = T1 + timedelta(hours=1)
ENTRE = T0 + timedelta(minutes=13)  # après 14:17, avant la fermeture de 15:17
DISPO = "bdpm.disponibilite"
CIS_A, CIS_B, CIS_C, CIS_D = "60019350", "60019927", "60018896", "60018088"
CIS_SANS_PRESENTATION = "69999999"
LIEN = "https://ansm.sante.fr/disponibilites-des-produits-de-sante/medicaments/essai-synthetique-"


def _presentations(code_cis: str) -> list[str]:
    """Les CIP13 d'un CIS dans l'extrait réel de ``CIS_CIP_bdpm.txt``, triés."""
    lignes = (FIXTURES / "bdpm" / "CIS_CIP_bdpm.txt").read_text(encoding="utf-8").splitlines()
    return sorted(ligne.split("\t")[6] for ligne in lignes if ligne.startswith(code_cis + "\t"))


def _ligne(cis: str, cip13: str, code: str, debut: str, maj: str, remise: str, lien: str) -> str:
    libelles = {
        "1": "Rupture de stock",
        "2": "Tension d'approvisionnement",
        "3": "Arrêt de commercialisation",
        "4": "Remise à disposition",
    }
    return "\t".join([cis, cip13, code, libelles[code], debut, maj, remise, LIEN + lien])


def _dispo_synthetique(*, avec_retirees: bool) -> bytes:
    lignes = []
    if avec_retirees:
        lignes.append(_ligne(CIS_A, "", "2", "01/09/2026", "10/10/2026", "", "a"))
    lignes.append(
        _ligne(CIS_B, _presentations(CIS_B)[0], "1", "01/10/2026", "15/10/2026", "", "b-direct")
    )
    if avec_retirees:
        lignes.append(_ligne(CIS_B, "", "2", "01/08/2026", "15/10/2026", "", "b"))
    lignes.append(_ligne(CIS_SANS_PRESENTATION, "", "3", "01/07/2027", "01/10/2026", "", "annonce"))
    lignes += [_ligne(CIS_D, "", "4", "02/10/2026", "02/10/2026", "02/10/2026", "d")] * 2
    contrat = charger_identifiant(DISPO)
    return ("\r\n".join(lignes) + "\r\n").encode(contrat.format.encodage)


@pytest.fixture(scope="module")
def vues_fixtures(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Le silver du bronze de ce module (voir le module) ; lu, jamais écrit par les tests."""
    racine = tmp_path_factory.mktemp("bronze") / "pharmaflux-data"
    for e in entrees_bdpm_txt():
        if e.identifiant != DISPO:
            _archiver(racine, e.identifiant, T0, (FIXTURES / "bdpm" / e.fichier).read_bytes())
    _archiver(racine, DISPO, T0, _dispo_synthetique(avec_retirees=True))
    _archiver(racine, DISPO, T1, _dispo_synthetique(avec_retirees=False))
    _archiver(racine, DISPO, T2, _dispo_synthetique(avec_retirees=False))
    sortie = tmp_path_factory.mktemp("sortie") / "evenements"
    assert rejeu.executer(racine, sortie, charger_tous(), list(charger_tous())).code_sortie == 0
    dossier = tmp_path_factory.mktemp("silver") / "lakehouse"
    construction.construire(sortie, dossier, charger_tous(), list(charger_tous()))
    return dossier


def _vues(dossier: Path, instant: datetime) -> tuple[vues_gold.Vues, dict[str, EntiteTypee]]:
    entrepot = Entrepot.ouvrir(dossier)
    etats = etats_types(entrepot, charger_tous(), instant)
    return vues_gold.vues(entrepot, charger_tous(), etats, instant), etats


def _etats(dispo: pa.Table, code_cis: str) -> list[tuple[str | None, str, str | None]]:
    """(CIP13, état, code statut) des lignes d'un CIS, dans l'ordre de la vue."""
    lignes = dispo.filter(pc.equal(dispo["code_cis"], pa.scalar(code_cis))).to_pylist()
    return [(lg["code_cip13"], lg["etat_signalement"], lg["code_statut"]) for lg in lignes]


# --- exigence 2 : la priorité, une branche par test ---------------------------------------------


def test_une_ligne_en_cours_est_declaree_sur_chaque_presentation_visee(vues_fixtures: Path) -> None:
    vues, _ = _vues(vues_fixtures, T0)
    a = vues.disponibilite.filter(pc.equal(vues.disponibilite["code_cis"], pa.scalar(CIS_A)))
    assert a.num_rows == 6 == len(_presentations(CIS_A))
    assert set(a["etat_signalement"].to_pylist()) == {"declare"}
    assert set(a["portee"].to_pylist()) == {"specialite"}  # la colonne qui marque l'expansion
    assert sorted(a["code_cip13"].to_pylist()) == _presentations(CIS_A)


def test_une_ligne_retiree_donne_la_fin_de_publication(vues_fixtures: Path) -> None:
    vues, _ = _vues(vues_fixtures, T2)
    a = vues.disponibilite.filter(pc.equal(vues.disponibilite["code_cis"], pa.scalar(CIS_A)))
    assert set(a["etat_signalement"].to_pylist()) == {"fin_de_publication"}
    assert set(a["fin_publication"].to_pylist()) == {T1}  # la date de la fermeture
    assert set(a["code_statut"].to_pylist()) == {"2"}  # son dernier statut
    assert set(a["libelle_statut"].to_pylist()) == {"Tension d'approvisionnement"}


def test_rien_de_ce_qu_on_a_appris_apres_l_instant(vues_fixtures: Path) -> None:
    """À 14:30, la fermeture de 15:17 n'est pas encore connue : A reste déclarée."""
    vues, _ = _vues(vues_fixtures, ENTRE)
    assert {e for _, e, _ in _etats(vues.disponibilite, CIS_A)} == {"declare"}
    assert "fin_de_publication" not in vues.disponibilite["etat_signalement"].to_pylist()


def test_une_ligne_en_cours_l_emporte_sur_une_fermeture(vues_fixtures: Path) -> None:
    vues, _ = _vues(vues_fixtures, T2)
    premiere, seconde = _presentations(CIS_B)
    assert _etats(vues.disponibilite, CIS_B) == [
        (premiere, "declare", "1"),  # la ligne directe ; la ligne de la spécialité est retirée
        (seconde, "fin_de_publication", "2"),
    ]
    avant, _ = _vues(vues_fixtures, T0)
    assert sorted(_etats(avant.disponibilite, CIS_B)) == [
        (premiere, "declare", "1"),
        (premiere, "declare", "2"),  # une ligne par signalement en cours
        (seconde, "declare", "2"),
    ]


def test_sans_signalement_ni_fermeture_aucun_signalement(vues_fixtures: Path) -> None:
    vues, _ = _vues(vues_fixtures, T2)
    assert _etats(vues.disponibilite, CIS_C) == [
        (cip, "aucun_signalement", None) for cip in _presentations(CIS_C)
    ]


def test_doublons_annonces_et_presentations_inconnues(vues_fixtures: Path) -> None:
    vues, _ = _vues(vues_fixtures, T2)
    d = vues.disponibilite.filter(pc.equal(vues.disponibilite["code_cis"], pa.scalar(CIS_D)))
    assert set(d["occurrences"].to_pylist()) == {2} and d.num_rows == len(_presentations(CIS_D))
    (orpheline,) = vues.disponibilite.filter(
        pc.equal(vues.disponibilite["code_cis"], pa.scalar(CIS_SANS_PRESENTATION))
    ).to_pylist()
    assert orpheline["code_cip13"] is None and orpheline["presentation_connue"] is False
    assert orpheline["debut_a_venir"] is True and orpheline["etat_signalement"] == "declare"
    fiche = vues.fiche.filter(pc.equal(vues.fiche["code_cis"], pa.scalar(CIS_SANS_PRESENTATION)))
    (partielle,) = fiche.to_pylist()
    assert partielle["dans_referentiel"] is False and partielle["presentations"] is None
    assert partielle["disponibilite"][0]["debut_a_venir"] is True


# --- exigence 1 : chaque vue contre sa référence DuckDB ------------------------------------------


@pytest.mark.parametrize("instant", [T0, ENTRE, T2])
def test_chaque_vue_egale_sa_reference_duckdb(vues_fixtures: Path, instant: datetime) -> None:
    entrepot = Entrepot.ouvrir(vues_fixtures)
    etats = etats_types(entrepot, charger_tous(), instant)
    vues = vues_gold.vues(entrepot, charger_tous(), etats, instant)
    con = ref.connexion_reference(
        etats, ref.historique(entrepot, etats), disponibilite_courante=vues.disponibilite
    )
    for vue, requete in (
        (vues.fiche, ref.FICHE),
        (vues.disponibilite, ref.DISPONIBILITE),
        (vues.alternatives, ref.ALTERNATIVES),
    ):
        attendue = ref.reference(con, requete, instant)
        assert attendue.num_rows == vue.num_rows
        assert ref.multiensemble(vue) == ref.multiensemble(attendue)
        assert vue.schema.names == attendue.schema.names


# --- les commandes ------------------------------------------------------------------------------


def test_gold_fiche_en_ligne_de_commande(vues_fixtures: Path) -> None:
    base = ["gold", "fiche", "--entrepot", str(vues_fixtures), "--a", "2026-10-24T16:17:00Z"]
    texte = CliRunner().invoke(application, [*base, "--cis", CIS_B, "--format", "texte"])
    assert texte.exit_code == 0, texte.output
    assert "fiche partielle" in texte.stdout  # CIS_B n'est pas dans l'extrait de CIS_bdpm.txt
    assert "Rupture de stock depuis le 2026-10-01" in texte.stdout
    assert "CIS_CIP_Dispo_Spec.txt : observée depuis le" in texte.stdout
    jsonl = CliRunner().invoke(application, [*base, "--tout"])
    assert jsonl.exit_code == 0 and len(jsonl.stdout.splitlines()) > 40
    for mauvais in ([], ["--tout", "--format", "texte"], ["--cis", "00000000"]):
        assert CliRunner().invoke(application, [*base, *mauvais]).exit_code == 2, mauvais


def test_gold_disponibilite_alternatives_et_sql(vues_fixtures: Path) -> None:
    base = ["--entrepot", str(vues_fixtures), "--a", "2026-10-24T16:17:00Z", "--format", "csv"]
    dispo = CliRunner().invoke(
        application,
        ["gold", "disponibilite", *base, "--cis", CIS_A, "--colonne", "etat_signalement"],
    )
    assert dispo.exit_code == 0, dispo.output
    assert dispo.stdout.splitlines() == ["etat_signalement", *["fin_de_publication"] * 6]
    assert CliRunner().invoke(application, ["gold", "alternatives", *base]).exit_code == 2
    sql = CliRunner().invoke(
        application,
        [
            "gold",
            "sql",
            *base,
            "SELECT etat_signalement, count(*) n FROM disponibilite_courante GROUP BY 1 ORDER BY 1",
        ],
    )
    assert sql.exit_code == 0, sql.output
    comptes = dict(ligne.split(",") for ligne in sql.stdout.splitlines()[1:])
    assert comptes["fin_de_publication"] == "7"  # six présentations de A, la seconde de B


def test_le_texte_de_la_fiche_ne_devine_rien(vues_fixtures: Path) -> None:
    vues, _ = _vues(vues_fixtures, T0)
    fiche = vues.fiche.filter(pc.equal(vues.fiche["code_cis"], pa.scalar(CIS_D))).to_pylist()[0]
    texte = fiche_en_texte(fiche)
    assert "Remise à disposition depuis le 2026-10-02" in texte
    sans = vues.fiche.filter(pc.equal(vues.fiche["code_cis"], pa.scalar(CIS_C))).to_pylist()[0]
    assert "aucun signalement dans le fichier de disponibilité (ce n'est pas « disponible »)" in (
        fiche_en_texte(sans)
    )
    assert etat_silver.lire_instant("2026-10-24T14:30:00Z") == ENTRE
