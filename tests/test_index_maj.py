"""Mission 07, palier 3 : la mise à jour par incréments, la vérification, les coupures.

Contre le Qdrant simulé et l'encodeur de test. La règle de toute la mission :
après une mise à jour, l'index est égal à l'index construit en entier depuis
les mêmes fiches (mêmes identifiants, mêmes charges, mêmes vecteurs), et
``verifier`` le dit conforme ; après une coupure à n'importe quelle étape, la
commande relancée y revient.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pyarrow as pa
import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.cli import application
from pharmaflux.index import changements, construction
from pharmaflux.index.construction import Cache, Fragments, IndexRefuse
from pharmaflux.index.encodeur import EncodeurTest
from pharmaflux.index.fragments import fragments
from pharmaflux.index.qdrant import ALIAS, COLLECTION_ETAT, Qdrant, QdrantIndisponible
from tests.qdrant_simule import QdrantSimule
from tests.test_fragments import fiche, presentation, signalement

AVANT, APRES = "2026-10-26T00:17:12Z", "2026-10-27T00:17:12Z"


def info(i: int) -> dict[str, Any]:
    titre = f"Actualité {i:02d} " + "x" * 60
    return {"date_debut": date(2024, 1, 1), "date_fin": None, "texte_et_lien": titre}


def ecrire(
    tmp_path: Path,
    nom: str,
    fiches: list[dict[str, Any]],
    instant: str,
    touches: list[str] | None = None,
    total: int | None = None,
) -> Fragments:
    """Le fichier de fragments que le sous-processus écrirait : tous, ou les CIS touchés."""
    choisies = fiches if touches is None else [f for f in fiches if f["code_cis"] in touches]
    liste = [x for f in sorted(choisies, key=lambda f: f["code_cis"]) for x in fragments(f)]
    chemin = tmp_path / f"{nom}.jsonl"
    chemin.write_text("".join(x.en_jsonl() + "\n" for x in liste), encoding="utf-8")
    return Fragments(
        chemin,
        instant,
        len(choisies),
        len(liste),
        total if total is not None else len(fiches),
        None if touches is None else tuple(sorted(touches)),
    )


AVANT_FICHES = [
    fiche(code_cis="60000001", presentations=[presentation("3400930000001")]),
    fiche(code_cis="60000002", presentations=[presentation("3400930000002")]),
    fiche(code_cis="60000003", infos_importantes=[info(i) for i in range(40)]),
    fiche(code_cis="60000004", denomination="DISPARAIT TEST"),
    fiche(code_cis="60000005", denomination="INCHANGE TEST"),
]
APRES_FICHES = [
    fiche(code_cis="60000001"),  # ses présentations disparaissent : la section se vide
    fiche(  # un prix change, un signalement arrive
        code_cis="60000002",
        presentations=[presentation("3400930000002", prix_public=None)],
        disponibilite=[signalement()],
    ),
    fiche(code_cis="60000003", infos_importantes=[info(i) for i in range(25)]),  # moins de parties
    fiche(code_cis="60000005", denomination="INCHANGE TEST"),
    fiche(code_cis="60000006", denomination="NOUVEAU TEST"),
]
TOUCHES = ["60000001", "60000002", "60000003", "60000004", "60000006"]


def client(simule: QdrantSimule) -> Qdrant:
    return Qdrant("http://qdrant.test", simule.transport())


def construire(simule: QdrantSimule, travail: Path, frags: Fragments) -> None:
    cache = Cache(travail, EncodeurTest.empreinte)
    with client(simule) as q:
        construction.construire(q, EncodeurTest(), frags, cache)
    cache.close()


def mettre_a_jour(
    simule: QdrantSimule, travail: Path, frags: Fragments
) -> construction.BilanMiseAJour:
    cache = Cache(travail, EncodeurTest.empreinte)
    try:
        with client(simule) as q:
            return construction.mettre_a_jour(q, EncodeurTest(), frags, cache)
    finally:
        cache.close()


def verifier(simule: QdrantSimule, travail: Path, frags: Fragments) -> construction.Verification:
    cache = Cache(travail, EncodeurTest.empreinte)
    try:
        with client(simule) as q:
            return construction.verifier(q, EncodeurTest(), frags, cache)
    finally:
        cache.close()


def contenu(simule: QdrantSimule) -> dict[str, tuple[Any, Any]]:
    return {i: (p["payload"], p["vector"]) for i, p in simule.points(ALIAS).items()}


def assert_egal_a_la_reconstruction(simule: QdrantSimule, tmp_path: Path, nom: str) -> None:
    complets = ecrire(tmp_path, f"{nom}-complets", APRES_FICHES, APRES)
    reference = QdrantSimule()
    construire(reference, tmp_path / f"{nom}-reference", complets)
    assert contenu(simule) == contenu(reference), "égal à la reconstruction complète"
    rapport = verifier(simule, tmp_path / "travail", complets)
    assert rapport.conforme, construction.formater_verification(rapport)
    etat = simule.points(COLLECTION_ETAT)
    [charge] = [p["payload"] for p in etat.values()]
    assert charge["instant"] == APRES and charge["vise"] is None
    assert charge["fiches"] == 5 and charge["fragments"] == len(simule.points(ALIAS))


@pytest.fixture
def index_avant(tmp_path: Path) -> QdrantSimule:
    simule = QdrantSimule()
    construire(simule, tmp_path / "travail", ecrire(tmp_path, "avant", AVANT_FICHES, AVANT))
    return simule


def test_mettre_a_jour_remplace_retire_et_egale_la_reconstruction(
    index_avant: QdrantSimule, tmp_path: Path
) -> None:
    frags = ecrire(tmp_path, "maj", APRES_FICHES, APRES, TOUCHES)
    bilan = mettre_a_jour(index_avant, tmp_path / "travail", frags)
    assert (bilan.depuis, bilan.instant, bilan.reprise, bilan.cis_touches) == (
        AVANT,
        APRES,
        False,
        5,
    )
    avant = {f.identifiant: f.texte for x in AVANT_FICHES for f in fragments(x)}
    apres = {f.identifiant: f.texte for x in APRES_FICHES for f in fragments(x)}
    assert bilan.retires == len(set(avant) - set(apres)) == 5, (
        "la section vidée (1), le CIS disparu (2), deux parties de moins (2)"
    )
    assert bilan.ajoutes == len(set(apres) - set(avant)) == 2, "le CIS nouveau"
    assert bilan.remplaces == sum(avant[i] != apres[i] for i in set(avant) & set(apres)) == 5
    assert bilan.inchanges == 5 and bilan.encodes == 7
    assert_egal_a_la_reconstruction(index_avant, tmp_path, "maj")
    assert not any(
        p["payload"]["code_cis"] == "60000004" for p in index_avant.points(ALIAS).values()
    ), "aucun fragment orphelin du CIS disparu"


def test_rien_a_faire(index_avant: QdrantSimule, tmp_path: Path) -> None:
    avant = contenu(index_avant)
    frags = ecrire(tmp_path, "rien", AVANT_FICHES, AVANT, [])
    bilan = mettre_a_jour(index_avant, tmp_path / "travail", frags)
    assert (bilan.cis_touches, bilan.encodes, bilan.ajoutes, bilan.retires) == (0, 0, 0, 0)
    assert contenu(index_avant) == avant


def test_le_silver_en_arriere_de_l_index_est_refuse(
    index_avant: QdrantSimule, tmp_path: Path
) -> None:
    frags = ecrire(tmp_path, "arriere", AVANT_FICHES, "2026-10-25T00:00:00Z", [])
    with pytest.raises(IndexRefuse, match="en arrière de l'index"):
        mettre_a_jour(index_avant, tmp_path / "travail", frags)


@pytest.mark.parametrize(
    ("appel", "rang"),
    [
        (f"PUT /collections/{COLLECTION_ETAT}/points", 1),  # avant d'écrire « vise »
        ("PUT /collections/pharmaflux-f2-test", 1),  # avant la première écriture de points
        (
            "POST /collections/pharmaflux-f2-test-20261026T001712Z/points/delete",
            1,
        ),  # avant de retirer
        (f"PUT /collections/{COLLECTION_ETAT}/points", 2),  # avant d'écrire le nouvel instant
    ],
    ids=["avant-vise", "avant-ecriture", "avant-retrait", "avant-instant"],
)
def test_une_coupure_puis_la_reprise_egale_la_reconstruction(
    index_avant: QdrantSimule, tmp_path: Path, appel: str, rang: int
) -> None:
    frags = ecrire(tmp_path, "maj", APRES_FICHES, APRES, TOUCHES)
    index_avant.couper(appel, rang)
    with pytest.raises(QdrantIndisponible, match="coupure simulée"):
        mettre_a_jour(index_avant, tmp_path / "travail", frags)
    etat = next(iter(index_avant.points(COLLECTION_ETAT).values()))["payload"]
    assert etat["instant"] == AVANT, "l'instant n'avance qu'à la fin"
    reprise = mettre_a_jour(index_avant, tmp_path / "travail", frags)
    assert reprise.reprise is (rang == 2 or "points/delete" in appel or "f2-test" in appel)
    assert_egal_a_la_reconstruction(index_avant, tmp_path, "reprise")


def test_une_coupure_entre_l_alias_et_l_etat_fait_refuser_la_lecture(
    index_avant: QdrantSimule, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contrôle du palier 2 : l'alias sur la nouvelle collection, l'état sur l'ancienne."""
    complets = ecrire(tmp_path, "complets", APRES_FICHES, APRES)
    index_avant.couper(f"PUT /collections/{COLLECTION_ETAT}/points")
    with pytest.raises(QdrantIndisponible):
        construire(index_avant, tmp_path / "travail", complets)
    with client(index_avant) as q:
        for lire in (
            lambda: construction.etat_exige(q),
            lambda: construction.chercher(q, EncodeurTest(), "x", 3),
        ):
            with pytest.raises(IndexRefuse, match="coupée entre la bascule de l'alias"):
                lire()
    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", index_avant.transport)
    for commande in (["index", "etat"], ["index", "chercher", "x", "--modele", "test"]):
        resultat = CliRunner().invoke(application, commande)
        assert resultat.exit_code == 2 and "relancer « pharmaflux index construire »" in (
            resultat.output
        )
    construire(index_avant, tmp_path / "travail", complets)  # la sortie : reconstruire
    with client(index_avant) as q:
        assert construction.etat_exige(q)["instant"] == APRES
    assert set(index_avant.collections) == {COLLECTION_ETAT, index_avant.alias[ALIAS]}, (
        "ni la collection de l'ancien alias, ni celle que l'ancien état décrivait (relecture 1)"
    )


def test_verifier_trouve_chaque_ecart(index_avant: QdrantSimule, tmp_path: Path) -> None:
    complets = ecrire(tmp_path, "avant-complets", AVANT_FICHES, AVANT)
    travail = tmp_path / "travail"
    assert verifier(index_avant, travail, complets).conforme
    points = index_avant.points(ALIAS)
    ids = sorted(points)
    manquant = points.pop(ids[0])
    points[ids[1]]["payload"] = points[ids[1]]["payload"] | {"texte": "retouché"}
    points[ids[2]]["vector"] = {"dense": [0.0] * 31 + [1.0]}
    points["orphelin"] = manquant | {"id": "orphelin"}
    rapport = verifier(index_avant, travail, complets)
    assert not rapport.conforme
    assert (rapport.manquants, rapport.orphelins, rapport.differents) == (
        [ids[0]],
        ["orphelin"],
        [ids[1]],
    )
    assert sorted(rapport.vecteurs_differents) == sorted([ids[1], ids[2]]), (
        "chacun une fois : le vecteur retouché, et celui dont le texte ne correspond plus"
    )
    assert sorted(rapport.creux_differents) == sorted([ids[1], ids[2]]), (
        "le vecteur creux recalculé depuis le texte retouché, et celui dont le creux a disparu"
    )
    lignes = construction.formater_verification(rapport)
    assert (
        lignes[-1] == "NON CONFORME" and f"manquants                        1 : {ids[0]}" in lignes
    )


def test_verifier_signale_une_mise_a_jour_en_suspens(
    index_avant: QdrantSimule, tmp_path: Path
) -> None:
    index_avant.couper("PUT /collections/pharmaflux-f2-test")
    with pytest.raises(QdrantIndisponible):
        mettre_a_jour(
            index_avant, tmp_path / "travail", ecrire(tmp_path, "m", APRES_FICHES, APRES, TOUCHES)
        )
    rapport = verifier(
        index_avant, tmp_path / "travail", ecrire(tmp_path, "c", AVANT_FICHES, AVANT)
    )
    assert rapport.suspens == APRES and not rapport.conforme


# --- les bascules du jour (addendum 1 E1) ------------------------------------------------------


def etats(
    dispo: list[tuple[str, date | None]], infos: list[tuple[str, date | None, date | None]]
) -> Any:
    return {
        "bdpm.disponibilite": SimpleNamespace(
            table=pa.table(
                {
                    "code_cis": [c for c, _ in dispo],
                    "date_debut": pa.array([d for _, d in dispo], pa.date32()),
                }
            )
        ),
        "bdpm.infos_importantes": SimpleNamespace(
            table=pa.table(
                {
                    "code_cis": [c for c, _, _ in infos],
                    "date_debut": pa.array([d for _, d, _ in infos], pa.date32()),
                    "date_fin": pa.array([f for _, _, f in infos], pa.date32()),
                }
            )
        ),
    }


def test_les_bascules_du_jour() -> None:
    j0, j1 = date(2026, 10, 26), date(2026, 10, 27)
    tables = etats(
        dispo=[
            ("A", date(2026, 10, 27)),  # annoncé au 27 : commence entre j0 et j1
            ("B", date(2026, 10, 26)),  # déjà commencé à j0
            ("C", date(2027, 7, 1)),  # toujours à venir
            ("D", None),
        ],
        infos=[
            ("E", date(2026, 10, 27), None),  # entre dans sa fenêtre
            ("F", date(2024, 1, 1), date(2026, 10, 26)),  # en cours le 26, sortie le 27
            ("G", date(2024, 1, 1), date(2026, 10, 27)),  # encore en cours le 27
            ("H", date(2024, 1, 1), None),
        ],
    )
    assert changements.bascules_du_jour(tables, j0, j1) == {"A", "E", "F"}
    assert changements.bascules_du_jour(tables, j1, j1) == set(), "même jour : aucune bascule"
    assert changements.bascules_du_jour(tables, date(2026, 10, 1), j1) >= {"A", "B", "E", "F"}


def test_une_bascule_change_le_texte_du_fragment() -> None:
    """Le texte d'un signalement annoncé change le jour où il commence : d'où les bascules."""
    a_venir = fiche(disponibilite=[signalement(date_debut=date(2026, 10, 27), debut_a_venir=True)])
    commence = fiche(disponibilite=[signalement(date_debut=date(2026, 10, 27))])
    texte = {f.section: f.texte for f in fragments(a_venir)}["disponibilite"]
    apres = {f.section: f.texte for f in fragments(commence)}["disponibilite"]
    assert "annoncé à partir du 2026-10-27" in texte and "depuis le 2026-10-27" in apres


def test_l_echec_de_qdrant_est_un_refus_en_ligne_de_commande(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def panne(requete: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refusé", request=requete)

    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", lambda: httpx.MockTransport(panne))
    for commande in ("etat", "verifier", "mettre-a-jour"):
        resultat = CliRunner().invoke(
            application,
            [
                "index",
                commande,
                *(["--travail", str(tmp_path)] if commande != "etat" else []),
                *(["--modele", "test"] if commande != "etat" else []),
            ],
        )
        assert resultat.exit_code == 2, (commande, resultat.output)


def test_un_index_reduit_se_declare_et_ne_se_met_pas_a_jour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relecture 1 : construire --cis garde ses CIS dans l'état ; la mise à jour refuse."""
    simule, travail = QdrantSimule(), tmp_path / "travail"
    reduites = [f for f in AVANT_FICHES if f["code_cis"] in ("60000001", "60000002")]
    frags = ecrire(tmp_path, "reduit", reduites, AVANT, total=len(AVANT_FICHES))
    cache = Cache(travail, EncodeurTest.empreinte)
    with client(simule) as q:
        construction.construire(q, EncodeurTest(), frags, cache, reduit=["60000002", "60000001"])
    cache.close()
    etat = next(iter(simule.points(COLLECTION_ETAT).values()))["payload"]
    assert etat["cis_reduits"] == ["60000001", "60000002"] and etat["fiches"] == 2
    with pytest.raises(IndexRefuse, match="réduit à 2 CIS"):
        mettre_a_jour(simule, travail, ecrire(tmp_path, "maj", APRES_FICHES, APRES, TOUCHES))
    assert verifier(simule, travail, frags).conforme, "comparé à la reconstruction de ses CIS"
    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", simule.transport)
    simple = CliRunner().invoke(application, ["index", "etat"])
    assert simple.exit_code == 0 and "réduit à         2 CIS" in simple.output
    complet = CliRunner().invoke(application, ["index", "etat", "--complet"])
    assert complet.exit_code == 2 and "reconstruire en entier" in complet.output


def test_verifier_prend_le_verrou(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Relecture 1 : son sous-processus écrit les mêmes fichiers que construire."""
    simule = QdrantSimule()
    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", simule.transport)
    with construction.verrou(tmp_path):
        resultat = CliRunner().invoke(
            application, ["index", "verifier", "--modele", "test", "--travail", str(tmp_path)]
        )
    assert resultat.exit_code == 2 and "un autre processus écrit l'index" in resultat.output
