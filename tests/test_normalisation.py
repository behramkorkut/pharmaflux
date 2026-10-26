"""Mission 02, décision 2 : la forme canonique par type ; une valeur illisible reste brute."""

from datetime import date

import pytest

from pharmaflux.contrats.modele import FORMATS_DATE, Regle, TypeNom, TypeValeur
from pharmaflux.contrats.normalisation import (
    REGLES_DE_FORME,
    REGLES_DE_LISIBILITE,
    Normalisee,
    normaliser_valeur,
)
from tests.test_contrats_verification import CODE_CIS, _type

TAUX = _type(
    TypeNom.ENUMERATION,
    valeurs=("65%", "65 %", "100%", "100 %", "35%"),
    canonique=(("65 %", "65%"), ("100 %", "100%")),
)
PRIX = _type(TypeNom.DECIMAL, milliers=",")
DATE_FR = _type(TypeNom.DATE, format="JJ/MM/AAAA", plage_min=date(1950, 1, 1))
LISTE_TAUX = _type(TypeNom.LISTE, de=TAUX, separateur=";")
LISTE_TEXTE = _type(TypeNom.LISTE, de=_type(TypeNom.TEXTE), separateur=";")


@pytest.mark.parametrize(
    ("type_", "brute", "canonique"),
    [
        (_type(TypeNom.TEXTE), "BIOGARAN", "BIOGARAN"),
        (_type(TypeNom.ENTIER), "42", "42"),
        (_type(TypeNom.ENTIER), "007", "7"),
        (_type(TypeNom.ENTIER), "-0", "0"),
        (_type(TypeNom.DECIMAL), "12,50", "12.50"),
        (_type(TypeNom.DECIMAL), "0,50", "0.50"),
        (_type(TypeNom.DECIMAL), "007,50", "7.50"),
        (_type(TypeNom.DECIMAL, decimales=3), "24,345", "24.345"),
        (PRIX, "1,003,48", "1003.48"),
        (PRIX, "66,596,25", "66596.25"),
        (PRIX, "1003,48", "1003.48"),
        (DATE_FR, "19/01/2026", "2026-01-19"),
        (_type(TypeNom.DATE, format="AAAAMMJJ"), "20260909", "2026-09-09"),
        (_type(TypeNom.DATE, format="AAAA-MM-JJ"), "2026-10-31", "2026-10-31"),
        (_type(TypeNom.BOOLEEN, vrai="Oui", faux="Non"), "Oui", "true"),
        (_type(TypeNom.BOOLEEN, vrai="Oui", faux="Non"), "Non", "false"),
        (TAUX, "65 %", "65%"),
        (TAUX, "65%", "65%"),
        (TAUX, "35%", "35%"),
        (_type(TypeNom.CODE, motif=CODE_CIS), "61266250", "61266250"),
        (
            _type(TypeNom.URL),
            "https://www.has-sante.fr/jcms/p_4461003",
            "https://www.has-sante.fr/jcms/p_4461003",
        ),
        (LISTE_TAUX, "65 %;100 %", "65%;100%"),
        (LISTE_TAUX, "65%;65 %;65%", "65%;65%;65%"),
    ],
)
def test_une_valeur_conforme_prend_sa_forme_canonique(
    type_: TypeValeur, brute: str, canonique: str
) -> None:
    assert normaliser_valeur(type_, brute) == Normalisee(canonique, None)


@pytest.mark.parametrize(
    ("type_", "brute", "regle"),
    [
        (_type(TypeNom.ENTIER), "4 2", Regle.ENTIER_ILLISIBLE),
        (_type(TypeNom.ENTIER), "٤٢", Regle.ENTIER_ILLISIBLE),
        (_type(TypeNom.DECIMAL), "1,003,48", Regle.DECIMAL_ILLISIBLE),
        (_type(TypeNom.DECIMAL), "12.50", Regle.DECIMAL_ILLISIBLE),
        (PRIX, "1,03,48", Regle.DECIMAL_ILLISIBLE),
        (PRIX, "NaN", Regle.DECIMAL_ILLISIBLE),
        (DATE_FR, "31/02/2026", Regle.DATE_ILLISIBLE),
        (DATE_FR, "2026-01-19", Regle.DATE_ILLISIBLE),
        (_type(TypeNom.BOOLEEN, vrai="Oui", faux="Non"), "oui", Regle.BOOLEEN_INCONNU),
        (TAUX, "65", Regle.VALEUR_INCONNUE),
        (TAUX, "65  %", Regle.VALEUR_INCONNUE),
        (_type(TypeNom.CODE, motif=CODE_CIS), "6126625", Regle.CODE_ILLISIBLE),
        (_type(TypeNom.URL), "www.has-sante.fr/x", Regle.URL_ILLISIBLE),
    ],
)
def test_une_valeur_illisible_reste_brute_avec_sa_regle(
    type_: TypeValeur, brute: str, regle: Regle
) -> None:
    normalisee = normaliser_valeur(type_, brute)
    assert normalisee == Normalisee(brute, regle)
    assert normalisee.valeur is brute, "la brute, pas une copie"
    assert regle in REGLES_DE_LISIBILITE


@pytest.mark.parametrize(
    ("type_", "brute", "canonique", "regle"),
    [
        (_type(TypeNom.TEXTE), " BIOGARAN", "BIOGARAN", Regle.ESPACE_PARASITE),
        (_type(TypeNom.TEXTE), "pommade ", "pommade", Regle.ESPACE_PARASITE),
        (_type(TypeNom.TEXTE), " a  b ", "a  b", Regle.ESPACE_PARASITE),
        (_type(TypeNom.TEXTE, longueur_max=3), "abcd", "abcd", Regle.LONGUEUR_DEPASSEE),
        (_type(TypeNom.TEXTE, longueur_max=3), " abcd ", "abcd", Regle.ESPACE_PARASITE),
        (DATE_FR, "19/01/1949", "1949-01-19", Regle.DATE_HORS_PLAGE),
        (
            _type(TypeNom.DATE, format="JJ/MM/AAAA", plage_max=date(2030, 12, 31)),
            "29/11/2924",
            "2924-11-29",
            Regle.DATE_HORS_PLAGE,
        ),
        (
            _type(TypeNom.URL, hotes=("ansm.sante.fr",)),
            "https://www.ansm.sante.fr/x",
            "https://www.ansm.sante.fr/x",
            Regle.HOTE_INCONNU,
        ),
        (LISTE_TEXTE, "orale; cutanée", "orale;cutanée", Regle.ESPACE_PARASITE),
    ],
)
def test_une_anomalie_de_forme_laisse_passer_la_forme_canonique(
    type_: TypeValeur, brute: str, canonique: str, regle: Regle
) -> None:
    """La valeur se lit ; l'anomalie dit sa forme ou sa vraisemblance, et reste consignée."""
    assert normaliser_valeur(type_, brute) == Normalisee(canonique, regle)
    assert regle in REGLES_DE_FORME


def test_les_regles_de_valeur_sont_toutes_classees() -> None:
    """Chaque règle qui porte sur une valeur est de lisibilité ou de forme, jamais les deux."""
    regles_de_ligne = {
        Regle.ENCODAGE,
        Regle.FIN_DE_LIGNE,
        Regle.NOMBRE_COLONNES,
        Regle.CLE_NON_UNIQUE,
        Regle.RETOUR_FINAL,
        Regle.LIGNE_VIDE,
        Regle.LIGNE_DUPLIQUEE,
        Regle.VALEUR_MANQUANTE,
        Regle.FICHIER_VIDE,
    }
    assert REGLES_DE_FORME.isdisjoint(REGLES_DE_LISIBILITE)
    assert REGLES_DE_FORME | REGLES_DE_LISIBILITE | regles_de_ligne == set(Regle)


def test_une_liste_se_normalise_element_par_element() -> None:
    """Un élément illisible reste brut ; les autres prennent leur forme canonique."""
    assert normaliser_valeur(LISTE_TAUX, "65 %;45%") == Normalisee("65%;45%", Regle.VALEUR_INCONNUE)
    assert normaliser_valeur(LISTE_TAUX, "65%;") == Normalisee("65%;", Regle.VALEUR_INCONNUE)
    assert normaliser_valeur(LISTE_TAUX, "100 %;65 %;100 %") == Normalisee("100%;65%;100%", None), (
        "même ordre, pas de dédoublonnage"
    )


def test_le_vide_reste_vide() -> None:
    for type_ in (_type(TypeNom.TEXTE), PRIX, DATE_FR, TAUX, LISTE_TAUX):
        assert normaliser_valeur(type_, "") == Normalisee("", None)


def test_une_valeur_inchangee_est_le_meme_objet() -> None:
    """Le snapshot partage les chaînes : la forme canonique égale à la brute est la brute."""
    for type_, brute in (
        (_type(TypeNom.TEXTE), "BIOGARAN"),
        (_type(TypeNom.ENTIER), "42"),
        (TAUX, "65%"),
        (_type(TypeNom.DATE, format="AAAA-MM-JJ"), "2026-10-31"),
        (LISTE_TAUX, "65%;100%"),
        (_type(TypeNom.URL), "https://www.has-sante.fr/jcms/p_4461003"),
    ):
        assert normaliser_valeur(type_, brute).valeur is brute


def test_les_dates_iso_valent_strptime() -> None:
    """Le découpage par format donne la même date que ``strptime`` (le motif étant vérifié)."""
    for format_, brute in (("JJ/MM/AAAA", "07/03/2024"), ("AAAAMMJJ", "20240307")):
        from datetime import datetime

        attendue = datetime.strptime(brute, FORMATS_DATE[format_][1]).date().isoformat()
        assert normaliser_valeur(_type(TypeNom.DATE, format=format_), brute).valeur == attendue
