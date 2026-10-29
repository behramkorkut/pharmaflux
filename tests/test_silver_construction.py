"""Mission 05, palier 1 : construire, vérifier, comparer, interroger, sur le bronze de synthèse.

Le bronze est celui de ``test_rejeu`` (``SUITE`` : oscillation A → B → A → B,
vide, bloquant, pertes en attente confirmées par l'archive suivante ou par un
passage inchangé, écartées, une ligne en triple ramenée à une puis remontée,
une archive en attente à la fin). ``evenements`` le rejoue sous ``tmp_path``,
``construire`` bâtit le silver, ``verifier`` le compare à chaque archive, et
les commandes sont jouées par ``CliRunner``. Aucun réseau, aucun conteneur.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pytest
from typer.testing import CliRunner

from pharmaflux import bronze
from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evenements import rejeu, snapshot
from pharmaflux.evenements.volume import Decision
from pharmaflux.silver import SilverRefuse, comparaison, construction, sql, verification
from pharmaflux.silver import etat as etat_silver
from pharmaflux.silver.entrepot import Entrepot, chemins_parquet
from pharmaflux.silver.schema import colonnes_du_contrat
from pharmaflux.silver.verification import _empreintes_silver, _empreintes_snapshot
from tests.conftest import texte_nu
from tests.test_rejeu import DISPO, PRESENTATIONS, SUITE, peupler

ENTITES = [PRESENTATIONS, DISPO]


@pytest.fixture(scope="module")
def bronze_et_sortie(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    racine = tmp_path_factory.mktemp("bronze") / "pharmaflux-data"
    peupler(racine, SUITE)
    sortie = tmp_path_factory.mktemp("sortie") / "evenements"
    rapport = rejeu.executer(racine, sortie, charger_tous(), ENTITES)
    assert rapport.code_sortie == 0
    return racine, sortie


@pytest.fixture(scope="module")
def entrepot(bronze_et_sortie: tuple[Path, Path], tmp_path_factory: pytest.TempPathFactory) -> Path:
    _, sortie = bronze_et_sortie
    dossier = tmp_path_factory.mktemp("silver") / "lakehouse"
    rapport = construction.construire(sortie, dossier, charger_tous(), ENTITES, lot=7)
    assert [r.identifiant for r in rapport.resumes] == ENTITES
    assert all(r.fichiers and r.commits for r in rapport.resumes)
    return dossier


def _bilans(sortie: Path, entite: str) -> list[dict[str, object]]:
    return [
        json.loads(c.read_text(encoding="utf-8"))
        for c in sorted((sortie / rejeu.DOSSIER_BILANS / entite).glob("*.json"))
    ]


def test_construire_compte_ce_que_les_bilans_comptent(
    bronze_et_sortie: tuple[Path, Path], entrepot: Path
) -> None:
    _, sortie = bronze_et_sortie
    silver = Entrepot.ouvrir(entrepot)
    assert silver.entites() == sorted(ENTITES)
    for entite in ENTITES:
        attendu = {"creee": 0, "modifiee": 0, "supprimee": 0}
        for bilan in _bilans(sortie, entite):
            ecart = bilan.get("ecart")
            if not ecart:  # le premier snapshot : une creee par ligne bien formée
                if bilan["decision"] in (Decision.RETENU, Decision.CONFIRME):
                    attendu["creee"] += int(bilan["lignes_bien_formees"])  # type: ignore[call-overload]
                continue
            for type_, n in (ecart.get("evenements") or {}).items():  # type: ignore[union-attr]
                attendu[type_] += n
        table = silver.table(entite)
        assert table is not None
        tout = table.scan().to_arrow()
        assert tout.num_rows == attendu["creee"] + attendu["modifiee"]
        assert (
            tout["fin_validite"].null_count
            == tout.num_rows - attendu["modifiee"] - attendu["supprimee"]
        )
        assert len(table.metadata.snapshots) >= 2  # des lots de 7 : plusieurs commits


def test_verifier_est_conforme_sur_toutes_les_archives(
    bronze_et_sortie: tuple[Path, Path], entrepot: Path
) -> None:
    racine, sortie = bronze_et_sortie
    rapport = verification.verifier(
        Entrepot.ouvrir(entrepot), sortie, racine, charger_tous(), ENTITES
    )
    assert rapport.code_sortie == 0, [
        (a.archive, a.differences) for e in rapport.entites for a in e.archives if not a.conforme
    ] + [e.invariants for e in rapport.entites]
    decisions = {a.decision for e in rapport.entites for a in e.archives}
    assert decisions == {Decision.RETENU, Decision.CONFIRME, Decision.ECARTE}
    en_attente = [n for e in rapport.entites for n in e.notes if "en attente" in n]
    assert len(en_attente) == 2  # une par entité à la fin du bronze
    bilans = sum(len(_bilans(sortie, e)) for e in ENTITES)
    assert rapport.archives_verifiees == bilans - 2 and rapport.archives_conformes == bilans - 2
    for e in rapport.entites:
        assert e.versions and e.ouvertes and e.fichiers and e.snapshots and not e.invariants


def test_etat_a_une_date_egale_le_snapshot_entre_deux_archives(
    bronze_et_sortie: tuple[Path, Path], entrepot: Path
) -> None:
    """Entre deux observations, l'état est celui du dernier retenu, à la seconde près."""
    racine, sortie = bronze_et_sortie
    contrats = charger_tous()
    silver = Entrepot.ouvrir(entrepot)
    for entite in ENTITES:
        contrat = contrats[entite]
        table = silver.table(entite)
        assert table is not None
        archives = {a.relatif(racine): a for a in bronze.lister(racine, "bdpm", contrat.fichier)}
        dernier = None
        for bilan in _bilans(sortie, entite):
            archive = archives[str(bilan["archive"])]
            if bilan["decision"] in (Decision.RETENU, Decision.CONFIRME):
                dernier = archive
            if dernier is None:
                continue
            attendu = _empreintes_snapshot(snapshot.lire(contrat, dernier, racine))
            colonnes = colonnes_du_contrat(table.schema().as_arrow())
            for decalage in (0, 1, 1799):  # à l'observation, une seconde après, une demi-heure
                instant = archive.horodatage.replace(microsecond=0) + timedelta(seconds=decalage)
                obtenu = _empreintes_silver(
                    etat_silver.etat_a(table, instant),
                    colonnes,
                    contrat.cle.colonnes,
                    contrat.cle.unique,
                )
                assert obtenu == attendu, (entite, archive.relatif(racine), decalage)
            # Une seconde avant une archive retenue qui change : l'état précédent.
        premiere, derniere = etat_silver.bornes(table)
        assert premiere is not None and derniere is not None and premiere <= derniere
        assert etat_silver.etat_a(table, premiere - timedelta(seconds=1)).num_rows == 0


def test_comparer_deux_constructions_identiques_et_une_differente(
    bronze_et_sortie: tuple[Path, Path], entrepot: Path, tmp_path: Path
) -> None:
    _, sortie = bronze_et_sortie
    autre = tmp_path / "autre"
    construction.construire(sortie, autre, charger_tous(), ENTITES, lot=1000)  # d'autres lots
    assert comparaison.comparer(Entrepot.ouvrir(entrepot), Entrepot.ouvrir(autre)) == []
    # Une sortie amputée de son dernier fichier de présentations : des versions manquent.
    amputee = tmp_path / "sortie-amputee"
    for fichier in sorted((sortie / rejeu.DOSSIER_EVENEMENTS).rglob("*.jsonl"))[:-1]:
        cible = amputee / fichier.relative_to(sortie)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(fichier.read_bytes())
    partiel = tmp_path / "partiel"
    construction.construire(amputee, partiel, charger_tous(), ENTITES)
    differences = comparaison.comparer(Entrepot.ouvrir(entrepot), Entrepot.ouvrir(partiel))
    assert differences and all("version(s) seulement dans" in d for d in differences)
    assert any(str(entrepot) in d for d in differences)
    # Une entité en moins d'un côté.
    seule = tmp_path / "seule"
    construction.construire(sortie, seule, charger_tous(), [PRESENTATIONS])
    differences = comparaison.comparer(Entrepot.ouvrir(entrepot), Entrepot.ouvrir(seule))
    assert differences == [f"{DISPO} : table seulement dans {entrepot}"]


def test_sql_lit_les_vues_et_refuse_tout_le_reste(entrepot: Path, tmp_path: Path) -> None:
    con = sql.connexion(Entrepot.ouvrir(entrepot))
    resultat = sql.executer(
        con, "SELECT count(*) AS n, count(fin_validite) AS fermees FROM presentations"
    )
    assert resultat.num_rows == 1 and resultat["n"][0].as_py() > resultat["fermees"][0].as_py() > 0
    jointure = sql.executer(
        con,
        "SELECT p.code_cip13, d.code_statut FROM presentations p JOIN disponibilite d"
        " ON p.code_cis = d.code_cis WHERE p.fin_validite IS NULL LIMIT 3",
    )
    assert jointure.num_rows <= 3 and jointure.schema.names == ["code_cip13", "code_statut"]
    instants = sql.executer(con, "SELECT min(debut_validite) AS d FROM presentations")
    assert str(instants["d"].type) == "timestamp[us, tz=UTC]"
    hors = tmp_path / "hors.csv"
    hors.write_text("a,b\n1,2\n", encoding="utf-8")
    refusees = {
        f"COPY (SELECT 1) TO '{tmp_path / 'x.csv'}'": "lecture seule",
        f"SELECT * FROM read_csv('{hors}')": "requête refusée",
        f"ATTACH '{tmp_path / 'autre.db'}'": "lecture seule",
        "INSTALL iceberg": "lecture seule",
        "SET enable_external_access = true": "lecture seule",
        "CREATE TABLE t AS SELECT 1": "lecture seule",
        "SELECT 1; SELECT 2": "une seule requête",
        f"SELECT * FROM read_parquet('{tmp_path}/*.parquet')": "requête refusée",
        "SELECT * FROM inconnue": "requête refusée",
        "SELECT (": "illisible",
    }
    for requete, motif in refusees.items():
        with pytest.raises(SilverRefuse, match=motif):
            sql.executer(con, requete)
    assert not (tmp_path / "x.csv").exists() and not (tmp_path / "autre.db").exists()
    # Le verrou tient aussi en dehors de « executer » : un SET direct est refusé par DuckDB.
    import duckdb

    with pytest.raises(duckdb.Error, match="locked"):
        con.execute("SET enable_external_access = true")
    # Relecture 1, point 3 : la connexion elle-même refuse d'écrire, d'attacher et d'installer.
    for enonce in (
        f"COPY (SELECT 1) TO '{tmp_path / 'y.csv'}'",
        f"ATTACH '{tmp_path / 'autre2.db'}'",
        "INSTALL iceberg",
    ):
        with pytest.raises(duckdb.Error):
            con.execute(enonce)
    assert not (tmp_path / "y.csv").exists() and not (tmp_path / "autre2.db").exists()
    assert (
        sql.executer(con, "SELECT count(*) FROM presentations").num_rows == 1
    )  # la vue se lit encore


def test_commandes_silver(
    bronze_et_sortie: tuple[Path, Path], entrepot: Path, tmp_path: Path
) -> None:
    racine, sortie = bronze_et_sortie
    lanceur = CliRunner()
    neuf = tmp_path / "neuf"
    r = lanceur.invoke(
        application,
        ["silver", "construire", "--sortie", str(sortie), "--entrepot", str(neuf), "--lot", "50"],
    )
    assert r.exit_code == 0, r.output
    assert PRESENTATIONS in r.output and "entrepôt :" in r.output
    r = lanceur.invoke(
        application, ["silver", "construire", "--sortie", str(sortie), "--entrepot", str(neuf)]
    )
    assert r.exit_code == 2 and "n'est pas vide" in texte_nu(r.output)
    r = lanceur.invoke(
        application,
        [
            "silver",
            "construire",
            "--sortie",
            str(tmp_path / "rien"),
            "--entrepot",
            str(tmp_path / "vide"),
        ],
    )
    assert r.exit_code == 2 and "aucun dossier d'événements" in texte_nu(r.output)

    # État à une date : toutes les présentations de A à l'instant de la première archive.
    table = Entrepot.ouvrir(neuf).table(PRESENTATIONS)
    assert table is not None
    premiere, derniere = etat_silver.bornes(table)
    assert premiere is not None and derniere is not None
    a = premiere.strftime("%Y-%m-%dT%H:%M:%SZ")
    r = lanceur.invoke(
        application,
        ["silver", "etat", "--entite", "CIS_CIP_bdpm.txt", "--a", a, "--entrepot", str(neuf)],
    )
    assert r.exit_code == 0, r.output
    lignes = [json.loads(ligne_) for ligne_ in r.stdout.splitlines() if ligne_.startswith("{")]
    assert lignes and all(
        ligne_["debut_validite"] == a and ligne_["fin_validite"] in (None, ligne_["fin_validite"])
        for ligne_ in lignes
    )
    assert f"{len(lignes)} version(s) valide(s)" in r.output
    r = lanceur.invoke(
        application,
        [
            "silver",
            "etat",
            "--entite",
            PRESENTATIONS,
            "--a",
            "2020-01-01",
            "--entrepot",
            str(neuf),
            "--format",
            "csv",
        ],
    )
    assert r.exit_code == 0 and "précède la première observation" in r.output
    assert r.stdout.splitlines()[0].startswith("code_cis,")  # l'en-tête CSV, aucune ligne
    r = lanceur.invoke(
        application,
        [
            "silver",
            "etat",
            "--entite",
            PRESENTATIONS,
            "--a",
            "2030-01-01T00:00:00Z",
            "--entrepot",
            str(neuf),
            "--format",
            "tableau",
            "--colonne",
            "code_cip13",
            "--colonne",
            "fin_validite",
        ],
    )
    assert r.exit_code == 0 and "s'arrête à la dernière observation" in r.output
    assert r.stdout.splitlines()[0].split() == ["code_cip13", "fin_validite"]
    cle = lignes[0]["code_cip13"]
    r = lanceur.invoke(
        application,
        [
            "silver",
            "etat",
            "--entite",
            PRESENTATIONS,
            "--a",
            a,
            "--entrepot",
            str(neuf),
            "--ou",
            f"code_cip13={cle}",
        ],
    )
    assert (
        r.exit_code == 0
        and sum(1 for ligne_ in r.stdout.splitlines() if ligne_.startswith("{")) == 1
    )
    for mauvais in (
        ["--a", "2026-10-24T14:17:00"],
        ["--a", a, "--ou", "prix=1"],
        ["--a", a, "--entrepot", str(tmp_path / "nulle-part")],
    ):
        r = lanceur.invoke(
            application,
            ["silver", "etat", "--entite", PRESENTATIONS, *mauvais]
            + (["--entrepot", str(neuf)] if "--entrepot" not in mauvais else []),
        )
        assert r.exit_code == 2 and "état refusé" in r.output, mauvais
    r = lanceur.invoke(
        application, ["silver", "etat", "--entite", "inconnue", "--a", a, "--entrepot", str(neuf)]
    )
    assert r.exit_code == 2

    # SQL : une requête, puis un refus.
    r = lanceur.invoke(
        application,
        ["silver", "sql", "SELECT count(*) AS n FROM disponibilite", "--entrepot", str(neuf)],
    )
    assert r.exit_code == 0 and r.stdout.splitlines()[0].strip() == "n" and "1 ligne(s)" in r.output
    r = lanceur.invoke(
        application,
        ["silver", "sql", f"COPY (SELECT 1) TO '{tmp_path / 'y.csv'}'", "--entrepot", str(neuf)],
    )
    assert (
        r.exit_code == 2
        and "lecture seule" in texte_nu(r.output)
        and not (tmp_path / "y.csv").exists()
    )

    # Comparer : identiques, puis différents.
    r = lanceur.invoke(application, ["silver", "comparer", str(entrepot), str(neuf)])
    assert r.exit_code == 0 and r.output.startswith("identiques : 2 table(s)")
    seule = tmp_path / "seule"
    construction.construire(sortie, seule, charger_tous(), [DISPO])
    r = lanceur.invoke(application, ["silver", "comparer", str(neuf), str(seule)])
    assert r.exit_code == 2 and "DIFFÉRENCE" in r.output and PRESENTATIONS in r.output
    r = lanceur.invoke(application, ["silver", "comparer", str(neuf), str(tmp_path / "absent")])
    assert r.exit_code == 2 and "comparaison refusée" in r.output

    # Vérifier : conforme ; puis contre les bilans d'un autre bronze (plus court) : code 2.
    r = lanceur.invoke(
        application,
        [
            "silver",
            "verifier",
            "--entrepot",
            str(neuf),
            "--sortie",
            str(sortie),
            "--racine",
            str(racine),
        ],
    )
    assert r.exit_code == 0, r.output
    assert "archive(s) conforme(s)" in r.output and "invariants : conformes" in r.output
    assert "DIFFÉRENCE" not in r.output and "(ecarte" in r.output and "(confirme" in r.output
    court = tmp_path / "bronze-court"
    peupler(court, SUITE[:6])
    sortie_courte = tmp_path / "sortie-courte"
    assert rejeu.executer(court, sortie_courte, charger_tous(), ENTITES).code_sortie == 0
    r = lanceur.invoke(
        application,
        [
            "silver",
            "verifier",
            "--entrepot",
            str(neuf),
            "--sortie",
            str(sortie_courte),
            "--racine",
            str(court),
        ],
    )
    assert r.exit_code == 2 and "TOMBÉS" in r.output
    r = lanceur.invoke(
        application,
        [
            "silver",
            "verifier",
            "--entrepot",
            str(neuf),
            "--sortie",
            str(tmp_path / "rien"),
            "--racine",
            str(racine),
        ],
    )
    assert r.exit_code == 2 and "référence introuvable" in texte_nu(r.output)


def test_verifier_voit_une_version_qui_manque(
    bronze_et_sortie: tuple[Path, Path], tmp_path: Path
) -> None:
    """Un silver bâti sans le dernier fichier de présentations n'est pas conforme à l'archive."""
    racine, sortie = bronze_et_sortie
    amputee = tmp_path / "amputee"
    fichiers = sorted((sortie / rejeu.DOSSIER_EVENEMENTS / PRESENTATIONS).glob("*.jsonl"))
    for fichier in [*fichiers[:-1], *(sortie / rejeu.DOSSIER_EVENEMENTS / DISPO).glob("*.jsonl")]:
        cible = amputee / fichier.relative_to(sortie)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(fichier.read_bytes())
    dossier = tmp_path / "silver"
    construction.construire(amputee, dossier, charger_tous(), ENTITES)
    rapport = verification.verifier(
        Entrepot.ouvrir(dossier), sortie, racine, charger_tous(), ENTITES
    )
    assert rapport.code_sortie == 2
    pres = next(e for e in rapport.entites if e.entite == PRESENTATIONS)
    non_conformes = [a for a in pres.archives if not a.conforme]
    assert non_conformes and all("identité(s)" in d for a in non_conformes for d in a.differences)
    assert pres.invariants and "les bilans comptent" in pres.invariants[-1]
    dispo = next(e for e in rapport.entites if e.entite == DISPO)
    assert dispo.conforme


def _avec(ligne: pa.Table, **valeurs: object) -> pa.Table:
    """Une copie de la ligne Arrow avec quelques colonnes changées (typage du schéma gardé)."""
    for nom, valeur in valeurs.items():
        champ = ligne.schema.field(nom)
        ligne = ligne.set_column(
            ligne.schema.get_field_index(nom), champ, pa.array([valeur], type=champ.type)
        )
    return ligne


def test_verifier_voit_chaque_invariant_du_scd2(
    bronze_et_sortie: tuple[Path, Path], tmp_path: Path
) -> None:
    """Relecture 1, point 2 : une version fautive ajoutée par un ``append`` direct fait tomber
    chacun des quatre invariants SQL, avec son message et le code 2."""
    racine, sortie = bronze_et_sortie
    h = timedelta(hours=1)

    def fautives(versions: pa.Table, cas: str) -> list[pa.Table]:
        ouverte = versions.filter(pc.is_null(versions["fin_validite"])).slice(0, 1)
        fermee = versions.filter(pc.is_valid(versions["fin_validite"])).slice(0, 1)
        debut = ouverte["debut_validite"][0].as_py()
        if cas == "ouvertes":  # la même identité ouverte deux fois
            return [_avec(ouverte, id_ouverture="faux-1")]
        if cas == "inversee":  # une fin avant le début
            return [
                _avec(
                    ouverte,
                    identite="fautive",
                    id_ouverture="faux-2",
                    fin_validite=debut - h,
                    id_fermeture="faux-3",
                )
            ]
        if cas == "chevauchement":  # deux versions fermées qui se recouvrent d'une heure
            return [
                _avec(
                    ouverte,
                    identite="fautive",
                    id_ouverture="faux-4",
                    fin_validite=debut + 2 * h,
                    id_fermeture="faux-5",
                ),
                _avec(
                    ouverte,
                    identite="fautive",
                    id_ouverture="faux-6",
                    debut_validite=debut + h,
                    fin_validite=debut + 3 * h,
                    id_fermeture="faux-7",
                ),
            ]
        return [_avec(fermee, identite="fautive")]  # les id d'une version existante, repris

    attendus = {
        "ouvertes": "1 identité(s) avec plusieurs versions ouvertes",
        "inversee": "1 version(s) dont la fin ne suit pas le début",
        "chevauchement": "1 chevauchement(s) de validités",
        "ids": "identifiants d'événements répétés : 1 en ouverture, 1 en fermeture",
    }
    for cas, attendu in attendus.items():
        dossier = tmp_path / cas
        construction.construire(sortie, dossier, charger_tous(), [PRESENTATIONS])
        table = Entrepot.ouvrir(dossier).table(PRESENTATIONS)
        assert table is not None
        for ligne in fautives(table.scan().to_arrow(), cas):
            table.append(ligne)
        rapport = verification.verifier(
            Entrepot.ouvrir(dossier), sortie, racine, charger_tous(), [PRESENTATIONS]
        )
        assert rapport.code_sortie == 2, cas
        invariants = rapport.entites[0].invariants
        assert attendu in invariants, (cas, invariants)
        if cas != "ouvertes":
            assert not any("plusieurs versions ouvertes" in i for i in invariants), cas
        assert "les bilans comptent" in invariants[-1], cas  # les comptes tombent aussi


def test_entrepot_sous_un_chemin_a_espace_et_accent(
    bronze_et_sortie: tuple[Path, Path], tmp_path: Path
) -> None:
    """Relecture 1, bloquant 1 : tout est écrit sous le dossier demandé, rien dans un voisin
    au nom encodé (``Mes%20projets%20%C3%A9``), et les chemins rendus existent."""
    racine, sortie = bronze_et_sortie
    parent = tmp_path / "Mes projets é"
    dossier = parent / "lakehouse"
    construction.construire(sortie, dossier, charger_tous(), ENTITES)
    assert [p.name for p in tmp_path.iterdir()] == ["Mes projets é"]
    assert [p.name for p in parent.iterdir()] == ["lakehouse"]
    silver = Entrepot.ouvrir(dossier)
    racine_uri = f"file://{dossier.resolve()}/"
    chemins: list[str] = []
    for entite in ENTITES:
        table = silver.table(entite)
        assert table is not None and table.metadata_location.startswith(racine_uri)
        chemins += chemins_parquet(table)
    assert chemins and all(Path(c).is_file() for c in chemins)
    sur_disque = {str(p) for p in dossier.resolve().rglob("*.parquet")}
    assert set(chemins) <= sur_disque  # le reste : les fichiers des snapshots précédents
    assert verification.verifier(silver, sortie, racine, charger_tous(), ENTITES).code_sortie == 0
    for mauvais in ("dièse#1", "quoi?"):  # lus comme la fin d'un URI : refus, rien de créé
        with pytest.raises(SilverRefuse, match="chemin d'entrepôt refusé"):
            Entrepot.creer(tmp_path / mauvais)
        assert not (tmp_path / mauvais).exists()


def test_bornes_et_etat_sur_une_table_vide(tmp_path: Path) -> None:
    silver = Entrepot.creer(tmp_path / "vide")
    table = silver.creer_table(charger_tous()[PRESENTATIONS], "fichiers")
    assert etat_silver.bornes(table) == (None, None)
    assert etat_silver.etat_a(table, datetime(2026, 1, 1, tzinfo=UTC)).num_rows == 0
    assert (
        sql.executer(sql.connexion(silver), "SELECT count(*) FROM presentations")[0][0].as_py() == 0
    )
