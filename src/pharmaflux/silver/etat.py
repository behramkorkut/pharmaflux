"""« État à une date » : les versions valides à un instant, et leur rendu (F).

L'instant est en UTC, à la seconde, sous trois formes seulement :
``2026-10-26T14:00:00Z``, ``2026-10-26T16:00:00+02:00`` (un décalage), ou une
date seule, qui vaut minuit UTC. Refusés : un instant sans fuseau, une fraction
de seconde (même ``.000``), une heure sans les secondes, la forme compacte ou
un espace à la place du ``T``. La règle de validité, ``debut_validite <= a`` et
(``fin_validite`` nulle ou ``> a``), est poussée entière à PyIceberg, qui
élague les fichiers par leurs bornes puis filtre dans Arrow ; aucun masque
Arrow maison (§0 K.6). Avant la première observation, aucune version ; après
la dernière, les versions ouvertes : dans les deux cas une réponse, code 0,
et un message sur la sortie d'erreur.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
from pyiceberg.expressions import BooleanExpression
from pyiceberg.table import Table

from pharmaflux.silver import Format, SilverRefuse
from pharmaflux.silver.expressions import egal, est_nul, et, inferieur_ou_egal, ou, superieur
from pharmaflux.silver.schema import litteral, texte_instant

_DATE_SEULE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_A_LA_SECONDE = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
_INSTANT = re.compile(_A_LA_SECONDE + r"(Z|[+-]\d{2}:\d{2})$")
_SANS_FUSEAU = re.compile(_A_LA_SECONDE + "$")
_FRACTION = re.compile(_A_LA_SECONDE + r"[.,]\d")
FORMES_ACCEPTEES = "AAAA-MM-JJ, AAAA-MM-JJThh:mm:ssZ ou AAAA-MM-JJThh:mm:ss±hh:mm"


def lire_instant(texte: str) -> datetime:
    """L'instant demandé, en UTC ; ``SilverRefuse`` hors des trois formes acceptées."""
    if _DATE_SEULE.match(texte) or _INSTANT.match(texte):
        try:  # bien formé, mais un 30 février ou un treizième mois reste impossible
            valeur = datetime.fromisoformat(texte)
        except ValueError as exc:
            raise SilverRefuse(f"instant illisible : {texte!r} ({FORMES_ACCEPTEES})") from exc
        if valeur.tzinfo is None:  # la date seule : minuit UTC
            valeur = valeur.replace(tzinfo=UTC)
    elif _SANS_FUSEAU.match(texte):
        raise SilverRefuse(
            f"instant sans fuseau : {texte!r} ; écris-le en UTC (…Z) ou avec un décalage (+02:00)"
        )
    elif _FRACTION.match(texte):
        raise SilverRefuse(
            f"instant à la fraction de seconde : {texte!r} ; les observations sont à la seconde"
        )
    else:
        raise SilverRefuse(f"instant illisible : {texte!r} ({FORMES_ACCEPTEES})")
    return valeur.astimezone(UTC)


def filtre_validite(instant: datetime) -> BooleanExpression:
    """Les versions valides à ``instant`` : ouvertes à cet instant, borne de fin exclue."""
    a = litteral(instant)
    return et(
        inferieur_ou_egal("debut_validite", a),
        ou(est_nul("fin_validite"), superieur("fin_validite", a)),
    )


def etat_a(table: Table, instant: datetime, filtres: Mapping[str, str] | None = None) -> pa.Table:
    """Les versions valides à ``instant``, filtrées par égalité sur des colonnes du contrat."""
    expression = filtre_validite(instant)
    colonnes = set(table.schema().as_arrow().names)
    for colonne, valeur in (filtres or {}).items():
        if colonne not in colonnes:
            raise SilverRefuse(
                f"colonne inconnue : {colonne} ; colonnes : {', '.join(sorted(colonnes))}"
            )
        expression = et(expression, egal(colonne, valeur))
    return table.scan(row_filter=expression).to_arrow()


def bornes(table: Table) -> tuple[datetime | None, datetime | None]:
    """La première observation et la dernière (début ou fin) que la table connaît."""
    instants = table.scan(selected_fields=("debut_validite", "fin_validite")).to_arrow()
    if not instants.num_rows:
        return None, None
    premiere = pc.min(instants["debut_validite"]).as_py()
    derniere = pc.max(instants["debut_validite"]).as_py()
    fins = instants["fin_validite"].drop_null()
    if len(fins):
        derniere = max(derniere, pc.max(fins).as_py())
    return premiere, derniere


def lire_filtres(textes: Sequence[str]) -> dict[str, str]:
    """``--ou colonne=valeur``, répétable."""
    filtres: dict[str, str] = {}
    for texte in textes:
        colonne, separateur, valeur = texte.partition("=")
        if not separateur or not colonne:
            raise SilverRefuse(f"--ou {texte!r} : colonne=valeur attendu")
        filtres[colonne] = valeur
    return filtres


def ordonner(arrow: pa.Table) -> pa.Table:
    """Un ordre lisible et stable : identité, puis début de validité."""
    return arrow.sort_by([("identite", "ascending"), ("debut_validite", "ascending")])


def colonnes_a_rendre(arrow: pa.Table, choisies: Sequence[str] | None) -> list[str]:
    """Les colonnes demandées (vérifiées), ou toutes : celles du contrat puis celles de version."""
    noms = arrow.schema.names
    if not choisies:
        return list(noms)
    inconnues = [nom for nom in choisies if nom not in noms]
    if inconnues:
        raise SilverRefuse(f"colonne(s) inconnue(s) : {', '.join(inconnues)}")
    return list(choisies)


def rendre(
    arrow: pa.Table, format_: Format, colonnes: Sequence[str] | None = None
) -> Iterator[str]:
    """Les lignes de la sortie : JSON Lines, tableau texte ou CSV ; instants en ``…Z``."""
    noms = colonnes_a_rendre(arrow, colonnes)
    lignes = (dict(zip(noms, valeurs, strict=True)) for valeurs in _valeurs(arrow, noms))
    if format_ is Format.JSONL:
        for ligne in lignes:
            yield json.dumps(ligne, ensure_ascii=False, separators=(",", ":"), default=str)
    elif format_ is Format.CSV:
        tampon = io.StringIO()
        plume = csv.writer(tampon, lineterminator="\n")
        plume.writerow(noms)
        yield tampon.getvalue().rstrip("\n")
        for ligne in lignes:
            tampon.seek(0)
            tampon.truncate()
            plume.writerow([_cellule(ligne[nom]) for nom in noms])
            yield tampon.getvalue().rstrip("\n")
    else:
        cellules = [[_cellule(ligne[nom]) for nom in noms] for ligne in lignes]
        largeurs = [
            max(len(nom), *(len(ligne[i]) for ligne in cellules)) if cellules else len(nom)
            for i, nom in enumerate(noms)
        ]
        yield "  ".join(nom.ljust(largeurs[i]) for i, nom in enumerate(noms)).rstrip()
        yield "  ".join("-" * largeur for largeur in largeurs)
        for rangee in cellules:
            yield "  ".join(valeur.ljust(largeurs[i]) for i, valeur in enumerate(rangee)).rstrip()


def _valeurs(arrow: pa.Table, noms: Sequence[str]) -> Iterator[list[Any]]:
    """Les lignes, colonne par colonne converties : instants en texte, le reste tel quel."""
    colonnes = []
    for nom in noms:
        colonne = arrow[nom]
        if pa.types.is_timestamp(colonne.type):
            colonnes.append([None if v is None else texte_instant(v) for v in colonne.to_pylist()])
        else:
            colonnes.append(colonne.to_pylist())
    for i in range(arrow.num_rows):
        yield [colonne[i] for colonne in colonnes]


def _cellule(valeur: object) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, str):
        return valeur
    if isinstance(valeur, bool):
        return "true" if valeur else "false"
    if isinstance(valeur, list | dict):
        return json.dumps(valeur, ensure_ascii=False, separators=(",", ":"))
    return str(valeur)


__all__ = [
    "bornes",
    "etat_a",
    "filtre_validite",
    "lire_filtres",
    "lire_instant",
    "ordonner",
    "rendre",
]
