"""Mission 09, addendum 1 E : les pages d'avis de la HAS du jeu de démo.

Le jeu du dépôt est contrôlé tel quel, sans réseau : sa partie BDPM est celle de ``beba0c8`` à
l'octet, sa liste suit la règle, ses pages sont celles de la liste. La fabrication est testée
sur une petite archive faite des pages réelles des fixtures, jamais sur l'archive de beko.
"""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.demo import has as demo_has
from pharmaflux.demo import jeu
from pharmaflux.has import manifeste as mf
from pharmaflux.has.perimetre import calculer
from tests.conftest import FIXTURES, texte_nu

DEPOT = Path(__file__).resolve().parent.parent
JEU = DEPOT / "demo" / "archive"
LISTE = DEPOT / "demo" / "has-pages.txt"
QUESTIONS_V1 = DEPOT / "evaluation" / "questions-reference-v1.toml"
PAGES = FIXTURES / "has"

# La partie BDPM du jeu à beba0c8 (fusion de la mission 08) : manifeste/collecte.jsonl et les
# 22 archives de bronze/bdpm, « chemin sha256 » triés et joints par « \n », puis sha256.
BDPM_A_BEBA0C8 = ("84924ced32d911e06d71c65eac0bfa2caabe7ab0fbfc3acd62537b8261d2f42e", 23)
PLAFOND_OCTETS = 10_000_000  # addendum 1 E


def _empreinte_bdpm(racine: Path) -> tuple[str, int]:
    fichiers = sorted(
        [*(racine / "bronze" / "bdpm").rglob("*.gz"), racine / "manifeste" / "collecte.jsonl"]
    )
    lignes = [
        f"{f.relative_to(racine).as_posix()} {hashlib.sha256(f.read_bytes()).hexdigest()}"
        for f in fichiers
    ]
    return hashlib.sha256("\n".join(lignes).encode()).hexdigest(), len(fichiers)


def test_la_partie_bdpm_du_jeu_n_a_pas_bouge() -> None:
    assert _empreinte_bdpm(JEU) == BDPM_A_BEBA0C8


def test_la_liste_suit_la_regle() -> None:
    attendue = demo_has.choisir(calculer(JEU), demo_has.cis_des_questions(QUESTIONS_V1))
    assert demo_has.lire_liste(LISTE) == attendue
    assert len(attendue) == demo_has.NOMBRE_PAGES
    raisons = [page.raison.split(" :")[0] for page in attendue]
    assert (raisons.count("§0"), raisons.count("collecte")) == (5, 17)


def test_le_jeu_porte_les_pages_de_la_liste() -> None:
    bilan = jeu.verifier(JEU)
    assert bilan.conforme, bilan.anomalies
    assert sorted(bilan.has.pages) == sorted(page.page_id for page in demo_has.lire_liste(LISTE))
    assert bilan.has.lignes == demo_has.NOMBRE_PAGES
    assert bilan.has.octets < PLAFOND_OCTETS
    # Chaque ligne est celle du passage de beko, telle quelle : extracteur v1, rejet compris.
    lignes = {ligne.page_id: ligne for ligne in mf.lire(JEU)}
    assert {ligne.passage_id for ligne in lignes.values()} == {"20261031T124148Z"}
    assert lignes["p_3608587"].rejet == "dossier_incoherent"


# --- la fabrication, sur une archive de synthèse faite des pages réelles ----------------------


def _page(racine: Path, page_id: str, horodatage: str, passage: str = "20261031T120000Z") -> None:
    octets = (PAGES / f"{page_id}.html").read_bytes()
    sha256 = hashlib.sha256(octets).hexdigest()
    chemin = f"bronze/has/pages/{page_id}/{horodatage}__{sha256[:12]}.html.gz"
    (racine / chemin).parent.mkdir(parents=True, exist_ok=True)
    (racine / chemin).write_bytes(gzip.compress(octets, mtime=0))
    mf.ajouter(
        racine,
        mf.LigneHas(
            passage_id=passage,
            role=mf.Role.PAGE,
            url=f"https://www.has-sante.fr/jcms/{page_id}",
            statut=mf.Statut.NOUVEAU,
            version_collecteur="0.1.0+test",
            page_id=page_id,
            taille=len(octets),
            sha256=sha256,
            archive=chemin,
        ),
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    racine = tmp_path / "source"
    mf.ajouter(
        racine,
        mf.LigneHas("20261031T120000Z", mf.Role.ROBOTS, "https://www.has-sante.fr/robots.txt",
                    mf.Statut.NOUVEAU, "0.1.0+test"),
    )  # fmt: skip
    for page_id in ("p_4072400", "p_3577036", "p_3608587"):
        _page(racine, page_id, "20261031T120001Z")
    return racine


def _liste(tmp_path: Path, *pages: str) -> Path:
    chemin = tmp_path / "liste.txt"
    demo_has.ecrire_liste(
        chemin,
        [demo_has.PageChoisie(f"https://www.has-sante.fr/jcms/{p}", p, "test") for p in pages],
        ["liste de test"],
    )
    return chemin


def test_fabriquer_copie_a_l_octet(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "jeu"
    bilan = demo_has.fabriquer(source, destination, _liste(tmp_path, "p_3608587", "p_4072400"))
    assert not bilan.anomalies
    assert bilan.pages == ["p_4072400", "p_3608587"]  # l'ordre du manifeste source
    brutes = mf.chemin_manifeste(source).read_bytes().splitlines()
    assert mf.chemin_manifeste(destination).read_bytes().splitlines() == [brutes[1], brutes[3]]
    for ligne in mf.lire(destination):
        assert (destination / str(ligne.archive)).read_bytes() == (
            source / str(ligne.archive)
        ).read_bytes()


def test_fabriquer_prend_la_derniere_archive(source: Path, tmp_path: Path) -> None:
    _page(source, "p_4072400", "20261101T090000Z", passage="20261101T090000Z")
    destination = tmp_path / "jeu"
    demo_has.fabriquer(source, destination, _liste(tmp_path, "p_4072400"))
    (ligne,) = mf.lire(destination)
    assert ligne.passage_id == "20261101T090000Z"


def test_fabriquer_refuse_sans_rien_ecrire(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "jeu"
    with pytest.raises(demo_has.FabricationRefusee, match="sans archive"):
        demo_has.fabriquer(source, destination, _liste(tmp_path, "p_4072400", "p_9999999"))
    with pytest.raises(demo_has.FabricationRefusee, match="en double"):
        demo_has.fabriquer(source, destination, _liste(tmp_path, "p_4072400", "p_4072400"))
    with pytest.raises(demo_has.FabricationRefusee, match="sous la racine"):
        demo_has.fabriquer(source, source / "jeu", _liste(tmp_path, "p_4072400"))
    assert not destination.exists()
    demo_has.fabriquer(source, destination, _liste(tmp_path, "p_4072400"))
    with pytest.raises(demo_has.FabricationRefusee, match="déjà ses pages"):
        demo_has.fabriquer(source, destination, _liste(tmp_path, "p_3577036"))


def test_verifier_nomme_chaque_ecart(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "jeu"
    demo_has.fabriquer(source, destination, _liste(tmp_path, "p_4072400", "p_3577036"))
    premiere, seconde = mf.lire(destination)
    (destination / str(premiere.archive)).write_bytes(gzip.compress(b"autre chose"))
    (destination / str(seconde.archive)).unlink()
    (destination / "bronze" / "has" / "pages" / "p_4072400" / "intrus.html.gz").write_bytes(b"")
    bilan = demo_has.verifier(destination)
    assert any("sha256 différent" in a for a in bilan.anomalies)
    assert any("absent du jeu" in a for a in bilan.anomalies)
    # Le contrôle d'ensemble voit le fichier qu'aucune ligne ne cite.
    assert any(
        "intrus.html.gz" in a and "étranger" in a for a in jeu.verifier(destination).anomalies
    )


def test_commandes_choisir_et_fabriquer(source: Path, tmp_path: Path) -> None:
    lanceur = CliRunner()
    sortie = tmp_path / "pages.txt"
    resultat = lanceur.invoke(
        application, ["demo", "choisir-has", "--racine", str(JEU), "--sortie", str(sortie)]
    )
    assert resultat.exit_code == 0, resultat.output
    assert sortie.read_text(encoding="utf-8") == LISTE.read_text(encoding="utf-8")
    destination = tmp_path / "jeu"
    arguments = [
        "demo",
        "fabriquer-has",
        "--racine",
        str(source),
        "--destination",
        str(destination),
    ]
    resultat = lanceur.invoke(
        application, [*arguments, "--liste", str(_liste(tmp_path, "p_3577036"))]
    )
    assert "pages d'avis de la HAS : 1 page(s)" in texte_nu(resultat.output)
    resultat = lanceur.invoke(application, [*arguments, "--liste", str(LISTE)])
    assert resultat.exit_code == 2
    assert "déjà ses pages" in texte_nu(resultat.output)
