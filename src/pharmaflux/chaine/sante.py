"""Les services dont une étape a besoin répondent-ils ? Sondés avant de la lancer.

Une panne de service se classe ici, par un test direct, jamais par le code de
sortie d'une commande : un service injoignable donne 1 pour le bus et 2 pour
l'index, où 2 veut aussi dire « refus ». Une étape n'est lancée que si ses
services répondent ; sinon le passage s'arrête, et le suivant reprend.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

import httpx

from pharmaflux.bus.client import COURTIER_PAR_DEFAUT, VARIABLE_COURTIER
from pharmaflux.bus.registre import REGISTRE_PAR_DEFAUT, VARIABLE_REGISTRE
from pharmaflux.index.qdrant import QDRANT_PAR_DEFAUT, VARIABLE_QDRANT

COURTIER, REGISTRE, QDRANT = "courtier", "registre", "qdrant"
DELAI_S = 5.0
ESSAIS = 3
PAUSE_S = 5.0


def adresse(service: str) -> str:
    """L'adresse du service : la variable d'environnement, sinon le défaut du code."""
    variable, defaut = {
        COURTIER: (VARIABLE_COURTIER, COURTIER_PAR_DEFAUT),
        REGISTRE: (VARIABLE_REGISTRE, REGISTRE_PAR_DEFAUT),
        QDRANT: (VARIABLE_QDRANT, QDRANT_PAR_DEFAUT),
    }[service]
    return os.environ.get(variable) or defaut


def _courtier(cible: str) -> str | None:
    from confluent_kafka import KafkaException
    from confluent_kafka.admin import AdminClient

    try:
        AdminClient({"bootstrap.servers": cible}).list_topics(timeout=DELAI_S)
    except (KafkaException, ValueError, RuntimeError) as exc:
        return f"{cible} : {exc}"
    return None


def _http(url: str) -> str | None:
    try:
        reponse = httpx.get(url, timeout=DELAI_S)
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        return f"{url} : {type(exc).__name__}"
    return None if reponse.status_code == 200 else f"{url} : HTTP {reponse.status_code}"


def _une_fois(service: str) -> str | None:
    cible = adresse(service)
    if service == COURTIER:
        return _courtier(cible)
    if service == REGISTRE:
        return _http(f"{cible.rstrip('/')}/subjects")
    return _http(f"{cible.rstrip('/')}/readyz")


def sonder(service: str, *, dormir: Callable[[float], None] = time.sleep) -> str | None:
    """None si le service répond ; sinon la raison, après trois essais espacés de cinq secondes."""
    raison: str | None = None
    for essai in range(ESSAIS):
        raison = _une_fois(service)
        if raison is None:
            return None
        if essai < ESSAIS - 1:
            dormir(PAUSE_S)
    return raison
