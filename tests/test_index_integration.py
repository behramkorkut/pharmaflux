"""Mission 07, palier 2 : l'index contre le vrai Qdrant (intégration).

Marqués ``integration`` : sautés, et dit, sans Qdrant sur ``PHARMAFLUX_QDRANT``
(défaut ``127.0.0.1:16333``, celui de ``docker compose -p pharmaflux up -d``) ;
en CI, ``PHARMAFLUX_INTEGRATION_EXIGEE`` fait du saut un échec. Chaque test
travaille dans un **espace** à lui (``pharmaflux-test-<suffixe>`` : alias,
collection d'état, collections), effacé à la fin : l'index du Mac
(``pharmaflux-fragments``) n'est jamais touché. L'encodeur est celui de test.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from pharmaflux.index import construction
from pharmaflux.index.construction import Cache
from pharmaflux.index.encodeur import EncodeurTest
from pharmaflux.index.fragments import fragments
from pharmaflux.index.qdrant import (
    QDRANT_PAR_DEFAUT,
    VARIABLE_QDRANT,
    Point,
    Qdrant,
    QdrantIndisponible,
    filtre_egal,
)
from tests.conftest import VARIABLE_EXIGEE
from tests.test_fragments import fiche
from tests.test_index import ecrire_fragments, trois_fiches

pytestmark = pytest.mark.integration
QDRANT = os.environ.get(VARIABLE_QDRANT, QDRANT_PAR_DEFAUT)


@pytest.fixture
def qdrant() -> Iterator[Qdrant]:
    espace = f"pharmaflux-test-{uuid.uuid4().hex[:8]}"
    client = Qdrant(QDRANT, espace=espace)
    try:
        client.collections()
    except QdrantIndisponible as exc:
        client.close()
        motif = f"aucun Qdrant sur {QDRANT} (docker compose -p pharmaflux up -d) : {exc}"
        if os.environ.get(VARIABLE_EXIGEE):
            pytest.fail(f"{VARIABLE_EXIGEE} est posée, le saut est un échec : {motif}")
        pytest.skip(motif)
    yield client
    for nom in client.collections():
        if nom.startswith(espace):
            client.supprimer_collection(nom)
    client.close()


def test_construire_chercher_et_reconstruire_sur_le_vrai_qdrant(
    qdrant: Qdrant, tmp_path: Path
) -> None:
    frags = ecrire_fragments(tmp_path, trois_fiches())
    cache = Cache(tmp_path / "travail", EncodeurTest.empreinte)
    premiere = construction.construire(qdrant, EncodeurTest(), frags, cache)
    assert qdrant.alias()[qdrant.alias_fragments] == premiere.collection
    assert qdrant.compter(qdrant.alias_fragments) == 7
    assert qdrant.compter(qdrant.alias_fragments, filtre_egal("code_cis", "60000002")) == 2
    etat = qdrant.lire_etat()
    assert etat is not None and etat["instant"] == "2026-10-27T00:17:12Z" and etat["vise"] is None
    cible = next(f for f in frags.lire() if f["section"] == "presentations")
    _, resultats = construction.chercher(qdrant, EncodeurTest(), cible["texte"], 3)
    assert resultats[0].charge == {k: v for k, v in cible.items() if k != "identifiant"}
    # L'hybride (défaut) rend un score de fusion ; le dense seul rend le cosinus du même vecteur.
    _, denses = construction.chercher(
        qdrant, EncodeurTest(), cible["texte"], 3, mode=construction.MODE_DENSE
    )
    assert denses[0].score == pytest.approx(1, abs=1e-5), "cosinus du même vecteur"
    # Format 2 : le vecteur creux est écrit à côté du dense, et le lexical le trouve par le mot.
    point = next(
        qdrant.parcourir(qdrant.alias_fragments, filtre_egal("code_cis", "60000002"), vecteurs=True)
    )
    assert "lexical" in point["vector"] and point["vector"]["lexical"]["indices"]
    _, lex = construction.chercher(
        qdrant, EncodeurTest(), "PARACETAMOL", 3, mode=construction.MODE_LEXICAL
    )
    assert lex and lex[0].charge["code_cis"] == "60000002", "60000002 est le seul PARACETAMOL"
    seconde = construction.construire(qdrant, EncodeurTest(), frags, cache)
    assert seconde.encodes == 0 and seconde.collection == premiere.collection + "-bis"
    assert premiere.collection not in qdrant.collections(), "l'ancienne est effacée"
    assert qdrant.alias()[qdrant.alias_fragments] == seconde.collection
    cache.close()


def test_parcourir_par_pages_et_supprimer_par_filtre(qdrant: Qdrant) -> None:
    """Ce que la mise à jour et la vérification (palier 3) demandent à Qdrant."""
    collection = f"{qdrant.espace}-points"
    qdrant.creer_collection(collection, EncodeurTest.dimension)
    liste = [f for i in range(700) for f in fragments(fiche(code_cis=f"6{i:07d}"))]  # 1 400
    vecteurs = EncodeurTest().passages([f.texte for f in liste])
    for debut in range(0, len(liste), 500):
        qdrant.ecrire(
            collection,
            [
                Point(f.identifiant, v.tolist(), f.en_dict())
                for f, v in zip(
                    liste[debut : debut + 500], vecteurs[debut : debut + 500], strict=True
                )
            ],
        )
    lus = list(qdrant.parcourir(collection, champs=["code_cis"]))
    assert len(lus) == 1400 and len({p["id"] for p in lus}) == 1400, "deux pages, sans doublon"
    garde = liste[0].identifiant  # l'identité de 60000000 ; sa disponibilité part
    qdrant.supprimer(
        collection,
        {
            "must": [{"key": "code_cis", "match": {"value": "60000000"}}],
            "must_not": [{"has_id": [garde]}],
        },
    )
    restants = list(qdrant.parcourir(collection, filtre_egal("code_cis", "60000000")))
    assert [p["id"] for p in restants] == [garde]
    avec = next(qdrant.parcourir(collection, filtre_egal("code_cis", "60000001"), vecteurs=True))
    assert len(avec["vector"]["dense"]) == EncodeurTest.dimension
