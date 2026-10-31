"""Un passage de collecte des pages d'avis de la HAS, sa reprise et sa simulation (mission 09).

Le passage, dans l'ordre :

1. **le manifeste** est relu : une page déjà archivée n'est jamais redemandée, une page en
   erreur ne l'est qu'avec ``reessayer_erreurs`` ; une archive orpheline (coupure entre
   l'archive et sa ligne) est adoptée par une ligne ``repris``, sans requête ;
2. **``robots.txt``** est lu, archivé s'il a changé, et décide de chaque chemin. Illisible ou
   absent, il arrête le passage avant toute page (code 2). Un ``Crawl-delay`` qui vise notre
   ``User-Agent`` allonge la pause du client pour tout le passage (jamais il ne l'abrège) ;
3. **les mentions légales** sont relues (une requête comptée, addendum 1, C2). L'empreinte de
   leur texte est comparée à la précédente : un texte changé est **signalé en tête du bilan**,
   sans arrêter la collecte ; l'IeC relit alors les conditions avant toute indexation ;
4. **les pages**, dans l'ordre du périmètre. Une réponse 200 en HTML non vide est archivée à
   l'octet (``bronze/has/pages/<page>/<horodatage>__<sha12>.html.gz``), son texte extrait et
   son empreinte consignés ; toute autre réponse est une erreur visible, consignée, jamais
   archivée.

Le client arrête tout au plafond, au premier 429 ou à la seconde défaillance d'affilée du
serveur (``client``) : le bilan le dit, et la relance reprend où l'on s'était arrêté.

Codes de sortie : 0 tout ce qui était à demander est archivé ; 1 fini, avec des pages en
erreur ; 2 refus (``robots.txt`` illisible) ; 3 arrêt net (429, 5xx répété, plafond).
"""

from __future__ import annotations

import contextlib
import hashlib
import math
import re
import urllib.robotparser
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pharmaflux import bronze
from pharmaflux.collecte.archive import ArchiveExistante, ecrire_archive
from pharmaflux.collecte.passage import FORMAT_PASSAGE_ID, version_collecteur
from pharmaflux.collecte.telechargement import agent_utilisateur
from pharmaflux.has import extraction
from pharmaflux.has import manifeste as mf
from pharmaflux.has.client import ArretNet, ClientHas, PlafondAtteint, Reponse
from pharmaflux.has.perimetre import PageVisee, Perimetre, page_id

URL_SITE = "https://www.has-sante.fr"
URL_ROBOTS = f"{URL_SITE}/robots.txt"
URL_MENTIONS = f"{URL_SITE}/jcms/c_518191/fr/mentions-legales"
DOSSIER_HAS = "has"
DOSSIER_PAGES = "pages"
REPONSE_MOYENNE_SECONDES = 0.15  # mesurée au §0 (12 requêtes, 0,10 à 0,17 s)
MARGE_REESSAIS = 0.05  # le plafond conseillé : 5 % de requêtes de plus que le nécessaire

CODE_COMPLET, CODE_ERREURS, CODE_REFUS, CODE_ARRET = 0, 1, 2, 3


@dataclass(frozen=True, slots=True)
class EtatConnu:
    """Ce que le manifeste et l'archive disent avant le passage."""

    archivees: frozenset[str]  # page_id
    en_erreur: frozenset[str]  # page_id dont la dernière tentative est une erreur
    orphelines: tuple[Path, ...]  # archives de pages sans ligne de manifeste
    robots_sha256: str | None
    robots_archive: str | None
    mentions_empreinte: str | None
    mentions_archive: str | None
    mentions_passage: str | None


@dataclass(frozen=True, slots=True)
class Plan:
    """Ce qu'un passage demanderait : la simulation le rend sans aucune requête."""

    perimetre: Perimetre
    etat: EtatConnu
    a_demander: tuple[PageVisee, ...]
    erreurs_ecartees: int  # pages en erreur que l'on ne redemande pas

    @property
    def requetes(self) -> int:
        """``robots.txt``, les mentions légales, puis une requête par page à demander."""
        return 2 + len(self.a_demander)

    @property
    def plafond_conseille(self) -> int:
        return self.requetes + max(10, math.ceil(self.requetes * MARGE_REESSAIS))

    def duree_estimee(self, pause: float) -> float:
        """En secondes : une pause et une réponse moyenne par requête, sans réessai."""
        return self.requetes * (pause + REPONSE_MOYENNE_SECONDES)


@dataclass(slots=True)
class Bilan:
    passage_id: str
    plafond: int
    requetes: int = 0
    a_demander: int = 0
    archivees: int = 0
    reprises: int = 0
    rejets: Counter[str] = field(default_factory=Counter)
    erreurs: list[str] = field(default_factory=list)
    interdites: list[str] = field(default_factory=list)
    restantes: int = 0
    robots: str = "non lu"
    mentions: str = "non lues"
    mentions_a_relire: bool = False
    refus: str | None = None
    arret: str | None = None
    duree: float = 0.0

    @property
    def code_sortie(self) -> int:
        if self.refus:
            return CODE_REFUS
        if self.arret:
            return CODE_ARRET
        return CODE_ERREURS if self.erreurs else CODE_COMPLET

    def resume(self) -> str:
        lignes = []
        if self.mentions_a_relire:
            lignes.append(f"ATTENTION — mentions légales : {self.mentions}")
        lignes.append(
            f"passage HAS {self.passage_id} : {self.requetes} requête(s) sur un plafond de"
            f" {self.plafond}, {_duree(self.duree)}"
        )
        lignes.append(f"robots.txt : {self.robots}")
        lignes.append(f"mentions légales : {self.mentions}")
        rejets = ", ".join(f"{motif} {n}" for motif, n in sorted(self.rejets.items()))
        rejets = f" : {rejets}" if rejets else ""
        lignes.append(
            f"pages : {self.a_demander} à demander ; {self.archivees} archivée(s)"
            f" (dont {sum(self.rejets.values())} rejetée(s) à l'extraction{rejets}),"
            f" {len(self.erreurs)} en erreur, {len(self.interdites)} interdite(s) par robots.txt,"
            f" {self.reprises} archive(s) orpheline(s) reprise(s), {self.restantes} non demandée(s)"
        )
        lignes += [f"  erreur : {erreur}" for erreur in self.erreurs]
        lignes += [f"  interdite : {url}" for url in self.interdites]
        if self.refus:
            lignes.append(f"REFUS : {self.refus}")
        if self.arret:
            lignes.append(f"ARRÊT NET : {self.arret} ; relancer reprend où l'on s'est arrêté")
        return "\n".join(lignes)


def lire_etat(racine: Path) -> EtatConnu:
    """Une lecture du manifeste et des dossiers de pages ; rien n'est écrit."""
    lignes = mf.lire(racine)
    archives_citees = {ligne.archive for ligne in lignes if ligne.archive}
    archivees: set[str] = set()
    derniere_tentative: dict[str, str] = {}
    robots_sha: str | None = None
    robots_archive: str | None = None
    mentions: tuple[str | None, str | None, str | None] = (None, None, None)
    for ligne in lignes:
        if ligne.role == mf.Role.PAGE and ligne.page_id:
            if ligne.statut in mf.ARCHIVES:
                archivees.add(ligne.page_id)
            if ligne.statut != mf.Statut.INTERDIT_ROBOTS:
                derniere_tentative[ligne.page_id] = ligne.statut
        elif ligne.role == mf.Role.ROBOTS and ligne.archive:
            robots_sha, robots_archive = ligne.sha256, ligne.archive
        elif ligne.role == mf.Role.MENTIONS and ligne.empreinte_texte:
            mentions = (ligne.empreinte_texte, ligne.archive, ligne.passage_id)
    en_erreur = {
        page for page, statut in derniere_tentative.items() if statut not in mf.ARCHIVES
    } - archivees
    orphelines = tuple(
        chemin
        for chemin in _archives_de_pages(racine)
        if chemin.relative_to(racine).as_posix() not in archives_citees
        and chemin.parent.name not in archivees
    )
    return EtatConnu(
        archivees=frozenset(archivees),
        en_erreur=frozenset(en_erreur),
        orphelines=orphelines,
        robots_sha256=robots_sha,
        robots_archive=robots_archive,
        mentions_empreinte=mentions[0],
        mentions_archive=mentions[1],
        mentions_passage=mentions[2],
    )


def planifier(racine: Path, perimetre: Perimetre, *, reessayer_erreurs: bool = False) -> Plan:
    """Ce qu'un passage demanderait, sans aucune requête (``--simuler``)."""
    etat = lire_etat(racine)
    reprises = {chemin.parent.name for chemin in etat.orphelines}
    deja = etat.archivees | reprises
    ecartees = set() if reessayer_erreurs else set(etat.en_erreur)
    a_demander = tuple(page for page in perimetre.pages if page.page_id not in deja | ecartees)
    erreurs_ecartees = sum(1 for page in perimetre.pages if page.page_id in ecartees - deja)
    return Plan(perimetre, etat, a_demander, erreurs_ecartees)


def executer(
    racine: Path,
    plan: Plan,
    client: ClientHas,
    *,
    maintenant: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Bilan:
    """Un passage réel : ``robots.txt``, mentions légales, pages. Voir le module."""
    debut = maintenant()
    contexte = _Contexte(
        racine=racine,
        client=client,
        passage_id=debut.strftime(FORMAT_PASSAGE_ID),
        version=version_collecteur(),
        bilan=Bilan(passage_id=debut.strftime(FORMAT_PASSAGE_ID), plafond=client.plafond),
    )
    bilan = contexte.bilan
    bilan.a_demander = len(plan.a_demander)
    _reprendre_orphelines(contexte, plan)
    try:
        robots = _lire_robots(contexte, plan.etat)
        if robots is not None:
            _relire_mentions(contexte, plan.etat, robots)
            for rang, page in enumerate(plan.a_demander):
                bilan.restantes = len(plan.a_demander) - rang
                _collecter_page(contexte, page, robots)
            bilan.restantes = 0
    except PlafondAtteint as exc:
        bilan.arret = str(exc)
    except ArretNet as exc:
        bilan.arret = str(exc)
    bilan.requetes = client.envoyees
    bilan.duree = (maintenant() - debut).total_seconds()
    return bilan


@dataclass(slots=True)
class _Contexte:
    racine: Path
    client: ClientHas
    passage_id: str
    version: str
    bilan: Bilan

    def ligne(self, role: mf.Role, url: str, statut: mf.Statut, **valeurs: object) -> mf.LigneHas:
        ligne = mf.LigneHas(
            passage_id=self.passage_id,
            role=role,
            url=url,
            statut=statut,
            version_collecteur=self.version,
            user_agent=agent_utilisateur(),
            **valeurs,  # type: ignore[arg-type]
        )
        mf.ajouter(self.racine, ligne)
        return ligne


def _lire_robots(contexte: _Contexte, etat: EtatConnu) -> urllib.robotparser.RobotFileParser | None:
    bilan = contexte.bilan
    try:
        reponse = contexte.client.demander(URL_ROBOTS)
    except ArretNet as exc:
        if exc.reponse is not None:
            _consigner_erreur(
                contexte, mf.Role.ROBOTS, exc.reponse, _statut(exc.reponse, "text/plain")
            )
        bilan.robots = f"non lu ({exc}) : aucune page demandée"
        raise
    statut = _statut(reponse, "text/plain")
    if statut != mf.Statut.NOUVEAU:
        _consigner_erreur(contexte, mf.Role.ROBOTS, reponse, statut)
        bilan.robots = f"illisible ({_detail(reponse, statut)})"
        bilan.refus = "robots.txt illisible : aucune page demandée"
        return None
    sha = hashlib.sha256(reponse.contenu).hexdigest()
    if sha == etat.robots_sha256:
        statut, archive = mf.Statut.INCHANGE, etat.robots_archive
        bilan.robots = f"inchangé ({len(reponse.contenu)} octets, sha256 {sha[:12]}…)"
    else:
        archive = _archiver(
            contexte, reponse, _chemin_du_jour(contexte, "robots.txt", reponse, ".txt")
        )
        quoi = "nouveau" if etat.robots_sha256 is None else "CHANGÉ"
        bilan.robots = f"{quoi} ({len(reponse.contenu)} octets, sha256 {sha[:12]}…)"
    contexte.ligne(mf.Role.ROBOTS, URL_ROBOTS, statut, archive=archive, **_mesures(reponse))
    analyseur = urllib.robotparser.RobotFileParser(URL_ROBOTS)
    analyseur.parse(_lignes_robots(reponse.contenu.decode("utf-8", errors="replace")))
    if not analyseur.can_fetch(agent_utilisateur(), f"{URL_SITE}/jcms/p_1"):
        bilan.robots += " ; les pages d'avis sont interdites"
    delai = analyseur.crawl_delay(agent_utilisateur())
    if delai is not None and float(delai) > contexte.client.pause:
        contexte.client.pause = float(delai)
        bilan.robots += f" ; Crawl-delay {delai} s : la pause passe à {delai} s"
    return analyseur


_CRAWL_DELAY_DECIMAL = re.compile(r"^(\s*crawl-delay\s*:\s*)(\d*\.\d+)\s*$", re.IGNORECASE)


def _lignes_robots(texte: str) -> list[str]:
    """Les lignes de ``robots.txt`` ; un ``Crawl-delay`` décimal est arrondi au-dessus.

    ``urllib.robotparser`` ne lit qu'un délai entier et ignore « 2.5 » sans rien dire : on le
    porte à 3, du côté de la politesse.
    """
    return [
        _CRAWL_DELAY_DECIMAL.sub(lambda m: f"{m[1]}{math.ceil(float(m[2]))}", ligne)
        for ligne in texte.splitlines()
    ]


def _relire_mentions(
    contexte: _Contexte, etat: EtatConnu, robots: urllib.robotparser.RobotFileParser
) -> None:
    bilan = contexte.bilan
    if not robots.can_fetch(agent_utilisateur(), URL_MENTIONS):
        contexte.ligne(mf.Role.MENTIONS, URL_MENTIONS, mf.Statut.INTERDIT_ROBOTS)
        bilan.mentions, bilan.mentions_a_relire = "interdites par robots.txt, non relues", True
        return
    try:
        reponse = contexte.client.demander(URL_MENTIONS)
    except ArretNet as exc:
        if exc.reponse is not None:
            _consigner_erreur(
                contexte, mf.Role.MENTIONS, exc.reponse, _statut(exc.reponse, "text/html")
            )
        bilan.mentions, bilan.mentions_a_relire = f"non relues ({exc})", True
        raise
    statut = _statut(reponse, "text/html")
    texte = extraction.texte_principal(reponse.contenu) if statut == mf.Statut.NOUVEAU else None
    if texte is None:
        detail = _detail(reponse, statut) if statut != mf.Statut.NOUVEAU else "aucun <main>"
        _consigner_erreur(contexte, mf.Role.MENTIONS, reponse, statut)
        bilan.mentions, bilan.mentions_a_relire = f"illisibles ({detail}) : à relire", True
        return
    empreinte = extraction.empreinte_texte(texte)
    if empreinte == etat.mentions_empreinte:
        statut, archive = mf.Statut.INCHANGE, etat.mentions_archive
        bilan.mentions = f"texte inchangé depuis le passage {etat.mentions_passage}"
    else:
        archive = _archiver(
            contexte, reponse, _chemin_du_jour(contexte, "mentions-legales", reponse, ".html")
        )
        if etat.mentions_empreinte is None:
            bilan.mentions = "pas encore de référence (premier passage) ; texte archivé"
        else:
            bilan.mentions = (
                f"TEXTE CHANGÉ depuis le passage {etat.mentions_passage} : relire les conditions"
                " de réutilisation (ADR 0004) avant toute indexation"
            )
            bilan.mentions_a_relire = True
    contexte.ligne(
        mf.Role.MENTIONS,
        URL_MENTIONS,
        statut,
        archive=archive,
        empreinte_texte=empreinte,
        **_mesures(reponse),
    )


def _collecter_page(
    contexte: _Contexte, page: PageVisee, robots: urllib.robotparser.RobotFileParser
) -> None:
    bilan = contexte.bilan
    attributs: dict[str, object] = {
        "page_id": page.page_id,
        "dossiers": list(page.dossiers),
        "date_avis_bdpm": page.date_avis,
    }
    if not robots.can_fetch(agent_utilisateur(), page.url):
        contexte.ligne(mf.Role.PAGE, page.url, mf.Statut.INTERDIT_ROBOTS, **attributs)
        bilan.interdites.append(page.url)
        return
    try:
        reponse = contexte.client.demander(page.url)
    except ArretNet as exc:
        if exc.reponse is not None:
            statut = _statut(exc.reponse, "text/html")
            _consigner_erreur(contexte, mf.Role.PAGE, exc.reponse, statut, **attributs)
            bilan.erreurs.append(f"{page.url} : {_detail(exc.reponse, statut)}")
        raise
    statut = _statut(reponse, "text/html")
    if statut != mf.Statut.NOUVEAU:
        _consigner_erreur(contexte, mf.Role.PAGE, reponse, statut, **attributs)
        bilan.erreurs.append(f"{page.url} : {_detail(reponse, statut)}")
        return
    chemin = (
        contexte.racine
        / bronze.DOSSIER_BRONZE
        / DOSSIER_HAS
        / DOSSIER_PAGES
        / page.page_id
        / _nom_archive(reponse, ".html")
    )
    archive = _archiver(contexte, reponse, chemin)
    extrait = _extraction(reponse.contenu, page.dossiers)
    contexte.ligne(
        mf.Role.PAGE,
        page.url,
        mf.Statut.NOUVEAU,
        archive=archive,
        **extrait,
        **_mesures(reponse),
        **attributs,
    )
    bilan.archivees += 1
    if "rejet" in extrait:
        bilan.rejets[str(extrait["rejet"])] += 1


def _reprendre_orphelines(contexte: _Contexte, plan: Plan) -> None:
    """Une archive sans ligne (coupure entre l'écriture et le manifeste) : adoptée, sans requête."""
    pages = {page.page_id: page for page in plan.perimetre.pages}
    for chemin in plan.etat.orphelines:
        identifiant = chemin.parent.name
        contenu = bronze.lire_archive(chemin)
        page = pages.get(identifiant)
        dossiers = page.dossiers if page else None
        extrait = _extraction(contenu, dossiers)
        if "rejet" in extrait:
            contexte.bilan.rejets[str(extrait["rejet"])] += 1
        contexte.ligne(
            mf.Role.PAGE,
            page.url if page else f"{URL_SITE}/jcms/{identifiant}",
            mf.Statut.REPRIS,
            page_id=identifiant,
            dossiers=list(dossiers) if dossiers else None,
            date_avis_bdpm=page.date_avis if page else None,
            archive=chemin.relative_to(contexte.racine).as_posix(),
            taille=len(contenu),
            sha256=hashlib.sha256(contenu).hexdigest(),
            **extrait,
        )
        contexte.bilan.reprises += 1


def _extraction(contenu: bytes, dossiers: tuple[str, ...] | None) -> dict[str, object]:
    try:
        extrait = extraction.extraire(contenu, dossiers=dossiers)
    except extraction.PageRejetee as exc:
        return {"extracteur": extraction.VERSION_EXTRACTEUR, "rejet": exc.motif}
    return {"extracteur": extraction.VERSION_EXTRACTEUR, "empreinte_texte": extrait.empreinte()}


def _statut(reponse: Reponse, type_attendu: str) -> mf.Statut:
    if reponse.statut is None:
        return mf.Statut.ERREUR_RESEAU
    if 300 <= reponse.statut < 400:
        return mf.Statut.REDIRECTION
    if reponse.statut != 200:
        return mf.Statut.ERREUR_HTTP
    if not reponse.contenu:
        return mf.Statut.VIDE
    type_recu = (reponse.en_tete("content-type") or "").split(";")[0].strip().lower()
    if type_recu != type_attendu:
        return mf.Statut.TYPE_INATTENDU
    return mf.Statut.NOUVEAU


def _detail(reponse: Reponse, statut: mf.Statut) -> str:
    if statut == mf.Statut.ERREUR_RESEAU:
        return str(reponse.erreur)
    if statut == mf.Statut.REDIRECTION:
        return f"HTTP {reponse.statut} vers {reponse.en_tete('location')}, non suivie"
    if statut == mf.Statut.TYPE_INATTENDU:
        return f"type {reponse.en_tete('content-type')}"
    if statut == mf.Statut.VIDE:
        return "corps vide"
    return f"HTTP {reponse.statut}"


def _mesures(reponse: Reponse) -> dict[str, object]:
    return {
        "debut": reponse.debut.isoformat(),
        "fin": reponse.fin.isoformat(),
        "essais": reponse.essais,
        "http_statut": reponse.statut,
        "content_type": reponse.en_tete("content-type"),
        "location": reponse.en_tete("location"),
        "taille": len(reponse.contenu),
        "sha256": hashlib.sha256(reponse.contenu).hexdigest(),
    }


def _consigner_erreur(
    contexte: _Contexte, role: mf.Role, reponse: Reponse, statut: mf.Statut, **valeurs: object
) -> None:
    url = reponse.url
    contexte.ligne(
        role, url, statut, erreur=_detail(reponse, statut), **_mesures(reponse), **valeurs
    )


def _nom_archive(reponse: Reponse, extension: str) -> str:
    sha = hashlib.sha256(reponse.contenu).hexdigest()
    return f"{reponse.debut.strftime(bronze.FORMAT_HORODATAGE)}__{sha[:12]}{extension}.gz"


def _chemin_du_jour(contexte: _Contexte, nom: str, reponse: Reponse, extension: str) -> Path:
    return (
        contexte.racine
        / bronze.DOSSIER_BRONZE
        / DOSSIER_HAS
        / nom
        / reponse.debut.strftime("%Y-%m-%d")
        / _nom_archive(reponse, extension)
    )


def _archiver(contexte: _Contexte, reponse: Reponse, chemin: Path) -> str:
    """Écrit l'archive à l'octet (immuable) ; rend son chemin relatif à la racine."""
    # Même horodatage et même empreinte : c'est la même réponse, déjà écrite.
    with contextlib.suppress(ArchiveExistante):
        ecrire_archive(chemin, reponse.contenu, reponse.debut)
    return chemin.relative_to(contexte.racine).as_posix()


def _archives_de_pages(racine: Path) -> list[Path]:
    dossier = racine / bronze.DOSSIER_BRONZE / DOSSIER_HAS / DOSSIER_PAGES
    if not dossier.is_dir():
        return []
    return sorted(
        chemin
        for page in dossier.iterdir()
        if page.is_dir()
        and not page.name.startswith(".")
        and page_id(f"{URL_SITE}/jcms/{page.name}")
        for chemin in page.iterdir()
        if chemin.is_file() and bronze.MOTIF_NOM.match(chemin.name)
    )


def _duree(secondes: float) -> str:
    minutes, reste = divmod(round(secondes), 60)
    return f"{minutes} min {reste:02d} s" if minutes else f"{reste} s"
