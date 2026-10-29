"""Les contrôles de qualité du gold à un instant (addendum 1, G).

**La règle qui classe** : un contrôle est *bloquant* quand il vérifie un
invariant que la chaîne garantit elle-même (contrats, garde-fou de volume,
SCD2, normalisation) ; s'il tombe, c'est le code ou le silver qui est faux,
et rien de ce que le gold affiche n'est sûr. Il est *mesuré* quand il
constate un fait de la source, que le gold montre sans pouvoir le corriger :
une source publique ne fait pas tomber la chaîne. Un contrôle mesuré
s'affiche toujours, même à 0. Un bloquant non nul donne le code 2.

Les comptes par entité et par colonne viennent du typage (``EntiteTypee``),
les contrôles du référentiel d'une requête DuckDB sur les entités typées,
les volumes d'un second état, juste avant le dernier changement de l'entité.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pyarrow.compute as pc
from pyiceberg.table import Table

from pharmaflux.contrats.modele import Contrat
from pharmaflux.gold import Classe
from pharmaflux.gold.sql import connexion, etats_types
from pharmaflux.gold.typage import EntiteTypee
from pharmaflux.silver import SilverRefuse
from pharmaflux.silver.entrepot import Entrepot
from pharmaflux.silver.etat import filtre_validite
from pharmaflux.silver.schema import texte_instant

# Les onze entités : les contrôles du référentiel les croisent toutes.
ENTITES_GOLD = (
    "bdpm.asmr",
    "bdpm.compositions",
    "bdpm.conditions_prescription",
    "bdpm.disponibilite",
    "bdpm.generiques",
    "bdpm.infos_importantes",
    "bdpm.liens_ct",
    "bdpm.mitm",
    "bdpm.presentations",
    "bdpm.smr",
    "bdpm.specialites",
)
ENTITES_CIS = tuple(e for e in ENTITES_GOLD if e not in ("bdpm.specialites", "bdpm.liens_ct"))

INVARIANT = "invariant de la chaîne : s'il tombe, le code ou le silver est faux"
FAIT_SOURCE = "fait de la source : montré, jamais corrigé ni absorbé"

Detail = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class Controle:
    numero: int
    nom: str
    classe: Classe
    valeur: int
    detail: Detail
    regle: str

    @property
    def tombe(self) -> bool:
        return self.classe is Classe.BLOQUANT and self.valeur > 0


@dataclass(slots=True)
class RapportQualite:
    instant: datetime
    controles: list[Controle] = field(default_factory=list)

    @property
    def bloquants(self) -> list[Controle]:
        return [controle for controle in self.controles if controle.tombe]

    @property
    def code_sortie(self) -> int:
        return 2 if self.bloquants else 0

    def resume(self) -> str:
        nb_bloquants = sum(1 for c in self.controles if c.classe is Classe.BLOQUANT)
        nb_mesures = len(self.controles) - nb_bloquants
        verdict = (
            f"{len(self.bloquants)} bloquant(s) tombé(s)"
            if self.bloquants
            else "aucun bloquant ne tombe"
        )
        return (
            f"{len(self.controles)} contrôles à {texte_instant(self.instant)} :"
            f" {nb_bloquants} bloquants, {nb_mesures} mesurés ; {verdict}."
        )


def exiger_les_onze(entrepot: Entrepot, instant: datetime) -> None:
    """Refuse un entrepôt sans les onze entités, ou un instant où l'une n'est pas encore observée.

    Avant la première observation du fichier de disponibilité, la vue dirait
    « aucun signalement » de toutes les présentations, et les contrôles
    compteraient comme absents des spécialités des CIS que l'on n'a pas encore
    lus : ce serait affirmer ce que l'on ne sait pas.
    """
    manquantes = [e for e in ENTITES_GOLD if entrepot.table(e) is None]
    if manquantes:
        raise SilverRefuse(f"le gold croise les onze entités ; absentes : {', '.join(manquantes)}")
    premieres: dict[str, datetime | None] = {}
    for entite in ENTITES_GOLD:
        table = entrepot.table(entite)
        assert table is not None
        premieres[entite] = _premiere(table)
    pas_encore = [e for e, p in premieres.items() if p is None or p > instant]
    if pas_encore:
        connues = [p for p in premieres.values() if p is not None]
        conseil = (
            f" ; les onze sont observées à partir de {texte_instant(max(connues))}"
            if len(connues) == len(premieres)
            else " ; une entité n'a encore aucune observation"
        )
        raise SilverRefuse(
            f"à {texte_instant(instant)}, pas encore observées : {', '.join(pas_encore)}{conseil}"
        )


def controler(
    entrepot: Entrepot, contrats: Mapping[str, Contrat], instant: datetime
) -> RapportQualite:
    """Les quatorze contrôles à ``instant`` ; refusés sans les onze entités observées."""
    exiger_les_onze(entrepot, instant)
    etats = etats_types(entrepot, contrats, instant)
    rapport = RapportQualite(instant)
    rapport.controles += _invariants(entrepot, etats, instant)
    rapport.controles += _referentiel(etats)
    rapport.controles += _anomalies(etats)
    rapport.controles.append(_volumes(entrepot, etats, instant))
    return rapport


def _invariants(
    entrepot: Entrepot, etats: Mapping[str, EntiteTypee], instant: datetime
) -> list[Controle]:
    cles = {e: t.doublons_cle for e, t in etats.items() if t.doublons_cle is not None}
    identites = {e: t.doublons_identite for e, t in etats.items()}
    non_typables = {
        f"{e}.{colonne}": n for e, t in etats.items() for colonne, n in t.non_typables.items()
    }
    vides: dict[str, int] = {}
    for entite, etat in etats.items():
        table = entrepot.table(entite)
        assert table is not None
        if etat.table.num_rows == 0 and _premiere(table) is not None:
            premiere = _premiere(table)
            assert premiere is not None
            if premiere <= instant:
                vides[entite] = 1
    return [
        Controle(
            1,
            "unicité des clés déclarées uniques (lignes en trop)",
            Classe.BLOQUANT,
            sum(cles.values()),
            cles,
            f"{INVARIANT} (un snapshot à clé non unique est écarté entier)",
        ),
        Controle(
            2,
            "une version par identité (versions en trop)",
            Classe.BLOQUANT,
            sum(identites.values()),
            identites,
            f"{INVARIANT} (SCD2)",
        ),
        Controle(
            3,
            "valeurs canoniques non typables",
            Classe.BLOQUANT,
            sum(non_typables.values()),
            non_typables,
            f"{INVARIANT} (forme canonique de la normalisation)",
        ),
        Controle(
            4,
            "entités vides après leur première observation",
            Classe.BLOQUANT,
            len(vides),
            vides,
            f"{INVARIANT} (le garde-fou de volume écarte un snapshot vide)",
        ),
    ]


# Les contrôles du référentiel : (numéro, nom, requête) ; la requête rend une ligne de comptes,
# la première colonne est la valeur du contrôle, les autres son détail.
_REQUETES: tuple[tuple[int, str, str], ...] = (
    (
        5,
        "présentations dont le CIS est absent des spécialités",
        """
        SELECT count(*) AS presentations, count(DISTINCT code_cis) AS cis
        FROM presentations WHERE code_cis NOT IN (SELECT code_cis FROM specialites)
        """,
    ),
    (
        7,
        "spécialités sans présentation",
        """
        SELECT count(*) AS specialites
        FROM specialites WHERE code_cis NOT IN (SELECT code_cis FROM presentations)
        """,
    ),
    (
        8,
        "CIP13 de la disponibilité absents des présentations",
        """
        SELECT count(*) AS lignes, count(DISTINCT code_cip13) AS cip13
        FROM disponibilite
        WHERE code_cip13 IS NOT NULL
          AND code_cip13 NOT IN (SELECT code_cip13 FROM presentations)
        """,
    ),
    (
        9,
        "signalements sans CIP13 dont la spécialité n'a aucune présentation",
        """
        SELECT count(DISTINCT code_cis) AS cis, count(*) AS lignes
        FROM disponibilite
        WHERE code_cip13 IS NULL AND code_cis NOT IN (SELECT code_cis FROM presentations)
        """,
    ),
    (
        10,
        "dossiers SMR et ASMR sans lien vers l'avis",
        """
        WITH sans_lien AS (
          SELECT 'smr' AS fichier, code_dossier_has FROM smr
          UNION SELECT 'asmr', code_dossier_has FROM asmr
        )
        SELECT count(*) AS smr_plus_asmr,
          count(*) FILTER (WHERE fichier = 'smr') AS smr,
          count(*) FILTER (WHERE fichier = 'asmr') AS asmr
        FROM sans_lien
        WHERE code_dossier_has NOT IN (SELECT code_dossier_has FROM liens_ct)
        """,
    ),
    (
        11,
        "lignes répétées des fichiers sans clé unique (occurrences au-delà de la première)",
        """
        SELECT
          (SELECT count(*) FROM disponibilite WHERE rang > 1)
          + (SELECT count(*) FROM smr WHERE rang > 1)
          + (SELECT count(*) FROM asmr WHERE rang > 1) AS lignes,
          (SELECT count(*) FROM disponibilite WHERE rang > 1) AS disponibilite,
          (SELECT count(*) FROM smr WHERE rang > 1) AS smr,
          (SELECT count(*) FROM asmr WHERE rang > 1) AS asmr
        """,
    ),
)


def _referentiel(etats: Mapping[str, EntiteTypee]) -> list[Controle]:
    con = connexion(etats)
    controles = []
    for numero, nom, requete in _REQUETES:
        ligne = con.sql(requete).fetchone()
        assert ligne is not None
        noms = [colonne[0] for colonne in con.sql(requete).description]
        detail = dict(zip(noms, (int(v) for v in ligne), strict=True))
        controles.append(Controle(numero, nom, Classe.MESURE, int(ligne[0]), detail, FAIT_SOURCE))
    # 6 : par entité, puis l'union (un CIS cité par plusieurs fichiers compte une fois).
    autres = " UNION ".join(f"SELECT code_cis FROM {e.partition('.')[2]}" for e in ENTITES_CIS)
    union = con.sql(
        f"SELECT count(*) FROM ({autres}) WHERE code_cis NOT IN (SELECT code_cis FROM specialites)"
    ).fetchone()
    assert union is not None
    par_entite: dict[str, int] = {}
    for entite in ENTITES_CIS:
        nom = entite.partition(".")[2]
        compte = con.sql(
            f"SELECT count(DISTINCT code_cis) FROM {nom}"
            " WHERE code_cis NOT IN (SELECT code_cis FROM specialites)"
        ).fetchone()
        assert compte is not None
        par_entite[nom] = int(compte[0])
    controles.append(
        Controle(
            6,
            "CIS des autres fichiers absents des spécialités (CIS distincts)",
            Classe.MESURE,
            int(union[0]),
            par_entite,
            FAIT_SOURCE,
        )
    )
    return sorted(controles, key=lambda c: c.numero)


def _anomalies(etats: Mapping[str, EntiteTypee]) -> list[Controle]:
    illisibles = {
        f"{e}.{colonne} ({regle})": n
        for e, t in etats.items()
        for (colonne, regle), n in sorted(t.illisibles.items())
    }
    autres = {
        f"{e}.{colonne} ({regle})": n
        for e, t in etats.items()
        for (colonne, regle), n in sorted(t.autres_anomalies.items())
    }
    return [
        Controle(
            12,
            "valeurs illisibles, par colonne (typées vides, brutes dans le silver)",
            Classe.MESURE,
            sum(illisibles.values()),
            illisibles,
            FAIT_SOURCE,
        ),
        Controle(
            13,
            "autres anomalies de valeur, par colonne (forme, vraisemblance, valeur manquante)",
            Classe.MESURE,
            sum(autres.values()),
            autres,
            FAIT_SOURCE,
        ),
    ]


def _volumes(entrepot: Entrepot, etats: Mapping[str, EntiteTypee], instant: datetime) -> Controle:
    """Le volume à l'instant, et l'écart à l'état juste avant le dernier changement."""
    detail: dict[str, object] = {}
    for entite, etat in etats.items():
        table = entrepot.table(entite)
        assert table is not None
        lignes = etat.table.num_rows
        changement = _dernier_changement(table, instant)
        premiere = _premiere(table)
        if changement is None or changement == premiere:
            detail[entite] = {"lignes": lignes, "depuis": "état initial"}
            continue
        avant = _compter(table, changement - timedelta(seconds=1))
        detail[entite] = {
            "lignes": lignes,
            "avant": avant,
            "ecart": lignes - avant,
            "ecart_pct": round(100 * (lignes - avant) / avant, 2) if avant else None,
            "depuis": texte_instant(changement),
        }
    total = sum(etat.table.num_rows for etat in etats.values())
    return Controle(
        14,
        "volumes par entité, écart au dernier changement",
        Classe.MESURE,
        total,
        detail,
        f"{FAIT_SOURCE} ; le seul volume bloquant est le vide (contrôle 4)",
    )


def _instants(table: Table) -> tuple[list[datetime], list[datetime]]:
    arrow = table.scan(selected_fields=("debut_validite", "fin_validite")).to_arrow()
    debuts = [t for t in pc.unique(arrow["debut_validite"]).to_pylist() if t is not None]
    fins = [t for t in pc.unique(arrow["fin_validite"]).to_pylist() if t is not None]
    return debuts, fins


def _premiere(table: Table) -> datetime | None:
    debuts, _ = _instants(table)
    return min(debuts, default=None)


def _dernier_changement(table: Table, instant: datetime) -> datetime | None:
    debuts, fins = _instants(table)
    return max((t for t in (*debuts, *fins) if t <= instant), default=None)


def _compter(table: Table, instant: datetime) -> int:
    return table.scan(row_filter=filtre_validite(instant), selected_fields=("identite",)).count()


def formater(rapport: RapportQualite) -> list[str]:
    """Une ligne par contrôle (numéro, classe, valeur, nom), son détail en retrait, le résumé."""
    lignes = []
    for controle in rapport.controles:
        marque = "TOMBE " if controle.tombe else ""
        lignes.append(
            f"{controle.numero:>2}  {controle.classe.value:<8}  {marque}{controle.valeur:>8}"
            f"  {controle.nom}"
        )
        for cle, valeur in controle.detail.items():
            lignes.append(f"{'':14}{cle} : {_texte(valeur)}")
    lignes.append(rapport.resume())
    return lignes


def _texte(valeur: object) -> str:
    if isinstance(valeur, dict):
        return ", ".join(f"{k} {v}" for k, v in valeur.items() if v is not None)
    return str(valeur)


def en_dict(controle: Controle) -> dict[str, object]:
    """Un contrôle pour la sortie JSON Lines."""
    return {
        "numero": controle.numero,
        "nom": controle.nom,
        "classe": controle.classe.value,
        "valeur": controle.valeur,
        "tombe": controle.tombe,
        "detail": controle.detail,
        "regle": controle.regle,
    }
