"""Empreintes : celle des octets bruts, et celle qui décide d'archiver.

Trois sources changent d'octets sans changer de fond : l'ordre des lignes
de ``CIS_InfoImportantes.txt`` n'est pas garanti, la page de téléchargement
porte un ``nonce`` différent à chaque réponse, le JSON de data.gouv.fr
contient des compteurs et des dates de robot. Pour elles, l'empreinte de
comparaison est calculée sur une projection stable du contenu. Le
``sha256`` du manifeste et le fichier archivé restent ceux des octets reçus.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pharmaflux.collecte.catalogue import ModeEmpreinte
from pharmaflux.collecte.page import AnalyseImpossible, analyser_page

CHAMPS_RESSOURCE_DATAGOUV = ("id", "title", "url", "format", "created_at", "description")


def sha256_hex(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def empreinte_comparaison(mode: ModeEmpreinte, contenu: bytes) -> str:
    """L'empreinte qui décide « nouveau » ou « inchangé » pour ce mode.

    Lève ``AnalyseImpossible`` quand le contenu n'a pas la forme attendue
    (page sans lien, JSON invalide ou sans ressources).
    """
    match mode:
        case ModeEmpreinte.OCTETS:
            return sha256_hex(contenu)
        case ModeEmpreinte.LIGNES_TRIEES:
            return sha256_hex(b"\n".join(sorted(contenu.split(b"\n"))))
        case ModeEmpreinte.PAGE_BDPM:
            couples = sorted(
                (lien.url, lien.date_affichee, lien.taille_affichee_ko)
                for lien in analyser_page(contenu)
            )
            return _sha256_json(couples)
        case ModeEmpreinte.METADONNEES_DATAGOUV:
            return _sha256_json(projection_datagouv(contenu))


def projection_datagouv(contenu: bytes) -> dict[str, Any]:
    """Ce qui compte dans les métadonnées d'un jeu data.gouv.fr.

    Les ressources (identifiant, titre, URL, format, date de création,
    description), triées par identifiant, plus ``last_modified`` du jeu et le
    nombre de ressources. Les ``last_modified`` par ressource sont ceux du
    robot de data.gouv.fr (ils bougent chaque jour sans publication) : exclus.
    """
    try:
        jeu = json.loads(contenu)
    except ValueError as exc:
        raise AnalyseImpossible(f"JSON invalide : {exc}") from exc
    if not isinstance(jeu, dict) or not isinstance(jeu.get("resources"), list):
        raise AnalyseImpossible("JSON sans liste « resources »")
    ressources: list[dict[str, Any]] = jeu["resources"]
    return {
        "last_modified": jeu.get("last_modified"),
        "nombre_ressources": len(ressources),
        "ressources": sorted(
            (
                {champ: ressource.get(champ) for champ in CHAMPS_RESSOURCE_DATAGOUV}
                for ressource in ressources
            ),
            key=lambda ressource: str(ressource["id"]),
        ),
    }


def _sha256_json(valeur: object) -> str:
    return sha256_hex(json.dumps(valeur, ensure_ascii=False, sort_keys=True).encode("utf-8"))
