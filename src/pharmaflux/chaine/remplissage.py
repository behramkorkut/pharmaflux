"""Le premier remplissage : tout le dérivé rebâti depuis l'archive, puis vérifié.

Les étapes sont les commandes existantes, dans l'ordre où on les taperait.
Deux contrôles d'abord (le modèle, les pages d'avis), qui n'écrivent rien : un
index bâti sans les pages d'avis les ignorerait ensuite en silence. Puis les
événements, le bus, le silver et l'index, chacun suivi de sa vérification.

Relancer le remplissage est sans danger : ``evenements``, ``publier`` et
``silver consommer`` reprennent où ils en étaient, et l'index se reconstruit
(en moins de temps, les vecteurs déjà calculés restant dans son cache).
"""

from __future__ import annotations

from pharmaflux.chaine.chemins import Chemins
from pharmaflux.chaine.etapes import Etape
from pharmaflux.chaine.sante import COURTIER, QDRANT, REGISTRE

GENRE = "remplissage"
MODELE_PAR_DEFAUT = "e5-small-int8"  # celui de l'index (ADR 0011)
ENCODEUR_DE_TEST = "test"  # sans fichier à vérifier : la CI, sur le jeu de démo


def plan(chemins: Chemins, modele: str = MODELE_PAR_DEFAUT) -> list[Etape]:
    """Les étapes du remplissage, dans l'ordre."""
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
    modele_epingle = (
        []
        if modele == ENCODEUR_DE_TEST
        else [Etape("modele", ("index", "modele", "verifier", modele))]
    )
    return [
        *modele_epingle,
        Etape("pages-has", ("has", "extraire", "--verifier", "--racine", racine)),
        Etape("evenements", ("evenements", "--reprendre", "--racine", racine, "--sortie", sortie)),
        Etape("schemas", ("schemas", "enregistrer"), (REGISTRE,)),
        Etape("publier", ("publier", "--reprendre", "--sortie", sortie), (COURTIER, REGISTRE)),
        Etape(
            "verifier-bus", ("verifier-bus", "--racine", racine, "--sortie", sortie), (COURTIER,)
        ),
        Etape("silver", ("silver", "consommer", "--entrepot", entrepot), (COURTIER,)),
        Etape(
            "silver-verifier",
            ("silver", "verifier", "--entrepot", entrepot, "--sortie", sortie, "--racine", racine),
        ),
        Etape("index", ("index", "construire", *index), (QDRANT,)),
        Etape("index-verifier", ("index", "verifier", *index), (QDRANT,)),
        Etape("index-etat", ("index", "etat", "--complet"), (QDRANT,)),
    ]
