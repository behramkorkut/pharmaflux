"""La collecte des pages d'avis de la HAS (mission 09, palier 1), sans réseau.

Le périmètre se calcule sur les vraies archives de la BDPM du jeu de démo (les mêmes que sur
le Mac, ``points-a-trancher.md``, B). Le site est simulé par ``httpx.MockTransport`` avec les
réponses du §0 (``tests/fixtures/has/``) ; la page des mentions légales n'ayant pas été
demandée au §0, une page d'avis du même gabarit en tient lieu. Le client ne dort jamais : les
pauses qu'il demande sont relevées.
"""

from __future__ import annotations

import ast
import gzip
import json
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.cli import application
from pharmaflux.has import collecte, extraction, inspection
from pharmaflux.has import manifeste as mf
from pharmaflux.has.client import ArretNet, ClientHas, PlafondAtteint
from pharmaflux.has.collecte import URL_MENTIONS, URL_ROBOTS
from pharmaflux.has.perimetre import PerimetreIllisible, calculer
from tests.conftest import EN_TETES_IGNORES, FIXTURES, ServeurSimule, texte_nu

JEU = Path(__file__).resolve().parent.parent / "demo" / "archive"
PAGES = FIXTURES / "has"
SITE = "https://www.has-sante.fr/jcms/"
# Cinq pages de quatre dossiers, dans l'ordre de collecte : date d'avis décroissante, puis
# dossier, puis URL (les deux pages de CT-20568 ont la même date et le même dossier).
DOSSIERS = ["CT-21681", "CT-21088", "CT-21030", "CT-20568"]
ORDRE = ["p_4072400", "p_3590639", "p_3577036", "p_3500927", "p_3741668"]
lanceur = CliRunner()


def en_tetes(fichier: str) -> dict[str, str]:
    lignes = (PAGES / f"{fichier}.headers").read_text(encoding="utf-8").splitlines()[1:]
    valeurs = {}
    for ligne in lignes:
        nom, _, valeur = ligne.partition(":")
        if nom.strip().lower() not in EN_TETES_IGNORES | {"set-cookie"}:
            valeurs[nom.strip()] = valeur.strip()
    return valeurs


def reponse(fichier: str) -> tuple[int, bytes, dict[str, str]]:
    return 200, (PAGES / fichier).read_bytes(), en_tetes(fichier)


@pytest.fixture
def site() -> ServeurSimule:
    serveur = ServeurSimule()
    serveur.scenariser(URL_ROBOTS, reponse("robots.txt"))
    serveur.scenariser(URL_MENTIONS, reponse("p_3741668.html"))
    for page in [*ORDRE, "c_2027377"]:
        serveur.scenariser(SITE + page, reponse(f"{page}.html"))
    return serveur


@pytest.fixture
def racine(tmp_path: Path) -> Path:
    """Une archive qui ne porte que les trois fichiers de la BDPM qu'il faut au périmètre."""
    racine = tmp_path / "archive"
    for fichier in ("HAS_LiensPageCT_bdpm.txt", "CIS_HAS_SMR_bdpm.txt", "CIS_HAS_ASMR_bdpm.txt"):
        shutil.copytree(JEU / "bronze" / "bdpm" / fichier, racine / "bronze" / "bdpm" / fichier)
    return racine


class Pauses(list[float]):
    def __call__(self, secondes: float) -> None:
        self.append(secondes)


def passage(
    racine: Path,
    site: ServeurSimule,
    *,
    plafond: int = 50,
    dossiers: list[str] | None = None,
    reessayer_erreurs: bool = False,
    pauses: Pauses | None = None,
) -> collecte.Bilan:
    perimetre = calculer(racine, dossiers=dossiers or DOSSIERS)
    plan = collecte.planifier(racine, perimetre, reessayer_erreurs=reessayer_erreurs)
    with ClientHas(
        plafond=plafond,
        transport=site.transport(),
        dormir=pauses if pauses is not None else Pauses(),
    ) as client:
        return collecte.executer(racine, plan, client)


def demandees(site: ServeurSimule) -> list[str]:
    return [str(requete.url).removeprefix(SITE) for requete in site.requetes]


# --- le périmètre ------------------------------------------------------------------------------


def test_perimetre_de_la_premiere_etape_sur_le_jeu() -> None:
    perimetre = calculer(JEU)
    assert perimetre.dossiers == 746
    assert perimetre.dossiers_avec_lien == 720
    assert len(perimetre.dossiers_sans_lien) == 26
    assert "CT-21716" in perimetre.dossiers_sans_lien  # OZEMPIC, avis_has-003
    assert len(perimetre.pages) == 722
    assert {page.page_id[:2] for page in perimetre.pages} == {"p_"}
    assert perimetre.liens_hors_forme == ()
    dates = [page.date_avis for page in perimetre.pages]
    assert dates == sorted(dates, reverse=True)
    assert [source.sha256[:12] for source in perimetre.sources] == [
        "2f01ff1e13f8",
        "c2215af6b207",
        "f849554030c7",
    ]
    adempas = [page for page in perimetre.pages if page.dossiers == ("CT-20568",)]
    assert [page.page_id for page in adempas] == ["p_3500927", "p_3741668"]


def test_perimetre_restreint(racine: Path) -> None:
    assert [p.page_id for p in calculer(racine, dossiers=DOSSIERS).pages] == ORDRE
    assert calculer(racine, dossiers=["CT-14040"]).pages == ()  # un avis de 2015
    ancien = calculer(racine, depuis=date(2015, 1, 1), dossiers=["CT-14040"])
    assert [p.page_id for p in ancien.pages] == ["c_2027377"]


def test_perimetre_sans_archive(tmp_path: Path) -> None:
    with pytest.raises(PerimetreIllisible, match=r"HAS_LiensPageCT_bdpm\.txt"):
        calculer(tmp_path)


# --- un passage --------------------------------------------------------------------------------


def test_un_passage_complet(racine: Path, site: ServeurSimule) -> None:
    pauses = Pauses()
    bilan = passage(racine, site, pauses=pauses)
    assert bilan.code_sortie == 0, bilan.resume()
    assert demandees(site) == [URL_ROBOTS, URL_MENTIONS.removeprefix(SITE), *ORDRE]
    # En série, deux secondes au moins entre deux requêtes : sept requêtes, six pauses.
    assert len(pauses) == 6
    assert all(1.9 < pause <= 2.0 for pause in pauses)
    assert all(requete.headers["user-agent"].startswith("pharmaflux/") for requete in site.requetes)
    assert (bilan.requetes, bilan.archivees, bilan.erreurs, bilan.restantes) == (7, 5, [], 0)
    assert "pas encore de référence" in bilan.mentions

    lignes = mf.lire(racine)
    assert [ligne.role for ligne in lignes] == ["robots", "mentions", *["page"] * 5]
    for ligne, page_id in zip(lignes[2:], ORDRE, strict=True):
        assert ligne.statut == "nouveau"
        assert ligne.page_id == page_id
        assert ligne.archive is not None
        assert ligne.archive.startswith(f"bronze/has/pages/{page_id}/")
        octets = gzip.decompress((racine / ligne.archive).read_bytes())
        assert octets == (PAGES / f"{page_id}.html").read_bytes()  # à l'octet
        assert ligne.empreinte_texte == extraction.extraire(octets).empreinte()
        assert ligne.extracteur == extraction.VERSION_EXTRACTEUR
        assert ligne.rejet is None
        assert ligne.user_agent is not None
        assert ligne.user_agent.startswith("pharmaflux/")
    assert lignes[-1].dossiers == ["CT-20568"]
    assert lignes[-1].date_avis_bdpm == "20240228"


def test_une_relance_ne_redemande_aucune_page(racine: Path, site: ServeurSimule) -> None:
    passage(racine, site)
    site.requetes.clear()
    bilan = passage(racine, site)
    assert demandees(site) == [URL_ROBOTS, URL_MENTIONS.removeprefix(SITE)]
    assert bilan.code_sortie == 0
    assert bilan.a_demander == 0
    assert "inchangé" in bilan.robots
    assert "texte inchangé" in bilan.mentions and not bilan.mentions_a_relire
    roles = [(ligne.role, ligne.statut) for ligne in mf.lire(racine)[7:]]
    assert roles == [("robots", "inchange"), ("mentions", "inchange")]


def test_des_mentions_legales_changees_se_signalent_en_tete(
    racine: Path, site: ServeurSimule
) -> None:
    passage(racine, site)
    autre = (
        (PAGES / "p_3741668.html")
        .read_bytes()
        .replace("non sollicitée".encode(), "non sollicitée (texte revu)".encode())
    )
    site.scenariser(URL_MENTIONS, (200, autre, en_tetes("p_3741668.html")))
    bilan = passage(racine, site)
    assert bilan.mentions_a_relire
    assert bilan.resume().splitlines()[0].startswith("ATTENTION — mentions légales : TEXTE CHANGÉ")
    assert bilan.code_sortie == 0  # la collecte n'est pas arrêtée


def test_le_plafond_arrete_net_puis_la_relance_reprend(racine: Path, site: ServeurSimule) -> None:
    bilan = passage(racine, site, plafond=4)
    assert bilan.code_sortie == 3
    assert "plafond de 4" in str(bilan.arret)
    assert demandees(site)[2:] == ORDRE[:2]
    assert bilan.restantes == 3
    site.requetes.clear()
    bilan = passage(racine, site)
    assert bilan.code_sortie == 0
    assert demandees(site)[2:] == ORDRE[2:]


def test_un_429_arrete_tout(racine: Path, site: ServeurSimule) -> None:
    site.scenariser(SITE + ORDRE[1], (429, b"trop", {"Retry-After": "120"}))
    bilan = passage(racine, site)
    assert bilan.code_sortie == 3
    assert "429" in str(bilan.arret) and "120" in str(bilan.arret)
    assert demandees(site)[2:] == ORDRE[:2]  # rien après le 429, pas de réessai
    derniere = mf.lire(racine)[-1]
    assert (derniere.page_id, derniere.statut, derniere.http_statut) == (
        ORDRE[1],
        "erreur_http",
        429,
    )


def test_un_5xx_isole_se_reessaie_une_fois(racine: Path, site: ServeurSimule) -> None:
    pauses = Pauses()
    site.scenariser(SITE + ORDRE[0], (503, b"", {}), reponse(f"{ORDRE[0]}.html"))
    bilan = passage(racine, site, pauses=pauses)
    assert bilan.code_sortie == 0
    assert demandees(site)[2:4] == [ORDRE[0], ORDRE[0]]
    assert any(9.9 < pause <= 10.0 for pause in pauses)  # le réessai attend dix secondes
    assert mf.lire(racine)[2].essais == 2


def test_un_5xx_repete_arrete_tout(racine: Path, site: ServeurSimule) -> None:
    site.scenariser(SITE + ORDRE[0], (502, b"", {}))
    bilan = passage(racine, site)
    assert bilan.code_sortie == 3
    assert "deux fois d'affilée" in str(bilan.arret)
    assert demandees(site)[2:] == [ORDRE[0], ORDRE[0]]


def test_une_erreur_reseau_puis_la_reponse(racine: Path, site: ServeurSimule) -> None:
    site.scenariser(SITE + ORDRE[2], httpx.ConnectError("coupure"), reponse(f"{ORDRE[2]}.html"))
    assert passage(racine, site).code_sortie == 0


def test_une_redirection_n_est_pas_suivie(racine: Path, site: ServeurSimule) -> None:
    ailleurs = "https://www.has-sante.fr/jcms/p_1/fr/ailleurs"
    site.scenariser(SITE + ORDRE[1], (302, b"", {"Location": ailleurs}))
    bilan = passage(racine, site)
    assert bilan.code_sortie == 1
    assert ailleurs not in [str(requete.url) for requete in site.requetes]
    ligne = next(ligne for ligne in mf.lire(racine) if ligne.page_id == ORDRE[1])
    assert (ligne.statut, ligne.location, ligne.archive) == ("redirection", ailleurs, None)
    assert "non suivie" in bilan.resume()
    # Une page en erreur ne se redemande que sur demande.
    site.requetes.clear()
    passage(racine, site)
    assert ORDRE[1] not in demandees(site)
    site.scenariser(SITE + ORDRE[1], reponse(f"{ORDRE[1]}.html"))
    site.requetes.clear()
    assert passage(racine, site, reessayer_erreurs=True).code_sortie == 0
    assert demandees(site)[2:] == [ORDRE[1]]


@pytest.mark.parametrize(
    ("reponse_", "statut"),
    [
        ((404, b"absent", {"Content-Type": "text/html"}), "erreur_http"),
        ((200, b"", {"Content-Type": "text/html"}), "vide"),
        ((200, b"%PDF-1.7", {"Content-Type": "application/pdf"}), "type_inattendu"),
    ],
)
def test_les_erreurs_visibles(
    racine: Path, site: ServeurSimule, reponse_: tuple[int, bytes, dict[str, str]], statut: str
) -> None:
    site.scenariser(SITE + ORDRE[3], reponse_)
    bilan = passage(racine, site)
    assert bilan.code_sortie == 1
    assert bilan.archivees == 4
    ligne = next(ligne for ligne in mf.lire(racine) if ligne.page_id == ORDRE[3])
    assert (ligne.statut, ligne.archive) == (statut, None)
    assert ligne.sha256 is not None and ligne.taille == len(reponse_[1])


def test_une_page_rejetee_est_archivee_et_comptee(racine: Path, site: ServeurSimule) -> None:
    site.scenariser(SITE + ORDRE[4], reponse("doc1-saut3-doXiti.html"))
    bilan = passage(racine, site)
    assert bilan.code_sortie == 0
    assert bilan.rejets == {"jsonld_absent": 1}
    ligne = mf.lire(racine)[-1]
    assert (ligne.statut, ligne.rejet, ligne.empreinte_texte) == ("nouveau", "jsonld_absent", None)


def test_robots_txt_decide(racine: Path, site: ServeurSimule) -> None:
    interdit = b"User-agent: *\nDisallow: /jcms/p_3577036\n"
    site.scenariser(URL_ROBOTS, (200, interdit, {"Content-Type": "text/plain"}))
    bilan = passage(racine, site)
    assert "p_3577036" not in demandees(site)
    assert bilan.interdites == [SITE + "p_3577036"]
    statuts = {ligne.page_id: ligne.statut for ligne in mf.lire(racine) if ligne.page_id}
    assert statuts["p_3577036"] == "interdit_robots"


def test_robots_txt_illisible_refuse_tout(racine: Path, site: ServeurSimule) -> None:
    site.scenariser(URL_ROBOTS, (404, b"", {"Content-Type": "text/html"}))
    bilan = passage(racine, site)
    assert bilan.code_sortie == 2
    assert demandees(site) == [URL_ROBOTS]


def test_une_archive_orpheline_est_reprise_sans_requete(racine: Path, site: ServeurSimule) -> None:
    """Une coupure entre l'écriture de l'archive et sa ligne de manifeste."""
    passage(racine, site, plafond=3)  # robots.txt, mentions, ORDRE[0]
    orpheline = racine / "bronze/has/pages" / ORDRE[1] / "20261101T100000Z__7e295c47fd2c.html.gz"
    orpheline.parent.mkdir(parents=True)
    orpheline.write_bytes(gzip.compress((PAGES / f"{ORDRE[1]}.html").read_bytes()))
    assert collecte.planifier(racine, calculer(racine, dossiers=DOSSIERS)).etat.orphelines == (
        orpheline,
    )
    site.requetes.clear()
    bilan = passage(racine, site)
    assert bilan.reprises == 1
    assert ORDRE[1] not in demandees(site)
    reprise = next(ligne for ligne in mf.lire(racine) if ligne.statut == "repris")
    assert reprise.page_id == ORDRE[1]
    assert reprise.empreinte_texte is not None


def test_le_client_tient_pause_et_plafond() -> None:
    with pytest.raises(ValueError, match=r"2\.0 s au moins"):
        ClientHas(plafond=10, pause=1.5)
    serveur = ServeurSimule()
    serveur.scenariser(URL_ROBOTS, reponse("robots.txt"))
    with ClientHas(plafond=1, transport=serveur.transport(), dormir=Pauses()) as client:
        client.demander(URL_ROBOTS)
        with pytest.raises(PlafondAtteint):
            client.demander(URL_ROBOTS)
    assert len(serveur.requetes) == 1
    serveur.scenariser(URL_ROBOTS, (301, b"", {"Location": "https://ailleurs.invalid/"}))
    with ClientHas(plafond=3, transport=serveur.transport(), dormir=Pauses()) as client:
        assert client.demander(URL_ROBOTS).statut == 301
    serveur.scenariser(URL_ROBOTS, (500, b"", {}), (200, b"ok", {}), (500, b"", {}), (503, b"", {}))
    with ClientHas(plafond=9, transport=serveur.transport(), dormir=Pauses()) as client:
        assert client.demander(URL_ROBOTS).statut == 200  # 500 puis 200
        with pytest.raises(ArretNet):
            client.demander(URL_ROBOTS)  # 500 puis 503


# --- l'inspection et la ligne de commande ------------------------------------------------------


def test_extraire_les_pages_archivees(racine: Path, site: ServeurSimule, tmp_path: Path) -> None:
    passage(racine, site)
    pages = inspection.pages_archivees(racine)
    assert [page.page_id for page in pages] == sorted(ORDRE)
    sortie = tmp_path / "extraits.jsonl"
    with sortie.open("w", encoding="utf-8") as flux:
        bilan = inspection.extraire(pages, verifier=True, sortie=flux)
    assert (bilan.pages, bilan.extraites, bilan.ecarts, bilan.divergences) == (5, 5, [], [])
    assert bilan.code_sortie == 0
    assert (bilan.empreintes_egales, bilan.changements) == (5, [])
    # Le second lien d'ADEMPAS n'a pas de document : accepté, mais compté à part.
    assert bilan.sans_controle == ["p_3741668 (CT-20568)"]
    assert "contrôle de dossier impossible : 1" in bilan.resume()
    lignes = [json.loads(ligne) for ligne in sortie.read_text(encoding="utf-8").splitlines()]
    assert {ligne["page_id"]: ligne["date_avis"] for ligne in lignes}["p_3741668"] == "2025-11-10"
    assert {ligne["page_id"]: ligne["controle_dossier"] for ligne in lignes} == {
        "p_4072400": True,
        "p_3590639": True,
        "p_3577036": True,
        "p_3500927": True,
        "p_3741668": False,
    }


def reecrire_manifeste(racine: Path, retouches: dict[str, dict[str, object]]) -> None:
    """Le manifeste d'un passage retouché page par page : comme s'il venait d'une autre version."""
    lignes = mf.lire(racine)
    mf.chemin_manifeste(racine).unlink()
    for ligne in lignes:
        mf.ajouter(racine, replace(ligne, **retouches.get(ligne.page_id or "", {})))


def empreinte_v1(page_id: str) -> str:
    return extraction.extraire((PAGES / f"{page_id}.html").read_bytes()).empreinte(1)


def test_un_manifeste_de_la_v1_relu_en_v2(racine: Path, site: ServeurSimule) -> None:
    """Le passage de beko est en v1 : le texte se compare quand même, les statuts changés se
    listent à part (addendum de l'IeC du 31/10)."""
    passage(racine, site)
    retouches: dict[str, dict[str, object]] = {
        page_id: {"extracteur": 1, "empreinte_texte": empreinte_v1(page_id)} for page_id in ORDRE
    }
    retouches["p_3577036"] = {"extracteur": 1, "empreinte_texte": None, "rejet": "nom_incoherent"}
    reecrire_manifeste(racine, retouches)
    bilan = inspection.extraire(inspection.pages_archivees(racine), verifier=True)
    assert (bilan.extraites, bilan.ecarts, bilan.divergences) == (5, [], [])
    assert bilan.empreintes_egales == 4
    assert bilan.changements == ["p_3577036 : rejetée (nom_incoherent) en v1 → extraite en v2"]
    assert bilan.code_sortie == 0
    assert (
        "statut changé depuis la version du manifeste : 1"
        " (rejetée → extraite 1, extraite → rejetée 0)"
    ) in bilan.resume()


def test_un_texte_ou_un_statut_qui_change_sans_raison_diverge(
    racine: Path, site: ServeurSimule
) -> None:
    passage(racine, site)
    reecrire_manifeste(
        racine,
        {
            # v1, mais un autre texte que celui des octets archivés.
            "p_4072400": {"extracteur": 1, "empreinte_texte": "0" * 64},
            # Rejetée à la version courante, extraite aujourd'hui : l'extracteur n'est pas stable.
            "p_3590639": {"empreinte_texte": None, "rejet": "nom_incoherent"},
        },
    )
    bilan = inspection.extraire(inspection.pages_archivees(racine), verifier=True)
    assert sorted(bilan.divergences) == [
        "p_3590639 : rejetée (nom_incoherent) au manifeste, extraite à version égale",
        "p_4072400 : texte différent de celui du manifeste (v1)",
    ]
    assert bilan.changements == []
    assert bilan.code_sortie == 1


def test_cli_simuler_ne_fait_aucune_requete(racine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def interdit() -> httpx.BaseTransport:
        raise AssertionError("la simulation a construit un client")

    monkeypatch.setattr(cli, "fabriquer_transport_has", interdit)
    resultat = lanceur.invoke(
        application, ["has", "collecter", "--simuler", "--racine", str(racine)]
    )
    assert resultat.exit_code == 0, resultat.output
    sortie = texte_nu(resultat.output)
    assert "746, dont 720 avec un lien et 26 sans lien ; 722 page(s)" in sortie
    assert "requêtes : 724" in sortie and "plafond conseillé : 761" in sortie
    assert not (racine / "manifeste").exists()


def test_cli_plafond_obligatoire_et_pause_minimale(racine: Path) -> None:
    resultat = lanceur.invoke(application, ["has", "collecter", "--racine", str(racine)])
    assert resultat.exit_code == 2
    assert "--plafond est obligatoire" in texte_nu(resultat.output)
    resultat = lanceur.invoke(
        application, ["has", "collecter", "--plafond", "5", "--pause", "1", "--racine", str(racine)]
    )
    assert resultat.exit_code == 2


def test_cli_un_passage_puis_extraire(
    racine: Path, site: ServeurSimule, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "fabriquer_transport_has", site.transport)
    monkeypatch.setattr(cli, "dormir_has", Pauses())
    arguments = ["has", "collecter", "--plafond", "10", "--racine", str(racine)]
    for dossier in DOSSIERS:
        arguments += ["--dossier", dossier]
    resultat = lanceur.invoke(application, arguments)
    assert resultat.exit_code == 0, resultat.output
    assert "5 archivée(s)" in texte_nu(resultat.output)
    resultat = lanceur.invoke(
        application, ["has", "extraire", "--verifier", "--racine", str(racine)]
    )
    assert resultat.exit_code == 0, resultat.output
    assert "5 page(s) : 5 extraite(s), 0 rejetée(s)" in texte_nu(resultat.output)
    assert "5 conforme(s), 0 avec écart" in texte_nu(resultat.output)


def test_le_script_du_s0_n_est_importe_par_aucun_test() -> None:
    """``requetes_s0.py`` reste comme preuve, journal plein (addendum 1, E)."""
    journal = (PAGES / "journal-s0.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(journal) == 12
    assert all(
        json.loads(ligne)["url"].startswith("https://www.has-sante.fr/") for ligne in journal
    )
    for fichier in Path(__file__).parent.rglob("*.py"):
        if fichier.name == "requetes_s0.py":
            continue
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                modules = [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                modules = [noeud.module or ""]
            else:
                continue
            assert not any("requetes_s0" in m or m.startswith("tests.fixtures") for m in modules)
