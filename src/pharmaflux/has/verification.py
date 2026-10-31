"""La preuve de non-altération : un second lecteur, qui ne partage aucun code avec l'extracteur.

Le texte de référence d'une page s'obtient ici par une autre voie que ``extraction`` : des
expressions régulières ôtent les scripts, les styles, les commentaires puis toutes les
balises ; ``html.unescape`` décode les entités ; enfin toute espace est retirée, l'extracteur
ayant le droit de les normaliser (licence de la HAS, ADR 0004). Chaque ligne extraite, ainsi
réduite, doit s'y retrouver, **dans l'ordre** de l'extraction (addendum 1, D).

Ce module ne prend de l'extraction que son résultat (``AvisExtrait``), jamais un de ses
outils : un défaut commun aux deux lecteurs ne pourrait pas se cacher.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from pharmaflux.has.extraction import AvisExtrait

_NON_TEXTE = re.compile(r"<script\b.*?</script\s*>|<style\b.*?</style\s*>|<!--.*?-->", re.S | re.I)
_BALISE = re.compile(r"<[^>]*>")
_ESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Ecart:
    """Une ligne extraite introuvable dans la référence, à sa place."""

    position: int  # dans la suite des textes contrôlés (le titre est 0)
    texte: str


def texte_de_reference(octets: bytes) -> str:
    """Le texte visible de la page, sans balise et sans aucune espace."""
    brut = octets.decode("utf-8")
    sans_balises = _BALISE.sub("", _NON_TEXTE.sub("", brut))
    return _ESPACE.sub("", html.unescape(sans_balises))


def ecarts(octets: bytes, extrait: AvisExtrait) -> list[Ecart]:
    """Les lignes de ``extrait`` (titre compris) absentes de la page, ou hors de leur ordre."""
    reference = texte_de_reference(octets)
    textes = [extrait.titre, *(ligne.texte for ligne in extrait.lignes)]
    trouves: list[Ecart] = []
    curseur = 0
    for position, texte in enumerate(textes):
        reduit = _ESPACE.sub("", texte)
        trouve = reference.find(reduit, curseur)
        if trouve < 0:
            trouves.append(Ecart(position, texte))
            continue
        curseur = trouve + len(reduit)
    return trouves
