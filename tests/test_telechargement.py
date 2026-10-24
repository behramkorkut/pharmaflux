"""Le client HTTP : User-Agent, relances, erreurs définitives, 304."""

import httpx
import pytest

from pharmaflux.collecte.telechargement import (
    ESSAIS_MAX,
    ErreurTelechargement,
    Telechargeur,
    agent_utilisateur,
)
from tests.conftest import ServeurSimule

URL = "https://exemple.invalid/fichier.txt"


def _telechargeur(serveur: ServeurSimule, attentes: list[float]) -> Telechargeur:
    return Telechargeur(transport=serveur.transport(), attente_base=2, dormir=attentes.append)


def test_user_agent_identifie_le_projet() -> None:
    serveur = ServeurSimule({URL: [(200, b"ok", {})]})
    with _telechargeur(serveur, []) as telechargeur:
        reponse = telechargeur.telecharger(URL)
    assert reponse.http_statut == 200 and reponse.contenu == b"ok" and reponse.essais == 1
    agent = serveur.requetes[0].headers["user-agent"]
    assert agent == agent_utilisateur()
    assert agent.startswith("pharmaflux/0.")
    assert "+https://github.com/behramkorkut/pharmaflux" in agent


def test_erreur_de_connexion_puis_succes() -> None:
    serveur = ServeurSimule({URL: [httpx.ConnectError("refus"), (200, b"ok", {})]})
    attentes: list[float] = []
    with _telechargeur(serveur, attentes) as telechargeur:
        reponse = telechargeur.telecharger(URL)
    assert reponse.essais == 2
    assert attentes == [0.0], "première relance immédiate après une erreur de connexion"


def test_5xx_attend_d_emblee_puis_echoue() -> None:
    serveur = ServeurSimule({URL: [(503, b"", {})]})
    attentes: list[float] = []
    with (
        _telechargeur(serveur, attentes) as telechargeur,
        pytest.raises(ErreurTelechargement) as info,
    ):
        telechargeur.telecharger(URL)
    assert info.value.essais == ESSAIS_MAX
    assert info.value.http_statut == 503
    assert attentes == [2.0, 4.0]
    assert serveur.requetes_vers(URL) == ESSAIS_MAX


def test_delai_depasse_trois_fois() -> None:
    serveur = ServeurSimule({URL: [httpx.ReadTimeout("trop long")]})
    attentes: list[float] = []
    with (
        _telechargeur(serveur, attentes) as telechargeur,
        pytest.raises(ErreurTelechargement) as info,
    ):
        telechargeur.telecharger(URL)
    assert info.value.essais == 3 and info.value.http_statut is None
    assert "ReadTimeout" in str(info.value)
    assert attentes == [0.0, 2.0]


def test_4xx_sans_relance() -> None:
    serveur = ServeurSimule({URL: [(404, b"", {})]})
    with _telechargeur(serveur, []) as telechargeur, pytest.raises(ErreurTelechargement) as info:
        telechargeur.telecharger(URL)
    assert info.value.essais == 1 and info.value.http_statut == 404
    assert serveur.requetes_vers(URL) == 1


def test_304_et_en_tetes() -> None:
    en_tetes = {
        "ETag": '"abc"',
        "Last-Modified": "Sat, 24 Oct 2026 13:00:00 GMT",
        "Content-Disposition": "attachment; filename=CIS_InfoImportantes_20261024132108_bdpm.txt",
    }
    serveur = ServeurSimule({URL: [(304, b"", en_tetes)]})
    with _telechargeur(serveur, []) as telechargeur:
        reponse = telechargeur.telecharger(URL)
    assert reponse.http_statut == 304 and reponse.contenu == b""
    assert reponse.etag == '"abc"'
    assert reponse.last_modified == "Sat, 24 Oct 2026 13:00:00 GMT"
    assert reponse.content_disposition_nom == "CIS_InfoImportantes_20261024132108_bdpm.txt"


def test_content_disposition_avec_guillemets_et_sans() -> None:
    serveur = ServeurSimule(
        {URL: [(200, b"", {"Content-Disposition": 'attachment; filename="CIS_bdpm.txt"'})]}
    )
    with _telechargeur(serveur, []) as telechargeur:
        assert telechargeur.telecharger(URL).content_disposition_nom == "CIS_bdpm.txt"
    serveur = ServeurSimule({URL: [(200, b"", {})]})
    with _telechargeur(serveur, []) as telechargeur:
        assert telechargeur.telecharger(URL).content_disposition_nom is None
