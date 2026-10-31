"""Les pages d'avis à demander, depuis l'archive de la BDPM, sans réseau (ADR 0004, mission 09).

Le corpus est celui des liens de ``HAS_LiensPageCT_bdpm.txt`` : une page par URL distincte.
Un dossier entre dans la première étape s'il a un avis SMR ou ASMR daté de ``depuis`` ou après ;
ses liens donnent les pages. On lit la **dernière archive** de chacun des trois fichiers, par
leur contrat : une anomalie bloquante refuse le périmètre plutôt que de deviner.

L'ordre est déterministe : la date d'avis la plus récente des dossiers qui lient la page, en
décroissant, puis le premier de ces dossiers, puis l'URL. Une commande arrêtée a donc pris les
avis les plus récents d'abord.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pharmaflux import bronze
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.contrats.verification import verifier

DEPUIS_PAR_DEFAUT = date(2024, 1, 1)
HOTE = "www.has-sante.fr"
MOTIF_URL_AVIS = re.compile(r"^https://www\.has-sante\.fr/jcms/(?P<page>[pc]_\d+)$")
FICHIERS = {
    "bdpm.liens_ct": "HAS_LiensPageCT_bdpm.txt",
    "bdpm.smr": "CIS_HAS_SMR_bdpm.txt",
    "bdpm.asmr": "CIS_HAS_ASMR_bdpm.txt",
}


class PerimetreIllisible(ValueError):  # noqa: N818 (nom français voulu)
    """Une archive de la BDPM manque ou porte une anomalie bloquante : rien n'est demandé."""


@dataclass(frozen=True, slots=True)
class SourceLue:
    """Une archive de la BDPM lue pour le périmètre : son chemin relatif et son sha256."""

    identifiant: str
    archive: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PageVisee:
    url: str
    page_id: str  # p_N ou c_N
    dossiers: tuple[str, ...]  # les dossiers qui lient la page, triés
    date_avis: str  # AAAAMMJJ, la plus récente des avis de ces dossiers


@dataclass(frozen=True, slots=True)
class Perimetre:
    depuis: date
    pages: tuple[PageVisee, ...]
    dossiers: int  # avec un avis daté de ``depuis`` ou après
    dossiers_avec_lien: int
    dossiers_sans_lien: tuple[str, ...]
    liens_hors_forme: tuple[str, ...]  # URL qui ne sont pas une page d'avis /jcms/p_N ou c_N
    sources: tuple[SourceLue, ...]
    # Les CIS de chaque dossier retenu, d'après le SMR et l'ASMR : le choix du jeu de démo.
    cis_par_dossier: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def empreinte_liste(self) -> str:
        """Le sha256 de la liste des URL, une par ligne, dans l'ordre : pour la citer."""
        return hashlib.sha256("".join(p.url + "\n" for p in self.pages).encode()).hexdigest()


def page_id(url: str) -> str | None:
    """``p_4072400`` pour ``https://www.has-sante.fr/jcms/p_4072400`` ; ``None`` hors forme."""
    correspondance = MOTIF_URL_AVIS.match(url)
    return correspondance["page"] if correspondance else None


def calculer(
    racine: Path, *, depuis: date = DEPUIS_PAR_DEFAUT, dossiers: Iterable[str] | None = None
) -> Perimetre:
    """Le périmètre depuis la dernière archive des trois fichiers. ``dossiers`` le restreint."""
    contrats = charger_tous()
    sources: list[SourceLue] = []
    lignes: dict[str, list[tuple[str, ...]]] = {}
    for identifiant, fichier in FICHIERS.items():
        archive = bronze.derniere(racine, "bdpm", fichier)
        if archive is None:
            raise PerimetreIllisible(f"aucune archive de {fichier} sous {racine}")
        octets = archive.lire()
        lecture = verifier(contrats[identifiant], octets, fichier=archive.relatif(racine))
        if lecture.bloquantes:
            premiere = lecture.bloquantes[0]
            raise PerimetreIllisible(
                f"{archive.relatif(racine)} : {len(lecture.bloquantes)} anomalie(s) bloquante(s),"
                f" dont {premiere.regle} ligne {premiere.ligne}"
            )
        sources.append(
            SourceLue(identifiant, archive.relatif(racine), hashlib.sha256(octets).hexdigest())
        )
        lignes[identifiant] = [valeurs for _, valeurs in lecture.lignes]

    seuil = depuis.strftime("%Y%m%d")
    retenus = set(dossiers) if dossiers is not None else None
    date_par_dossier: dict[str, str] = {}
    cis_par_dossier: dict[str, set[str]] = defaultdict(set)
    for identifiant in ("bdpm.smr", "bdpm.asmr"):
        contrat = contrats[identifiant]
        i_dossier, i_date = contrat.index("code_dossier_has"), contrat.index("date_avis")
        i_cis = contrat.index("code_cis")
        for valeurs in lignes[identifiant]:
            dossier, date_avis = valeurs[i_dossier], valeurs[i_date]
            if date_avis >= seuil and (retenus is None or dossier in retenus):
                date_par_dossier[dossier] = max(date_par_dossier.get(dossier, ""), date_avis)
                cis_par_dossier[dossier].add(valeurs[i_cis])

    contrat_liens = contrats["bdpm.liens_ct"]
    i_dossier, i_lien = contrat_liens.index("code_dossier_has"), contrat_liens.index("lien_avis")
    dossiers_par_url: dict[str, set[str]] = defaultdict(set)
    for valeurs in lignes["bdpm.liens_ct"]:
        if valeurs[i_dossier] in date_par_dossier:
            dossiers_par_url[valeurs[i_lien]].add(valeurs[i_dossier])

    avec_lien = set().union(*dossiers_par_url.values()) if dossiers_par_url else set()
    hors_forme = sorted(url for url in dossiers_par_url if page_id(url) is None)
    pages = [
        PageVisee(
            url=url,
            page_id=str(page_id(url)),
            dossiers=tuple(sorted(lies)),
            date_avis=max(date_par_dossier[d] for d in lies),
        )
        for url, lies in dossiers_par_url.items()
        if page_id(url) is not None
    ]
    # La date décroissante, puis le premier dossier, puis l'URL : sans ambiguïté.
    pages.sort(key=lambda p: (_inverse(p.date_avis), p.dossiers[0], p.url))
    return Perimetre(
        depuis=depuis,
        pages=tuple(pages),
        dossiers=len(date_par_dossier),
        dossiers_avec_lien=len(avec_lien),
        dossiers_sans_lien=tuple(sorted(set(date_par_dossier) - avec_lien)),
        liens_hors_forme=tuple(hors_forme),
        sources=tuple(sources),
        cis_par_dossier={d: tuple(sorted(c)) for d, c in sorted(cis_par_dossier.items())},
    )


def _inverse(date_avis: str) -> str:
    """Une clé de tri qui range AAAAMMJJ du plus récent au plus ancien, en restant une chaîne."""
    return "".join(str(9 - int(chiffre)) for chiffre in date_avis)
