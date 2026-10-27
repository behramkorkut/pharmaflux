"""Mission 03, décisions 5, 6 et 8 : ``verifier-bus`` sur un bus en mémoire, sans Docker.

Le lecteur simulé relit le ``BusSimule`` de ``test_bus`` ; le ``BusCoupe``
interrompt une publication pendant un fichier donné, ses messages partis et
l'accusé de réception jamais rendu : le cas de la coupure suivie de
``--reprendre``. Les mêmes scénarios tournent contre le vrai courtier dans
``test_bus_integration``.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from pharmaflux.bus import publication, verification
from pharmaflux.bus.client import (
    CONFIG_ECHECS,
    CONFIG_EVENEMENTS,
    DELAI_COURTIER_S,
    Bus,
    DefinitionTopic,
    EtatTopic,
    MessageLu,
    Rappel,
)
from pharmaflux.bus.enveloppe import Enveloppe
from pharmaflux.contrats.chargeur import charger_tous
from tests.test_bus import DISPO, PRESENTATIONS, BusSimule, _registre_pret, _sortie
from tests.test_rejeu import SUITE, _executer, peupler

ENTITES = [PRESENTATIONS, DISPO]
TOPIC_PRESENTATIONS = "pharmaflux.bdpm.presentations.v1"
CONFIGURATION_ATTENDUE = dict(CONFIG_EVENEMENTS)  # rétention -1/-1, delete, CreateTime


class LecteurSimule:
    """Relit le ``BusSimule`` : une seule partition, l'ordre d'arrivée."""

    def __init__(self, bus: BusSimule) -> None:
        self.bus = bus

    def decrire_topic(self, nom: str) -> EtatTopic | None:
        definition = self.bus.topics.get(nom)
        if definition is None:
            return None
        return EtatTopic(nom, definition.partitions, dict(definition.configuration))

    def lire(self, nom: str) -> Iterator[MessageLu]:
        for offset, e in enumerate(self.bus.messages.get(nom, [])):
            yield MessageLu(nom, 0, offset, e.cle, e.valeur, dict(e.en_tetes), e.horodatage_ms)


@dataclass
class BusCoupe:
    """Coupe la publication pendant le fichier numéro ``apres`` + 1.

    Ses messages partent sur le courtier, mais l'attente des accusés rend un
    message de plus que prévu : ``LivraisonEchouee``, et l'état n'avance pas.
    """

    bus: Bus
    apres: int
    fichiers: int = 0

    def verifier_courtier(self, delai_s: float = DELAI_COURTIER_S) -> list[str]:
        return self.bus.verifier_courtier(delai_s)

    def preparer_topics(self, definitions: list[DefinitionTopic]) -> None:
        self.bus.preparer_topics(definitions)

    def produire(self, enveloppe: Enveloppe, rappel: Rappel) -> None:
        self.bus.produire(enveloppe, rappel)

    def attendre(self, delai_s: float) -> int:
        restants = self.bus.attendre(delai_s)
        self.fichiers += 1
        return restants + 1 if self.fichiers == self.apres + 1 else restants


def _verifier(bus: BusSimule, sortie: Path, racine: Path | None = None) -> verification.Rapport:
    lecteur = LecteurSimule(bus)
    if racine is None:
        reference = verification.reference_fichiers(sortie)
    else:
        reference = verification.reference_archive(sortie, racine, charger_tous())
    return verification.verifier(lecteur, ENTITES, reference, description_reference="essai")


def _lignes(chemin: Path) -> int:
    return sum(1 for ligne in chemin.read_bytes().splitlines() if ligne.strip())


def test_publication_complete_puis_verification_conforme(tmp_path: Path) -> None:
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    bus = BusSimule()
    _, r = _registre_pret()
    assert publication.executer(sortie, bus, r).code_sortie == 0
    rapport = _verifier(bus, sortie)
    assert rapport.code_sortie == 0 and rapport.doublons == 0
    pres, dispo, echecs = rapport.topics
    assert (pres.entite, pres.topic, pres.messages) == (PRESENTATIONS, TOPIC_PRESENTATIONS, n_pres)
    assert pres.conforme and pres.lignes_bus == pres.lignes_reference > 0
    assert (
        dispo.messages == n_dispo and dispo.conforme and dispo.lignes_bus == dispo.lignes_reference
    )
    assert (echecs.entite, echecs.topic, echecs.messages) == ("echecs", "pharmaflux.echecs.v1", 0)
    assert echecs.conforme and (echecs.lignes_bus, echecs.lignes_reference) == (0, 0)
    assert pres.configuration == CONFIGURATION_ATTENDUE and pres.partitions == 3
    assert echecs.configuration == CONFIG_ECHECS and echecs.partitions == 1
    assert rapport.reference == "essai" and rapport.duree_s >= 0


@pytest.mark.parametrize("coupure", [0, 1, 2])
def test_coupure_puis_reprise_sans_difference_doublons_du_seul_fichier_republie(
    tmp_path: Path, coupure: int
) -> None:
    sortie, _, _ = _sortie(tmp_path)
    fichiers = publication.lister_fichiers(sortie)  # dans l'ordre de publication
    assert len(fichiers) == 3
    bus = BusSimule()
    _, r = _registre_pret()
    with pytest.raises(publication.LivraisonEchouee, match="sans accusé"):
        publication.executer(sortie, BusCoupe(bus, coupure), r)
    etat = publication.lire_etat(sortie / "publication.json") if coupure else {}
    assert sum(len(v) for v in etat.values()) == coupure, (
        "l'état s'arrête au dernier fichier accusé"
    )
    assert publication.executer(sortie, bus, r, reprendre=True).code_sortie == 0
    rapport = _verifier(bus, sortie)
    assert rapport.code_sortie == 0, [t.differences for t in rapport.topics]
    _, chemin = fichiers[coupure]
    lignes = _lignes(sortie / chemin)
    par_fichier = {f: n for t in rapport.topics for f, n in t.doublons_par_fichier.items()}
    assert par_fichier == {chemin: lignes} and rapport.doublons == lignes, (
        "le seul fichier republié"
    )


def test_toute_difference_donne_le_code_2(tmp_path: Path) -> None:
    sortie, _, _ = _sortie(tmp_path)
    bus = BusSimule()
    _, r = _registre_pret()
    publication.executer(sortie, bus, r)

    def presentations(rapport: verification.Rapport) -> verification.VerificationTopic:
        (topic,) = [t for t in rapport.topics if t.entite == PRESENTATIONS]
        return topic

    # Un message de moins sur le bus.
    retire = bus.messages[TOPIC_PRESENTATIONS].pop()
    rapport = _verifier(bus, sortie)
    assert rapport.code_sortie == 2
    assert len(presentations(rapport).differences) == 1
    assert "identité(s)" in presentations(rapport).differences[0]
    bus.messages[TOPIC_PRESENTATIONS].append(retire)
    assert _verifier(bus, sortie).code_sortie == 0
    # Un flux incohérent : la même création sous un autre identifiant.
    premier = bus.messages[TOPIC_PRESENTATIONS][0]
    identifiant = json.loads(premier.valeur)["id"]
    forge = Enveloppe(
        premier.topic,
        premier.cle,
        premier.valeur.replace(identifiant.encode(), b"f" * 64),
        premier.en_tetes,
        premier.horodatage_ms,
    )
    bus.messages[TOPIC_PRESENTATIONS].append(forge)
    rapport = _verifier(bus, sortie)
    assert rapport.code_sortie == 2
    assert presentations(rapport).differences[0].startswith("flux incohérent : ")
    bus.messages[TOPIC_PRESENTATIONS].pop()
    # La rétention par défaut d'un courtier, pas celle du projet (décision 5).
    definition = bus.topics[TOPIC_PRESENTATIONS]
    bus.topics[TOPIC_PRESENTATIONS] = DefinitionTopic(
        TOPIC_PRESENTATIONS, 3, {**definition.configuration, "retention.ms": "604800000"}
    )
    rapport = _verifier(bus, sortie)
    assert rapport.code_sortie == 2
    assert presentations(rapport).differences == (
        "configuration : retention.ms=604800000 (attendu -1)",
    )
    assert presentations(rapport).messages > 0, "le topic est quand même relu et comparé"
    bus.topics[TOPIC_PRESENTATIONS] = DefinitionTopic(
        TOPIC_PRESENTATIONS, 1, definition.configuration
    )
    assert presentations(_verifier(bus, sortie)).differences == ("partitions : 1 (attendu 3)",)
    # Le topic n'existe pas.
    del bus.topics[TOPIC_PRESENTATIONS]
    rapport = _verifier(bus, sortie)
    assert rapport.code_sortie == 2
    assert presentations(rapport).differences == ("topic absent du courtier",)
    assert presentations(rapport).messages == 0 and presentations(rapport).lignes_reference > 0


def test_les_deux_references_fichiers_et_archive(tmp_path: Path) -> None:
    """Sur un bronze complet (suite des tests du rejeu) : flux de fichiers et snapshot retenu."""
    racine = tmp_path / "bronze"
    peupler(racine, SUITE)
    sortie = tmp_path / "sortie"
    assert _executer(racine, sortie).code_sortie == 0
    bus = BusSimule()
    _, r = _registre_pret()
    assert publication.executer(sortie, bus, r).code_sortie == 0
    for rapport in (_verifier(bus, sortie), _verifier(bus, sortie, racine)):
        assert rapport.code_sortie == 0 and rapport.doublons == 0, [
            t.differences for t in rapport.topics
        ]
        assert all(
            t.lignes_bus == t.lignes_reference > 0 for t in rapport.topics if t.entite != "echecs"
        )
    # Une entité qu'etat.json ne connaît pas n'a pas de référence : dit en clair, topic non relu.
    etat = json.loads((sortie / "etat.json").read_text(encoding="utf-8"))
    del etat["entites"][DISPO]
    (sortie / "etat.json").write_text(json.dumps(etat), encoding="utf-8")
    _assert_entite_sans_reference(_verifier(bus, sortie, racine))
    # Sans etat.json du tout, la référence est refusée avant de lire le bus.
    (sortie / "etat.json").unlink()
    with pytest.raises(
        verification.ReferenceIntrouvable, match=r"référence introuvable : .*etat\.json$"
    ):
        verification.reference_archive(sortie, racine, charger_tous())


def _assert_entite_sans_reference(rapport: verification.Rapport) -> None:
    pres, dispo, echecs = rapport.topics
    assert rapport.code_sortie == 2 and pres.conforme and echecs.conforme
    assert dispo.differences == (verification.SANS_REFERENCE,)
    assert (dispo.messages, dispo.lignes_bus, dispo.lignes_reference) == (0, 0, 0), "non relu"
    assert dispo.partitions == 3 and dispo.configuration == CONFIGURATION_ATTENDUE, (
        "le topic est quand même décrit"
    )


def test_une_entite_sans_fichier_d_evenements_est_dite_sans_reference(tmp_path: Path) -> None:
    sortie, _, _ = _sortie(tmp_path)
    bus = BusSimule()
    _, r = _registre_pret()
    assert publication.executer(sortie, bus, r).code_sortie == 0
    shutil.rmtree(sortie / "evenements" / DISPO)
    _assert_entite_sans_reference(_verifier(bus, sortie))


def test_une_reference_introuvable_est_refusee_avant_de_lire_le_bus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from pharmaflux import cli
    from pharmaflux.cli import application

    sortie = tmp_path / "sans-evenements"
    sortie.mkdir()
    with pytest.raises(verification.ReferenceIntrouvable, match="référence introuvable : "):
        verification.reference_fichiers(sortie)
    lecteurs_fabriques: list[str] = []
    monkeypatch.setattr(cli, "fabriquer_lecteur", lambda c: lecteurs_fabriques.append(c))
    resultat = CliRunner().invoke(application, ["verifier-bus", "--sortie", str(sortie)])
    assert resultat.exit_code == 2, resultat.output
    assert f"référence introuvable : {sortie / 'evenements'}" in resultat.output
    assert lecteurs_fabriques == [], "le bus n'est pas lu"


def test_commande_verifier_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from pharmaflux import cli
    from pharmaflux.cli import application

    sortie, n_pres, _ = _sortie(tmp_path)
    bus = BusSimule()
    _, r = _registre_pret()
    publication.executer(sortie, bus, r)
    monkeypatch.setattr(cli, "fabriquer_lecteur", lambda _courtier: LecteurSimule(bus))
    lanceur = CliRunner()
    selection = ["--fichier", PRESENTATIONS, "--fichier", DISPO]
    resultat = lanceur.invoke(application, ["verifier-bus", "--sortie", str(sortie), *selection])
    assert resultat.exit_code == 0, resultat.output
    assert f"bdpm.presentations           {n_pres} message(s), 0 doublon(s)" in resultat.output
    assert (
        "3 partition(s), retention.ms=-1, retention.bytes=-1, cleanup.policy=delete,"
        " message.timestamp.type=CreateTime ; conforme" in (resultat.output)
    )
    assert "pharmaflux.echecs.v1         0 message(s) dans la file" in resultat.output
    assert f"référence : fichiers d'événements de {sortie}" in resultat.output
    assert "durée :" in resultat.output
    bus.messages["pharmaflux.bdpm.disponibilite.v1"].pop()
    resultat = lanceur.invoke(
        application,
        ["verifier-bus", "--sortie", str(sortie), "--fichier", DISPO, "--courtier", "x:1"],
    )
    assert resultat.exit_code == 2 and "DIFFÉRENCE : 1 identité(s)" in resultat.output
    assert "bdpm.presentations" not in resultat.output, "la sélection est respectée"
    racine = tmp_path / "vide"
    racine.mkdir()
    resultat = lanceur.invoke(
        application,
        ["verifier-bus", "--sortie", str(sortie), "--racine", str(racine), *selection[:2]],
    )
    assert resultat.exit_code == 2, resultat.output
    assert f"référence introuvable : {sortie / 'etat.json'}" in resultat.output, (
        "cette sortie n'a pas d'etat.json"
    )


def test_un_fichier_d_evenements_vide_est_publie_et_compte_par_la_verification(
    tmp_path: Path,
) -> None:
    """Mission 04 : un snapshot retenu « identique au dernier retenu » laisse un JSONL vide ;
    il est publié (zéro message), inscrit dans l'état, et la vérification le voit comme publié."""
    sortie, n_pres, _ = _sortie(tmp_path)
    nom = "20261024T161700Z__eeeeeeeeeeee.jsonl"
    (sortie / "evenements" / PRESENTATIONS / nom).write_bytes(b"")
    bus = BusSimule()
    _, r = _registre_pret()
    rapport = publication.executer(sortie, bus, r)
    assert rapport.code_sortie == 0
    (pres,) = [x for x in rapport.resumes if x.identifiant == PRESENTATIONS]
    assert (pres.fichiers, pres.messages) == (3, n_pres)
    etat = publication.lire_etat(sortie / "publication.json")
    assert etat[PRESENTATIONS][f"evenements/bdpm.presentations/{nom}"].messages == 0
    verification_ = _verifier(bus, sortie)
    assert verification_.code_sortie == 0 and verification_.doublons == 0
    topic = verification_.topics[0]
    assert topic.entite == PRESENTATIONS and topic.conforme and topic.messages == n_pres
    assert topic.lignes_bus == topic.lignes_reference > 0
    assert publication.executer(sortie, bus, r, reprendre=True).topics == {}, "rien à reprendre"
