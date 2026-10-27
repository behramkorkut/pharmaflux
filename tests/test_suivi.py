"""Mission 04, palier 2 : ``pharmaflux suivre`` sur des messages fabriqués, sans courtier.

Le formatage est vérifié sur les événements des fixtures (clé et ligne,
création, modification, suppression) ; le suiveur simulé rend une suite de
``MessageLu`` et sait lever le ``Ctrl-C``. Le vrai consommateur est exercé
dans ``test_demo_integration``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from typer.testing import CliRunner

from pharmaflux import cli
from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import suivi
from pharmaflux.bus.client import MessageLu
from pharmaflux.bus.suivi import MessageIllisible, formater
from pharmaflux.cli import application
from pharmaflux.evenements import schema
from pharmaflux.evenements.comparaison import comparer
from pharmaflux.evenements.schema import Evenement, TypeEvenement
from tests.test_bus import DISPO, PRESENTATIONS, _evenements_presentations, _snap

TOPIC = env.nom_topic(PRESENTATIONS)


def _message(evenement: Evenement, offset: int = 0, topic: str = TOPIC) -> MessageLu:
    enveloppe = env.envelopper(
        schema.serialiser(evenement).encode(), "f.jsonl", evenement.entite, 1
    )
    return MessageLu(topic, 0, offset, enveloppe.cle, enveloppe.valeur, {}, enveloppe.horodatage_ms)


@dataclass
class SuiveurSimule:
    """Rend ses messages dans l'ordre ; un ``None`` dans la suite vaut un Ctrl-C."""

    messages: list[MessageLu | None]
    demandes: list[tuple[list[str], bool]] = field(default_factory=list)

    def suivre(self, topics: list[str], *, depuis_le_debut: bool = False) -> Iterator[MessageLu]:
        self.demandes.append((topics, depuis_le_debut))
        for message in self.messages:
            if message is None:
                raise KeyboardInterrupt
            yield message
        raise AssertionError("le suiveur simulé est à court : « nombre » aurait dû arrêter avant")


def test_formater_une_ligne_par_evenement() -> None:
    initiales, suivants = _evenements_presentations()
    creation = formater(_message(initiales[0]))
    assert creation.startswith("24/10 14:17:00  bdpm.presentations           creee     code_cip13=")
    assert "→" not in creation, "une création ne liste pas de colonnes changées"
    par_type = {e.type: e for e in suivants}
    modification = formater(_message(par_type[TypeEvenement.MODIFIEE]))
    assert modification.startswith("24/10 15:17:00  bdpm.presentations           modifiee  ")
    assert "modifiee  code_cip13=" in modification
    assert modification.endswith(
        "  → " + ", ".join(par_type[TypeEvenement.MODIFIEE].champs_modifies)
    )
    assert "supprimee code_cip13=" in formater(_message(par_type[TypeEvenement.SUPPRIMEE]))
    ligne = next(iter(comparer(None, _snap(DISPO, "dispo_a.txt"))))
    assert ligne.identite.value == "ligne"
    assert formater(_message(ligne)).endswith(
        f"creee     empreinte={ligne.empreinte_ligne[:12]} rang=1"
    )


def test_formater_refuse_ce_qui_n_est_pas_un_evenement_v1() -> None:
    with pytest.raises(MessageIllisible, match="JSON illisible"):
        formater(MessageLu(TOPIC, 0, 0, b"", b"{", {}, 0))
    with pytest.raises(MessageIllisible, match="version_schema 1 attendue"):
        formater(MessageLu(TOPIC, 0, 0, b"", b'{"version_schema": 2}', {}, 0))
    with pytest.raises(MessageIllisible, match=r"UTF-8|utf-8"):
        formater(MessageLu(TOPIC, 0, 0, b"", b"\xff\xfe", {}, 0))


def test_suivre_compte_les_illisibles_et_s_arrete_au_nombre_ou_au_clavier() -> None:
    initiales, _ = _evenements_presentations()
    messages: list[MessageLu | None] = [
        _message(initiales[0], 0),
        MessageLu(TOPIC, 1, 7, b"", b"pas du JSON", {}, 0),
        _message(initiales[1], 2),
        _message(initiales[2], 3),
    ]
    sortie: list[str] = []
    erreurs: list[str] = []
    suiveur = SuiveurSimule(messages)
    resume = suivi.suivre(
        suiveur, [TOPIC], nombre=3, dire=sortie.append, dire_erreur=erreurs.append
    )
    assert (resume.lus, resume.illisibles, resume.interrompu) == (3, 1, False)
    assert len(sortie) == 2 and erreurs == [
        f"message illisible {TOPIC}/1@7 : JSON illisible : Expecting value: line 1 column 1"
        " (char 0)"
    ]
    assert suiveur.demandes == [([TOPIC], False)]
    assert suivi.formater_resume(resume) == [
        "3 message(s) lu(s), 1 illisible(s)",
        f"  {TOPIC} : 3 message(s)",
    ]
    # Ctrl-C après deux messages : résumé rendu, dit interrompu.
    interrompu = SuiveurSimule([messages[0], messages[2], None])
    resume = suivi.suivre(
        interrompu, [TOPIC], depuis_le_debut=True, dire=sortie.append, dire_erreur=erreurs.append
    )
    assert (resume.lus, resume.interrompu) == (2, True)
    assert suivi.formater_resume(resume)[0].endswith(" ; arrêté au clavier")
    assert interrompu.demandes == [([TOPIC], True)]
    assert suivi.suivre(interrompu, [TOPIC], nombre=0, dire=print, dire_erreur=print).lus == 0


def test_commande_suivre(monkeypatch: pytest.MonkeyPatch) -> None:
    initiales, _ = _evenements_presentations()
    suiveur = SuiveurSimule([_message(e, i) for i, e in enumerate(initiales)])
    monkeypatch.setattr(cli, "fabriquer_suiveur", lambda _courtier: suiveur)
    lanceur = CliRunner()
    resultat = lanceur.invoke(
        application, ["suivre", "--nombre", "3", "--fichier", PRESENTATIONS, "--depuis-le-debut"]
    )
    assert resultat.exit_code == 0, resultat.output
    lignes = resultat.output.splitlines()
    assert len(lignes) == 5
    assert all(ligne.startswith("24/10 14:17:00  bdpm.presentations") for ligne in lignes[:3])
    assert lignes[3] == "3 message(s) lu(s), 0 illisible(s)"
    assert lignes[4] == f"  {TOPIC} : 3 message(s)"
    assert suiveur.demandes == [([TOPIC], True)]
    # Sans --fichier : les onze topics d'événements, depuis la fin.
    suiveur.demandes.clear()
    lanceur.invoke(application, ["suivre", "--nombre", "1"])
    (demande,) = suiveur.demandes
    assert len(demande[0]) == 11 and demande[1] is False
    assert all(t.startswith("pharmaflux.bdpm.") and t.endswith(".v1") for t in demande[0])
    assert env.topic_echecs() not in demande[0]
