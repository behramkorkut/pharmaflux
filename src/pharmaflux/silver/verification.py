"""Vérifier le silver contre l'archive : l'état à chaque observation égale le snapshot (G).

Pour chaque entité, les archives et leur verdict viennent des **bilans** de la
sortie de ``evenements`` (``decision`` : ``retenu``, ``confirme``, ``ecarte``,
``en_attente``), jamais des événements. Le snapshot d'une archive retenue ou
confirmée est recalculé depuis le bronze, réduit à une empreinte par
identité (valeurs triées et occurrences, la réduction de ``verifier-bus``) ;
l'état du silver à l'horodatage de l'archive est réduit de même et comparé.
Une archive écartée n'a bougé aucune version : son état doit être celui du
dernier snapshot retenu avant elle. Une archive en attente à la fin du
bronze n'a pas d'événement : elle est dite, pas vérifiée. Le temps de la
connaissance est l'horodatage de l'archive, à la seconde.

S'y ajoutent les **invariants du SCD2**, en DuckDB sur les Parquet de la
table : une seule version ouverte par identité, aucun chevauchement de
validités d'une identité, ``fin > debut``, chaque identifiant d'événement au
plus une fois en ouverture et une fois en fermeture, et les comptes
d'ouvertures et de fermetures égaux à ceux des bilans. Toute différence ou
tout invariant tombé : code 2.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.dataset as ds
from pyiceberg.table import Table

from pharmaflux import bronze
from pharmaflux.contrats.modele import Contrat
from pharmaflux.evenements import rejeu, snapshot
from pharmaflux.evenements.snapshot import SEPARATEUR_EMPREINTE, Identite, Snapshot
from pharmaflux.evenements.volume import Decision
from pharmaflux.silver import SilverRefuse
from pharmaflux.silver.entrepot import Entrepot, chemins_parquet
from pharmaflux.silver.etat import etat_a
from pharmaflux.silver.schema import colonnes_du_contrat
from pharmaflux.silver.sql import connexion_verrouillee

Journal = Callable[[str], None]
Empreintes = dict[
    str, bytes
]  # identité (celle d'``appliquer``) → empreinte de (valeurs, occurrences)
EXEMPLES = 3
LOIN = "TIMESTAMPTZ '9999-12-31 00:00:00+00'"  # une fin ouverte, pour les chevauchements


@dataclass(frozen=True, slots=True)
class VerificationArchive:
    archive: str  # chemin relatif
    decision: str
    observee: str  # ISO Z
    identites: int  # dans la référence
    differences: tuple[str, ...]
    duree_s: float

    @property
    def conforme(self) -> bool:
        return not self.differences


@dataclass(slots=True)
class VerificationEntite:
    entite: str
    archives: list[VerificationArchive] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)  # ceux qui tombent
    notes: list[str] = field(default_factory=list)  # en attente, table absente…
    versions: int = 0
    ouvertes: int = 0
    fichiers: int = 0
    snapshots: int = 0

    @property
    def conforme(self) -> bool:
        return all(a.conforme for a in self.archives) and not self.invariants


@dataclass(slots=True)
class Rapport:
    entites: list[VerificationEntite] = field(default_factory=list)
    duree_s: float = 0.0

    @property
    def code_sortie(self) -> int:
        return 0 if all(e.conforme for e in self.entites) else 2

    @property
    def archives_verifiees(self) -> int:
        return sum(len(e.archives) for e in self.entites)

    @property
    def archives_conformes(self) -> int:
        return sum(1 for e in self.entites for a in e.archives if a.conforme)


def verifier(
    entrepot: Entrepot,
    sortie: Path,
    racine: Path,
    contrats: dict[str, Contrat],
    selection: list[str],
    *,
    journal: Journal | None = None,
) -> Rapport:
    """Chaque entité de ``selection`` ; ``SilverRefuse`` si la référence n'existe pas."""
    dire = journal or (lambda _: None)
    bilans_dir = sortie / rejeu.DOSSIER_BILANS
    if not bilans_dir.is_dir():
        raise SilverRefuse(f"référence introuvable : aucun bilan dans {sortie} ({bilans_dir})")
    depart = time.monotonic()
    rapport = Rapport()
    for identifiant in selection:
        contrat = contrats[identifiant]
        resultat = VerificationEntite(identifiant)
        rapport.entites.append(resultat)
        table = entrepot.table(identifiant)
        bilans = sorted((bilans_dir / identifiant).glob("*.json"))
        if table is None:
            if bilans:
                resultat.invariants.append("aucune table dans l'entrepôt pour cette entité")
            else:
                resultat.notes.append("ni bilan ni table : rien à vérifier")
            continue
        if not bilans:
            resultat.invariants.append(f"aucun bilan dans {bilans_dir / identifiant}")
            continue
        dire(f"{identifiant} : {len(bilans)} archive(s) à vérifier")
        _verifier_archives(table, contrat, bilans, racine, resultat, dire)
        _verifier_invariants(table, bilans, resultat)
    rapport.duree_s = time.monotonic() - depart
    return rapport


def _verifier_archives(
    table: Table,
    contrat: Contrat,
    bilans: list[Path],
    racine: Path,
    resultat: VerificationEntite,
    dire: Journal,
) -> None:
    colonnes = colonnes_du_contrat(table.schema().as_arrow())
    par_chemin = {
        a.relatif(racine): a
        for a in bronze.lister(racine, contrat.identifiant.partition(".")[0], contrat.fichier)
    }
    attendu_retenu: Empreintes = {}
    for chemin in bilans:
        bilan = json.loads(chemin.read_text(encoding="utf-8"))
        decision = str(bilan["decision"])
        relatif = str(bilan["archive"])
        archive = par_chemin.get(relatif)
        depart = time.monotonic()
        if archive is None:
            resultat.archives.append(
                VerificationArchive(relatif, decision, "?", 0, ("archive absente du bronze",), 0.0)
            )
            continue
        if decision == Decision.EN_ATTENTE:
            resultat.notes.append(
                f"{Path(relatif).name} en attente : aucun événement, non vérifiée"
            )
            continue
        if decision in (Decision.RETENU, Decision.CONFIRME):
            attendu_retenu = _empreintes_snapshot(snapshot.lire(contrat, archive, racine))
        attendu = attendu_retenu  # une archive écartée n'a bougé aucune version
        obtenu = _empreintes_silver(
            etat_a(table, archive.horodatage), colonnes, contrat.cle.colonnes, contrat.cle.unique
        )
        differences = _comparer(obtenu, attendu)
        verification = VerificationArchive(
            relatif,
            decision,
            archive.horodatage.strftime("%Y-%m-%dT%H:%M:%SZ"),
            len(attendu),
            tuple(differences),
            time.monotonic() - depart,
        )
        resultat.archives.append(verification)
        verdict = "conforme" if verification.conforme else "DIFFÉRENCE"
        dire(f"{contrat.identifiant} {Path(relatif).name} ({decision}) : {verdict}")


def _verifier_invariants(table: Table, bilans: list[Path], resultat: VerificationEntite) -> None:
    """Les invariants du SCD2, en DuckDB sur les Parquet de la table (aucun accès fichier)."""
    resultat.snapshots = len(table.metadata.snapshots)
    chemins = chemins_parquet(table)
    resultat.fichiers = len(chemins)
    schema = table.schema().as_arrow()
    con = connexion_verrouillee()
    con.register(
        "t",
        ds.dataset(chemins, format="parquet", schema=schema) if chemins else schema.empty_table(),
    )
    total, ouvertes, fermees = _ligne(
        con, "SELECT count(*), count(*) - count(fin_validite), count(fin_validite) FROM t"
    )
    resultat.versions, resultat.ouvertes = total, ouvertes
    doubles = _ligne(
        con,
        "SELECT count(*) FROM (SELECT identite FROM t WHERE fin_validite IS NULL"
        " GROUP BY identite HAVING count(*) > 1)",
    )[0]
    if doubles:
        resultat.invariants.append(f"{doubles} identité(s) avec plusieurs versions ouvertes")
    inversees = _ligne(con, "SELECT count(*) FROM t WHERE fin_validite <= debut_validite")[0]
    if inversees:
        resultat.invariants.append(f"{inversees} version(s) dont la fin ne suit pas le début")
    chevauchements = _ligne(
        con,
        "SELECT count(*) FROM t a JOIN t b ON a.identite = b.identite"
        " AND a.id_ouverture < b.id_ouverture"
        f" AND a.debut_validite < coalesce(b.fin_validite, {LOIN})"
        f" AND b.debut_validite < coalesce(a.fin_validite, {LOIN})",
    )[0]
    if chevauchements:
        resultat.invariants.append(f"{chevauchements} chevauchement(s) de validités")
    ouvertures_doubles = _ligne(con, "SELECT count(*) - count(DISTINCT id_ouverture) FROM t")[0]
    fermetures_doubles = _ligne(
        con, "SELECT count(id_fermeture) - count(DISTINCT id_fermeture) FROM t"
    )[0]
    if ouvertures_doubles or fermetures_doubles:
        resultat.invariants.append(
            f"identifiants d'événements répétés : {ouvertures_doubles} en ouverture,"
            f" {fermetures_doubles} en fermeture"
        )
    con.close()
    comptes: Counter[str] = Counter()
    for chemin in bilans:
        bilan = json.loads(chemin.read_text(encoding="utf-8"))
        ecart = bilan.get("ecart")
        if ecart:
            comptes.update({str(k): int(v) for k, v in (ecart.get("evenements") or {}).items()})
        elif bilan.get("decision") in (Decision.RETENU, Decision.CONFIRME):
            # Le premier snapshot n'a pas d'écart : une creee par ligne bien formée (ADR 0006).
            comptes["creee"] += int(bilan["lignes_bien_formees"])
    attendu_ouvertures = comptes["creee"] + comptes["modifiee"]
    attendu_fermetures = comptes["modifiee"] + comptes["supprimee"]
    if total != attendu_ouvertures or fermees != attendu_fermetures:
        resultat.invariants.append(
            f"{total} version(s) et {fermees} fermeture(s), les bilans comptent"
            f" {attendu_ouvertures} ouverture(s) et {attendu_fermetures} fermeture(s)"
        )


def _ligne(con: duckdb.DuckDBPyConnection, requete: str) -> tuple[int, ...]:
    ligne = con.sql(requete).fetchone()
    assert ligne is not None
    return tuple(int(v) for v in ligne)


def _empreinte(valeurs: Mapping[str, str | None], occurrences: int) -> bytes:
    """La réduction de ``verifier-bus`` : (colonnes triées, occurrences), hachés."""
    contenu = json.dumps([sorted(valeurs.items()), occurrences], ensure_ascii=False)
    return hashlib.sha256(contenu.encode("utf-8")).digest()


def _empreintes_snapshot(s: Snapshot) -> Empreintes:
    """Le snapshot réduit comme ``etat_du_snapshot`` puis ``_empreintes`` le feraient, sans
    construire l'état complet : une ligne à la fois."""
    noms = s.contrat.noms_colonnes
    if s.identite is Identite.CLE:
        ordre = [s.contrat.cle.colonnes.index(nom) for nom in sorted(s.contrat.cle.colonnes)]
        return {
            SEPARATEUR_EMPREINTE.join(cle[i] for i in ordre): _empreinte(
                dict(zip(noms, ligne.normalisees, strict=True)), 1
            )
            for cle, ligne in s.par_cle.items()
        }
    return {
        empreinte: _empreinte(dict(zip(noms, ligne.normalisees, strict=True)), n)
        for empreinte, (ligne, n) in s.par_ligne.items()
    }


def _empreintes_silver(
    versions: pa.Table, colonnes: list[str], cle: tuple[str, ...], par_cle: bool
) -> Empreintes:
    """Les versions valides réduites comme l'état d'``appliquer`` : par clé, ou par empreinte
    avec le nombre d'occurrences (les rangs)."""
    empreintes: Empreintes = {}
    comptes: Counter[str] = Counter()
    valeurs_par_empreinte: dict[str, dict[str, str | None]] = {}
    tri = sorted(cle)
    for lot in versions.select([*colonnes, "empreinte_ligne"]).to_batches(max_chunksize=5_000):
        for ligne in lot.to_pylist():
            valeurs = {nom: ligne[nom] for nom in colonnes}
            if par_cle:
                identite = SEPARATEUR_EMPREINTE.join(str(ligne[nom]) for nom in tri)
                empreintes[identite] = _empreinte(valeurs, 1)
            else:
                empreinte = str(ligne["empreinte_ligne"])
                comptes[empreinte] += 1
                valeurs_par_empreinte.setdefault(empreinte, valeurs)
    if not par_cle:
        for empreinte, n in comptes.items():
            empreintes[empreinte] = _empreinte(valeurs_par_empreinte[empreinte], n)
    return empreintes


def _comparer(silver: Empreintes, attendu: Empreintes) -> list[str]:
    differences = []
    seulement_silver = sorted(silver.keys() - attendu.keys())
    seulement_archive = sorted(attendu.keys() - silver.keys())
    autres = sorted(k for k in silver.keys() & attendu.keys() if silver[k] != attendu[k])
    for libelle, identites in (
        ("seulement dans le silver", seulement_silver),
        ("seulement dans l'archive", seulement_archive),
        ("valeurs ou occurrences différentes", autres),
    ):
        if identites:
            exemples = ", ".join(repr(i) for i in identites[:EXEMPLES])
            suite = " …" if len(identites) > EXEMPLES else ""
            differences.append(f"{len(identites)} identité(s) {libelle} : {exemples}{suite}")
    return differences
