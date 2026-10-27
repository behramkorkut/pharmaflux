"""Le rejeu accéléré de la démo (mission 04) : ``pharmaflux demo rejouer``.

La commande rejoue une archive (le jeu figé ``demo/archive`` par défaut) sur
le bus, dans l'**ordre global des observations** et à une cadence accélérée :

1. le courtier et le registre répondent (comme ``publier`` : code 1 sans
   courtier, 2 sans schéma enregistré) ;
2. le bus et la sortie sont dans l'état attendu (table plus bas) ;
3. ``rejeu.executer`` (le code de ``evenements``) écrit les fichiers
   d'événements et les bilans dans la sortie : ils restent la référence, il
   n'y a pas de second chemin de calcul ;
4. l'ordre global est construit : une entrée par bilan (chaque archive lue
   en laisse un, écartée ou non), triée par (horodatage de l'archive,
   entité), et, sauf ``sans_passages``, une entrée par passage du manifeste
   sans archive nouvelle pour les entités rejouées ;
5. chaque entrée attend son instant sur l'horloge de la démo, est affichée,
   et son fichier d'événements est publié par le code de ``publier``
   (``publication.publier_fichier``, le même ``publication.json``) ;
6. le résumé.

**L'horloge.** Pour une entrée observée à ``t_obs``, l'instant réel visé est
``t_reel_depart + (t_obs - t_obs_premiere) / facteur`` ; la commande dort
jusqu'à lui, jamais d'une durée négative : une publication plus longue que
la pause enchaîne, et l'horloge rattrape. Au facteur 1 000, une heure
observée dure 3,6 s et un jour 86 s. ``sans_pause`` (la CI) n'attend jamais.

**L'ordre par topic est celui de ``publier``** : le nom d'un fichier commence
par l'horodatage de son archive, donc l'ordre global restreint à une entité
est l'ordre des noms. Seul l'entrelacement entre topics change, et il ne
compte pour personne. Un rejeu interrompu se reprend avec ``reprendre`` :
``evenements --reprendre`` (rien de neuf sur un jeu figé), puis les fichiers
absents de l'état, le fichier coupé en entier (ses doublons sont ceux de la
mission 03, même ``id``).

**Un bus qui n'est pas dans l'état attendu est refusé, code 2, avant toute
publication** (``DemoRefusee``), avec la voie de retour :

=================== =================== ====================== ==============
topics de la démo    ``publication.json`` sans ``reprendre``     avec
=================== =================== ====================== ==============
aucun               absent              rejeu complet          rejeu complet
présents            présent             refus : ``make rebatir`` reprise
présents            absent              refus : ``make rebatir`` refus
aucun               présent             refus : ``make rebatir`` refus
=================== =================== ====================== ==============

Les « topics de la démo » sont exactement ceux qu'elle publierait : un par
entité rejouée, plus la file des échecs. Les topics des tests d'intégration
(``pharmaflux.test-<suffixe>.…``, effacés à la fin de chaque test, parfois
encore visibles juste après) ne comptent pas. La cohérence de l'état
(fichier publié disparu ou modifié, fichier hors d'ordre) reste le contrôle
de ``publication.preparer``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pharmaflux.bronze import FORMAT_HORODATAGE
from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import publication
from pharmaflux.bus.client import Bus
from pharmaflux.bus.registre import Registre
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.manifeste import Statut
from pharmaflux.contrats.modele import Contrat
from pharmaflux.evenements import rejeu
from pharmaflux.evenements.rejeu import DOSSIER_BILANS, DOSSIER_EVENEMENTS
from pharmaflux.evenements.volume import Decision

FACTEUR_PAR_DEFAUT = 1000
SORTIE_PAR_DEFAUT = Path("data/demo")  # sous data/, hors git ; jamais sous la racine rejouée
Journal = Callable[[str], None]
LARGEUR_ENTITE = 28


class DemoRefusee(Exception):  # noqa: N818 (nom français voulu)
    """Le bus ou la sortie ne sont pas dans l'état attendu (code 2) : rien n'est publié, le
    message donne la voie de retour (``make rebatir``)."""


class DemoInterrompue(Exception):  # noqa: N818 (nom français voulu)
    """Le rejeu des événements s'est arrêté sur une archive illisible (code 1)."""


@dataclass(frozen=True, slots=True)
class Entree:
    """Une entrée de l'ordre global : une archive lue (son bilan), ou un passage sans archive."""

    instant: datetime  # horodatage de l'archive, ou du passage
    entite: str  # vide pour un passage
    nom: str | None  # <horodatage>__<sha12> ; None pour un passage
    decision: Decision | None  # None pour un passage
    motif: str
    etat_initial: bool  # premier snapshot retenu de l'entité : tous ses événements sont creee
    evenements: tuple[tuple[str, int], ...]  # type → nombre, d'après le bilan
    fichier: str | None  # chemin relatif du fichier d'événements à publier, s'il existe
    fichiers_revus: int = 0  # passage : fichiers des entités rejouées revus sans changement

    @property
    def est_passage(self) -> bool:
        return self.nom is None


@dataclass(slots=True)
class Resume:
    archives: int = 0  # bilans déroulés
    publies: int = 0  # fichiers publiés par cette exécution
    deja_publies: int = 0  # fichiers déjà dans l'état (reprise)
    ecartees: int = 0
    en_attente: int = 0
    passages: int = 0  # passages sans archive affichés
    messages: dict[str, int] = field(default_factory=dict)  # par topic, cette exécution
    echecs: int = 0
    premiere_observation: datetime | None = None
    derniere_observation: datetime | None = None
    duree_rejeu_s: float = 0.0  # evenements
    duree_reelle_s: float = 0.0  # le déroulé, pauses et publications
    facteur: float = FACTEUR_PAR_DEFAUT
    etat: Path | None = None

    @property
    def code_sortie(self) -> int:
        """Ceux de ``publier`` : 3 si la file des échecs a reçu au moins un message, 0 sinon."""
        return 3 if self.echecs else 0


def executer(
    racine: Path,
    sortie: Path,
    contrats: dict[str, Contrat],
    selection: list[str],
    bus: Bus,
    registre: Registre,
    *,
    reprendre: bool = False,
    facteur: float = FACTEUR_PAR_DEFAUT,
    sans_pause: bool = False,
    sans_passages: bool = False,
    prefixe: str = env.PREFIXE_PAR_DEFAUT,
    maintenant: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    journal: Journal | None = None,
) -> Resume:
    """Rejoue ``racine`` vers ``sortie`` et sur le bus, dans l'ordre global, à la cadence.

    ``maintenant`` (secondes monotones) et ``dormir`` sont injectables : les
    tests vérifient les instants visés sans dormir. ``facteur`` doit être
    strictement positif.
    """
    if facteur <= 0:
        raise ValueError(f"facteur {facteur} : un nombre strictement positif est attendu")
    dire = journal or (lambda _: None)
    topics_du_courtier = bus.verifier_courtier()
    publication.identifiants_de_schema(registre, selection, prefixe)
    verifier_etat_du_bus(topics_du_courtier, sortie, selection, prefixe, reprendre=reprendre)
    resume = Resume(facteur=facteur, etat=sortie / publication.NOM_PUBLICATION)

    debut_rejeu = maintenant()
    rapport = rejeu.executer(racine, sortie, contrats, selection, reprendre=reprendre)
    resume.duree_rejeu_s = maintenant() - debut_rejeu
    lues = sum(r.archives_lues for r in rapport.resumes)
    dire(
        f"rejeu de {racine} : {lues} archive(s) lue(s) pour {len(selection)} entité(s)"
        f" en {resume.duree_rejeu_s:.1f} s ; sortie : {sortie}"
    )
    if rapport.code_sortie:
        erreurs = " ; ".join(f"{r.identifiant} : {r.erreur}" for r in rapport.resumes if r.erreur)
        raise DemoInterrompue(f"archive illisible, rien n'est publié : {erreurs}")

    preparation = publication.preparer(sortie, bus, registre, reprendre=reprendre, prefixe=prefixe)
    entrees = ordre_global(racine, sortie, selection, preparation, sans_passages=sans_passages)
    resume.deja_publies = sum(len(publies) for publies in preparation.etat.values())
    if not entrees:
        dire("rien à rejouer : tous les fichiers sont dans l'état")
    debut_reel = maintenant()
    premiere = entrees[0].instant if entrees else None
    for entree in entrees:
        if not sans_pause and premiere is not None:
            cible = debut_reel + (entree.instant - premiere).total_seconds() / facteur
            attente = cible - maintenant()
            if attente > 0:
                dormir(attente)
        dire(_derouler(entree, preparation, bus, resume, maintenant))
    resume.duree_reelle_s = maintenant() - debut_reel
    rapport_publication = preparation.rapport()
    resume.messages = dict(rapport_publication.topics)
    resume.echecs = sum(r.echecs for r in rapport_publication.resumes)
    if entrees:
        resume.premiere_observation = entrees[0].instant
        resume.derniere_observation = entrees[-1].instant
    return resume


def verifier_etat_du_bus(
    topics_du_courtier: list[str],
    sortie: Path,
    selection: list[str],
    prefixe: str,
    *,
    reprendre: bool,
) -> None:
    """La table du module : refus (``DemoRefusee``) de tout état autre qu'un bus vide sans état,
    ou qu'un bus publié avec son état quand on reprend. Seuls comptent les topics exacts que la
    démo publierait (``topics_de_la_demo``) : ceux des tests d'intégration ne font pas refuser."""
    attendus = set(topics_de_la_demo(selection, prefixe))
    du_projet = sorted(t for t in topics_du_courtier if t in attendus)
    chemin_etat = sortie / publication.NOM_PUBLICATION
    etat = publication.lire_etat(chemin_etat)  # illisible : PublicationRefusee, code 2
    if du_projet and etat:
        if reprendre:
            return
        raise DemoRefusee(
            f"le bus a déjà reçu une publication ({len(du_projet)} topic(s) de la démo sur le"
            f" courtier, état {chemin_etat}) : pour rejouer la démo depuis le début, rebâtis le"
            " bus et la sortie (make rebatir) ; pour continuer un rejeu interrompu, relance"
            " avec --reprendre"
        )
    if du_projet:
        raise DemoRefusee(
            f"bus non vide sans état : {len(du_projet)} topic(s) de la démo sur le courtier"
            f" ({du_projet[0]}…) et pas de {chemin_etat} ; un événement publié n'est jamais"
            " réécrit : rebâtis le bus (make rebatir)"
        )
    if etat:
        raise DemoRefusee(
            f"état sans bus : {chemin_etat} existe mais le courtier n'a aucun topic de la démo ;"
            f" supprime la sortie {sortie} (make rebatir)"
        )


def topics_de_la_demo(selection: list[str], prefixe: str) -> list[str]:
    """Les topics que la démo publierait : un par entité sélectionnée, puis la file des échecs."""
    return [env.nom_topic(entite, prefixe) for entite in selection] + [env.topic_echecs(prefixe)]


def ordre_global(
    racine: Path,
    sortie: Path,
    selection: list[str],
    preparation: publication.Preparation,
    *,
    sans_passages: bool = False,
) -> list[Entree]:
    """Les entrées à dérouler, triées par (instant, entité).

    Une par bilan de la sortie pour les entités de ``selection``, avec son
    fichier d'événements s'il existe ; une par passage du manifeste de la
    racine sans archive nouvelle pour ces entités, sauf ``sans_passages``. En
    reprise, les bilans dont le fichier est déjà publié sont écartés, et avec
    eux tout ce qui précède le premier fichier à publier.
    """
    presents = {chemin for _, chemin in preparation.fichiers}
    a_publier = {chemin for _, chemin in preparation.a_publier}
    entrees: list[Entree] = []
    deja: list[datetime] = []
    for entite in selection:
        for chemin_bilan in sorted((sortie / DOSSIER_BILANS / entite).glob("*.json")):
            entree = _entree_du_bilan(entite, chemin_bilan, presents)
            if entree.fichier is not None and entree.fichier not in a_publier:
                deja.append(entree.instant)
                continue
            entrees.append(entree)
    if not sans_passages:
        entrees.extend(_passages_sans_archive(racine, set(selection)))
    entrees.sort(key=lambda e: (e.instant, e.entite))
    if deja:
        premier = min((e.instant for e in entrees if e.fichier is not None), default=None)
        if premier is None:
            return []
        entrees = [e for e in entrees if e.instant >= premier]
    return entrees


def _entree_du_bilan(entite: str, chemin_bilan: Path, presents: set[str]) -> Entree:
    bilan = json.loads(chemin_bilan.read_text(encoding="utf-8"))
    nom = chemin_bilan.stem  # <horodatage>__<sha12>
    fichier = f"{DOSSIER_EVENEMENTS}/{entite}/{nom}.jsonl"
    ecart = bilan.get("ecart")
    evenements: dict[str, int] = {} if ecart is None else dict(ecart.get("evenements", {}))
    return Entree(
        instant=_instant(nom.partition("__")[0]),
        entite=entite,
        nom=nom,
        decision=Decision(str(bilan["decision"])),
        motif=str(bilan.get("motif", "")),
        etat_initial=ecart is None,
        evenements=tuple(sorted(evenements.items())),
        fichier=fichier if fichier in presents else None,
    )


def _passages_sans_archive(racine: Path, voulus: set[str]) -> list[Entree]:
    """Un passage du manifeste (``passage_id``) sans ligne ``nouveau`` pour les entités voulues."""
    nouveaux: set[str] = set()
    revus: dict[str, int] = {}
    for ligne in manifeste.parcourir(racine):
        if ligne.identifiant not in voulus:
            continue
        if ligne.statut == Statut.NOUVEAU:
            nouveaux.add(ligne.passage_id)
        elif ligne.statut in (Statut.INCHANGE, Statut.NON_MODIFIE_304):
            revus[ligne.passage_id] = revus.get(ligne.passage_id, 0) + 1
        else:
            revus.setdefault(ligne.passage_id, 0)
    return [
        Entree(
            instant=_instant(passage_id),
            entite="",
            nom=None,
            decision=None,
            motif="",
            etat_initial=False,
            evenements=(),
            fichier=None,
            fichiers_revus=nombre,
        )
        for passage_id, nombre in sorted(revus.items())
        if passage_id not in nouveaux
    ]


def _instant(horodatage: str) -> datetime:
    return datetime.strptime(horodatage, FORMAT_HORODATAGE).replace(tzinfo=UTC)


def _derouler(
    entree: Entree,
    preparation: publication.Preparation,
    bus: Bus,
    resume: Resume,
    maintenant: Callable[[], float],
) -> str:
    """Publie le fichier de l'entrée s'il y en a un, tient le résumé, rend la ligne à afficher."""
    if entree.est_passage:
        resume.passages += 1
        return (
            f"{entree.instant:%d/%m %H:%M}     {'passage':{LARGEUR_ENTITE}} "
            f"{entree.fichiers_revus} fichier(s) revu(s) sans changement, rien de neuf"
        )
    resume.archives += 1
    debut = f"{entree.instant:%d/%m %H:%M:%S}  {entree.entite:{LARGEUR_ENTITE}} "
    if entree.fichier is None:
        if entree.decision is Decision.ECARTE:
            resume.ecartees += 1
            return f"{debut}snapshot écarté : {entree.motif} (rien publié)"
        if entree.decision is Decision.EN_ATTENTE:
            resume.en_attente += 1
            return f"{debut}en attente : {entree.motif} (rien publié)"
        return f"{debut}{entree.decision} : {entree.motif} (pas de fichier d'événements)"
    depart = maintenant()
    publie = publication.publier_fichier(preparation, bus, entree.entite, entree.fichier)
    duree = maintenant() - depart
    resume.publies += 1
    topic = env.nom_topic(entree.entite, preparation.prefixe)
    if entree.etat_initial:
        texte = f"état initial : creee {publie.messages}"
    elif entree.evenements:
        texte = ", ".join(f"{type_} {nombre}" for type_, nombre in entree.evenements)
    else:  # retenu sans événement : le motif sans l'archive citée, que le bilan garde
        texte = f"{entree.decision} : {entree.motif.partition(' (')[0]}, 0 événement"
    echecs = f", {publie.echecs} en échec" if publie.echecs else ""
    return f"{debut}{texte} → {topic} ({publie.messages} message(s), {duree:.1f} s{echecs})"


def formater_resume(resume: Resume) -> list[str]:
    """Les lignes du résumé de fin, dans l'ordre d'affichage."""
    lignes = [
        f"rejeu : {resume.archives} archive(s) déroulée(s), {resume.publies} fichier(s)"
        f" publié(s) ({resume.deja_publies} déjà), {resume.ecartees} écartée(s),"
        f" {resume.en_attente} en attente, {resume.passages} passage(s) sans archive"
    ]
    lignes.extend(f"  {topic} : {n} message(s)" for topic, n in sorted(resume.messages.items()))
    if resume.echecs:
        lignes.append(f"  {resume.echecs} message(s) dans la file des échecs")
    if resume.premiere_observation and resume.derniere_observation:
        observee = (resume.derniere_observation - resume.premiere_observation).total_seconds()
        lignes.append(
            f"observé : du {resume.premiere_observation:%d/%m %H:%M:%S} au"
            f" {resume.derniere_observation:%d/%m %H:%M:%S} ({duree_lisible(observee)}) ;"
            f" réel : {duree_lisible(resume.duree_reelle_s)} après {resume.duree_rejeu_s:.1f} s"
            f" de rejeu ; facteur {resume.facteur:g}"
        )
    lignes.append(f"état : {resume.etat}")
    return lignes


def duree_lisible(secondes: float) -> str:
    """``65 h 36 min``, ``4 min 12 s``, ``9.4 s``."""
    if secondes >= 3600:
        heures, reste = divmod(int(secondes), 3600)
        return f"{heures} h {reste // 60:02d} min"
    if secondes >= 60:
        minutes, reste = divmod(int(secondes), 60)
        return f"{minutes} min {reste:02d} s"
    return f"{secondes:.1f} s"
