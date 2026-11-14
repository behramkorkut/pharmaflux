"""Un passage de la chaîne : le verrou, les étapes une par une, une ligne au journal.

Le remplissage (palier 1) s'arrête à la première étape qui ne rend pas 0 : il
se relance à la main, et chaque étape reprend où elle en était. Un passage ne
décide jamais en lisant la sortie d'une étape ; il ne connaît que son code, le
signal qui l'a tuée, et la réponse des services sondés avant de la lancer.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from importlib.metadata import version as version_du_paquet
from pathlib import Path
from types import FrameType
from typing import Any

from pharmaflux.chaine import etapes, journal, sante
from pharmaflux.chaine.chemins import Chemins
from pharmaflux.chaine.etapes import Etape, Interruption, Resultat
from pharmaflux.chaine.verrou import verrou
from pharmaflux.index.modeles import VARIABLE_MODELES

COMPLET, ARRETE, INTERROMPU = "complet", "arrete", "interrompu"
_COMMIT = re.compile(r"[0-9a-f]{40}")


def commit_du_code() -> str | None:
    """Le commit du code qui tourne, lu dans ``VERSION`` à la racine de la version déposée.

    ``git archive`` y écrit le commit (``export-subst``). Dans un clone de travail, le fichier
    porte encore sa marque : le commit est alors inconnu, et la chaîne le dit.
    """
    try:
        texte = (Path(sys.prefix).resolve().parent / "VERSION").read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return texte if _COMMIT.fullmatch(texte) else None


@contextmanager
def _signaux() -> Iterator[None]:
    """SIGTERM, SIGINT et SIGHUP arrêtent l'étape en cours ; le passage s'écrit au journal."""

    def interrompre(numero: int, _cadre: FrameType | None) -> None:
        raise Interruption(signal.Signals(numero).name)

    anciens = {s: signal.signal(s, interrompre) for s in etapes.SIGNAUX}
    try:
        yield
    finally:
        for numero, ancien in anciens.items():
            signal.signal(numero, ancien)


def _environnement(chemins: Chemins) -> dict[str, str]:
    environnement = dict(os.environ)
    environnement["PYTHONUNBUFFERED"] = "1"  # la sortie d'une étape passe ligne à ligne
    if chemins.modeles is not None:
        environnement[VARIABLE_MODELES] = str(chemins.modeles)
    return environnement


def _motif(resultat: Resultat) -> str:
    if resultat.signal is not None:
        return f"tuée par le signal {resultat.signal}"
    return f"code {resultat.code}"


def derouler(
    genre: str,
    plan: Sequence[Etape],
    chemins: Chemins,
    *,
    ecrire: Callable[[str], None],
) -> int:
    """Déroule ``plan`` sous le verrou et rend le code de sortie ; ``VerrouTenu`` s'il est pris.

    0 : toutes les étapes ont rendu 0. 2 : une étape a refusé (code 2), ses services répondant.
    1 : tout le reste (service injoignable, étape en échec ou tuée, passage interrompu, étape
    qui rend 2 parce que le noyau a tué un de ses processus au plafond de mémoire).
    """
    with verrou(chemins.verrou), _signaux():
        debut, depart = etapes.horodatage(), time.monotonic()
        # Sous le verrou, aucune autre commande de la chaîne ne tourne : ce qu'une étape tuée a
        # laissé dans le dossier temporaire ne sert plus à personne.
        shutil.rmtree(chemins.tmp, ignore_errors=True)
        chemins.tmp.mkdir(parents=True, exist_ok=True)
        environnement = _environnement(chemins)
        faites: list[Resultat] = []
        arret: dict[str, str] | None = None
        issue, code = COMPLET, 0
        en_cours = ""  # l'étape lancée et pas encore rendue
        try:
            for rang, etape in enumerate(plan, start=1):
                ecrire(f"{genre} : étape {rang}/{len(plan)}, {etape.nom}")
                panne = next(
                    (f"{s} injoignable ({r})" for s in etape.services if (r := sante.sonder(s))),
                    None,
                )
                if panne is not None:
                    arret, issue, code = {"etape": etape.nom, "motif": panne}, ARRETE, 1
                    break
                tues_avant = etapes.morts_par_memoire()
                en_cours = etape.nom
                resultat = etapes.lancer(etape, environnement=environnement, dossier=chemins.tmp)
                faites.append(resultat)
                en_cours = ""
                tues = etapes.morts_par_memoire()
                ecrire(
                    f"{genre} : {etape.nom}, {_motif(resultat)}, {resultat.duree_s} s,"
                    f" résident {resultat.resident_mo} Mo"
                )
                if not resultat.reussie:
                    arret = {"etape": etape.nom, "motif": _motif(resultat)}
                    issue, code = ARRETE, 2 if resultat.code == 2 else 1
                    # Le noyau a tué un processus du groupe pendant l'étape (son compteur, pas
                    # la sortie de l'étape) : c'est une panne, quel que soit le code rendu.
                    # « index construire » rend 2 quand son sous-processus meurt.
                    if tues is not None and tues_avant is not None and tues > tues_avant:
                        arret["motif"] += ", un processus tué par le plafond de mémoire"
                        code = 1
                    break
        except Interruption as exc:
            etapes.ignorer_les_signaux()
            etape_touchee = en_cours or (plan[len(faites)].nom if len(faites) < len(plan) else "")
            arret = {"etape": etape_touchee, "motif": f"passage interrompu ({exc})"}
            issue, code = INTERROMPU, 1
        except Exception as exc:
            etape_touchee = en_cours or (plan[len(faites)].nom if len(faites) < len(plan) else "")
            arret = {"etape": etape_touchee, "motif": f"{type(exc).__name__} : {exc}"}
            issue, code = ARRETE, 1
        # Une étape lancée puis coupée n'est ni rendue, ni « non lancée ».
        reste = plan[len(faites) + (1 if en_cours else 0) :]
        passage: dict[str, Any] = {
            "genre": genre,
            "id": debut.replace("-", "").replace(":", ""),
            "version": version_du_paquet("pharmaflux"),
            "commit": commit_du_code(),
            "debut": debut,
            "fin": etapes.horodatage(),
            "duree_s": round(time.monotonic() - depart, 1),
            "issue": issue,
            "code": code,
            "arret": arret,
            "etapes": [r.en_json() for r in faites],
            "non_lancees": [e.nom for e in reste],
            "pic_groupe_mo": etapes.pic_groupe_mo(),
            "partage_groupe_mo": etapes.partage_groupe_mo(),
            "morts_par_memoire": etapes.morts_par_memoire(),
        }
        journal.ajouter(chemins.passages, passage)
        if arret is None:
            ecrire(f"{genre} : complet, {len(faites)} étape(s), {passage['duree_s']} s")
        else:
            ecrire(f"{genre} : arrêté à l'étape {arret['etape']} ({arret['motif']})")
        return code
