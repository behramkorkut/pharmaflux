"""Mission 06, palier 1 : le typage du gold, ses contrôles, ``gold etat`` et ``gold sql``.

Le bronze est fait des onze extraits réels de ``tests/fixtures/bdpm/`` à
14:17 (le 24/10/2026), puis, à 15:17, de deux variantes **synthétiques**
construites en mémoire, jamais écrites sous ``tests/fixtures/`` : la première
présentation porte un prix écrit à point (``24.35`` au lieu de ``24,34``, un
décimal illisible pour le contrat, qui a pourtant l'air canonique), la
première spécialité une date d'AMM impossible (``31/02/1998``). ``evenements``
le rejoue sous un dossier jetable, ``silver construire`` bâtit le silver, et
le gold se calcule dessus. Deux silvers **corrompus à dessein** (des
événements retouchés, que la chaîne ne produit jamais) font tomber les
contrôles bloquants 3 et 4. Aucun réseau, aucun conteneur.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.archive import chemin_archive, ecrire_archive
from pharmaflux.collecte.empreintes import empreinte_comparaison, sha256_hex
from pharmaflux.collecte.manifeste import Enregistrement
from pharmaflux.contrats.chargeur import charger_identifiant, charger_tous
from pharmaflux.contrats.modele import TypeNom, TypeValeur
from pharmaflux.demo.jeu import JEU_PAR_DEFAUT
from pharmaflux.evenements import rejeu
from pharmaflux.gold import COLONNES_ILLISIBLES, COLONNES_VERSION_GOLD, Classe
from pharmaflux.gold import qualite as qualite_gold
from pharmaflux.gold.typage import (
    derniere_observation,
    etat_type,
    type_arrow,
    typer_etat,
    typer_valeurs,
)
from pharmaflux.silver import construction
from pharmaflux.silver import etat as etat_silver
from pharmaflux.silver.entrepot import Entrepot
from pharmaflux.silver.schema import schema_du_contrat
from tests.conftest import FIXTURES, entree, entrees_bdpm_txt, texte_nu

T0 = datetime(2026, 10, 24, 14, 17, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
A0, A1 = "2026-10-24T14:17:00Z", "2026-10-24T15:17:00Z"
PRESENTATIONS, SPECIALITES, MITM = "bdpm.presentations", "bdpm.specialites", "bdpm.mitm"
CIP13_PRIX_A_POINT = "3400949497294"  # 1re ligne de l'extrait de CIS_CIP_bdpm.txt
CIS_DATE_IMPOSSIBLE = "61266250"  # 1re ligne de l'extrait de CIS_bdpm.txt

# --- le bronze de fixtures ----------------------------------------------------------------------


def _archiver(racine: Path, identifiant: str, instant: datetime, contenu: bytes) -> None:
    """Archive ``contenu`` et écrit sa ligne de manifeste, comme un passage de collecte."""
    e = entree(identifiant)
    sha256 = sha256_hex(contenu)
    absolu = chemin_archive(racine, e, instant, sha256)
    ecrire_archive(absolu, contenu, instant)
    manifeste.ajouter(
        racine,
        Enregistrement(
            passage_id=instant.strftime("%Y%m%dT%H%M%SZ"),
            identifiant=e.identifiant,
            source=e.source,
            fichier=e.fichier,
            url=e.url,
            debut=instant.isoformat(),
            fin=(instant + timedelta(seconds=1)).isoformat(),
            statut="nouveau",
            version_collecteur="essai",
            sha256=sha256,
            empreinte_comparaison=empreinte_comparaison(e.empreinte, contenu),
            taille_octets=len(contenu),
            date_source_affichee="2026-10-24",
            chemin_archive=absolu.relative_to(racine).as_posix(),
        ),
    )


def _variante(identifiant: str, colonne: str, ancienne: str, nouvelle: str) -> bytes:
    """L'extrait réel dont la première ligne a ``colonne`` réécrite : une archive synthétique."""
    contrat = charger_identifiant(identifiant)
    texte = (FIXTURES / "bdpm" / contrat.fichier).read_bytes().decode(contrat.format.encodage)
    premiere, reste = texte.split("\n", 1)
    valeurs = premiere.split("\t")
    i = contrat.index(colonne)
    assert valeurs[i] == ancienne, valeurs[i]
    valeurs[i] = nouvelle
    return ("\t".join(valeurs) + "\n" + reste).encode(contrat.format.encodage)


@pytest.fixture(scope="module")
def fixtures_gold(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """La sortie de ``evenements`` et le silver du bronze de fixtures (voir le module)."""
    racine = tmp_path_factory.mktemp("bronze") / "pharmaflux-data"
    for e in entrees_bdpm_txt():
        _archiver(racine, e.identifiant, T0, (FIXTURES / "bdpm" / e.fichier).read_bytes())
    # « 24.35 » et non « 24.34 » : « 24.34 » brut égale la forme canonique de « 24,34 », et
    # la détection, qui compare les valeurs normalisées, n'y verrait aucun changement.
    prix = _variante(PRESENTATIONS, "prix_medicament", "24,34", "24.35")
    _archiver(racine, PRESENTATIONS, T1, prix)
    _archiver(
        racine, SPECIALITES, T1, _variante(SPECIALITES, "date_amm", "12/03/1998", "31/02/1998")
    )
    sortie = tmp_path_factory.mktemp("sortie") / "evenements"
    assert rejeu.executer(racine, sortie, charger_tous(), list(charger_tous())).code_sortie == 0
    dossier = tmp_path_factory.mktemp("silver") / "lakehouse"
    construction.construire(sortie, dossier, charger_tous(), list(charger_tous()))
    return sortie, dossier


def _silver_corrompu(sortie: Path, dossier: Path, retoucher: Any) -> Path:
    """Un silver bâti sur une copie des événements que ``retoucher`` modifie (jamais la chaîne)."""
    copie = dossier.parent / "evenements"
    shutil.copytree(sortie, copie)
    retoucher(copie / rejeu.DOSSIER_EVENEMENTS)
    entrepot = dossier.parent / "lakehouse"
    construction.construire(copie, entrepot, charger_tous(), list(charger_tous()))
    return entrepot


# --- le typage, valeur par valeur ---------------------------------------------------------------


def test_le_type_arrow_vient_du_contrat() -> None:
    contrats = charger_tous()
    types = {
        f"{e}.{c.nom}": type_arrow(c.type)
        for e, contrat in contrats.items()
        for c in contrat.colonnes
    }
    assert types["bdpm.presentations.prix_public"] == pa.decimal128(18, 2)
    assert types["bdpm.presentations.taux_remboursement"] == pa.list_(pa.string())
    assert types["bdpm.presentations.date_declaration_commercialisation"] == pa.date32()
    assert types["bdpm.specialites.voies_administration"] == pa.list_(pa.string())
    assert types["bdpm.specialites.surveillance_renforcee"] == pa.bool_()
    assert types["bdpm.generiques.numero_tri"] == pa.int64()
    assert types["bdpm.disponibilite.lien_ansm"] == pa.string()  # une url
    assert types["bdpm.disponibilite.code_statut"] == pa.string()  # une énumération
    assert types["bdpm.presentations.code_cip13"] == pa.string()  # un code, pas un nombre
    attendus = {
        TypeNom.TEXTE: pa.string(),
        TypeNom.CODE: pa.string(),
        TypeNom.URL: pa.string(),
        TypeNom.ENUMERATION: pa.string(),
        TypeNom.ENTIER: pa.int64(),
        TypeNom.DATE: pa.date32(),
        TypeNom.BOOLEEN: pa.bool_(),
    }
    for contrat in contrats.values():
        for c in contrat.colonnes:
            if c.type.nom in attendus:
                assert type_arrow(c.type) == attendus[c.type.nom], c.nom


def _typer(type_: TypeValeur, valeurs: list[str | None]) -> tuple[list[Any], list[bool]]:
    typees, refusees = typer_valeurs(pa.array(valeurs, pa.string()), type_)
    return typees.to_pylist(), refusees.to_pylist()


def test_chaque_type_ne_lit_que_sa_forme_canonique() -> None:
    entier = TypeValeur(TypeNom.ENTIER)
    assert _typer(entier, ["7", "-12", "0", None, "007", "1.0", "x", "1" * 19]) == (
        [7, -12, 0, None, None, None, None, None],
        [False, False, False, False, True, True, True, True],
    )
    decimal = TypeValeur(TypeNom.DECIMAL, decimales=2)
    typees, refusees = _typer(decimal, ["1.16", "66597.27", "-0.50", "1,16", "1.1", "01.16", None])
    assert typees == [
        Decimal("1.16"),
        Decimal("66597.27"),
        Decimal("-0.50"),
        None,
        None,
        None,
        None,
    ]
    assert refusees == [False, False, False, True, True, True, False]
    assert str(typees[0]) == "1.16"  # exact : jamais 1.1600000000000001
    jour = TypeValeur(TypeNom.DATE, format="JJ/MM/AAAA")
    assert _typer(jour, ["2026-06-25", "2924-11-29", "2026-02-30", "25/06/2026", None]) == (
        [date(2026, 6, 25), date(2924, 11, 29), None, None, None],
        [False, False, True, True, False],
    )
    booleen = TypeValeur(TypeNom.BOOLEEN, vrai="Oui", faux="Non")
    assert _typer(booleen, ["true", "false", "Oui", None]) == (
        [True, False, None, None],
        [False, False, True, False],
    )
    texte = TypeValeur(TypeNom.TEXTE)
    assert _typer(texte, ["a", None]) == (["a", None], [False, False])


def test_une_liste_se_decoupe_sur_son_separateur_et_un_refus_la_vide() -> None:
    voies = TypeValeur(TypeNom.LISTE, de=TypeValeur(TypeNom.TEXTE), separateur=";")
    assert _typer(voies, ["orale;sublinguale", "orale", None]) == (
        [["orale", "sublinguale"], ["orale"], None],
        [False, False, False],
    )
    entiers = TypeValeur(TypeNom.LISTE, de=TypeValeur(TypeNom.ENTIER), separateur=";")
    assert _typer(entiers, ["1;2", "1;x", None]) == ([[1, 2], None, None], [False, True, False])


def _ligne_silver(contrat_id: str, **valeurs: Any) -> dict[str, Any]:
    """Une version du silver (schéma de la mission 05) : chaînes vides sauf ``valeurs``."""
    contrat = charger_identifiant(contrat_id)
    ligne: dict[str, Any] = {nom: "" for nom in contrat.noms_colonnes}
    ligne |= {
        "identite": "",
        "empreinte_ligne": "e",
        "rang": 1,
        "date_source": "2026-10-24",
        "debut_validite": T0,
        "fin_validite": None,
        "id_ouverture": "i",
        "id_fermeture": None,
        "archive_ouverture": "a",
        "archive_fermeture": None,
        "version_contrat": contrat.version,
        "etat_initial": True,
        "anomalies": [],
    }
    ligne |= valeurs
    return ligne


def _etat_silver(contrat_id: str, lignes: list[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(lignes, schema_du_contrat(charger_identifiant(contrat_id)))


def test_une_valeur_illisible_n_est_jamais_devinee() -> None:
    """« 24.34 » brut (décimal illisible) et « 24.34 » canonique : seule l'anomalie les sépare."""
    illisible = [{"colonne": "prix_medicament", "regle": "decimal_illisible"}]
    etat = _etat_silver(
        PRESENTATIONS,
        [
            _ligne_silver(PRESENTATIONS, code_cip13="1", identite="1", prix_medicament="24.34"),
            _ligne_silver(
                PRESENTATIONS,
                code_cip13="2",
                identite="2",
                prix_medicament="24.34",
                anomalies=illisible,
            ),
            _ligne_silver(PRESENTATIONS, code_cip13="3", identite="3", prix_medicament="24,34"),
        ],
    )
    typee = typer_etat(PRESENTATIONS, charger_identifiant(PRESENTATIONS), etat)
    assert typee.table["prix_medicament"].to_pylist() == [Decimal("24.34"), None, None]
    assert typee.table[COLONNES_ILLISIBLES].to_pylist() == [[], ["prix_medicament"], []]
    assert typee.illisibles == {("prix_medicament", "decimal_illisible"): 1}
    # « 24,34 » sans anomalie : le silver devait le rendre canonique ; c'est un invariant rompu.
    assert typee.non_typables == {"prix_medicament": 1}
    assert typee.table["taux_remboursement"].to_pylist() == [None, None, None]  # vide → nul


def test_doublons_de_cle_et_d_identite() -> None:
    etat = _etat_silver(
        PRESENTATIONS,
        [
            _ligne_silver(PRESENTATIONS, code_cip13="1", identite="a"),
            _ligne_silver(PRESENTATIONS, code_cip13="1", identite="a"),
            _ligne_silver(PRESENTATIONS, code_cip13="2", identite="b"),
        ],
    )
    typee = typer_etat(PRESENTATIONS, charger_identifiant(PRESENTATIONS), etat)
    assert (typee.doublons_cle, typee.doublons_identite) == (1, 1)
    dispo = _etat_silver("bdpm.disponibilite", [_ligne_silver("bdpm.disponibilite", identite="x")])
    assert (
        typer_etat(
            "bdpm.disponibilite", charger_identifiant("bdpm.disponibilite"), dispo
        ).doublons_cle
        is None
    )


# --- le gold sur le silver des fixtures ---------------------------------------------------------


def test_etat_type_aux_deux_instants(fixtures_gold: tuple[Path, Path]) -> None:
    _, dossier = fixtures_gold
    entrepot = Entrepot.ouvrir(dossier)
    contrat = charger_identifiant(PRESENTATIONS)
    filtre = {"code_cip13": CIP13_PRIX_A_POINT}
    avant = etat_type(entrepot, contrat, etat_silver.lire_instant(A0), filtre).table
    apres = etat_type(entrepot, contrat, etat_silver.lire_instant(A1), filtre).table
    assert avant["prix_medicament"].to_pylist() == [Decimal("24.34")]
    assert avant[COLONNES_ILLISIBLES].to_pylist() == [[]]
    assert apres["prix_medicament"].to_pylist() == [None]
    assert apres[COLONNES_ILLISIBLES].to_pylist() == [["prix_medicament"]]
    # La brute reste lisible dans le silver, avec sa règle.
    table = entrepot.table(PRESENTATIONS)
    assert table is not None
    brute = etat_silver.etat_a(table, etat_silver.lire_instant(A1), filtre)
    assert brute["prix_medicament"].to_pylist() == ["24.35"]
    assert brute["anomalies"].to_pylist() == [
        [{"colonne": "prix_medicament", "regle": "decimal_illisible"}]
    ]
    specialite = etat_type(
        entrepot,
        charger_identifiant(SPECIALITES),
        etat_silver.lire_instant(A1),
        {"code_cis": CIS_DATE_IMPOSSIBLE},
    ).table
    assert specialite["date_amm"].to_pylist() == [None]
    assert specialite["surveillance_renforcee"].type == pa.bool_()
    assert derniere_observation(entrepot) == T1


def test_le_gold_ne_dit_rien_de_ce_qu_on_a_appris_apres(fixtures_gold: tuple[Path, Path]) -> None:
    _, dossier = fixtures_gold
    contrat = charger_identifiant(PRESENTATIONS)
    typee = etat_type(Entrepot.ouvrir(dossier), contrat, etat_silver.lire_instant(A0))
    assert typee.table.schema.names == [
        *contrat.noms_colonnes,
        *COLONNES_VERSION_GOLD,
        COLONNES_ILLISIBLES,
    ]
    for absente in ("fin_validite", "id_fermeture", "archive_fermeture"):
        assert absente not in typee.table.schema.names


def test_qualite_sur_les_fixtures(fixtures_gold: tuple[Path, Path]) -> None:
    _, dossier = fixtures_gold
    entrepot = Entrepot.ouvrir(dossier)
    rapport = qualite_gold.controler(entrepot, charger_tous(), T1)
    assert [c.numero for c in rapport.controles] == list(range(1, 15))
    assert [c.classe for c in rapport.controles[:4]] == [Classe.BLOQUANT] * 4
    assert all(c.classe is Classe.MESURE for c in rapport.controles[4:])
    assert rapport.code_sortie == 0 and not rapport.bloquants
    par_numero = {c.numero: c for c in rapport.controles}
    assert par_numero[12].detail == {
        "bdpm.presentations.prix_medicament (decimal_illisible)": 1,
        "bdpm.specialites.date_amm (date_illisible)": 1,
    }
    volumes = par_numero[14].detail
    lignes = etat_type(entrepot, charger_identifiant(PRESENTATIONS), T1).table.num_rows
    assert volumes[PRESENTATIONS] == {
        "lignes": lignes,
        "avant": lignes,
        "ecart": 0,
        "ecart_pct": 0.0,
        "depuis": A1,
    }
    mitm = etat_type(entrepot, charger_identifiant(MITM), T1).table.num_rows
    assert volumes[MITM] == {"lignes": mitm, "depuis": "état initial"}
    # Avant 15:17, le prix est encore lisible.
    assert qualite_gold.controler(entrepot, charger_tous(), T0).controles[11].valeur == 0


def test_gold_qualite_en_ligne_de_commande(fixtures_gold: tuple[Path, Path]) -> None:
    _, dossier = fixtures_gold
    resultat = CliRunner().invoke(application, ["gold", "qualite", "--entrepot", str(dossier)])
    assert resultat.exit_code == 0, resultat.output
    assert f"instant : {A1} (dernière observation du silver)" in resultat.output
    assert "14 contrôles à 2026-10-24T15:17:00Z : 4 bloquants, 10 mesurés" in resultat.output
    assert "TOMBE" not in resultat.output
    jsonl = CliRunner().invoke(
        application, ["gold", "qualite", "--entrepot", str(dossier), "--a", A0, "--format", "jsonl"]
    )
    assert jsonl.exit_code == 0
    controles = [json.loads(ligne) for ligne in jsonl.stdout.splitlines()]
    assert [c["numero"] for c in controles] == list(range(1, 15))
    assert controles[0]["classe"] == "bloquant" and controles[4]["classe"] == "mesuré"


def _retoucher_prix(evenements: Path) -> None:
    """Un prix non canonique (« 24,34 ») sans anomalie : ce que la normalisation ne laisse pas."""
    fichier = sorted((evenements / PRESENTATIONS).glob("*.jsonl"))[0]
    lignes = []
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        brut = json.loads(ligne)
        if brut["cle"] == {"code_cip13": CIP13_PRIX_A_POINT}:
            brut["apres"]["prix_medicament"] = "24,34"
        lignes.append(json.dumps(brut, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    fichier.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def _vider_mitm(evenements: Path) -> None:
    """Une `supprimee` par ligne de MITM à 14:30 : un vide que le garde-fou de volume écarterait."""
    (premier,) = sorted((evenements / MITM).glob("*.jsonl"))
    archive = "bronze/bdpm/CIS_MITM.txt/2026-10-24/20261024T143000Z__000000000000.txt.gz"
    suppressions = []
    for ligne in premier.read_text(encoding="utf-8").splitlines():
        brut = json.loads(ligne)
        brut |= {
            "type": "supprimee",
            "etat_initial": False,
            "avant": brut["apres"],
            "apres": None,
            "date_observation": "2026-10-24T14:30:00Z",
            "archive_precedente": brut["archive"],
            "archive_precedente_sha256": brut["archive_sha256"],
            "archive": archive,
            "archive_sha256": "0" * 64,
            "id": hashlib.sha256(f"vide{brut['id']}".encode()).hexdigest(),
        }
        suppressions.append(json.dumps(brut, ensure_ascii=False, sort_keys=True))
    vide = evenements / MITM / "20261024T143000Z__000000000000.jsonl"
    vide.write_text("\n".join(suppressions) + "\n", encoding="utf-8")


def test_un_bloquant_qui_tombe_donne_le_code_2(
    fixtures_gold: tuple[Path, Path], tmp_path: Path
) -> None:
    sortie, _ = fixtures_gold
    corrompu = _silver_corrompu(sortie, tmp_path / "prix" / "lakehouse", _retoucher_prix)
    resultat = CliRunner().invoke(
        application, ["gold", "qualite", "--entrepot", str(corrompu), "--a", A0]
    )
    assert resultat.exit_code == 2, resultat.output
    assert "1 bloquant(s) tombé(s)" in resultat.output
    assert "bdpm.presentations.prix_medicament : 1" in resultat.output
    ligne = next(lg for lg in resultat.output.splitlines() if lg.startswith(" 3 "))
    assert "TOMBE" in ligne
    # La colonne typée est vide ; la brute reste dans le silver.
    typee = etat_type(
        Entrepot.ouvrir(corrompu),
        charger_identifiant(PRESENTATIONS),
        etat_silver.lire_instant(A0),
        {"code_cip13": CIP13_PRIX_A_POINT},
    )
    assert typee.table["prix_medicament"].to_pylist() == [None]
    assert typee.non_typables == {"prix_medicament": 1}


def test_une_entite_videe_fait_tomber_le_controle_4(
    fixtures_gold: tuple[Path, Path], tmp_path: Path
) -> None:
    sortie, _ = fixtures_gold
    corrompu = _silver_corrompu(sortie, tmp_path / "vide" / "lakehouse", _vider_mitm)
    entrepot = Entrepot.ouvrir(corrompu)
    avant = qualite_gold.controler(entrepot, charger_tous(), T0)
    assert avant.code_sortie == 0
    apres = qualite_gold.controler(entrepot, charger_tous(), T0 + timedelta(minutes=13))
    assert apres.code_sortie == 2
    (tombe,) = apres.bloquants
    assert (tombe.numero, tombe.detail) == (4, {MITM: 1})


def test_les_controles_demandent_les_onze_entites(
    fixtures_gold: tuple[Path, Path], tmp_path: Path
) -> None:
    sortie, _ = fixtures_gold
    partiel = tmp_path / "partiel"
    construction.construire(sortie, partiel, charger_tous(), [PRESENTATIONS])
    resultat = CliRunner().invoke(application, ["gold", "qualite", "--entrepot", str(partiel)])
    assert resultat.exit_code == 2
    assert "absentes : bdpm.asmr" in texte_nu(resultat.output)
    # gold etat, lui, se contente de l'entité demandée.
    etat = CliRunner().invoke(
        application,
        ["gold", "etat", "--entrepot", str(partiel), "--entite", PRESENTATIONS, "--a", A0],
    )
    assert etat.exit_code == 0


def test_gold_etat_en_ligne_de_commande(fixtures_gold: tuple[Path, Path]) -> None:
    _, dossier = fixtures_gold
    base = ["gold", "etat", "--entrepot", str(dossier), "--entite", "CIS_CIP_bdpm.txt"]
    resultat = CliRunner().invoke(
        application, [*base, "--a", A0, "--ou", f"code_cip13={CIP13_PRIX_A_POINT}"]
    )
    assert resultat.exit_code == 0, resultat.output
    (ligne,) = [json.loads(lg) for lg in resultat.stdout.splitlines()]
    assert ligne["prix_medicament"] == "24.34"  # un décimal sort en chaîne exacte
    assert ligne["debut_validite"] == A0 and "fin_validite" not in ligne
    assert f"{PRESENTATIONS} à {A0} : 1 ligne(s) typée(s)" in resultat.output
    tableau = CliRunner().invoke(
        application,
        [
            *base,
            "--a",
            A1,
            "--format",
            "tableau",
            "--colonne",
            "code_cip13",
            "--colonne",
            "prix_medicament",
            "--colonne",
            COLONNES_ILLISIBLES,
            "--ou",
            f"code_cip13={CIP13_PRIX_A_POINT}",
        ],
    )
    assert tableau.exit_code == 0, tableau.output
    assert tableau.stdout.splitlines()[2].split() == [CIP13_PRIX_A_POINT, '["prix_medicament"]']
    for refus, motif in (
        (["--a", "2026-10-24T14:17:00"], "sans fuseau"),
        (["--a", A0, "--colonne", "fin_validite"], "inconnue"),
        (["--a", A0, "--ou", "prix=1"], "colonne inconnue"),
    ):
        mauvais = CliRunner().invoke(application, [*base, *refus])
        assert mauvais.exit_code == 2 and motif in texte_nu(mauvais.output), refus
    absent = CliRunner().invoke(
        application, ["gold", "etat", "--entrepot", str(dossier.parent / "rien"), "--entite", MITM]
    )
    assert absent.exit_code == 2 and "aucun entrepôt" in texte_nu(absent.output)


def test_gold_sql_sur_les_entites_typees(fixtures_gold: tuple[Path, Path]) -> None:
    _, dossier = fixtures_gold
    base = ["gold", "sql", "--entrepot", str(dossier), "--format", "jsonl", "--a", A0]
    requete = (
        "SELECT typeof(prix_medicament) t, typeof(date_amm) d, prix_medicament + 0.01 p"
        " FROM presentations LEFT JOIN specialites USING (code_cis)"
        f" WHERE code_cip13 = '{CIP13_PRIX_A_POINT}'"
    )
    resultat = CliRunner().invoke(application, [*base, requete])
    assert resultat.exit_code == 0, resultat.output
    assert json.loads(resultat.stdout) == {"t": "DECIMAL(18,2)", "d": "DATE", "p": "24.35"}
    for refusee in (
        "COPY (SELECT 1) TO 'x.csv'",
        "CREATE TABLE t AS SELECT 1",
        "SELECT 1; SELECT 2",
    ):
        mauvaise = CliRunner().invoke(application, [*base, refusee])
        assert mauvaise.exit_code == 2, refusee
    assert not (Path.cwd() / "x.csv").exists()
    fermees = CliRunner().invoke(application, [*base, "SELECT fin_validite FROM presentations"])
    assert fermees.exit_code == 2  # la colonne n'existe pas dans le gold


def test_la_cli_n_importe_pas_les_bibliotheques_du_gold() -> None:
    """Comme le silver : ``pharmaflux.gold`` seul ne charge ni pyarrow, ni pyiceberg, ni duckdb."""
    code = (
        "import sys, pharmaflux.cli, pharmaflux.gold; "
        "print(sorted(m for m in ('pyarrow', 'pyiceberg', 'duckdb') if m in sys.modules))"
    )
    sortie = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120
    )
    assert sortie.stdout.strip() == "[]"


def test_une_question_hors_de_la_fenetre_du_silver_fait_sortir_en_2(
    fixtures_gold: tuple[Path, Path],
) -> None:
    """H.2 : ce silver s'arrête à 15:17 ; les archives citées par le jeu sont de 19:41 et après."""
    _, dossier = fixtures_gold
    base = ["questions", "verifier", "--racine", str(JEU_PAR_DEFAUT)]
    assert CliRunner().invoke(application, base).exit_code == 0
    resultat = CliRunner().invoke(application, [*base, "--entrepot", str(dossier)])
    assert resultat.exit_code == 2, resultat.output
    assert resultat.stdout.splitlines()[-1] == (
        "25 question(s) depuis le gold : 25 non calculable depuis le gold."
    )
    assert "hors de la fenêtre du silver" in resultat.stdout


def test_un_instant_avant_la_premiere_observation_est_refuse(
    fixtures_gold: tuple[Path, Path],
) -> None:
    """Avant 14:17, rien n'est observé : ni contrôle, ni vue ne parle à la place de la source."""
    _, dossier = fixtures_gold
    for commande in (["qualite"], ["disponibilite"], ["fiche", "--tout"]):
        resultat = CliRunner().invoke(
            application,
            ["gold", *commande, "--entrepot", str(dossier), "--a", "2026-10-24T14:00:00Z"],
        )
        assert resultat.exit_code == 2, commande
        assert "pas encore observées : bdpm.asmr" in texte_nu(resultat.output)
        assert f"les onze sont observées à partir de {A0}" in texte_nu(resultat.output)
