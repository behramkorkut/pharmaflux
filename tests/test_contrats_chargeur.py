"""Mission 01, décision 2 : les onze contrats du paquet et le refus des contrats mal formés."""

from pathlib import Path

import pytest

from pharmaflux.contrats import chargeur
from pharmaflux.contrats.chargeur import (
    ContratIntrouvable,
    ContratInvalide,
    charger,
    charger_identifiant,
    charger_octets,
    charger_tous,
)
from pharmaflux.contrats.modele import FinDeLigne, LignesVides, RetourFinal, TypeNom
from tests.conftest import entrees_bdpm_txt

CONTRAT_MINIMAL = """\
version = "v0"
identifiant = "essai.minimal"
fichier = "minimal.txt"
description = "Contrat d'essai"

[source]
documentation = "doc.pdf"
documentation_sha256 = "db10d5a62bc640c227405bcb11cef5db9ad2a2d9a6b4b547198ee19978b6bc8b"
section = "3.1"
date_verification = 2026-10-26
archive_reference = "bronze/essai/minimal.txt/2026-10-24/a.txt.gz"
archive_sha256 = "332b95926f76f1a2ab3d70cdf64205397fc13e74b7cc9afad9b625fbb6961640"

[format]
encodage = "cp1252"
fin_de_ligne = "CRLF"

[[colonnes]]
nom = "code"
type = "code"
motif = '\\d{3}'
obligatoire = true

[[colonnes]]
nom = "statut"
type = "enumeration"
valeurs = ["a", "b"]
obligatoire = true

[[colonnes]]
nom = "jour"
type = "date"
format = "JJ/MM/AAAA"
plage_min = 2000-01-01
obligatoire = false

[cle]
colonnes = ["code"]
unique = true

[[liens]]
colonne = "code"
vers = "essai.autre"
colonne_cible = "code"
"""


def _charger(texte: str):  # type: ignore[no-untyped-def]
    return charger_octets(texte.encode("utf-8"), "essai.toml")


def test_les_onze_contrats_du_paquet_se_chargent_et_suivent_le_catalogue() -> None:
    """Un contrat par fichier TSV du catalogue, même identifiant, même nom de fichier."""
    contrats = charger_tous()
    attendus = {entree.identifiant: entree.fichier for entree in entrees_bdpm_txt()}
    assert len(attendus) == 11
    assert {identifiant: c.fichier for identifiant, c in contrats.items()} == attendus
    for identifiant, contrat in contrats.items():
        assert contrat.version == "v0" and contrat.identifiant == identifiant
        assert charger_identifiant(identifiant) == contrat
        assert contrat.source.documentation.endswith("_v5.pdf")
        assert contrat.source.archive_reference.startswith(
            f"bronze/bdpm/{contrat.fichier}/2026-10-24/"
        )
        for lien in contrat.liens:
            assert lien.colonne_cible in contrats[lien.vers].noms_colonnes


def test_les_contrats_disent_ce_que_l_archive_du_24_10_a_montre() -> None:
    """Les constats du §0 sont dans les contrats, pas dans des tolérances cachées."""
    contrats = charger_tous()
    non_uniques = {i for i, c in contrats.items() if not c.cle.unique}
    assert non_uniques == {"bdpm.smr", "bdpm.asmr", "bdpm.disponibilite"}
    assert all(contrats[i].cle.raison for i in non_uniques)
    assert contrats["bdpm.mitm"].format.retour_final is RetourFinal.TOLERE
    assert contrats["bdpm.conditions_prescription"].format.lignes_vides is LignesVides.ANOMALIE
    utf8 = {i for i, c in contrats.items() if c.format.encodage == "utf-8"}
    assert utf8 == {"bdpm.presentations", "bdpm.infos_importantes"}
    assert all(contrats[i].format.fin_de_ligne is FinDeLigne.LF for i in utf8)
    taux = contrats["bdpm.presentations"].colonnes[8]
    assert taux.nom == "taux_remboursement" and taux.type.nom is TypeNom.LISTE
    assert taux.type.de is not None and "65 %" in taux.type.de.valeurs
    formats = {
        c.type.format for contrat in contrats.values() for c in contrat.colonnes if c.type.format
    }
    assert formats == {"JJ/MM/AAAA", "AAAAMMJJ", "AAAA-MM-JJ"}


def test_contrat_introuvable() -> None:
    with pytest.raises(ContratIntrouvable, match=r"bdpm/inexistant\.toml"):
        charger_identifiant("bdpm.inexistant")
    with pytest.raises(ContratIntrouvable):
        charger_identifiant("sans_point")


def test_contrat_minimal_valide() -> None:
    contrat = _charger(CONTRAT_MINIMAL)
    assert contrat.noms_colonnes == ("code", "statut", "jour")
    assert (
        contrat.format.separateur == "\t" and contrat.format.retour_final is RetourFinal.OBLIGATOIRE
    )
    assert (
        contrat.colonnes[2].type.plage_min is not None
        and contrat.colonnes[2].type.plage_max is None
    )
    assert contrat.index("jour") == 2 and contrat.liens[0].vers == "essai.autre"


@pytest.mark.parametrize(
    ("ancien", "nouveau", "message"),
    [
        ('version = "v0"', 'version = "v1"', "version « v1 »"),
        (
            'description = "Contrat d\'essai"',
            'description = "Contrat d\'essai"\ncouleur = "bleu"',
            "inconnue",
        ),
        ('identifiant = "essai.minimal"', 'identifiant = "Essai Minimal"', "hors forme"),
        ('encodage = "cp1252"', 'encodage = "klingon"', "encodage « klingon » inconnu"),
        ('fin_de_ligne = "CRLF"', 'fin_de_ligne = "CR"', "attendu : CRLF, LF"),
        (
            'fin_de_ligne = "CRLF"',
            'fin_de_ligne = "CRLF"\nretour_final = "parfois"',
            "retour_final",
        ),
        ("type = \"code\"\nmotif = '\\d{3}'", 'type = "chaine"', "type « chaine » inconnu"),
        ("type = \"code\"\nmotif = '\\d{3}'", "type = \"code\"\nmotif = '('", "motif"),
        ("type = \"code\"\nmotif = '\\d{3}'", 'type = "code"', "« motif » manquante"),
        ("type = \"code\"\nmotif = '\\d{3}'", 'type = "texte"\nvaleurs = ["a"]', "sans objet"),
        ('valeurs = ["a", "b"]', "valeurs = []", "sans valeurs"),
        ('valeurs = ["a", "b"]', 'valeurs = ["a", "a"]', "en double"),
        ('valeurs = ["a", "b"]', 'valeurs = ["a", 2]', "liste de chaînes"),
        ('format = "JJ/MM/AAAA"', 'format = "MM/JJ/AAAA"', "format de date"),
        (
            "plage_min = 2000-01-01",
            "plage_min = 2000-01-01\nplage_max = 1999-12-31",
            "plage_min après",
        ),
        ("plage_min = 2000-01-01", 'plage_min = "2000-01-01"', "date TOML"),
        ("obligatoire = false", 'obligatoire = "non"', "booléen"),
        ("obligatoire = false", "", "« obligatoire » manquante"),
        ('nom = "jour"', 'nom = "code"', "en double : code"),
        ('nom = "jour"', 'nom = "Jour de l\'avis"', "snake_case"),
        (
            'colonnes = ["code"]\nunique = true',
            'colonnes = ["cip"]\nunique = true',
            "inconnue(s) : cip",
        ),
        (
            'colonnes = ["code"]\nunique = true',
            'colonnes = ["code"]\nunique = false',
            "exige une « raison »",
        ),
        (
            'colonnes = ["code"]\nunique = true',
            'colonnes = ["code"]\nunique = true\nraison = "x"',
            "n'a de sens",
        ),
        ('colonnes = ["code"]\nunique = true', "colonnes = []\nunique = true", "sans colonne"),
        (
            'colonne = "code"\nvers = "essai.autre"',
            'colonne = "nope"\nvers = "essai.autre"',
            "inconnue(s) : nope",
        ),
        ('vers = "essai.autre"', 'vers = "autre"', "identifiant du catalogue"),
        ('documentation_sha256 = "db10', 'documentation_sha256 = "zz10', "sha256"),
        (
            "date_verification = 2026-10-26",
            "date_verification = 2026-10-26T10:00:00Z",
            "sans heure",
        ),
    ],
)
def test_contrat_mal_forme_refuse(ancien: str, nouveau: str, message: str) -> None:
    assert ancien in CONTRAT_MINIMAL, "le cas de test ne porte sur rien"
    texte = CONTRAT_MINIMAL.replace(ancien, nouveau, 1)
    with pytest.raises(ContratInvalide, match=message.replace("(", r"\(").replace(")", r"\)")):
        _charger(texte)


def test_liste_de_listes_et_liste_sans_separateur_refusees() -> None:
    de_liste = 'de = { type = "liste", separateur = ",", de = { type = "texte" } }'
    liste = f'type = "liste"\nseparateur = ";"\n{de_liste}'
    with pytest.raises(ContratInvalide, match="liste de listes"):
        _charger(CONTRAT_MINIMAL.replace("type = \"code\"\nmotif = '\\d{3}'", liste))
    with pytest.raises(ContratInvalide, match="« separateur » manquante"):
        _charger(
            CONTRAT_MINIMAL.replace(
                "type = \"code\"\nmotif = '\\d{3}'", 'type = "liste"\nde = { type = "texte" }'
            )
        )
    with pytest.raises(ContratInvalide, match=r"de : clé\(s\) inconnue\(s\)"):
        _charger(
            CONTRAT_MINIMAL.replace(
                "type = \"code\"\nmotif = '\\d{3}'",
                'type = "liste"\nseparateur = ";"\nde = { type = "texte", motif = "x" }',
            )
        )


def test_toml_illisible_et_fichier_absent(tmp_path: Path) -> None:
    with pytest.raises(ContratInvalide, match="TOML illisible"):
        _charger("version = ")
    with pytest.raises(ContratInvalide, match="illisible"):
        charger(tmp_path / "absent.toml")
    chemin = tmp_path / "minimal.toml"
    chemin.write_text(CONTRAT_MINIMAL, encoding="utf-8")
    assert charger(chemin).identifiant == "essai.minimal"


def test_charger_tous_verifie_les_liens_entre_contrats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un lien vers un contrat absent ou une colonne absente est refusé à l'échelle du jeu."""
    dossier = tmp_path / "essai"
    dossier.mkdir()
    (dossier / "minimal.toml").write_text(CONTRAT_MINIMAL, encoding="utf-8")
    monkeypatch.setattr(chargeur, "_dossier", lambda source: tmp_path / source)
    with pytest.raises(ContratInvalide, match=r"essai\.autre », contrat absent"):
        charger_tous("essai")
    autre = CONTRAT_MINIMAL.replace(
        'identifiant = "essai.minimal"', 'identifiant = "essai.autre"'
    ).replace('nom = "code"', 'nom = "identifiant"')
    autre = autre.replace('colonnes = ["code"]', 'colonnes = ["identifiant"]').replace(
        'colonne = "code"', 'colonne = "identifiant"'
    )
    (dossier / "autre.toml").write_text(autre, encoding="utf-8")
    with pytest.raises(ContratInvalide, match=r"lien vers essai\.autre\.code, colonne absente"):
        charger_tous("essai")
    (dossier / "autre.toml").write_text(
        autre.replace('colonne_cible = "code"', 'colonne_cible = "identifiant"'), encoding="utf-8"
    )
    (dossier / "minimal.toml").write_text(
        CONTRAT_MINIMAL.replace('colonne_cible = "code"', 'colonne_cible = "identifiant"'),
        encoding="utf-8",
    )
    assert set(charger_tous("essai")) == {"essai.minimal", "essai.autre"}
    (dossier / "faux.toml").write_text(CONTRAT_MINIMAL, encoding="utf-8")
    with pytest.raises(ContratInvalide, match=r"identifiant essai\.minimal, attendu essai\.faux"):
        charger_tous("essai")
