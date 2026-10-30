"""Mission 07, palier 2 : construire l'index, chercher, décrire son état.

Contre un Qdrant simulé en mémoire (``tests/qdrant_simule.py``) et l'encodeur
de test, déterministe (addendum 1 C2) : la mécanique, pas la qualité. Le vrai
Qdrant est dans ``test_index_integration.py`` ; le vrai modèle, dans
``test_encodeur_modele.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.cli import application
from pharmaflux.index import construction, encodeur, lexical
from pharmaflux.index.construction import Cache, Fragments, IndexRefuse
from pharmaflux.index.encodeur import EncodeurTest
from pharmaflux.index.fragments import fragments
from pharmaflux.index.qdrant import ALIAS, COLLECTION_ETAT, Qdrant, filtre_egal
from tests.qdrant_simule import QdrantSimule
from tests.test_fragments import fiche, presentation, signalement

INSTANT = "2026-10-27T00:17:12Z"


def ecrire_fragments(tmp_path: Path, fiches: list[dict[str, Any]], nom: str = "f") -> Fragments:
    liste = [f for x in fiches for f in fragments(x)]
    chemin = tmp_path / f"{nom}.jsonl"
    chemin.write_text("".join(f.en_jsonl() + "\n" for f in liste), encoding="utf-8")
    return Fragments(chemin, INSTANT, len(fiches), len(liste))


def trois_fiches() -> list[dict[str, Any]]:
    return [
        fiche(code_cis="60000001", presentations=[presentation("3400930000001")]),
        fiche(code_cis="60000002", denomination="PARACETAMOL TEST", disponibilite=[signalement()]),
        fiche(code_cis="60000003", denomination="IBUPROFENE TEST"),
    ]


@pytest.fixture
def simule() -> QdrantSimule:
    return QdrantSimule()


def construire(
    simule: QdrantSimule, tmp_path: Path, frags: Fragments
) -> construction.BilanConstruction:
    cache = Cache(tmp_path / "travail", EncodeurTest.empreinte)
    try:
        with Qdrant("http://qdrant.test", simule.transport()) as client:
            return construction.construire(client, EncodeurTest(), frags, cache)
    finally:
        cache.close()


def test_construire_ecrit_tous_les_fragments_puis_l_alias_puis_l_etat(
    simule: QdrantSimule, tmp_path: Path
) -> None:
    frags = ecrire_fragments(tmp_path, trois_fiches())
    bilan = construire(simule, tmp_path, frags)
    assert bilan.fragments == frags.nombre == 7 and bilan.encodes == 7
    assert bilan.collection == "pharmaflux-f2-test-20261027T001712Z"
    assert simule.alias == {ALIAS: bilan.collection}
    attendus = {f["identifiant"]: f for f in frags.lire()}
    points = simule.points(ALIAS)
    assert set(points) == set(attendus)
    for identifiant, point in points.items():
        assert point["payload"] == {
            k: v for k, v in attendus[identifiant].items() if k != "identifiant"
        }
        attendu = EncodeurTest().passages([attendus[identifiant]["texte"]])[0]
        assert np.allclose(point["vector"]["dense"], attendu), "le vecteur nommé « dense »"
    etat = simule.points(COLLECTION_ETAT)
    assert [p["payload"] for p in etat.values()] == [
        {
            "collection": bilan.collection,
            "instant": INSTANT,
            "vise": None,
            "format": 2,
            "modele": "test",
            "empreinte_modele": "test@1",
            "dimension": 32,
            "fiches": 3,
            "fragments": 7,
            "cis_reduits": None,
        }
    ]
    assert simule.collections[COLLECTION_ETAT]["dimension"] is None, "l'état n'a pas de vecteur"


def test_reconstruire_reprend_le_cache_et_ne_laisse_qu_une_collection(
    simule: QdrantSimule, tmp_path: Path
) -> None:
    frags = ecrire_fragments(tmp_path, trois_fiches())
    premiere = construire(simule, tmp_path, frags)
    seconde = construire(simule, tmp_path, frags)
    assert seconde.encodes == 0, "même modèle, mêmes textes : rien n'est réencodé (PRD §7.5)"
    assert seconde.collection == premiere.collection + "-bis", "la collection lue n'est pas effacée"
    assert set(simule.collections) == {COLLECTION_ETAT, seconde.collection}
    troisieme = construire(simule, tmp_path, frags)
    assert troisieme.collection == premiere.collection
    assert set(simule.collections) == {COLLECTION_ETAT, premiere.collection}
    une_de_plus = ecrire_fragments(tmp_path, [*trois_fiches(), fiche(code_cis="60000004")], "g")
    assert construire(simule, tmp_path, une_de_plus).encodes == 2, "seuls les textes nouveaux"


def test_chercher_rend_les_plus_proches_avec_l_instant_de_l_index(
    simule: QdrantSimule, tmp_path: Path
) -> None:
    frags = ecrire_fragments(tmp_path, trois_fiches())
    construire(simule, tmp_path, frags)
    cible = next(
        f for f in frags.lire() if f["code_cis"] == "60000002" and f["section"] == "disponibilite"
    )
    with Qdrant("http://qdrant.test", simule.transport()) as client:
        etat, resultats = construction.chercher(client, EncodeurTest(), cible["texte"], 3)
        assert etat["instant"] == INSTANT
        # L'hybride (défaut) : le texte exact de la cible la met au rang 1 (dense ET lexical).
        assert resultats[0].charge["texte"] == cible["texte"]
        assert [r.rang for r in resultats] == [1, 2, 3]
        # Le dense seul rend la cible à un cosinus de 1.
        _, denses = construction.chercher(
            client, EncodeurTest(), cible["texte"], 3, mode=construction.MODE_DENSE
        )
        assert denses[0].charge["texte"] == cible["texte"] and denses[0].score == pytest.approx(1)
        _, filtres = construction.chercher(
            client, EncodeurTest(), "x", 10, filtre_egal("section", "identite")
        )
        assert {r.charge["section"] for r in filtres} == {"identite"} and len(filtres) == 3


def test_construire_ecrit_le_vecteur_creux_bm25(simule: QdrantSimule, tmp_path: Path) -> None:
    frags = ecrire_fragments(tmp_path, trois_fiches())
    construire(simule, tmp_path, frags)
    attendus = {f["identifiant"]: f["texte"] for f in frags.lire()}
    for identifiant, point in simule.points(ALIAS).items():
        attendu = lexical.en_creux(lexical.vecteur_document(attendus[identifiant]))
        assert construction._creux_normalise(point["vector"]["lexical"]) == (
            construction._creux_normalise(attendu)
        ), "le vecteur creux est une fonction du texte, écrit à côté du dense"


def test_fusion_rrf_par_rang_et_ex_aequo_tranches_par_identifiant() -> None:
    a = [{"id": "x", "score": 9.0, "payload": {"t": "X"}}, {"id": "y", "score": 8.0, "payload": {}}]
    b = [{"id": "y", "score": 5.0, "payload": {}}, {"id": "z", "score": 4.0, "payload": {}}]
    fusion = construction.fusion_rrf([a, b], 3, constante=60)
    # y paraît dans les deux voies (1/61 + 1/62) ; x au rang 1 de a (1/61) ; z au rang 2 de b.
    assert [p["id"] for p in fusion] == ["y", "x", "z"]
    assert fusion[0]["payload"] == {"t": "X"} or fusion[0]["id"] == "y"
    # Deux ex æquo (chacun rang 1 d'une voie) : l'identifiant croissant tranche.
    exaequo = construction.fusion_rrf(
        [[{"id": "b", "score": 1.0, "payload": {}}], [{"id": "a", "score": 1.0, "payload": {}}]], 2
    )
    assert [p["id"] for p in exaequo] == ["a", "b"]


def test_chercher_lexical_et_hybride_trouvent_par_le_mot(
    simule: QdrantSimule, tmp_path: Path
) -> None:
    frags = ecrire_fragments(tmp_path, trois_fiches())
    construire(simule, tmp_path, frags)
    with Qdrant("http://qdrant.test", simule.transport()) as client:
        # « PARACETAMOL » n'est la dénomination que de 60000002 : le lexical le trouve par le mot.
        _, lex = construction.chercher(
            client, EncodeurTest(), "PARACETAMOL", 3, mode=construction.MODE_LEXICAL
        )
        assert lex and lex[0].charge["code_cis"] == "60000002"
        assert all(r.charge["code_cis"] == "60000002" for r in lex), "seul 60000002 porte ce mot"
        # L'hybride le remonte aussi, là où le dense (aléatoire ici) ne l'aurait pas mis en tête.
        _, hyb = construction.chercher(
            client, EncodeurTest(), "PARACETAMOL", 5, mode=construction.MODE_HYBRIDE
        )
        assert "60000002" in {r.charge["code_cis"] for r in hyb}


def test_chercher_refuse_sans_index_ou_avec_un_autre_modele(
    simule: QdrantSimule, tmp_path: Path
) -> None:
    with (
        Qdrant("http://qdrant.test", simule.transport()) as client,
        pytest.raises(IndexRefuse, match="aucun index"),
    ):
        construction.chercher(client, EncodeurTest(), "x", 5)
    construire(simule, tmp_path, ecrire_fragments(tmp_path, trois_fiches()))

    class Autre(EncodeurTest):
        empreinte = "autre@2"

    with (
        Qdrant("http://qdrant.test", simule.transport()) as client,
        pytest.raises(IndexRefuse, match="encodé par test@1, pas par autre@2"),
    ):
        construction.chercher(client, Autre(), "x", 5)


def test_citer_les_sources_d_un_fragment() -> None:
    charge = {
        "sources": [
            {
                "fichier": "CIS_bdpm.txt",
                "date_source": "2026-09-29",
                "observee_depuis": "2026-10-24T19:41:43Z",
            },
            {"fichier": "CIS_CIP_Dispo_Spec.txt", "date_source": None, "observee_depuis": None},
        ]
    }
    assert construction.citer(charge) == (
        "CIS_bdpm.txt (source du 2026-09-29, observée depuis le 2026-10-24T19:41:43Z) ;"
        " CIS_CIP_Dispo_Spec.txt (source non datée)"
    )


def test_le_verrou_refuse_une_seconde_ecriture(tmp_path: Path) -> None:
    with (
        construction.verrou(tmp_path),
        pytest.raises(IndexRefuse, match="un autre processus"),
        construction.verrou(tmp_path),
    ):
        pass
    with construction.verrou(tmp_path):
        pass  # relâché à la sortie


def test_le_cache_garde_les_vecteurs_par_modele(tmp_path: Path) -> None:
    v = np.arange(4, dtype=np.float32)
    cache = Cache(tmp_path, "a@1")
    cache.ecrire({"sha1": v})
    assert np.array_equal(cache.lire(["sha1", "sha2"])["sha1"], v)
    cache.close()
    autre = Cache(tmp_path, "b@1")
    assert autre.lire(["sha1"]) == {}, "un autre modèle ne lit pas ces vecteurs"
    autre.close()


def test_les_formes_de_lot_d_e5_sont_quatre_et_au_budget() -> None:
    assert encodeur.FORMES == ((16, 64), (8, 128), (4, 256), (2, 512))
    assert all(lignes * largeur == encodeur.BUDGET_JETONS for lignes, largeur in encodeur.FORMES)
    assert encodeur.FORMES[-1][1] == encodeur.FENETRE_E5, "la plus large tient la fenêtre"


def test_l_encodeur_de_test_est_deterministe_et_norme() -> None:
    a, b = EncodeurTest().passages(["un", "deux"]), EncodeurTest().passages(["un", "deux"])
    assert np.array_equal(a, b) and a.shape == (2, 32) and a.dtype == np.float32
    assert np.allclose(np.linalg.norm(a, axis=1), 1)
    assert np.array_equal(EncodeurTest().requete("un"), a[0])


def test_construire_chercher_et_etat_en_ligne_de_commande(
    demo_silver: tuple[Path, Path],
    simule: QdrantSimule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le jeu de démo entier, en deux processus (le gold en sous-processus), encodeur de test."""
    _, entrepot = demo_silver
    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", simule.transport)
    travail = ["--travail", str(tmp_path / "index"), "--modele", "test"]
    resultat = CliRunner().invoke(
        application, ["index", "construire", "--entrepot", str(entrepot), *travail]
    )
    assert resultat.exit_code == 0, resultat.output
    assert (
        "index construit : 72296 fragments de 21445 fiches, 72296 encodé(s), 0 repris du cache"
        in resultat.output
    )
    assert "état au 2026-10-27T00:17:12Z" in resultat.output
    memoire = re.search(
        r"résident maximal : encodage (\d+) Mo, fragments \(sous-processus\) (\d+) Mo",
        resultat.output,
    )
    assert memoire, "chaque construction est une mesure (addendum 1 J, palier 2)"
    # Ici, « encodage » mesure le processus de pytest, qui a aussi construit le silver du jeu :
    # pas de seuil dans ce test, seulement la présence des deux mesures.
    assert int(memoire[1]) > 0 and int(memoire[2]) > 0
    etat = CliRunner().invoke(application, ["index", "etat"])
    assert etat.exit_code == 0, etat.output
    assert "fragments         72296" in etat.output and "  disponibilite   21445" in etat.output
    cherche = CliRunner().invoke(
        application,
        ["index", "chercher", "LEVOCARNIL", "--cis", "60016589", "--section", "disponibilite",
         "--format", "jsonl", "--modele", "test"],
    )  # fmt: skip
    assert cherche.exit_code == 0, cherche.output
    lignes = [json.loads(x) for x in cherche.stdout.splitlines()]
    assert [(x["code_cis"], x["section"], x["instant_index"]) for x in lignes] == [
        ("60016589", "disponibilite", "2026-10-27T00:17:12Z")
    ]
    refus = CliRunner().invoke(application, ["index", "chercher", "x", "--section", "autre"])
    assert refus.exit_code == 2 and "section parmi" in refus.output


def test_evaluer_mesure_les_rangs_sans_seuil(simule: QdrantSimule, tmp_path: Path) -> None:
    """Avec l'encodeur de test, une question égale au texte d'un fragment le trouve au rang 1."""
    from datetime import date

    from pharmaflux.evaluation.questions import Attendu, Comportement, Jeu, Question
    from pharmaflux.index import evaluation

    frags = ecrire_fragments(tmp_path, trois_fiches())
    construire(simule, tmp_path, frags)
    textes = {(f["code_cis"], f["section"]): f["texte"] for f in frags.lire()}

    def question(id_: str, texte: str, fichier: str, cle: dict[str, str]) -> Question:
        attendu = Attendu(date(2026, 10, 24), fichier, "a", "s", cle, ("x",), ())
        return Question(id_, id_.split("-")[0], texte, Comportement.REPONSE, attendu)

    jeu = Jeu(
        "v0",
        "essai",
        (
            question(
                "disponibilite-1",
                textes[("60000002", "disponibilite")],
                "bdpm.disponibilite",
                {"code_cis": "60000002"},
            ),
            question(
                "remboursement-1",
                textes[("60000001", "presentations")],
                "bdpm.presentations",
                {"code_cip13": "3400930000001"},
            ),
            question("avis-1", "rien de proche", "bdpm.smr", {"code_cis": "60000003"}),
            Question("medical-1", "medical", "Quelle dose ?", Comportement.REFUS_MEDICAL),
        ),
    )
    with Qdrant("http://qdrant.test", simule.transport()) as client:
        mesure = evaluation.evaluer(client, EncodeurTest(), jeu)
    attendu_rangs = [
        ("disponibilite-1", "60000002", "disponibilite", 1),
        ("remboursement-1", "60000001", "presentations", 1),
        ("avis-1", "60000003", "avis", None),
    ]  # le CIP13 retrouve son CIS dans les fragments ; 60000003 n'a pas d'avis
    for mode in evaluation.MODES:  # le texte exact trouve le fragment au rang 1, dans chaque mode
        assert [
            (x.question, x.code_cis, x.section, x.rangs[mode]) for x in mesure.lignes
        ] == attendu_rangs, mode
    assert mesure.rappel(evaluation.MODE_HYBRIDE, 1) == 2
    assert mesure.rang_reciproque(evaluation.MODE_HYBRIDE) == pytest.approx(2 / 3)
    assert [q for q, _ in mesure.hors] == ["medical-1"]
    texte = evaluation.formater(mesure)
    assert (
        texte[0]
        == "index au 2026-10-27T00:17:12Z, modèle test@1 ; 3 questions nomment un médicament"
    )
    assert texte[2].split() == ["mode", "bon", "CIS", "@1/5/10", "bon", "CIS+section", "@1/5/10",
                                "rang", "réciproque", "moyen"]  # fmt: skip
    hybride = next(ligne for ligne in texte if ligne.startswith("hybride"))
    assert "@1 2/3  @5 2/3  @10 2/3" in hybride and hybride.endswith("0.667")
