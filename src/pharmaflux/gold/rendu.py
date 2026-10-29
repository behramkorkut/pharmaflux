"""Le rendu du gold : JSON Lines à toute profondeur, et la fiche médicament en texte.

Un décimal s'écrit en chaîne exacte (``"1.16"``, jamais un flottant), une
date en ``AAAA-MM-JJ``, un instant en ``…Z`` à la seconde, y compris dans les
listes et les structures imbriquées de la fiche. Le tableau et le CSV sont
ceux du silver (``silver.etat.rendre``).

Le texte de la fiche est déterministe et lisible par un humain : il sert au
README et à la ligne de commande, et **n'engage pas** le format des
fragments du Lot 3 (ADR 0010). Chaque section cite son fichier, la date de
sa source et depuis quand la valeur est observée.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pyarrow as pa

from pharmaflux.silver import Format
from pharmaflux.silver import etat as etat_silver
from pharmaflux.silver.schema import texte_instant

LOT_RENDU = 500  # lignes converties en objets Python à la fois


def en_json(valeur: object) -> object:
    """Une valeur Arrow (``to_pylist``) écrite comme le gold l'écrit, à toute profondeur."""
    if isinstance(valeur, datetime):
        return texte_instant(valeur)
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return str(valeur)
    if isinstance(valeur, Mapping):
        return {cle: en_json(v) for cle, v in valeur.items()}
    if isinstance(valeur, list | tuple):
        return [en_json(v) for v in valeur]
    return valeur


def rendre(
    table: pa.Table, format_: Format, colonnes: Sequence[str] | None = None
) -> Iterator[str]:
    """Les lignes de la sortie ; JSON Lines par ``en_json``, le reste comme le silver."""
    if format_ is not Format.JSONL:
        yield from etat_silver.rendre(table, format_, colonnes)
        return
    noms = etat_silver.colonnes_a_rendre(table, colonnes)
    # Par lots : la fiche entière en objets Python passait le seuil de 512 Mo (552 Mo).
    for lot in table.select(noms).to_batches(max_chunksize=LOT_RENDU):
        for ligne in lot.to_pylist():
            yield json.dumps(en_json(ligne), ensure_ascii=False, separators=(",", ":"))


def _date(valeur: object) -> str:
    return "?" if valeur is None else str(en_json(valeur))


def _liste(valeurs: Sequence[Any] | None) -> str:
    return ", ".join(str(v) for v in valeurs or ()) or "—"


def fiche_en_texte(fiche: Mapping[str, Any]) -> str:
    """La fiche d'un CIS, en texte ; ``fiche`` est une ligne de la vue (``to_pylist``)."""
    lignes = [f"CIS {fiche['code_cis']} — {fiche['denomination'] or '(dénomination inconnue)'}"]
    lignes.append(f"État au {_date(fiche['instant'])}")
    if not fiche["dans_referentiel"]:
        lignes.append(
            "Absent du référentiel des spécialités (CIS_bdpm.txt) : fiche partielle, faite des"
            " seuls fichiers qui citent ce CIS."
        )
    else:
        lignes.append(
            f"Spécialité : {fiche['forme_pharmaceutique']} ; voie(s) "
            f"{_liste(fiche['voies_administration'])} ; {fiche['statut_amm']} depuis le"
            f" {_date(fiche['date_amm'])} ({fiche['type_procedure_amm']}) ;"
            f" {fiche['etat_commercialisation']} ; titulaire(s) {_liste(fiche['titulaires'])}"
        )
        if fiche["surveillance_renforcee"]:
            lignes.append("Sous surveillance renforcée.")
    if fiche["mitm"]:
        lignes.append(
            f"Médicament d'intérêt thérapeutique majeur (ATC {fiche['code_atc']}, liste publiée"
            f" le {_date(fiche['date_publication_mitm'])})."
        )
    lignes += _section(
        "Présentations",
        fiche["presentations"],
        lambda p: (
            f"{p['code_cip13']} : {p['libelle_presentation']} ; {p['etat_commercialisation']} ;"
            f" taux {_liste(p['taux_remboursement'])} ; prix public"
            f" {en_json(p['prix_public']) or '—'} €"
        ),
    )
    lignes += _section(
        "Composition",
        fiche["composition"],
        lambda c: (
            f"{c['designation_element']} : {c['denomination_substance']} {c['dosage'] or ''}"
            f" ({c['nature_composant']})".replace("  ", " ")
        ),
    )
    lignes += _section(
        "Groupes génériques",
        fiche["groupes_generiques"],
        lambda g: (
            f"groupe {g['identifiant_groupe']} ({g['libelle_groupe']}), type {g['type_generique']}"
        ),
    )
    lignes += _section("Conditions de prescription", fiche["conditions_prescription"], str)
    for genre in ("smr", "asmr"):
        lignes += _section(
            f"Avis {genre.upper()}",
            fiche[f"avis_{genre}"],
            lambda a, g=genre: (
                f"{_date(a['date_avis'])} : {a[f'valeur_{g}']}"
                f" ({a['motif_evaluation']}, {a['code_dossier_has']}) {_liste(a['liens_avis'])}"
            ),
        )
    lignes += _section(
        "Disponibilité (signalements en cours)",
        fiche["disponibilite"],
        lambda s: (
            f"{s['libelle_statut']} depuis le {_date(s['date_debut'])}"
            f"{' (annoncé, pas encore commencé)' if s['debut_a_venir'] else ''}, mis à jour le"
            f" {_date(s['date_mise_a_jour'])} ; vise "
            f"{s['code_cip13'] or 'toutes les présentations de la spécialité'} ; {s['lien_ansm']}"
        ),
        vide="aucun signalement dans le fichier de disponibilité (ce n'est pas « disponible »)",
    )
    lignes += _section(
        "Informations importantes en cours",
        fiche["infos_importantes"],
        lambda i: f"du {_date(i['date_debut'])} au {_date(i['date_fin'])} : {i['texte_et_lien']}",
    )
    if fiche["colonnes_illisibles"]:
        lignes.append(
            "Valeurs illisibles dans la source, laissées vides : "
            + ", ".join(fiche["colonnes_illisibles"])
        )
    lignes += _section(
        "Sources",
        fiche["provenance"],
        lambda p: (
            f"{p['fichier']} : observée depuis le {_date(p['connu_depuis'])}"
            + (f", source du {p['date_source']}" if p["date_source"] else ", source non datée")
        ),
    )
    return "\n".join(lignes)


def _section(
    titre: str, elements: Sequence[Any] | None, decrire: Any, vide: str = "—"
) -> list[str]:
    if not elements:
        return [f"{titre} : {vide}"]
    return [f"{titre} ({len(elements)}) :", *(f"  - {decrire(e)}" for e in elements)]
