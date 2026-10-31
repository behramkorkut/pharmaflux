"""Mission 01, décisions 7 et 8 : le jeu de questions de référence et son rejeu."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.collecte.archive import chemin_archive, ecrire_archive
from pharmaflux.collecte.empreintes import sha256_hex
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evaluation.questions import (
    CATEGORIES,
    Comportement,
    JeuInvalide,
    charger,
    charger_octets,
)
from pharmaflux.evaluation.verification import Verdict, formater_bilan, verifier_jeu
from tests.conftest import FIXTURES, entree, texte_nu

lanceur = CliRunner()
JEU_REFERENCE = Path(__file__).parent.parent / "evaluation" / "questions-reference-v0.toml"
JEU_ESSAI = FIXTURES / "evaluation" / "questions-essai.toml"
INSTANT = datetime(2026, 10, 24, 14, 17, tzinfo=UTC)

QUESTION_MINIMALE = """\
version = "v0"
description = "Essai"

[[questions]]
id = "disponibilite-001"
categorie = "disponibilite"
question = "Essai ?"
comportement = "reponse"

[questions.attendu]
date_reference = 2026-10-24
fichier = "bdpm.disponibilite"
archive = "bronze/bdpm/CIS_CIP_Dispo_Spec.txt/2026-10-24/20261024T194201Z__43b7d2f3cfe6.txt.gz"
sha256 = "43b7d2f3cfe699fffded55893472d9fa17fd77964c5e3a31d4017160b8d35ed6"
cle = { code_cis = "65999556" }
colonnes = ["libelle_statut"]

[[questions.attendu.valeurs]]
libelle_statut = "Rupture de stock"
"""


@pytest.fixture
def racine_essai(racine: Path) -> Path:
    """Les fixtures archivées sous les noms que cite le jeu d'essai (horodatage figé)."""
    for identifiant in ("bdpm.disponibilite", "bdpm.generiques", "bdpm.specialites"):
        e = entree(identifiant)
        octets = (FIXTURES / "bdpm" / e.fichier).read_bytes()
        ecrire_archive(chemin_archive(racine, e, INSTANT, sha256_hex(octets)), octets, INSTANT)
    return racine


def _charger(texte: str):  # type: ignore[no-untyped-def]
    return charger_octets(texte.encode("utf-8"), "essai.toml", charger_tous())


# Le jeu v0 du dépôt


def test_le_jeu_v0_a_quarante_questions_cinq_par_categorie() -> None:
    contrats = charger_tous()
    jeu = charger(JEU_REFERENCE, contrats)
    assert len(jeu.questions) == 40
    assert {c: len(q) for c, q in jeu.par_categorie().items()} == dict.fromkeys(CATEGORIES, 5)
    ids = [q.id for q in jeu.questions]
    assert ids == sorted(ids, key=lambda i: (CATEGORIES.index(i.rsplit("-", 1)[0]), i))
    assert all(
        f"{q.categorie}-{n:03d}" == q.id
        for c in CATEGORIES
        for n, q in enumerate(jeu.par_categorie()[c], 1)
    )


def test_le_jeu_v0_suit_l_addendum() -> None:
    """Dépense sans valeur (lot 4), CIS absents en abstention, un seul début futur, voulu."""
    contrats = charger_tous()
    jeu = charger(JEU_REFERENCE, contrats)
    groupes = jeu.par_categorie()
    assert all(q.attendu is None and q.calculable_au == "lot4" for q in groupes["depense"])
    assert all(q.comportement is Comportement.ABSTENTION for q in groupes["hors_perimetre"])
    assert all(q.comportement is Comportement.REFUS_MEDICAL for q in groupes["medical"])
    absents = [
        q
        for q in jeu.questions
        if q.comportement is Comportement.ABSTENTION
        and q.attendu is not None
        and q.attendu.fichier == "bdpm.specialites"
        and not q.attendu.valeurs
    ]
    assert len(absents) == 2, "au moins une question sur un CIS absent de CIS_bdpm.txt"
    futurs = [q for q in groupes["historique"] if q.prudence and "2027" in q.prudence]
    assert [q.id for q in futurs] == ["historique-005"]
    for question in jeu.questions:
        if question.attendu is not None:
            contrat = contrats[question.attendu.fichier]
            assert question.attendu.archive == contrat.source.archive_reference, question.id
            assert question.attendu.sha256 == contrat.source.archive_sha256, question.id
            assert question.attendu.date_reference.isoformat() == "2026-10-24"
            for ligne in question.attendu.valeurs:
                assert all(v == v.strip() for v in ligne.values()), question.id
    assert {q.attendu.fichier for q in jeu.questions if q.attendu} >= {
        "bdpm.disponibilite",
        "bdpm.generiques",
        "bdpm.presentations",
        "bdpm.smr",
        "bdpm.asmr",
        "bdpm.liens_ct",
        "bdpm.specialites",
    }


# Lecture stricte


@pytest.mark.parametrize(
    ("ancien", "nouveau", "message"),
    [
        ('version = "v0"', 'version = "v2"', "version « v2 »"),
        ('description = "Essai"', 'description = "Essai"\ncouleur = "bleu"', "inconnue"),
        ('id = "disponibilite-001"', 'id = "dispo 1"', "hors forme"),
        ('id = "disponibilite-001"', 'id = "alternatives-001"', "ne commence pas par"),
        ('categorie = "disponibilite"', 'categorie = "stock"', "catégorie « stock » inconnue"),
        ('comportement = "reponse"', 'comportement = "oui"', "comportement « oui » inconnu"),
        (
            'comportement = "reponse"',
            'comportement = "reponse"\nmotif = "x"',
            "abstention ou un refus",
        ),
        (
            'comportement = "reponse"',
            'comportement = "reponse"\ncalculable_au = "lot4"',
            "pas les deux",
        ),
        (
            'comportement = "reponse"',
            'comportement = "reponse"\ncalculable_au = "lot9"',
            "lot1 à lot5",
        ),
        ('comportement = "reponse"', 'comportement = "abstention"', "exige un « motif »"),
        ('comportement = "reponse"', 'comportement = "abstention"\nmotif = "x"', "aucune ligne"),
        (
            'comportement = "reponse"',
            'comportement = "refus_medical"\nmotif = "x"',
            "pas d'« attendu »",
        ),
        ("date_reference = 2026-10-24", "date_reference = 2026-10-23", "jour de référence"),
        ("date_reference = 2026-10-24", 'date_reference = "2026-10-24"', "date TOML"),
        ('fichier = "bdpm.disponibilite"', 'fichier = "bdpm.stock"', "sans contrat"),
        ('archive = "bronze/', 'archive = "silver/', "chemin bronze/bdpm/CIS_CIP_Dispo_Spec.txt"),
        (
            'archive = "bronze/bdpm/CIS_CIP_Dispo_Spec.txt/',
            'archive = "bronze/bdpm/CIS_bdpm.txt/',
            "le dossier bronze de bdpm.disponibilite",
        ),
        ("/2026-10-24/20261024T", "/2026-10-24/../20261024T", "nom du fichier archivé"),
        ("/2026-10-24/20261024T", "/2026-10-24/x/20261024T", "nom du fichier archivé"),
        ("43b7d2f3cfe6.txt.gz", "43b7d2f3cfe6.txt", "nom du fichier archivé"),
        ('sha256 = "43b7', 'sha256 = "zz7b', "sha256 hexadécimal"),
        ('cle = { code_cis = "65999556" }', "cle = { }", "clé sans colonne"),
        ('cle = { code_cis = "65999556" }', "cle = { code_cis = 65999556 }", "une chaîne"),
        (
            'cle = { code_cis = "65999556" }',
            'cle = { cis = "65999556" }',
            "inconnue(s) de bdpm.disponibilite : cis",
        ),
        ('colonnes = ["libelle_statut"]', "colonnes = []", "aucune colonne"),
        (
            'colonnes = ["libelle_statut"]',
            'colonnes = ["libelle_statut", "libelle_statut"]',
            "en double",
        ),
        ('libelle_statut = "Rupture de stock"', 'statut = "Rupture de stock"', "ni plus ni moins"),
        (
            'libelle_statut = "Rupture de stock"',
            'libelle_statut = "Rupture de stock"\ndate_debut = "x"',
            "ni plus ni moins",
        ),
    ],
)
def test_jeu_mal_forme_refuse(ancien: str, nouveau: str, message: str) -> None:
    assert ancien in QUESTION_MINIMALE, "le cas de test ne porte sur rien"
    texte = QUESTION_MINIMALE.replace(ancien, nouveau, 1)
    with pytest.raises(JeuInvalide, match=message.replace("(", r"\(").replace(")", r"\)")):
        _charger(texte)


_DEPENSE_V1 = """\
version = "v1"
description = "Essai v1"
instant = "2026-10-27T00:17:12Z"

[[questions]]
id = "depense-001"
categorie = "depense"
question = "Quelle dépense remboursée en 2025 pour les statines ?"
comportement = "abstention"
motif = "la dépense remboursée (Open Medic) n'est pas disponible avant le Lot 4"
calculable_au = "lot4"
"""


def test_v1_accepte_une_abstention_differee_de_depense() -> None:
    """Contrôle du palier 1, point 1 : en v1 une abstention peut porter « calculable_au »
    (l'assistant s'abstient, la dépense devient calculable au Lot 4)."""
    jeu = _charger(_DEPENSE_V1)
    (question,) = jeu.questions
    assert question.comportement is Comportement.ABSTENTION
    assert question.calculable_au == "lot4"
    assert question.motif is not None


def test_v0_refuse_une_abstention_avec_calculable_au() -> None:
    """La v0 ne change pas : « calculable_au » n'a de sens que pour une réponse."""
    texte = _DEPENSE_V1.replace('version = "v1"', 'version = "v0"').replace(
        '\ninstant = "2026-10-27T00:17:12Z"', ""
    )
    with pytest.raises(JeuInvalide, match="n'a de sens que pour une réponse"):
        _charger(texte)


def test_identifiants_en_double_et_fichier_absent(tmp_path: Path) -> None:
    double = QUESTION_MINIMALE + "\n" + QUESTION_MINIMALE.split("\n", 3)[3]
    with pytest.raises(JeuInvalide, match="en double : disponibilite-001"):
        _charger(double)
    with pytest.raises(JeuInvalide, match="TOML illisible"):
        _charger("version = ")
    with pytest.raises(JeuInvalide, match="illisible"):
        charger(tmp_path / "absent.toml", charger_tous())


# Rejeu


def test_rejeu_du_jeu_d_essai_conforme(racine_essai: Path) -> None:
    contrats = charger_tous()
    jeu = charger(JEU_ESSAI, contrats)
    bilan = verifier_jeu(jeu, racine_essai, contrats)
    verdicts = {r.question.id: r.verdict for r in bilan.resultats}
    assert verdicts == {
        "disponibilite-001": Verdict.CONFORME,
        "disponibilite-002": Verdict.CONFORME,
        "historique-001": Verdict.CONFORME,
        "alternatives-001": Verdict.CONFORME,
        "avis_has-001": Verdict.CONFORME,
        "depense-001": Verdict.NON_CALCULABLE,
        "hors_perimetre-001": Verdict.SANS_ATTENDU,
        "medical-001": Verdict.SANS_ATTENDU,
    }
    assert bilan.code_sortie == 0 and not bilan.echecs
    details = {r.question.id: r.detail for r in bilan.resultats}
    assert details["disponibilite-002"] == "2 ligne(s)" and details["avis_has-001"] == "0 ligne(s)"
    assert bilan.resume() == "8 question(s) : 5 conforme, 1 non calculable, 2 sans attendu."
    texte = formater_bilan(bilan)
    assert texte.splitlines()[0] == "conforme        disponibilite-001    1 ligne(s)"
    assert texte.splitlines()[-1] == bilan.resume()


def test_rejeu_signale_chaque_echec(racine_essai: Path) -> None:
    contrats = charger_tous()
    texte = JEU_ESSAI.read_text(encoding="utf-8")
    cas = (
        ('date_debut = "25/06/2026"', 'date_debut = "26/06/2026"'),
        ('code_cis = "65999556" }', 'code_cis = "00000000" }'),
        ("fb5c69b300941d57", "fb5c69b300941d58"),
        ("20261024T141700Z__fb5c69b30094", "20261024T151700Z__fb5c69b30094"),
    )
    attendus = (
        (Verdict.ECART, "ligne 1, date_debut : attendu « 26/06/2026 », lu « 25/06/2026 »"),
        (Verdict.ECART, "1 ligne(s) attendue(s), 0 trouvée(s)"),
        (Verdict.SHA256_DIFFERENT, "lu fb5c69b300941d57"),
        (Verdict.ARCHIVE_INTROUVABLE, "20261024T151700Z__fb5c69b30094.txt.gz"),
    )
    for (ancien, nouveau), (verdict, detail) in zip(cas, attendus, strict=True):
        assert ancien in texte
        jeu = charger_octets(texte.replace(ancien, nouveau, 1).encode(), "essai", contrats)
        bilan = verifier_jeu(jeu, racine_essai, contrats)
        premier = bilan.resultats[0]
        assert premier.verdict is verdict and detail in premier.detail, (ancien, premier)
        assert premier.echec and bilan.code_sortie == 1


def test_rejeu_refuse_une_archive_non_conforme(racine: Path) -> None:
    """Une archive à anomalie bloquante n'a pas de colonnes fiables : on s'arrête là."""
    contrats = charger_tous()
    fabriquee = (FIXTURES / "contrats" / "specialites_anomalies.txt").read_bytes()
    sha256 = sha256_hex(fabriquee)
    e = entree("bdpm.specialites")
    ecrire_archive(chemin_archive(racine, e, INSTANT, sha256), fabriquee, INSTANT)
    texte = QUESTION_MINIMALE.replace(
        "20261024T194201Z__43b7d2f3cfe6", f"20261024T141700Z__{sha256[:12]}"
    )
    texte = texte.replace("CIS_CIP_Dispo_Spec.txt", "CIS_bdpm.txt")
    texte = texte.replace(
        "43b7d2f3cfe699fffded55893472d9fa17fd77964c5e3a31d4017160b8d35ed6", sha256
    )
    texte = texte.replace('fichier = "bdpm.disponibilite"', 'fichier = "bdpm.specialites"')
    texte = texte.replace('colonnes = ["libelle_statut"]', 'colonnes = ["denomination"]')
    texte = texte.replace('libelle_statut = "Rupture de stock"', 'denomination = "x"')
    jeu = charger_octets(texte.encode(), "essai", contrats)
    (resultat,) = verifier_jeu(jeu, racine, contrats).resultats
    assert resultat.verdict is Verdict.ARCHIVE_NON_CONFORME
    assert resultat.detail == "cle_non_unique, fin_de_ligne, nombre_colonnes"


# Ligne de commande


def test_commande_questions_verifier(racine_essai: Path, tmp_path: Path) -> None:
    arguments = [
        "questions",
        "verifier",
        "--racine",
        str(racine_essai),
        "--questions",
        str(JEU_ESSAI),
    ]
    resultat = lanceur.invoke(application, arguments)
    assert resultat.exit_code == 0, resultat.output
    assert "8 question(s) : 5 conforme" in resultat.output

    vide = racine_essai / "vide"
    resultat = lanceur.invoke(application, [*arguments[:3], str(vide), *arguments[4:]])
    assert resultat.exit_code == 1
    assert resultat.output.count("archive introuvable  ") == 5

    invalide = tmp_path / "invalide.toml"
    invalide.write_text(QUESTION_MINIMALE.replace('version = "v0"', 'version = "v9"'))
    resultat = lanceur.invoke(application, [*arguments[:5], str(invalide)])
    assert resultat.exit_code == 2 and "v9" in texte_nu(resultat.output)

    resultat = lanceur.invoke(application, ["questions", "verifier", "--help"])
    assert resultat.exit_code == 0 and "questions-reference-v0.toml" in resultat.output
