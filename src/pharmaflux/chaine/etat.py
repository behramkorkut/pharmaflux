"""L'état de la chaîne : le journal des passages, le manifeste et le témoin, lus sans rien lancer.

``pharmaflux chaine etat`` n'écrit rien et ne joint aucun service : il se lance
d'un compte qui ne fait que lire le dérivé (l'IeC, le codeur, beko le matin).
Ce qui demande un service (les collections orphelines de Qdrant) est relevé par
le passage horaire et lu dans son journal.

La fraîcheur (addendum 1, I) va de ``fin`` dans le manifeste (l'archive écrite)
à la fin de l'étape ``index`` du passage complet qui l'a portée. Elle ne compte
que les archives écrites une fois la chaîne en service (après le départ du
premier passage horaire), et l'unité de compte est le passage.
"""

from __future__ import annotations

import json
import os
import statistics
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from pharmaflux.chaine import formats, horaire, journal, remplissage, verification
from pharmaflux.chaine.chemins import Chemins
from pharmaflux.collecte import manifeste

GENRES = (horaire.GENRE, remplissage.GENRE, verification.GENRE)
VERIFICATION_MAX_H = 26  # le minuteur est quotidien : un jour, plus deux heures de marge
P95_A_PARTIR_DE = 20  # en dessous, un p95 ne veut rien dire (addendum 1, question 23)


def _secondes(debut: str, fin: str) -> float:
    return (datetime.fromisoformat(fin) - datetime.fromisoformat(debut)).total_seconds()


def resume(passage: dict[str, Any]) -> dict[str, Any]:
    """Ce qu'on lit d'un passage sans ses étapes."""
    return {
        cle: passage.get(cle)
        for cle in ("genre", "id", "debut", "fin", "duree_s", "issue", "code", "arret", "commit")
    } | {"signalements": passage.get("signalements") or []}


def _etape(passage: dict[str, Any], nom: str) -> dict[str, Any] | None:
    return next((e for e in passage.get("etapes", []) if e.get("nom") == nom), None)


def _complet(passage: dict[str, Any]) -> bool:
    return passage.get("issue") == "complet"


def _nom_bilan(chemin_archive: str) -> str:
    """``bronze/…/20261110T161712Z__af0f1fb00e00.txt.gz`` → ``20261110T161712Z__af0f1fb00e00``."""
    return Path(chemin_archive).name.split(".", 1)[0]


def nature(chemins: Chemins, archive: dict[str, Any]) -> str:
    """Ce que l'archive a donné, d'après son bilan (``evenements``) : la population de la
    fraîcheur est faite des archives « porteuses » ; les autres cas sont nommés à part."""
    bilan = (
        chemins.evenements
        / "bilans"
        / str(archive.get("identifiant"))
        / f"{_nom_bilan(str(archive.get('chemin_archive')))}.json"
    )
    try:
        contenu = json.loads(bilan.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "sans_bilan"  # pas une entité (la page de téléchargement), ou pas encore traitée
    decision = contenu.get("decision")
    nombre = sum((contenu.get("ecart") or {}).get("evenements", {}).values())
    if decision == "confirme":
        return "confirmee_apres_attente"  # une heure de plus, par construction (ADR 0006)
    if decision == "en_attente":
        return "en_attente"
    if decision != "retenu":
        return "ecartee"  # fichier servi vide, garde-fou de volume
    return "porteuse" if nombre else "sans_evenement"


def fraicheur(chemins: Chemins, passages: list[dict[str, Any]]) -> dict[str, Any]:
    """Chaque archive portée jusqu'à l'index, son délai et sa nature ; le résumé par passage."""
    horaires = [p for p in passages if p.get("genre") == horaire.GENRE]
    if not horaires:
        return {"en_service_depuis": None, "archives": [], "passages_porteurs": [], "resume": None}
    en_service = str(horaires[0]["debut"])
    archives: list[dict[str, Any]] = []
    attente: list[dict[str, Any]] = []  # portées par un passage qui n'a pas fini : au suivant
    for passage in horaires:
        attente.extend(passage.get("archives") or [])
        index = _etape(passage, "index")
        if not _complet(passage) or index is None or index.get("code") != 0:
            continue
        for archive in attente:
            if str(archive.get("fin")) < en_service:
                continue  # écrite avant la mise en service : le remplissage ou le rattrapage
            archives.append(
                {
                    **archive,
                    "passage": passage["id"],
                    "nature": nature(chemins, archive),
                    "delai_s": round(_secondes(str(archive["fin"]), str(index["fin"])), 1),
                    "attente_s": round(_secondes(str(archive["fin"]), str(passage["debut"])), 1),
                    "etapes_s": {e["nom"]: e["duree_s"] for e in passage.get("etapes", [])},
                }
            )
        attente = []
    porteurs: dict[str, dict[str, Any]] = {}
    for archive in archives:
        if archive["nature"] != "porteuse":
            continue
        porteur = porteurs.setdefault(
            archive["passage"],
            {"passage": archive["passage"], "archives": 0, "delai_s": 0.0, "etapes_s": {}},
        )
        porteur["archives"] += 1
        porteur["delai_s"] = max(porteur["delai_s"], archive["delai_s"])
        porteur["etapes_s"] = archive["etapes_s"]
    delais = [p["delai_s"] for p in porteurs.values()]
    synthese = None
    if delais:
        synthese = {
            "passages": len(delais),
            "median_s": round(statistics.median(delais), 1),
            "maximum_s": max(delais),
            "p95_s": (
                round(statistics.quantiles(delais, n=20)[-1], 1)
                if len(delais) >= P95_A_PARTIR_DE
                else None
            ),
        }
    return {
        "en_service_depuis": en_service,
        "archives": archives,
        "passages_porteurs": list(porteurs.values()),
        "resume": synthese,
    }


def _passages_de_collecte(chemins: Chemins) -> dict[str, str]:
    """Chaque passage de collecte et la fin de sa dernière ligne, dans l'ordre du manifeste."""
    fins: dict[str, str] = {}
    for ligne in manifeste.parcourir(chemins.racine):
        fin = horaire._instant(ligne.fin)
        if fin > fins.get(ligne.passage_id, ""):
            fins[ligne.passage_id] = fin
    return fins


def _disque(chemin: Path) -> dict[str, int] | None:
    try:
        statut = os.statvfs(chemin)
    except OSError:
        return None
    return {
        "libre_octets": statut.f_bavail * statut.f_frsize,
        "total_octets": statut.f_blocks * statut.f_frsize,
    }


def _dernier(passages: Iterable[dict[str, Any]], genre: str) -> dict[str, Any] | None:
    return next((p for p in reversed(list(passages)) if p.get("genre") == genre), None)


def lire(chemins: Chemins, modele: str, maintenant: datetime) -> dict[str, Any]:
    """L'état entier, en données : ``chaine etat --format json`` le rend tel quel."""
    from pharmaflux.chaine.passage import commit_du_code

    passages = list(journal.lire(chemins.passages))
    derniers = {genre: _dernier(passages, genre) for genre in GENRES}
    complets = [p for p in passages if p.get("genre") == horaire.GENRE and _complet(p)]
    dernier_complet = complets[-1] if complets else None
    erreurs = [p for p in passages if p.get("code") not in (0, None)]
    collecte = _passages_de_collecte(chemins)
    depuis = dernier_complet["debut"] if dernier_complet else None
    non_traites = sorted(i for i, fin in collecte.items() if depuis is not None and fin > depuis)
    try:
        temoin = formats.lire(chemins.formats)
        attendu = formats.attendus(modele)
        ecarts = formats.ecarts(temoin, attendu) if temoin else []
    except ValueError as exc:
        temoin, ecarts = None, [str(exc)]
    dernier_horaire = derniers[horaire.GENRE]
    premier_horaire = next((p for p in passages if p.get("genre") == horaire.GENRE), None)
    verdict = _verdict_du_passage(dernier_horaire, non_traites)
    derniere_verification = derniers[verification.GENRE]
    age_verification_h = _age_h(derniere_verification, maintenant)
    alerte = _alerte_verification(
        derniere_verification, age_verification_h, _age_h(premier_horaire, maintenant, "debut")
    )
    if alerte:
        verdict += f" ; {alerte}"
    age_min = None
    if dernier_complet is not None:
        age_min = round(
            (maintenant - datetime.fromisoformat(str(dernier_complet["fin"]))).total_seconds() / 60
        )
    return {
        "verdict": verdict,
        "code_courant": commit_du_code(),
        "temoin": temoin,
        "ecarts_de_formats": ecarts,
        "derniers": {g: resume(p) if p else None for g, p in derniers.items()},
        "dernier_complet": resume(dernier_complet) if dernier_complet else None,
        "age_dernier_complet_min": age_min,
        "age_verification_h": age_verification_h,
        "derniere_erreur": resume(erreurs[-1]) if erreurs else None,
        "collecte": {
            "dernier_passage": next(reversed(collecte), None),
            "non_traites": non_traites,
        },
        "disque": _disque(chemins.derive),
        "collections_orphelines": (dernier_horaire or {}).get("collections_orphelines"),
        "fraicheur": fraicheur(chemins, passages),
    }


def _etapes_en_cause(passage: dict[str, Any]) -> str:
    """L'étape de l'arrêt, sinon celles des échecs circonscrits."""
    arret = passage.get("arret") or {}
    if arret.get("etape"):
        return str(arret["etape"])
    return ", ".join(str(s.get("etape")) for s in passage.get("signalements") or [])


def _verdict_du_passage(passage: dict[str, Any] | None, non_traites: list[str]) -> str:
    if passage is None:
        return "jamais lancée"
    code = passage.get("code")
    if code not in (0, None) and not passage.get("arret") and passage.get("signalements"):
        motifs = " ; ".join(f"{s.get('etape')} : {s.get('motif')}" for s in passage["signalements"])
        return f"échec circonscrit au dernier passage ({motifs})"
    if code not in (0, None):
        etape = _etapes_en_cause(passage)
        return f"en panne (code {code}" + (f", étape {etape})" if etape else ")")
    if non_traites:
        return f"en retard de {len(non_traites)} passage(s) de collecte"
    return "à jour"


def _age_h(
    passage: dict[str, Any] | None, maintenant: datetime, champ: str = "fin"
) -> float | None:
    if passage is None or not passage.get(champ):
        return None
    ecart = maintenant - datetime.fromisoformat(str(passage[champ]))
    return round(ecart.total_seconds() / 3600, 1)


def _alerte_verification(
    verification_: dict[str, Any] | None,
    age_h: float | None,
    age_service_h: float | None,
) -> str | None:
    """Ce que la dernière vérification ajoute au verdict : un échec, ou un retard de plus de
    ``VERIFICATION_MAX_H`` heures (le minuteur est quotidien)."""
    if verification_ is None:
        if age_service_h is not None and age_service_h > VERIFICATION_MAX_H:
            return f"aucune vérification depuis la mise en service, il y a {age_service_h} h"
        return None
    alertes = []
    code = verification_.get("code")
    if code not in (0, None):
        alertes.append(
            f"vérification en échec (code {code}, étape {_etapes_en_cause(verification_)})"
        )
    if age_h is not None and age_h > VERIFICATION_MAX_H:
        alertes.append(f"dernière vérification il y a {age_h} h")
    return " ; ".join(alertes) or None


def _ligne_passage(passage: dict[str, Any] | None) -> str:
    if passage is None:
        return "aucun"
    texte = (
        f"{passage['debut']}, {passage['duree_s']} s, {passage['issue']}, code {passage['code']}"
    )
    if passage.get("arret"):
        texte += f" (étape {passage['arret'].get('etape')} : {passage['arret'].get('motif')})"
    if passage.get("signalements"):
        texte += f" ; {len(passage['signalements'])} échec(s) circonscrit(s)"
    return texte


def _court(commit: str | None) -> str:
    return commit[:7] if commit else "inconnu"


def en_texte(etat: dict[str, Any]) -> list[str]:
    """Les lignes de ``chaine etat`` ; beko lit la première le matin."""
    temoin = etat["temoin"]
    bati = _court(temoin.get("commit")) if temoin else "inconnu (pas de témoin)"
    lignes = [
        f"chaîne : {etat['verdict']} ; code {_court(etat['code_courant'])}, dérivé bâti par {bati}"
    ]
    derniers = etat["derniers"]
    lignes.append(f"dernier passage      {_ligne_passage(derniers[horaire.GENRE])}")
    complet = etat["dernier_complet"]
    lignes.append(
        "dernier complet      "
        + (
            f"{complet['fin']}, il y a {etat['age_dernier_complet_min']} min"
            if complet
            else "aucun"
        )
    )
    collecte = etat["collecte"]
    lignes.append(
        f"collecte             dernier passage {collecte['dernier_passage'] or 'aucun'} ;"
        f" {len(collecte['non_traites'])} non traité(s) par la chaîne"
    )
    age_h = etat["age_verification_h"]
    lignes.append(
        f"vérification         {_ligne_passage(derniers[verification.GENRE])}"
        + (f", il y a {age_h} h" if age_h is not None else "")
    )
    lignes.append(f"remplissage          {_ligne_passage(derniers[remplissage.GENRE])}")
    disque = etat["disque"]
    if disque:
        gio = 1 << 30
        lignes.append(
            f"disque               {disque['libre_octets'] / gio:.1f} Gio libres"
            f" sur {disque['total_octets'] / gio:.1f} Gio"
        )
    orphelines = etat["collections_orphelines"]
    lignes.append(
        "collections orphelines "
        + ("inconnu" if orphelines is None else f"{len(orphelines)} {' '.join(orphelines)}".strip())
    )
    resume_ = etat["fraicheur"]["resume"]
    lignes.append(
        "fraîcheur            "
        + (
            f"{resume_['passages']} passage(s) porteur(s) ; médian {resume_['median_s']} s ;"
            f" maximum {resume_['maximum_s']} s"
            + (f" ; p95 {resume_['p95_s']} s" if resume_["p95_s"] is not None else "")
            if resume_
            else "aucun passage porteur encore"
        )
    )
    lignes.append(
        "formats              "
        + (
            "conformes au code"
            if temoin and not etat["ecarts_de_formats"]
            else f"écarts : {', '.join(etat['ecarts_de_formats'])}"
            if etat["ecarts_de_formats"]
            else "pas de témoin (écrit au premier passage complet)"
        )
    )
    erreur = etat["derniere_erreur"]
    lignes.append(
        "dernière erreur      "
        + (f"{erreur['genre']} {_ligne_passage(erreur)}" if erreur else "aucune")
    )
    return lignes
