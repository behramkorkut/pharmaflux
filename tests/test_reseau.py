"""La garde réseau des tests (``conftest.reseau_coupe``) : aucun client ne sort de la machine.

Elle couvre la mission 09, la première à écrire un client vers un site tiers dont les tests
ne doivent jamais rien demander, et toutes les autres : la HAS, la BDPM et data.gouv.fr restent
injoignables pendant les tests, quel que soit le client.
"""

from __future__ import annotations

import socket
import urllib.request

import httpx
import pytest

from pharmaflux.has.client import ClientHas
from tests.conftest import ReseauInterdit, hote_local


@pytest.mark.parametrize(
    "url",
    [
        "https://www.has-sante.fr/robots.txt",
        "https://base-donnees-publique.medicaments.gouv.fr/telechargement",
        "https://www.data.gouv.fr/api/1/datasets/",
    ],
)
def test_httpx_ne_sort_pas(url: str) -> None:
    with pytest.raises(ReseauInterdit):
        httpx.get(url, timeout=1)


def test_le_client_de_la_has_ne_sort_pas_sans_transport_simule() -> None:
    with ClientHas(plafond=1, dormir=lambda _s: None) as client, pytest.raises(ReseauInterdit):
        client.demander("https://www.has-sante.fr/robots.txt")


def test_urllib_et_une_adresse_ip_ne_sortent_pas() -> None:
    with pytest.raises(ReseauInterdit):
        urllib.request.urlopen("https://www.has-sante.fr/robots.txt", timeout=1)
    with socket.socket() as prise, pytest.raises(ReseauInterdit):
        prise.connect(("93.184.216.34", 443))


def test_les_services_locaux_restent_joignables() -> None:
    assert hote_local("127.0.0.1")
    assert hote_local("localhost")
    assert hote_local("::1")
    assert not hote_local("www.has-sante.fr")
    assert not hote_local("10.0.0.1")
