"""Lecture de la page de téléchargement de la BDPM.

Chaque fichier y est un ``<a href="/download/…">`` dont le texte contient,
pour dix fichiers sur onze, ``(Date de mise à jour : JJ/MM/AAAA, N Ko)``.
Le lien et sa date sont dans le même élément : on les lit ensemble avec
l'analyseur HTML de la bibliothèque standard, jamais par expression
régulière sur la page entière.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

from pharmaflux.collecte.catalogue import SITE_BDPM

MOTIF_DATE_TAILLE = re.compile(
    r"\(Date de mise à jour : (?P<jour>\d{2})/(?P<mois>\d{2})/(?P<annee>\d{4}), (?P<ko>\d+) Ko\)"
)


class AnalyseImpossible(ValueError):  # noqa: N818 (nom français voulu)
    """Le contenu reçu n'a pas la forme attendue."""


@dataclass(frozen=True, slots=True)
class LienTelechargement:
    """Un lien de téléchargement tel que la page l'affiche."""

    url: str
    libelle: str
    date_affichee: str | None  # AAAA-MM-JJ, date locale du site, au jour près
    taille_affichee_ko: int | None

    @property
    def nom(self) -> str:
        return self.url.rsplit("/", 1)[-1]

    @property
    def est_fichier_de_donnees(self) -> bool:
        """Les fichiers de données sont des ``.txt`` ; la page offre aussi un PDF (format v5)."""
        return self.nom.endswith(".txt")


class _AnalyseurLiens(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.liens: list[LienTelechargement] = []
        self._courant: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href and href.startswith("/download/"):
            self._courant = (href, [])

    def handle_data(self, data: str) -> None:
        if self._courant is not None:
            self._courant[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._courant is None:
            return
        href, morceaux = self._courant
        self._courant = None
        texte = " ".join("".join(morceaux).split())
        correspondance = MOTIF_DATE_TAILLE.search(texte)
        date_affichee = taille = None
        libelle = texte
        if correspondance:
            date_affichee = "{annee}-{mois}-{jour}".format(**correspondance.groupdict())
            taille = int(correspondance.group("ko"))
            libelle = texte[: correspondance.start()].strip()
        self.liens.append(
            LienTelechargement(
                url=f"{SITE_BDPM}{href}",
                libelle=libelle,
                date_affichee=date_affichee,
                taille_affichee_ko=taille,
            )
        )


def analyser_page(contenu: bytes) -> list[LienTelechargement]:
    """Les liens de téléchargement de la page, dans l'ordre d'affichage.

    Lève ``AnalyseImpossible`` si la page ne contient aucun lien ``/download/`` :
    une page d'erreur ou de maintenance ne doit pas passer pour une page vide.
    """
    analyseur = _AnalyseurLiens()
    analyseur.feed(contenu.decode("utf-8", errors="replace"))
    analyseur.close()
    if not analyseur.liens:
        raise AnalyseImpossible("aucun lien /download/ dans la page")
    return analyseur.liens
