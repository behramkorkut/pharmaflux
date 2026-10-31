"""Le client HTTP de la collecte des pages de la HAS : poli par construction (ADR 0004, mission 09).

À côté du client de la BDPM (``collecte.telechargement``), dont il reprend le ``User-Agent``
et l'injection d'un transport pour les tests. Il en diffère sur ce que le site de la HAS
demande, et que la BDPM n'a pas à changer :

- **aucune redirection suivie** : une réponse 3xx est rendue telle quelle, à consigner ;
- **la pause est tenue ici**, avant toute requête, réessai compris : ``pause`` secondes au
  moins après la fin de la précédente, deux au minimum ;
- **un plafond de requêtes** : la requête qui le dépasserait n'est pas envoyée
  (``PlafondAtteint``) ;
- **l'arrêt net** (``ArretNet``) au premier 429, ou à la seconde défaillance d'affilée du
  serveur (5xx ou erreur réseau), sur la même URL ou sur la suivante ;
- **un seul réessai**, après ``REESSAI_SECONDES``, sur une défaillance isolée.

Un cookie de session reste en mémoire le temps du client (une session côté serveur par
passage) ; il n'est jamais écrit.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Self

import httpx

from pharmaflux.collecte.telechargement import agent_utilisateur

PAUSE_MINIMALE = 2.0
REESSAI_SECONDES = 10.0
DELAI_SECONDES = 30.0


class PlafondAtteint(Exception):  # noqa: N818 (nom français voulu)
    """La requête suivante dépasserait le plafond : elle n'est pas envoyée."""


class ArretNet(Exception):  # noqa: N818 (nom français voulu)
    """Le serveur demande d'arrêter (429) ou défaille deux fois d'affilée : on s'arrête."""

    def __init__(self, message: str, *, reponse: Reponse | None = None) -> None:
        super().__init__(message)
        self.reponse = reponse


@dataclass(frozen=True, slots=True)
class Reponse:
    """Une réponse reçue (de tout statut), ou l'erreur réseau d'une requête sans réponse."""

    url: str
    debut: datetime
    fin: datetime
    essais: int
    statut: int | None  # None : erreur réseau, sans réponse
    contenu: bytes = b""
    en_tetes: httpx.Headers | None = None
    erreur: str | None = None

    def en_tete(self, nom: str) -> str | None:
        if self.en_tetes is None:
            return None
        valeur = self.en_tetes.get(nom)
        return str(valeur) if valeur is not None else None

    @property
    def defaillance(self) -> bool:
        """Une défaillance du serveur ou du réseau : 5xx, ou aucune réponse."""
        return self.statut is None or self.statut >= 500


class ClientHas:
    """À utiliser comme gestionnaire de contexte. ``dormir`` et ``horloge`` servent aux tests."""

    def __init__(
        self,
        *,
        plafond: int,
        pause: float = PAUSE_MINIMALE,
        transport: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
        horloge: Callable[[], float] = time.monotonic,
        maintenant: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if pause < PAUSE_MINIMALE:
            raise ValueError(f"pause de {pause} s : {PAUSE_MINIMALE} s au moins")
        if plafond < 1:
            raise ValueError(f"plafond de {plafond} requête(s) : une au moins")
        self.plafond = plafond
        self.pause = pause
        self.envoyees = 0
        self._dormir = dormir
        self._horloge = horloge
        self._maintenant = maintenant
        self._fin_precedente: float | None = None
        self._defaillance_precedente = False
        self._client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(DELAI_SECONDES),
            headers={"User-Agent": agent_utilisateur()},
            follow_redirects=False,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        type_exception: type[BaseException] | None,
        exception: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self._client.close()

    @property
    def restantes(self) -> int:
        return self.plafond - self.envoyees

    def demander(self, url: str) -> Reponse:
        """GET de ``url``, un réessai au plus. Lève ``PlafondAtteint`` ou ``ArretNet``."""
        reponse = self._une_requete(url, essai=1, attente=self.pause)
        if reponse.statut == 429:
            raise ArretNet(_arret_429(reponse), reponse=reponse)
        if reponse.defaillance:
            if self._defaillance_precedente:
                raise ArretNet(f"{_libelle(reponse)}, après une défaillance", reponse=reponse)
            self._defaillance_precedente = True
            reponse = self._une_requete(url, essai=2, attente=max(self.pause, REESSAI_SECONDES))
            if reponse.statut == 429:
                raise ArretNet(_arret_429(reponse), reponse=reponse)
            if reponse.defaillance:
                raise ArretNet(f"{_libelle(reponse)}, deux fois d'affilée", reponse=reponse)
        self._defaillance_precedente = False
        return reponse

    def _une_requete(self, url: str, *, essai: int, attente: float) -> Reponse:
        if self.envoyees >= self.plafond:
            raise PlafondAtteint(f"plafond de {self.plafond} requête(s) atteint")
        if self._fin_precedente is not None:
            reste = attente - (self._horloge() - self._fin_precedente)
            if reste > 0:
                self._dormir(reste)
        self.envoyees += 1
        debut = self._maintenant()
        try:
            brute = self._client.get(url)
        except httpx.HTTPError as exc:
            return Reponse(
                url, debut, self._terminer(), essai, None, erreur=f"{type(exc).__name__}: {exc}"
            )
        return Reponse(
            url, debut, self._terminer(), essai, brute.status_code, brute.content, brute.headers
        )

    def _terminer(self) -> datetime:
        self._fin_precedente = self._horloge()
        return self._maintenant()


def _libelle(reponse: Reponse) -> str:
    return f"HTTP {reponse.statut}" if reponse.statut is not None else str(reponse.erreur)


def _arret_429(reponse: Reponse) -> str:
    attendre = reponse.en_tete("retry-after")
    return "HTTP 429" + (f" (Retry-After : {attendre})" if attendre else "")
