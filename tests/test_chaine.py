"""Mission 10, palier 1 : la chaîne enchaîne, sous un verrou, sans rien calculer.

Les chemins, le verrou, le journal des passages, le lancement d'une étape dans un
sous-processus (une vraie commande ``pharmaflux``, sans service), et le remplissage : l'ordre
des étapes, l'arrêt à la première qui échoue, le service qui ne répond pas, le verrou tenu.
Aucun service n'est joint : les sondes et, pour le remplissage, les étapes sont simulées.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.chaine import etapes, journal, passage, remplissage, sante
from pharmaflux.chaine.chemins import Chemins, CheminsRefuses, resoudre
from pharmaflux.chaine.etapes import Etape, Resultat
from pharmaflux.chaine.verrou import VerrouTenu, verrou
from tests.conftest import commande_cli, texte_nu

lanceur = CliRunner()


@pytest.fixture
def chemins(tmp_path: Path) -> Chemins:
    racine = tmp_path / "archive"
    racine.mkdir()
    return resoudre(racine, tmp_path / "derive")


def _resultat(etape: Etape, code: int | None = 0, signal_: int | None = None) -> Resultat:
    return Resultat(
        nom=etape.nom,
        commande="pharmaflux " + " ".join(etape.arguments),
        debut="2026-11-14T18:17:00Z",
        fin="2026-11-14T18:17:01Z",
        duree_s=1.0,
        code=code,
        signal=signal_,
        resident_mo=10,
    )


class Simulation:
    """Les étapes et les sondes simulées : ce qui a été lancé, et ce qui doit échouer."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.lancees: list[str] = []
        self.sondes: list[str] = []
        self.codes: dict[str, int | None] = {}
        self.pannes: dict[str, str] = {}
        self.environnement: dict[str, str] = {}
        monkeypatch.setattr(etapes, "lancer", self._lancer)
        monkeypatch.setattr(sante, "sonder", self._sonder)

    def _lancer(self, etape: Etape, *, environnement: dict[str, str], dossier: Path) -> Resultat:
        self.lancees.append(etape.nom)
        self.environnement = environnement
        self.dossier = dossier
        code = self.codes.get(etape.nom, 0)
        return _resultat(etape, code, signal.SIGKILL if code is None else None)

    def _sonder(self, service: str) -> str | None:
        self.sondes.append(service)
        return self.pannes.get(service)


@pytest.fixture(autouse=True)
def sans_variables_de_la_chaine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aucun test ne lit les chemins du shell qui lance pytest : un PHARMAFLUX_DERIVE exporté
    ferait écrire une commande simulée dans un vrai journal des passages."""
    for variable in ("PHARMAFLUX_DERIVE", "PHARMAFLUX_DATA", "PHARMAFLUX_MODELES"):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def simulation(monkeypatch: pytest.MonkeyPatch) -> Simulation:
    return Simulation(monkeypatch)


# --- chemins -----------------------------------------------------------------------------------


def test_les_dossiers_du_derive(chemins: Chemins) -> None:
    assert chemins.evenements == chemins.derive / "evenements"
    assert chemins.lakehouse == chemins.derive / "lakehouse"
    assert chemins.index == chemins.derive / "index"
    assert chemins.verrou == chemins.derive / "chaine" / "verrou"
    assert chemins.passages == chemins.derive / "chaine" / "passages.jsonl"


def test_chemins_refuses(tmp_path: Path) -> None:
    racine = tmp_path / "archive"
    racine.mkdir()
    with pytest.raises(CheminsRefuses, match="PHARMAFLUX_DERIVE"):
        resoudre(racine, None)
    with pytest.raises(CheminsRefuses, match="absolu"):
        resoudre(racine, Path("data/derive"))
    with pytest.raises(CheminsRefuses, match="introuvable"):
        resoudre(tmp_path / "absente", tmp_path / "derive")
    with pytest.raises(CheminsRefuses, match="modèles"):
        resoudre(racine, tmp_path / "derive", tmp_path / "modeles-absents")


def test_le_derive_ne_s_ecrit_ni_dans_l_archive_ni_autour(tmp_path: Path) -> None:
    racine = tmp_path / "archive"
    racine.mkdir()
    for derive in (racine, racine / "derive", tmp_path):
        with pytest.raises(CheminsRefuses, match="séparés"):
            resoudre(racine, derive)


def test_ni_points_ni_lien_ne_cachent_un_derive_dans_l_archive(tmp_path: Path) -> None:
    racine = tmp_path / "archive"
    racine.mkdir()
    with pytest.raises(CheminsRefuses, match="séparés"):
        resoudre(racine, tmp_path / "ailleurs" / ".." / "archive" / "derive")
    (tmp_path / "lien").symlink_to(racine, target_is_directory=True)
    with pytest.raises(CheminsRefuses, match="séparés"):
        resoudre(racine, tmp_path / "lien" / "derive")
    assert resoudre(tmp_path / "lien", tmp_path / "derive").racine == racine.resolve()


# --- verrou ------------------------------------------------------------------------------------


def test_le_verrou_ne_se_prend_pas_deux_fois(chemins: Chemins) -> None:
    with verrou(chemins.verrou), pytest.raises(VerrouTenu), verrou(chemins.verrou):
        pass
    with verrou(chemins.verrou):  # relâché à la sortie du bloc
        pass


def test_le_verrou_tombe_avec_le_processus_et_se_prend_en_lecture(chemins: Chemins) -> None:
    """Un autre processus le tient, puis meurt ; un lecteur du fichier peut le prendre (c'est ce
    que fait la bascule de version, par la commande flock, sous un compte qui ne fait que lire)."""
    chemins.verrou.parent.mkdir(parents=True)
    code = (
        "import fcntl, sys, time\n"
        f"f = open({str(chemins.verrou)!r}, 'a')\n"
        "fcntl.flock(f, fcntl.LOCK_EX)\n"
        "print('tenu', flush=True)\n"
        "time.sleep(60)\n"
    )
    autre = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
    try:
        assert autre.stdout is not None and autre.stdout.readline().strip() == b"tenu"
        with pytest.raises(VerrouTenu), verrou(chemins.verrou):
            pass
    finally:
        autre.kill()
        autre.wait()
    with (
        verrou(chemins.verrou),
        chemins.verrou.open("rb") as lecteur,
        pytest.raises(BlockingIOError),
    ):
        fcntl.flock(lecteur, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with chemins.verrou.open("rb") as lecteur:
        fcntl.flock(lecteur, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(VerrouTenu), verrou(chemins.verrou):
            pass


# --- journal -----------------------------------------------------------------------------------


def test_le_journal_ajoute_une_ligne_par_passage(chemins: Chemins) -> None:
    assert list(journal.lire(chemins.passages)) == []
    journal.ajouter(chemins.passages, {"id": "a", "résumé": "é"})
    journal.ajouter(chemins.passages, {"id": "b"})
    assert [p["id"] for p in journal.lire(chemins.passages)] == ["a", "b"]
    assert chemins.passages.read_text(encoding="utf-8").count("\n") == 2
    assert "é" in chemins.passages.read_text(encoding="utf-8")


def test_une_ligne_coupee_ne_gate_pas_la_suivante(chemins: Chemins) -> None:
    journal.ajouter(chemins.passages, {"id": "a"})
    with chemins.passages.open("a", encoding="utf-8") as fichier:
        fichier.write('{"id": "coup')  # écriture coupée par une panne
    journal.ajouter(chemins.passages, {"id": "c"})
    assert [p["id"] for p in journal.lire(chemins.passages)] == ["a", "c"]
    with chemins.passages.open("ab") as fichier:
        fichier.write(b'{"motif": "tu' + "é".encode()[:1])  # coupée dans un « é »
    journal.ajouter(chemins.passages, {"id": "d"})
    assert [p["id"] for p in journal.lire(chemins.passages)] == ["a", "c", "d"]


# --- une étape, dans un vrai sous-processus ----------------------------------------------------


def test_une_etape_est_une_commande_pharmaflux(capfdbinary: pytest.CaptureFixture[bytes]) -> None:
    resultat = etapes.lancer(Etape("version", ("--version",)))
    assert resultat.reussie and resultat.code == 0 and resultat.signal is None
    assert resultat.commande == "pharmaflux --version"
    assert resultat.resume.startswith("pharmaflux ")
    assert resultat.resident_mo is not None and resultat.resident_mo > 0
    assert resultat.duree_s >= 0 and resultat.debut <= resultat.fin
    # La sortie de l'étape passe telle quelle : c'est elle que journald garde.
    assert capfdbinary.readouterr().out.startswith(b"pharmaflux ")


def test_une_etape_en_echec_rend_son_code_et_la_fin_de_son_erreur() -> None:
    resultat = etapes.lancer(Etape("inconnue", ("commande-inconnue",)))
    assert not resultat.reussie and resultat.code == 2
    assert any("commande-inconnue" in ligne for ligne in resultat.erreur)
    assert json.dumps(resultat.en_json())  # se range tel quel dans le journal


def test_une_etape_tuee_rend_son_signal() -> None:
    python = (sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)")
    resultat = etapes.lancer(Etape("tuee", ()), prefixe=python)
    assert resultat.code is None and resultat.signal == signal.SIGKILL and not resultat.reussie


def test_une_etape_ne_garde_que_la_fin_de_sa_sortie_d_erreur() -> None:
    bavard = "import sys\nfor i in range(100): print('ligne', i, file=sys.stderr)\nprint('fin')"
    resultat = etapes.lancer(Etape("bavarde", ()), prefixe=(sys.executable, "-c", bavard))
    assert resultat.resume == "fin"
    assert len(resultat.erreur) == etapes.LIGNES_GARDEES and resultat.erreur[-1] == "ligne 99"


def test_l_environnement_passe_a_l_etape() -> None:
    lire = "import os; print(os.environ['PHARMAFLUX_MODELES'])"
    resultat = etapes.lancer(
        Etape("env", ()),
        prefixe=(sys.executable, "-c", lire),
        environnement={**os.environ, "PHARMAFLUX_MODELES": "/srv/modeles"},
    )
    assert resultat.resume == "/srv/modeles"


class _Sortie:
    """La sortie standard de la chaîne, le temps d'un test : garde la première ligne de l'étape
    (son numéro de processus) et le signale."""

    def __init__(self) -> None:
        self.lue = threading.Event()
        self.ligne = b""

    buffer = property(lambda self: self)

    def write(self, octets: bytes) -> None:
        if not self.lue.is_set():
            self.ligne = octets
            self.lue.set()

    def flush(self) -> None:
        pass


def _vivant(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.parametrize("sourde", [False, True], ids=["obeit", "ignore-sigterm"])
def test_une_interruption_arrete_l_etape_en_cours(
    sourde: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIGTERM pendant une étape (arrêt de l'unité) : l'étape est arrêtée, même si elle ignore
    le signal (elle est alors tuée après le délai), et l'interruption remonte."""
    monkeypatch.setattr(etapes, "DELAI_ARRET_S", 0.5)
    code = (
        "import os, signal, time\n"
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if sourde else "")
        + "print(os.getpid(), flush=True)\ntime.sleep(60)"
    )
    sortie, arme = _Sortie(), threading.Event()
    avant = signal.getsignal(signal.SIGTERM)

    def interrompre() -> None:
        if sortie.lue.wait(30) and arme.is_set():
            os.kill(os.getpid(), signal.SIGTERM)

    monkeypatch.setattr(sys, "stdout", sortie)
    arme.set()
    threading.Thread(target=interrompre, daemon=True).start()
    try:
        with passage._signaux(), pytest.raises(etapes.Interruption, match="SIGTERM"):
            etapes.lancer(Etape("longue", ()), prefixe=(sys.executable, "-c", code))
    finally:
        arme.clear()
    assert not _vivant(int(sortie.ligne))  # l'étape n'a pas survécu
    assert signal.getsignal(signal.SIGTERM) is avant  # le gestionnaire est rendu


def test_l_arret_atteint_ce_que_l_etape_a_lance(monkeypatch: pytest.MonkeyPatch) -> None:
    """« index construire » extrait ses fragments dans un sous-processus : l'étape est chef de
    son groupe, et l'arrêt vise le groupe."""
    monkeypatch.setattr(etapes, "DELAI_ARRET_S", 0.5)
    code = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print(p.pid, flush=True)\ntime.sleep(60)"
    )
    sortie, arme = _Sortie(), threading.Event()

    def interrompre() -> None:
        if sortie.lue.wait(30) and arme.is_set():
            os.kill(os.getpid(), signal.SIGTERM)

    monkeypatch.setattr(sys, "stdout", sortie)
    arme.set()
    threading.Thread(target=interrompre, daemon=True).start()
    try:
        with passage._signaux(), pytest.raises(etapes.Interruption):
            etapes.lancer(Etape("mere", ()), prefixe=(sys.executable, "-c", code))
    finally:
        arme.clear()
    petit_fils = int(sortie.ligne)
    for _ in range(50):  # orphelin, il est repris par init : on lui laisse le temps de finir
        if not _vivant(petit_fils):
            break
        time.sleep(0.1)
    assert not _vivant(petit_fils)


def test_une_etape_tourne_dans_son_dossier(tmp_path: Path) -> None:
    resultat = etapes.lancer(
        Etape("ou", ()),
        prefixe=(sys.executable, "-c", "import os; print(os.getcwd())"),
        dossier=tmp_path,
    )
    assert Path(resultat.resume) == tmp_path.resolve()


def test_un_descendant_qui_garde_la_sortie_ne_bloque_pas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(etapes, "DELAI_RELAIS_S", 0.3)
    code = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3)'])\nprint('fini')"
    )
    resultat = etapes.lancer(Etape("pressee", ()), prefixe=(sys.executable, "-c", code))
    assert resultat.code == 0 and resultat.duree_s < 2.5


def _groupe_factice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    groupe = tmp_path / "groupe"
    groupe.mkdir()
    monkeypatch.setattr(etapes, "_groupe", lambda: groupe)
    return groupe


def test_les_releves_du_groupe_de_controle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Les fichiers du noyau (cgroup v2), dans leur format : c'est de là que viennent les mesures
    citées depuis le VPS. Hors de Linux, ou fichier absent : None, jamais une erreur."""
    groupe = _groupe_factice(tmp_path, monkeypatch)
    assert etapes.pic_groupe_mo() is None and etapes.partage_groupe_mo() is None
    assert etapes.morts_par_memoire() is None
    # 530 Mio : 555 « Mo » décimaux, qui paraîtraient dépasser MemoryMax=512M.
    (groupe / "memory.peak").write_text(f"{530 * 2**20}\n", encoding="ascii")
    (groupe / "memory.stat").write_text(
        f"anon 1000\nfile 2000\nshmem {12 * 2**20 + 2**20 - 1}\ninactive_file 5\n",
        encoding="ascii",
    )
    (groupe / "memory.events").write_text(
        "low 0\nhigh 0\nmax 7\noom 3\noom_kill 2\noom_group_kill 0\n", encoding="ascii"
    )
    assert etapes.pic_groupe_mo() == 530
    assert etapes.partage_groupe_mo() == 12  # arrondi vers le bas, comme le reste
    assert etapes.morts_par_memoire() == 2


def test_un_mo_de_la_chaine_est_l_unite_de_memorymax(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """« MemoryMax=512M » compte en puissances de deux : un groupe au plafond se lit 512, pas
    536 ; le résident du plus gros processus suit la même unité, sous Linux comme sur macOS."""
    assert etapes.OCTETS_PAR_MO == 1_048_576
    groupe = _groupe_factice(tmp_path, monkeypatch)
    (groupe / "memory.peak").write_text(f"{512 * 2**20}\n", encoding="ascii")
    assert etapes.pic_groupe_mo() == 512

    class Usage:
        ru_maxrss = 0

    monkeypatch.setattr(sys, "platform", "linux")
    Usage.ru_maxrss = 512 * 1024  # Ko sous Linux
    assert etapes._resident_mo(Usage()) == 512
    monkeypatch.setattr(sys, "platform", "darwin")
    Usage.ru_maxrss = 512 * 2**20  # octets sur macOS
    assert etapes._resident_mo(Usage()) == 512


# --- le remplissage ----------------------------------------------------------------------------

ETAPES = [
    "modele",
    "pages-has",
    "evenements",
    "schemas",
    "publier",
    "verifier-bus",
    "silver",
    "silver-verifier",
    "index",
    "index-verifier",
    "index-etat",
]


def test_le_plan_du_remplissage(chemins: Chemins) -> None:
    """Le plan entier, argument par argument : une option retirée (--verifier, --racine,
    --complet, --archive-has) laisserait chaque commande rendre 0 sans rien vérifier."""
    a, d = str(chemins.racine), chemins.derive
    ev, lac = str(d / "evenements"), str(d / "lakehouse")
    index = ("--entrepot", lac, "--travail", str(d / "index"), "--modele", "e5-small-int8")
    index += ("--archive-has", a)
    assert [(e.nom, e.arguments, e.services) for e in remplissage.plan(chemins)] == [
        ("modele", ("index", "modele", "verifier", "e5-small-int8"), ()),
        ("pages-has", ("has", "extraire", "--verifier", "--racine", a), ()),
        ("evenements", ("evenements", "--reprendre", "--racine", a, "--sortie", ev), ()),
        ("schemas", ("schemas", "enregistrer"), ("registre",)),
        ("publier", ("publier", "--reprendre", "--sortie", ev), ("courtier", "registre")),
        ("verifier-bus", ("verifier-bus", "--racine", a, "--sortie", ev), ("courtier",)),
        ("silver", ("silver", "consommer", "--entrepot", lac), ("courtier",)),
        (
            "silver-verifier",
            ("silver", "verifier", "--entrepot", lac, "--sortie", ev, "--racine", a),
            (),
        ),
        ("index", ("index", "construire", *index), ("qdrant",)),
        ("index-verifier", ("index", "verifier", *index), ("qdrant",)),
        ("index-etat", ("index", "etat", "--complet"), ("qdrant",)),
    ]
    # L'encodeur de test n'a pas de fichier épinglé à vérifier.
    assert [e.nom for e in remplissage.plan(chemins, "test")] == ETAPES[1:]


def test_chaque_etape_du_plan_est_une_commande_qui_existe(chemins: Chemins) -> None:
    """Le plan ne nomme que des commandes et des options que la ligne de commande connaît :
    click analyse les arguments de chaque étape, sans rien exécuter."""
    for etape in remplissage.plan(chemins):
        commande, reste = commande_cli(etape.arguments)
        assert not hasattr(commande, "commands"), etape  # une commande, pas un groupe
        assert commande.name == etape.arguments[len(etape.arguments) - len(reste) - 1]
        commande.make_context(etape.nom, reste)  # lève sur une option inconnue


def test_un_remplissage_complet(chemins: Chemins, simulation: Simulation) -> None:
    lignes: list[str] = []
    code = passage.derouler("remplissage", remplissage.plan(chemins), chemins, ecrire=lignes.append)
    assert code == 0
    assert simulation.lancees == ETAPES
    assert simulation.sondes == [
        "registre",  # schemas
        "courtier",  # publier
        "registre",
        "courtier",  # verifier-bus
        "courtier",  # silver
        "qdrant",  # index
        "qdrant",  # index-verifier
        "qdrant",  # index-etat
    ]
    assert simulation.environnement["PYTHONUNBUFFERED"] == "1"
    assert chemins.tmp == chemins.derive / "tmp" and chemins.tmp.is_dir()  # TMPDIR de l'unité
    assert simulation.dossier == chemins.tmp  # le dossier courant des étapes
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["genre"] == "remplissage" and consigne["issue"] == "complet"
    assert consigne["code"] == 0 and consigne["arret"] is None
    assert [e["nom"] for e in consigne["etapes"]] == ETAPES and consigne["non_lancees"] == []
    assert consigne["debut"] <= consigne["fin"]
    assert lignes[0] == "remplissage : étape 1/11, modele"
    assert lignes[-1].startswith("remplissage : complet, 11 étape(s)")


def test_le_dossier_des_modeles_passe_aux_etapes(tmp_path: Path, simulation: Simulation) -> None:
    racine, modeles = tmp_path / "archive", tmp_path / "modeles"
    racine.mkdir()
    modeles.mkdir()
    chemins = resoudre(racine, tmp_path / "derive", modeles)
    passage.derouler("remplissage", remplissage.plan(chemins), chemins, ecrire=lambda _: None)
    assert simulation.environnement["PHARMAFLUX_MODELES"] == str(modeles)


@pytest.mark.parametrize(
    ("code_etape", "code_attendu", "motif"),
    [(1, 1, "code 1"), (2, 2, "code 2"), (3, 1, "code 3"), (None, 1, "tuée par le signal 9")],
)
def test_le_remplissage_s_arrete_a_la_premiere_etape_en_echec(
    chemins: Chemins,
    simulation: Simulation,
    code_etape: int | None,
    code_attendu: int,
    motif: str,
) -> None:
    simulation.codes["publier"] = code_etape
    lignes: list[str] = []
    code = passage.derouler("remplissage", remplissage.plan(chemins), chemins, ecrire=lignes.append)
    assert code == code_attendu
    assert simulation.lancees == ETAPES[:5]  # rien après publier
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["issue"] == "arrete" and consigne["code"] == code_attendu
    assert consigne["arret"] == {"etape": "publier", "motif": motif}
    assert consigne["non_lancees"] == ETAPES[5:]
    assert lignes[-1] == f"remplissage : arrêté à l'étape publier ({motif})"


def test_un_service_qui_ne_repond_pas_arrete_avant_de_lancer(
    chemins: Chemins, simulation: Simulation
) -> None:
    """Qdrant injoignable donnerait le code 2 d'un refus : la sonde le classe en panne (1), et
    l'étape n'est pas lancée."""
    simulation.pannes["qdrant"] = "http://127.0.0.1:16333/readyz : ConnectError"
    code = passage.derouler(
        "remplissage", remplissage.plan(chemins), chemins, ecrire=lambda _: None
    )
    assert code == 1
    assert simulation.lancees == ETAPES[:8]  # jusqu'à silver-verifier ; l'index n'est pas lancé
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["arret"]["etape"] == "index"
    assert consigne["arret"]["motif"].startswith("qdrant injoignable (")
    assert consigne["non_lancees"] == ETAPES[8:]


@pytest.mark.usefixtures("simulation")
def test_un_passage_interrompu_est_consigne(
    chemins: Chemins, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrompu(etape: Etape, **_: object) -> Resultat:
        if etape.nom == "silver":
            raise etapes.Interruption("SIGTERM")
        return _resultat(etape)

    monkeypatch.setattr(etapes, "lancer", interrompu)
    code = passage.derouler(
        "remplissage", remplissage.plan(chemins), chemins, ecrire=lambda _: None
    )
    assert code == 1
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["issue"] == "interrompu"
    assert consigne["arret"] == {"etape": "silver", "motif": "passage interrompu (SIGTERM)"}
    assert [e["nom"] for e in consigne["etapes"]][-1] == "verifier-bus"
    assert (
        consigne["non_lancees"][0] == "silver-verifier"
    )  # silver, coupée, n'est ni l'un ni l'autre


def test_une_etape_tuee_par_le_plafond_est_une_panne_meme_si_elle_rend_2(
    chemins: Chemins, simulation: Simulation, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """« index construire » rend 2 quand son sous-processus meurt. Le compteur du noyau, relevé
    avant et après l'étape, dit que c'est le plafond : code 1, pas un refus."""
    groupe = _groupe_factice(tmp_path, monkeypatch)
    evenements = groupe / "memory.events"
    evenements.write_text("oom_kill 0\n", encoding="ascii")
    simulation.codes["index"] = 2
    vrai = simulation._lancer

    def lancer(etape: Etape, **options: object) -> Resultat:
        if etape.nom == "index":
            evenements.write_text("oom_kill 1\n", encoding="ascii")
        return vrai(etape, **options)  # type: ignore[arg-type]

    monkeypatch.setattr(etapes, "lancer", lancer)
    code = passage.derouler(
        "remplissage", remplissage.plan(chemins), chemins, ecrire=lambda _: None
    )
    assert code == 1
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["arret"]["motif"] == "code 2, un processus tué par le plafond de mémoire"
    assert consigne["morts_par_memoire"] == 1


@pytest.mark.usefixtures("simulation")
def test_une_erreur_imprevue_laisse_quand_meme_une_ligne(
    chemins: Chemins, monkeypatch: pytest.MonkeyPatch
) -> None:
    def casse(etape: Etape, **_: object) -> Resultat:
        if etape.nom == "evenements":
            raise OSError("fork refusé")
        return _resultat(etape)

    monkeypatch.setattr(etapes, "lancer", casse)
    code = passage.derouler(
        "remplissage", remplissage.plan(chemins), chemins, ecrire=lambda _: None
    )
    assert code == 1
    (consigne,) = journal.lire(chemins.passages)
    assert consigne["issue"] == "arrete"
    assert consigne["arret"] == {"etape": "evenements", "motif": "OSError : fork refusé"}


def test_le_dossier_temporaire_est_vide_au_depart(chemins: Chemins, simulation: Simulation) -> None:
    chemins.tmp.mkdir(parents=True)
    (chemins.tmp / "reste-d-une-etape-tuee").write_text("x", encoding="ascii")
    passage.derouler("remplissage", remplissage.plan(chemins), chemins, ecrire=lambda _: None)
    assert simulation.lancees and list(chemins.tmp.iterdir()) == []


def test_le_verrou_tenu_ne_lance_rien(chemins: Chemins, simulation: Simulation) -> None:
    with verrou(chemins.verrou), pytest.raises(VerrouTenu):
        passage.derouler("remplissage", remplissage.plan(chemins), chemins, ecrire=lambda _: None)
    assert simulation.lancees == [] and not chemins.passages.exists()


def test_le_commit_du_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``VERSION`` porte le commit après ``git archive`` ; dans un clone, sa marque, donc rien."""
    version = tmp_path / "versions" / "abc"
    (version / ".venv").mkdir(parents=True)
    monkeypatch.setattr(sys, "prefix", str(version / ".venv"))
    assert passage.commit_du_code() is None  # pas de fichier
    (version / "VERSION").write_text("$Format:%H$\n", encoding="ascii")
    assert passage.commit_du_code() is None  # un clone de travail : la marque, pas un commit
    (version / "VERSION").write_text("0123456789abcdef0123456789abcdef01234567\n", encoding="ascii")
    assert passage.commit_du_code() == "0123456789abcdef0123456789abcdef01234567"


def test_version_est_marque_pour_git_archive() -> None:
    assert Path("VERSION").read_text(encoding="ascii") == "$Format:%H$\n"
    attributs = Path(".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "VERSION export-subst" in attributs


# --- la commande -------------------------------------------------------------------------------


def test_chaine_remplir(tmp_path: Path, simulation: Simulation) -> None:
    racine, derive = tmp_path / "archive", tmp_path / "derive"
    racine.mkdir()
    resultat = lanceur.invoke(
        cli.application, ["chaine", "remplir", "--racine", str(racine), "--derive", str(derive)]
    )
    assert resultat.exit_code == 0, resultat.output
    assert simulation.lancees == ETAPES
    assert "remplissage : complet, 11 étape(s)" in resultat.output
    assert len(list(journal.lire(derive / "chaine" / "passages.jsonl"))) == 1


def test_chaine_remplir_lit_la_variable_du_derive(
    tmp_path: Path, simulation: Simulation, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine, derive = tmp_path / "archive", tmp_path / "derive"
    racine.mkdir()
    monkeypatch.setenv("PHARMAFLUX_DATA", str(racine))
    monkeypatch.setenv("PHARMAFLUX_DERIVE", str(derive))
    resultat = lanceur.invoke(cli.application, ["chaine", "remplir", "--modele", "test"])
    assert resultat.exit_code == 0, resultat.output
    assert simulation.lancees == ETAPES[1:]


def test_chaine_remplir_refuse(tmp_path: Path, simulation: Simulation) -> None:
    racine, derive = tmp_path / "archive", tmp_path / "derive"
    racine.mkdir()
    sans_derive = lanceur.invoke(cli.application, ["chaine", "remplir", "--racine", str(racine)])
    assert sans_derive.exit_code == 2
    assert "remplissage refusé : le dossier du dérivé manque" in texte_nu(sans_derive.output)
    arguments = ["chaine", "remplir", "--racine", str(racine), "--derive", str(derive)]
    with verrou(derive / "chaine" / "verrou"):
        tenu = lanceur.invoke(cli.application, arguments)
    assert tenu.exit_code == 2
    assert "remplissage refusé : une autre commande de la chaîne tourne" in texte_nu(tenu.output)
    assert simulation.lancees == []


def test_chaine_remplir_rend_le_code_de_l_arret(tmp_path: Path, simulation: Simulation) -> None:
    racine, derive = tmp_path / "archive", tmp_path / "derive"
    racine.mkdir()
    simulation.codes["index-verifier"] = 1
    resultat = lanceur.invoke(
        cli.application, ["chaine", "remplir", "--racine", str(racine), "--derive", str(derive)]
    )
    assert resultat.exit_code == 1
    assert "arrêté à l'étape index-verifier (code 1)" in resultat.output


# --- les sondes --------------------------------------------------------------------------------


def test_une_sonde_reessaie_puis_rend_la_raison(monkeypatch: pytest.MonkeyPatch) -> None:
    reponses = iter(["panne", "panne", None])
    pauses: list[float] = []
    monkeypatch.setattr(sante, "_une_fois", lambda _service: next(reponses))
    assert sante.sonder(sante.QDRANT, dormir=pauses.append) is None
    assert pauses == [sante.PAUSE_S, sante.PAUSE_S]
    monkeypatch.setattr(sante, "_une_fois", lambda _service: "toujours en panne")
    pauses.clear()
    assert sante.sonder(sante.QDRANT, dormir=pauses.append) == "toujours en panne"
    assert len(pauses) == sante.ESSAIS - 1


def test_les_adresses_des_sondes_sont_celles_des_commandes(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("PHARMAFLUX_COURTIER", "PHARMAFLUX_REGISTRE", "PHARMAFLUX_QDRANT"):
        monkeypatch.delenv(variable, raising=False)
    assert sante.adresse(sante.COURTIER) == "127.0.0.1:19092"
    assert sante.adresse(sante.REGISTRE) == "http://127.0.0.1:18081"
    assert sante.adresse(sante.QDRANT) == "http://127.0.0.1:16333"
    monkeypatch.setenv("PHARMAFLUX_QDRANT", "http://127.0.0.1:26333")
    assert sante.adresse(sante.QDRANT) == "http://127.0.0.1:26333"


def test_chaque_service_est_sonde_a_son_adresse(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("PHARMAFLUX_COURTIER", "PHARMAFLUX_REGISTRE", "PHARMAFLUX_QDRANT"):
        monkeypatch.delenv(variable, raising=False)
    sondes: list[str] = []
    monkeypatch.setattr(sante, "_http", lambda url: sondes.append(url))
    monkeypatch.setattr(sante, "_courtier", lambda cible: sondes.append(cible))
    for service in (sante.COURTIER, sante.REGISTRE, sante.QDRANT):
        assert sante._une_fois(service) is None
    assert sondes == [
        "127.0.0.1:19092",
        "http://127.0.0.1:18081/subjects",
        "http://127.0.0.1:16333/readyz",
    ]


def test_une_adresse_mal_ecrite_est_une_panne_pas_une_trace() -> None:
    assert sante._http("http://[::1/readyz") is not None


def test_un_courtier_absent_rend_une_raison(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une vraie tentative, vers cette machine, sur un port que rien n'écoute."""
    monkeypatch.setattr(sante, "DELAI_S", 1.0)
    raison = sante._courtier("127.0.0.1:9")
    assert raison is not None and raison.startswith("127.0.0.1:9 : ")


def test_une_sonde_http_sur_un_port_ferme_rend_une_raison() -> None:
    """Une vraie connexion, vers cette machine, sur un port que rien n'écoute."""
    raison = sante._http("http://127.0.0.1:9/readyz")
    assert raison is not None and raison.startswith("http://127.0.0.1:9/readyz : ")
