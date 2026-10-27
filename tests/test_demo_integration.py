"""Mission 04, palier 2 : la démo, ``suivre`` et le registre contre le Redpanda local (intégration).

Mêmes règles que ``test_bus_integration`` (fixtures de ``conftest.py``) : sautés
sans courtier, préfixe unique par test, topics et sujets effacés à la fin,
seules les fixtures sont lues. Le reliquat F.2 de la mission 03 est testé ici
contre le **vrai** registre : un schéma qui perd une propriété requise est
jugé incompatible sous ``BACKWARD_TRANSITIVE``, et ``enregistrer_tout``
s'arrête avant de l'enregistrer.
"""

from __future__ import annotations

import copy
import threading
import time
from pathlib import Path

import httpx
import pytest

from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import publication, suivi, verification
from pharmaflux.bus import registre as registre_module
from pharmaflux.bus.client import BusKafka, LecteurKafka
from pharmaflux.bus.registre import (
    SCHEMA_EVENEMENT,
    Registre,
    SchemaIncompatible,
    charger_schema,
    enregistrer_tout,
)
from pharmaflux.bus.registre import sujet as sujet_de
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.demo import rejeu_accelere
from pharmaflux.demo.rejeu_accelere import DemoRefusee
from tests.conftest import COURTIER, REGISTRE
from tests.test_bus import DISPO, PRESENTATIONS, _sortie
from tests.test_rejeu import SUITE, peupler

pytestmark = pytest.mark.integration
ENTITES = [PRESENTATIONS, DISPO]


def test_demo_rejouer_sur_le_courtier_puis_verifier_bus(
    bus: BusKafka, registre: Registre, lecteur: LecteurKafka, prefixe: str, tmp_path: Path
) -> None:
    racine, sortie = tmp_path / "archive", tmp_path / "demo"
    peupler(racine, SUITE)
    lignes: list[str] = []
    resume = rejeu_accelere.executer(
        racine, sortie, charger_tous(), ENTITES, bus, registre,
        sans_pause=True, prefixe=prefixe, journal=lignes.append,
    )  # fmt: skip
    assert resume.code_sortie == 0 and (resume.archives, resume.publies) == (22, 15)
    assert resume.messages == {
        env.nom_topic(PRESENTATIONS, prefixe): 80,
        env.nom_topic(DISPO, prefixe): 12,
    }
    assert sum(ligne[16:].startswith("passage ") for ligne in lignes) == 2
    # Les deux références de verifier-bus : les fichiers, et le dernier snapshot retenu.
    for reference in (
        verification.reference_fichiers(sortie),
        verification.reference_archive(sortie, racine, charger_tous()),
    ):
        rapport = verification.verifier(
            lecteur, ENTITES, reference, description_reference="démo", prefixe=prefixe
        )
        assert rapport.code_sortie == 0 and rapport.doublons == 0, [
            t.differences for t in rapport.topics
        ]
        assert [t.messages for t in rapport.topics] == [80, 12, 0]
    # Relancer sans --reprendre : le bus a déjà reçu la démo, refus ; avec : rien à rejouer.
    with pytest.raises(DemoRefusee, match=r"le bus a déjà reçu une publication.*make rebatir"):
        rejeu_accelere.executer(
            racine, sortie, charger_tous(), ENTITES, bus, registre, sans_pause=True, prefixe=prefixe
        )
    reprise = rejeu_accelere.executer(
        racine, sortie, charger_tous(), ENTITES, bus, registre,
        sans_pause=True, reprendre=True, prefixe=prefixe,
    )  # fmt: skip
    assert (reprise.publies, reprise.deja_publies) == (0, 15)


def test_suivre_attend_un_topic_absent_puis_lit_ce_qui_arrive(
    bus: BusKafka, registre: Registre, prefixe: str, tmp_path: Path
) -> None:
    sortie, n_pres, _ = _sortie(tmp_path)
    topic = env.nom_topic(PRESENTATIONS, prefixe)
    suiveur = LecteurKafka(COURTIER)
    lignes: list[str] = []
    erreurs: list[str] = []
    resultat: dict[str, suivi.Resume] = {}

    def regarder() -> None:
        resultat["resume"] = suivi.suivre(
            suiveur, [topic], nombre=n_pres, dire=lignes.append, dire_erreur=erreurs.append
        )

    fil = threading.Thread(target=regarder, daemon=True)
    fil.start()
    time.sleep(2.5)  # le topic n'existe pas encore : « suivre » l'attend
    assert fil.is_alive() and lignes == []
    publication.executer(sortie, bus, registre, prefixe=prefixe)
    fil.join(timeout=60)
    assert not fil.is_alive(), "« suivre » devait s'arrêter au vingtième message"
    assert (resultat["resume"].lus, resultat["resume"].illisibles) == (n_pres, 0)
    assert len(lignes) == n_pres and erreurs == []
    assert all(ligne.startswith(("24/10 14:17:00", "24/10 15:17:00")) for ligne in lignes)
    assert sum(" modifiee  " in ligne for ligne in lignes) == 1
    assert sum(" supprimee " in ligne for ligne in lignes) == 1
    # Depuis le début d'un topic qui existe : les mêmes lignes, à l'ordre des partitions près.
    depuis_le_debut = LecteurKafka(COURTIER)
    relues: list[str] = []
    resume = suivi.suivre(
        depuis_le_debut,
        [topic],
        depuis_le_debut=True,
        nombre=n_pres,
        dire=relues.append,
        dire_erreur=erreurs.append,
    )
    depuis_le_debut.close()
    suiveur.close()
    assert resume.lus == n_pres and sorted(relues) == sorted(lignes)


def test_un_schema_sans_propriete_requise_est_incompatible_pour_le_vrai_registre(
    registre: Registre, prefixe: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    sujet = sujet_de(env.nom_topic(PRESENTATIONS, prefixe))
    courant = charger_schema(SCHEMA_EVENEMENT)
    reduit = copy.deepcopy(courant)
    assert isinstance(reduit["required"], list) and isinstance(reduit["properties"], dict)
    reduit["required"].remove("date_source")
    del reduit["properties"]["date_source"]
    assert registre.compatible(sujet, courant), "le schéma courant est compatible avec lui-même"
    assert registre.compatible(sujet, reduit) is False, (
        "BACKWARD_TRANSITIVE : le schéma réduit ne lit pas un événement qui porte date_source"
    )
    versions_avant = httpx.get(f"{REGISTRE}/subjects/{sujet}/versions", timeout=10).json()
    # enregistrer_tout s'arrête avant d'enregistrer : le reliquat F.2, contre le vrai registre.
    monkeypatch.setattr(registre_module, "charger_schema", lambda _nom: reduit)
    with pytest.raises(SchemaIncompatible, match="incompatible avec les versions enregistrées"):
        enregistrer_tout(registre, [PRESENTATIONS], prefixe)
    versions_apres = httpx.get(f"{REGISTRE}/subjects/{sujet}/versions", timeout=10).json()
    assert versions_apres == versions_avant == [1], "rien n'a été enregistré pour ce sujet"
