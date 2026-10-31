"""Mission 09, palier 2 : la section avis_has de l'index et sa seconde horloge (addendum 1 F).

Sur les pages réelles des fixtures, contre le Qdrant simulé et l'encodeur de test : un fragment
par (page, CIS, partie), le texte de la page mot pour mot, aucune URL dans le texte ; la page
rattachée par les liens de la fiche, jamais l'inverse ; la position du manifeste HAS dans
l'état ; après une page arrivée, la mise à jour égale la reconstruction.
"""

from __future__ import annotations

import gzip
import hashlib
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.cli import application
from pharmaflux.has import extraction
from pharmaflux.has import manifeste as mf
from pharmaflux.index import construction, pages_has
from pharmaflux.index.construction import Fragments, IndexRefuse
from pharmaflux.index.fragments import (
    BORNE_CARACTERES,
    SECTIONS_INDEX,
    SOURCE_AVIS_HAS,
    Source,
    fragments,
    identifiant_avis_has,
)
from pharmaflux.index.pages_has import PageIndexee
from pharmaflux.index.qdrant import ALIAS, COLLECTION_ETAT
from tests.conftest import FIXTURES
from tests.qdrant_simule import QdrantSimule
from tests.test_fragments import fiche
from tests.test_index_maj import construire, contenu, mettre_a_jour, verifier

PAGES = FIXTURES / "has"
SITE = "https://www.has-sante.fr/jcms/"
COLLECTE = "2026-10-31T12:45:00Z"
AVANT, APRES = "2026-10-26T00:17:12Z", "2026-10-27T00:17:12Z"


def page_indexee(page_id: str, rang: int = 0, collectee: str = COLLECTE) -> PageIndexee:
    octets = (PAGES / f"{page_id}.html").read_bytes()
    return PageIndexee(
        url=SITE + page_id,
        page_id=page_id,
        archive=f"bronze/has/pages/{page_id}/20261031T124500Z__{page_id}.html.gz",
        sha256=hashlib.sha256(octets).hexdigest(),
        collectee_le=collectee,
        rang=rang,
        extrait=extraction.extraire(octets),
    )


def avis(dossier: str, date_avis: date, *pages: str) -> dict[str, Any]:
    return {
        "code_dossier_has": dossier,
        "motif_evaluation": "Inscription (CT)",
        "date_avis": date_avis,
        "valeur_smr": "Important",
        "libelle_smr": "Le service médical rendu est important.",
        "liens_avis": [SITE + p for p in pages] or None,
        "occurrences": 1,
    }


KALYDECO = fiche(
    code_cis="67851912",
    denomination="KALYDECO 13,4 mg, granulés en sachet",
    avis_smr=[avis("CT-21030", date(2024, 12, 18), "p_3577036")],
)


def avis_has(liste: list[Any]) -> list[Any]:
    return [f for f in liste if f.section == "avis_has"]


# --- les fragments ------------------------------------------------------------------------------


def test_un_fragment_par_page_cis_et_partie() -> None:
    pages = {SITE + "p_3577036": page_indexee("p_3577036")}
    liste = fragments(KALYDECO, pages)
    sections = list(dict.fromkeys(f.section for f in liste))
    assert sections == [s for s in SECTIONS_INDEX if s in sections]  # avis_has après avis
    morceaux = avis_has(liste)
    assert len(morceaux) > 1, "la page de KALYDECO fait plus de 1 200 caractères"
    for numero, morceau in enumerate(morceaux, start=1):
        lignes = morceau.texte.split("\n")
        assert lignes[0] == "CIS 67851912 — KALYDECO 13,4 mg, granulés en sachet"
        assert lignes[1] == (
            "Avis de la Commission de la transparence (HAS) « KALYDECO (ivacaftor) -"
            " Mucoviscidose », dossier CT-21030, du 2024-12-18 ; page mise en ligne le 2025-01-10"
        )
        mention = "(partie 1 sur" if numero == 1 else f"(suite, partie {numero} sur"
        assert lignes[2].startswith(mention)
        assert len(morceau.texte) <= BORNE_CARACTERES
        assert morceau.identifiant == identifiant_avis_has("67851912", "p_3577036", numero)
        assert "https://" not in morceau.texte and "has-sante.fr" not in morceau.texte
        assert morceau.liens == (SITE + "p_3577036",)
        assert morceau.sources == (Source(SOURCE_AVIS_HAS, "2024-12-18", COLLECTE),)
        assert morceau.page is not None
        assert (morceau.page["date_avis"], morceau.page["mis_en_ligne"]) == (
            "2024-12-18",
            "2025-01-10",
        )
        assert morceau.page["dossiers"] == ["CT-21030"]
        assert morceau.en_dict()["page"]["url"] == SITE + "p_3577036"


def test_le_texte_de_la_page_mot_pour_mot() -> None:
    page = page_indexee("p_3577036")
    assert page.extrait is not None
    repris = []
    for morceau in avis_has(fragments(KALYDECO, {page.url: page})):
        for ligne in morceau.texte.split("\n")[2:]:
            if ligne.startswith(("(partie ", "(suite, partie ")) or ligne.endswith(" (suite)"):
                continue
            repris.append(ligne)
    assert repris == page.extrait.lignes_rendues()[1:]  # le titre est dans l'en-tête


def test_sans_pages_aucun_fragment_avis_has() -> None:
    assert avis_has(fragments(KALYDECO)) == []
    assert avis_has(fragments(KALYDECO, {})) == []


def test_la_page_vient_des_liens_de_la_fiche() -> None:
    pages = {SITE + p: page_indexee(p) for p in ("p_3577036", "p_3608587", "p_3687274")}
    sans_lien = fiche(code_cis="60000001", avis_smr=[avis("CT-21030", date(2024, 12, 18))])
    assert avis_has(fragments(sans_lien, pages)) == []
    # PEDMARQSI : le document d'avis nomme CT-21123, pas le dossier de la fiche.
    pedmarqsi = fiche(
        code_cis="62372210", avis_smr=[avis("CT-21223", date(2025, 5, 28), "p_3608587")]
    )
    assert avis_has(fragments(pedmarqsi, pages)) == []
    # NIMENRIX : l'avis commun nomme son dossier, parmi cinq.
    nimenrix = fiche(
        code_cis="60000002", avis_smr=[avis("CT-21402", date(2025, 9, 10), "p_3687274")]
    )
    assert {f.page["page_id"] for f in avis_has(fragments(nimenrix, pages)) if f.page} == {
        "p_3687274"
    }
    # Une page rejetée pour sa structure ne donne rien.
    rejetee = PageIndexee(
        SITE + "p_3577036", "p_3577036", "a", "b", COLLECTE, 0, None, "corps_vide"
    )
    assert avis_has(fragments(KALYDECO, {SITE + "p_3577036": rejetee})) == []


def test_deux_pages_d_un_dossier_la_plus_recente_d_abord() -> None:
    adempas = fiche(
        code_cis="60000003",
        avis_smr=[avis("CT-20568", date(2024, 2, 28), "p_3500927", "p_3741668")],
    )
    pages = {SITE + p: page_indexee(p) for p in ("p_3500927", "p_3741668")}
    ordre = [f.page["page_id"] for f in avis_has(fragments(adempas, pages)) if f.page]
    assert ordre[0] == "p_3741668" and ordre[-1] == "p_3500927"  # 2025-11-10, puis 2024-02-28


# --- les pages lues depuis le manifeste ---------------------------------------------------------


def _archiver(racine: Path, page_id: str, debut: str) -> None:
    octets = (PAGES / f"{page_id}.html").read_bytes()
    sha256 = hashlib.sha256(octets).hexdigest()
    chemin = f"bronze/has/pages/{page_id}/20261031T120000Z__{sha256[:12]}.html.gz"
    (racine / chemin).parent.mkdir(parents=True, exist_ok=True)
    (racine / chemin).write_bytes(gzip.compress(octets, mtime=0))
    mf.ajouter(
        racine,
        mf.LigneHas(
            passage_id="20261031T120000Z",
            role=mf.Role.PAGE,
            url=SITE + page_id,
            statut=mf.Statut.NOUVEAU,
            version_collecteur="0.1.0+test",
            page_id=page_id,
            debut=debut,
            sha256=sha256,
            archive=chemin,
        ),
    )


DOSSIERS = {
    SITE + "p_3577036": {"CT-21030"},
    SITE + "p_3608587": {"CT-21223"},
    SITE + "p_3741668": {"CT-20568"},
    SITE + "p_4072400": {"CT-21681"},
}


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    racine = tmp_path / "archive"
    _archiver(racine, "p_3577036", "2026-10-31T12:00:01.500000+00:00")
    _archiver(racine, "p_3608587", "2026-10-31T12:00:04+00:00")
    _archiver(racine, "p_3741668", "2026-10-31T12:00:06+00:00")
    _archiver(racine, "p_3590639", "2026-10-31T12:00:08+00:00")  # qu'aucun lien ne désigne
    return racine


def test_les_pages_lues_a_une_position(archive: Path) -> None:
    lues = pages_has.lire(archive, DOSSIERS)
    assert sorted(lues.pages) == [SITE + p for p in ("p_3577036", "p_3608587", "p_3741668")]
    etat = lues.etat()
    assert (etat["position"], etat["archivees"], etat["rattachees"], etat["extraites"]) == (
        4,
        4,
        3,
        2,
    )
    assert etat["collecte"] == "2026-10-31T12:00:08Z"
    assert etat["rejets"] == {"dossier_incoherent": 1}
    assert etat["sans_controle"] == ["p_3741668"]
    assert etat["extracteur"] == extraction.VERSION_EXTRACTEUR
    deux = pages_has.lire(archive, DOSSIERS, lignes=2)
    assert sorted(deux.pages) == [SITE + "p_3577036", SITE + "p_3608587"]
    assert deux.collecte == "2026-10-31T12:00:04Z"


def test_un_prefixe_change_impose_la_reconstruction(archive: Path) -> None:
    connue = pages_has.position(archive)
    pages_has.exiger_prefixe(archive, connue)
    _archiver(archive, "p_4072400", "2026-11-01T09:00:00+00:00")  # le manifeste s'allonge : admis
    pages_has.exiger_prefixe(archive, connue)
    chemin = mf.chemin_manifeste(archive)
    chemin.write_bytes(chemin.read_bytes().replace(b"12:00:01.5", b"12:00:01.6", 1))
    with pytest.raises(pages_has.PositionRefusee, match="préfixe changé"):
        pages_has.exiger_prefixe(archive, connue)
    with pytest.raises(pages_has.PositionRefusee, match="n'en a plus que"):
        pages_has.position(archive, 99)


def test_une_archive_alteree_est_refusee(archive: Path) -> None:
    (ligne,) = [x for x in mf.lire(archive) if x.page_id == "p_3577036"]
    (archive / str(ligne.archive)).write_bytes(gzip.compress(b"autre chose"))
    with pytest.raises(pages_has.PositionRefusee, match="sha256"):
        pages_has.lire(archive, DOSSIERS)


# --- l'index : seconde horloge, incrément, vérification -----------------------------------------


FICHES = [
    KALYDECO,
    fiche(code_cis="60000003", avis_smr=[avis("CT-20568", date(2024, 2, 28), "p_3741668")]),
    fiche(code_cis="60000004", denomination="SANS AVIS TEST"),
]


def ecrire(
    tmp_path: Path,
    nom: str,
    pages: dict[str, PageIndexee],
    has: dict[str, Any],
    instant: str = APRES,
    touches: list[str] | None = None,
) -> Fragments:
    choisies = FICHES if touches is None else [f for f in FICHES if f["code_cis"] in touches]
    liste = [x for f in sorted(choisies, key=lambda f: f["code_cis"]) for x in fragments(f, pages)]
    chemin = tmp_path / f"{nom}.jsonl"
    chemin.write_text("".join(x.en_jsonl() + "\n" for x in liste), encoding="utf-8")
    return Fragments(
        chemin,
        instant,
        len(choisies),
        len(liste),
        len(FICHES),
        None if touches is None else tuple(sorted(touches)),
        has=has,
    )


def has(position: int) -> dict[str, Any]:
    return {"position": position, "empreinte": f"{position:064d}", "extracteur": 2}


def test_une_page_arrivee_puis_la_mise_a_jour_egale_la_reconstruction(tmp_path: Path) -> None:
    kalydeco = {SITE + "p_3577036": page_indexee("p_3577036")}
    toutes = kalydeco | {SITE + "p_3741668": page_indexee("p_3741668", rang=1)}
    simule = QdrantSimule()
    construire(simule, tmp_path / "travail", ecrire(tmp_path, "avant", kalydeco, has(1), AVANT))
    avant = {i for i, p in simule.points(ALIAS).items() if p["payload"]["section"] == "avis_has"}
    assert avant and all(
        simule.points(ALIAS)[i]["payload"]["code_cis"] == "67851912" for i in avant
    )
    # La page d'ADEMPAS arrive au manifeste : seul son CIS est touché.
    increment = ecrire(tmp_path, "increment", toutes, has(2), touches=["60000003"])
    bilan = mettre_a_jour(simule, tmp_path / "travail", increment)
    assert bilan.ajoutes >= 1 and bilan.retires == 0
    complets = ecrire(tmp_path, "complets", toutes, has(2))
    reference = QdrantSimule()
    construire(reference, tmp_path / "reference", complets)
    assert contenu(simule) == contenu(reference)
    rapport = verifier(simule, tmp_path / "travail", complets)
    assert rapport.conforme, construction.formater_verification(rapport)
    [etat] = [p["payload"] for p in simule.points(COLLECTION_ETAT).values()]
    assert etat["has"] == has(2)


def test_la_verification_exige_la_meme_position(tmp_path: Path) -> None:
    pages = {SITE + "p_3577036": page_indexee("p_3577036")}
    simule = QdrantSimule()
    construire(simule, tmp_path / "travail", ecrire(tmp_path, "un", pages, has(1)))
    with pytest.raises(IndexRefuse, match="pas celles que l'index a lues"):
        verifier(simule, tmp_path / "travail", ecrire(tmp_path, "deux", pages, has(2)))


def test_une_mise_a_jour_sans_les_pages_est_refusee(tmp_path: Path) -> None:
    pages = {SITE + "p_3577036": page_indexee("p_3577036")}
    simule = QdrantSimule()
    construire(simule, tmp_path / "travail", ecrire(tmp_path, "un", pages, has(1), AVANT))
    sans = ecrire(tmp_path, "sans", {}, has(1), touches=[])
    object.__setattr__(sans, "has", None)
    with pytest.raises(IndexRefuse, match="--archive-has"):
        mettre_a_jour(simule, tmp_path / "travail", sans)


def test_exiger_has(archive: Path) -> None:
    lue = pages_has.lire(archive, DOSSIERS).etat()
    etat = {"has": lue}
    construction.exiger_has(etat, archive)
    construction.exiger_has({"has": None}, None)
    with pytest.raises(IndexRefuse, match="--archive-has est attendu"):
        construction.exiger_has(etat, None)
    with pytest.raises(IndexRefuse, match="v1"):
        construction.exiger_has({"has": lue | {"extracteur": 1}}, archive)
    with pytest.raises(IndexRefuse, match="préfixe changé"):
        construction.exiger_has({"has": lue | {"empreinte": "0" * 64}}, archive)


def test_index_etat_rend_la_seconde_horloge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pages = {SITE + "p_3577036": page_indexee("p_3577036")}
    lue = has(1) | {
        "collecte": "2026-10-31T13:07:40Z",
        "archivees": 1,
        "rattachees": 1,
        "extraites": 1,
        "rejets": {},
        "sans_controle": [],
    }
    monkeypatch.setattr(cli, "fabriquer_transport_qdrant", lambda: avec.transport())
    avec = QdrantSimule()
    construire(avec, tmp_path / "avec", ecrire(tmp_path, "avec", pages, lue))
    resultat = CliRunner().invoke(application, ["index", "etat", "--complet"])
    assert resultat.exit_code == 0, resultat.output
    assert "collectées jusqu'au 2026-10-31T13:07:40Z" in resultat.output
    assert "avis_has" in resultat.output
    # Un index sans les pages d'avis : make index le reconstruit (code 2 avec --complet).
    avec = QdrantSimule()
    construire(avec, tmp_path / "sans", ecrire(tmp_path, "sans", {}, None))  # type: ignore[arg-type]
    resultat = CliRunner().invoke(application, ["index", "etat", "--complet"])
    assert resultat.exit_code == 2 and "sans les pages d'avis" in resultat.output
    assert "aucune (index construit sans --archive-has)" in resultat.output


# --- palier 4 : une page ne se rattache qu'aux fiches du référentiel --------------------------


def test_une_fiche_partielle_n_a_pas_de_fragment_d_avis() -> None:
    """La page est écartée tant que sa fiche est absente du référentiel, rattachée quand elle y
    entre : le rattachement se recalcule à chaque construction, sans nouvelle collecte."""
    pages = {SITE + "p_3577036": page_indexee("p_3577036")}
    partielle = KALYDECO | {"dans_referentiel": False, "denomination": None}
    assert avis_has(fragments(partielle, pages)) == []
    assert avis_has(fragments(KALYDECO, pages)) != []


def test_les_pages_sans_fiche_du_referentiel_sont_comptees(archive: Path) -> None:
    lues = pages_has.lire(archive, DOSSIERS)
    # Seule la page de KALYDECO est citée par une fiche du référentiel ; PEDMARQSI est rejetée.
    lues.marquer_sans_fiche({SITE + "p_3577036"})
    assert lues.etat()["sans_fiche"] == ["p_3741668"]
    assert lues.etat()["extraites"] == 2  # l'extraction ne change pas, seul le rattachement


def test_une_fiche_qui_entre_au_referentiel_retrouve_sa_page(tmp_path: Path) -> None:
    """La mise à jour par incréments : la fiche touchée (elle entre au référentiel) reçoit les
    fragments de sa page ; l'index égale sa reconstruction."""
    pages = {SITE + "p_3577036": page_indexee("p_3577036")}
    partielle = KALYDECO | {"dans_referentiel": False, "denomination": None}

    def fichier(
        nom: str, fiches: list[dict[str, Any]], instant: str, touches: Any = None
    ) -> Fragments:
        liste = [x for f in fiches for x in fragments(f, pages)]
        chemin = tmp_path / f"{nom}.jsonl"
        chemin.write_text("".join(x.en_jsonl() + "\n" for x in liste), encoding="utf-8")
        return Fragments(chemin, instant, len(fiches), len(liste), 1, touches, has=has(1))

    simule = QdrantSimule()
    construire(simule, tmp_path / "travail", fichier("avant", [partielle], AVANT))
    sections = {p["payload"]["section"] for p in simule.points(ALIAS).values()}
    assert "avis_has" not in sections
    mettre_a_jour(simule, tmp_path / "travail", fichier("maj", [KALYDECO], APRES, ("67851912",)))
    reference = QdrantSimule()
    complets = fichier("complets", [KALYDECO], APRES)
    construire(reference, tmp_path / "reference", complets)
    assert contenu(simule) == contenu(reference)
    assert "avis_has" in {p["payload"]["section"] for p in simule.points(ALIAS).values()}
    assert verifier(simule, tmp_path / "travail", complets).conforme
