"""Mission 01, décision 4 : ``pharmaflux profil`` sur une racine peuplée depuis les fixtures."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.collecte.archive import chemin_archive, ecrire_archive
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.contrats.modele import Regle
from pharmaflux.contrats.profil import ArchiveIntrouvable, profiler, profiler_racine
from pharmaflux.contrats.rendu import nombre, pourcentage, rendre_markdown, tableau
from tests.conftest import FIXTURES, Lanceur, contenu_fixture, entree, entrees_bdpm_txt

lanceur = CliRunner()


@pytest.fixture
def racine_peuplee(lancer: Lanceur, racine: Path) -> Path:
    """Les onze fichiers TSV archivés depuis les fixtures, par un passage simulé."""
    bilan = lancer(entrees_bdpm_txt())
    assert bilan.code_sortie == 0
    return racine


def test_profil_de_chaque_fixture(racine_peuplee: Path) -> None:
    contrats = charger_tous()
    profils = profiler_racine(racine_peuplee, contrats, list(contrats))
    assert [p.contrat.identifiant for p in profils] == list(contrats)
    par_identifiant = {p.contrat.identifiant: p for p in profils}
    specialites = par_identifiant["bdpm.specialites"]
    assert specialites.nombre_lignes == specialites.lignes_bien_formees == 45
    assert specialites.nombre_bloquantes == 0 and not specialites.archive_de_reference
    assert [g.regle for g in specialites.anomalies] == [Regle.ESPACE_PARASITE]
    assert specialites.anomalies[0].nombre == 51 and len(specialites.anomalies[0].exemples) == 5
    assert specialites.cle_distinctes == 45 and specialites.cle_repetees == 0
    statut = next(c for c in specialites.colonnes if c.nom == "statut_amm")
    assert statut.repartition is not None and len(statut.repartition) == 5
    assert statut.repartition[0][0] == "Autorisation active"
    denomination = next(c for c in specialites.colonnes if c.nom == "denomination")
    assert denomination.repartition is None and denomination.distinctes == 45
    date_amm = next(c for c in specialites.colonnes if c.nom == "date_amm")
    assert (date_amm.minimum, date_amm.maximum) == ("07/07/1997", "25/03/2024")
    assert date_amm.maximum is not None and date_amm.minimum != date_amm.maximum

    presentations = par_identifiant["bdpm.presentations"]
    regles = {g.regle: g.nombre for g in presentations.anomalies}
    assert regles == {Regle.DATE_HORS_PLAGE: 2}, "les prix à virgule des milliers se lisent (v1)"
    prix = next(c for c in presentations.colonnes if c.nom == "prix_medicament")
    assert prix.minimum is not None and prix.minimum.count(",") == 1
    assert prix.maximum == "7,518,58", "lu 7518.58 pour les bornes, rendu tel qu'écrit"
    (lien_cis,) = presentations.liens
    assert lien_cis.vers == "bdpm.specialites" and lien_cis.archive_cible is not None
    assert lien_cis.lignes == 49 and lien_cis.distinctes_trouvees <= lien_cis.distinctes

    disponibilite = par_identifiant["bdpm.disponibilite"]
    assert {g.regle: g.nombre for g in disponibilite.anomalies} == {Regle.LIGNE_DUPLIQUEE: 1}
    assert disponibilite.cle_repetees >= 1, "clé déclarée non unique : compté, pas bloquant"
    ordre = next(
        o
        for o in disponibilite.ordres_dates
        if (o.premiere, o.seconde) == ("date_debut", "date_mise_a_jour")
    )
    assert ordre.comparables == 47 and ordre.posterieure >= 1, "le début au 01/07/2027 est futur"
    remise = next(
        o
        for o in disponibilite.ordres_dates
        if (o.premiere, o.seconde) == ("date_debut", "date_remise_a_disposition")
    )
    assert remise.comparables == remise.egales > 0, "remise à disposition = date de début"
    mitm = next(lien for lien in disponibilite.liens if lien.vers == "bdpm.mitm")
    assert mitm.lignes == 47 and mitm.distinctes_trouvees <= mitm.distinctes

    assert all(p.nombre_bloquantes == 0 for p in profils)


def test_valeur_inconnue_en_tete_et_bloquantes_avant_le_reste(racine_peuplee: Path) -> None:
    """Addendum 1 : un nouveau statut est le premier signe d'un changement de format."""
    contrats = charger_tous()
    fabriquee = (FIXTURES / "contrats" / "specialites_anomalies.txt").read_bytes()
    debut = datetime(2026, 10, 25, 14, 17, tzinfo=UTC)
    chemin = chemin_archive(racine_peuplee, entree("bdpm.specialites"), debut, "f" * 64)
    ecrire_archive(chemin, fabriquee, debut)
    (profil,) = profiler_racine(racine_peuplee, contrats, ["bdpm.specialites"])
    regles = [g.regle for g in profil.anomalies]
    assert regles[0] is Regle.VALEUR_INCONNUE
    assert regles[1:4] == [Regle.CLE_NON_UNIQUE, Regle.FIN_DE_LIGNE, Regle.NOMBRE_COLONNES]
    assert profil.nombre_bloquantes == 4 and profil.archive.endswith("ffffffffffff.txt.gz")
    assert profil.lignes_bien_formees == 5 and profil.cle_repetees == 2


def test_bornes_sans_les_nombres_non_conformes() -> None:
    """Relecture 1, point 1 : « NaN », « 1e9 », « Infinity » sont comptés, jamais des bornes."""
    contrat = charger_tous()["bdpm.presentations"]
    i = contrat.index("prix_medicament")
    lignes = [
        ligne.split(b"\t")
        for ligne in contenu_fixture(entree("bdpm.presentations")).split(b"\n")[:4]
    ]
    for ligne, faux in zip(lignes[1:], (b"NaN", b"1e9", b"Infinity"), strict=True):
        ligne[i] = faux
    octets = b"\n".join(b"\t".join(ligne) for ligne in lignes) + b"\n"
    profil = profiler(contrat, octets, "essai", {})
    prix = next(c for c in profil.colonnes if c.nom == "prix_medicament")
    assert (prix.minimum, prix.maximum) == (lignes[0][i].decode(), lignes[0][i].decode())
    assert prix.distinctes == 4 and prix.vides == 0
    assert {g.regle: g.nombre for g in profil.anomalies}[Regle.DECIMAL_ILLISIBLE] == 3


def test_archive_precise_et_introuvable(racine_peuplee: Path) -> None:
    contrats = charger_tous()
    relatif = next((racine_peuplee / "bronze" / "bdpm" / "CIS_MITM.txt").rglob("*.gz"))
    (profil,) = profiler_racine(
        racine_peuplee, contrats, ["bdpm.mitm"], relatif.relative_to(racine_peuplee)
    )
    assert profil.archive == relatif.relative_to(racine_peuplee).as_posix()
    assert profil.nombre_lignes == 43
    with pytest.raises(ArchiveIntrouvable, match="introuvable"):
        profiler_racine(racine_peuplee, contrats, ["bdpm.mitm"], Path("bronze/absente.gz"))
    with pytest.raises(ValueError, match="un seul fichier"):
        profiler_racine(racine_peuplee, contrats, ["bdpm.mitm", "bdpm.smr"], relatif)
    with pytest.raises(ArchiveIntrouvable, match="aucune archive"):
        profiler_racine(racine_peuplee / "vide", contrats, ["bdpm.mitm"])


def test_lien_sans_archive_cible(racine: Path, lancer: Lanceur) -> None:
    lancer([entree("bdpm.presentations")])
    (profil,) = profiler_racine(racine, charger_tous(), ["bdpm.presentations"])
    (lien,) = profil.liens
    assert lien.archive_cible is None and lien.lignes == 0
    assert "aucune archive du fichier cible" in rendre_markdown(profil)


def test_rendu_markdown(racine_peuplee: Path) -> None:
    contrats = charger_tous()
    (profil,) = profiler_racine(racine_peuplee, contrats, ["bdpm.presentations"])
    texte = rendre_markdown(profil, datetime(2026, 10, 26, 12, 0, tzinfo=UTC))
    assert texte.startswith("# Profil — `CIS_CIP_bdpm.txt` (bdpm.presentations)\n")
    assert f"sha256 `{profil.sha256}`" in texte and "le 2026-10-26 12:00Z" in texte
    assert "le contrat a été vérifié sur `bronze/bdpm/CIS_CIP_bdpm.txt/2026-10-24/" in texte
    assert "**aucune anomalie bloquante**" in texte
    assert "| date_hors_plage" in texte and "`29/11/2924`" in texte
    assert "decimal_illisible" not in texte and "| 7,518,58" in texte, "borne lue grâce à milliers"
    assert "**taux_remboursement**" in texte and "| 65 %" in texte
    assert "## Liens vers d'autres fichiers" in texte and "bdpm.specialites.code_cis" in texte
    assert "## Ordre des dates" not in texte, "une seule colonne de date"
    assert "\t" not in texte


def test_outils_de_rendu() -> None:
    assert nombre(15883) == "15 883" and nombre(7) == "7"  # noqa: RUF001
    assert pourcentage(1, 3) == "33,3 %" and pourcentage(0, 0) == "—"  # noqa: RUF001
    assert tableau(("a", "bb"), [("x|y", "\t")]) == "| a    | bb |\n|------|----|\n| x\\|y | ⇥  |"


def test_commande_profil(racine_peuplee: Path, tmp_path: Path) -> None:
    resultat = lanceur.invoke(application, ["profil", "--racine", str(racine_peuplee)])
    assert resultat.exit_code == 0, resultat.output
    assert resultat.output.count("# Profil — ") == 11
    assert "11 fichier(s) profilé(s), 0 anomalie(s) bloquante(s)." in resultat.output

    dossier = tmp_path / "donnees"
    resultat = lanceur.invoke(
        application,
        [
            "profil",
            "--racine",
            str(racine_peuplee),
            "--markdown",
            str(dossier),
            "--fichier",
            "CIS_bdpm.txt",
            "--fichier",
            "bdpm.mitm",
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    assert sorted(p.name for p in dossier.iterdir()) == ["bdpm.mitm.md", "bdpm.specialites.md"]
    assert "bdpm.specialites" in resultat.output and "espace_parasite 51" in resultat.output
    assert (
        (dossier / "bdpm.mitm.md")
        .read_text(encoding="utf-8")
        .startswith("# Profil — `CIS_MITM.txt`")
    )

    resultat = lanceur.invoke(
        application, ["profil", "--racine", str(racine_peuplee), "--fichier", "inconnu.txt"]
    )
    assert resultat.exit_code == 2 and "inconnu.txt inconnu" in resultat.output


def test_commande_profil_archive_et_code_de_sortie(racine_peuplee: Path) -> None:
    debut = datetime(2026, 10, 25, 14, 17, tzinfo=UTC)
    chemin = chemin_archive(racine_peuplee, entree("bdpm.mitm"), debut, "e" * 64)
    ecrire_archive(chemin, (FIXTURES / "contrats" / "mitm_anomalies.txt").read_bytes(), debut)
    relatif = chemin.relative_to(racine_peuplee)
    resultat = lanceur.invoke(
        application, ["profil", "--racine", str(racine_peuplee), "--archive", str(relatif)]
    )
    assert resultat.exit_code == 0, resultat.output
    assert "hote_inconnu" in resultat.output and "3 lignes non vides" in resultat.output

    chemin = chemin_archive(racine_peuplee, entree("bdpm.specialites"), debut, "d" * 64)
    ecrire_archive(chemin, (FIXTURES / "contrats" / "specialites_utf8.txt").read_bytes(), debut)
    resultat = lanceur.invoke(
        application, ["profil", "--racine", str(racine_peuplee), "--fichier", "bdpm.specialites"]
    )
    assert resultat.exit_code == 1, resultat.output
    assert "1 anomalie(s) bloquante(s)." in resultat.output and "| encodage" in resultat.output

    resultat = lanceur.invoke(
        application, ["profil", "--racine", str(racine_peuplee), "--archive", "ailleurs/x.gz"]
    )
    assert resultat.exit_code == 2 and "déduit" in resultat.output
    resultat = lanceur.invoke(
        application,
        [
            "profil",
            "--racine",
            str(racine_peuplee),
            "--archive",
            str(relatif),
            "--fichier",
            "bdpm.mitm",
            "--fichier",
            "bdpm.smr",
        ],
    )
    assert resultat.exit_code == 2 and "un seul" in resultat.output
