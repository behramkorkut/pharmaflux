"""Mission 08, palier 2 : l'assistant gouverné.

Aucun test ne construit un client réel : tous passent par le double (addendum 1 J). Les tests
du chemin montent un petit index dans le Qdrant simulé (trois fiches), l'encodeur de test, et
font répondre le double. Un test vérifie que, sans double et sans clé, l'assistant s'arrête
proprement (« clé absente », code 2), sans réseau.
"""

from __future__ import annotations

import gzip
import os
import random
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.assistant import chemin, controle, regles, repere
from pharmaflux.assistant.budget import (
    PLAFOND,
    BudgetDepasse,
    Journal,
    Ligne,
    Usage,
    cout,
    cout_estime,
    exiger_budget,
    jetons_estimes,
)
from pharmaflux.assistant.cache import CacheReponses
from pharmaflux.assistant.cache import cle as cle_cache
from pharmaflux.assistant.client import (
    SCHEMA,
    ClientClaude,
    DoubleClient,
    ErreurAPI,
    ReponseLLM,
    cle_presente,
    interpreter_reponse,
)
from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evaluation.questions import Jeu
from pharmaflux.evaluation.questions import charger as charger_jeu
from pharmaflux.index import construction
from pharmaflux.index.construction import Cache
from pharmaflux.index.encodeur import EncodeurTest
from pharmaflux.index.qdrant import Qdrant
from tests.qdrant_simule import QdrantSimule
from tests.test_index import ecrire_fragments, trois_fiches

_USAGE_DEFAUT = Usage(100, 50)


def _llm(
    comportement: str = "reponse",
    texte: str = "Un signalement de disponibilité est en cours pour ce médicament.",
    citations: tuple[int, ...] = (1,),
    *,
    motif: str | None = None,
    orientation: str | None = None,
    reserve: bool = False,
    usage: Usage = _USAGE_DEFAUT,
    stop_reason: str = "end_turn",
    technique: bool = False,
) -> ReponseLLM:
    return ReponseLLM(
        comportement, texte, citations, motif, orientation, reserve, usage, stop_reason, technique
    )


# --- règles (hors LLM) -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Puis-je remplacer LARIAM 250 mg par un autre antipaludique ?",
        "Quelle dose d'OZEMPIC dois-je prendre ?",
        "KARDEGIC 75 mg est-il compatible avec une grossesse ?",
        "ZELBORAF risque-t-il d'abîmer mon foie dans mon cas ?",
    ],
)
def test_refus_medical_declenche(question: str) -> None:
    assert regles.refus_medical(question) is not None


@pytest.mark.parametrize(
    "question",
    [
        # zone grise (« mon traitement », aucune décision) ; « puis-je » sans geste de soin
        "Mon traitement par LARIAM 250 mg est-il concerné par une rupture ?",
        "Où puis-je acheter DOLIPRANE au prix le plus bas ?",
        "DOLIPRANE 1000 mg est-il disponible ?",
    ],
)
def test_refus_medical_ne_declenche_pas(question: str) -> None:
    assert regles.refus_medical(question) is None


def test_abstention_depense_et_hors_perimetre() -> None:
    assert regles.abstention("Quelle dépense remboursée en 2025 pour les statines ?") is not None
    assert regles.abstention("Quel montant a été remboursé en 2025 ?") is not None
    assert regles.abstention("Combien coûte une complémentaire santé ?") is not None
    assert regles.abstention("Quels sont les effets indésirables de DOLIPRANE ?") is not None
    assert regles.abstention("DOLIPRANE est-il disponible ?") is None


# --- repérage ----------------------------------------------------------------------------------


def _dico(*denoms: tuple[str, str]) -> repere.Dictionnaire:
    return repere.construire_dictionnaire(
        [{"code_cis": cis, "denomination": nom} for cis, nom in denoms]
    )


def test_reperage_cis_explicite_et_denomination() -> None:
    dico = _dico(("60000002", "PARACETAMOL TEST"), ("60000003", "IBUPROFENE TEST"))
    assert repere.reperer("68705771 est-il connu ?", dico).vises == {"68705771"}
    assert repere.reperer("PARACETAMOL est-il disponible ?", dico).vises == {"60000002"}
    assert not repere.reperer("Quel temps fait-il ?", dico).un_medicament_est_vise


def test_deux_medicaments_meme_dci_marques_differentes() -> None:
    """Contrôle de la v1 (disponibilite-009 vs -010) : distinguer deux produits de même DCI."""
    dico = _dico(
        ("62934770", "SUNITINIB BIOGARAN 37,5 mg, gélule"),
        ("62934771", "SUNITINIB ZENTIVA 37,5 mg, gélule"),
    )
    deux = "SUNITINIB BIOGARAN et SUNITINIB ZENTIVA sont-ils tous les deux en tension ?"
    un = "SUNITINIB BIOGARAN 37,5 mg, gélule est-il en tension d'approvisionnement ?"
    assert repere.medicaments_nommes(repere.reperer(deux, dico), deux, dico) == 2
    assert repere.medicaments_nommes(repere.reperer(un, dico), un, dico) == 1


# --- contrôle des nombres et des dates ---------------------------------------------------------


def test_controle_dates_trois_formes_et_nombres() -> None:
    frag = (
        "CIS 67026956 — Avis SMR 20260909. Taux 65 % prix public 12,50 €. Remboursé 1 000 unités."
    )
    for texte in ("Avis du 9 septembre 2026.", "Avis du 09/09/2026.", "Avis du 2026-09-09."):
        assert controle.controler(texte, [frag], "question") is None
    assert controle.controler("Taux de 65% et prix 12,5 €.", [frag], "q") is None
    assert controle.controler("Le taux est 73 %.", [frag], "q") is not None
    assert controle.controler("Avis du 10/09/2026.", [frag], "q") is not None


def test_controle_un_code_colle_a_un_label_nest_pas_un_faux_nombre() -> None:
    """Régression (démo Q1) : « CIP13 3400933961688 » ne doit pas donner « 13 340 » (le « 13 »
    du label collé au début du CIP) ni couper le CIP ; « P01BC02 » ne donne aucun nombre."""
    nombres, _ = controle.extraire("présentation CIP13 3400933961688 (ATC P01BC02), boîte de 8")
    assert nombres == {"3400933961688", "8"}
    frag = "CIS 65999556 — plaquette de 8 comprimés (CIP13 3400933961688)"
    reponse = "Sa seule présentation est la CIP13 3400933961688, une boîte de 8 comprimés."
    assert controle.controler(reponse, [frag], "LARIAM en rupture ?") is None


def test_controle_nombre_colle_a_son_unite_est_vu() -> None:
    """Un nombre collé à son unité (« 250mg », « 10mg ») doit être lu : sinon un chiffre
    inventé et collé à son unité passerait le contrôle sans être vu (régression du palier 3)."""
    assert controle.extraire("10mg")[0] == {"10"}
    frag = "CIS 60000001 — DOLIPRANE 250mg, comprimé"
    assert controle.controler("La dose est 250mg.", [frag], "q") is None  # appuyé → passe
    assert controle.controler("La dose est 500mg.", [frag], "q") is not None  # inventé → abstention


# --- budget ------------------------------------------------------------------------------------


def test_budget_cout_estimation_et_journal(tmp_path: Path) -> None:
    assert cout(Usage(1_000_000, 0)) == pytest.approx(4.0)
    assert cout(Usage(0, 1_000_000)) == pytest.approx(20.0)
    assert cout(Usage(0, 0, jetons_cache_lecture=1_000_000)) == pytest.approx(0.20)
    assert jetons_estimes("abcd" * 10) > 0
    assert cout_estime("x" * 100, 4000) > 0
    journal = Journal(tmp_path / "depenses.jsonl")
    assert journal.total() == 0.0 and journal.reste() == PLAFOND
    journal.ajouter(Ligne("2026-10-30T00:00:00Z", 8, "q-1", "m", "low", 10, 5, 0, 0, 1.5))
    assert journal.total() == pytest.approx(1.5) and journal.reste() == pytest.approx(PLAFOND - 1.5)


def test_exiger_budget_refuse_au_dela_du_plafond(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "depenses.jsonl")
    journal.ajouter(Ligne("2026-10-30T00:00:00Z", 8, "q-1", "m", "low", 0, 0, 0, 0, PLAFOND - 0.01))
    with pytest.raises(BudgetDepasse):
        exiger_budget(journal, 0.5)


# --- cache des réponses ------------------------------------------------------------------------


def test_cache_cle_stable_et_lecture_ecriture(tmp_path: Path) -> None:
    a = cle_cache("sys", "contenu", "m", "low", 4000, SCHEMA)
    assert a == cle_cache("sys", "contenu", "m", "low", 4000, SCHEMA)
    assert a != cle_cache("sys", "contenu", "m", "medium", 4000, SCHEMA)
    cache = CacheReponses(tmp_path / "assistant")
    try:
        assert cache.lire(a) is None
        cache.ecrire(a, {"x": 1})
        assert cache.lire(a) == {"x": 1}
    finally:
        cache.close()


# --- interprétation de la réponse du SDK (sortie illisible → technique) ------------------------


def _faux_usage() -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=2500,
        output_tokens=300,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )


def _faux_reponse(content: list[object], stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, usage=_faux_usage(), stop_details=None
    )


def test_interpreter_sortie_valide() -> None:
    import json

    contenu = json.dumps(
        {
            "comportement": "reponse",
            "texte": "x",
            "citations": [1],
            "motif": None,
            "orientation": None,
            "reserve": False,
        }
    )
    r = interpreter_reponse(_faux_reponse([SimpleNamespace(type="text", text=contenu)]))
    assert r.comportement == "reponse" and not r.technique
    assert r.usage.jetons_entree == 2500 and r.usage.jetons_sortie == 300


@pytest.mark.parametrize(
    "content",
    [
        [],  # aucun bloc texte
        [SimpleNamespace(type="text", text="pas du json")],  # JSON invalide
        [SimpleNamespace(type="text", text='{"texte": "x"}')],  # clé manquante
    ],
)
def test_interpreter_sortie_illisible_est_technique_avec_usage(content: list[object]) -> None:
    """Contrôle du palier 2, point 1 : une sortie illisible devient une abstention technique
    qui porte son usage — l'appel payé est donc journalisable, jamais perdu par une exception."""
    r = interpreter_reponse(_faux_reponse(content))
    assert r.technique and r.comportement == "abstention"
    assert r.usage.jetons_entree == 2500 and r.usage.jetons_sortie == 300


def test_interpreter_refus_du_modele_est_technique() -> None:
    r = interpreter_reponse(_faux_reponse([], stop_reason="refusal"))
    assert r.technique and r.stop_reason == "refusal"


# --- le chemin, bout en bout, avec le double ---------------------------------------------------


@pytest.fixture
def index(tmp_path: Path) -> Iterator[Qdrant]:
    simule = QdrantSimule()
    frags = ecrire_fragments(tmp_path, trois_fiches())
    cache_vec = Cache(tmp_path / "travail", EncodeurTest.empreinte)
    client = Qdrant("http://qdrant.test", simule.transport())
    construction.construire(client, EncodeurTest(), frags, cache_vec)
    cache_vec.close()
    yield client
    client.close()


def _demander(index: Qdrant, question: str, double: DoubleClient, tmp_path: Path, **kw: object):  # type: ignore[no-untyped-def]
    journal = Journal(tmp_path / "depenses.jsonl")
    cache = CacheReponses(tmp_path / "assistant")
    try:
        return chemin.demander(index, EncodeurTest(), double, question, journal, cache, **kw)  # type: ignore[arg-type]
    finally:
        cache.close()


def test_refus_medical_ne_touche_pas_le_llm(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(fixe=_llm())
    reponse = _demander(
        index, "Puis-je prendre PARACETAMOL TEST pour ma fièvre ?", double, tmp_path
    )
    assert reponse.comportement == "refus_medical"
    assert reponse.orientation and reponse.cout == 0.0
    assert double.appels == []  # décidé hors du LLM


def test_abstention_depense_hors_llm(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(fixe=_llm())
    reponse = _demander(
        index, "Quelle dépense remboursée en 2025 pour PARACETAMOL ?", double, tmp_path
    )
    assert reponse.comportement == "abstention" and reponse.decision == "abstention_regle"
    assert double.appels == []


def test_porte_structurelle_sur_cis_absent(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(fixe=_llm())
    reponse = _demander(index, "Le CIS 99999999 est-il disponible ?", double, tmp_path)
    assert reponse.comportement == "abstention" and reponse.decision == "porte_structurelle"
    assert double.appels == []


def test_deux_medicaments_abstention(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(fixe=_llm())
    question = "PARACETAMOL TEST et IBUPROFENE TEST sont-ils tous les deux disponibles ?"
    reponse = _demander(index, question, double, tmp_path)
    assert reponse.comportement == "abstention" and reponse.decision == "deux_medicaments"
    assert double.appels == []


def test_reponse_verifiee_journalise_et_cite(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(fixe=_llm(citations=(1,)))
    reponse = _demander(index, "PARACETAMOL TEST est-il disponible ?", double, tmp_path)
    assert reponse.comportement == "reponse" and reponse.citations
    assert reponse.cout > 0 and not reponse.depuis_cache
    assert Journal(tmp_path / "depenses.jsonl").total() == pytest.approx(reponse.cout)


def test_controle_echoue_devient_abstention(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(fixe=_llm(texte="Le taux de remboursement est de 73 %.", citations=(1,)))
    reponse = _demander(index, "PARACETAMOL TEST est-il disponible ?", double, tmp_path)
    assert reponse.comportement == "abstention" and reponse.decision == "controle"


def test_citation_hors_fournis_devient_abstention(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(fixe=_llm(citations=(99,)))
    reponse = _demander(index, "PARACETAMOL TEST est-il disponible ?", double, tmp_path)
    assert reponse.comportement == "abstention" and reponse.decision == "controle"


def test_abstention_technique_du_modele(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(
        fixe=_llm(comportement="abstention", technique=True, stop_reason="refusal")
    )
    reponse = _demander(index, "PARACETAMOL TEST est-il disponible ?", double, tmp_path)
    assert reponse.comportement == "abstention" and reponse.decision == "technique"


def test_cache_evite_le_second_appel(index: Qdrant, tmp_path: Path) -> None:
    double = DoubleClient(fixe=_llm(citations=(1,)))
    premiere = _demander(index, "PARACETAMOL TEST est-il disponible ?", double, tmp_path)
    seconde = _demander(index, "PARACETAMOL TEST est-il disponible ?", double, tmp_path)
    assert len(double.appels) == 1  # le second passe par le cache
    assert not premiere.depuis_cache and seconde.depuis_cache
    assert seconde.cout == 0.0


def test_technique_journalisee_mais_pas_cachee(index: Qdrant, tmp_path: Path) -> None:
    """Contrôle du palier 2, point 2 : une abstention technique est journalisée (l'appel est
    payé) mais n'entre pas au cache — une reprise retente l'appel."""
    double = DoubleClient(
        fixe=_llm(comportement="abstention", technique=True, stop_reason="refusal")
    )
    question = "PARACETAMOL TEST est-il disponible ?"
    r1 = _demander(index, question, double, tmp_path)
    r2 = _demander(index, question, double, tmp_path)
    assert r1.decision == "technique" and r2.decision == "technique"
    assert len(double.appels) == 2  # pas de cache : le second appel a bien lieu
    assert Journal(tmp_path / "depenses.jsonl").total() == pytest.approx(cout(_USAGE_DEFAUT) * 2)


def test_budget_refuse_avant_tout_appel(index: Qdrant, tmp_path: Path) -> None:
    journal = Journal(tmp_path / "depenses.jsonl")
    journal.ajouter(Ligne("2026-10-30T00:00:00Z", 8, "q", "m", "low", 0, 0, 0, 0, PLAFOND - 0.001))
    cache = CacheReponses(tmp_path / "assistant")
    double = DoubleClient(fixe=_llm())
    try:
        with pytest.raises(BudgetDepasse):
            chemin.demander(
                index, EncodeurTest(), double, "PARACETAMOL TEST disponible ?", journal, cache
            )
    finally:
        cache.close()
    assert double.appels == []


# --- la ligne de commande ----------------------------------------------------------------------


@pytest.fixture
def cli_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> QdrantSimule:
    simule = QdrantSimule()
    frags = ecrire_fragments(tmp_path, trois_fiches())
    cache_vec = Cache(tmp_path / "travail", EncodeurTest.empreinte)
    client = Qdrant("http://qdrant.test", simule.transport())
    construction.construire(client, EncodeurTest(), frags, cache_vec)
    cache_vec.close()
    client.close()
    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", simule.transport)
    return simule


@pytest.mark.usefixtures("cli_index")
def test_cli_demander_texte(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli, "fabriquer_client_llm", lambda: DoubleClient(fixe=_llm(citations=(1,)))
    )
    resultat = CliRunner().invoke(
        application,
        [
            "assistant",
            "demander",
            "PARACETAMOL TEST disponible ?",
            "--modele",
            "test",
            "--donnees",
            str(tmp_path / "a"),
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    assert "Réponse" in resultat.output and "état de l'index au" in resultat.output
    attendu = CliRunner().invoke(
        application,
        ["assistant", "depenses", "--donnees", str(tmp_path / "a")],
    )
    assert "mission 8" in attendu.output


@pytest.mark.usefixtures("cli_index")
def test_cli_demander_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli, "fabriquer_client_llm", lambda: DoubleClient(fixe=_llm(citations=(1,)))
    )
    resultat = CliRunner().invoke(
        application,
        [
            "assistant",
            "demander",
            "PARACETAMOL TEST disponible ?",
            "--modele",
            "test",
            "--format",
            "json",
            "--donnees",
            str(tmp_path / "a"),
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    import json

    charge = json.loads(resultat.output)
    assert charge["comportement"] == "reponse" and charge["trace"]["decision_controle"] == "vérifié"


def test_cli_cle_absente_sans_double(monkeypatch: pytest.MonkeyPatch) -> None:
    """Addendum 1 J : sans double et sans clé, arrêt propre « clé absente », code 2, sans réseau."""
    monkeypatch.setattr(cli, "fabriquer_client_llm", lambda: None)
    for nom in [n for n in os.environ if n.startswith("ANTHROPIC_")]:
        monkeypatch.delenv(nom)
    assert not cle_presente()
    resultat = CliRunner().invoke(application, ["assistant", "demander", "test ?"])
    assert resultat.exit_code == 2
    assert "clé absente" in resultat.output


# --- la v1 entière contre les règles et le repérage (addendum 1 D2, palier 3) -------------------

JEU_V1 = Path("evaluation/questions-reference-v1.toml")
CIS_BDPM_DEMO = Path(
    "demo/archive/bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz"
)
CIS_GENER_DEMO = Path(
    "demo/archive/bronze/bdpm/CIS_GENER_bdpm.txt/2026-10-24/20261024T194157Z__04ea92fb3d2e.txt.gz"
)


def _lignes_bdpm(chemin: Path) -> list[list[str]]:
    lignes = gzip.decompress(chemin.read_bytes()).decode("cp1252").splitlines()
    return [ligne.split("\t") for ligne in lignes if ligne.strip()]


@pytest.fixture(scope="module")
def jeu_v1() -> Jeu:
    return charger_jeu(JEU_V1, charger_tous())


def test_v1_chaque_question_medical_est_refusee_par_les_regles(jeu_v1: Jeu) -> None:
    medicales = [q for q in jeu_v1.questions if q.categorie == "medical"]
    assert len(medicales) >= 10
    oublis = [q.id for q in medicales if regles.refus_medical(q.question) is None]
    assert oublis == []


def test_v1_aucune_autre_question_n_est_refusee(jeu_v1: Jeu) -> None:
    """Un faux refus est un défaut, au même titre qu'un oubli (addendum 1 D2) : disponibilite-011
    (« mon traitement », aucune décision) et hors_perimetre-006 (effets indésirables) passent."""
    faux = [
        q.id
        for q in jeu_v1.questions
        if q.categorie != "medical" and regles.refus_medical(q.question) is not None
    ]
    assert faux == []


@pytest.fixture(scope="module")
def dictionnaire_demo() -> repere.Dictionnaire:
    """Le dictionnaire du repérage tiré des 15 883 dénominations réelles du jeu de démo
    (``CIS_bdpm.txt``) et de ses groupes génériques (``CIS_GENER_bdpm.txt``, rendus comme le
    texte d'un fragment ``identite``), dans le dépôt, sans index ni réseau."""
    groupes: dict[str, list[str]] = {}
    for champs in _lignes_bdpm(CIS_GENER_DEMO):
        groupes.setdefault(champs[2], []).append(f"  - groupe {champs[0]} ({champs[1]}), type 0")
    identite = [
        {"code_cis": c[0], "denomination": c[1], "texte": "\n".join(groupes.get(c[0], []))}
        for c in _lignes_bdpm(CIS_BDPM_DEMO)
    ]
    return repere.construire_dictionnaire(identite)


def test_v1_deux_medicaments_seulement_sur_le_piege(
    jeu_v1: Jeu, dictionnaire_demo: repere.Dictionnaire
) -> None:
    """Régression du palier 3 : sur les dénominations réelles, « deux médicaments » ne se
    déclenche que sur le piège disponibilite-010. Avant le correctif, « B O P, comprimé enrobé »
    faisait de « comprime » un nom de médicament, et 18 réponses attendues s'abstenaient."""
    declenchees = [
        q.id
        for q in jeu_v1.questions
        if regles.refus_medical(q.question) is None
        and regles.abstention(q.question) is None
        and repere.medicaments_nommes(
            repere.reperer(q.question, dictionnaire_demo), q.question, dictionnaire_demo
        )
        >= 2
    ]
    assert declenchees == ["disponibilite-010"]


def test_v0_deux_medicaments_jamais(dictionnaire_demo: repere.Dictionnaire) -> None:
    """La v0 (non-régression) : aucune question qui passe les règles ne déclenche « deux
    médicaments » (medical-002 en nomme deux, mais le refus médical la prend avant)."""
    jeu_v0 = charger_jeu(Path("evaluation/questions-reference-v0.toml"), charger_tous())
    declenchees = [
        q.id
        for q in jeu_v0.questions
        if regles.refus_medical(q.question) is None
        and regles.abstention(q.question) is None
        and repere.medicaments_nommes(
            repere.reperer(q.question, dictionnaire_demo), q.question, dictionnaire_demo
        )
        >= 2
    ]
    assert declenchees == []


def test_deux_medicaments_sur_200_tires_au_hasard(dictionnaire_demo: repere.Dictionnaire) -> None:
    """Un test indépendant du jeu d'évaluation (contrôle du palier 3) : 200 médicaments tirés au
    hasard parmi les dénominations du jeu de démo qui ont un mot significatif (15 816 sur
    15 883 ; « B O P » n'en a pas), posés seuls (la règle ne se déclenche jamais, et le
    médicament est repéré), puis deux par deux (elle se déclenche toujours)."""
    dico = dictionnaire_demo
    nommables = sorted(
        cis
        for cis, d in dico.denomination_par_cis.items()
        if repere.premier_mot(d, dico.mots_de_forme)
    )
    tirage = random.Random(8).sample(nommables, 200)

    def compte(question: str) -> int:
        return repere.medicaments_nommes(repere.reperer(question, dico), question, dico)

    seuls = [f"{dico.denomination_par_cis[c]} est-il en rupture de stock ?" for c in tirage]
    assert [q for q in seuls if compte(q) != 1] == []
    assert all(c in repere.reperer(q, dico).vises for c, q in zip(tirage, seuls, strict=True))
    paires = [
        f"{dico.denomination_par_cis[a]} et {dico.denomination_par_cis[b]} sont-ils en rupture ?"
        for a, b in zip(tirage[::2], tirage[1::2], strict=True)
    ]
    assert [q for q in paires if compte(q) < 2] == []


def test_mots_de_forme_ne_nomment_pas_un_medicament() -> None:
    dico = _dico(
        ("60443192", "B O P, comprimé enrobé"),
        ("68486929", "MICROVAL, comprimé enrobé"),
        (
            "60000009",
            "AMOXICILLINE/ACIDE CLAVULANIQUE BIOGARAN 500 mg/62,5 mg, comprimé pelliculé"
            " (rapport amoxicilline/acide clavulanique : 8/1)",
        ),
        ("60000010", "AMOXICILLINE BIOGARAN 500 mg, gélule"),
    )
    assert {"comprime", "enrobe", "pellicule", "gelule"} <= dico.mots_de_forme
    assert "amoxicilline" not in dico.mots_de_forme  # les parenthèses ne sont pas la forme
    question = "MICROVAL, comprimé enrobé est-il en tension d'approvisionnement ?"
    repere_ = repere.reperer(question, dico)
    assert repere_.vises == {"68486929"}
    assert repere.medicaments_nommes(repere_, question, dico) == 1
    assert repere.premier_mot("AMOXICILLINE BIOGARAN 500 mg, gélule", dico.mots_de_forme) == (
        "amoxicilline"
    )


def test_deux_medicaments_nom_contenu_et_groupe_borne() -> None:
    """Un nom contenu dans un autre ne compte pas à part ; l'exception « groupe » ne vaut que
    pour des noms qui tiennent dans le libellé d'un même groupe générique de l'index."""
    groupe_793 = "  - groupe 793 (EZETIMIBE 10 mg - EZETROL 10 mg, comprimé), type 0"
    dico = repere.construire_dictionnaire(
        [
            {"code_cis": cis, "denomination": nom, "texte": texte}
            for cis, nom, texte in (
                ("65381862", "SUNITINIB EG 12,5 mg, gélule", ""),
                ("62934770", "SUNITINIB BIOGARAN 37,5 mg, gélule", ""),
                ("62934771", "SUNITINIB ZENTIVA 37,5 mg, gélule", ""),
                ("63996942", "NEBIVOLOL/HYDROCHLOROTHIAZIDE BIOGARAN 5 mg/ 25 mg, comprimé", ""),
                ("63996900", "NEBIVOLOL BIOGARAN 5 mg, comprimé", ""),
                ("60981780", "EZETIMIBE EG 10 mg, comprimé", groupe_793),
                ("60981789", "EZETROL 10 mg, comprimé", groupe_793),
                ("60234100", "DOLIPRANE 1000 mg, comprimé", ""),
            )
        ]
    )
    cas = (
        ("SUNITINIB BIOGARAN 37,5 mg, gélule est-il en tension ?", 1),
        ("SUNITINIB BIOGARAN et SUNITINIB ZENTIVA sont-ils en tension ?", 2),
        ("NEBIVOLOL/HYDROCHLOROTHIAZIDE BIOGARAN est-il remboursé ?", 1),
        ("NEBIVOLOL BIOGARAN et NEBIVOLOL/HYDROCHLOROTHIAZIDE BIOGARAN ?", 1),
        ("Le princeps du groupe générique « EZETIMIBE 10 mg » (EZETROL) ?", 1),
        ("EZETIMIBE EG et EZETROL sont-ils remboursés ?", 2),  # sans « groupe »
        ("EZETROL et DOLIPRANE sont-ils du même groupe générique ?", 2),  # hors d'un libellé
        ("DOLIPRANE 1000 mg (CIS 60234100) est-il remboursé ?", 1),  # le nom et son CIS
    )
    for question, attendu in cas:
        repere_ = repere.reperer(question, dico)
        assert repere.medicaments_nommes(repere_, question, dico) == attendu, question


# --- le contrôle des dates : avant 2000, année seule, mois sans jour (palier 3) -----------------


def test_controle_dates_anciennes_annee_et_mois() -> None:
    frag = "Autorisation active depuis le 1985-05-17 ; Rupture de stock depuis le 2026-06-25"
    assert controle.extraire("AMM du 02/06/1980")[1] == {(1980, 6, 2)}
    for texte in ("AMM du 17 mai 1985.", "AMM en 1985.", "En rupture depuis juin 2026."):
        assert controle.controler(texte, [frag], "q") is None, texte
    assert controle.controler("AMM du 17/05/1958.", [frag], "q") is not None
    assert controle.controler("En rupture depuis juillet 2026.", [frag], "q") is not None
    assert controle.extraire("CIS 65999556")[1] == frozenset()  # un CIS n'est jamais une date


# --- les remarques du contrôle du palier 2 ------------------------------------------------------


def test_abstention_du_llm_controlee_comme_une_reponse(index: Qdrant, tmp_path: Path) -> None:
    """Un fait sans appui ne passe pas par le texte d'une abstention : le code remplace le texte,
    le motif et l'orientation par les siens."""
    inventee = _llm(
        "abstention",
        "Ce médicament a été retiré le 03/03/2021.",
        (),
        motif="retiré en 2021",
        orientation="voir l'ANSM",
    )
    reponse = _demander(
        index, "PARACETAMOL TEST est-il disponible ?", DoubleClient(fixe=inventee), tmp_path
    )
    assert reponse.comportement == "abstention" and reponse.texte == ""
    assert reponse.motif == chemin.MOTIF_ABSTENTION_LLM and reponse.orientation is None
    sobre = _llm("abstention", "Les fragments ne répondent pas.", (), motif="rien sur ce point")
    reponse = _demander(
        index, "PARACETAMOL TEST est-il cher ?", DoubleClient(fixe=sobre), tmp_path / "b"
    )
    assert (
        reponse.texte == "Les fragments ne répondent pas." and reponse.motif == "rien sur ce point"
    )


def test_refus_du_llm_prend_la_forme_du_code(index: Qdrant, tmp_path: Path) -> None:
    refus = _llm("refus_medical", "Prenez plutôt 2 comprimés.", (1,), motif="dose de 2 comprimés")
    reponse = _demander(index, "PARACETAMOL TEST convient-il ?", DoubleClient(fixe=refus), tmp_path)
    assert reponse.comportement == "refus_medical" and reponse.decision == "llm"
    assert reponse.texte == chemin.TEXTE_REFUS and reponse.citations == ()
    assert reponse.orientation == regles.ORIENTATION_MEDICALE
    assert reponse.motif == chemin.MOTIF_REFUS_LLM  # « 2 » sans appui : motif du code


def test_client_claude_traduit_une_erreur_de_l_api() -> None:
    """Une erreur de l'API (ici une coupure réseau simulée, sans réseau) devient ErreurAPI, que
    les commandes rendent en code 2 avec une ligne lisible (contrôle du palier 2)."""
    import anthropic
    import httpx

    class SdkEnPanne:
        class messages:  # noqa: N801 (mime l'attribut du SDK)
            @staticmethod
            def create(**_: object) -> object:
                requete = httpx.Request("POST", "https://api.anthropic.test/v1/messages")
                raise anthropic.APIConnectionError(request=requete)

    client = ClientClaude(sdk=SdkEnPanne())
    with pytest.raises(ErreurAPI, match="APIConnectionError"):
        client.repondre("s", "c", effort="low", max_tokens=10)


@dataclass
class DoubleEnPanne:
    def repondre(self, *_: object, **__: object) -> ReponseLLM:
        raise ErreurAPI("l'API Claude n'a rendu aucune réponse (OverloadedError, statut 529)")


@pytest.mark.usefixtures("cli_index")
def test_cli_demander_erreur_api_code_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "fabriquer_client_llm", DoubleEnPanne)
    resultat = CliRunner().invoke(
        application,
        [
            "assistant",
            "demander",
            "PARACETAMOL TEST disponible ?",
            "--modele",
            "test",
            "--donnees",
            str(tmp_path / "a"),
        ],
    )
    assert resultat.exit_code == 2
    assert "assistant refusé : l'API Claude n'a rendu aucune réponse" in resultat.output
    assert Journal(tmp_path / "a" / "depenses.jsonl").total() == 0.0  # rien de payé, rien d'écrit
