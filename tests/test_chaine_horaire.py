"""Mission 10, palier 2 : le passage horaire, les vérifications, le témoin des formats, l'état.

Aucun service n'est joint : les étapes et les sondes sont simulées comme au palier 1
(``tests/test_chaine.py``), et le manifeste est écrit à la main dans un dossier temporaire.
Le passage réel, sur le jeu de démo et contre un bus, tourne dans la CI.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.chaine import etapes, etat, formats, horaire, journal, passage, verification
from pharmaflux.chaine.chemins import Chemins, resoudre
from pharmaflux.chaine.etapes import Resultat
from pharmaflux.chaine.verrou import verrou
from tests.conftest import commande_cli, texte_nu
from tests.test_chaine import Simulation

lanceur = CliRunner()
ETAPES = ["evenements", "schemas", "publier", "silver", "index"]
VERIFICATIONS = ["verifier-bus", "silver-verifier", "index-verifier", "index-etat"]


@pytest.fixture(autouse=True)
def sans_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("PHARMAFLUX_DERIVE", "PHARMAFLUX_DATA", "PHARMAFLUX_MODELES"):
        monkeypatch.delenv(variable, raising=False)
    for nom in horaire.VARIABLES_DECLENCHEUR.values():
        monkeypatch.delenv(nom, raising=False)


@pytest.fixture
def chemins(tmp_path: Path) -> Chemins:
    racine = tmp_path / "archive"
    racine.mkdir()
    return resoudre(racine, tmp_path / "derive")


@pytest.fixture
def simulation(monkeypatch: pytest.MonkeyPatch) -> Simulation:
    return Simulation(monkeypatch)


def _ligne(passage_id: str, fin: str, archive: str | None, identifiant: str) -> dict[str, Any]:
    return {
        "passage_id": passage_id,
        "identifiant": identifiant,
        "source": "bdpm",
        "fichier": "CIS_bdpm.txt",
        "url": "https://exemple.invalid/CIS_bdpm.txt",
        "debut": fin,
        "fin": fin,
        "statut": "nouveau" if archive else "inchange",
        "version_collecteur": "0.1.0",
        "essais": 1,
        "http_statut": 200,
        "sha256": "0" * 64,
        "empreinte_comparaison": "0" * 64,
        "taille_octets": 1,
        "chemin_archive": archive,
        "erreur": None,
    }


def _manifeste(chemins: Chemins, lignes: list[dict[str, Any]]) -> None:
    chemin = chemins.racine / "manifeste" / "collecte.jsonl"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as fichier:
        for ligne in lignes:
            fichier.write(json.dumps(ligne) + "\n")


def _passer(chemins: Chemins, *, orphelines: list[str] | None = None) -> int:
    return passage.derouler(
        horaire.GENRE,
        horaire.plan(chemins, "test"),
        chemins,
        ecrire=lambda _: None,
        controle=horaire.controle(chemins, "test"),
        circonscrit=horaire.circonscrit(chemins),
        complements=horaire.complements(chemins),
        conclure=horaire.conclure(chemins, "test", orphelines=lambda: orphelines),
    )


# --- le plan -----------------------------------------------------------------------------------


def test_le_plan_du_passage_horaire(chemins: Chemins) -> None:
    plan = horaire.plan(chemins)
    assert [e.nom for e in plan] == ETAPES
    index = plan[-1]
    assert index.arguments[:2] == ("index", "mettre-a-jour")  # jamais « construire »
    assert "--archive-has" in index.arguments and index.geste == horaire.GESTE_SANS_INDEX
    assert [e.services for e in plan] == [
        (),
        ("registre",),
        ("courtier", "registre"),
        ("courtier",),
        ("qdrant",),
    ]


def test_le_plan_des_verifications(chemins: Chemins) -> None:
    assert [e.nom for e in verification.plan(chemins)] == VERIFICATIONS


@pytest.mark.parametrize("module", [horaire, verification])
def test_chaque_etape_est_une_commande_qui_existe(chemins: Chemins, module: Any) -> None:
    for etape in module.plan(chemins):
        commande, reste = commande_cli(etape.arguments)
        assert not hasattr(commande, "commands"), etape
        commande.make_context(etape.nom, reste)


# --- le passage --------------------------------------------------------------------------------


def test_un_passage_a_vide_lance_les_cinq_etapes(chemins: Chemins, simulation: Simulation) -> None:
    """Sans archive nouvelle, chaque étape est lancée et ne fait rien : c'est la reprise, prouvée
    à chaque heure (addendum 1, C : pas de court-circuit)."""
    assert _passer(chemins, orphelines=[]) == 0
    assert simulation.lancees == ETAPES
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["genre"] == "passage" and consigne["issue"] == "complet"
    assert consigne["archives"] == [] and consigne["signalements"] == []
    assert consigne["declencheur"] is None  # lancé à la main
    assert consigne["collections_orphelines"] == []


def test_le_declencheur_vient_de_systemd(
    chemins: Chemins, simulation: Simulation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MONITOR_UNIT", "pharmaflux-collecte.service")
    monkeypatch.setenv("MONITOR_SERVICE_RESULT", "exit-code")
    monkeypatch.setenv("MONITOR_EXIT_STATUS", "1")
    _passer(chemins)
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["declencheur"] == {
        "unite": "pharmaflux-collecte.service",
        "resultat": "exit-code",
        "statut_sortie": "1",
    }
    assert simulation.lancees == ETAPES  # un code 1 de la collecte lance aussi la chaîne


def test_les_archives_nouvelles_depuis_le_passage_precedent(
    chemins: Chemins, simulation: Simulation
) -> None:
    """Le critère est ``chemin_archive`` non nul (§0 C) ; chaque passage ne liste que les lignes
    du manifeste écrites depuis le précédent."""
    _manifeste(
        chemins,
        [
            _ligne("20261115T001703Z", "2026-11-15T00:17:20+00:00", "bronze/a/1__x.txt.gz", "a"),
            _ligne("20261115T001703Z", "2026-11-15T00:17:25+00:00", None, "b"),
        ],
    )
    journal.ajouter(chemins.passages, {"genre": "remplissage", "debut": "2026-11-15T00:00:00Z"})
    _passer(chemins)
    _manifeste(
        chemins,
        [_ligne("20261115T011703Z", "2026-11-15T01:17:20+00:00", "bronze/b/2__y.txt.gz", "b")],
    )
    _passer(chemins)
    premier, second = list(journal.lire(chemins.passages))[1:]
    assert [a["chemin_archive"] for a in premier["archives"]] == ["bronze/a/1__x.txt.gz"]
    assert premier["archives"][0]["fin"] == "2026-11-15T00:17:20Z"
    assert premier["manifeste"] == {"lignes": 2}
    assert [a["chemin_archive"] for a in second["archives"]] == ["bronze/b/2__y.txt.gz"]
    assert second["manifeste"] == {"lignes": 3}
    assert simulation.lancees == ETAPES * 2


def test_publier_3_continue_quand_publication_json_le_prouve(
    chemins: Chemins, simulation: Simulation
) -> None:
    """La file des échecs a reçu des messages : le bus reste cohérent, le passage continue
    jusqu'à l'index et sort en 1 (addendum 1, question 7)."""
    chemins.evenements.mkdir(parents=True)
    (chemins.evenements / "publication.json").write_text(
        json.dumps(
            {
                "bdpm.cis": {
                    "evenements/bdpm.cis/a.jsonl": {"sha256": "x", "messages": 3, "echecs": 2}
                }
            }
        ),
        encoding="utf-8",
    )
    simulation.codes["publier"] = 3
    assert _passer(chemins) == 1
    assert simulation.lancees == ETAPES
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["issue"] == "complet" and consigne["arret"] is None
    assert consigne["signalements"] == [
        {
            "etape": "publier",
            "motif": "2 message(s) dans la file des échecs, d'après publication.json",
        }
    ]


def test_publier_3_sans_preuve_arrete(chemins: Chemins, simulation: Simulation) -> None:
    simulation.codes["publier"] = 3  # aucun publication.json : le code seul ne suffit pas
    assert _passer(chemins) == 1
    assert simulation.lancees == ETAPES[:3]
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["arret"] == {"etape": "publier", "motif": "code 3"}


def test_evenements_1_arrete_le_passage(chemins: Chemins, simulation: Simulation) -> None:
    """Une archive illisible n'est écrite dans aucun fichier : le passage s'arrête (question 7)."""
    simulation.codes["evenements"] = 1
    assert _passer(chemins) == 1
    assert simulation.lancees == ["evenements"]


def test_sans_index_le_passage_refuse_et_nomme_le_remplissage(
    chemins: Chemins, simulation: Simulation
) -> None:
    simulation.codes["index"] = 2  # « mise à jour refusée : pas d'index », Qdrant répondant
    assert _passer(chemins) == 2
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["arret"]["geste"] == horaire.GESTE_SANS_INDEX
    assert "pharmaflux-remplissage.service" in consigne["arret"]["geste"]


def test_qdrant_injoignable_est_une_panne_pas_un_refus(
    chemins: Chemins, simulation: Simulation
) -> None:
    simulation.pannes["qdrant"] = "ConnectError"
    assert _passer(chemins) == 1
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["arret"] == {"etape": "index", "motif": "qdrant injoignable (ConnectError)"}
    assert "geste" not in consigne["arret"]


def test_la_reprise_apres_un_passage_coupe(chemins: Chemins, simulation: Simulation) -> None:
    """Un passage coupé au silver ; le suivant relance tout depuis evenements, chaque étape
    sautant ce qu'elle a déjà fait, et porte les archives du passage coupé."""
    _manifeste(
        chemins,
        [_ligne("20261115T001703Z", "2026-11-15T00:17:20+00:00", "bronze/a/1__x.txt.gz", "a")],
    )
    journal.ajouter(chemins.passages, {"genre": "remplissage", "debut": "2026-11-15T00:00:00Z"})
    simulation.codes["silver"] = 1
    assert _passer(chemins) == 1
    simulation.codes.clear()
    assert _passer(chemins) == 0
    assert simulation.lancees == ETAPES[:4] + ETAPES
    coupe, repris = list(journal.lire(chemins.passages))[1:]
    assert coupe["non_lancees"] == ["index"] and repris["issue"] == "complet"
    assert len(coupe["archives"]) == 1 and repris["archives"] == []  # la fraîcheur les rattache


def test_le_verrou_tenu_saute_le_passage_en_code_0(tmp_path: Path, simulation: Simulation) -> None:
    racine, derive = tmp_path / "archive", tmp_path / "derive"
    racine.mkdir()
    arguments = ["chaine", "passer", "--racine", str(racine), "--derive", str(derive)]
    with verrou(derive / "chaine" / "verrou"):
        resultat = lanceur.invoke(cli.application, arguments)
    assert resultat.exit_code == 0
    assert "passage sauté : une autre commande de la chaîne tourne" in texte_nu(resultat.output)
    assert simulation.lancees == [] and not (derive / "chaine" / "passages.jsonl").exists()


def test_chaine_passer(
    tmp_path: Path, simulation: Simulation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(horaire, "collections_orphelines", lambda: ["pharmaflux-f4-vieille"])
    racine, derive = tmp_path / "archive", tmp_path / "derive"
    racine.mkdir()
    resultat = lanceur.invoke(
        cli.application,
        ["chaine", "passer", "--racine", str(racine), "--derive", str(derive), "--modele", "test"],
    )
    assert resultat.exit_code == 0, resultat.output
    assert "passage : complet, 5 étape(s)" in resultat.output
    (consigne,) = journal.lire(derive / "chaine" / "passages.jsonl")
    assert consigne["collections_orphelines"] == ["pharmaflux-f4-vieille"]
    assert simulation.lancees == ETAPES


# --- le témoin des formats ---------------------------------------------------------------------


def test_le_premier_passage_complet_ecrit_le_temoin(
    chemins: Chemins, simulation: Simulation
) -> None:
    """Le dérivé du VPS a été bâti avant le témoin : le premier passage complet l'écrit."""
    assert simulation is not None
    _passer(chemins)
    temoin = formats.lire(chemins.formats)
    assert temoin is not None and temoin["par"] == "passage"
    assert temoin["formats"] == formats.attendus("test")
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["temoin_ecrit"] is True


def test_un_passage_arrete_n_ecrit_pas_le_temoin(chemins: Chemins, simulation: Simulation) -> None:
    simulation.codes["silver"] = 1
    _passer(chemins)
    assert formats.lire(chemins.formats) is None


def test_un_format_change_refuse_avant_toute_etape(
    chemins: Chemins, simulation: Simulation
) -> None:
    attendu = formats.attendus("test")
    formats.ecrire(chemins.formats, formats={**attendu, "index": 3}, commit="a" * 40, par="x")
    assert _passer(chemins) == 2
    assert simulation.lancees == []
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["arret"]["etape"] == "formats"
    assert "index 3 → 4" in consigne["arret"]["motif"]
    assert formats.REBATIR_INDEX in consigne["arret"]["motif"]
    assert consigne["non_lancees"] == ETAPES


def test_le_plus_grand_geste_l_emporte() -> None:
    attendu = formats.attendus("test")
    bati = {**attendu, "index": 3, "silver": 0}
    temoin = {"formats": bati}
    differents = formats.ecarts(temoin, attendu)
    assert differents == ["index", "silver"]
    assert formats.REBATIR_SILVER in formats.refus(differents, temoin, attendu)
    contrats = {**attendu, "contrats": {"bdpm.cis": "v0"}}
    assert formats.REBATIR_TOUT in formats.refus(["contrats"], {"formats": contrats}, attendu)


def test_seul_le_commit_change_le_passage_passe(chemins: Chemins, simulation: Simulation) -> None:
    formats.ecrire(chemins.formats, formats=formats.attendus("test"), commit="b" * 40, par="x")
    assert _passer(chemins) == 0
    assert simulation.lancees == ETAPES


def test_le_remplissage_rebatit_l_index_mais_pas_le_silver(
    chemins: Chemins, simulation: Simulation
) -> None:
    from pharmaflux.chaine import remplissage

    attendu = formats.attendus("test")
    formats.ecrire(chemins.formats, formats={**attendu, "modele": "autre"}, commit=None, par="x")
    remplir = remplissage.controle(chemins, "test")
    assert remplir() is None  # le modèle change : le remplissage reconstruit l'index
    formats.ecrire(chemins.formats, formats={**attendu, "silver": 0}, commit=None, par="x")
    refus = remplir()
    assert refus is not None and formats.REBATIR_SILVER in refus
    assert simulation.lancees == []


def test_le_numero_du_silver_suit_son_schema() -> None:
    """Le schéma des tables du silver a changé sans que FORMAT_SILVER change : incrémente-le,
    puis recopie l'empreinte (§0 G, question 18)."""
    from pharmaflux.contrats.chargeur import charger_tous
    from pharmaflux.silver.schema import schema_du_contrat

    texte = "\n".join(f"{i}\n{schema_du_contrat(c)}" for i, c in sorted(charger_tous().items()))
    assert hashlib.sha256(texte.encode()).hexdigest() == formats.EMPREINTE_SILVER, (
        f"schéma du silver changé : incrémente FORMAT_SILVER ({formats.FORMAT_SILVER})"
    )


def test_un_temoin_illisible_refuse(chemins: Chemins, simulation: Simulation) -> None:
    chemins.formats.parent.mkdir(parents=True)
    chemins.formats.write_text("[]", encoding="utf-8")
    assert _passer(chemins) == 2
    assert simulation.lancees == []


# --- les vérifications -------------------------------------------------------------------------


def test_les_verifications_vont_toutes_au_bout(chemins: Chemins, simulation: Simulation) -> None:
    simulation.codes["silver-verifier"] = 1
    code = passage.derouler(
        verification.GENRE,
        verification.plan(chemins, "test"),
        chemins,
        ecrire=lambda _: None,
        circonscrit=verification.circonscrit,
    )
    assert code == 1
    assert simulation.lancees == VERIFICATIONS
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["signalements"] == [
        {"etape": "silver-verifier", "motif": "silver-verifier : code 1"}
    ]


def test_une_verification_tuee_arrete(chemins: Chemins, simulation: Simulation) -> None:
    simulation.codes["silver-verifier"] = None  # tuée par un signal
    passage.derouler(
        verification.GENRE,
        verification.plan(chemins, "test"),
        chemins,
        ecrire=lambda _: None,
        circonscrit=verification.circonscrit,
    )
    assert simulation.lancees == VERIFICATIONS[:2]


def test_chaine_verifier_saute_si_le_verrou_est_tenu(
    tmp_path: Path, simulation: Simulation
) -> None:
    racine, derive = tmp_path / "archive", tmp_path / "derive"
    racine.mkdir()
    arguments = ["chaine", "verifier", "--racine", str(racine), "--derive", str(derive)]
    with verrou(derive / "chaine" / "verrou"):
        tenu = lanceur.invoke(cli.application, arguments)
    assert tenu.exit_code == 0 and "vérification sautée" in tenu.output
    libre = lanceur.invoke(cli.application, arguments)
    assert libre.exit_code == 0, libre.output
    assert simulation.lancees == VERIFICATIONS


# --- l'état ------------------------------------------------------------------------------------


def _passage_horaire(
    ident: str,
    debut: str,
    fin_index: str,
    archives: list[dict[str, Any]],
    *,
    issue: str = "complet",
) -> dict[str, Any]:
    return {
        "genre": "passage",
        "id": ident,
        "debut": debut,
        "fin": fin_index,
        "duree_s": 30.0,
        "issue": issue,
        "code": 0 if issue == "complet" else 1,
        "arret": None if issue == "complet" else {"etape": "silver", "motif": "code 1"},
        "signalements": [],
        "archives": archives,
        "etapes": [
            {"nom": "evenements", "duree_s": 5.0, "code": 0, "fin": debut},
            *(
                [{"nom": "index", "duree_s": 20.0, "code": 0, "fin": fin_index}]
                if issue == "complet"
                else []
            ),
        ],
        "collections_orphelines": [],
    }


def _bilan(chemins: Chemins, identifiant: str, nom: str, decision: str, nombre: int) -> None:
    chemin = chemins.evenements / "bilans" / identifiant / f"{nom}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps({"decision": decision, "ecart": {"evenements": {"modifiee": nombre}}}),
        encoding="utf-8",
    )


def _archive(identifiant: str, nom: str, fin: str) -> dict[str, Any]:
    return {
        "identifiant": identifiant,
        "passage_id": "x",
        "fin": fin,
        "chemin_archive": f"bronze/bdpm/{identifiant}/{nom}.txt.gz",
    }


def test_la_fraicheur_compte_les_passages_porteurs(chemins: Chemins) -> None:
    """L'archive d'un passage coupé est portée par le suivant ; une archive d'avant la mise en
    service est hors population ; une archive sans événement ou confirmée est nommée à part."""
    _bilan(chemins, "bdpm.cis", "1__a", "retenu", 3)
    _bilan(chemins, "bdpm.cis", "2__b", "retenu", 0)
    _bilan(chemins, "bdpm.smr", "3__c", "confirme", 4)
    _bilan(chemins, "bdpm.cis", "4__d", "retenu", 2)
    passages = [
        _passage_horaire(
            "p1",
            "2026-11-15T00:17:30Z",
            "2026-11-15T00:17:50Z",
            [_archive("bdpm.cis", "0__z", "2026-11-14T22:17:20Z")],  # avant la mise en service
        ),
        _passage_horaire(
            "p2",
            "2026-11-15T01:17:30Z",
            "",
            [_archive("bdpm.cis", "1__a", "2026-11-15T01:17:20Z")],
            issue="arrete",
        ),
        _passage_horaire(
            "p3",
            "2026-11-15T02:17:30Z",
            "2026-11-15T02:18:10Z",
            [
                _archive("bdpm.cis", "2__b", "2026-11-15T02:17:21Z"),
                _archive("bdpm.smr", "3__c", "2026-11-15T02:17:22Z"),
            ],
        ),
        _passage_horaire(
            "p4",
            "2026-11-15T03:17:30Z",
            "2026-11-15T03:18:00Z",
            [_archive("bdpm.cis", "4__d", "2026-11-15T03:17:20Z")],
        ),
    ]
    resultat = etat.fraicheur(chemins, passages)
    natures = {
        a["chemin_archive"].split("/")[-1]: (a["nature"], a["passage"])
        for a in resultat["archives"]
    }
    assert natures == {
        "1__a.txt.gz": ("porteuse", "p3"),  # portée par le passage complet suivant
        "2__b.txt.gz": ("sans_evenement", "p3"),
        "3__c.txt.gz": ("confirmee_apres_attente", "p3"),
        "4__d.txt.gz": ("porteuse", "p4"),
    }
    assert [p["passage"] for p in resultat["passages_porteurs"]] == ["p3", "p4"]
    assert resultat["resume"] == {
        "passages": 2,
        "median_s": (3650.0 + 40.0) / 2,
        "maximum_s": 3650.0,
        "p95_s": None,  # moins de vingt valeurs
    }


def test_l_etat_lit_le_journal_le_manifeste_et_le_temoin(chemins: Chemins) -> None:
    _manifeste(
        chemins,
        [
            _ligne("20261115T011703Z", "2026-11-15T01:17:20+00:00", None, "a"),
            _ligne("20261115T021703Z", "2026-11-15T02:17:20+00:00", None, "a"),
        ],
    )
    journal.ajouter(
        chemins.passages,
        _passage_horaire("p1", "2026-11-15T01:17:30Z", "2026-11-15T01:17:50Z", []),
    )
    contenu = etat.lire(chemins, "test", datetime(2026, 11, 15, 2, 20, tzinfo=UTC))
    assert contenu["verdict"] == "en retard de 1 passage(s) de collecte"
    assert contenu["collecte"] == {
        "dernier_passage": "20261115T021703Z",
        "non_traites": ["20261115T021703Z"],
    }
    assert contenu["age_dernier_complet_min"] == 62
    assert contenu["temoin"] is None and contenu["derniere_erreur"] is None
    assert contenu["disque"]["libre_octets"] > 0
    lignes = etat.en_texte(contenu)
    assert lignes[0].startswith("chaîne : en retard de 1 passage(s) de collecte ; code ")
    assert any(ligne.startswith("formats              pas de témoin") for ligne in lignes)


def test_l_etat_d_une_chaine_en_panne(chemins: Chemins) -> None:
    journal.ajouter(
        chemins.passages,
        _passage_horaire("p1", "2026-11-15T01:17:30Z", "", [], issue="arrete"),
    )
    contenu = etat.lire(chemins, "test", datetime(2026, 11, 15, 2, 20, tzinfo=UTC))
    assert contenu["verdict"] == "en panne (code 1, étape silver)"
    assert contenu["derniere_erreur"]["id"] == "p1"
    assert contenu["age_dernier_complet_min"] is None


def test_chaine_etat_sans_option_lit_les_deux_variables(
    chemins: Chemins, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L'IeC la lance sans option, ses chemins en deux variables (addendum 1, question 20)."""
    monkeypatch.setenv("PHARMAFLUX_DATA", str(chemins.racine))
    monkeypatch.setenv("PHARMAFLUX_DERIVE", str(chemins.derive))
    texte = lanceur.invoke(cli.application, ["chaine", "etat"])
    assert texte.exit_code == 0, texte.output
    assert texte.output.startswith("chaîne : jamais lancée")
    en_json = lanceur.invoke(cli.application, ["chaine", "etat", "--format", "json"])
    assert en_json.exit_code == 0
    assert json.loads(en_json.output)["verdict"] == "jamais lancée"
    assert not chemins.passages.exists()  # rien d'écrit


def test_l_etat_ne_lance_rien(chemins: Chemins, monkeypatch: pytest.MonkeyPatch) -> None:
    def interdit(*_: object, **__: object) -> Resultat:
        raise AssertionError("chaine etat a lancé une étape")

    monkeypatch.setattr(etapes, "lancer", interdit)
    etat.lire(chemins, "test", datetime.now(UTC))


def test_une_verification_tuee_au_plafond_n_est_pas_circonscrite(
    chemins: Chemins, simulation: Simulation, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le compteur du noyau l'emporte : une vérification dont un processus est tué au plafond
    arrête le passage, même si elle rend un simple code 1."""
    groupe = tmp_path / "groupe"
    groupe.mkdir()
    monkeypatch.setattr(etapes, "_groupe", lambda: groupe)
    evenements = groupe / "memory.events"
    evenements.write_text("oom_kill 0\n", encoding="ascii")
    simulation.codes["silver-verifier"] = 1
    vrai = simulation._lancer

    def lancer(etape: etapes.Etape, **options: object) -> Resultat:
        if etape.nom == "silver-verifier":
            evenements.write_text("oom_kill 1\n", encoding="ascii")
        return vrai(etape, **options)  # type: ignore[arg-type]

    monkeypatch.setattr(etapes, "lancer", lancer)
    code = passage.derouler(
        verification.GENRE,
        verification.plan(chemins, "test"),
        chemins,
        ecrire=lambda _: None,
        circonscrit=verification.circonscrit,
    )
    assert code == 1 and simulation.lancees == VERIFICATIONS[:2]
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["arret"]["motif"] == "code 1, un processus tué par le plafond de mémoire"
    assert consigne["signalements"] == []


# --- l'état : ce que la première ligne doit dire (contrôle du palier 2, retouche 1) ------------


def _verification(
    fin: str, code: int = 0, signalements: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    return {
        "genre": "verification",
        "id": fin,
        "debut": fin,
        "fin": fin,
        "duree_s": 240.0,
        "issue": "complet",
        "code": code,
        "arret": None,
        "signalements": signalements or [],
        "etapes": [],
    }


MAINTENANT = datetime(2026, 11, 17, 4, 0, tzinfo=UTC)


def _etat_avec(chemins: Chemins, *passages: dict[str, Any]) -> dict[str, Any]:
    for passage_ in passages:
        journal.ajouter(chemins.passages, passage_)
    return etat.lire(chemins, "test", MAINTENANT)


def test_une_verification_recente_et_conforme_laisse_le_verdict(chemins: Chemins) -> None:
    contenu = _etat_avec(
        chemins,
        _passage_horaire("p0", "2026-11-15T03:17:30Z", "2026-11-15T03:17:50Z", []),
        _verification("2026-11-17T03:44:00Z"),
        _passage_horaire("p1", "2026-11-17T03:17:30Z", "2026-11-17T03:17:50Z", []),
    )
    assert contenu["verdict"] == "à jour"
    assert contenu["age_verification_h"] == 0.3
    ligne = next(x for x in etat.en_texte(contenu) if x.startswith("vérification"))
    assert ligne.endswith(", il y a 0.3 h")


def test_une_verification_en_echec_entre_dans_le_verdict(chemins: Chemins) -> None:
    contenu = _etat_avec(
        chemins,
        _verification(
            "2026-11-17T03:44:00Z",
            code=1,
            signalements=[{"etape": "index-verifier", "motif": "index-verifier : code 1"}],
        ),
        _passage_horaire("p1", "2026-11-17T03:17:30Z", "2026-11-17T03:17:50Z", []),
    )
    assert contenu["verdict"] == "à jour ; vérification en échec (code 1, étape index-verifier)"
    assert etat.en_texte(contenu)[0].startswith(
        "chaîne : à jour ; vérification en échec (code 1, étape index-verifier) ; code "
    )


def test_une_verification_de_plus_de_26_heures_entre_dans_le_verdict(chemins: Chemins) -> None:
    contenu = _etat_avec(
        chemins,
        _verification("2026-11-16T01:00:00Z"),
        _passage_horaire("p1", "2026-11-17T03:17:30Z", "2026-11-17T03:17:50Z", []),
    )
    assert contenu["verdict"] == "à jour ; dernière vérification il y a 27.0 h"


def test_aucune_verification_apres_26_heures_de_service(chemins: Chemins) -> None:
    contenu = _etat_avec(
        chemins,
        _passage_horaire("p0", "2026-11-16T01:17:30Z", "2026-11-16T01:17:50Z", []),
        _passage_horaire("p1", "2026-11-17T03:17:30Z", "2026-11-17T03:17:50Z", []),
    )
    assert contenu["verdict"] == (
        "à jour ; aucune vérification depuis la mise en service, il y a 26.7 h"
    )


def test_aucune_verification_avant_26_heures_ne_dit_rien(chemins: Chemins) -> None:
    contenu = _etat_avec(
        chemins, _passage_horaire("p1", "2026-11-17T03:17:30Z", "2026-11-17T03:17:50Z", [])
    )
    assert contenu["verdict"] == "à jour" and contenu["age_verification_h"] is None


def test_un_echec_circonscrit_est_nomme_avec_son_etape(chemins: Chemins) -> None:
    circonscrit = _passage_horaire("p1", "2026-11-17T03:17:30Z", "2026-11-17T03:17:50Z", [])
    circonscrit["code"] = 1
    circonscrit["signalements"] = [
        {"etape": "publier", "motif": "2 message(s) dans la file des échecs"}
    ]
    contenu = _etat_avec(chemins, circonscrit)
    assert contenu["verdict"] == (
        "échec circonscrit au dernier passage (publier : 2 message(s) dans la file des échecs)"
    )
    assert "en panne" not in contenu["verdict"]
