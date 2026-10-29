"""Mission 06, paliers 1 et 2 : le gold du jeu de démo ``demo/archive``.

Palier 1 : l'état typé et les contrôles. Palier 2 : les vues métier, comparées
à leur requête DuckDB de référence sur un échantillon fixe de CIS (ceux des
questions et les cas limites du §0), et les 25 questions recalculées depuis le
gold.

Le silver est celui de ``demo_silver`` (``conftest``), construit une fois par
session dans un dossier jetable. Les chiffres attendus sont ceux mesurés au
§0 (``docs/rapports/mission-06/points-a-trancher.md``). Aucun réseau, aucun
conteneur.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
from typer.testing import CliRunner

from pharmaflux.cli import QUESTIONS_PAR_DEFAUT as QUESTIONS
from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_identifiant, charger_tous
from pharmaflux.demo.jeu import JEU_PAR_DEFAUT
from pharmaflux.evaluation import questions as jeu_questions
from pharmaflux.evaluation.questions import Jeu
from pharmaflux.gold import COLONNES_ILLISIBLES
from pharmaflux.gold import qualite as qualite_gold
from pharmaflux.gold import questions as questions_gold
from pharmaflux.gold import vues as vues_gold
from pharmaflux.gold.sql import etats_types
from pharmaflux.gold.typage import derniere_observation, etat_type
from pharmaflux.silver import etat as etat_silver
from pharmaflux.silver.entrepot import Entrepot
from tests import references_gold as ref

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


# --- palier 2 : les vues métier, leurs références, les questions ---------------------------------


def _echantillon(vues: vues_gold.Vues, jeu: Jeu) -> list[str]:
    """Les CIS de l'exigence 1 : ceux des questions, puis les cas limites du §0."""
    fiche, dispo = vues.fiche, vues.disponibilite
    cis = {
        q.attendu.cle["code_cis"]
        for q in jeu.questions
        if q.attendu and "code_cis" in q.attendu.cle
    }
    cip13 = [
        q.attendu.cle["code_cip13"]
        for q in jeu.questions
        if q.attendu and "code_cip13" in q.attendu.cle
    ]
    cis |= set(
        dispo.filter(pc.is_in(dispo["code_cip13"], value_set=pa.array(cip13)))[
            "code_cis"
        ].to_pylist()
    )
    groupes = [
        q.attendu.cle["identifiant_groupe"]
        for q in jeu.questions
        if q.attendu and "identifiant_groupe" in q.attendu.cle
    ]
    alt = vues.alternatives
    cis |= set(
        alt.filter(pc.is_in(alt["identifiant_groupe"], value_set=pa.array(groupes)))[
            "code_cis"
        ].to_pylist()
    )
    longueurs = {
        nom: pc.fill_null(pc.list_value_length(fiche[nom]), 0)
        for nom in ("groupes_generiques", "presentations", "avis_smr")
    }
    plusieurs_groupes = fiche.filter(pc.greater(longueurs["groupes_generiques"], 1))["code_cis"]
    cis.add(min(plusieurs_groupes.to_pylist()))
    for nom, maximum in (("presentations", 37), ("avis_smr", 44)):
        (code,) = fiche.filter(pc.equal(longueurs[nom], maximum))["code_cis"].to_pylist()[:1]
        cis.add(code)
    cis.add("62119207")  # BEFIZAL L.P. : deux statuts sur la même fiche ANSM
    cis.add(min(fiche.filter(pc.invert(fiche["dans_referentiel"]))["code_cis"].to_pylist()))
    orphelins = dispo.filter(pc.invert(dispo["presentation_connue"]))
    cis.add(min(orphelins.filter(pc.is_null(orphelins["code_cip13"]))["code_cis"].to_pylist()))
    return sorted(cis)


def test_les_vues_du_jeu_egalent_leur_reference_sur_l_echantillon(
    demo_silver: tuple[Path, Path],
) -> None:
    _, dossier = demo_silver
    entrepot = Entrepot.ouvrir(dossier)
    instant = etat_silver.lire_instant(DERNIERE)
    etats = etats_types(entrepot, charger_tous(), instant)
    vues = vues_gold.vues(entrepot, charger_tous(), etats, instant)
    assert (vues.fiche.num_rows, pc.sum(vues.fiche["dans_referentiel"]).as_py()) == (21_445, 15_883)
    assert vues.disponibilite.num_rows == 20_918
    comptes = vues.disponibilite.group_by("etat_signalement").aggregate([([], "count_all")])
    assert dict(
        zip(comptes["etat_signalement"].to_pylist(), comptes["count_all"].to_pylist(), strict=True)
    ) == {
        "declare": 914,
        "aucun_signalement": 20_004,
    }
    par_expansion = vues.disponibilite.filter(pc.equal(vues.disponibilite["portee"], "specialite"))
    assert pc.count_distinct(par_expansion["code_cip13"]).as_py() == 849
    echantillon = _echantillon(vues, jeu_questions.charger(QUESTIONS, charger_tous()))
    assert len(echantillon) >= 25
    con = ref.connexion_reference(
        etats, ref.historique(entrepot, etats), echantillon, vues.disponibilite
    )
    for vue, requete in (
        (vues.fiche, ref.FICHE),
        (vues.disponibilite, ref.DISPONIBILITE),
        (vues.alternatives, ref.ALTERNATIVES),
    ):
        attendue = ref.reference(con, requete, instant)
        assert ref.multiensemble(vue, echantillon) == ref.multiensemble(attendue)
        assert attendue.num_rows > 0


def test_les_25_questions_concordent_depuis_le_gold(demo_silver: tuple[Path, Path]) -> None:
    _, dossier = demo_silver
    resultat = CliRunner().invoke(
        application,
        ["questions", "verifier", "--racine", str(JEU_PAR_DEFAUT), "--entrepot", str(dossier)],
    )
    assert resultat.exit_code == 0, resultat.output
    assert "40 question(s) : 25 conforme, 5 non calculable, 10 sans attendu." in resultat.stdout
    assert resultat.stdout.splitlines()[-1] == "25 question(s) depuis le gold : 25 concorde."
    routes = [
        lg.split(" : ")[0].split(maxsplit=3)[-1]
        for lg in resultat.stdout.splitlines()
        if lg.startswith("gold ")
    ]
    assert sum(r.startswith(("fiche", "alternatives")) for r in routes) == 24
    assert routes.count("colonnes typées") == 1


def test_une_discordance_affiche_les_deux_calculs(demo_silver: tuple[Path, Path]) -> None:
    _, dossier = demo_silver
    jeu = jeu_questions.charger(QUESTIONS, charger_tous())
    question = next(q for q in jeu.questions if q.id == "remboursement-001")
    assert question.attendu is not None
    faux = dataclasses.replace(
        question.attendu, valeurs=({**question.attendu.valeurs[0], "prix_public": "2,19"},)
    )
    jeu_faux = dataclasses.replace(jeu, questions=(dataclasses.replace(question, attendu=faux),))
    bilan = questions_gold.verifier_gold(jeu_faux, Entrepot.ouvrir(dossier), charger_tous())
    (resultat,) = bilan.resultats
    assert resultat.verdict is questions_gold.VerdictGold.DISCORDE and bilan.code_sortie == 2
    sortie = "\n".join(questions_gold.formater(bilan))
    assert '"prix_public": "2.19"' in sortie and '"prix_public": "2.18"' in sortie
