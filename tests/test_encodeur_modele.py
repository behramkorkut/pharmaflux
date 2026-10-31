"""Mission 07, palier 2 : le vrai modèle e5, quand ses fichiers sont là (``$PHARMAFLUX_MODELES``).

Marqués ``modele`` : sautés, et dit, sans les fichiers épinglés ; en CI, l'étape
du modèle les télécharge (épinglés, vérifiés) et ``PHARMAFLUX_MODELE_EXIGE``
fait du saut un échec. Les autres tests n'utilisent jamais le vrai modèle
(addendum 1 C2).

Le tokenizer SentencePiece d'origine (``sentencepiece.bpe.model``, avec le
décalage de fairseq) doit donner les mêmes identifiants que ``tokenizer.json``
(lu par ``tokenizers``, la référence, en dépendance de développement) : sur
les 40 questions v0 et sur un échantillon fixe de fragments du jeu (décision
de l'IeC au palier 2). Le rapport donne la comparaison sur les 72 296
fragments ; l'écart résiduel connu (une égalité de score) est dans l'ADR 0011.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from pharmaflux.cli import QUESTIONS_PAR_DEFAUT
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evaluation import questions as jeu_questions
from pharmaflux.gold import vues as vues_gold
from pharmaflux.gold.sql import etats_types
from pharmaflux.gold.typage import derniere_observation
from pharmaflux.index import encodeur, modeles, pages_has
from pharmaflux.index.encodeur import E5Onnx
from pharmaflux.index.fragments import BORNE_CARACTERES, fragments_des_fiches, rattachements
from pharmaflux.silver.entrepot import Entrepot

pytestmark = pytest.mark.modele
VARIABLE_EXIGE = "PHARMAFLUX_MODELE_EXIGE"
NOM = "e5-small-int8"
JEU = Path(__file__).resolve().parent.parent / "demo" / "archive"
PAS_ECHANTILLON = 500  # un fragment sur 500 du jeu, dans l'ordre : 145 fragments


@pytest.fixture(scope="module")
def e5() -> Iterator[E5Onnx]:
    ecarts = modeles.verifier(modeles.lire(NOM), modeles.racine_modeles())
    if ecarts:
        motif = f"fichiers du modèle {NOM} absents ou différents : {'; '.join(ecarts)}"
        if os.environ.get(VARIABLE_EXIGE):
            pytest.fail(f"{VARIABLE_EXIGE} est posée, le saut est un échec : {motif}")
        pytest.skip(motif)
    charge = encodeur.charger(NOM)
    assert isinstance(charge, E5Onnx)
    yield charge


@pytest.fixture(scope="module")
def echantillon(demo_silver: tuple[Path, Path]) -> list[str]:
    _, dossier = demo_silver
    entrepot = Entrepot.ouvrir(dossier)
    instant = derniere_observation(entrepot)
    assert instant is not None
    contrats = charger_tous()
    vues = vues_gold.vues(entrepot, contrats, etats_types(entrepot, contrats, instant), instant)
    return [
        f.texte for i, f in enumerate(fragments_des_fiches(vues.fiche)) if i % PAS_ECHANTILLON == 0
    ]


def test_sentencepiece_donne_les_identifiants_de_tokenizer_json(
    e5: E5Onnx, echantillon: list[str]
) -> None:
    from tokenizers import Tokenizer

    dossier = modeles.dossier(modeles.lire(NOM), modeles.racine_modeles())
    reference = Tokenizer.from_file(str(dossier / "tokenizer.json"))
    reference.no_truncation()
    questions = jeu_questions.charger(QUESTIONS_PAR_DEFAUT, charger_tous()).questions
    textes = [f"query: {q.question}" for q in questions]
    textes += [f"passage: {t}" for t in echantillon]
    assert len(textes) == 40 + 145
    attendus = [c.ids for c in reference.encode_batch(textes)]
    assert e5._ids(textes) == attendus


def test_aucun_fragment_de_l_echantillon_ne_depasse_la_fenetre(
    e5: E5Onnx, echantillon: list[str]
) -> None:
    longueurs = [e5.nombre_de_jetons(t) for t in echantillon]
    assert max(longueurs) <= 512
    assert all(len(t) <= BORNE_CARACTERES for t in echantillon)


def test_aucun_fragment_avis_has_du_jeu_ne_depasse_la_fenetre(
    e5: E5Onnx, demo_silver: tuple[Path, Path]
) -> None:
    """Mission 09 : les fragments d'avis du jeu, tous, 1 255 au format 4 (la prose d'un avis se
    coupe autrement que les codes d'une fiche, et une ligne d'avis peut faire 1 781 caractères)."""
    _, dossier = demo_silver
    entrepot = Entrepot.ouvrir(dossier)
    instant = derniere_observation(entrepot)
    assert instant is not None
    contrats = charger_tous()
    vues = vues_gold.vues(entrepot, contrats, etats_types(entrepot, contrats, instant), instant)
    dossiers, _, _ = rattachements(vues.fiche)
    pages = pages_has.lire(JEU, dossiers).pages
    textes = [
        f.texte for f in fragments_des_fiches(vues.fiche, pages=pages) if f.section == "avis_has"
    ]
    assert len(textes) > 1000
    assert max(e5.nombre_de_jetons(t) for t in textes) <= 512
    assert all(len(t) <= BORNE_CARACTERES for t in textes)


def test_e5_rend_des_vecteurs_normes_reproductibles(e5: E5Onnx, echantillon: list[str]) -> None:
    une, deux = e5.passages(echantillon[:20]), e5.passages(echantillon[:20])
    assert une.shape == (20, 384) and np.array_equal(une, deux), "mêmes textes, même ordre"
    assert np.allclose(np.linalg.norm(une, axis=1), 1, atol=1e-5)
    requete = e5.requete("LEVOCARNIL est-il disponible ?")
    assert requete.shape == (384,)
    seul = e5.passages(echantillon[:1])[0]
    assert float(seul @ une[0]) > 0.99, "le voisinage de lot ne change presque rien"
