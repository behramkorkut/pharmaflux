"""Le jeu de démo figé (``demo/archive``) : sa fabrication depuis une archive, sa vérification.

Le jeu est une archive Pharmaflux comme une autre (``bronze/…``,
``manifeste/collecte.jsonl``), coupée à un passage de collecte et réduite
aux fichiers que ``evenements`` lit : toute commande qui prend ``--racine``
marche dessus sans rien de neuf. Il est fabriqué par ``pharmaflux demo
fabriquer``, jamais à la main : les archives citées par le manifeste sont
copiées à l'octet, les lignes du manifeste reprises telles quelles et dans
l'ordre, rien n'est jamais écrit dans l'archive source. C'est la seule
donnée admise dans le dépôt (``CLAUDE.md``) : elle vient d'un service
public, elle est figée, et ``verifier`` la contrôle sur un clone neuf.

Depuis la mission 09, le jeu a une seconde partie figée : des pages d'avis de la HAS, avec leur
manifeste à part (``demo.has``). ``verifier`` contrôle les deux.

Comme ``pharmaflux.bronze``, tout nom qui commence par un point est ignoré
(``.DS_Store`` d'un Mac, dossier d'un rapatriement coupé) : il n'entre pas
dans « rien d'autre n'est présent ».
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pharmaflux.bronze import DOSSIER_BRONZE, MOTIF_NOM
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.manifeste import Enregistrement, ManifesteCorrompu, Statut
from pharmaflux.demo import has

JEU_PAR_DEFAUT = Path("demo/archive")  # relatif à la racine du dépôt
MOTIF_PASSAGE = re.compile(r"^\d{8}T\d{6}Z$")
TAILLE_BLOC = 1 << 20


class FabricationRefusee(Exception):  # noqa: N818 (nom français voulu)
    """Coupure mal formée, destination non vide ou sous la racine, source incomplète :
    rien n'est écrit. Un jeu ne se met pas à jour, on en fabrique un autre."""


@dataclass(frozen=True, slots=True)
class ArchiveDuJeu:
    """Une archive du jeu, telle que sa ligne ``nouveau`` du manifeste la décrit."""

    identifiant: str
    fichier: str
    passage_id: str
    chemin: str  # relatif à la racine du jeu, comme dans le manifeste
    sha256: str
    taille_octets: int | None
    date_source_affichee: str | None


@dataclass(slots=True)
class Bilan:
    """Ce que le jeu contient, et ce qui le rend non conforme s'il y a quelque chose."""

    lignes: int = 0
    archives: list[ArchiveDuJeu] = field(default_factory=list)
    entites: list[str] = field(default_factory=list)  # identifiants, triés
    passages: int = 0  # passages de collecte distincts
    premier_passage: str | None = None
    dernier_passage: str | None = None
    anomalies: list[str] = field(default_factory=list)
    has: has.BilanHas = field(default_factory=has.BilanHas)  # la partie HAS (mission 09)

    @property
    def conforme(self) -> bool:
        return not self.anomalies

    def archives_par_entite(self) -> dict[str, int]:
        comptes: dict[str, int] = {}
        for archive in self.archives:
            comptes[archive.identifiant] = comptes.get(archive.identifiant, 0) + 1
        return dict(sorted(comptes.items()))


def fabriquer(
    racine: Path, destination: Path, jusqu_au_passage: str, identifiants: Iterable[str]
) -> Bilan:
    """Copie dans ``destination`` les lignes et archives des ``identifiants`` jusqu'au passage.

    Le passage ``jusqu_au_passage`` (``AAAAMMJJTHHMMSSZ``) est inclus : un
    passage est l'unité, tout ce qu'il a consigné entre, ou rien. Les lignes
    du manifeste sont reprises à l'octet et dans l'ordre, les archives citées
    par les lignes ``nouveau`` sont copiées à l'octet (``shutil.copyfile``).
    Deux passes sur le manifeste, en flux : la première vérifie que tout ce
    qu'il faut copier existe, la seconde écrit ; une destination non vide ou
    placée sous la racine est refusée avant la première. Rend le bilan de
    ``verifier`` sur le jeu écrit.
    """
    if not MOTIF_PASSAGE.match(jusqu_au_passage):
        raise FabricationRefusee(
            f"coupure {jusqu_au_passage!r} : un identifiant de passage AAAAMMJJTHHMMSSZ est attendu"
        )
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise FabricationRefusee(
            f"{destination} n'est pas un dossier vide : un jeu ne se met pas à jour, choisis une"
            " destination neuve"
        )
    if destination.resolve().is_relative_to(racine.resolve()):
        raise FabricationRefusee(f"{destination} est sous la racine {racine}, qui ne s'écrit pas")
    source_manifeste = manifeste.chemin_manifeste(racine)
    if not source_manifeste.is_file():
        raise FabricationRefusee(f"{source_manifeste} absent : {racine} n'est pas une archive")
    voulus = set(identifiants)
    retenues = 0
    for _, ligne in manifeste.parcourir_brut(racine):
        if not _retenue(ligne, voulus, jusqu_au_passage):
            continue
        retenues += 1
        if (
            ligne.statut == Statut.NOUVEAU
            and ligne.chemin_archive
            and not (racine / ligne.chemin_archive).is_file()
        ):
            raise FabricationRefusee(
                f"{ligne.chemin_archive}, cité par le manifeste, est absent de {racine}"
            )
    if not retenues:
        raise FabricationRefusee(
            f"aucune ligne du manifeste jusqu'au passage {jusqu_au_passage} pour"
            f" {', '.join(sorted(voulus)) or 'aucune entité'}"
        )
    cible = manifeste.chemin_manifeste(destination)
    cible.parent.mkdir(parents=True, exist_ok=True)
    temporaire = cible.with_name(f".{cible.name}.partiel")
    with temporaire.open("wb") as flux:
        for brute, ligne in manifeste.parcourir_brut(racine):
            if not _retenue(ligne, voulus, jusqu_au_passage):
                continue
            if ligne.statut == Statut.NOUVEAU and ligne.chemin_archive:
                copie = destination / ligne.chemin_archive
                copie.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(racine / ligne.chemin_archive, copie)
            flux.write(brute + b"\n")
    temporaire.replace(cible)
    return verifier(destination)


def _retenue(ligne: Enregistrement, voulus: set[str], jusqu_au_passage: str) -> bool:
    return ligne.identifiant in voulus and ligne.passage_id <= jusqu_au_passage


def verifier(racine: Path) -> Bilan:
    """Le jeu est-il exactement ce que son manifeste dit ? Le bilan liste chaque écart.

    Vérifié : le manifeste se lit, ses lignes sont dans l'ordre des passages,
    aucune n'est en erreur ; chaque ligne ``nouveau`` cite une archive sous
    ``bronze/<source>/<fichier>/`` qui existe, dont le nom porte les douze
    premiers caractères de son sha256 et dont les octets décompressés ont ce
    sha256 et la taille consignée ; chaque fichier du jeu est le manifeste ou
    une archive citée par exactement une ligne ; aucun dossier n'est vide ni
    étranger. Les lignes ``inchange`` postérieures à la dernière archive sont
    admises : elles disent que le fichier n'a plus bougé.
    """
    bilan = Bilan()
    chemin_manifeste = manifeste.chemin_manifeste(racine)
    if not chemin_manifeste.is_file():
        bilan.anomalies.append(f"{chemin_manifeste} absent")
        return _avec_has(racine, bilan, set())
    cites: dict[str, int] = {}
    passages: set[str] = set()
    entites: set[str] = set()
    precedent: tuple[str, str] | None = None
    try:
        for ligne in manifeste.parcourir(racine):
            bilan.lignes += 1
            numero = bilan.lignes
            ordre = (ligne.passage_id, ligne.debut)
            if precedent is not None and ordre < precedent:
                bilan.anomalies.append(
                    f"ligne {numero} : passage {ligne.passage_id} ({ligne.debut}) rangé après"
                    f" {precedent[0]} ({precedent[1]}) : le manifeste n'est pas dans l'ordre"
                )
            precedent = ordre
            passages.add(ligne.passage_id)
            if ligne.identifiant:
                entites.add(ligne.identifiant)
            if ligne.statut == Statut.ERREUR:
                bilan.anomalies.append(f"ligne {numero} : statut erreur ({ligne.erreur})")
            if ligne.statut != Statut.NOUVEAU:
                continue
            if not (ligne.identifiant and ligne.chemin_archive and ligne.sha256):
                bilan.anomalies.append(
                    f"ligne {numero} : nouveau sans identifiant, chemin_archive ou sha256"
                )
                continue
            cites[ligne.chemin_archive] = cites.get(ligne.chemin_archive, 0) + 1
            bilan.archives.append(
                ArchiveDuJeu(
                    ligne.identifiant,
                    ligne.fichier,
                    ligne.passage_id,
                    ligne.chemin_archive,
                    ligne.sha256,
                    ligne.taille_octets,
                    ligne.date_source_affichee,
                )
            )
            bilan.anomalies.extend(_verifier_archive(racine, ligne))
    except ManifesteCorrompu as exc:
        bilan.anomalies.append(str(exc))
    for chemin, nombre in sorted(cites.items()):
        if nombre > 1:
            bilan.anomalies.append(f"{chemin} : cité par {nombre} lignes nouveau")
    bilan.entites = sorted(entites)
    bilan.passages = len(passages)
    if passages:
        bilan.premier_passage, bilan.dernier_passage = min(passages), max(passages)
    return _avec_has(racine, bilan, set(cites))


def _avec_has(racine: Path, bilan: Bilan, cites: set[str]) -> Bilan:
    """La partie HAS, puis l'arborescence : rien d'autre que ce que les deux manifestes citent."""
    bilan.has = has.verifier(racine)
    bilan.anomalies.extend(bilan.has.anomalies)
    bilan.anomalies.extend(_verifier_arborescence(racine, cites | bilan.has.cites))
    return bilan


def _verifier_archive(racine: Path, ligne: Enregistrement) -> list[str]:
    """L'archive d'une ligne ``nouveau`` : son emplacement, son nom, ses octets."""
    chemin = ligne.chemin_archive or ""
    sha256 = ligne.sha256 or ""
    anomalies = []
    attendu = f"{DOSSIER_BRONZE}/{ligne.source}/{ligne.fichier}/"
    if not chemin.startswith(attendu):
        anomalies.append(f"{chemin} : hors de {attendu}")
    correspondance = MOTIF_NOM.match(Path(chemin).name)
    if correspondance is None:
        anomalies.append(f"{chemin} : nom sans la forme <horodatage>__<sha256 12 car.>.<ext>.gz")
    elif correspondance["sha256"] != sha256[:12]:
        anomalies.append(f"{chemin} : le nom ne porte pas le début du sha256 {sha256[:12]}")
    fichier = racine / chemin
    if not fichier.is_file():
        anomalies.append(f"{chemin} : cité par le manifeste, absent du jeu")
        return anomalies
    try:
        empreinte, taille = _sha256_decompresse(fichier)
    except (OSError, EOFError) as exc:
        anomalies.append(f"{chemin} : archive illisible ({exc})")
        return anomalies
    if empreinte != sha256:
        anomalies.append(f"{chemin} : sha256 {empreinte[:12]}… au lieu de {sha256[:12]}…")
    if ligne.taille_octets is not None and taille != ligne.taille_octets:
        anomalies.append(f"{chemin} : {taille} octets au lieu de {ligne.taille_octets}")
    return anomalies


def _sha256_decompresse(chemin: Path) -> tuple[str, int]:
    """Le sha256 et la taille des octets décompressés, lus par blocs."""
    empreinte = hashlib.sha256()
    taille = 0
    with gzip.open(chemin, "rb") as flux:
        while bloc := flux.read(TAILLE_BLOC):
            empreinte.update(bloc)
            taille += len(bloc)
    return empreinte.hexdigest(), taille


def _verifier_arborescence(racine: Path, cites: set[str]) -> list[str]:
    """Rien d'autre que le manifeste et les archives citées ; aucun dossier vide ni étranger."""
    attendus = cites | {manifeste.chemin_manifeste(racine).relative_to(racine).as_posix()}
    anomalies: list[str] = []
    for parent, sous_dossiers, noms in os.walk(racine):
        sous_dossiers[:] = sorted(nom for nom in sous_dossiers if not nom.startswith("."))
        visibles = sorted(nom for nom in noms if not nom.startswith("."))
        dossier = Path(parent)
        relatif = dossier.relative_to(racine).as_posix()
        if dossier == racine:
            etrangers = [nom for nom in sous_dossiers if nom not in (DOSSIER_BRONZE, "manifeste")]
            anomalies.extend(f"{nom}/ : dossier étranger au jeu" for nom in etrangers)
            sous_dossiers[:] = [nom for nom in sous_dossiers if nom not in etrangers]
        elif not sous_dossiers and not visibles:
            anomalies.append(f"{relatif}/ : dossier vide")
        for nom in visibles:
            chemin = f"{relatif}/{nom}" if relatif != "." else nom
            if chemin not in attendus:
                anomalies.append(f"{chemin} : fichier étranger au jeu, cité par aucune ligne")
    return anomalies
