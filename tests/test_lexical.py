"""Le tokenizer lexical et le vecteur creux BM25 (index.lexical, ADR 0012)."""

from __future__ import annotations

import numpy as np
import pytest

from pharmaflux.index import lexical


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("DOLIPRANE 1000 mg", ["doliprane", "1000", "mg"]),
        ("3400930000000", ["3400930000000"]),  # un CIP13 reste entier
        ("65999556", ["65999556"]),  # un CIS reste entier
        ("LEVOTHYROX 50 microgrammes", ["levothyrox", "50", "ug"]),
        ("500 mcg", ["500", "ug"]),
        ("250 µg", ["250", "ug"]),  # le signe micro
        ("l'avis", ["l", "avis"]),  # l'élision
        ("générique", ["generique"]),  # un accent déplié
        ("Aucun signalement.", ["aucun", "signalement"]),
        ("ANSM / MITM", ["ansm", "mitm"]),
    ],
)
def test_jetons_figes(texte: str, attendu: list[str]) -> None:
    assert lexical.jetons(texte) == attendu


def test_longueur_du_document() -> None:
    # |d| = nombre de jetons, répétitions comprises (base de la constante avgdl).
    assert lexical.jetons("DOLIPRANE 1000 mg, 500 mg") == ["doliprane", "1000", "mg", "500", "mg"]
    assert len(lexical.jetons("DOLIPRANE 1000 mg, 500 mg")) == 5


def test_indice_stable_et_sur_31_bits() -> None:
    assert lexical.indice("doliprane") == lexical.indice("doliprane")
    assert lexical.indice("doliprane") != lexical.indice("lariam")
    for terme in ("doliprane", "500", "3400930000000", "ug", ""):
        assert 0 <= lexical.indice(terme) < (1 << 31)


def test_vecteur_document_bm25_sature_et_normalise_par_la_longueur() -> None:
    k1, b, avgdl = lexical.K1, lexical.B, lexical.LONGUEUR_MOYENNE

    def poids(frequence: int, longueur: int) -> float:
        return frequence * (k1 + 1) / (frequence + k1 * (1 - b + b * longueur / avgdl))

    # Un terme qui paraît une fois, dans un document d'un seul jeton.
    vecteur = lexical.vecteur_document("doliprane")
    assert vecteur == {lexical.indice("doliprane"): pytest.approx(poids(1, 1))}
    # La fréquence sature : deux occurrences valent moins que le double d'une.
    deux = lexical.vecteur_document("doliprane doliprane")[lexical.indice("doliprane")]
    une = poids(1, 1)
    assert deux < 2 * une
    assert deux == pytest.approx(poids(2, 2))
    # La longueur pénalise : le même terme, seul, pèse plus que noyé dans un long document.
    long = lexical.vecteur_document("doliprane " + "autre " * 20)[lexical.indice("doliprane")]
    assert long < une


def test_vecteur_document_vide() -> None:
    assert lexical.vecteur_document("") == {}
    assert lexical.vecteur_document("   ") == {}


def test_vecteur_requete_porte_la_frequence_brute() -> None:
    # La requête ne sature pas : Qdrant ajoute l'IDF, la valeur est la fréquence du terme.
    requete = lexical.vecteur_requete("mg mg doliprane")
    assert requete == {lexical.indice("mg"): 2.0, lexical.indice("doliprane"): 1.0}


def test_en_creux_indices_croissants_et_float32() -> None:
    creux = lexical.en_creux({7: 1.5, 2: 0.25, 5: 2.0})
    assert creux["indices"] == [2, 5, 7]
    assert creux["values"] == [np.float32(0.25), np.float32(2.0), np.float32(1.5)]
    assert all(np.float32(v) == v for v in creux["values"]), "déjà en float32"
