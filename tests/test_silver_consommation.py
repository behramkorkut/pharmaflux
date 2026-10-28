"""Mission 05, palier 2 : le consommateur du bus sur un bus simulé, sans Docker (décision 3).

Le ``BusSimule`` de la mission 03 reçoit la publication des fichiers du
bronze de synthèse (``SUITE`` de ``test_rejeu``) ; ``LecteurSilverSimule``
le relit en **trois partitions** réparties par la clé du message, chacune
dans l'ordre d'arrivée, comme Redpanda. Le silver du bus est comparé à celui
des fichiers (``comparer``) et vérifié contre l'archive (``verifier``). Les
coupures sont simulées à chaque étape : pendant la lecture, pendant le commit
du catalogue (entre le ``metadata.json`` et SQLite), après le commit.
"""

from __future__ import annotations

import shutil
import zlib
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from pyiceberg.catalog.sql import SqlCatalog
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import publication
from pharmaflux.bus.client import CourtierInjoignable, EtatTopic, MessageLu
from pharmaflux.bus.enveloppe import Enveloppe
from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.evenements import rejeu
from pharmaflux.silver import (
    FluxIncoherent,
    SilverRefuse,
    comparaison,
    consommation,
    construction,
    verification,
)
from pharmaflux.silver.consommation import PROP_OFFSETS, Position, consommer, lire_positions
from pharmaflux.silver.entrepot import (
    ORIGINE_BUS,
    PROP_GRAPPE,
    PROP_ORIGINE,
    PROP_POSITIONS,
    PROP_VERSION_CONTRAT,
    Entrepot,
)
from tests.conftest import texte_nu
from tests.test_bus import BusSimule, _registre_pret
from tests.test_bus_verification import BusCoupe
from tests.test_rejeu import DISPO, PRESENTATIONS, SUITE, peupler

ENTITES = [PRESENTATIONS, DISPO]
GRAPPE = "simule.aaaa-bbbb"


class LecteurSilverSimule:
    """Relit le ``BusSimule`` en ``partitions`` partitions, réparties par la clé du message."""

    def __init__(self, bus: BusSimule, partitions: int = 3, grappe: str | None = GRAPPE) -> None:
        self.bus = bus
        self.partitions = partitions
        self.grappe = grappe
        self.injectes: dict[tuple[str, int], list[Enveloppe]] = {}

    def _listes(self, nom: str) -> dict[int, list[Enveloppe]]:
        listes: dict[int, list[Enveloppe]] = {p: [] for p in range(self.partitions)}
        for enveloppe in self.bus.messages.get(nom, []):
            listes[zlib.crc32(enveloppe.cle) % self.partitions].append(enveloppe)
        for (topic, partition), extras in self.injectes.items():
            if topic == nom:
                listes[partition].extend(extras)
        return listes

    def injecter(self, nom: str, partition: int, valeur: bytes) -> None:
        """Un message brut à la fin d'une partition : ce que le bus ne devrait jamais porter."""
        self.injectes.setdefault((nom, partition), []).append(
            Enveloppe(nom, b"{}", valeur, [("id", b"injecte")], 0)
        )

    def identifiant_grappe(self) -> str | None:
        return self.grappe

    def decrire_topic(self, nom: str) -> EtatTopic | None:
        definition = self.bus.topics.get(nom)
        if definition is None:
            return None
        return EtatTopic(nom, self.partitions, dict(definition.configuration))

    def bornes(self, nom: str) -> dict[int, tuple[int, int]]:
        return {p: (0, len(liste)) for p, liste in self._listes(nom).items()}

    def message_a(self, nom: str, partition: int, offset: int) -> MessageLu | None:
        liste = self._listes(nom).get(partition, [])
        if not 0 <= offset < len(liste):
            return None
        return _lu(nom, partition, offset, liste[offset])

    def derniers_messages(
        self, nom: str, offsets: Mapping[int, int]
    ) -> dict[int, MessageLu | None]:
        return {p: self.message_a(nom, p, o) for p, o in offsets.items()}

    def lire_depuis(
        self, nom: str, debuts: Mapping[int, int], fins: Mapping[int, int]
    ) -> Iterator[MessageLu]:
        listes = self._listes(nom)
        curseurs = {p: debuts.get(p, 0) for p in sorted(fins)}
        while True:
            avance = False
            for p, offset in list(curseurs.items()):  # les partitions tour à tour, en ordre
                if offset < fins[p]:
                    yield _lu(nom, p, offset, listes[p][offset])
                    curseurs[p] = offset + 1
                    avance = True
            if not avance:
                return


def _lu(nom: str, partition: int, offset: int, e: Enveloppe) -> MessageLu:
    return MessageLu(nom, partition, offset, e.cle, e.valeur, dict(e.en_tetes), e.horodatage_ms)


class LecteurCoupe(LecteurSilverSimule):
    """Le courtier tombe après ``apres`` messages lus, toutes lectures confondues."""

    def __init__(self, bus: BusSimule, apres: int) -> None:
        super().__init__(bus)
        self.apres = apres
        self.lus = 0

    def lire_depuis(
        self, nom: str, debuts: Mapping[int, int], fins: Mapping[int, int]
    ) -> Iterator[MessageLu]:
        for message in super().lire_depuis(nom, debuts, fins):
            if self.lus >= self.apres:
                raise CourtierInjoignable(f"coupure simulée après {self.lus} message(s)")
            self.lus += 1
            yield message


@pytest.fixture(scope="module")
def monde(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, BusSimule, Path]:
    """Le bronze de synthèse, sa sortie, le bus qui l'a reçue, le silver des fichiers."""
    racine = tmp_path_factory.mktemp("bronze") / "pharmaflux-data"
    peupler(racine, SUITE)
    sortie = tmp_path_factory.mktemp("sortie") / "evenements"
    assert rejeu.executer(racine, sortie, charger_tous(), ENTITES).code_sortie == 0
    bus = BusSimule()
    _, registre = _registre_pret()
    assert publication.executer(sortie, bus, registre).code_sortie == 0
    fichiers = tmp_path_factory.mktemp("silver") / "fichiers"
    construction.construire(sortie, fichiers, charger_tous(), ENTITES)
    return racine, sortie, bus, fichiers


def _consommer(lecteur: LecteurSilverSimule, dossier: Path, lot: int = 7) -> consommation.Rapport:
    return consommer(lecteur, dossier, charger_tous(), ENTITES, lot=lot)


def _egal(dossier: Path, fichiers: Path) -> None:
    assert comparaison.comparer(Entrepot.ouvrir(dossier), Entrepot.ouvrir(fichiers)) == []


def test_le_silver_du_bus_egale_celui_des_fichiers_et_l_archive(
    monde: tuple[Path, Path, BusSimule, Path], tmp_path: Path
) -> None:
    racine, sortie, bus, fichiers = monde
    lecteur = LecteurSilverSimule(bus)
    dossier = tmp_path / "bus"
    rapport = _consommer(lecteur, dossier)
    assert rapport.grappe == GRAPPE and not rapport.avertissements
    assert [r.identifiant for r in rapport.resumes] == ENTITES
    for resume in rapport.resumes:
        bornes = lecteur.bornes(resume.topic)
        assert resume.messages == sum(fin for _, fin in bornes.values()) > 0
        assert resume.doublons == 0 and resume.commits >= 2 and not resume.notes
        assert resume.positions == {
            p: Position(fin, lecteur.message_a(resume.topic, p, fin - 1).en_tetes["id"].decode())  # type: ignore[union-attr]
            for p, (_, fin) in bornes.items()
            if fin
        }
    _egal(dossier, fichiers)
    verif = verification.verifier(Entrepot.ouvrir(dossier), sortie, racine, charger_tous(), ENTITES)
    assert verif.code_sortie == 0 and verif.archives_conformes == verif.archives_verifiees > 0
    silver = Entrepot.ouvrir(dossier)
    table = silver.table(PRESENTATIONS)
    assert table is not None
    assert table.properties[PROP_ORIGINE] == ORIGINE_BUS and table.properties[PROP_GRAPPE] == GRAPPE
    assert lire_positions(table) == rapport.resumes[0].positions
    dernier = table.current_snapshot()
    assert dernier is not None and PROP_OFFSETS in dernier.summary.additional_properties
    # Rien de nouveau : aucun commit, les métadonnées ne bougent pas.
    emplacement = table.metadata_location
    encore = _consommer(lecteur, dossier)
    assert all(
        r.messages == 0 and r.commits == 0 and "rien de nouveau" in r.notes for r in encore.resumes
    )
    table = silver.table(PRESENTATIONS)
    assert table is not None and table.metadata_location == emplacement
    _egal(dossier, fichiers)


def test_reprise_apres_une_publication_en_deux_fois_et_apres_des_doublons(
    monde: tuple[Path, Path, BusSimule, Path], tmp_path: Path
) -> None:
    _, sortie, _, fichiers = monde
    # Une sortie qui grandit : les premiers fichiers, publiés et consommés ; puis le reste.
    progressive = tmp_path / "progressive"
    tous = sorted((sortie / rejeu.DOSSIER_EVENEMENTS).rglob("*.jsonl"))
    moitie = len(tous) // 2
    for fichier in tous[:moitie]:
        cible = progressive / fichier.relative_to(sortie)
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fichier, cible)
    bus = BusSimule()
    _, registre = _registre_pret()
    assert publication.executer(progressive, bus, registre).code_sortie == 0
    dossier = tmp_path / "bus"
    premier = _consommer(LecteurSilverSimule(bus), dossier)
    for fichier in tous[moitie:]:
        shutil.copyfile(fichier, progressive / fichier.relative_to(sortie))
    assert publication.executer(progressive, bus, registre, reprendre=True).code_sortie == 0
    second = _consommer(LecteurSilverSimule(bus), dossier)
    assert second.messages > 0 and all(r.doublons == 0 for r in second.resumes)
    assert premier.messages + second.messages == sum(len(m) for m in bus.messages.values())
    _egal(dossier, fichiers)
    # Une publication coupée pendant un fichier puis reprise : des doublons sur le bus.
    copie = tmp_path / "copie"  # la sortie du monde porte déjà son publication.json
    shutil.copytree(sortie / rejeu.DOSSIER_EVENEMENTS, copie / rejeu.DOSSIER_EVENEMENTS)
    bus2 = BusSimule()
    _, registre2 = _registre_pret()
    coupe = BusCoupe(bus2, apres=1)
    with pytest.raises(publication.LivraisonEchouee):
        publication.executer(copie, coupe, registre2)
    assert publication.executer(copie, bus2, registre2, reprendre=True).code_sortie == 0
    total = sum(len(m) for m in bus2.messages.values())
    dossier2 = tmp_path / "bus2"
    rapport = _consommer(LecteurSilverSimule(bus2), dossier2)
    assert rapport.messages == total and sum(r.doublons for r in rapport.resumes) > 0
    _egal(dossier2, fichiers)


def _points(total: int, lot: int) -> list[int]:
    """Quelques points de coupure : le début, les bords du premier et du dernier lot, le milieu,
    la fin. Chaque point coûte deux consommations et une comparaison."""
    dernier_bord = (total - 1) // lot * lot
    points = {0, 1, lot - 1, lot, lot + 1, total // 2, dernier_bord, total - 1}
    return sorted(p for p in points if 0 <= p < total)


def test_coupure_pendant_la_lecture_puis_reprise(
    monde: tuple[Path, Path, BusSimule, Path], tmp_path: Path
) -> None:
    _, _, bus, fichiers = monde
    total = sum(len(m) for m in bus.messages.values())
    for n in _points(total, 7):
        dossier = tmp_path / f"coupure-{n}"
        with pytest.raises(CourtierInjoignable, match="coupure simulée"):
            _consommer(LecteurCoupe(bus, apres=n), dossier)
        reprise = _consommer(LecteurSilverSimule(bus), dossier)
        assert reprise.messages <= total
        _egal(dossier, fichiers)


def test_coupure_pendant_et_apres_le_commit_puis_reprise(
    monde: tuple[Path, Path, BusSimule, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le commit du catalogue : le metadata.json est écrit, puis la ligne SQLite mise à jour.

    La cale vise ``SqlCatalog._write_metadata`` de PyIceberg **0.12.0**, appelée
    par ``commit_table`` juste avant l'``UPDATE`` : lever après elle simule une
    coupure entre les deux. Si une montée de version la déplace, ce test casse,
    et c'est voulu : la reprise est à revoir.
    """
    _, _, bus, fichiers = monde
    original = SqlCatalog._write_metadata
    for k in (1, 2, 5):
        appels = {"n": 0}

        def cale(
            *args: object, k: int = k, appels: dict[str, int] = appels, **kwargs: object
        ) -> None:
            appels["n"] += 1
            original(*args, **kwargs)
            if appels["n"] == k:
                raise RuntimeError("coupure simulée entre le metadata.json et SQLite")

        dossier = tmp_path / f"commit-{k}"
        monkeypatch.setattr(SqlCatalog, "_write_metadata", staticmethod(cale))
        with pytest.raises(RuntimeError, match="coupure simulée"):
            _consommer(LecteurSilverSimule(bus), dossier)
        monkeypatch.setattr(SqlCatalog, "_write_metadata", staticmethod(original))
        _consommer(LecteurSilverSimule(bus), dossier)
        _egal(dossier, fichiers)
    # Après le commit : le lot est appliqué, position comprise ; la reprise continue après lui.
    original_lot = consommation.appliquer_lot
    for k in (1, 3):
        appels = {"n": 0}

        def apres_commit(
            *args: object, k: int = k, appels: dict[str, int] = appels, **kwargs: object
        ) -> object:
            resultat = original_lot(*args, **kwargs)  # type: ignore[arg-type]
            appels["n"] += 1
            if appels["n"] == k:
                raise RuntimeError("coupure simulée après le commit")
            return resultat

        dossier = tmp_path / f"apres-{k}"
        monkeypatch.setattr(consommation, "appliquer_lot", apres_commit)
        with pytest.raises(RuntimeError, match="après le commit"):
            _consommer(LecteurSilverSimule(bus), dossier)
        monkeypatch.setattr(consommation, "appliquer_lot", original_lot)
        reprise = _consommer(LecteurSilverSimule(bus), dossier)
        assert all(r.doublons == 0 for r in reprise.resumes)  # la position a avancé avec le lot
        _egal(dossier, fichiers)


def test_refus_du_consommateur(monde: tuple[Path, Path, BusSimule, Path], tmp_path: Path) -> None:
    _, sortie, bus, fichiers = monde
    topic = env.nom_topic(PRESENTATIONS)
    # Un silver construit depuis les fichiers n'a pas de position.
    with pytest.raises(SilverRefuse, match="construit depuis les fichiers"):
        _consommer(LecteurSilverSimule(bus), fichiers)
    # Un bus vide : aucun topic.
    with pytest.raises(SilverRefuse, match="bus est vide"):
        _consommer(LecteurSilverSimule(BusSimule()), tmp_path / "vide")
    assert not (tmp_path / "vide").exists()
    # Un message qui n'est pas un événement v1, en tête d'une partition : rien n'est écrit.
    lecteur = LecteurSilverSimule(bus)
    lecteur.injecter(topic, 0, b"pas du JSON")
    dossier = tmp_path / "illisible"
    with pytest.raises(FluxIncoherent, match="pas un événement v1"):
        _consommer(lecteur, dossier, lot=10**6)
    table = Entrepot.ouvrir(dossier).table(PRESENTATIONS)
    assert table is not None and table.current_snapshot() is None
    assert PROP_POSITIONS not in table.properties
    # Le même, après un lot déjà appliqué : le lot fautif n'est pas écrit, la position tient.
    dossier = tmp_path / "illisible-tard"
    with pytest.raises(FluxIncoherent):
        _consommer(lecteur, dossier, lot=5)
    table = Entrepot.ouvrir(dossier).table(PRESENTATIONS)
    assert table is not None
    positions = lire_positions(table)
    assert positions and all(
        v.suivant <= lecteur.bornes(topic)[p][1] - 1 for p, v in positions.items() if p == 0
    )
    # Un silver du bus, puis un bus rebâti autrement (d'autres événements) : refus par les ids.
    dossier = tmp_path / "bus"
    _consommer(LecteurSilverSimule(bus), dossier)
    autre = BusSimule()
    _, registre = _registre_pret()
    amputee = tmp_path / "amputee"
    for fichier in sorted((sortie / rejeu.DOSSIER_EVENEMENTS).rglob("*.jsonl"))[1:]:
        cible = amputee / fichier.relative_to(sortie)
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fichier, cible)
    assert publication.executer(amputee, autre, registre).code_sortie == 0
    with pytest.raises(SilverRefuse, match=r"n'est pas celui qui a construit le silver|au-delà"):
        _consommer(LecteurSilverSimule(autre), dossier)
    # Un bus rebâti vide : la position est au-delà de la fin.
    neuf = BusSimule()
    neuf.preparer_topics([publication._definitions(ENTITES, env.PREFIXE_PAR_DEFAUT)[0]])
    neuf.preparer_topics(publication._definitions(ENTITES, env.PREFIXE_PAR_DEFAUT))
    with pytest.raises(SilverRefuse, match="au-delà de la fin"):
        _consommer(LecteurSilverSimule(neuf), dossier)
    # Une autre grappe : un avertissement, pas un refus ; le silver reste égal.
    rapport = _consommer(LecteurSilverSimule(bus, grappe="simule.autre"), dossier)
    assert rapport.avertissements and "simule.autre" in rapport.avertissements[0]
    _egal(dossier, fichiers)
    # Une autre version de contrat dans la table : refus.
    table = Entrepot.ouvrir(dossier).table(PRESENTATIONS)
    assert table is not None
    with table.transaction() as transaction:
        transaction.set_properties({PROP_VERSION_CONTRAT: "v9"})
    with pytest.raises(SilverRefuse, match="rebâtis le silver"):
        _consommer(LecteurSilverSimule(bus), dossier)
    with pytest.raises(SilverRefuse, match="au moins 1"):
        _consommer(LecteurSilverSimule(bus), tmp_path / "lot", lot=0)


def test_commande_silver_consommer(
    monde: tuple[Path, Path, BusSimule, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, bus, fichiers = monde
    monkeypatch.setattr(cli, "fabriquer_lecteur_silver", lambda _courtier: LecteurSilverSimule(bus))
    lanceur = CliRunner()
    dossier = tmp_path / "bus"
    r = lanceur.invoke(
        application, ["silver", "consommer", "--entrepot", str(dossier), "--lot", "9"]
    )
    assert r.exit_code == 0, r.output
    assert (
        PRESENTATIONS in r.output
        and "positions : p0 →" in r.output
        and f"grappe : {GRAPPE}" in r.output
    )
    _egal(dossier, fichiers)
    r = lanceur.invoke(application, ["silver", "consommer", "--entrepot", str(dossier)])
    assert r.exit_code == 0 and "rien de nouveau" in r.output and "0 commit(s)" in r.output
    r = lanceur.invoke(application, ["silver", "consommer", "--entrepot", str(fichiers)])
    assert r.exit_code == 2 and "consommation refusée" in texte_nu(r.output)
    monkeypatch.setattr(
        cli, "fabriquer_lecteur_silver", lambda _courtier: LecteurCoupe(bus, apres=3)
    )
    r = lanceur.invoke(application, ["silver", "consommer", "--entrepot", str(tmp_path / "coupe")])
    assert r.exit_code == 1 and "consommation interrompue" in texte_nu(r.output)
    monkeypatch.setattr(
        cli,
        "fabriquer_lecteur_silver",
        lambda _courtier: LecteurSilverSimule(bus, grappe="simule.z"),
    )
    r = lanceur.invoke(application, ["silver", "consommer", "--entrepot", str(dossier)])
    assert r.exit_code == 0 and "AVERTISSEMENT" in r.output
