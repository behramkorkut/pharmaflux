"""Téléchargement HTTP : un client, un délai, trois essais, un User-Agent.

Les sources sont des services publics : téléchargements en série, un
``User-Agent`` qui identifie le projet, et des relances mesurées. Une erreur
de connexion est relancée tout de suite puis avec attente exponentielle ;
une réponse 5xx attend d'emblée ; une réponse 4xx, une redirection en boucle
ou un corps indécodable ne sont pas relancés. Toute erreur ``httpx`` ressort
en ``ErreurTelechargement`` : rien d'autre ne sort de ``telecharger``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version as version_du_paquet
from types import TracebackType
from typing import Self

import httpx

URL_DEPOT = "https://github.com/behramkorkut/pharmaflux"
DELAI_SECONDES = 60.0
ESSAIS_MAX = 3
ATTENTE_BASE_SECONDES = 2.0


def agent_utilisateur() -> str:
    return f"pharmaflux/{version_du_paquet('pharmaflux')} (+{URL_DEPOT})"


@dataclass(frozen=True, slots=True)
class Reponse:
    """Une réponse HTTP exploitable (200 ou 304), avec le nombre d'essais."""

    http_statut: int
    contenu: bytes
    en_tetes: httpx.Headers
    essais: int

    def en_tete(self, nom: str) -> str | None:
        valeur = self.en_tetes.get(nom)
        return str(valeur) if valeur is not None else None

    @property
    def last_modified(self) -> str | None:
        return self.en_tete("last-modified")

    @property
    def etag(self) -> str | None:
        return self.en_tete("etag")

    @property
    def content_disposition_nom(self) -> str | None:
        """Le nom de fichier annoncé par ``Content-Disposition``, s'il y en a un."""
        valeur = self.en_tete("content-disposition")
        if not valeur:
            return None
        for partie in valeur.split(";"):
            cle, _, nom = partie.strip().partition("=")
            if cle.strip().lower() == "filename" and nom:
                return str(nom.strip().strip('"'))
        return None


class ErreurTelechargement(Exception):  # noqa: N818 (nom français voulu)
    """Le téléchargement a échoué après ses essais (ou sans relance pour un 4xx)."""

    def __init__(self, message: str, *, essais: int, http_statut: int | None = None) -> None:
        super().__init__(message)
        self.essais = essais
        self.http_statut = http_statut


class Telechargeur:
    """Client HTTP du collecteur. À utiliser comme gestionnaire de contexte.

    ``transport`` permet aux tests de simuler le serveur (``httpx.MockTransport``) ;
    ``attente_base`` et ``dormir`` rendent les relances instantanées en test.
    """

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        attente_base: float = ATTENTE_BASE_SECONDES,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._attente_base = attente_base
        self._dormir = dormir
        self._client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(DELAI_SECONDES),
            headers={"User-Agent": agent_utilisateur()},
            follow_redirects=True,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        type_exception: type[BaseException] | None,
        exception: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.fermer()

    def fermer(self) -> None:
        self._client.close()

    def telecharger(self, url: str) -> Reponse:
        """GET sans condition ; trois essais au plus. Lève ``ErreurTelechargement``."""
        derniere_erreur = ""
        dernier_statut: int | None = None
        for essai in range(1, ESSAIS_MAX + 1):
            try:
                reponse = self._client.get(url)
            except httpx.TransportError as exc:
                # Connexion, délai, lecture interrompue : relance immédiate puis exponentielle.
                derniere_erreur = _libelle(exc)
                dernier_statut = None
                attente = 0.0 if essai == 1 else self._attente_base * 2 ** (essai - 2)
            except httpx.HTTPError as exc:
                # Redirection en boucle, corps indécodable (Content-Encoding menteur)… :
                # un nouvel essai donnerait la même chose, l'erreur est définitive.
                raise ErreurTelechargement(_libelle(exc), essais=essai) from exc
            else:
                if reponse.status_code in (200, 304):
                    return Reponse(reponse.status_code, reponse.content, reponse.headers, essai)
                derniere_erreur = f"HTTP {reponse.status_code}"
                dernier_statut = reponse.status_code
                if reponse.status_code < 500:
                    raise ErreurTelechargement(
                        derniere_erreur, essais=essai, http_statut=reponse.status_code
                    )
                # 5xx : le serveur souffre, on attend d'emblée.
                attente = self._attente_base * 2 ** (essai - 1)
            if essai < ESSAIS_MAX:
                self._dormir(attente)
        raise ErreurTelechargement(derniere_erreur, essais=ESSAIS_MAX, http_statut=dernier_statut)


def _libelle(exc: httpx.HTTPError) -> str:
    """``TooManyRedirects: Exceeded maximum allowed redirects.`` : le type, puis le message."""
    return f"{type(exc).__name__}: {exc}".strip(": ")
