"""Mission 02, décisions 7 et 8 : la chaîne, le rejeu, la reprise, sur un bronze de synthèse.

Le bronze est construit dans ``tmp_path`` à partir des archives fabriquées de
``tests/fixtures/evenements/`` (voir le README des fixtures), avec un manifeste
aux horodatages fixés : rien ne vient de l'horloge.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.collecte import manifeste
from pharmaflux.collecte.archive import chemin_archive, ecrire_archive
from pharmaflux.collecte.empreintes import empreinte_comparaison, sha256_hex
from pharmaflux.collecte.manifeste import Enregistrement
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evenements import rejeu, schema, snapshot
from pharmaflux.evenements.comparaison import appliquer, etat_du_snapshot
from pharmaflux.evenements.rejeu import ReprendreImpossible, executer, lire_evenements
from tests.conftest import FIXTURES, entree

T0 = datetime(2026, 10, 24, 14, 17, tzinfo=UTC)
PRESENTATIONS, DISPO = "bdpm.presentations", "bdpm.disponibilite"


@dataclass(frozen=True)
class Collecte:
    """Un passage de collecte simulé : une archive (``nom``), ou un passage inchangé (None)."""

    identifiant: str
    heures: float  # depuis T0
    nom: str | None  # fixture archivée, ou None pour un ``inchange`` de la dernière archive
    date_source: str | None = None

    @property
    def instant(self) -> datetime:
        return T0 + timedelta(hours=self.heures)


def _fixture(nom: str) -> bytes:
    """Une archive fabriquée (``evenements/``), un extrait des contrats, ou un chemin sous
    ``fixtures/`` (``bdpm/CIS_bdpm.txt``)."""
    for chemin in (FIXTURES / "evenements" / nom, FIXTURES / "contrats" / nom, FIXTURES / nom):
        if chemin.is_file():
            return chemin.read_bytes()
    raise FileNotFoundError(nom)


# Toutes entités confondues, dans l'ordre du temps. Présentations (clé) : A, B, vide, A, B
# (oscillation), bloquant, perte confirmée par l'archive suivante, retour, perte écartée
# par B, perte confirmée par un passage inchangé, retour, puis deux pertes en attente qui se
# suivent dans les deux sens (relecture 1) : la perte forte écartée par la perte, elle-même en
# attente, puis la perte confirmée par la perte forte, elle-même en attente à la fin du bronze.
# Disponibilité (ligne à ligne) : A (une ligne en double), B (en attente, écartée), la ligne en
# triple, ramenée à une (en attente, confirmée par un passage inchangé), remontée à trois, puis
# B en attente à la fin du bronze.
SUITE: tuple[Collecte, ...] = (
    Collecte(PRESENTATIONS, 0, "presentations_a.txt", "2026-10-24"),
    Collecte(DISPO, 0.1, "dispo_a.txt"),
    Collecte(PRESENTATIONS, 1, "presentations_b.txt", "2026-10-24"),
    Collecte(DISPO, 1.1, "dispo_b.txt"),
    Collecte(PRESENTATIONS, 2, "presentations_vide.txt"),
    Collecte(DISPO, 2.1, "dispo_triple.txt"),
    Collecte(PRESENTATIONS, 3, "presentations_a.txt", "2026-10-24"),
    Collecte(DISPO, 3.1, "dispo_simple.txt"),
    Collecte(DISPO, 3.6, None),  # inchangé : confirme la ligne en triple ramenée à une
    Collecte(PRESENTATIONS, 4, "presentations_b.txt", "2026-10-24"),
    Collecte(DISPO, 4.1, "dispo_triple.txt"),
    Collecte(PRESENTATIONS, 5, "presentations_anomalies.txt"),
    Collecte(DISPO, 5.1, "dispo_b.txt"),
    Collecte(PRESENTATIONS, 6, "presentations_perte.txt", "2026-10-24"),
    Collecte(PRESENTATIONS, 7, "presentations_perte.txt", "2026-10-24"),
    Collecte(PRESENTATIONS, 8, "presentations_a.txt", "2026-10-24"),
    Collecte(PRESENTATIONS, 9, "presentations_perte.txt", "2026-10-25"),
    Collecte(PRESENTATIONS, 10, "presentations_b.txt", "2026-10-25"),
    Collecte(PRESENTATIONS, 11, "presentations_perte.txt", "2026-10-25"),
    Collecte(PRESENTATIONS, 11.5, None),  # inchangé : confirme la perte de 11 h
    Collecte(PRESENTATIONS, 12, "presentations_a.txt", "2026-10-25"),
    Collecte(PRESENTATIONS, 13, "presentations_perte_forte.txt", "2026-10-25"),
    Collecte(PRESENTATIONS, 14, "presentations_perte.txt", "2026-10-25"),  # écarte 13 h, attend
    Collecte(PRESENTATIONS, 15, "presentations_perte_forte.txt", "2026-10-25"),  # confirme 14 h
)
ARCHIVES = [c for c in SUITE if c.nom is not None]


def peupler(racine: Path, suite: tuple[Collecte, ...] | list[Collecte]) -> None:
    """Archive chaque collecte et écrit sa ligne de manifeste, dans l'ordre."""
    dernieres: dict[str, tuple[str, str]] = {}  # identifiant → (empreinte, chemin relatif)
    sha256: str | None = None
    taille: int | None = None
    for ligne in manifeste.parcourir(racine):
        if ligne.identifiant and ligne.statut == "nouveau" and ligne.chemin_archive:
            dernieres[ligne.identifiant] = (ligne.empreinte_comparaison or "", ligne.chemin_archive)
    for collecte in suite:
        e = entree(collecte.identifiant)
        if collecte.nom is None:
            empreinte, chemin = dernieres[collecte.identifiant]
            statut = "inchange"
        else:
            contenu = _fixture(collecte.nom)
            empreinte = empreinte_comparaison(e.empreinte, contenu)
            sha256, taille = sha256_hex(contenu), len(contenu)
            absolu = chemin_archive(racine, e, collecte.instant, sha256)
            ecrire_archive(absolu, contenu, collecte.instant)
            chemin = absolu.relative_to(racine).as_posix()
            dernieres[collecte.identifiant] = (empreinte, chemin)
            statut = "nouveau"
        manifeste.ajouter(
            racine,
            Enregistrement(
                passage_id=collecte.instant.strftime("%Y%m%dT%H%M%SZ"),
                identifiant=e.identifiant,
                source=e.source,
                fichier=e.fichier,
                url=e.url,
                debut=collecte.instant.isoformat(),
                fin=(collecte.instant + timedelta(seconds=1)).isoformat(),
                statut=statut,
                version_collecteur="essai",
                sha256=sha256 if statut == "nouveau" else None,
                empreinte_comparaison=empreinte,
                taille_octets=taille if statut == "nouveau" else None,
                date_source_affichee=collecte.date_source,
                chemin_archive=chemin if statut == "nouveau" else None,
            ),
        )


def _arbre(sortie: Path) -> dict[str, bytes]:
    return {
        chemin.relative_to(sortie).as_posix(): chemin.read_bytes()
        for chemin in sorted(sortie.rglob("*"))
        if chemin.is_file()
    }


def _executer(racine: Path, sortie: Path, *, reprendre: bool = False) -> rejeu.Rapport:
    return executer(racine, sortie, charger_tous(), [PRESENTATIONS, DISPO], reprendre=reprendre)


@pytest.fixture
def bronze_complet(tmp_path: Path) -> Path:
    racine = tmp_path / "bronze-complet"
    peupler(racine, SUITE)
    return racine


@pytest.fixture
def reference(bronze_complet: Path, tmp_path: Path) -> dict[str, bytes]:
    sortie = tmp_path / "reference"
    rapport = _executer(bronze_complet, sortie)
    assert rapport.code_sortie == 0
    return _arbre(sortie)


def test_rejeu_complet_ce_qu_il_produit(bronze_complet: Path, tmp_path: Path) -> None:
    sortie = tmp_path / "sortie"
    rapport = _executer(bronze_complet, sortie)
    (pres, dispo) = rapport.resumes
    assert (pres.archives_lues, pres.retenues, pres.ecartees, pres.en_attente) == (16, 11, 4, 1)
    # Comparaisons : A initiale (c17) ; A→B (s1 m1 c1) ; B→A ; A→B ; B→perte confirmée par
    # l'archive suivante (s10 m1 c1) ; perte→perte (rien) ; perte→A (c9) ; la perte de 9 h est
    # écartée, A→B ; B→perte confirmée par le passage inchangé (s10 m1 c1) ; perte→A (c9) ; la
    # perte forte de 13 h est écartée par la perte de 14 h, elle-même en attente, que la perte
    # forte de 15 h confirme (A→perte : s9) ; celle de 15 h reste en attente.
    assert dict(pres.evenements) == {"creee": 41, "modifiee": 6, "supprimee": 33}
    # Disponibilité : B perd une ligne sur sept (14 %), le triple l'écarte (c1, rang 3) ; la ligne
    # ramenée à une est en attente, confirmée par le passage inchangé (s3, s2) ; remontée à trois
    # (c2, c3) ; B en attente à la fin du bronze.
    assert (dispo.archives_lues, dispo.retenues, dispo.ecartees, dispo.en_attente) == (6, 4, 1, 1)
    assert dict(dispo.evenements) == {"creee": 10, "supprimee": 2}
    arbre = _arbre(sortie)
    evenements = sorted(c for c in arbre if c.startswith("evenements/"))
    bilans = sorted(c for c in arbre if c.startswith("bilans/"))
    assert len(evenements) == 11 + 4 and len(bilans) == 16 + 6 and "etat.json" in arbre
    decisions = {
        c.removeprefix("bilans/bdpm.presentations/")[:16]: json.loads(arbre[c])["decision"]
        for c in bilans
        if "presentations" in c
    }
    attendues = [
        "retenu", "retenu", "ecarte", "retenu", "retenu", "ecarte",
        "confirme", "retenu", "retenu", "ecarte", "retenu", "confirme",
        "retenu", "ecarte", "confirme", "en_attente",
    ]  # fmt: skip
    assert [
        decisions[f"{(T0 + timedelta(hours=h)):%Y%m%dT%H%M%S}Z"] for h in range(16)
    ] == attendues, "le bilan d'une archive en attente est réécrit : confirmé ou écarté"
    etat = json.loads(arbre["etat.json"])
    assert etat["version"] == 1 and set(etat["entites"]) == {PRESENTATIONS, DISPO}
    dispo_etat = etat["entites"][DISPO]
    assert dispo_etat["en_attente"] is not None and "T192300Z__" in dispo_etat["en_attente"]
    assert dispo_etat["dernier_retenu"] == dispo_etat["derniere_archive_traitee"]
    assert "T182300Z__" in dispo_etat["dernier_retenu"], "l'état reste avant l'archive en attente"
    attente = next(c for c in bilans if "T192300Z" in c)
    assert json.loads(arbre[attente])["decision"] == "en_attente"
    pres_etat = etat["entites"][PRESENTATIONS]
    assert pres_etat["version_contrat"] == "v1" and "20261025T051700Z__" in pres_etat["en_attente"]
    assert pres_etat["dernier_retenu"] == pres_etat["derniere_archive_traitee"]
    assert pres_etat["dernier_retenu"].startswith(
        "bronze/bdpm/CIS_CIP_bdpm.txt/2026-10-25/20261025T041700Z__"
    ), "la dernière traitée est la perte confirmée par l'archive en attente, pas celle d'avant"
    assert arbre[next(c for c in evenements if "20261025T041700Z" in c)].count(b"supprimee") == 9
    vide = next(c for c in bilans if "20261024T161700Z" in c)
    assert json.loads(arbre[vide])["motif"] == "vide : aucune ligne bien formée"
    assert not any("20261024T161700Z" in c for c in evenements), "écarté : pas d'événements"
    confirmee = next(c for c in evenements if "20261024T201700Z" in c)
    assert arbre[confirmee].count(b'"type":"supprimee"') == 10, "confirmée par l'archive suivante"
    assert arbre[next(c for c in evenements if "20261024T211700Z" in c)] == b"", "identique : vide"


def test_deux_rejeux_complets_identiques_a_l_octet(
    bronze_complet: Path, tmp_path: Path, reference: dict[str, bytes]
) -> None:
    sortie = tmp_path / "second"
    _executer(bronze_complet, sortie)
    assert _arbre(sortie) == reference
    _executer(bronze_complet, sortie)  # par-dessus la sortie existante
    assert _arbre(sortie) == reference


@pytest.mark.parametrize("coupure", range(1, len(ARCHIVES) + 1))
def test_reprise_apres_chaque_point_d_arret(
    coupure: int, tmp_path: Path, reference: dict[str, bytes]
) -> None:
    """Un bronze arrêté après ``coupure`` archives, rejeu complet ; puis le reste, --reprendre."""
    jusqu_a = SUITE.index(ARCHIVES[coupure - 1]) + 1
    racine, sortie = tmp_path / "bronze", tmp_path / "sortie"
    peupler(racine, SUITE[:jusqu_a])
    assert _executer(racine, sortie).code_sortie == 0
    peupler(racine, SUITE[jusqu_a:])
    assert _executer(racine, sortie, reprendre=True).code_sortie == 0
    assert _arbre(sortie) == reference


def test_reprise_sans_rien_de_nouveau_et_sans_etat(
    bronze_complet: Path, tmp_path: Path, reference: dict[str, bytes]
) -> None:
    sortie = tmp_path / "sortie"
    _executer(bronze_complet, sortie)
    rapport = _executer(bronze_complet, sortie, reprendre=True)
    assert all(r.archives_lues == 0 for r in rapport.resumes) and _arbre(sortie) == reference
    (sortie / "etat.json").unlink()
    _executer(bronze_complet, sortie, reprendre=True)
    assert _arbre(sortie) == reference, "sans état, la reprise est un rejeu complet"


def test_aucun_identifiant_en_double_et_appliquer_sur_la_sortie_relue(
    bronze_complet: Path, tmp_path: Path
) -> None:
    sortie = tmp_path / "sortie"
    _executer(bronze_complet, sortie)
    contrats = charger_tous()
    etat = json.loads((sortie / "etat.json").read_text(encoding="utf-8"))
    identifiants: list[str] = []
    for identifiant in (PRESENTATIONS, DISPO):
        evenements = list(lire_evenements(sortie, identifiant))
        identifiants.extend(e.id for e in evenements)
        archive = next(
            a
            for a in rejeu.bronze.lister(bronze_complet, "bdpm", contrats[identifiant].fichier)
            if a.relatif(bronze_complet) == etat["entites"][identifiant]["dernier_retenu"]
        )
        dernier = snapshot.lire(contrats[identifiant], archive, bronze_complet)
        assert appliquer({}, evenements) == etat_du_snapshot(dernier), identifiant
    assert len(identifiants) == len(set(identifiants)) == 80 + 12
    fichier = next((sortie / "evenements" / DISPO).glob("20261024T172300Z__*.jsonl"))
    relus = [schema.deserialiser(li) for li in fichier.read_text(encoding="utf-8").splitlines()]
    assert [(e.type.value, e.rang) for e in relus] == [("supprimee", 3), ("supprimee", 2)], (
        "la ligne en triple ramenée à une : du rang le plus haut au plus bas, relu du disque"
    )


def test_reprendre_refuse_si_le_contrat_a_change(bronze_complet: Path, tmp_path: Path) -> None:
    sortie = tmp_path / "sortie"
    _executer(bronze_complet, sortie)
    etat_chemin = sortie / "etat.json"
    etat = json.loads(etat_chemin.read_text(encoding="utf-8"))
    etat["entites"][PRESENTATIONS]["version_contrat"] = "v0"
    etat_chemin.write_text(json.dumps(etat), encoding="utf-8")
    with pytest.raises(ReprendreImpossible, match="passé de v0 à v1 : relance sans --reprendre"):
        _executer(bronze_complet, sortie, reprendre=True)
    resultat = CliRunner().invoke(
        application,
        ["evenements", "--racine", str(bronze_complet), "--sortie", str(sortie), "--reprendre"],
    )
    assert resultat.exit_code == 2 and "reprise impossible" in resultat.output
    etat_chemin.write_text('{"version": 1}', encoding="utf-8")
    with pytest.raises(ReprendreImpossible, match="illisible"):
        _executer(bronze_complet, sortie, reprendre=True)


def test_etat_illisible_sans_reprendre_dit_quoi_faire_et_n_efface_rien(
    bronze_complet: Path, tmp_path: Path, reference: dict[str, bytes]
) -> None:
    """Contrôle 3 bis : le conseil ne renvoie pas au rejeu complet qu'on vient de lancer."""
    sortie = tmp_path / "sortie"
    _executer(bronze_complet, sortie)
    etat_chemin = sortie / "etat.json"
    etat_chemin.write_text("{pas du json", encoding="utf-8")
    with pytest.raises(ReprendreImpossible, match="choisis une autre sortie"):
        _executer(bronze_complet, sortie)
    resultat = CliRunner().invoke(
        application, ["evenements", "--racine", str(bronze_complet), "--sortie", str(sortie)]
    )
    assert resultat.exit_code == 2 and "rejeu impossible" in resultat.output
    assert "relance sans --reprendre" not in resultat.output
    intact = {c: o for c, o in _arbre(sortie).items() if c != "etat.json"}
    assert intact == {c: o for c, o in reference.items() if c != "etat.json"}, "rien n'est effacé"
    etat_chemin.unlink()
    _executer(bronze_complet, sortie)
    assert _arbre(sortie) == reference, "le conseil suivi, le rejeu complet redonne la référence"


def test_archive_illisible_arrete_le_fichier_et_sort_non_nul(tmp_path: Path) -> None:
    racine, sortie = tmp_path / "bronze", tmp_path / "sortie"
    peupler(racine, SUITE[:3])
    cible = next(racine.rglob("CIS_CIP_bdpm.txt/*/*T151700Z__*.gz"))
    cible.write_bytes(b"pas du gzip")
    rapport = _executer(racine, sortie)
    assert rapport.code_sortie == 1
    pres = rapport.resumes[0]
    assert pres.erreur is not None and "archive illisible" in pres.erreur
    assert pres.archives_lues == 1 and rapport.resumes[1].erreur is None, "l'autre fichier continue"


def test_commande_evenements(bronze_complet: Path, tmp_path: Path) -> None:
    sortie = tmp_path / "sortie"
    lanceur = CliRunner()
    resultat = lanceur.invoke(
        application,
        [
            "evenements",
            "--racine",
            str(bronze_complet),
            "--sortie",
            str(sortie),
            "--fichier",
            "CIS_CIP_bdpm.txt",
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    assert (
        "bdpm.presentations" in resultat.output
        and "16 archive(s) lue(s), 11 retenue(s), 4 écartée(s), 1 en attente" in resultat.output
    )
    assert (
        "creee 41, modifiee 6, supprimee 33" in resultat.output
        and "bdpm.disponibilite" not in resultat.output
    )
    assert (sortie / "evenements" / PRESENTATIONS).is_dir() and not (
        sortie / "evenements" / DISPO
    ).exists()
    reprise = lanceur.invoke(
        application,
        ["evenements", "--racine", str(bronze_complet), "--sortie", str(sortie), "--reprendre"],
    )
    assert reprise.exit_code == 0 and "bdpm.disponibilite" in reprise.output
    assert "bdpm.presentations           0 archive(s) lue(s)" in reprise.output
    assert "bdpm.disponibilite           6 archive(s) lue(s)" in reprise.output, "rejeu complet"
    sous_racine = lanceur.invoke(
        application,
        [
            "evenements",
            "--racine",
            str(bronze_complet),
            "--sortie",
            str(bronze_complet / "evenements"),
        ],
    )
    assert sous_racine.exit_code == 2 and "ne s'écrit pas" in sous_racine.output
    assert not (bronze_complet / "evenements").exists(), "l'archive n'est jamais écrite"


def test_rejeu_complet_interrompu_puis_reprise(
    bronze_complet: Path, tmp_path: Path, reference: dict[str, bytes]
) -> None:
    """Contrôle 3 : l'entité quitte l'état avant l'effacement, la reprise la rejoue en entier."""
    sortie = tmp_path / "sortie"
    assert _executer(bronze_complet, sortie).code_sortie == 0
    premiere = min(bronze_complet.rglob("CIS_CIP_bdpm.txt/*/*.gz"))
    octets = premiere.read_bytes()
    premiere.write_bytes(b"pas du gzip")
    rapport = _executer(bronze_complet, sortie)  # rejeu complet coupé en tête
    assert rapport.code_sortie == 1 and rapport.resumes[0].archives_lues == 0
    etat = json.loads((sortie / "etat.json").read_text(encoding="utf-8"))
    assert PRESENTATIONS not in etat["entites"] and DISPO in etat["entites"]
    assert not (sortie / "evenements" / PRESENTATIONS).exists()
    premiere.write_bytes(octets)
    rapport = _executer(bronze_complet, sortie, reprendre=True)
    assert rapport.code_sortie == 0 and rapport.resumes[0].archives_lues == 16
    assert _arbre(sortie) == reference, "la reprise redonne la sortie du rejeu complet"


def test_une_sortie_de_rejeu_complet_repart_de_zero(
    bronze_complet: Path, tmp_path: Path, reference: dict[str, bytes]
) -> None:
    sortie = tmp_path / "sortie"
    _executer(bronze_complet, sortie)
    intrus = sortie / "evenements" / PRESENTATIONS / "00000000T000000Z__intrus.jsonl"
    intrus.write_text("", encoding="utf-8")
    shutil.copy(intrus, sortie / "bilans" / PRESENTATIONS / "00000000T000000Z__intrus.json")
    _executer(bronze_complet, sortie)
    assert _arbre(sortie) == reference, "un fichier d'une exécution précédente ne survit pas"


def test_commande_evenements_journalise_sur_la_sortie_d_erreur(
    bronze_complet: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mission 04 (Q4) : le journal par archive existe et ne se mêle pas à la sortie standard."""
    import sys

    from pharmaflux import cli

    appels: list[bool] = []
    monkeypatch.setattr(
        cli, "configurer_journal", lambda flux=None: appels.append(flux is sys.stderr)
    )
    resultat = CliRunner().invoke(
        application,
        ["evenements", "--racine", str(bronze_complet), "--sortie", str(tmp_path / "sortie")],
    )
    assert resultat.exit_code == 0, resultat.output
    assert appels == [True], "configuré une fois, sur la sortie d'erreur"
