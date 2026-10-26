"""Mission 01, décision 3 : une archive contre son contrat, des anomalies, jamais une correction."""

import re
from datetime import date

import pytest

from pharmaflux.contrats.chargeur import charger_identifiant, charger_tous
from pharmaflux.contrats.modele import REGLES_BLOQUANTES, Regle, TypeNom, TypeValeur
from pharmaflux.contrats.verification import FICHIER_ENTIER, verifier, verifier_valeur
from tests.conftest import FIXTURES, contenu_fixture, entrees_bdpm_txt

FABRIQUEES = FIXTURES / "contrats"
CODE_CIS = re.compile(r"\d{8}")

# Anomalies non bloquantes attendues sur les fixtures réelles (lignes réelles choisies,
# voir tests/fixtures/README.md) : règle → nombre. Rien d'autre que ces règles.
ATTENDUES_SUR_FIXTURES_REELLES: dict[str, dict[Regle, int]] = {
    "bdpm.specialites": {Regle.ESPACE_PARASITE: 45 + 6},  # titulaires sur chaque ligne, six formes
    "bdpm.presentations": {
        Regle.DECIMAL_ILLISIBLE: 4,
        Regle.DATE_HORS_PLAGE: 2,
    },  # deux prix, deux dates
    "bdpm.compositions": {},
    "bdpm.smr": {},
    "bdpm.asmr": {},
    "bdpm.liens_ct": {},
    "bdpm.generiques": {},
    # Les trois lignes qui précèdent les lignes vides finissent par un « \r » de plus,
    # qui reste dans la valeur : espace parasite, constaté, pas corrigé.
    "bdpm.conditions_prescription": {Regle.LIGNE_VIDE: 3, Regle.ESPACE_PARASITE: 3},
    "bdpm.infos_importantes": {},
    "bdpm.disponibilite": {Regle.LIGNE_DUPLIQUEE: 1},
    "bdpm.mitm": {},
}


@pytest.mark.parametrize("identifiant", [e.identifiant for e in entrees_bdpm_txt()])
def test_chaque_fixture_reelle_passe_son_contrat_sans_anomalie_bloquante(identifiant: str) -> None:
    (entree,) = [e for e in entrees_bdpm_txt() if e.identifiant == identifiant]
    contrat = charger_identifiant(identifiant)
    octets = contenu_fixture(entree)
    lecture = verifier(contrat, octets)
    assert lecture.bloquantes == []
    assert lecture.fichier == entree.fichier
    non_vides = [m for m in octets.split(b"\n") if m.strip(b"\r")]
    assert lecture.nombre_lignes == len(non_vides) == len(lecture.lignes)
    comptes = {regle: len(anomalies) for regle, anomalies in lecture.par_regle().items()}
    assert comptes == ATTENDUES_SUR_FIXTURES_REELLES[identifiant]
    assert all(len(valeurs) == len(contrat.colonnes) for _, valeurs in lecture.lignes)


def test_les_anomalies_connues_sont_signalees_pas_corrigees() -> None:
    """Option (a) de l'addendum 1 : la valeur brute est rendue telle quelle."""
    lecture = verifier(
        charger_identifiant("bdpm.presentations"), contenu_fixture_par_nom("CIS_CIP_bdpm.txt")
    )
    par_regle = lecture.par_regle()
    assert {a.valeur for a in par_regle[Regle.DECIMAL_ILLISIBLE]} == {
        "1,466,29",
        "1,469,05",
        "7,518,58",
        "7,519,60",
    }, "la virgule des milliers est rendue telle quelle"
    assert {a.colonne for a in par_regle[Regle.DECIMAL_ILLISIBLE]} == {
        "prix_medicament",
        "prix_public",
    }
    assert sorted(a.valeur[-4:] for a in par_regle[Regle.DATE_HORS_PLAGE]) == ["1949", "2924"]
    doublon = verifier(
        charger_identifiant("bdpm.disponibilite"), contenu_fixture_par_nom("CIS_CIP_Dispo_Spec.txt")
    )
    (ligne_dupliquee,) = doublon.par_regle()[Regle.LIGNE_DUPLIQUEE]
    assert ligne_dupliquee.ligne == 47 and ligne_dupliquee.valeur.startswith(
        "identique à la ligne 46 : "
    )
    assert not ligne_dupliquee.bloquante, "la clé est déclarée non unique : rien ne bloque"


def contenu_fixture_par_nom(nom: str) -> bytes:
    return (FIXTURES / "bdpm" / nom).read_bytes()


def _constats(lecture, *, sauf: Regle | None = None) -> set[tuple[int, str | None, Regle]]:  # type: ignore[no-untyped-def]
    return {(a.ligne, a.colonne, a.regle) for a in lecture.anomalies if a.regle is not sauf}


def test_fixture_fabriquee_specialites() -> None:
    """Six lignes de CIS_bdpm.txt : fin de ligne, colonnes, clé, doublon, valeurs, retour final."""
    lecture = verifier(
        charger_identifiant("bdpm.specialites"),
        (FABRIQUEES / "specialites_anomalies.txt").read_bytes(),
    )
    assert _constats(lecture, sauf=Regle.ESPACE_PARASITE) == {
        (2, None, Regle.FIN_DE_LIGNE),
        (3, None, Regle.NOMBRE_COLONNES),
        (4, "statut_amm", Regle.VALEUR_INCONNUE),
        (4, "date_amm", Regle.DATE_ILLISIBLE),
        (4, "surveillance_renforcee", Regle.BOOLEEN_INCONNU),
        (4, "code_cis", Regle.CLE_NON_UNIQUE),
        (5, None, Regle.LIGNE_DUPLIQUEE),
        (5, "code_cis", Regle.CLE_NON_UNIQUE),
        (6, "code_cis", Regle.CODE_ILLISIBLE),
        (6, "denomination", Regle.VALEUR_MANQUANTE),
        (6, None, Regle.RETOUR_FINAL),
    }
    assert {a.colonne for a in lecture.anomalies if a.regle is Regle.ESPACE_PARASITE} <= {
        "titulaires",
        "forme_pharmaceutique",
    }
    assert [numero for numero, _ in lecture.lignes] == [1, 2, 4, 5, 6], (
        "la ligne à 11 colonnes est écartée"
    )
    assert lecture.nombre_lignes == 6
    assert sorted(a.regle for a in lecture.bloquantes) == sorted(
        [Regle.FIN_DE_LIGNE, Regle.NOMBRE_COLONNES, Regle.CLE_NON_UNIQUE, Regle.CLE_NON_UNIQUE]
    )
    (colonnes,) = [a for a in lecture.anomalies if a.regle is Regle.NOMBRE_COLONNES]
    assert colonnes.valeur.startswith("11 colonnes au lieu de 12 : ") and colonnes.valeur.endswith(
        "…"
    )
    (cle,) = [a for a in lecture.anomalies if a.regle is Regle.CLE_NON_UNIQUE and a.ligne == 5]
    assert cle.valeur == "déjà vue ligne 1 : " + lecture.lignes[0][1][0]
    assert lecture.anomalies == sorted(lecture.anomalies, key=lambda a: a.ligne)


def test_fixture_fabriquee_specialites_en_utf8() -> None:
    """Un fichier cp1252 qui arrive en UTF-8 se décode sans erreur : le constat est explicite."""
    lecture = verifier(
        charger_identifiant("bdpm.specialites"), (FABRIQUEES / "specialites_utf8.txt").read_bytes()
    )
    (encodage,) = [a for a in lecture.anomalies if a.regle is Regle.ENCODAGE]
    assert encodage.ligne == FICHIER_ENTIER and encodage.bloquante
    assert "se décode entièrement en UTF-8" in encodage.valeur and "cp1252" in encodage.valeur
    assert len(lecture.lignes) == 3, "la lecture continue"
    reel = verifier(
        charger_identifiant("bdpm.specialites"), contenu_fixture_par_nom("CIS_bdpm.txt")
    )
    assert Regle.ENCODAGE not in reel.par_regle(), (
        "le vrai fichier cp1252 ne déclenche pas le constat"
    )


def test_fixture_fabriquee_presentations() -> None:
    """Fichier UTF-8 LF : octet cp1252, ligne CRLF, élément de liste inconnu, décimal, date."""
    lecture = verifier(
        charger_identifiant("bdpm.presentations"),
        (FABRIQUEES / "presentations_anomalies.txt").read_bytes(),
    )
    assert _constats(lecture) == {
        (2, None, Regle.ENCODAGE),
        (3, None, Regle.FIN_DE_LIGNE),
        (3, "taux_remboursement", Regle.VALEUR_INCONNUE),
        (3, "prix_medicament", Regle.DECIMAL_ILLISIBLE),
        (3, "date_declaration_commercialisation", Regle.DATE_HORS_PLAGE),
    }
    (encodage,) = [a for a in lecture.anomalies if a.regle is Regle.ENCODAGE]
    assert encodage.valeur == "octets e9 illisibles en utf-8"
    (fin,) = [a for a in lecture.anomalies if a.regle is Regle.FIN_DE_LIGNE]
    assert fin.valeur == "CRLF au lieu de LF"
    assert len(lecture.lignes) == 3, "la ligne à l'octet illisible est lue avec substitution"
    assert {a.valeur for a in lecture.anomalies if a.colonne == "taux_remboursement"} == {"65%;45%"}


def test_fixture_fabriquee_compositions() -> None:
    lecture = verifier(
        charger_identifiant("bdpm.compositions"),
        (FABRIQUEES / "compositions_anomalies.txt").read_bytes(),
    )
    assert _constats(lecture, sauf=Regle.ESPACE_PARASITE) == {
        (2, "nature_composant", Regle.VALEUR_INCONNUE),
        (2, "numero_liaison", Regle.ENTIER_ILLISIBLE),
        (3, None, Regle.NOMBRE_COLONNES),
    }
    (vide,) = lecture.bloquantes
    assert vide.valeur == "ligne vide", (
        "lignes vides interdites : une ligne vide est un nombre de colonnes faux"
    )
    assert [numero for numero, _ in lecture.lignes] == [1, 2, 4] and lecture.nombre_lignes == 3


def test_fixture_fabriquee_mitm() -> None:
    lecture = verifier(
        charger_identifiant("bdpm.mitm"), (FABRIQUEES / "mitm_anomalies.txt").read_bytes()
    )
    assert _constats(lecture) == {
        (2, "lien_bdpm", Regle.HOTE_INCONNU),
        (3, "lien_bdpm", Regle.URL_ILLISIBLE),
        (3, "code_atc", Regle.CODE_ILLISIBLE),
    }
    assert lecture.bloquantes == [] and Regle.RETOUR_FINAL not in lecture.par_regle(), (
        "retour final toléré"
    )


def test_fixture_fabriquee_bom() -> None:
    lecture = verifier(
        charger_identifiant("bdpm.liens_ct"), (FABRIQUEES / "liens_ct_bom.txt").read_bytes()
    )
    assert _constats(lecture) == {(1, None, Regle.ENCODAGE)}
    assert lecture.anomalies[0].valeur.startswith("marque d'ordre des octets")
    assert len(lecture.lignes) == 3


def test_nom_de_fichier_et_valeur_tronquee() -> None:
    contrat = charger_identifiant("bdpm.conditions_prescription")
    longue = ("12345678\t" + "x" * 300 + "\tcolonne en trop\r\n").encode("cp1252")
    lecture = verifier(contrat, longue, fichier="bronze/bdpm/CIS_CPD_bdpm.txt/2026-10-24/a.txt.gz")
    (anomalie,) = lecture.anomalies
    assert anomalie.fichier.startswith("bronze/") and anomalie.regle is Regle.NOMBRE_COLONNES
    assert len(anomalie.valeur) == 80 and anomalie.valeur.endswith("…")
    vide = verifier(contrat, b"")
    assert vide.anomalies == [] and vide.nombre_lignes == 0 and vide.lignes == []


def _type(nom: TypeNom, **parametres: object) -> TypeValeur:
    return TypeValeur(nom, **parametres)  # type: ignore[arg-type]


ENUM_TAUX = _type(TypeNom.ENUMERATION, valeurs=("65%", "65 %", "100%"))


@pytest.mark.parametrize(
    ("type_", "valeur", "attendu"),
    [
        (_type(TypeNom.TEXTE), "pommade", None),
        (_type(TypeNom.TEXTE), " BOIRON", Regle.ESPACE_PARASITE),
        (_type(TypeNom.TEXTE), "pommade ", Regle.ESPACE_PARASITE),
        (_type(TypeNom.TEXTE, longueur_max=3), "abcd", Regle.LONGUEUR_DEPASSEE),
        (_type(TypeNom.ENTIER), "42", None),
        (_type(TypeNom.ENTIER), "-7", None),
        (_type(TypeNom.ENTIER), "4 2", Regle.ENTIER_ILLISIBLE),
        (_type(TypeNom.ENTIER), "1a", Regle.ENTIER_ILLISIBLE),
        (_type(TypeNom.ENTIER), "٤٢", Regle.ENTIER_ILLISIBLE),
        (_type(TypeNom.DECIMAL), "24,34", None),
        (_type(TypeNom.DECIMAL), "1,003,48", Regle.DECIMAL_ILLISIBLE),
        (_type(TypeNom.DECIMAL), "24.34", Regle.DECIMAL_ILLISIBLE),
        (_type(TypeNom.DECIMAL), "24,3", Regle.DECIMAL_ILLISIBLE),
        (_type(TypeNom.DECIMAL), "1,²³", Regle.DECIMAL_ILLISIBLE),
        (_type(TypeNom.DECIMAL), "1,٢٣", Regle.DECIMAL_ILLISIBLE),
        (_type(TypeNom.DECIMAL, decimales=3), "24,345", None),
        (_type(TypeNom.DATE, format="JJ/MM/AAAA"), "12/03/1998", None),
        (_type(TypeNom.DATE, format="JJ/MM/AAAA"), "31/02/1998", Regle.DATE_ILLISIBLE),
        (_type(TypeNom.DATE, format="JJ/MM/AAAA"), "1/3/1998", Regle.DATE_ILLISIBLE),
        (_type(TypeNom.DATE, format="JJ/MM/AAAA"), "1998-03-12", Regle.DATE_ILLISIBLE),
        (
            _type(TypeNom.DATE, format="JJ/MM/AAAA", plage_min=date(1950, 1, 1)),
            "19/01/1910",
            Regle.DATE_HORS_PLAGE,
        ),
        (
            _type(TypeNom.DATE, format="JJ/MM/AAAA", plage_max=date(2030, 12, 31)),
            "29/11/2924",
            Regle.DATE_HORS_PLAGE,
        ),
        (_type(TypeNom.DATE, format="AAAAMMJJ"), "20260909", None),
        (_type(TypeNom.DATE, format="AAAAMMJJ"), "20261309", Regle.DATE_ILLISIBLE),
        (_type(TypeNom.DATE, format="AAAA-MM-JJ"), "2026-10-31", None),
        (_type(TypeNom.BOOLEEN, vrai="Oui", faux="Non"), "Non", None),
        (_type(TypeNom.BOOLEEN, vrai="Oui", faux="Non"), "oui", Regle.BOOLEEN_INCONNU),
        (ENUM_TAUX, "65 %", None),
        (ENUM_TAUX, "65", Regle.VALEUR_INCONNUE),
        (_type(TypeNom.CODE, motif=CODE_CIS), "61266250", None),
        (_type(TypeNom.CODE, motif=CODE_CIS), "6126625", Regle.CODE_ILLISIBLE),
        (_type(TypeNom.CODE, motif=CODE_CIS), "61266250 ", Regle.CODE_ILLISIBLE),
        (_type(TypeNom.URL), "https://www.has-sante.fr/jcms/p_4461003", None),
        (_type(TypeNom.URL), "www.has-sante.fr/jcms/p_4461003", Regle.URL_ILLISIBLE),
        (_type(TypeNom.URL), "ftp://www.has-sante.fr/x", Regle.URL_ILLISIBLE),
        (
            _type(TypeNom.URL, hotes=("ansm.sante.fr",)),
            "https://www.ansm.sante.fr/x",
            Regle.HOTE_INCONNU,
        ),
        (_type(TypeNom.URL, hotes=("ansm.sante.fr",)), "https://ANSM.sante.fr/x", None),
        (_type(TypeNom.LISTE, de=ENUM_TAUX, separateur=";"), "65%;100%", None),
        (_type(TypeNom.LISTE, de=ENUM_TAUX, separateur=";"), "65%;45%", Regle.VALEUR_INCONNUE),
        (_type(TypeNom.LISTE, de=ENUM_TAUX, separateur=";"), "65%;", Regle.VALEUR_INCONNUE),
        (
            _type(TypeNom.LISTE, de=_type(TypeNom.TEXTE), separateur=";"),
            "orale; cutanée",
            Regle.ESPACE_PARASITE,
        ),
    ],
)
def test_verifier_valeur(type_: TypeValeur, valeur: str, attendu: Regle | None) -> None:
    assert verifier_valeur(type_, valeur) is attendu


def test_regles_bloquantes_sont_les_quatre_de_l_addendum() -> None:
    assert {
        Regle.ENCODAGE,
        Regle.FIN_DE_LIGNE,
        Regle.NOMBRE_COLONNES,
        Regle.CLE_NON_UNIQUE,
    } == REGLES_BLOQUANTES


def test_une_cle_unique_n_a_pas_de_raison() -> None:
    """La « raison » d'une clé dit pourquoi elle n'est pas unique ; une clé unique n'en a pas."""
    for contrat in charger_tous().values():
        assert not contrat.cle.unique or contrat.cle.raison == "", contrat.identifiant
