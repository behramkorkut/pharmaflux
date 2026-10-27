"""Mission 04, palier 2 : le rejeu accéléré sur le bus simulé de la mission 03, sans dormir.

L'horloge et le sommeil sont injectés : les instants visés se vérifient à la
seconde près sans attendre. Le bronze est celui de ``test_rejeu`` (deux
entités), ou un bronze à trois entités et sept archives entrelacées pour
l'ordre global.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import publication, verification
from pharmaflux.bus.registre import Registre
from pharmaflux.cli import application
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.demo import rejeu_accelere
from pharmaflux.demo.rejeu_accelere import DemoRefusee, Resume, executer
from pharmaflux.evenements import rejeu
from tests.test_bus import DISPO, PRESENTATIONS, BusSimule, RegistreSimule, _registre_pret
from tests.test_bus_verification import BusCoupe, LecteurSimule
from tests.test_rejeu import SUITE, T0, Collecte, peupler

SPECIALITES = "bdpm.specialites"
TROIS_ENTITES = [PRESENTATIONS, SPECIALITES, DISPO]
# Trois entités, sept archives entrelacées, un passage où seule la disponibilité est revue.
TROIS = (
    Collecte(PRESENTATIONS, 0, "presentations_a.txt", "2026-10-24"),
    Collecte(SPECIALITES, 0.05, "bdpm/CIS_bdpm.txt", "2026-10-24"),
    Collecte(DISPO, 0.1, "dispo_a.txt"),
    Collecte(DISPO, 1.0, None),
    Collecte(PRESENTATIONS, 2, "presentations_b.txt", "2026-10-24"),
    Collecte(DISPO, 2.1, "dispo_b.txt"),  # perd une ligne sur sept : en attente, puis écartée
    Collecte(PRESENTATIONS, 3, "presentations_vide.txt"),  # écarté : vide
    Collecte(DISPO, 3.1, "dispo_triple.txt"),  # écarte B, retenu
)
FICHIERS_PUBLIES = 5  # présentations A et B, spécialités, disponibilité A et triple


@dataclass
class Horloge:
    """Un temps monotone simulé : ``dormir`` l'avance, et note chaque pause."""

    t: float = 0.0
    pauses: list[float] = field(default_factory=list)

    def maintenant(self) -> float:
        return self.t

    def dormir(self, duree: float) -> None:
        assert duree > 0, "jamais de pause nulle ou négative"
        self.pauses.append(duree)
        self.t += duree


@dataclass
class BusLent(BusSimule):
    """Chaque attente d'accusés de réception prend dix secondes de l'horloge simulée."""

    horloge: Horloge = field(default_factory=Horloge)

    def attendre(self, delai_s: float) -> int:
        self.horloge.t += 10
        return super().attendre(delai_s)


def _contexte(
    tmp_path: Path, suite: tuple[Collecte, ...] = TROIS, entites: list[str] = TROIS_ENTITES
) -> tuple[Path, Path, BusSimule, Registre]:
    racine = tmp_path / "archive"
    peupler(racine, suite)
    _, registre = _registre_pret(tuple(entites))
    return racine, tmp_path / "demo", BusSimule(), registre


def _rejouer(
    racine: Path,
    sortie: Path,
    bus: BusSimule,
    registre: Registre,
    entites: list[str] = TROIS_ENTITES,
    horloge: Horloge | None = None,
    **options: object,
) -> tuple[Resume, list[str]]:
    lignes: list[str] = []
    cadence = (
        {"sans_pause": True}
        if horloge is None
        else {"maintenant": horloge.maintenant, "dormir": horloge.dormir}
    )
    resume = executer(
        racine,
        sortie,
        charger_tous(),
        entites,
        bus,
        registre,
        journal=lignes.append,
        **cadence,  # type: ignore[arg-type]
        **options,  # type: ignore[arg-type]
    )
    return resume, lignes


def _instant(heures: float) -> str:
    return f"{T0 + timedelta(hours=heures):%d/%m %H:%M:%S}"


def test_ordre_global_entrelace_et_meme_ordre_par_topic_que_publier(tmp_path: Path) -> None:
    racine, sortie, bus, registre = _contexte(tmp_path)
    resume, lignes = _rejouer(racine, sortie, bus, registre)
    assert lignes[0].startswith(f"rejeu de {racine} : 7 archive(s) lue(s) pour 3 entité(s)")
    deroule = lignes[1:]
    assert [ligne[:16].rstrip() for ligne in deroule] == [
        _instant(0), _instant(0.05), _instant(0.1), f"{T0 + timedelta(hours=1):%d/%m %H:%M}",
        _instant(2), _instant(2.1), _instant(3), _instant(3.1),
    ], "l'ordre global : par horodatage, toutes entités confondues"  # fmt: skip
    topic_pres = env.nom_topic(PRESENTATIONS)
    assert deroule[0].startswith(f"{_instant(0)}  {PRESENTATIONS:28} état initial : creee 17 → ")
    assert f"→ {topic_pres} (17 message(s), " in deroule[0]
    assert "passage                      1 fichier(s) revu(s) sans changement" in deroule[3]
    assert "supprimee 1, modifiee 1, creee 1" not in deroule[4], "types triés par nom"
    assert "creee 1, modifiee 1, supprimee 1 → " in deroule[4]
    assert deroule[1].startswith(f"{_instant(0.05)}  {SPECIALITES:28} état initial : creee ")
    assert deroule[5].startswith(f"{_instant(2.1)}  {DISPO:28} snapshot écarté : "), (
        "le bilan de l'archive en attente a été réécrit par l'archive suivante"
    )
    assert deroule[5].endswith("(rien publié)")
    assert "snapshot écarté : vide" in deroule[6] and deroule[6].endswith("(rien publié)")
    assert deroule[7].startswith(f"{_instant(3.1)}  {DISPO:28} creee 1 → ")
    assert (resume.archives, resume.publies, resume.deja_publies) == (7, FICHIERS_PUBLIES, 0)
    assert (resume.ecartees, resume.en_attente, resume.passages) == (2, 0, 1)
    assert resume.premiere_observation == T0 and resume.derniere_observation == T0 + timedelta(
        hours=3.1
    )
    assert resume.code_sortie == 0 and resume.echecs == 0
    assert set(resume.messages) == {env.nom_topic(e) for e in TROIS_ENTITES}

    # Le même ordre par topic que « publier » sur la même sortie, à l'enveloppe près.
    temoin = tmp_path / "temoin"
    rejeu.executer(racine, temoin, charger_tous(), TROIS_ENTITES)
    bus_temoin = BusSimule()
    publication.executer(temoin, bus_temoin, registre)
    assert bus.messages == bus_temoin.messages
    assert json.loads((sortie / publication.NOM_PUBLICATION).read_text()) == json.loads(
        (temoin / publication.NOM_PUBLICATION).read_text()
    )
    rapport = verification.verifier(
        LecteurSimule(bus),
        TROIS_ENTITES,
        verification.reference_fichiers(sortie),
        description_reference="fichiers",
    )
    assert rapport.code_sortie == 0, [t.differences for t in rapport.topics]
    lignes_resume = rejeu_accelere.formater_resume(resume)
    assert lignes_resume[0] == (
        "rejeu : 7 archive(s) déroulée(s), 5 fichier(s) publié(s) (0 déjà), 2 écartée(s),"
        " 0 en attente, 1 passage(s) sans archive"
    )
    assert any(
        "observé : du 24/10 14:17:00 au 24/10 17:23:00 (3 h 06 min)" in ligne
        for ligne in lignes_resume
    )


def test_la_cadence_divise_les_ecarts_observes_par_le_facteur(tmp_path: Path) -> None:
    racine, sortie, bus, registre = _contexte(tmp_path)
    horloge = Horloge()
    resume, _ = _rejouer(racine, sortie, bus, registre, horloge=horloge, facteur=1000)
    # Écarts observés entre entrées successives : 3 min, 3 min, 54 min, 1 h, 6 min, 54 min, 6 min.
    assert horloge.pauses == pytest.approx([0.18, 0.18, 3.24, 3.6, 0.36, 3.24, 0.36])
    assert resume.duree_reelle_s == pytest.approx(11.16), "3 h 06 observées en 11,16 s"
    assert resume.facteur == 1000

    # Au facteur 100, tout est dix fois plus long ; les passages tus ne font plus d'entrée.
    shutil.rmtree(sortie)
    horloge, bus = Horloge(), BusSimule()
    _rejouer(racine, sortie, bus, registre, horloge=horloge, facteur=100, sans_passages=True)
    assert horloge.pauses == pytest.approx([1.8, 1.8, 68.4, 3.6, 32.4, 3.6])

    # Une publication plus longue que les pauses : aucune pause négative, l'horloge rattrape.
    shutil.rmtree(sortie)
    horloge = Horloge()
    lent = BusLent(horloge=horloge)
    resume, _ = _rejouer(racine, sortie, lent, registre, horloge=horloge)
    assert horloge.pauses == [], "après la première publication (10 s), l'horloge ne rattrape plus"
    assert resume.duree_reelle_s == 10 * FICHIERS_PUBLIES

    # Sans pause : jamais de sommeil, quelle que soit l'horloge.
    shutil.rmtree(sortie)
    horloge, bus = Horloge(), BusSimule()
    executer(
        racine, sortie, charger_tous(), TROIS_ENTITES, bus, registre,
        sans_pause=True, maintenant=horloge.maintenant, dormir=horloge.dormir,
    )  # fmt: skip
    assert horloge.pauses == []
    with pytest.raises(ValueError, match="strictement positif"):
        executer(racine, sortie, charger_tous(), TROIS_ENTITES, bus, registre, facteur=0)


def test_refus_d_un_bus_inattendu_avant_toute_publication(tmp_path: Path) -> None:
    racine, sortie, bus, registre = _contexte(tmp_path)
    # Bus non vide (un topic du projet), pas d'état : refus, avec et sans --reprendre, et la
    # sortie n'est même pas créée (le rejeu des événements n'a pas tourné).
    bus.preparer_topics([publication.definition_evenements(env.nom_topic("bdpm.x"))])
    for reprendre in (False, True):
        with pytest.raises(DemoRefusee, match=r"bus non vide sans état.*make rebatir"):
            _rejouer(racine, sortie, bus, registre, reprendre=reprendre)
        assert not sortie.exists()
    # Un topic d'un autre projet ne compte pas.
    bus = BusSimule()
    bus.preparer_topics([publication.definition_evenements("autre.bdpm.x.v1")])
    resume, _ = _rejouer(racine, sortie, bus, registre)
    assert resume.publies == FICHIERS_PUBLIES
    # Bus publié, état présent : refus sans --reprendre, « rien à rejouer » avec.
    with pytest.raises(DemoRefusee, match=r"le bus a déjà reçu une publication.*make rebatir"):
        _rejouer(racine, sortie, bus, registre)
    resume, lignes = _rejouer(racine, sortie, bus, registre, reprendre=True)
    assert (resume.publies, resume.deja_publies, resume.archives) == (0, FICHIERS_PUBLIES, 0)
    assert lignes[-1] == "rien à rejouer : tous les fichiers sont dans l'état"
    assert sum(len(m) for m in bus.messages.values()) == sum(resume_messages(bus))
    # État sans bus : refus, sortie conseillée à supprimer.
    for reprendre in (False, True):
        with pytest.raises(DemoRefusee, match=r"état sans bus.*make rebatir"):
            _rejouer(racine, sortie, BusSimule(), registre, reprendre=reprendre)
    # État illisible : le refus de « publier », code 2 lui aussi.
    (sortie / publication.NOM_PUBLICATION).write_text("{", encoding="utf-8")
    with pytest.raises(publication.PublicationRefusee, match="état illisible"):
        _rejouer(racine, sortie, bus, registre, reprendre=True)


def resume_messages(bus: BusSimule) -> list[int]:
    return [len(m) for m in bus.messages.values()]


def test_reprise_apres_une_coupure_puis_refus_d_un_fichier_hors_d_ordre(tmp_path: Path) -> None:
    racine, sortie, bus, registre = _contexte(tmp_path)
    coupe = BusCoupe(bus, apres=2)  # le troisième fichier publié (disponibilité A) est coupé
    with pytest.raises(publication.LivraisonEchouee):
        _rejouer(racine, sortie, coupe, registre)
    etat = publication.lire_etat(sortie / publication.NOM_PUBLICATION)
    assert sum(len(p) for p in etat.values()) == 2 and DISPO not in etat
    resume, lignes = _rejouer(racine, sortie, bus, registre, reprendre=True)
    assert (resume.publies, resume.deja_publies) == (3, 2)
    assert lignes[1].startswith(f"{_instant(0.1)}  {DISPO:28} état initial : creee "), (
        "la reprise repart du fichier coupé, en entier"
    )
    assert (resume.archives, resume.passages) == (5, 1), "rien de ce qui précède n'est rejoué"
    rapport = verification.verifier(
        LecteurSimule(bus),
        TROIS_ENTITES,
        verification.reference_fichiers(sortie),
        description_reference="fichiers",
    )
    assert rapport.code_sortie == 0 and rapport.doublons > 0
    dispo = next(t for t in rapport.topics if t.entite == DISPO)
    assert list(dispo.doublons_par_fichier) == [f"evenements/{DISPO}/" + sorted(
        p.name for p in (sortie / "evenements" / DISPO).glob("*.jsonl")
    )[0]], "les doublons viennent tous du fichier coupé puis republié"  # fmt: skip

    # Un fichier copié à la main sous un nom qui se range avant le dernier publié : refus avant
    # le premier message, par le module et par la commande « demo rejouer --reprendre ».
    dossier = sortie / "evenements" / PRESENTATIONS
    dernier = sorted(dossier.glob("*.jsonl"))[-1]
    shutil.copyfile(dernier, dossier / "20261024T000000Z__000000000000.jsonl")
    avant = resume_messages(bus)
    with pytest.raises(publication.PublicationRefusee, match="se range avant le dernier fichier"):
        _rejouer(racine, sortie, bus, registre, reprendre=True)
    assert resume_messages(bus) == avant


def test_commande_demo_rejouer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    racine = tmp_path / "archive"
    peupler(racine, SUITE)
    sortie = tmp_path / "demo"
    simule, bus = RegistreSimule(), BusSimule()
    monkeypatch.setattr(cli, "fabriquer_transport_registre", simule.transport)
    monkeypatch.setattr(cli, "fabriquer_bus", lambda _courtier: bus)
    lanceur = CliRunner()
    base = ["demo", "rejouer", "--racine", str(racine), "--sortie", str(sortie), "--sans-pause"]
    pour_deux = ["--fichier", PRESENTATIONS, "--fichier", "CIS_CIP_Dispo_Spec.txt"]
    # Sans schéma enregistré : refus, code 2, le conseil, et rien n'est écrit.
    refus = lanceur.invoke(application, base + pour_deux)
    assert refus.exit_code == 2 and "schemas enregistrer" in refus.output, refus.output
    assert not sortie.exists()
    assert lanceur.invoke(application, ["schemas", "enregistrer"]).exit_code == 0
    sous_racine = lanceur.invoke(
        application, ["demo", "rejouer", "--racine", str(racine), "--sortie", str(racine / "x")]
    )
    assert sous_racine.exit_code == 2 and "sous la racine" in sous_racine.output
    nul = lanceur.invoke(application, [*base, "--facteur", "0"])
    assert nul.exit_code == 2 and "strictement positif" in nul.output

    resultat = lanceur.invoke(application, base + pour_deux)
    assert resultat.exit_code == 0, resultat.output
    lignes = resultat.output.splitlines()
    assert lignes[0].startswith(f"rejeu de {racine} : 22 archive(s) lue(s) pour 2 entité(s)")
    assert lignes[1].startswith(
        "24/10 14:17:00  bdpm.presentations           état initial : creee 17"
    )
    assert "→ pharmaflux.bdpm.presentations.v1 (17 message(s), " in lignes[1]
    assert sum(ligne[16:].startswith("passage ") for ligne in lignes) == 2, (
        "deux passages inchangés"
    )
    assert "rejeu : 22 archive(s) déroulée(s), 15 fichier(s) publié(s) (0 déjà)" in resultat.output
    assert "  pharmaflux.bdpm.presentations.v1 : 80 message(s)" in resultat.output
    assert "; facteur 1000" in resultat.output and "état : " in resultat.output
    assert f"{sortie / publication.NOM_PUBLICATION}" in resultat.output

    encore = lanceur.invoke(application, base + pour_deux)
    assert encore.exit_code == 2, encore.output
    assert "démo refusée : le bus a déjà reçu une publication" in encore.output
    assert "make rebatir" in encore.output
    reprise = lanceur.invoke(application, base + pour_deux + ["--reprendre"])
    assert reprise.exit_code == 0 and "rien à rejouer" in reprise.output, reprise.output
    assert "(15 déjà)" in reprise.output

    # Un fichier hors d'ordre copié à la main : « demo rejouer --reprendre » refuse, code 2.
    dossier = sortie / "evenements" / PRESENTATIONS
    shutil.copyfile(
        sorted(dossier.glob("*.jsonl"))[-1], dossier / "20261024T000000Z__000000000000.jsonl"
    )
    hors_d_ordre = lanceur.invoke(application, base + pour_deux + ["--reprendre"])
    assert hors_d_ordre.exit_code == 2, hors_d_ordre.output
    assert (
        "démo refusée : bdpm.presentations : 20261024T000000Z__000000000000.jsonl se range avant"
        in (hors_d_ordre.output)
    )

    # Courtier arrêté : code 1.
    monkeypatch.setattr(cli, "fabriquer_bus", lambda _courtier: BusSimule(injoignable=True))
    arrete = lanceur.invoke(application, base + pour_deux)
    assert arrete.exit_code == 1 and "démo interrompue : aucun courtier" in arrete.output
