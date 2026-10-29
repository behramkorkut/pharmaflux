"""Outils communs des tests : serveur simulé sur fixtures, horloge, lancement d'un passage,
et les fixtures des tests d'intégration contre le Redpanda local.

Aucun test unitaire n'appelle le réseau : ``httpx.MockTransport`` sert les
fichiers de ``tests/fixtures/`` (extraits réels, voir
``tests/fixtures/README.md``). Les tests marqués ``integration`` parlent au
courtier de ``docker compose -p pharmaflux up -d`` ; sans lui, ``bus`` les
saute, et le dit (un échec en CI, ``PHARMAFLUX_INTEGRATION_EXIGEE``).
"""

from __future__ import annotations

# Ne pas retirer cet import, ni le déplacer : ``pharmaflux.silver`` pose
# ARROW_DEFAULT_MEMORY_POOL=system, qui ne vaut que s'il précède le premier import de PyArrow
# (ADR 0009). Les modules de test importent PyArrow tôt ; sans cet import en tête, Arrow prend
# jemalloc et le test des vues sur le jeu de démo monte à 945 Mo au lieu de 524 (mission 06,
# palier 2). Les tests mesurent ainsi la mémoire comme la ligne de commande la consomme.
import pharmaflux.silver  # noqa: F401  # isort: skip

import os
import re
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import registre as registre_module
from pharmaflux.bus.client import (
    COURTIER_PAR_DEFAUT,
    VARIABLE_COURTIER,
    BusKafka,
    CourtierInjoignable,
    LecteurKafka,
)
from pharmaflux.bus.registre import (
    REGISTRE_PAR_DEFAUT,
    VARIABLE_REGISTRE,
    Registre,
    enregistrer_tout,
    sujets_du_projet,
)
from pharmaflux.collecte.catalogue import CATALOGUE, Entree
from pharmaflux.collecte.passage import Bilan, executer_passage
from pharmaflux.collecte.telechargement import Telechargeur
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.demo.jeu import JEU_PAR_DEFAUT
from pharmaflux.evenements import rejeu

FIXTURES = Path(__file__).parent / "fixtures"
EN_TETES_IGNORES = {"transfer-encoding", "content-length", "content-encoding"}

# Une réponse scénarisée : (statut, contenu, en-têtes) ou une exception à lever.
ReponseSimulee = tuple[int, bytes, dict[str, str]] | Exception

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_CADRE = re.compile(r"[─│╭╮╰╯]")


def texte_nu(sortie: str) -> str:
    """La sortie d'une commande sans couleurs ni cadre Rich, les blancs réduits à une espace.

    Typer affiche une erreur d'option (code 2) dans un cadre Rich de 80 colonnes, en couleur
    sur le runner de la CI (``GITHUB_ACTIONS``) ; la ligne est coupée là où le chemin qu'elle
    contient la pousse. Une phrase se cherche donc ici, jamais dans la sortie brute.
    """
    return " ".join(_CADRE.sub(" ", _ANSI.sub("", sortie)).split())


def chemin_fixture(entree: Entree) -> Path:
    return FIXTURES / entree.source / entree.fichier.replace("metadonnees.json", "dataset.json")


def contenu_fixture(entree: Entree) -> bytes:
    return chemin_fixture(entree).read_bytes()


def en_tetes_fixture(entree: Entree) -> dict[str, str]:
    """Les en-têtes HTTP relevés au §0, sans ceux que le transport gère lui-même."""
    en_tetes: dict[str, str] = {}
    lignes = chemin_fixture(entree).with_suffix(chemin_fixture(entree).suffix + ".headers")
    for ligne in lignes.read_text(encoding="utf-8").splitlines()[1:]:
        nom, separateur, valeur = ligne.partition(":")
        if separateur and nom.strip().lower() not in EN_TETES_IGNORES:
            en_tetes[nom.strip()] = valeur.strip()
    return en_tetes


@dataclass
class ServeurSimule:
    """Répond aux URL du catalogue avec les fixtures ; scénarisable URL par URL."""

    reponses: dict[str, list[ReponseSimulee]] = field(default_factory=dict)
    requetes: list[httpx.Request] = field(default_factory=list)

    def servir_catalogue(self) -> None:
        for entree in CATALOGUE:
            self.reponses[entree.url] = [(200, contenu_fixture(entree), en_tetes_fixture(entree))]

    def scenariser(self, url: str, *suite: ReponseSimulee) -> None:
        """Les réponses successives de ``url`` ; la dernière est répétée ensuite."""
        self.reponses[url] = list(suite)

    def remplacer_contenu(self, url: str, contenu: bytes) -> None:
        statut, _, en_tetes = self._derniere(url)
        self.reponses[url] = [(statut, contenu, en_tetes)]

    def _derniere(self, url: str) -> tuple[int, bytes, dict[str, str]]:
        derniere = self.reponses[url][-1]
        assert not isinstance(derniere, Exception)
        return derniere

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        suite = self.reponses.get(str(requete.url))
        if not suite:
            return httpx.Response(404, content=b"inconnu du serveur simule")
        reponse = suite.pop(0) if len(suite) > 1 else suite[0]
        if isinstance(reponse, Exception):
            raise reponse
        statut, contenu, en_tetes = reponse
        return httpx.Response(statut, content=contenu, headers=en_tetes)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._repondre)

    def requetes_vers(self, url: str) -> int:
        return sum(1 for requete in self.requetes if str(requete.url) == url)


@dataclass
class Horloge:
    """Une horloge qui avance d'une seconde à chaque lecture, pilotable."""

    instant: datetime = datetime(2026, 10, 24, 14, 17, 0, tzinfo=UTC)

    def maintenant(self) -> datetime:
        courant = self.instant
        self.instant += timedelta(seconds=1)
        return courant

    def avancer(self, **duree: int) -> None:
        self.instant += timedelta(**duree)


@pytest.fixture
def serveur() -> ServeurSimule:
    simule = ServeurSimule()
    simule.servir_catalogue()
    return simule


@pytest.fixture
def horloge() -> Horloge:
    return Horloge()


@pytest.fixture
def racine(tmp_path: Path) -> Path:
    return tmp_path / "pharmaflux-data"


Lanceur = Callable[..., Bilan]


@pytest.fixture
def lancer(racine: Path, serveur: ServeurSimule, horloge: Horloge) -> Lanceur:
    """Un passage sans réseau, sans attente, sur l'horloge et le serveur simulés."""

    def _lancer(entrees: Iterable[Entree] = CATALOGUE) -> Bilan:
        with Telechargeur(
            transport=serveur.transport(), attente_base=0, dormir=lambda _: None
        ) as telechargeur:
            return executer_passage(
                racine,
                list(entrees),
                telechargeur,
                maintenant=horloge.maintenant,
                dormir=lambda _: None,
                pause=0,
            )

    return _lancer


def entrees_bdpm_txt() -> list[Entree]:
    """Les onze fichiers TSV de la BDPM, ceux qui ont un contrat de schéma."""
    return [e for e in CATALOGUE if e.source == "bdpm" and e.extension == ".txt"]


def entree(identifiant: str) -> Entree:
    return next(e for e in CATALOGUE if e.identifiant == identifiant)


# --- Intégration : le Redpanda local -----------------------------------------------------------

COURTIER = os.environ.get(VARIABLE_COURTIER, COURTIER_PAR_DEFAUT)
REGISTRE = os.environ.get(VARIABLE_REGISTRE, REGISTRE_PAR_DEFAUT)
VARIABLE_EXIGEE = "PHARMAFLUX_INTEGRATION_EXIGEE"  # posée par la CI : un saut devient un échec
ENTITES_INTEGRATION = ["bdpm.presentations", "bdpm.disponibilite"]  # les sujets et topics du test


@pytest.fixture(scope="session")
def bus() -> Iterator[BusKafka]:
    """Le courtier, ou le saut de tous les tests d'intégration avec le motif (échec en CI)."""
    bus_ = BusKafka(COURTIER)
    try:
        bus_.verifier_courtier(delai_s=5)
    except CourtierInjoignable as exc:
        motif = f"aucun courtier sur {COURTIER} (docker compose -p pharmaflux up -d) : {exc}"
        if os.environ.get(VARIABLE_EXIGEE):
            pytest.fail(f"{VARIABLE_EXIGEE} est posée, le saut est un échec : {motif}")
        pytest.skip(motif)
    yield bus_
    bus_.attendre(10)


@pytest.fixture
def prefixe() -> str:
    """Un préfixe par test : chaque test relit des topics qu'il est seul à remplir."""
    return f"pharmaflux.test-{uuid.uuid4().hex[:8]}"


@dataclass
class Nettoyage:
    """Les sujets et les topics créés par les tests, effacés une seule fois en fin de session."""

    sujets: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)


@pytest.fixture(scope="session")
def a_nettoyer(bus: BusKafka) -> Iterator[Nettoyage]:
    """Le nettoyage en fin de session, et non à la fin de chaque test (mission 07, A1).

    Le registre de Redpanda coupait parfois un ``POST …/versions`` pendant qu'il effaçait les
    topics du test précédent (run de ``main`` sur ``98505d3``, puis 1 passage sur 15 sur le
    Mac) : plus aucun test n'écrit dans le registre pendant un effacement. Les préfixes sont
    uniques par test.
    """
    nettoyage = Nettoyage()
    yield nettoyage
    with Registre(REGISTRE) as registre_:
        for sujet_ in nettoyage.sujets:
            registre_.supprimer(sujet_)
    if nettoyage.topics:
        bus.supprimer_topics(nettoyage.topics)


@pytest.fixture
def registre(a_nettoyer: Nettoyage, prefixe: str) -> Iterator[Registre]:
    """Les schémas enregistrés sous les sujets du test ; effacés, avec les topics, en fin
    de session."""
    a_nettoyer.sujets += [s for s, _ in sujets_du_projet(ENTITES_INTEGRATION, prefixe)]
    a_nettoyer.topics += [
        *(env.nom_topic(entite, prefixe) for entite in ENTITES_INTEGRATION),
        env.topic_echecs(prefixe),
    ]
    with Registre(REGISTRE) as registre_:
        enregistrer_tout(registre_, ENTITES_INTEGRATION, prefixe)
        yield registre_


@pytest.fixture(autouse=True)
def reessais_isoles(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hors intégration, les réessais du registre (simulés) ne comptent pas pour la session."""
    if request.node.get_closest_marker("integration") is None:
        monkeypatch.setattr(registre_module, "REESSAIS", [])


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Un réessai du registre pendant les tests d'intégration fait échouer la session (A2).

    Le réessai protège la chaîne réelle ; dans les tests, il cacherait une nouvelle cause de
    coupure. Seul le test de reproduction, dont c'est l'objet, retire les siens du décompte.
    """
    if not registre_module.REESSAIS:
        return
    rapport = session.config.pluginmanager.get_plugin("terminalreporter")
    lignes = [
        f"un réessai a servi pendant les tests d'intégration ({len(registre_module.REESSAIS)}) :"
        " voir les lignes « registre : … » horodatées, à recouper avec le journal du courtier",
        *registre_module.REESSAIS,
    ]
    if rapport is not None:
        rapport.ensure_newline()
        rapport.section("réessais du registre", red=True)
        for ligne in lignes:
            rapport.write_line(ligne)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture
def lecteur() -> Iterator[LecteurKafka]:
    lecteur_ = LecteurKafka(COURTIER)
    yield lecteur_
    lecteur_.close()


# --- Le silver du jeu de démo, une fois par session --------------------------------------------


@pytest.fixture(scope="session")
def demo_silver(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Les événements et le silver de ``demo/archive``, dans un dossier jetable (missions 05, 06).

    Une vingtaine de secondes ; le silver (``test_silver_demo``) et le gold
    (``test_gold_demo``) le lisent sans l'écrire.
    """
    from pharmaflux.silver import construction  # PyArrow : seulement pour qui le demande

    sortie = tmp_path_factory.mktemp("demo") / "evenements"
    rapport = rejeu.executer(JEU_PAR_DEFAUT, sortie, charger_tous(), list(charger_tous()))
    assert rapport.code_sortie == 0
    dossier = tmp_path_factory.mktemp("demo") / "lakehouse"
    construction.construire(sortie, dossier, charger_tous(), list(charger_tous()))
    return sortie, dossier
