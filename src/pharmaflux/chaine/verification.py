"""Les vérifications quotidiennes : le bus, le silver et l'index, relus contre l'archive.

Une fois par jour, vers 03:40 UTC, loin de minuit où tombent les changements
(addendum 1, question 21), sous le même verrou que le passage horaire : elles
ne se chevauchent jamais. Ce sont les vérifications du remplissage, sans rien
bâtir. Toutes sont lancées, même après une étape en échec : chacune lit le
dérivé sans l'écrire, et chaque verdict compte.
"""

from __future__ import annotations

from pharmaflux.chaine.chemins import Chemins
from pharmaflux.chaine.etapes import Etape, Resultat
from pharmaflux.chaine.remplissage import MODELE_PAR_DEFAUT
from pharmaflux.chaine.sante import COURTIER, QDRANT

GENRE = "verification"


def plan(chemins: Chemins, modele: str = MODELE_PAR_DEFAUT) -> list[Etape]:
    """Les vérifications, dans l'ordre : le bus d'abord, l'index en dernier."""
    racine, sortie = str(chemins.racine), str(chemins.evenements)
    entrepot = str(chemins.lakehouse)
    index = (
        "--entrepot",
        entrepot,
        "--travail",
        str(chemins.index),
        "--modele",
        modele,
        "--archive-has",
        racine,
    )
    return [
        Etape(
            "verifier-bus", ("verifier-bus", "--racine", racine, "--sortie", sortie), (COURTIER,)
        ),
        Etape(
            "silver-verifier",
            ("silver", "verifier", "--entrepot", entrepot, "--sortie", sortie, "--racine", racine),
        ),
        Etape("index-verifier", ("index", "verifier", *index), (QDRANT,)),
        Etape("index-etat", ("index", "etat", "--complet"), (QDRANT,)),
    ]


def circonscrit(etape: Etape, resultat: Resultat) -> str | None:
    """Une vérification en échec n'empêche pas les suivantes : elles ne font que lire."""
    if resultat.signal is not None:
        return None  # tuée (mémoire, arrêt) : on s'arrête
    return f"{etape.nom} : code {resultat.code}"
