"""Catalogue des sources : ce que le collecteur télécharge, déclaré une fois.

Quatorze entrées : la page de téléchargement de la BDPM (preuve datée de ce
que le site affiche), les onze fichiers BDPM de l'annexe A du PRD, la
documentation PDF de leur format (un changement y signale un changement de
schéma) et les métadonnées du jeu Open Medic sur data.gouv.fr. Chaque entrée porte sa
cadence et le mode de calcul de son empreinte de comparaison (voir
``empreintes.py``). Rien n'est téléchargé qui ne soit déclaré ici.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

SITE_BDPM = "https://base-donnees-publique.medicaments.gouv.fr"
URL_PAGE_BDPM = f"{SITE_BDPM}/telechargement"
FICHIER_DOCUMENTATION_FORMATS = "Contenu_et_format_des_fichiers_telechargeables_dans_la_BDM_v5.pdf"
URL_METADONNEES_OPENMEDIC = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes/"
)


class Cadence(StrEnum):
    """À quelle fréquence une entrée est collectée."""

    CHAQUE_PASSAGE = "chaque_passage"
    QUOTIDIENNE = "quotidienne"


class ModeEmpreinte(StrEnum):
    """Comment calculer l'empreinte qui décide « nouveau » ou « inchangé ».

    L'archive et le ``sha256`` du manifeste portent toujours sur les octets
    bruts ; ce mode ne sert qu'à la décision d'archiver.
    """

    OCTETS = "octets"
    LIGNES_TRIEES = "lignes_triees"
    PAGE_BDPM = "page_bdpm"
    METADONNEES_DATAGOUV = "metadonnees_datagouv"


@dataclass(frozen=True, slots=True)
class Entree:
    """Une source à collecter."""

    identifiant: str
    source: str
    fichier: str
    url: str
    description: str
    cadence: Cadence = Cadence.CHAQUE_PASSAGE
    empreinte: ModeEmpreinte = ModeEmpreinte.OCTETS

    @property
    def extension(self) -> str:
        """Extension du fichier d'archive, avant le ``.gz`` (``.txt``, ``.html``, ``.json``)."""
        return PurePosixPath(self.fichier).suffix


class IdentifiantInconnu(ValueError):  # noqa: N818 (nom français voulu)
    """Un identifiant demandé n'est pas dans le catalogue."""


def _bdpm(identifiant: str, fichier: str, description: str) -> Entree:
    """Un fichier BDPM ordinaire : route ``/download/file/``, octets comparés tels quels."""
    return Entree(
        identifiant=f"bdpm.{identifiant}",
        source="bdpm",
        fichier=fichier,
        url=f"{SITE_BDPM}/download/file/{fichier}",
        description=description,
    )


CATALOGUE: tuple[Entree, ...] = (
    # La page d'abord : elle donne les dates et tailles affichées des fichiers
    # qui suivent, et permet de détecter un lien absent ou nouveau.
    Entree(
        identifiant="bdpm.page_telechargement",
        source="bdpm",
        fichier="telechargement.html",
        url=URL_PAGE_BDPM,
        description="Page de téléchargement : liens, dates de mise à jour et tailles affichées",
        empreinte=ModeEmpreinte.PAGE_BDPM,
    ),
    _bdpm("specialites", "CIS_bdpm.txt", "Spécialités"),
    _bdpm("presentations", "CIS_CIP_bdpm.txt", "Présentations, prix, taux de remboursement"),
    _bdpm("compositions", "CIS_COMPO_bdpm.txt", "Compositions"),
    _bdpm("smr", "CIS_HAS_SMR_bdpm.txt", "Avis SMR de la HAS"),
    _bdpm("asmr", "CIS_HAS_ASMR_bdpm.txt", "Avis ASMR de la HAS"),
    _bdpm(
        "liens_ct",
        "HAS_LiensPageCT_bdpm.txt",
        "Liens vers les avis de la Commission de la transparence",
    ),
    _bdpm("generiques", "CIS_GENER_bdpm.txt", "Groupes génériques"),
    _bdpm(
        "conditions_prescription", "CIS_CPD_bdpm.txt", "Conditions de prescription et de délivrance"
    ),
    _bdpm(
        "disponibilite",
        "CIS_CIP_Dispo_Spec.txt",
        "Disponibilité des spécialités (ruptures, tensions)",
    ),
    _bdpm("mitm", "CIS_MITM.txt", "Médicaments d'intérêt thérapeutique majeur"),
    Entree(
        identifiant="bdpm.infos_importantes",
        source="bdpm",
        fichier="CIS_InfoImportantes.txt",
        # Autre route que les dix autres fichiers : généré à la demande.
        url=f"{SITE_BDPM}/download/CIS_InfoImportantes.txt",
        description="Informations importantes (généré à la demande, lignes non triées)",
        empreinte=ModeEmpreinte.LIGNES_TRIEES,
    ),
    Entree(
        identifiant="bdpm.documentation_formats",
        source="bdpm",
        fichier=FICHIER_DOCUMENTATION_FORMATS,
        url=f"{SITE_BDPM}/download/file/{FICHIER_DOCUMENTATION_FORMATS}",
        description="Documentation du format des fichiers BDPM (PDF) : change avec le schéma",
        cadence=Cadence.QUOTIDIENNE,
    ),
    Entree(
        identifiant="openmedic.metadonnees",
        source="openmedic",
        fichier="metadonnees.json",
        url=URL_METADONNEES_OPENMEDIC,
        description="Métadonnées du jeu Open Medic sur data.gouv.fr (ressources, dates)",
        cadence=Cadence.QUOTIDIENNE,
        empreinte=ModeEmpreinte.METADONNEES_DATAGOUV,
    ),
)


def par_identifiant(identifiants: list[str]) -> list[Entree]:
    """Les entrées demandées, dans l'ordre du catalogue (la page reste en tête)."""
    connus = {entree.identifiant for entree in CATALOGUE}
    inconnus = sorted(set(identifiants) - connus)
    if inconnus:
        raise IdentifiantInconnu(
            f"identifiant(s) inconnu(s) : {', '.join(inconnus)}. "
            f"Connus : {', '.join(sorted(connus))}."
        )
    demandes = set(identifiants)
    return [entree for entree in CATALOGUE if entree.identifiant in demandes]


def entrees_bdpm_par_url() -> dict[str, Entree]:
    """Les entrées de fichiers BDPM (page exclue), par URL : sert à relire la page."""
    return {
        entree.url: entree
        for entree in CATALOGUE
        if entree.source == "bdpm" and entree.empreinte is not ModeEmpreinte.PAGE_BDPM
    }
