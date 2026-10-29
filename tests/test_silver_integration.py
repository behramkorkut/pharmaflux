"""Mission 05, palier 2 : le consommateur du silver contre le Redpanda local (intégration).

Marqués ``integration`` : sautés, et dit, sans courtier ; un échec en CI
(``PHARMAFLUX_INTEGRATION_EXIGEE``). Les fixtures ``bus``, ``prefixe``,
``registre`` et ``lecteur`` sont celles de ``conftest.py`` : topics et sujets
à suffixe unique, effacés à la fin. La publication des fixtures de
``test_bus`` est consommée par ``LecteurKafka``, le silver obtenu est comparé
à celui des fichiers ; une publication coupée puis reprise laisse des doublons
que le consommateur reconnaît.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pharmaflux.bus import publication
from pharmaflux.bus.client import BusKafka, LecteurKafka
from pharmaflux.bus.registre import Registre
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.silver import comparaison, construction
from pharmaflux.silver.consommation import consommer
from pharmaflux.silver.entrepot import PROP_GRAPPE, Entrepot
from tests.test_bus import DISPO, PRESENTATIONS, _sortie
from tests.test_bus_verification import BusCoupe

pytestmark = pytest.mark.integration
ENTITES = [PRESENTATIONS, DISPO]


def test_consommer_sur_le_courtier_egale_le_silver_des_fichiers(
    bus: BusKafka, registre: Registre, prefixe: str, lecteur: LecteurKafka, tmp_path: Path
) -> None:
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    assert publication.executer(sortie, bus, registre, prefixe=prefixe).code_sortie == 0
    grappe = lecteur.identifiant_grappe()
    assert grappe and grappe.startswith("redpanda.")
    dossier = tmp_path / "bus"
    rapport = consommer(lecteur, dossier, charger_tous(), ENTITES, lot=500, prefixe=prefixe)
    assert rapport.grappe == grappe and not rapport.avertissements
    pres, dispo = rapport.resumes
    assert (pres.messages, dispo.messages) == (n_pres, n_dispo)
    assert pres.doublons == 0 and sum(v.suivant for v in pres.positions.values()) == n_pres
    assert len(pres.positions) == 3  # trois partitions, toutes reçues
    fichiers = tmp_path / "fichiers"
    construction.construire(sortie, fichiers, charger_tous(), ENTITES)
    assert comparaison.comparer(Entrepot.ouvrir(dossier), Entrepot.ouvrir(fichiers)) == []
    table = Entrepot.ouvrir(dossier).table(PRESENTATIONS)
    assert table is not None and table.properties[PROP_GRAPPE] == grappe
    encore = consommer(lecteur, dossier, charger_tous(), ENTITES, prefixe=prefixe)
    assert encore.messages == 0 and all("rien de nouveau" in r.notes for r in encore.resumes)


def test_publication_coupee_puis_reprise_les_doublons_sont_reconnus(
    bus: BusKafka, registre: Registre, prefixe: str, lecteur: LecteurKafka, tmp_path: Path
) -> None:
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    with pytest.raises(publication.LivraisonEchouee):
        publication.executer(sortie, BusCoupe(bus, apres=0), registre, prefixe=prefixe)
    assert (
        publication.executer(sortie, bus, registre, reprendre=True, prefixe=prefixe).code_sortie
        == 0
    )
    dossier = tmp_path / "bus"
    rapport = consommer(lecteur, dossier, charger_tous(), ENTITES, prefixe=prefixe)
    assert rapport.messages > n_pres + n_dispo
    assert sum(r.doublons for r in rapport.resumes) == rapport.messages - n_pres - n_dispo
    fichiers = tmp_path / "fichiers"
    construction.construire(sortie, fichiers, charger_tous(), ENTITES)
    assert comparaison.comparer(Entrepot.ouvrir(dossier), Entrepot.ouvrir(fichiers)) == []
