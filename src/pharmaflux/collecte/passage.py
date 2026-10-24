"""Un passage de collecte : télécharger, comparer, archiver, consigner.

Pour chaque entrée du catalogue, dans l'ordre et en série : téléchargement,
empreintes, décision « nouveau » ou « inchangé » contre la dernière
empreinte connue du manifeste, archivage si nouveau, et dans tous les cas
une ligne dans le manifeste. Une erreur sur un fichier n'arrête pas les
autres. La page de téléchargement, lue en premier, fournit la date et la
taille affichées des fichiers BDPM et révèle un lien absent ou nouveau.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version as version_du_paquet
from pathlib import Path

from pharmaflux.collecte import manifeste
from pharmaflux.collecte.archive import ArchiveExistante, chemin_archive, ecrire_archive
from pharmaflux.collecte.catalogue import (
    Cadence,
    Entree,
    ModeEmpreinte,
    entrees_bdpm_par_url,
)
from pharmaflux.collecte.empreintes import empreinte_comparaison, sha256_hex
from pharmaflux.collecte.manifeste import Enregistrement, Statut
from pharmaflux.collecte.page import AnalyseImpossible, LienTelechargement, analyser_page
from pharmaflux.collecte.telechargement import ErreurTelechargement, Telechargeur

journal = logging.getLogger("pharmaflux.collecte")

PAUSE_SECONDES = 2.0
FORMAT_PASSAGE_ID = "%Y%m%dT%H%M%SZ"

MOTIF_LIEN_ABSENT = "lien_absent"
MOTIF_LIEN_NOUVEAU = "lien_nouveau"
MOTIF_ARCHIVE_EXISTANTE = "archive_existante"
MOTIF_INATTENDUE = "inattendue"


def maintenant_utc() -> datetime:
    return datetime.now(UTC)


def version_collecteur() -> str:
    """Version du paquet et commit courant (``0.1.0+abc1234``), pour le rejeu."""
    version = version_du_paquet("pharmaflux")
    try:
        resultat = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return version
    commit = resultat.stdout.strip()
    return f"{version}+{commit}" if resultat.returncode == 0 and commit else version


@dataclass(slots=True)
class Bilan:
    """Ce qu'un passage a produit."""

    passage_id: str
    enregistrements: list[Enregistrement] = field(default_factory=list)

    def compter(self, statut: Statut) -> int:
        return sum(1 for e in self.enregistrements if e.statut == statut)

    @property
    def code_sortie(self) -> int:
        return 1 if self.compter(Statut.ERREUR) else 0

    def resume(self) -> str:
        return (
            f"passage {self.passage_id} : {self.compter(Statut.NOUVEAU)} nouveau(x), "
            f"{self.compter(Statut.INCHANGE)} inchangé(s), "
            f"{self.compter(Statut.NON_MODIFIE_304)} non modifié(s) 304, "
            f"{self.compter(Statut.ERREUR)} erreur(s)"
        )


@dataclass(slots=True)
class _Contexte:
    racine: Path
    telechargeur: Telechargeur
    maintenant: Callable[[], datetime]
    passage_id: str
    version: str
    empreintes_connues: dict[str, str]


def executer_passage(
    racine: Path,
    entrees: list[Entree] | tuple[Entree, ...],
    telechargeur: Telechargeur,
    *,
    maintenant: Callable[[], datetime] = maintenant_utc,
    dormir: Callable[[float], None] = time.sleep,
    pause: float = PAUSE_SECONDES,
) -> Bilan:
    """Un passage complet sur ``entrees`` : tout finit dans le manifeste.

    Une erreur sur une entrée, prévue (téléchargement, analyse, archive) ou
    non (filet ``inattendue``), donne une ligne en erreur et le passage
    continue. Ne lève que si le manifeste lui-même ne peut plus être écrit
    (``OSError``, disque plein) : il n'y a alors plus où consigner.
    """
    debut_passage = maintenant()
    anterieurs = manifeste.lire(racine)
    contexte = _Contexte(
        racine=racine,
        telechargeur=telechargeur,
        maintenant=maintenant,
        passage_id=debut_passage.strftime(FORMAT_PASSAGE_ID),
        version=version_collecteur(),
        empreintes_connues=manifeste.dernieres_empreintes(anterieurs),
    )
    bilan = Bilan(contexte.passage_id)
    journal.info("début du passage %s vers %s", contexte.passage_id, racine)

    liens_page: dict[str, LienTelechargement] | None = None
    premier = True
    for entree in entrees:
        if entree.cadence is Cadence.QUOTIDIENNE and _collectee_ce_jour(
            anterieurs, entree, debut_passage
        ):
            journal.info(
                "%s : déjà collectée aujourd'hui (cadence quotidienne)", entree.identifiant
            )
            continue
        if not premier:
            dormir(pause)
        premier = False

        enregistrement: Enregistrement | None = None
        try:
            enregistrement, contenu = _collecter(contexte, entree)
            if entree.empreinte is ModeEmpreinte.PAGE_BDPM and contenu is not None:
                liens_page = _liens_par_url(contenu)
            elif entree.source == "bdpm" and liens_page is not None:
                _appliquer_page(enregistrement, liens_page.get(entree.url))
        except Exception as exc:  # filet (décision 6) : une entrée n'arrête pas les autres
            journal.exception("%s : erreur inattendue", entree.identifiant)
            enregistrement = _marquer_inattendue(contexte, entree, enregistrement, exc)
        _consigner(contexte, bilan, enregistrement)

    if liens_page is not None:
        for lien in _liens_nouveaux(liens_page):
            _consigner(contexte, bilan, _enregistrement_lien_nouveau(contexte, lien))

    journal.info(bilan.resume())
    return bilan


def _collecter(contexte: _Contexte, entree: Entree) -> tuple[Enregistrement, bytes | None]:
    """Télécharge et archive une entrée ; renvoie la ligne de manifeste et les octets reçus."""
    debut = contexte.maintenant()
    enregistrement = Enregistrement(
        passage_id=contexte.passage_id,
        identifiant=entree.identifiant,
        source=entree.source,
        fichier=entree.fichier,
        url=entree.url,
        debut=debut.isoformat(),
        fin=debut.isoformat(),
        statut=Statut.ERREUR,
        version_collecteur=contexte.version,
    )
    try:
        reponse = contexte.telechargeur.telecharger(entree.url)
    except ErreurTelechargement as exc:
        enregistrement.erreur = str(exc)
        enregistrement.essais = exc.essais
        enregistrement.http_statut = exc.http_statut
        return _terminer(contexte, enregistrement), None

    enregistrement.essais = reponse.essais
    enregistrement.http_statut = reponse.http_statut
    enregistrement.last_modified = reponse.last_modified
    enregistrement.etag = reponse.etag
    enregistrement.content_disposition_nom = reponse.content_disposition_nom
    if reponse.http_statut == 304:
        enregistrement.statut = Statut.NON_MODIFIE_304
        return _terminer(contexte, enregistrement), None

    contenu = reponse.contenu
    sha256 = sha256_hex(contenu)
    enregistrement.sha256 = sha256
    enregistrement.taille_octets = len(contenu)
    try:
        empreinte = empreinte_comparaison(entree.empreinte, contenu)
    except AnalyseImpossible as exc:
        # Forme inattendue : on archive quand même (l'archive est irremplaçable),
        # mais la ligne est en erreur pour que quelqu'un regarde. L'empreinte
        # retombe sur les octets : un contenu identique n'est pas réarchivé.
        enregistrement.erreur = f"analyse_impossible: {exc}"
        empreinte = sha256
    enregistrement.empreinte_comparaison = empreinte
    if contexte.empreintes_connues.get(entree.identifiant) == empreinte:
        if enregistrement.erreur is None:
            enregistrement.statut = Statut.INCHANGE
        return _terminer(contexte, enregistrement), contenu

    chemin = chemin_archive(contexte.racine, entree, debut, enregistrement.sha256)
    try:
        ecrire_archive(chemin, contenu, debut)
    except ArchiveExistante:
        enregistrement.erreur = MOTIF_ARCHIVE_EXISTANTE
    except OSError as exc:
        enregistrement.erreur = f"ecriture: {exc}"
    else:
        enregistrement.chemin_archive = chemin.relative_to(contexte.racine).as_posix()
        if enregistrement.erreur is None:
            enregistrement.statut = Statut.NOUVEAU
    return _terminer(contexte, enregistrement), contenu


def _terminer(contexte: _Contexte, enregistrement: Enregistrement) -> Enregistrement:
    enregistrement.fin = contexte.maintenant().isoformat()
    return enregistrement


def _marquer_inattendue(
    contexte: _Contexte, entree: Entree, enregistrement: Enregistrement | None, exc: BaseException
) -> Enregistrement:
    """La ligne d'une entrée dont le traitement a levé une exception imprévue.

    Si ``_collecter`` avait déjà produit sa ligne (archive écrite, puis page
    illisible par exemple), elle est gardée et passe en erreur, motif
    enchaîné ; sinon une ligne minimale est créée. La trace est dans le journal.
    """
    motif = f"{MOTIF_INATTENDUE}: {type(exc).__name__}: {exc}".strip(": ")
    if enregistrement is None:
        instant = contexte.maintenant().isoformat()
        enregistrement = Enregistrement(
            passage_id=contexte.passage_id,
            identifiant=entree.identifiant,
            source=entree.source,
            fichier=entree.fichier,
            url=entree.url,
            debut=instant,
            fin=instant,
            statut=Statut.ERREUR,
            version_collecteur=contexte.version,
        )
    enregistrement.statut = Statut.ERREUR
    enregistrement.erreur = " ; ".join(filter(None, (enregistrement.erreur, motif)))
    return _terminer(contexte, enregistrement)


def _consigner(contexte: _Contexte, bilan: Bilan, enregistrement: Enregistrement) -> None:
    manifeste.ajouter(contexte.racine, enregistrement)
    bilan.enregistrements.append(enregistrement)
    detail = enregistrement.erreur or enregistrement.chemin_archive or ""
    journal.info("%s : %s %s", enregistrement.fichier, enregistrement.statut, detail)


def _collectee_ce_jour(
    anterieurs: list[Enregistrement], entree: Entree, debut_passage: datetime
) -> bool:
    jour = debut_passage.strftime("%Y-%m-%d")
    return any(
        e.identifiant == entree.identifiant
        and e.statut != Statut.ERREUR
        and e.debut.startswith(jour)
        for e in anterieurs
    )


def _liens_par_url(contenu: bytes) -> dict[str, LienTelechargement] | None:
    try:
        return {lien.url: lien for lien in analyser_page(contenu)}
    except AnalyseImpossible:
        return None


def _appliquer_page(enregistrement: Enregistrement, lien: LienTelechargement | None) -> None:
    """Reporte la date et la taille affichées ; signale un lien que la page n'a plus.

    Une erreur déjà présente (``HTTP 404``…) n'est pas écrasée : les motifs
    s'enchaînent (``HTTP 404 ; lien_absent``).
    """
    if lien is None:
        enregistrement.statut = Statut.ERREUR
        enregistrement.erreur = " ; ".join(filter(None, (enregistrement.erreur, MOTIF_LIEN_ABSENT)))
        return
    enregistrement.date_source_affichee = lien.date_affichee
    enregistrement.taille_affichee_ko = lien.taille_affichee_ko


def _liens_nouveaux(liens_page: dict[str, LienTelechargement]) -> list[LienTelechargement]:
    connus = entrees_bdpm_par_url()
    return [
        lien
        for url, lien in liens_page.items()
        if url not in connus and lien.est_fichier_de_donnees
    ]


def _enregistrement_lien_nouveau(contexte: _Contexte, lien: LienTelechargement) -> Enregistrement:
    instant = contexte.maintenant().isoformat()
    return Enregistrement(
        passage_id=contexte.passage_id,
        identifiant=None,
        source="bdpm",
        fichier=lien.nom,
        url=lien.url,
        debut=instant,
        fin=instant,
        statut=Statut.ERREUR,
        version_collecteur=contexte.version,
        date_source_affichee=lien.date_affichee,
        taille_affichee_ko=lien.taille_affichee_ko,
        erreur=f"{MOTIF_LIEN_NOUVEAU}: {lien.libelle}",
    )
