"""Les pages d'avis de la HAS du jeu de démo (mission 09, addendum 1 E) : choix, copie, contrôle.

Le jeu a deux parties figées, chacune avec son manifeste : la BDPM (mission 04,
``manifeste/collecte.jsonl``), qui ne change pas d'un octet, et un sous-ensemble des pages
d'avis de la première étape (mission 09, ``manifeste/has-pages.jsonl``, archives sous
``bronze/has/pages/``).

Le choix est une règle, écrite ici et dans ``demo/README.md``. La liste qu'elle donne est
committée (``demo/has-pages.txt``), et un test la recalcule sur le jeu :

1. les pages imposées (``PAGES_IMPOSEES``) : les fixtures du §0 et les cas que la collecte
   a montrés (avis communs, entités, page rejetée, contrôle de dossier impossible) ;
2. les pages des CIS visés par une question du jeu v1 (``cis_attendu``) ;
3. un complément déterministe : les plus petits sha256 de l'URL, jusqu'à ``NOMBRE_PAGES``.

``fabriquer`` copie, depuis l'archive de beko, la dernière archive de chaque page de la liste
et sa ligne de manifeste, à l'octet, dans l'ordre du manifeste source. Il refuse un jeu qui a
déjà ses pages, et n'écrit jamais dans la racine. ``verifier`` contrôle chaque page (place,
nom, sha256, taille) ; le contrôle d'ensemble (rien d'étranger) est dans ``jeu.verifier``.
"""

from __future__ import annotations

import gzip
import hashlib
import re
import shutil
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pharmaflux.bronze import MOTIF_NOM
from pharmaflux.collecte.manifeste import ManifesteCorrompu
from pharmaflux.has import manifeste as mf
from pharmaflux.has.perimetre import Perimetre

NOMBRE_PAGES = 150
LISTE_PAR_DEFAUT = Path("demo/has-pages.txt")
QUESTIONS_PAR_DEFAUT = Path("evaluation/questions-reference-v1.toml")
DOSSIER_PAGES = "bronze/has/pages"
COMPLEMENT = "complément : plus petit sha256 de l'URL"

# Dans cet ordre en tête de liste ; chacune est une page de la première étape.
PAGES_IMPOSEES: dict[str, str] = {
    "p_4072400": "§0 : MOUNJARO, un dossier pour douze spécialités",
    "p_3590639": "§0 : IMFINZI - LYNPARZA, un dossier, deux marques",
    "p_3577036": "§0 : KALYDECO (avis_has-002, -008, -009 de la v1)",
    "p_3500927": "§0 : ADEMPAS, premier des deux liens de CT-20568",
    "p_3741668": "§0 : ADEMPAS, second lien de CT-20568, sans document d'avis",
    "p_3638197": "collecte : KEPPRA, entité dans le nom JSON-LD",
    "p_3892357": "collecte : XALKORI, entité dans le nom JSON-LD",
    "p_3686940": "collecte : BEXSERO, avis commun à cinq vaccins (« & »)",
    "p_3687274": "collecte : NIMENRIX, avis commun à cinq vaccins (« & »)",
    "p_3686928": "collecte : MENQUADFI, avis commun à cinq vaccins (« & »)",
    "p_3686943": "collecte : MENVEO, avis commun à cinq vaccins (« & »)",
    "p_3686931": "collecte : TRUMENBA, avis commun à cinq vaccins (« & »)",
    "p_3530986": "collecte : FINLEE / SPEXOTRAS, avis commun à deux dossiers",
    "p_4335961": "collecte : NICORANDIL, avis commun à cinq dossiers (« _ »)",
    "p_4335975": "collecte : NICORANDIL, avis commun à cinq dossiers (« _ »)",
    "p_4335965": "collecte : NICORANDIL, avis commun à cinq dossiers (« _ »)",
    "p_4335969": "collecte : NICORANDIL, avis commun à cinq dossiers (« _ »)",
    "p_4335946": "collecte : NICORANDIL, avis commun à cinq dossiers (« _ »)",
    "p_3608587": "collecte : PEDMARQSI, rejetée (le document d'avis nomme un autre dossier)",
    "p_3534726": "collecte : contrôle de dossier impossible (synthèse seule)",
    "p_3639721": "collecte : contrôle de dossier impossible (aucun document)",
    "p_3861364": "collecte : contrôle de dossier impossible (réévaluation de classe)",
}

_LIGNE_LISTE = re.compile(r"^(?P<url>https://\S+)\s+#\s+(?P<raison>.+)$")


class FabricationRefusee(Exception):  # noqa: N818 (nom français voulu)
    """Liste illisible, page absente de l'archive, pages déjà dans le jeu : rien n'est écrit."""


@dataclass(frozen=True, slots=True)
class PageChoisie:
    url: str
    page_id: str
    raison: str


@dataclass(slots=True)
class BilanHas:
    """La partie HAS d'un jeu : ses lignes, ses pages, ce qui la rend non conforme."""

    lignes: int = 0
    pages: list[str] = field(default_factory=list)  # page_id, dans l'ordre du manifeste
    octets: int = 0  # archives compressées
    cites: set[str] = field(default_factory=set)  # chemins relatifs à la racine du jeu
    anomalies: list[str] = field(default_factory=list)
    present: bool = False


def cis_des_questions(chemin: Path) -> set[str]:
    """Les CIS visés par un jeu de questions (``cis_attendu``)."""
    questions = tomllib.loads(chemin.read_text(encoding="utf-8"))["questions"]
    return {str(q["cis_attendu"]) for q in questions if q.get("cis_attendu")}


def choisir(perimetre: Perimetre, cis_voulus: Iterable[str]) -> list[PageChoisie]:
    """La règle du module, dans l'ordre : imposées, pages des questions, complément."""
    par_id = {page.page_id: page for page in perimetre.pages}
    absentes = sorted(set(PAGES_IMPOSEES) - set(par_id))
    if absentes:
        raise FabricationRefusee(f"pages imposées hors du périmètre : {', '.join(absentes)}")
    choix = {page_id: PageChoisie(par_id[page_id].url, page_id, raison)
             for page_id, raison in PAGES_IMPOSEES.items()}  # fmt: skip
    voulus = set(cis_voulus)
    for page in perimetre.pages:
        cis = {c for d in page.dossiers for c in perimetre.cis_par_dossier.get(d, ())} & voulus
        if cis and page.page_id not in choix:
            raison = f"question v1 : CIS {', '.join(sorted(cis))}"
            choix[page.page_id] = PageChoisie(page.url, page.page_id, raison)
    reste = sorted(
        (page for page in perimetre.pages if page.page_id not in choix),
        key=lambda page: hashlib.sha256(page.url.encode()).hexdigest(),
    )
    for page in reste[: max(0, NOMBRE_PAGES - len(choix))]:
        choix[page.page_id] = PageChoisie(page.url, page.page_id, COMPLEMENT)
    return list(choix.values())


def ecrire_liste(chemin: Path, pages: Iterable[PageChoisie], entete: Iterable[str]) -> None:
    lignes = [f"# {ligne}" if ligne else "#" for ligne in entete]
    lignes += [f"{page.url}  # {page.raison}" for page in pages]
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def lire_liste(chemin: Path) -> list[PageChoisie]:
    """``URL  # raison`` par ligne ; les lignes qui commencent par « # » sont l'en-tête."""
    pages = []
    for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), start=1):
        if not ligne.strip() or ligne.startswith("#"):
            continue
        trouve = _LIGNE_LISTE.match(ligne)
        page_id = trouve["url"].rsplit("/", 1)[-1] if trouve else ""
        if trouve is None or not re.fullmatch(r"[pc]_\d+", page_id):
            raise FabricationRefusee(f"{chemin}, ligne {numero} : « URL  # raison » attendu")
        pages.append(PageChoisie(trouve["url"], page_id, trouve["raison"]))
    return pages


def fabriquer(racine: Path, destination: Path, liste: Path) -> BilanHas:
    """Copie la dernière archive de chaque page de ``liste`` et sa ligne, à l'octet.

    Deux passes sur le manifeste source : la première vérifie que chaque page a une archive
    présente, la seconde écrit. Refus, avant tout écriture : liste illisible ou en double,
    page sans archive, destination sous la racine, pages HAS déjà dans le jeu.
    """
    voulues = [page.page_id for page in lire_liste(liste)]
    doubles = sorted({p for p in voulues if voulues.count(p) > 1})
    if doubles:
        raise FabricationRefusee(f"{liste} : page(s) en double : {', '.join(doubles)}")
    if destination.resolve().is_relative_to(racine.resolve()):
        raise FabricationRefusee(f"{destination} est sous la racine {racine}, qui ne s'écrit pas")
    cible = mf.chemin_manifeste(destination)
    if cible.exists() or (destination / DOSSIER_PAGES).exists():
        raise FabricationRefusee(
            f"{destination} a déjà ses pages d'avis : un jeu ne se met pas à jour"
        )
    source = mf.chemin_manifeste(racine)
    if not source.is_file():
        raise FabricationRefusee(f"{source} absent : aucune page d'avis collectée sous {racine}")
    dernieres: dict[str, int] = {}  # page_id -> rang de sa dernière ligne archivée
    lignes = list(mf.parcourir_brut(racine))
    for rang, (_, ligne) in enumerate(lignes):
        if ligne.role == mf.Role.PAGE and ligne.statut in mf.ARCHIVES and ligne.page_id:
            dernieres[ligne.page_id] = rang
    sans_archive = [p for p in voulues if p not in dernieres]
    if sans_archive:
        raise FabricationRefusee(f"page(s) sans archive sous {racine} : {', '.join(sans_archive)}")
    retenus = sorted(dernieres[p] for p in voulues)
    for rang in retenus:
        archive = lignes[rang][1].archive or ""
        if not (racine / archive).is_file():
            raise FabricationRefusee(f"{archive}, cité par le manifeste, est absent de {racine}")
    cible.parent.mkdir(parents=True, exist_ok=True)
    temporaire = cible.with_name(f".{cible.name}.partiel")
    with temporaire.open("wb") as flux:
        for rang in retenus:
            brute, ligne = lignes[rang]
            copie = destination / (ligne.archive or "")
            copie.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(racine / (ligne.archive or ""), copie)
            flux.write(brute + b"\n")
    temporaire.replace(cible)
    return verifier(destination)


def verifier(racine: Path) -> BilanHas:
    """Chaque ligne du manifeste HAS du jeu : une page archivée, à sa place, au sha256 près."""
    bilan = BilanHas()
    if not mf.chemin_manifeste(racine).exists():
        return bilan
    bilan.present = True
    bilan.cites.add(mf.chemin_manifeste(racine).relative_to(racine).as_posix())
    try:
        for _, ligne in mf.parcourir_brut(racine):
            bilan.lignes += 1
            bilan.anomalies.extend(_verifier_page(racine, bilan, ligne))
    except ManifesteCorrompu as exc:
        bilan.anomalies.append(str(exc))
    return bilan


def _verifier_page(racine: Path, bilan: BilanHas, ligne: mf.LigneHas) -> list[str]:
    numero = f"has-pages.jsonl, ligne {bilan.lignes}"
    if ligne.role != mf.Role.PAGE or ligne.statut not in mf.ARCHIVES or not ligne.archive:
        return [f"{numero} : pas une page archivée ({ligne.role}, {ligne.statut})"]
    if ligne.page_id in bilan.pages:
        return [f"{numero} : {ligne.page_id} déjà dans le jeu"]
    bilan.pages.append(str(ligne.page_id))
    chemin, sha256 = ligne.archive, ligne.sha256 or ""
    anomalies = []
    if not chemin.startswith(f"{DOSSIER_PAGES}/{ligne.page_id}/"):
        anomalies.append(f"{chemin} : hors de {DOSSIER_PAGES}/{ligne.page_id}/")
    correspondance = MOTIF_NOM.match(Path(chemin).name)
    if correspondance is None or correspondance["sha256"] != sha256[:12]:
        anomalies.append(f"{chemin} : le nom ne porte pas le début du sha256 {sha256[:12]}")
    fichier = racine / chemin
    if not fichier.is_file():
        return [*anomalies, f"{chemin} : cité par le manifeste, absent du jeu"]
    bilan.cites.add(chemin)
    bilan.octets += fichier.stat().st_size
    try:
        octets = gzip.decompress(fichier.read_bytes())
    except (OSError, EOFError) as exc:
        return [*anomalies, f"{chemin} : archive illisible ({exc})"]
    if hashlib.sha256(octets).hexdigest() != sha256:
        anomalies.append(f"{chemin} : sha256 différent de celui du manifeste")
    if ligne.taille is not None and len(octets) != ligne.taille:
        anomalies.append(f"{chemin} : {len(octets)} octets au lieu de {ligne.taille}")
    return anomalies
