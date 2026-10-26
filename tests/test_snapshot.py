"""Mission 02, décision 1 : le snapshot normalisé d'une archive, son bilan, l'écart si bloquant."""

from datetime import UTC, date
from pathlib import Path

import pytest

from pharmaflux import bronze
from pharmaflux.contrats.chargeur import charger_identifiant, charger_tous
from pharmaflux.contrats.modele import REGLES_BLOQUANTES, Regle
from pharmaflux.contrats.verification import verifier
from pharmaflux.evenements import snapshot
from pharmaflux.evenements.snapshot import Identite, Ligne, Snapshot, empreinte_ligne
from tests.conftest import Lanceur, contenu_fixture, entrees_bdpm_txt
from tests.test_contrats_verification import FABRIQUEES, contenu_fixture_par_nom

SANS_CLE_UNIQUE = {"bdpm.smr", "bdpm.asmr", "bdpm.disponibilite"}


def _snapshot(identifiant: str) -> Snapshot:
    (entree,) = [e for e in entrees_bdpm_txt() if e.identifiant == identifiant]
    contrat = charger_identifiant(identifiant)
    return snapshot.construire(contrat, contenu_fixture(entree), f"essai/{entree.fichier}")


@pytest.mark.parametrize("identifiant", [e.identifiant for e in entrees_bdpm_txt()])
def test_chaque_fixture_reelle_donne_un_snapshot_retenu(identifiant: str) -> None:
    """Aucune anomalie bloquante sur les fixtures réelles : rien n'est écarté."""
    s = _snapshot(identifiant)
    bilan = s.bilan
    assert not s.ecarte and s.motif_ecart is None and bilan.motif_ecart is None
    assert s.archive == bilan.archive and s.sha256 == bilan.sha256 and len(s.sha256) == 64
    assert bilan.version_contrat == s.contrat.version
    assert s.identite is (Identite.LIGNE if identifiant in SANS_CLE_UNIQUE else Identite.CLE)
    assert bilan.lignes == bilan.lignes_bien_formees > 0
    assert bilan.entites + bilan.occurrences_en_doublon == bilan.lignes_bien_formees
    if s.identite is Identite.CLE:
        assert len(s.par_cle) == bilan.entites and s.par_ligne == {}
        index = [s.contrat.index(nom) for nom in s.contrat.cle.colonnes]
        for cle, ligne in s.par_cle.items():
            assert cle == tuple(ligne.normalisees[i] for i in index)
    else:
        assert len(s.par_ligne) == bilan.entites and s.par_cle == {}
        assert sum(n for _, n in s.par_ligne.values()) == bilan.lignes_bien_formees
        for empreinte, (ligne, _) in s.par_ligne.items():
            assert empreinte == ligne.empreinte == empreinte_ligne(ligne.normalisees)
    regles = dict(bilan.anomalies)
    assert not (set(regles) & REGLES_BLOQUANTES) and Regle.FICHIER_VIDE not in regles
    numeros = [ligne.numero for ligne in s.lignes]
    assert numeros == sorted(numeros) and len(numeros) == bilan.entites
    for ligne in s.lignes:
        assert len(ligne.brutes) == len(ligne.normalisees) == len(s.contrat.colonnes)
        for brute, normalisee in zip(ligne.brutes, ligne.normalisees, strict=True):
            assert (normalisee is brute) == (normalisee == brute), "chaîne partagée si inchangée"


def test_les_tuples_bruts_sont_ceux_de_la_lecture() -> None:
    """Pas de copie : ``brutes`` est le tuple de la ``Lecture`` ; ``normalisees`` est ``brutes``."""
    contrat = charger_identifiant("bdpm.liens_ct")  # code + url : rien ne change jamais
    lecture = verifier(contrat, contenu_fixture_par_nom("HAS_LiensPageCT_bdpm.txt"))
    s = snapshot.depuis_lecture(lecture, "0" * 64)
    par_numero = {numero: valeurs for numero, valeurs in lecture.lignes}
    for ligne in s.lignes:
        assert ligne.brutes is par_numero[ligne.numero]
        assert ligne.normalisees is ligne.brutes
    assert s.horodatage is None and s.bilan.anomalies == ()


def test_presentations_normalisees_prix_taux_dates() -> None:
    s = _snapshot("bdpm.presentations")
    contrat = s.contrat
    i_prix, i_public = contrat.index("prix_medicament"), contrat.index("prix_public")
    i_taux, i_date = (
        contrat.index("taux_remboursement"),
        contrat.index("date_declaration_commercialisation"),
    )
    par_brute_prix = {ligne.brutes[i_prix]: ligne for ligne in s.lignes}
    chere = par_brute_prix["1,466,29"]
    assert (chere.normalisees[i_prix], chere.normalisees[i_public]) == ("1466.29", "1469.05")
    assert chere.brutes[i_prix] == "1,466,29", "la brute reste brute"
    assert chere.anomalies == (), "plus d'anomalie sur les prix (v1)"
    avec_espace = [ligne for ligne in s.lignes if "100 %" in ligne.brutes[i_taux]]
    assert avec_espace and all("100 %" not in ligne.normalisees[i_taux] for ligne in avec_espace)
    assert all(ligne.normalisees[i_date][4] == "-" for ligne in s.lignes), "dates en ISO"
    (ancienne,) = [ligne for ligne in s.lignes if ligne.brutes[i_date] == "19/01/1949"]
    assert ancienne.normalisees[i_date] == "1949-01-19"
    assert ancienne.anomalies == (("date_declaration_commercialisation", Regle.DATE_HORS_PLAGE),)
    assert dict(s.bilan.anomalies) == {Regle.DATE_HORS_PLAGE: 2}
    ((colonne, graphies),) = s.bilan.graphies
    assert colonne == "taux_remboursement"
    comptes = dict(graphies)
    assert (
        comptes["100 %"] >= 1
        and comptes["65%"] >= 1
        and set(comptes) <= {"65%", "65 %", "100%", "100 %", "30%", "30 %", "15%", "15 %", "35%"}
    )
    assert list(graphies) == sorted(graphies, key=lambda g: (-g[1], g[0]))


def test_ligne_a_ligne_compte_les_occurrences() -> None:
    """``CIS_CIP_Dispo_Spec.txt`` : deux lignes identiques, une entité, deux occurrences."""
    s = _snapshot("bdpm.disponibilite")
    assert s.identite is Identite.LIGNE
    doubles = [(ligne, n) for ligne, n in s.par_ligne.values() if n > 1]
    assert [(ligne.numero, n) for ligne, n in doubles] == [(46, 2)]
    assert s.bilan.occurrences_en_doublon == 1
    assert dict(s.bilan.anomalies) == {Regle.LIGNE_DUPLIQUEE: 1}
    assert doubles[0][0].anomalies == (), (
        "l'anomalie est sur la seconde ligne, la première est gardée"
    )
    assert s.bilan.graphies == ()


def test_une_anomalie_bloquante_ecarte_le_snapshot_sans_exception() -> None:
    contrat = charger_identifiant("bdpm.specialites")
    s = snapshot.construire(contrat, (FABRIQUEES / "specialites_anomalies.txt").read_bytes(), "a")
    assert s.ecarte
    assert s.motif_ecart == (
        "4 anomalie(s) bloquante(s) : cle_non_unique (2), fin_de_ligne (1), nombre_colonnes (1)"
    )
    assert s.bilan.lignes == 6 and s.bilan.lignes_bien_formees == 5
    assert s.bilan.entites == 3 and s.bilan.occurrences_en_doublon == 2, (
        "la clé répétée est comptée, la première ligne gardée"
    )
    assert Regle.CLE_NON_UNIQUE in dict(s.bilan.anomalies)
    assert [ligne.numero for ligne in s.lignes] == [1, 2, 6], "lignes 4 et 5 : clé de la ligne 1"
    ligne_6 = s.lignes[-1]
    assert ("code_cis", Regle.CODE_ILLISIBLE) in ligne_6.anomalies
    assert ("denomination", Regle.VALEUR_MANQUANTE) in ligne_6.anomalies
    assert (None, Regle.RETOUR_FINAL) in ligne_6.anomalies


def test_un_fichier_vide_n_est_pas_ecarte_par_le_snapshot() -> None:
    """``fichier_vide`` n'est pas bloquante : c'est au garde-fou de volume de décider."""
    s = snapshot.construire(charger_identifiant("bdpm.presentations"), b"", "vide")
    assert not s.ecarte and s.bilan.entites == 0 and s.lignes == []
    assert s.bilan.anomalies == ((Regle.FICHIER_VIDE, 1),)
    assert s.bilan.lignes == s.bilan.lignes_bien_formees == 0


def test_lire_une_archive_du_bronze(racine: Path, lancer: Lanceur) -> None:
    (entree,) = [e for e in entrees_bdpm_txt() if e.identifiant == "bdpm.mitm"]
    assert lancer([entree]).code_sortie == 0
    archive = bronze.derniere(racine, "bdpm", entree.fichier)
    assert archive is not None
    s = snapshot.lire(charger_tous()["bdpm.mitm"], archive, racine)
    assert s.archive == archive.relatif(racine) and s.archive.startswith(
        "bronze/bdpm/CIS_MITM.txt/"
    )
    assert s.horodatage == archive.horodatage and s.horodatage.tzinfo is UTC
    assert s.horodatage.date() == date(2026, 10, 24)
    assert s.sha256.startswith(archive.sha256_prefixe)
    assert s.bilan.lignes_bien_formees == len(s.par_cle) > 0 and not s.ecarte


def test_empreinte_de_ligne() -> None:
    a = empreinte_ligne(("1", "2"))
    assert a == empreinte_ligne(("1", "2")) and len(a) == 64
    assert a != empreinte_ligne(("12", "")) and a != empreinte_ligne(("1", "2", ""))
    ligne = Ligne(1, ("1", "2"), ("1", "2"), ())
    assert ligne.empreinte == a
