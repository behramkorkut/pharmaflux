"""Les vues métier du gold à un instant : fiche médicament, disponibilité courante, alternatives.

Elles se construisent depuis les entités typées (``typage``), en PyArrow et
en Python, sans DuckDB : la fiche faite en SQL DuckDB montait à 552-705 Mo
résidents sur le jeu de démo, contre 318 Mo ici (§0 K). Chaque vue a, dans
les tests, une requête DuckDB de référence écrite à part, et les deux
doivent donner le même multiensemble de lignes (addendum 1, exigence 1).

**La fiche médicament** : une ligne par CIS connu à l'instant, c'est-à-dire
cité par au moins une entité, avec ``dans_referentiel`` (le CIS est dans
``CIS_bdpm.txt``) ; les sections à plusieurs lignes sont des
``list<struct>`` triées de façon stable ; les avis SMR et ASMR sont tous
gardés (pas d'identifiant d'indication), du plus récent au plus ancien ; les
lignes répétées d'un fichier sans clé unique portent ``occurrences``.

**La disponibilité courante** : une ligne par présentation et par ligne de
signalement en cours, avec une priorité écrite (exigence 2) :

1. une ligne en cours la vise, directement (``portee = presentation``) ou
   par sa spécialité (ligne sans CIP13, ``portee = specialite``) :
   ``etat_signalement = declare``, une ligne par signalement ;
2. sinon, une ligne l'a visée et a été retirée du fichier au plus tard à
   l'instant : ``fin_de_publication``, avec la fermeture la plus récente et
   le dernier statut de cette ligne (ADR 0003 : l'ANSM ne publie plus la
   fiche ; ce n'est pas une remise à disposition). Seules les versions dont
   la fin est au plus l'instant sont lues : rien de ce qu'on a appris après ;
3. sinon : ``aucun_signalement``.

Un signalement qui ne vise aucune présentation connue (CIP13 absent des
présentations, ou spécialité sans présentation) garde sa ligne, avec
``presentation_connue = false``.

**Les alternatives** : une ligne par groupe générique et présentation d'une
spécialité du groupe (une ligne sans présentation pour une spécialité qui
n'en a pas), avec la disponibilité de la présentation. Triée par groupe puis
par ``numero_tri`` (l'ordre de la BDPM) ; elle ne classe ni ne recommande
rien.

Le « jour » d'un instant est sa date UTC (``debut_a_venir``, informations en
cours).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal, cast

import pyarrow as pa
import pyarrow.compute as pc

from pharmaflux.contrats.modele import Contrat
from pharmaflux.gold import COLONNES_ILLISIBLES
from pharmaflux.gold.typage import EntiteTypee, typer_etat
from pharmaflux.silver.entrepot import Entrepot
from pharmaflux.silver.expressions import inferieur_ou_egal
from pharmaflux.silver.schema import TYPE_INSTANT, litteral

type Tri = list[tuple[str, Literal["ascending", "descending"]]]

DECLARE, FIN_DE_PUBLICATION, AUCUN = "declare", "fin_de_publication", "aucun_signalement"
PORTEE_PRESENTATION, PORTEE_SPECIALITE = "presentation", "specialite"

# Les colonnes plates de la fiche, depuis les spécialités (une ligne par CIS au plus).
COLONNES_SPECIALITE = (
    "denomination",
    "forme_pharmaceutique",
    "voies_administration",
    "statut_amm",
    "type_procedure_amm",
    "etat_commercialisation",
    "date_amm",
    "statut_bdm",
    "numero_autorisation_europeenne",
    "titulaires",
    "surveillance_renforcee",
)
# Les sections de la fiche : (entité, colonne de la fiche, champs, tri dans la liste).
CHAMPS_PRESENTATION = (
    "code_cip13",
    "code_cip7",
    "libelle_presentation",
    "statut_administratif",
    "etat_commercialisation",
    "date_declaration_commercialisation",
    "agrement_collectivites",
    "taux_remboursement",
    "prix_medicament",
    "prix_public",
    "honoraires_dispensation",
    "indications_remboursement",
)
CHAMPS_COMPOSITION = (
    "designation_element",
    "code_substance",
    "denomination_substance",
    "dosage",
    "reference_dosage",
    "nature_composant",
    "numero_liaison",
)
CHAMPS_GROUPE = ("identifiant_groupe", "libelle_groupe", "type_generique", "numero_tri")
CHAMPS_AVIS = ("code_dossier_has", "motif_evaluation", "date_avis")
CHAMPS_SIGNALEMENT = (
    "code_cip13",
    "code_statut",
    "libelle_statut",
    "date_debut",
    "date_mise_a_jour",
    "date_remise_a_disposition",
    "lien_ansm",
)
CHAMPS_INFO = ("date_debut", "date_fin", "texte_et_lien")
ENTITES_FICHE = (  # les entités qui portent un CIS, dans l'ordre de la provenance
    "bdpm.asmr",
    "bdpm.compositions",
    "bdpm.conditions_prescription",
    "bdpm.disponibilite",
    "bdpm.generiques",
    "bdpm.infos_importantes",
    "bdpm.mitm",
    "bdpm.presentations",
    "bdpm.smr",
    "bdpm.specialites",
)

_CHAMPS_DISPONIBILITE: list[tuple[str, pa.DataType]] = [
    ("code_cis", pa.string()),
    ("code_cip13", pa.string()),
    ("libelle_presentation", pa.string()),
    ("denomination", pa.string()),
    ("etat_signalement", pa.string()),
    ("code_statut", pa.string()),
    ("libelle_statut", pa.string()),
    ("date_debut", pa.date32()),
    ("date_mise_a_jour", pa.date32()),
    ("date_remise_a_disposition", pa.date32()),
    ("lien_ansm", pa.string()),
    ("portee", pa.string()),
    ("occurrences", pa.int64()),
    ("presentation_connue", pa.bool_()),
    ("debut_a_venir", pa.bool_()),
    ("fin_publication", TYPE_INSTANT),
    ("date_source", pa.string()),
    ("connu_depuis", TYPE_INSTANT),
    (COLONNES_ILLISIBLES, pa.list_(pa.string())),
]
SCHEMA_DISPONIBILITE = pa.schema(_CHAMPS_DISPONIBILITE)
TRI_DISPONIBILITE: Tri = [
    ("code_cis", "ascending"),
    ("code_cip13", "ascending"),
    ("etat_signalement", "ascending"),
    ("lien_ansm", "ascending"),
    ("code_statut", "ascending"),
    ("date_debut", "ascending"),
    ("date_mise_a_jour", "ascending"),
    ("date_remise_a_disposition", "ascending"),
]
COLONNES_DISPO_ALTERNATIVES = (
    "etat_signalement",
    "code_statut",
    "libelle_statut",
    "date_debut",
    "date_remise_a_disposition",
    "lien_ansm",
    "portee",
    "debut_a_venir",
    "fin_publication",
)
_CHAMPS_ALTERNATIVES: list[tuple[str, pa.DataType]] = [
    ("identifiant_groupe", pa.string()),
    ("libelle_groupe", pa.string()),
    ("code_cis", pa.string()),
    ("denomination", pa.string()),
    ("type_generique", pa.string()),
    ("numero_tri", pa.int64()),
    ("code_cip13", pa.string()),
    ("libelle_presentation", pa.string()),
    ("etat_commercialisation", pa.string()),
    ("statut_administratif", pa.string()),
    *((nom, SCHEMA_DISPONIBILITE.field(nom).type) for nom in COLONNES_DISPO_ALTERNATIVES),
]
SCHEMA_ALTERNATIVES = pa.schema(_CHAMPS_ALTERNATIVES)
TRI_ALTERNATIVES: Tri = [
    ("identifiant_groupe", "ascending"),
    ("numero_tri", "ascending"),
    ("code_cis", "ascending"),
    ("code_cip13", "ascending"),
    ("etat_signalement", "ascending"),
    ("lien_ansm", "ascending"),
    ("code_statut", "ascending"),
    ("date_debut", "ascending"),
    ("date_remise_a_disposition", "ascending"),
]

Ligne = dict[str, Any]


def jour(instant: datetime) -> date:
    """La date UTC de l'instant : celle que le gold compare aux dates de la source."""
    return instant.astimezone(UTC).date()


# --- outils ------------------------------------------------------------------------------------


def _chaines(colonne: pa.Array[Any] | pa.ChunkedArray[Any]) -> list[str]:
    """Les valeurs d'une colonne de chaînes (les clés et libellés que les vues indexent)."""
    return cast(list[str], colonne.to_pylist())


def _booleen(masque: object) -> pa.BooleanArray:
    return cast(pa.BooleanArray, masque)


def _lister(table: pa.Table, cle: str, champs: Sequence[str], tri: Tri) -> pa.Table:
    """Une ligne par valeur de ``cle`` : la liste triée des ``champs`` de ses lignes.

    Un seul champ donne une ``list`` de ses valeurs, plusieurs une ``list<struct>``.
    """
    triee = table.sort_by([(cle, "ascending"), *tri])
    cles = _chaines(triee[cle])
    distinctes: list[str] = []
    decalages = [0]
    for i, valeur in enumerate(cles):
        if i and valeur != cles[i - 1]:
            decalages.append(i)
        if not i or valeur != cles[i - 1]:
            distinctes.append(valeur)
    if cles:
        decalages.append(len(cles))
    colonnes = [triee[nom].combine_chunks() for nom in champs]
    valeurs = (
        colonnes[0]
        if len(champs) == 1
        else pa.StructArray.from_arrays(colonnes, names=list(champs))
    )
    listes = pa.ListArray.from_arrays(pa.array(decalages, pa.int32()), valeurs)
    return pa.table({cle: pa.array(distinctes, pa.string()), "liste": listes})


def _aligner(
    univers: pa.Array[Any], cles: pa.ChunkedArray[Any], valeurs: pa.ChunkedArray[Any]
) -> pa.Array[Any]:
    """Les ``valeurs`` rangées dans l'ordre de ``univers`` (nulles là où la clé manque)."""
    return valeurs.combine_chunks().take(pc.index_in(univers, value_set=cles.combine_chunks()))


def _compter(table: pa.Table, colonnes: Sequence[str]) -> pa.Table:
    """Les lignes distinctes sur ``colonnes``, leurs ``occurrences``, leur provenance récente."""
    groupes = table.group_by(list(colonnes), use_threads=False).aggregate(
        [([], "count_all"), ("date_source", "max"), ("debut_validite", "max")]
    )
    return groupes.select(
        [*colonnes, "count_all", "date_source_max", "debut_validite_max"]
    ).rename_columns([*colonnes, "occurrences", "date_source", "connu_depuis"])


# --- la fiche médicament -----------------------------------------------------------------------


def fiche(etats: Mapping[str, EntiteTypee], instant: datetime) -> pa.Table:
    """La fiche médicament de chaque CIS connu à ``instant`` (voir le module)."""
    tables = {entite: etats[entite].table for entite in (*ENTITES_FICHE, "bdpm.liens_ct")}
    cis = pa.concat_arrays(
        [tables[e]["code_cis"].combine_chunks().cast(pa.string()) for e in ENTITES_FICHE]
    )
    univers = pc.unique(cis)
    univers = univers.take(pc.array_sort_indices(univers))

    specialites = tables["bdpm.specialites"]
    colonnes: dict[str, pa.Array[Any]] = {"code_cis": univers}
    colonnes["dans_referentiel"] = pc.is_valid(
        pc.index_in(univers, value_set=specialites["code_cis"].combine_chunks())
    )
    for nom in COLONNES_SPECIALITE:
        colonnes[nom] = _aligner(univers, specialites["code_cis"], specialites[nom])
    mitm = tables["bdpm.mitm"]
    colonnes["mitm"] = pc.is_valid(
        pc.index_in(univers, value_set=mitm["code_cis"].combine_chunks())
    )
    colonnes["code_atc"] = _aligner(univers, mitm["code_cis"], mitm["code_atc"])
    colonnes["date_publication_mitm"] = _aligner(
        univers, mitm["code_cis"], mitm["date_publication"]
    )

    sections = {
        "presentations": _lister(
            tables["bdpm.presentations"],
            "code_cis",
            CHAMPS_PRESENTATION,
            [("code_cip13", "ascending")],
        ),
        "composition": _lister(
            tables["bdpm.compositions"],
            "code_cis",
            CHAMPS_COMPOSITION,
            [
                (c, "ascending")
                for c in (
                    "designation_element",
                    "numero_liaison",
                    "nature_composant",
                    "code_substance",
                )
            ],
        ),
        "groupes_generiques": _lister(
            tables["bdpm.generiques"],
            "code_cis",
            CHAMPS_GROUPE,
            [("identifiant_groupe", "ascending")],
        ),
        "conditions_prescription": _lister(
            tables["bdpm.conditions_prescription"],
            "code_cis",
            ["condition"],
            [("condition", "ascending")],
        ),
        "avis_smr": _avis(tables["bdpm.smr"], tables["bdpm.liens_ct"], "smr"),
        "avis_asmr": _avis(tables["bdpm.asmr"], tables["bdpm.liens_ct"], "asmr"),
        "disponibilite": _signalements(tables["bdpm.disponibilite"], instant),
        "infos_importantes": _infos(tables["bdpm.infos_importantes"], instant),
        "provenance": _provenance(etats),
    }
    for nom, section in sections.items():
        colonnes[nom] = _aligner(univers, section["code_cis"], section["liste"])
    colonnes[COLONNES_ILLISIBLES] = _illisibles_par_cis(etats, univers)
    colonnes["instant"] = pa.array([instant] * len(univers), TYPE_INSTANT)
    return pa.table(colonnes)


def _avis(avis: pa.Table, liens_ct: pa.Table, genre: str) -> pa.Table:
    champs = [*CHAMPS_AVIS, f"valeur_{genre}", f"libelle_{genre}"]
    distincts = _compter(avis, ["code_cis", *champs])
    liens = _lister(liens_ct, "code_dossier_has", ["lien_avis"], [("lien_avis", "ascending")])
    distincts = distincts.append_column(
        "liens_avis",
        liens["liste"]
        .combine_chunks()
        .take(
            pc.index_in(
                distincts["code_dossier_has"].combine_chunks(),
                value_set=liens["code_dossier_has"].combine_chunks(),
            )
        ),
    )
    tri: Tri = [("date_avis", "descending")]
    tri += [(c, "ascending") for c in champs if c != "date_avis"]
    return _lister(distincts, "code_cis", [*champs, "liens_avis", "occurrences"], tri)


def _signalements(disponibilite: pa.Table, instant: datetime) -> pa.Table:
    distincts = _compter(disponibilite, ["code_cis", *CHAMPS_SIGNALEMENT])
    portee = pc.if_else(
        pc.is_null(distincts["code_cip13"]),
        pa.scalar(PORTEE_SPECIALITE),
        pa.scalar(PORTEE_PRESENTATION),
    )
    a_venir = pc.greater(distincts["date_debut"], pa.scalar(jour(instant), pa.date32()))
    distincts = distincts.append_column("portee", portee).append_column("debut_a_venir", a_venir)
    tri: Tri = [
        (c, "ascending")
        for c in (
            "date_debut",
            "lien_ansm",
            "code_cip13",
            "code_statut",
            "date_mise_a_jour",
            "date_remise_a_disposition",
        )
    ]
    return _lister(
        distincts, "code_cis", [*CHAMPS_SIGNALEMENT, "portee", "occurrences", "debut_a_venir"], tri
    )


def _infos(infos: pa.Table, instant: datetime) -> pa.Table:
    """Les informations en cours : ``date_debut <= jour <= date_fin``, une fin vide = en cours."""
    aujourd_hui = pa.scalar(jour(instant), pa.date32())
    debut = pc.fill_null(pc.less_equal(infos["date_debut"], aujourd_hui), pa.scalar(False))
    fin = pc.fill_null(pc.greater_equal(infos["date_fin"], aujourd_hui), pa.scalar(True))
    en_cours = infos.filter(pc.and_(_booleen(debut), _booleen(fin)))
    tri: Tri = [(c, "ascending") for c in CHAMPS_INFO]
    return _lister(en_cours, "code_cis", CHAMPS_INFO, tri)


def _provenance(etats: Mapping[str, EntiteTypee]) -> pa.Table:
    """Par CIS et par entité : la source la plus récente, et depuis quand on la connaît."""
    morceaux = []
    for entite in ENTITES_FICHE:
        table = etats[entite].table
        groupes = table.group_by("code_cis", use_threads=False).aggregate(
            [("date_source", "max"), ("debut_validite", "max")]
        )
        nombre = groupes.num_rows
        morceaux.append(
            pa.table(
                {
                    "code_cis": groupes["code_cis"].cast(pa.string()),
                    "entite": pa.array([entite] * nombre, pa.string()),
                    "fichier": pa.array([etats[entite].contrat.fichier] * nombre, pa.string()),
                    "date_source": groupes["date_source_max"].cast(pa.string()),
                    "connu_depuis": groupes["debut_validite_max"].cast(TYPE_INSTANT),
                }
            )
        )
    tout = pa.concat_tables(morceaux)
    return _lister(
        tout,
        "code_cis",
        ["entite", "fichier", "date_source", "connu_depuis"],
        [("entite", "ascending")],
    )


def _illisibles_par_cis(etats: Mapping[str, EntiteTypee], univers: pa.Array[Any]) -> pa.Array[Any]:
    """Pour chaque CIS, les colonnes vidées par une règle de lisibilité (« entite.colonne »)."""
    par_cis: dict[str, set[str]] = defaultdict(set)
    for entite in ENTITES_FICHE:
        table = etats[entite].table
        nom = entite.partition(".")[2]
        for code_cis, colonnes in zip(
            _chaines(table["code_cis"]), table[COLONNES_ILLISIBLES].to_pylist(), strict=True
        ):
            for colonne in colonnes or ():
                par_cis[code_cis].add(f"{nom}.{colonne}")
    return pa.array([sorted(par_cis.get(c, ())) for c in _chaines(univers)], pa.list_(pa.string()))


# --- la disponibilité courante -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Fermees:
    """Les lignes de disponibilité retirées du fichier au plus tard à l'instant, typées."""

    table: pa.Table
    fins: list[datetime]


def fermees(entrepot: Entrepot, contrat: Contrat, instant: datetime) -> Fermees:
    """Les versions de disponibilité dont la fin est au plus l'instant (rien d'après)."""
    table = entrepot.table(contrat.identifiant)
    assert table is not None
    brutes = table.scan(row_filter=inferieur_ou_egal("fin_validite", litteral(instant))).to_arrow()
    fins = [f for f in brutes["fin_validite"].to_pylist() if f is not None]
    return Fermees(typer_etat(contrat.identifiant, contrat, brutes).table, fins)


def disponibilite(
    etats: Mapping[str, EntiteTypee], historique: Fermees, instant: datetime
) -> pa.Table:
    """La disponibilité courante par présentation, selon la priorité du module."""
    aujourd_hui = jour(instant)
    presentations: dict[str, list[tuple[str, str]]] = defaultdict(list)  # CIS → (CIP13, libellé)
    connues: dict[str, tuple[str, str]] = {}  # CIP13 → (CIS, libellé)
    pres = etats["bdpm.presentations"].table
    for code_cis, cip13, libelle in zip(
        _chaines(pres["code_cis"]),
        _chaines(pres["code_cip13"]),
        _chaines(pres["libelle_presentation"]),
        strict=True,
    ):
        presentations[code_cis].append((cip13, libelle))
        connues[cip13] = (code_cis, libelle)
    spec = etats["bdpm.specialites"].table
    denominations = dict(
        zip(_chaines(spec["code_cis"]), _chaines(spec["denomination"]), strict=True)
    )

    def cibles(ligne: Ligne) -> list[tuple[str | None, str | None]]:
        """Les présentations que la ligne vise : (CIP13, libellé) ; (CIP13 ou None, None) sinon."""
        if ligne["code_cip13"] is not None:
            connue = connues.get(ligne["code_cip13"])
            return [(ligne["code_cip13"], connue[1] if connue else None)]
        visees = presentations.get(ligne["code_cis"], [])
        return [(cip, libelle) for cip, libelle in sorted(visees)] or [(None, None)]

    lignes: list[Ligne] = []
    declarees: set[tuple[str, str | None]] = set()  # (CIS, CIP13) déjà couverts par un signalement

    for signalement in _lignes_distinctes(etats["bdpm.disponibilite"].table):
        for cible, nom in cibles(signalement):
            declarees.add((signalement["code_cis"], cible))
            lignes.append(
                _ligne_dispo(signalement, cible, nom, denominations, DECLARE, aujourd_hui)
            )

    retirees: dict[tuple[str, str | None], tuple[datetime, Ligne, str | None]] = {}
    for ferme, fin in zip(historique.table.to_pylist(), historique.fins, strict=True):
        for cible, nom in cibles(ferme):
            cle = (ferme["code_cis"], cible)
            if cle in declarees:
                continue
            courant = retirees.get(cle)
            if courant is None or (fin, _ordre(ferme)) > (courant[0], _ordre(courant[1])):
                retirees[cle] = (fin, ferme, nom)
    for (_, cible), (fin, ferme, nom) in retirees.items():
        ligne = _ligne_dispo(
            {**ferme, "occurrences": 1, "connu_depuis": ferme["debut_validite"]},
            cible,
            nom,
            denominations,
            FIN_DE_PUBLICATION,
            aujourd_hui,
        )
        ligne["fin_publication"] = fin
        lignes.append(ligne)

    couvertes = declarees | set(retirees)
    for code_cis, visees in presentations.items():
        for cip13, libelle in visees:
            if (code_cis, cip13) not in couvertes:
                lignes.append(
                    {
                        "code_cis": code_cis,
                        "code_cip13": cip13,
                        "libelle_presentation": libelle,
                        "denomination": denominations.get(code_cis),
                        "etat_signalement": AUCUN,
                        "presentation_connue": True,
                        COLONNES_ILLISIBLES: [],
                    }
                )
    return pa.Table.from_pylist(lignes, SCHEMA_DISPONIBILITE).sort_by(TRI_DISPONIBILITE)


def _lignes_distinctes(table: pa.Table) -> list[Ligne]:
    """Les lignes de signalement distinctes, avec leurs occurrences et leur provenance."""
    distinctes: dict[tuple[Any, ...], Ligne] = {}
    for ligne in table.to_pylist():
        cle = tuple(ligne[c] for c in ("code_cis", *CHAMPS_SIGNALEMENT))
        courante = distinctes.get(cle)
        if courante is None:
            distinctes[cle] = {
                **ligne,
                "occurrences": 1,
                "connu_depuis": ligne["debut_validite"],
                COLONNES_ILLISIBLES: sorted(set(ligne[COLONNES_ILLISIBLES])),
            }
            continue
        courante["occurrences"] += 1
        courante["date_source"] = (
            max(courante["date_source"] or "", ligne["date_source"] or "") or None
        )
        courante["connu_depuis"] = max(courante["connu_depuis"], ligne["debut_validite"])
        courante[COLONNES_ILLISIBLES] = sorted(
            set(courante[COLONNES_ILLISIBLES]) | set(ligne[COLONNES_ILLISIBLES])
        )
    return list(distinctes.values())


def _ordre(ligne: Ligne) -> tuple[str, ...]:
    """Départage deux fermetures au même instant, de façon stable."""
    return tuple(str(ligne[c]) for c in CHAMPS_SIGNALEMENT)


def _ligne_dispo(
    source: Ligne,
    cip13: str | None,
    libelle: str | None,
    denominations: Mapping[str, str],
    etat: str,
    aujourd_hui: date,
) -> Ligne:
    debut = source["date_debut"]
    return {
        "code_cis": source["code_cis"],
        "code_cip13": cip13,
        "libelle_presentation": libelle,
        "denomination": denominations.get(source["code_cis"]),
        "etat_signalement": etat,
        "code_statut": source["code_statut"],
        "libelle_statut": source["libelle_statut"],
        "date_debut": debut,
        "date_mise_a_jour": source["date_mise_a_jour"],
        "date_remise_a_disposition": source["date_remise_a_disposition"],
        "lien_ansm": source["lien_ansm"],
        "portee": PORTEE_SPECIALITE if source["code_cip13"] is None else PORTEE_PRESENTATION,
        "occurrences": source["occurrences"],
        "presentation_connue": libelle is not None,
        "debut_a_venir": None if debut is None else debut > aujourd_hui,
        "date_source": source["date_source"],
        "connu_depuis": source["connu_depuis"],
        COLONNES_ILLISIBLES: sorted(set(source[COLONNES_ILLISIBLES] or ())),
    }


# --- les alternatives --------------------------------------------------------------------------


def alternatives(etats: Mapping[str, EntiteTypee], dispo: pa.Table) -> pa.Table:
    """Groupe générique, présentations de ses spécialités et leur disponibilité (voir le module)."""
    pres = etats["bdpm.presentations"].table
    par_cis: dict[str, list[Ligne]] = defaultdict(list)
    for ligne in pres.select(
        [
            "code_cis",
            "code_cip13",
            "libelle_presentation",
            "etat_commercialisation",
            "statut_administratif",
        ]
    ).to_pylist():
        par_cis[ligne["code_cis"]].append(ligne)
    par_cip13: dict[str, list[Ligne]] = defaultdict(list)
    for ligne in dispo.select(
        ["code_cip13", "presentation_connue", *COLONNES_DISPO_ALTERNATIVES]
    ).to_pylist():
        if ligne["code_cip13"] is not None and ligne["presentation_connue"]:
            par_cip13[ligne["code_cip13"]].append(ligne)
    spec = etats["bdpm.specialites"].table
    denominations = dict(
        zip(_chaines(spec["code_cis"]), _chaines(spec["denomination"]), strict=True)
    )
    lignes: list[Ligne] = []
    for groupe in etats["bdpm.generiques"].table.select(["code_cis", *CHAMPS_GROUPE]).to_pylist():
        base = {**groupe, "denomination": denominations.get(groupe["code_cis"])}
        presentations = par_cis.get(groupe["code_cis"])
        if not presentations:
            lignes.append(base)
            continue
        for presentation in presentations:
            for etat in par_cip13.get(presentation["code_cip13"], [{}]):
                lignes.append(
                    {
                        **base,
                        **presentation,
                        **{c: etat.get(c) for c in COLONNES_DISPO_ALTERNATIVES},
                    }
                )
    return pa.Table.from_pylist(lignes, SCHEMA_ALTERNATIVES).sort_by(TRI_ALTERNATIVES)


# --- toutes les vues à un instant --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Vues:
    fiche: pa.Table
    disponibilite: pa.Table
    alternatives: pa.Table


def vues(
    entrepot: Entrepot,
    contrats: Mapping[str, Contrat],
    etats: Mapping[str, EntiteTypee],
    instant: datetime,
) -> Vues:
    """Les trois vues métier à ``instant``, depuis les entités typées (les onze)."""
    historique = fermees(entrepot, contrats["bdpm.disponibilite"], instant)
    dispo = disponibilite(etats, historique, instant)
    return Vues(fiche(etats, instant), dispo, alternatives(etats, dispo))
