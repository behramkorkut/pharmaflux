"""Du bronze aux événements : rejeu complet, reprise, sortie par archive, état (ADR 0006).

Pour chaque fichier source, les archives sont lues dans l'ordre du bronze,
chacune passe par le garde-fou de volume (``volume.Suivi``), et chaque
archive lue laisse sur le disque :

- ``<sortie>/evenements/<entite>/<horodatage>__<sha12>.jsonl`` quand elle est
  retenue ou confirmée (vide quand rien n'a changé : la preuve qu'elle a été
  comparée) ;
- ``<sortie>/bilans/<entite>/<horodatage>__<sha12>.json`` toujours, réécrit
  quand une archive en attente est tranchée ;
- ``<sortie>/etat.json`` après les fichiers de l'archive, dans l'ordre
  événements, bilan, état, chaque fichier écrit sous un nom temporaire puis
  renommé ; les événements y sont écrits **ligne à ligne**, au fil de la
  comparaison, sans jamais tenir en mémoire plus d'un événement à la fois
  (mission 03, palier 1).

Le flux d'une source est la concaténation de ses fichiers d'événements dans
l'ordre des noms. La reprise lit l'état, recalcule le dernier snapshot retenu
(et celui en attente) **depuis leur archive**, et ne traite que les archives
postérieures à la dernière traitée : la dernière dont le verdict est
définitif (retenue, confirmée ou écartée), ce qui peut être l'archive en
attente que la dernière archive lue a tranchée, quand celle-ci est à son tour
en attente. Rien ne vient de l'horloge : les dates viennent des noms
d'archive et du manifeste.
"""

from __future__ import annotations

import gzip
import json
import shutil
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pharmaflux import bronze
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.manifeste import Enregistrement, Statut
from pharmaflux.contrats.modele import Contrat
from pharmaflux.evenements import bilan as bilans
from pharmaflux.evenements import schema, snapshot
from pharmaflux.evenements.schema import Evenement
from pharmaflux.evenements.snapshot import Snapshot
from pharmaflux.evenements.volume import Decision, Resultat, Suivi

VERSION_ETAT = 1
NOM_ETAT = "etat.json"
DOSSIER_EVENEMENTS = "evenements"
DOSSIER_BILANS = "bilans"
Journal = Callable[[str], None]


class ReprendreImpossible(Exception):  # noqa: N818 (nom français voulu)
    """La reprise ne peut pas donner la sortie d'un rejeu complet, ou ``etat.json`` est
    illisible (dans les deux modes, puisqu'un rejeu complet le relit pour garder les autres
    entités) : le message dit quoi faire, et rien n'est effacé."""


@dataclass(frozen=True, slots=True)
class EtatEntite:
    """Ce que ``etat.json`` garde par entité ; les snapshots eux-mêmes ne sont jamais sérialisés."""

    version_contrat: str
    derniere_archive_traitee: str | None  # chemin relatif ; reste avant un snapshot en attente
    dernier_retenu: str | None  # chemin relatif de l'archive du dernier snapshot retenu
    en_attente: str | None  # chemin relatif de l'archive en attente, ou None


@dataclass(slots=True)
class ResumeEntite:
    """Ce que le terminal résume pour un fichier."""

    identifiant: str
    fichier: str
    archives_lues: int = 0
    retenues: int = 0  # retenues ou confirmées
    ecartees: int = 0
    en_attente: int = 0  # encore en attente à la fin
    evenements: Counter[str] = field(default_factory=Counter)
    erreur: str | None = None


@dataclass(slots=True)
class Rapport:
    resumes: list[ResumeEntite]

    @property
    def code_sortie(self) -> int:
        """1 si une archive est illisible ; un snapshot écarté est un constat, pas une panne."""
        return 1 if any(resume.erreur for resume in self.resumes) else 0


def executer(
    racine: Path,
    sortie: Path,
    contrats: dict[str, Contrat],
    selection: list[str],
    *,
    reprendre: bool = False,
    journal: Journal | None = None,
) -> Rapport:
    """Rejeu complet des fichiers de ``selection``, ou reprise depuis ``etat.json``.

    ``--reprendre`` refuse quand une version de contrat diffère de celle de
    l'état (``ReprendreImpossible``) : les événements déjà écrits auraient une
    autre forme que les suivants.
    """
    dire = journal or (lambda _: None)
    etats = _lire_etat(sortie) if reprendre else {}
    if reprendre:
        for identifiant in selection:
            etat = etats.get(identifiant)
            if etat is not None and etat.version_contrat != contrats[identifiant].version:
                raise ReprendreImpossible(
                    f"le contrat {identifiant} est passé de {etat.version_contrat} à"
                    f" {contrats[identifiant].version} : relance sans --reprendre"
                )
    manifeste_ = _Manifeste.lire(racine, set(selection))
    resumes = []
    for identifiant in selection:
        contrat = contrats[identifiant]
        etat = etats.get(identifiant) if reprendre else None
        resumes.append(_traiter_entite(racine, sortie, contrat, etat, manifeste_, dire))
    return Rapport(resumes)


def _traiter_entite(
    racine: Path,
    sortie: Path,
    contrat: Contrat,
    etat: EtatEntite | None,
    manifeste_: _Manifeste,
    dire: Journal,
) -> ResumeEntite:
    identifiant = contrat.identifiant
    resume = ResumeEntite(identifiant, contrat.fichier)
    archives = bronze.lister(racine, _source(identifiant), contrat.fichier)
    par_chemin = {archive.relatif(racine): archive for archive in archives}
    suivi = Suivi()
    debut = 0
    if etat is None:
        # Rejeu complet : tout est recalculé, la sortie de l'entité repart de zéro.
        # L'entité quitte d'abord l'état, puis ses dossiers sont effacés : une coupure
        # entre les deux laisse une entité sans état, que --reprendre rejoue en entier.
        _retirer_etat(sortie, identifiant)
        for dossier in (DOSSIER_EVENEMENTS, DOSSIER_BILANS):
            shutil.rmtree(sortie / dossier / identifiant, ignore_errors=True)
    else:
        suivi.retenu = _recalculer(contrat, racine, par_chemin, etat.dernier_retenu)
        suivi.en_attente = _recalculer(contrat, racine, par_chemin, etat.en_attente)
        if suivi.en_attente is not None:
            suivi.date_source_en_attente = manifeste_.date_source(etat.en_attente)
        if etat.derniere_archive_traitee is not None:
            if etat.derniere_archive_traitee not in par_chemin:
                raise ReprendreImpossible(
                    f"{identifiant} : la dernière archive traitée"
                    f" ({etat.derniere_archive_traitee}) n'est plus dans le bronze :"
                    " relance sans --reprendre"
                )
            debut = list(par_chemin).index(etat.derniere_archive_traitee) + 1
        dire(f"{identifiant} : reprise après {etat.derniere_archive_traitee or 'rien'}")
    derniere_traitee = etat.derniere_archive_traitee if etat else None
    for archive in archives[debut:]:
        relatif = archive.relatif(racine)
        if suivi.en_attente is not None and relatif == suivi.en_attente.archive:
            continue  # déjà lue, en attente : c'est l'archive suivante qui la tranche
        derniere_traitee = _traiter_archive(
            sortie, contrat, suivi, archive, relatif, manifeste_, resume, derniere_traitee, dire
        )
        if resume.erreur is not None:
            break
    if suivi.en_attente is not None and resume.erreur is None:
        inchange_revu = manifeste_.inchange_revu(
            identifiant, suivi.en_attente.archive, suivi.en_attente.horodatage, None
        )
        for resultat in suivi.clore(inchange_revu=inchange_revu):
            _ecrire_resultat(sortie, resultat, resume, dire)
            if resultat.verdict.decision is not Decision.EN_ATTENTE:
                derniere_traitee = resultat.snapshot.archive
        _ecrire_etat(sortie, identifiant, contrat, suivi, derniere_traitee)
    resume.en_attente = 1 if suivi.en_attente is not None else 0
    return resume


def _traiter_archive(
    sortie: Path,
    contrat: Contrat,
    suivi: Suivi,
    archive: bronze.Archive,
    relatif: str,
    manifeste_: _Manifeste,
    resume: ResumeEntite,
    derniere_traitee: str | None,
    dire: Journal,
) -> str | None:
    """Une archive : lue, passée au garde-fou, ses résultats et l'état écrits.

    Rend la dernière archive traitée. Tout ce qui est lu ou produit ici meurt
    au retour : quand l'archive suivante est lue, seuls le dernier retenu et
    le snapshot en attente sont encore en mémoire (mission 03, palier 1).
    """
    identifiant = contrat.identifiant
    try:
        nouveau = _lire_snapshot(contrat, archive, relatif)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        resume.erreur = f"{relatif} : archive illisible ({exc})"
        dire(resume.erreur)
        return derniere_traitee
    resume.archives_lues += 1
    inchange_revu = suivi.en_attente is not None and manifeste_.inchange_revu(
        identifiant, suivi.en_attente.archive, suivi.en_attente.horodatage, archive.horodatage
    )
    resultats = suivi.traiter(
        nouveau, date_source=manifeste_.date_source(relatif), inchange_revu=inchange_revu
    )
    for resultat in resultats:
        _ecrire_resultat(sortie, resultat, resume, dire)
        # Chaque verdict définitif avance la dernière archive traitée : celui de l'archive en
        # attente que cette archive tranche, puis le sien s'il ne la met pas elle-même en
        # attente. Ne regarder que le dernier résultat laisserait la reprise relire une archive
        # déjà traitée, et effacer ses événements (relecture 1).
        if resultat.verdict.decision is not Decision.EN_ATTENTE:
            derniere_traitee = resultat.snapshot.archive
    _ecrire_etat(sortie, identifiant, contrat, suivi, derniere_traitee)
    return derniere_traitee


def _lire_snapshot(contrat: Contrat, archive: bronze.Archive, relatif: str) -> Snapshot:
    """Lit et construit dans la même fonction : les octets et la lecture meurent au retour."""
    return snapshot.construire(contrat, archive.lire(), relatif, archive.horodatage)


def _recalculer(
    contrat: Contrat, racine: Path, par_chemin: dict[str, bronze.Archive], chemin: str | None
) -> Snapshot | None:
    """Le snapshot d'une archive de l'état, relu depuis le bronze : jamais sérialisé."""
    if chemin is None:
        return None
    archive = par_chemin.get(chemin)
    if archive is None:
        raise ReprendreImpossible(
            f"{contrat.identifiant} : l'archive {chemin} de l'état n'est plus dans le bronze :"
            " relance sans --reprendre"
        )
    return snapshot.lire(contrat, archive, racine)


def _ecrire_resultat(sortie: Path, resultat: Resultat, resume: ResumeEntite, dire: Journal) -> None:
    """Les événements (si comparé) puis le bilan d'une archive, chacun écrit puis renommé."""
    s = resultat.snapshot
    nom = Path(s.archive).name.removesuffix(".gz")
    nom = nom[: nom.index(".")] if "." in nom else nom  # <horodatage>__<sha12>
    entite = s.contrat.identifiant
    decision = resultat.verdict.decision
    comptes: Counter[str] = Counter()
    if resultat.verdict.compare:
        chemin = sortie / DOSSIER_EVENEMENTS / entite / f"{nom}.jsonl"
        comptes = _ecrire_evenements(chemin, resultat.evenements())
        resume.retenues += 1
        resume.evenements.update(comptes)
    elif decision is Decision.ECARTE:
        resume.ecartees += 1
    bilan = bilans.en_dict(bilans.etablir(resultat, comptes))
    contenu = json.dumps(bilan, sort_keys=True, ensure_ascii=False, indent=2)
    _ecrire(sortie / DOSSIER_BILANS / entite / f"{nom}.json", contenu + "\n")
    types = ", ".join(f"{t} {n}" for t, n in sorted(comptes.items()))
    suffixe = f" ; {types}" if types else ""
    dire(f"{entite} {nom} : {decision.value} ({resultat.verdict.motif}){suffixe}")


def _ecrire_evenements(chemin: Path, evenements: Iterable[Evenement]) -> Counter[str]:
    """Écrit les événements ligne à ligne sous un nom temporaire, puis renomme ; rend les comptes.

    Chaque événement est sérialisé et écrit dès qu'il est produit, puis
    oublié : la mémoire ne dépend pas du nombre d'événements. Le fichier
    existe même vide (une comparaison sans changement), et une coupure laisse
    un ``.partiel`` que ``lire_evenements`` ignore.
    """
    comptes: Counter[str] = Counter()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.parent / f".{chemin.name}.partiel"
    with temporaire.open("w", encoding="utf-8") as flux:
        for evenement in evenements:
            flux.write(schema.serialiser(evenement))
            comptes[evenement.type.value] += 1
    temporaire.replace(chemin)
    return comptes


def _ecrire(chemin: Path, contenu: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.parent / f".{chemin.name}.partiel"
    temporaire.write_text(contenu, encoding="utf-8")
    temporaire.replace(chemin)


def _ecrire_etat(
    sortie: Path, identifiant: str, contrat: Contrat, suivi: Suivi, derniere_traitee: str | None
) -> None:
    """Réécrit ``etat.json`` entier, l'entité mise à jour, les autres conservées."""
    etats = _lire_etat(sortie)
    etats[identifiant] = EtatEntite(
        version_contrat=contrat.version,
        derniere_archive_traitee=derniere_traitee,
        dernier_retenu=None if suivi.retenu is None else suivi.retenu.archive,
        en_attente=None if suivi.en_attente is None else suivi.en_attente.archive,
    )
    _sauver_etats(sortie, etats)


def _retirer_etat(sortie: Path, identifiant: str) -> None:
    """Réécrit ``etat.json`` sans l'entité, avant que le rejeu complet efface sa sortie."""
    etats = _lire_etat(sortie)
    if etats.pop(identifiant, None) is not None:
        _sauver_etats(sortie, etats)


def _sauver_etats(sortie: Path, etats: dict[str, EtatEntite]) -> None:
    contenu = {
        "version": VERSION_ETAT,
        "entites": {
            ident: {
                "version_contrat": e.version_contrat,
                "derniere_archive_traitee": e.derniere_archive_traitee,
                "dernier_retenu": e.dernier_retenu,
                "en_attente": e.en_attente,
            }
            for ident, e in sorted(etats.items())
        },
    }
    _ecrire(sortie / NOM_ETAT, json.dumps(contenu, sort_keys=True, indent=2) + "\n")


def _lire_etat(sortie: Path) -> dict[str, EtatEntite]:
    chemin = sortie / NOM_ETAT
    if not chemin.is_file():
        return {}
    conseil = f"supprime {NOM_ETAT} ou choisis une autre sortie"
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
        if brut["version"] != VERSION_ETAT:
            raise ReprendreImpossible(
                f"{chemin} : version {brut['version']}, attendu {VERSION_ETAT} : {conseil}"
            )
        return {
            ident: EtatEntite(
                version_contrat=e["version_contrat"],
                derniere_archive_traitee=e["derniere_archive_traitee"],
                dernier_retenu=e["dernier_retenu"],
                en_attente=e["en_attente"],
            )
            for ident, e in brut["entites"].items()
        }
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ReprendreImpossible(f"{chemin} : état illisible ({exc!r}) : {conseil}") from exc


@dataclass(slots=True)
class _Manifeste:
    """Ce que le rejeu prend au manifeste : la date source par archive, les passages inchangés."""

    nouveaux: dict[str, Enregistrement]  # chemin_archive → ligne ``nouveau``
    inchanges: dict[str, list[tuple[str, datetime]]]  # identifiant → (empreinte, fin du passage)

    @classmethod
    def lire(cls, racine: Path, identifiants: set[str]) -> _Manifeste:
        nouveaux: dict[str, Enregistrement] = {}
        inchanges: dict[str, list[tuple[str, datetime]]] = {}
        for ligne in manifeste.parcourir(racine):
            if ligne.identifiant not in identifiants:
                continue
            if ligne.statut == Statut.NOUVEAU and ligne.chemin_archive:
                nouveaux.setdefault(ligne.chemin_archive, ligne)
            elif ligne.statut == Statut.INCHANGE and ligne.empreinte_comparaison:
                inchanges.setdefault(ligne.identifiant, []).append(
                    (ligne.empreinte_comparaison, _instant(ligne.fin))
                )
        return cls(nouveaux, inchanges)

    def date_source(self, chemin_archive: str | None) -> str | None:
        if chemin_archive is None:
            return None
        ligne = self.nouveaux.get(chemin_archive)
        return ligne.date_source_affichee if ligne else None

    def inchange_revu(
        self, identifiant: str, chemin_archive: str, depuis: datetime | None, avant: datetime | None
    ) -> bool:
        """Un passage ``inchange`` a revu l'empreinte de l'archive entre ``depuis`` et ``avant``.

        Entre son archivage et l'archive suivante (ou la fin du manifeste) : au
        delà, un ``inchange`` compare à l'archive suivante, pas à celle-ci.
        """
        ligne = self.nouveaux.get(chemin_archive)
        if ligne is None or not ligne.empreinte_comparaison or depuis is None:
            return False
        attendue = ligne.empreinte_comparaison
        return any(
            empreinte == attendue and depuis < fin and (avant is None or fin < avant)
            for empreinte, fin in self.inchanges.get(identifiant, [])
        )


def _instant(iso: str) -> datetime:
    instant = datetime.fromisoformat(iso)
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def _source(identifiant: str) -> str:
    return identifiant.partition(".")[0]


def entites_suivies(sortie: Path) -> frozenset[str]:
    """Les entités qu'``etat.json`` connaît ; vide sans fichier, ``ReprendreImpossible`` s'il est
    illisible. Pour ``verifier-bus --racine`` : une entité absente n'a pas de référence."""
    return frozenset(_lire_etat(sortie))


def dernier_retenu(racine: Path, sortie: Path, contrat: Contrat) -> Snapshot | None:
    """Le dernier snapshot retenu d'une entité d'après ``etat.json``, relu depuis le bronze.

    Pour ``verifier-bus --racine`` : la seconde référence, indépendante des
    fichiers d'événements. None sans état pour l'entité, ou sans snapshot retenu.
    """
    etat = _lire_etat(sortie).get(contrat.identifiant)
    if etat is None:
        return None
    archives = bronze.lister(racine, _source(contrat.identifiant), contrat.fichier)
    par_chemin = {archive.relatif(racine): archive for archive in archives}
    return _recalculer(contrat, racine, par_chemin, etat.dernier_retenu)


def lire_evenements(sortie: Path, identifiant: str) -> Iterator[Evenement]:
    """Le flux d'une entité : ses fichiers d'événements dans l'ordre des noms, ligne à ligne."""
    dossier = sortie / DOSSIER_EVENEMENTS / identifiant
    if not dossier.is_dir():
        return
    for fichier in sorted(dossier.glob("*.jsonl")):
        with fichier.open(encoding="utf-8") as flux:
            for ligne in flux:
                if ligne.strip():
                    yield schema.deserialiser(ligne)
