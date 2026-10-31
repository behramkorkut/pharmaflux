"""Recherche lexicale : un tokenizer déterministe et un vecteur creux BM25 (ADR 0012, addendum 1 A).

Le dense retrouve le sens ; le lexical retrouve les noms, les CIS, les CIP13 et
les dosages — par les mots, pas par le voisinage sémantique. À côté de son
vecteur ``dense``, chaque fragment reçoit dans Qdrant un vecteur **creux**
nommé ``lexical`` : l'indice d'un terme vient d'un hachage stable (``blake2b``,
31 bits), sa valeur est le terme « document » de BM25 (saturation de la
fréquence et normalisation par la longueur), calculé avec des **constantes
figées du format** — ``K1``, ``B`` et la longueur moyenne ``LONGUEUR_MOYENNE``.

L'IDF, qui dépend du corpus entier, n'est **pas** dans la valeur stockée : il
est laissé à Qdrant (``"modifier": "idf"`` sur le vecteur creux), appliqué au
moment de la requête. Ainsi le vecteur creux d'un fragment ne dépend que de son
texte : la mise à jour par incréments et ``index verifier`` restent justes,
puisqu'ils comparent la seule valeur stockée, jamais un score. La requête porte
la fréquence brute de ses termes ; Qdrant la multiplie par l'IDF et par la
valeur du document.

Pas de racinisation ni de liste de mots vides dans cette mission : les noms et
les codes sont la cible, et l'IDF écrase déjà les mots trop communs.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter

import numpy as np

# BM25, figés (addendum 1 A2). ``LONGUEUR_MOYENNE`` est la moyenne du nombre de jetons par
# fragment, mesurée une fois sur les 72 296 fragments du jeu de démo (instant
# 2026-10-27T00:17:12Z) par le tokenizer ci-dessous, puis figée : jamais recalculée, pour que la
# valeur d'un fragment ne dépende que de son texte. |d| et cette moyenne se comptent de la même
# façon (jetons, répétitions comprises). Voir ADR 0012.
K1 = 1.2
B = 0.75
LONGUEUR_MOYENNE = 53.29

# Indices des termes dans Qdrant : 31 bits (positifs, bien dans les u32 de Qdrant). Les
# collisions sont acceptées — leurs valeurs s'additionnent — et il n'y en a aucune sur le jeu
# (65 363 termes distincts). Voir ADR 0012.
_BITS_INDICE = 31
_OCTETS_HACHAGE = 4

# µ (signe micro) et μ (mu grec) deviennent « u » avant tout : non alphanumériques, ils seraient
# sinon coupés, et « µg » perdrait sa dose.
_MICRO = str.maketrans({"µ": "u", "μ": "u"})
_SEPARATEUR = re.compile(r"[^a-z0-9]+")
# Unités d'une dose ramenées à une graphie. Pas « gramme » (ambigu) ; « mg » reste « mg ».
_SYNONYMES = {
    "mcg": "ug",
    "microg": "ug",
    "microgramme": "ug",
    "microgrammes": "ug",
    "milligramme": "mg",
    "milligrammes": "mg",
}


def _deplier(texte: str) -> str:
    """Accents dépliés (NFKD, marques combinantes retirées) ; le micro d'abord ramené à « u »."""
    nfkd = unicodedata.normalize("NFKD", texte.translate(_MICRO))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def jetons(texte: str) -> list[str]:
    """Les jetons lexicaux : minuscules, accents dépliés, suites alphanumériques entières.

    Les CIS (8 chiffres) et les CIP13 (13 chiffres) restent un seul jeton ; « 500 mg » donne
    « 500 » et « mg » ; les unités de dose sont ramenées à une graphie. Répétitions gardées.
    """
    bruts = [jeton for jeton in _SEPARATEUR.split(_deplier(texte).lower()) if jeton]
    return [_SYNONYMES.get(jeton, jeton) for jeton in bruts]


def indice(terme: str) -> int:
    """L'indice d'un terme dans le vecteur creux : hachage ``blake2b`` stable, sur 31 bits."""
    brut = hashlib.blake2b(terme.encode("utf-8"), digest_size=_OCTETS_HACHAGE).digest()
    return int.from_bytes(brut, "big") & ((1 << _BITS_INDICE) - 1)


def vecteur_document(texte: str) -> dict[int, float]:
    """Le vecteur creux d'un fragment : indice du terme → terme « document » de BM25.

    ``poids = f*(K1+1) / (f + K1*(1 - B + B*|d|/avgdl))``. La saturation de la fréquence et la
    normalisation par la longueur sont ici ; l'IDF est à Qdrant. Les collisions d'indice
    s'additionnent.
    """
    liste = jetons(texte)
    longueur = len(liste)
    if longueur == 0:
        return {}
    constante = K1 * (1 - B + B * longueur / LONGUEUR_MOYENNE)
    creux: dict[int, float] = {}
    for terme, frequence in Counter(liste).items():
        poids = frequence * (K1 + 1) / (frequence + constante)
        creux[indice(terme)] = creux.get(indice(terme), 0.0) + poids
    return creux


def vecteur_requete(texte: str) -> dict[int, float]:
    """Le vecteur creux d'une question : indice du terme → fréquence brute (Qdrant ajoute l'IDF)."""
    creux: dict[int, float] = {}
    for terme, frequence in Counter(jetons(texte)).items():
        creux[indice(terme)] = creux.get(indice(terme), 0.0) + float(frequence)
    return creux


def en_creux(vecteur: dict[int, float]) -> dict[str, object]:
    """La forme Qdrant d'un vecteur creux : indices croissants, valeurs en ``float32``."""
    indices = sorted(vecteur)
    valeurs = np.asarray([vecteur[i] for i in indices], np.float32)
    return {"indices": indices, "values": valeurs.tolist()}
