"""Mission 04, décisions 1 et 5 : le jeu de démo figé, sa fabrication, sa vérification.

Le jeu du dépôt (``demo/archive``) est contrôlé tel quel, sans réseau, avec
son README ; la fabrication est testée sur le bronze de synthèse de
``test_rejeu`` (``peupler``), jamais sur l'archive réelle.
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.manifeste import Enregistrement
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.demo.jeu import FabricationRefusee, fabriquer, verifier
from tests.test_rejeu import DISPO, PRESENTATIONS, SUITE, _arbre, _executer, peupler

DEPOT = Path(__file__).resolve().parent.parent
JEU = DEPOT / "demo" / "archive"
README = DEPOT / "demo" / "README.md"
# La coupure du jeu de synthèse : les treize premières collectes de SUITE (jusqu'au dispo_b de
# 5 h 06), douze archives et un passage inchangé, les deux entités ayant des archives après.
COUPURE = 13
PASSAGE_COUPURE = SUITE[COUPURE - 1].instant.strftime("%Y%m%dT%H%M%SZ")
LIGNE_TABLE = re.compile(
    r"^\| (\d{8}T\d{6}Z) \| `([^`]+)` \| [^|]* \| [^|]* \| `([0-9a-f]{64})` \|$"
)


def test_le_jeu_du_depot_est_conforme() -> None:
    bilan = verifier(JEU)
    assert bilan.conforme, bilan.anomalies
    assert (len(bilan.archives), len(bilan.entites), bilan.lignes, bilan.passages) == (
        22,
        11,
        781,
        71,
    )
    assert (bilan.premier_passage, bilan.dernier_passage) == (
        "20261024T194141Z",
        "20261027T151708Z",
    )
    assert bilan.entites == sorted(charger_tous()), "les onze fichiers TSV, rien d'autre"
    assert all(
        a.chemin.endswith(".txt.gz") and a.identifiant.startswith("bdpm.") for a in bilan.archives
    )
    assert bilan.archives_par_entite()["bdpm.infos_importantes"] == 9, (
        "l'alternance du 27/10 est là"
    )


def test_le_readme_du_jeu_suit_le_manifeste() -> None:
    bilan = verifier(JEU)
    texte = README.read_text(encoding="utf-8")
    table = [(m[1], m[2], m[3]) for m in map(LIGNE_TABLE.match, texte.splitlines()) if m]
    assert len(table) == len(bilan.archives) == 22, "une ligne par archive, ni plus ni moins"
    assert sorted(table) == sorted((a.passage_id, a.fichier, a.sha256) for a in bilan.archives), (
        "chaque sha256 du README est celui de la ligne nouveau du manifeste"
    )

    def nombre(mot: str) -> int:
        correspondance = re.search(rf"\*\*(\d+) {mot}\*\*", texte)
        assert correspondance, f"« N {mot} » en gras attendu dans le README"
        return int(correspondance[1])

    assert nombre("archives") == len(bilan.archives)
    assert nombre("entités") == len(bilan.entites)
    assert nombre("lignes") == bilan.lignes
    assert nombre("passages") == bilan.passages
    assert f"`{bilan.premier_passage}`" in texte and f"`{bilan.dernier_passage}`" in texte


@pytest.fixture
def source(tmp_path: Path) -> Path:
    racine = tmp_path / "source"
    peupler(racine, SUITE)
    return racine


def test_fabriquer_coupe_au_passage_et_copie_a_l_octet(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "jeu"
    bilan = fabriquer(source, destination, PASSAGE_COUPURE, [PRESENTATIONS, DISPO])
    assert bilan.conforme, bilan.anomalies
    assert (bilan.lignes, len(bilan.archives), bilan.passages) == (COUPURE, COUPURE - 1, COUPURE)
    assert bilan.entites == [DISPO, PRESENTATIONS]
    assert (bilan.premier_passage, bilan.dernier_passage) == ("20261024T141700Z", PASSAGE_COUPURE)
    for archive in bilan.archives:
        assert (destination / archive.chemin).read_bytes() == (source / archive.chemin).read_bytes()
    # Le manifeste du jeu est, à l'octet, celui qu'aurait écrit une collecte arrêtée à la coupure.
    tronque = tmp_path / "tronque"
    peupler(tronque, SUITE[:COUPURE])
    assert (
        manifeste.chemin_manifeste(destination).read_bytes()
        == manifeste.chemin_manifeste(tronque).read_bytes()
    )
    # Et « evenements » y donne la même sortie.
    _executer(destination, tmp_path / "sortie-jeu")
    _executer(tronque, tmp_path / "sortie-tronque")
    assert _arbre(tmp_path / "sortie-jeu") == _arbre(tmp_path / "sortie-tronque")
    # Une seule entité : ses seules lignes.
    partiel = fabriquer(source, tmp_path / "partiel", PASSAGE_COUPURE, [PRESENTATIONS])
    assert partiel.conforme and partiel.entites == [PRESENTATIONS]
    assert (partiel.lignes, len(partiel.archives)) == (6, 6)
    assert not (tmp_path / "partiel" / "bronze" / "bdpm" / "CIS_CIP_Dispo_Spec.txt").exists()
    # Un dossier vide existant est une destination acceptable.
    (tmp_path / "vide").mkdir()
    assert fabriquer(source, tmp_path / "vide", PASSAGE_COUPURE, [DISPO]).conforme


def test_fabriquer_refuse_sans_rien_ecrire(source: Path, tmp_path: Path) -> None:
    with pytest.raises(FabricationRefusee, match="AAAAMMJJTHHMMSSZ"):
        fabriquer(source, tmp_path / "a", "2026-10-24", [PRESENTATIONS])
    assert not (tmp_path / "a").exists()
    with pytest.raises(FabricationRefusee, match="sous la racine"):
        fabriquer(source, source / "jeu", PASSAGE_COUPURE, [PRESENTATIONS])
    assert not (source / "jeu").exists()
    occupe = tmp_path / "occupe"
    occupe.mkdir()
    (occupe / "x").write_text("")
    with pytest.raises(FabricationRefusee, match="pas un dossier vide"):
        fabriquer(source, occupe, PASSAGE_COUPURE, [PRESENTATIONS])
    assert [p.name for p in occupe.iterdir()] == ["x"], "un jeu ne se met pas à jour"
    with pytest.raises(FabricationRefusee, match="aucune ligne"):
        fabriquer(source, tmp_path / "b", "20200101T000000Z", [PRESENTATIONS])
    assert not (tmp_path / "b").exists()
    with pytest.raises(FabricationRefusee, match="n'est pas une archive"):
        fabriquer(tmp_path / "nulle-part", tmp_path / "c", PASSAGE_COUPURE, [PRESENTATIONS])
    premiere = next(ligne for ligne in manifeste.parcourir(source) if ligne.chemin_archive)
    assert premiere.chemin_archive is not None
    (source / premiere.chemin_archive).unlink()
    with pytest.raises(FabricationRefusee, match="absent de"):
        fabriquer(source, tmp_path / "d", PASSAGE_COUPURE, [PRESENTATIONS, DISPO])
    assert not (tmp_path / "d").exists(), "la source est vérifiée avant d'écrire quoi que ce soit"


def test_verifier_nomme_chaque_ecart(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "jeu"
    archives = fabriquer(source, destination, PASSAGE_COUPURE, [PRESENTATIONS, DISPO]).archives
    (destination / "bronze" / "intrus.txt").write_text("x")
    (destination / "bronze" / "bdpm" / "vide").mkdir()
    (destination / "notes").mkdir()
    (destination / ".DS_Store").write_bytes(b"")  # un nom qui commence par un point est ignoré
    with gzip.open(destination / archives[0].chemin, "wb") as flux:
        flux.write(b"autre contenu")
    (destination / archives[1].chemin).unlink()
    manifeste.ajouter(
        destination,
        Enregistrement(
            passage_id="20200101T000000Z",
            identifiant=PRESENTATIONS,
            source="bdpm",
            fichier="CIS_CIP_bdpm.txt",
            url="https://exemple.test/CIS_CIP_bdpm.txt",
            debut="2020-01-01T00:00:00+00:00",
            fin="2020-01-01T00:00:01+00:00",
            statut="erreur",
            version_collecteur="essai",
            erreur="HTTP 503",
        ),
    )
    bilan = verifier(destination)
    assert not bilan.conforme
    texte = "\n".join(bilan.anomalies)
    for attendu in (
        "bronze/intrus.txt : fichier étranger au jeu",
        "bronze/bdpm/vide/ : dossier vide",
        "notes/ : dossier étranger",
        f"{archives[0].chemin} : sha256",
        f"{archives[0].chemin} : 13 octets au lieu de",
        f"{archives[1].chemin} : cité par le manifeste, absent du jeu",
        "ligne 14 : statut erreur (HTTP 503)",
        "ligne 14 : passage 20200101T000000Z",
        "n'est pas dans l'ordre",
    ):
        assert attendu in texte, attendu
    assert ".DS_Store" not in texte and len(bilan.anomalies) == 8, texte
    assert bilan.lignes == COUPURE + 1, "le bilan compte quand même"
    rien = tmp_path / "rien"
    assert verifier(rien).anomalies == [f"{rien / 'manifeste' / 'collecte.jsonl'} absent"]


def test_commandes_demo_fabriquer_et_verifier(source: Path, tmp_path: Path) -> None:
    lanceur = CliRunner()
    destination = tmp_path / "jeu"
    arguments = ["demo", "fabriquer", "--racine", str(source), "--destination", str(destination)]
    arguments += ["--jusqu-au-passage", PASSAGE_COUPURE, "--fichier", "CIS_CIP_bdpm.txt"]
    resultat = lanceur.invoke(application, arguments)
    assert resultat.exit_code == 0, resultat.output
    assert f"jeu : {destination}" in resultat.output
    # La dernière collecte de présentations avant la coupure est celle de 19 h 17.
    assert "6 ligne(s) de manifeste, 6 passage(s) du 20261024T141700Z au 20261024T191700Z" in (
        resultat.output
    )
    assert "6 archive(s), 1 entité(s)" in resultat.output
    assert "bdpm.presentations           6 archive(s)" in resultat.output
    assert resultat.output.rstrip().endswith("conforme")
    encore = lanceur.invoke(application, arguments)
    assert encore.exit_code == 2 and "pas un dossier vide" in encore.output
    mal_coupe = ["--jusqu-au-passage", "hier"]
    mal = lanceur.invoke(
        application,
        [
            "demo",
            "fabriquer",
            "--racine",
            str(source),
            "--destination",
            str(tmp_path / "x"),
            *mal_coupe,
        ],
    )
    assert mal.exit_code == 2 and "AAAAMMJJTHHMMSSZ" in mal.output and not (tmp_path / "x").exists()
    verification = lanceur.invoke(application, ["demo", "verifier", "--racine", str(destination)])
    assert verification.exit_code == 0 and verification.output.rstrip().endswith("conforme")
    (destination / "bronze" / "intrus").write_text("")
    refus = lanceur.invoke(application, ["demo", "verifier", "--racine", str(destination)])
    assert refus.exit_code == 1 and "NON CONFORME : 1 anomalie(s)" in refus.output
    assert "bronze/intrus : fichier étranger" in refus.output
    assert "fabriquer" in lanceur.invoke(application, ["demo"]).output
