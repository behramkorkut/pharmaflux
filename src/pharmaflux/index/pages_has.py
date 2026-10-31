"""Les pages d'avis de la HAS que lit l'index (mission 09, addendum 1 D2, F) : position, pages.

L'index ne lit jamais la sortie de ``has extraire`` : il relit le manifeste HAS jusqu'à une
**position** (un nombre de lignes lisibles, et le sha256 de ce préfixe), prend la dernière
archive de chaque page, et réextrait ses octets à chaque construction. Une page est rattachée à
un CIS par les liens de la BDPM **à l'instant du silver**, jamais l'inverse (F3) : une page que
plus aucun lien ne désigne n'est pas lue, et une page collectée après l'instant du silver
n'apporte que ce qu'elle date elle-même.

Les deux horloges de l'index : l'instant du silver, et la position du manifeste HAS, avec la
dernière collecte qu'elle contient (« pages d'avis de la HAS collectées jusqu'au … »). Un
préfixe qui change, ou un autre extracteur, impose la reconstruction.
"""

from __future__ import annotations

import gzip
import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pharmaflux.has import extraction
from pharmaflux.has import manifeste as mf


class PositionRefusee(Exception):  # noqa: N818 (nom français voulu)
    """Le manifeste HAS ne prolonge pas celui que l'index a lu : il faut reconstruire."""


@dataclass(frozen=True, slots=True)
class Position:
    lignes: int  # lignes lisibles du manifeste lues par l'index
    empreinte: str  # sha256 de leurs octets, chacune suivie de « \n »


@dataclass(frozen=True, slots=True)
class PageIndexee:
    url: str
    page_id: str
    archive: str
    sha256: str
    collectee_le: str  # AAAA-MM-JJTHH:MM:SSZ, le début de la réponse archivée
    rang: int  # rang de sa ligne dans le manifeste (0 pour la première)
    extrait: extraction.AvisExtrait | None  # None : rejetée pour sa structure
    rejet: str | None = None  # le motif, structure ou dossier
    controle_dossier: bool = True  # False : le document d'avis ne nomme aucun dossier lisible


@dataclass(slots=True)
class PagesHas:
    """Les pages lues à une position, et ce qu'il faut en dire dans l'état de l'index."""

    position: Position
    pages: dict[str, PageIndexee] = field(default_factory=dict)  # par URL
    archivees: int = 0  # pages distinctes archivées jusqu'à la position
    collecte: str | None = None  # la dernière collecte de ces pages
    rejets: Counter[str] = field(default_factory=Counter)

    def etat(self) -> dict[str, object]:
        """Ce que l'état de l'index garde (sans le texte) : sa seconde horloge."""
        extraites = [p for p in self.pages.values() if p.rejet is None]
        return {
            "position": self.position.lignes,
            "empreinte": self.position.empreinte,
            "collecte": self.collecte,
            "extracteur": extraction.VERSION_EXTRACTEUR,
            "archivees": self.archivees,
            "rattachees": len(self.pages),
            "extraites": len(extraites),
            "rejets": dict(sorted(self.rejets.items())),
            "sans_controle": sorted(p.page_id for p in extraites if not p.controle_dossier),
        }


def position(racine: Path, lignes: int | None = None) -> Position:
    """La position du manifeste HAS : toutes ses lignes lisibles, ou les ``lignes`` premières."""
    brutes = [brute for brute, _ in mf.parcourir_brut(racine)]
    if lignes is not None:
        if lignes > len(brutes):
            raise PositionRefusee(
                f"l'index a lu {lignes} lignes du manifeste HAS, il n'en a plus que {len(brutes)}"
            )
        brutes = brutes[:lignes]
    return Position(len(brutes), hashlib.sha256(b"".join(b + b"\n" for b in brutes)).hexdigest())


def exiger_prefixe(racine: Path, connue: Position) -> None:
    """Le manifeste prolonge-t-il la position que l'index a lue ? Sinon, reconstruire."""
    if position(racine, connue.lignes) != connue:
        raise PositionRefusee(
            f"le manifeste HAS de {racine} ne prolonge plus les {connue.lignes} lignes que l'index"
            " a lues (préfixe changé) : reconstruire l'index"
        )


def lire(
    racine: Path,
    dossiers_par_url: Mapping[str, Iterable[str]],
    lignes: int | None = None,
) -> PagesHas:
    """Les pages rattachées (``dossiers_par_url``, depuis le gold), extraites, jusqu'à ``lignes``.

    Une page sans archive, ou qu'aucun lien ne désigne, n'est pas lue. Une page rejetée par
    l'extracteur est gardée avec son motif, sans texte : aucun fragment, mais l'état la compte.
    """
    lues = position(racine, lignes)
    dernieres: dict[str, tuple[int, mf.LigneHas]] = {}
    for rang, (_, ligne) in enumerate(mf.parcourir_brut(racine)):
        if rang >= lues.lignes:
            break
        if ligne.role == mf.Role.PAGE and ligne.statut in mf.ARCHIVES and ligne.archive:
            dernieres[ligne.url] = (rang, ligne)
    resultat = PagesHas(lues, archivees=len(dernieres))
    collectes = [_instant(ligne.debut) for _, ligne in dernieres.values() if ligne.debut]
    resultat.collecte = max(collectes) if collectes else None
    for url in sorted(dernieres):
        if url not in dossiers_par_url:
            continue
        rang, ligne = dernieres[url]
        resultat.pages[url] = _extraire(racine, rang, ligne, tuple(sorted(dossiers_par_url[url])))
        if resultat.pages[url].rejet:
            resultat.rejets[str(resultat.pages[url].rejet)] += 1
    return resultat


def _extraire(
    racine: Path, rang: int, ligne: mf.LigneHas, dossiers: tuple[str, ...]
) -> PageIndexee:
    octets = gzip.decompress((racine / str(ligne.archive)).read_bytes())
    if hashlib.sha256(octets).hexdigest() != ligne.sha256:
        raise PositionRefusee(f"{ligne.archive} : sha256 différent de celui du manifeste")
    commun = {
        "url": ligne.url,
        "page_id": str(ligne.page_id),
        "archive": str(ligne.archive),
        "sha256": str(ligne.sha256),
        "collectee_le": _instant(ligne.debut) if ligne.debut else "",
        "rang": rang,
    }
    try:
        extrait = extraction.extraire(octets)
    except extraction.PageRejetee as exc:
        return PageIndexee(**commun, extrait=None, rejet=exc.motif)  # type: ignore[arg-type]
    # Le contrôle de dossier, ici sur tous les dossiers qui lient la page (comme has extraire),
    # pour l'état ; les fragments le refont fiche par fiche, sur ses seuls dossiers.
    rejet = None
    try:
        extraction.controler_dossiers(extrait, dossiers)
    except extraction.PageRejetee as exc:
        rejet = exc.motif
    controle = bool(extrait.dossiers_documents)
    return PageIndexee(**commun, extrait=extrait, rejet=rejet, controle_dossier=controle)  # type: ignore[arg-type]


def _instant(debut: str) -> str:
    """« 2026-10-31T12:45:53.123+00:00 » → « 2026-10-31T12:45:53Z »."""
    return datetime.fromisoformat(debut).strftime("%Y-%m-%dT%H:%M:%SZ")
