"""Une étape de la chaîne : une commande ``pharmaflux``, lancée dans un sous-processus.

Les mêmes commandes, avec les mêmes options, que celles qu'on taperait à la
main : rien ne change dans le calcul, les codes de sortie restent ceux des
commandes, et la mémoire d'une étape est rendue avant la suivante. La sortie
de l'étape passe telle quelle (journald, sous systemd) ; la chaîne n'en garde
que la fin, pour le journal des passages, et ne s'en sert jamais pour décider.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

LIGNES_GARDEES = 12  # la fin de la sortie d'erreur, dans le journal des passages
LARGEUR_GARDEE = 300  # une ligne plus longue est coupée dans le journal, pas dans la sortie
DELAI_ARRET_S = 30.0  # laissé à une étape pour finir quand la chaîne est interrompue
DELAI_RELAIS_S = 5.0  # laissé aux sorties d'une étape finie pour se vider
# Un « Mo » de la chaîne est un Mio (2²⁰ octets), l'unité de « MemoryMax=512M » : un pic se
# compare ainsi au plafond sans conversion.
OCTETS_PAR_MO = 1 << 20
# Ce qui arrête un passage : l'arrêt de l'unité, Ctrl-C, la session ssh qui tombe.
SIGNAUX = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


class Interruption(BaseException):
    """La chaîne a reçu SIGTERM ou SIGINT : l'étape en cours est arrêtée, le passage consigné."""


@dataclass(frozen=True, slots=True)
class Etape:
    """Une commande à lancer, et les services qu'elle demande."""

    nom: str
    arguments: tuple[str, ...]  # ce qui suit « pharmaflux » sur la ligne de commande
    services: tuple[str, ...] = ()  # sondés avant le lancement (chaine.sante)
    # Le geste à faire quand l'étape refuse (code 2, ses services répondant) : un refus ne se
    # répare pas seul, le passage suivant refuserait de même.
    geste: str = ""


@dataclass(slots=True)
class Resultat:
    """Ce qu'une étape a rendu."""

    nom: str
    commande: str
    debut: str
    fin: str
    duree_s: float
    code: int | None  # None : tuée par un signal
    signal: int | None = None
    resident_mo: int | None = None  # le plus gros processus de l'étape
    # Le pic du groupe systemd depuis son départ, relevé à la fin de l'étape : il ne décroît
    # jamais, et ne dit rien d'une étape plus petite que celles d'avant.
    pic_groupe_mo: int | None = None
    resume: str = ""  # la dernière ligne de la sortie standard
    erreur: list[str] = field(default_factory=list)  # la fin de la sortie d'erreur

    @property
    def reussie(self) -> bool:
        return self.code == 0

    def en_json(self) -> dict[str, Any]:
        return {
            "nom": self.nom,
            "commande": self.commande,
            "debut": self.debut,
            "fin": self.fin,
            "duree_s": self.duree_s,
            "code": self.code,
            "signal": self.signal,
            "resident_mo": self.resident_mo,
            "pic_groupe_mo": self.pic_groupe_mo,
            "resume": self.resume,
            "erreur": self.erreur,
        }


def horodatage() -> str:
    """L'heure UTC à la seconde, comme le manifeste (``2026-11-14T18:17:26Z``)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def interprete() -> str:
    """Le Python de la version en cours, sans passer par un lien qui peut basculer.

    Sur le VPS, ``courante`` est un lien vers une version : une étape lancée après une bascule
    doit rester sur la version où le passage a commencé.
    """
    python = Path(sys.prefix).resolve() / "bin" / "python"
    return str(python) if python.exists() else sys.executable


def _groupe() -> Path | None:
    """Le dossier du groupe de contrôle de ce processus (cgroup v2), sous Linux seulement."""
    try:
        lignes = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    except OSError:
        return None
    for ligne in lignes:
        if ligne.startswith("0::"):
            return Path("/sys/fs/cgroup") / ligne[3:].lstrip("/")
    return None


def pic_groupe_mo() -> int | None:
    """Le pic de mémoire du groupe depuis son départ, en Mo (2²⁰ octets) ; None hors de Linux."""
    groupe = _groupe()
    if groupe is None:
        return None
    try:
        return int((groupe / "memory.peak").read_text(encoding="ascii")) // OCTETS_PAR_MO
    except (OSError, ValueError):
        return None


def partage_groupe_mo() -> int | None:
    """La mémoire partagée du groupe (``shmem`` : tmpfs, dont un /tmp en mémoire), en Mo (2²⁰)."""
    groupe = _groupe()
    if groupe is None:
        return None
    try:
        lignes = (groupe / "memory.stat").read_text(encoding="ascii").splitlines()
    except OSError:
        return None
    for ligne in lignes:
        cle, _, valeur = ligne.partition(" ")
        if cle == "shmem" and valeur.isdigit():
            return int(valeur) // OCTETS_PAR_MO
    return None


def morts_par_memoire() -> int | None:
    """Combien de processus du groupe le noyau a tués pour dépassement du plafond."""
    groupe = _groupe()
    if groupe is None:
        return None
    try:
        lignes = (groupe / "memory.events").read_text(encoding="ascii").splitlines()
    except OSError:
        return None
    for ligne in lignes:
        cle, _, valeur = ligne.partition(" ")
        if cle == "oom_kill" and valeur.isdigit():
            return int(valeur)
    return None


def _relayer(source: BinaryIO, cible: BinaryIO, gardees: deque[str]) -> None:
    """Recopie la sortie d'une étape au fil de l'eau, et en garde les dernières lignes."""
    for ligne in iter(source.readline, b""):
        try:
            cible.write(ligne)
            cible.flush()
        except (OSError, ValueError):
            pass  # la sortie de la chaîne est fermée : l'étape continue
        texte = ligne.decode("utf-8", errors="replace").strip()
        if texte:
            gardees.append(texte[:LARGEUR_GARDEE])
    source.close()


def _resident_mo(usage: Any) -> int:
    # ru_maxrss : en octets sur macOS, en Ko sous Linux.
    return int(usage.ru_maxrss) * (1 if sys.platform == "darwin" else 1024) // OCTETS_PAR_MO


def ignorer_les_signaux() -> None:
    """Après une première interruption : les suivantes ne coupent ni l'arrêt de l'étape, ni
    l'écriture du passage au journal. Les gestionnaires sont rendus à la fin du passage."""
    for numero in SIGNAUX:
        signal.signal(numero, signal.SIG_IGN)


def _arreter(processus: subprocess.Popen[bytes]) -> None:
    """Arrête l'étape et ses propres sous-processus : elle est chef de son groupe."""
    for numero, delai in ((signal.SIGTERM, DELAI_ARRET_S), (signal.SIGKILL, None)):
        with contextlib.suppress(ProcessLookupError, PermissionError):  # déjà finie
            os.killpg(processus.pid, numero)
        try:
            processus.wait(timeout=delai)
            return
        except subprocess.TimeoutExpired:
            continue


def lancer(
    etape: Etape,
    *,
    prefixe: tuple[str, ...] | None = None,
    environnement: dict[str, str] | None = None,
    dossier: Path | None = None,
) -> Resultat:
    """Lance l'étape et attend sa fin. ``Interruption`` l'arrête proprement, puis remonte.

    ``dossier`` est le dossier courant de l'étape : un chemin relatif qu'une bibliothèque
    prendrait par défaut y tombe, au lieu du dossier d'où la chaîne est lancée (« / » sous
    systemd, en lecture seule).
    """
    commande = [*(prefixe or (interprete(), "-m", "pharmaflux")), *etape.arguments]
    debut, depart = horodatage(), time.monotonic()
    sortie: deque[str] = deque(maxlen=1)
    erreur: deque[str] = deque(maxlen=LIGNES_GARDEES)
    processus = subprocess.Popen(
        commande,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environnement,
        cwd=dossier,
        # Un groupe à elle : l'arrêt atteint aussi ce qu'elle lance (« index construire »
        # extrait ses fragments dans un sous-processus).
        start_new_session=True,
    )
    assert processus.stdout is not None and processus.stderr is not None
    relais = [
        threading.Thread(target=_relayer, args=(processus.stdout, sys.stdout.buffer, sortie)),
        threading.Thread(target=_relayer, args=(processus.stderr, sys.stderr.buffer, erreur)),
    ]
    try:
        for fil in relais:
            fil.daemon = True
            fil.start()
        # wait4 rend aussi la consommation de l'étape : le résident de son plus gros processus.
        _, statut, usage = os.wait4(processus.pid, 0)
        retour = os.waitstatus_to_exitcode(statut)
        processus.returncode = retour
        # L'étape est finie : ses sorties se ferment. Si un de ses descendants les gardait
        # ouvertes, on ne l'attend pas.
        for fil in relais:
            fil.join(DELAI_RELAIS_S)
    except Interruption:
        ignorer_les_signaux()
        _arreter(processus)
        raise
    return Resultat(
        nom=etape.nom,
        commande="pharmaflux " + " ".join(etape.arguments),
        debut=debut,
        fin=horodatage(),
        duree_s=round(time.monotonic() - depart, 1),
        code=retour if retour >= 0 else None,
        signal=-retour if retour < 0 else None,
        resident_mo=_resident_mo(usage),
        pic_groupe_mo=pic_groupe_mo(),
        resume=sortie[-1] if sortie else "",
        erreur=list(erreur),
    )
