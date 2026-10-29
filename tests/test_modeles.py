"""Mission 07, palier 1 : l'épinglage des modèles d'embeddings et sa procédure (addendum 1 K7).

Aucun téléchargement : le hub de Hugging Face est simulé (``httpx.MockTransport``),
les fichiers vont dans un dossier jetable. Les vrais téléchargements sont ceux de
beko, selon la procédure du rapport du palier 1.
"""

from __future__ import annotations

import hashlib
import tomllib
from datetime import date
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from pharmaflux.cli import application
from pharmaflux.index import modeles
from pharmaflux.index.modeles import Epinglage, EpinglageInvalide, Fichier

CONTENUS = {"onnx/model.onnx": b"poids du modele", "tokenizer.json": b'{"version": "1.0"}'}
REVISION = "a" * 40


def sha(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def epinglage(**surcharges: object) -> Epinglage:
    base: dict[str, object] = {
        "nom": "essai",
        "depot": "org/essai",
        "licence": "MIT",
        "revision": REVISION,
        "date_revision": date(2026, 10, 1),
        "fichiers": tuple(Fichier(c, sha(v)) for c, v in CONTENUS.items()),
    }
    return Epinglage(**(base | surcharges))  # type: ignore[arg-type]


class Hub:
    """Le hub simulé : la liste des commits, puis les fichiers à une révision."""

    def __init__(self, contenus: dict[str, bytes] = CONTENUS) -> None:
        self.contenus = contenus
        self.requetes: list[str] = []

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._repondre))

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete.url.path)
        if requete.url.path == "/api/models/org/essai/commits/main":
            return httpx.Response(
                200,
                json=[
                    {"id": "c" * 40, "date": "2026-10-25T10:00:00.000Z"},  # trop récent
                    {"id": REVISION, "date": "2026-10-01T08:00:00.000Z"},
                    {"id": "b" * 40, "date": "2026-09-01T08:00:00.000Z"},
                ],
            )
        prefixe = f"/org/essai/resolve/{REVISION}/"
        chemin = requete.url.path.removeprefix(prefixe)
        if requete.url.path.startswith(prefixe) and chemin in self.contenus:
            return httpx.Response(200, content=self.contenus[chemin])
        return httpx.Response(404)


def test_le_modele_retenu_est_epingle() -> None:
    """Palier 2 : e5-small-int8 retenu, potion écarté (ADR 0011) ; chaque fichier a son sha256."""
    assert modeles.noms() == ["e5-small-int8"]
    lu = modeles.lire("e5-small-int8")
    assert lu.epingle and lu.revision == "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
    assert [f.chemin for f in lu.fichiers] == [
        "onnx/model_quantized.onnx",
        "tokenizer.json",
        "config.json",
        "sentencepiece.bpe.model",
    ]
    with pytest.raises(EpinglageInvalide, match="modèle inconnu"):
        modeles.lire("inconnu")


def test_un_epinglage_refuse_une_cle_inconnue() -> None:
    brut = tomllib.loads(
        'nom = "x"\ndepot = "o/x"\nlicence = "MIT"\nbranche = "main"\n[[fichiers]]\nchemin = "a"\n'
    )
    with pytest.raises(EpinglageInvalide, match="branche"):
        modeles.depuis_toml(brut, "x.toml")


def test_la_revision_choisie_a_deux_semaines() -> None:
    commits = [
        {"id": "recent", "date": "2026-10-20T00:00:00Z"},
        {"id": "juste", "date": "2026-10-15T23:59:59Z"},
        {"id": "ancien", "date": "2026-09-01T00:00:00Z"},
    ]
    assert modeles.choisir_revision(commits, date(2026, 10, 29)) == ("juste", date(2026, 10, 15))
    with pytest.raises(EpinglageInvalide, match="deux semaines"):
        modeles.choisir_revision(commits[:1], date(2026, 10, 29))


def test_relever_telecharge_a_sa_place_et_rend_le_toml(tmp_path: Path) -> None:
    hub = Hub()
    with hub.client() as client:
        releve = modeles.relever(
            epinglage(revision=None, date_revision=None), client, tmp_path, date(2026, 10, 29)
        )
    assert releve.revision == REVISION and releve.date_revision == date(2026, 10, 1)
    relu = modeles.depuis_toml(tomllib.loads(releve.en_toml(epinglage())), "relevé")
    assert relu == epinglage(), "le TOML affiché se recopie tel quel"
    assert modeles.verifier(relu, tmp_path) == [], "et les fichiers relevés sont déjà en place"
    with hub.client() as client:
        assert modeles.installer(relu, client, tmp_path) == [
            "onnx/model.onnx : déjà en place",
            "tokenizer.json : déjà en place",
        ]
    assert not any("resolve" in r for r in hub.requetes[3:]), "aucun second téléchargement"


def test_installer_verifie_avant_de_mettre_en_place(tmp_path: Path) -> None:
    with Hub().client() as client:
        assert modeles.installer(epinglage(), client, tmp_path) == [
            "onnx/model.onnx : installé, sha256 vérifié",
            "tokenizer.json : installé, sha256 vérifié",
        ]
    assert (
        tmp_path / "essai" / REVISION / "onnx" / "model.onnx"
    ).read_bytes() == b"poids du modele"
    altere = Hub(CONTENUS | {"tokenizer.json": b"autre chose"})
    autre = tmp_path / "autre"
    with altere.client() as client, pytest.raises(EpinglageInvalide, match="rien installé"):
        modeles.installer(epinglage(), client, autre)
    assert not (autre / "essai" / REVISION / "tokenizer.json").exists()
    assert not list(autre.rglob("*.partiel")), "le fichier altéré n'est pas laissé"


def test_installer_refuse_un_modele_pas_encore_epingle(tmp_path: Path) -> None:
    sans_empreinte = epinglage(fichiers=(Fichier("tokenizer.json", None),))
    with Hub().client() as client, pytest.raises(EpinglageInvalide, match="relever essai"):
        modeles.installer(sans_empreinte, client, tmp_path)


def test_verifier_sans_reseau(tmp_path: Path) -> None:
    lu = epinglage()
    assert modeles.verifier(lu, tmp_path) == [
        f"essai/onnx/model.onnx : absent de {tmp_path / 'essai' / REVISION}",
        f"essai/tokenizer.json : absent de {tmp_path / 'essai' / REVISION}",
    ]
    base = tmp_path / "essai" / REVISION
    (base / "onnx").mkdir(parents=True)
    (base / "onnx" / "model.onnx").write_bytes(b"poids du modele")
    (base / "tokenizer.json").write_bytes(b"modifie")
    assert modeles.verifier(lu, tmp_path) == [
        "essai/tokenizer.json : sha256 différent de l'épinglage"
    ]


def test_modele_verifier_en_ligne_de_commande(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(modeles.VARIABLE_MODELES, str(tmp_path))
    resultat = CliRunner().invoke(application, ["index", "modele", "verifier", "e5-small-int8"])
    assert resultat.exit_code == 1
    assert "e5-small-int8/onnx/model_quantized.onnx : absent de" in resultat.output
    inconnu = CliRunner().invoke(application, ["index", "modele", "verifier", "inconnu"])
    assert inconnu.exit_code == 2 and "modèle inconnu" in inconnu.output


def test_relever_a_la_revision_du_toml_ne_telecharge_que_les_fichiers_ajoutes(
    tmp_path: Path,
) -> None:
    """Palier 2 : un fichier ajouté au TOML, la révision imposée, les autres repris tels quels."""
    hub = Hub(CONTENUS | {"sentencepiece.bpe.model": b"jetons"})
    with hub.client() as client:
        modeles.installer(epinglage(), client, tmp_path)
    avant = len(hub.requetes)
    plus_un = epinglage(fichiers=(*epinglage().fichiers, Fichier("sentencepiece.bpe.model", None)))
    with hub.client() as client:
        releve = modeles.relever(plus_un, client, tmp_path, date(2026, 10, 29), REVISION)
    assert hub.requetes[avant:] == [f"/org/essai/resolve/{REVISION}/sentencepiece.bpe.model"]
    assert releve.revision == REVISION and releve.date_revision == date(2026, 10, 1)
    assert [f.sha256 for f in releve.fichiers] == [
        sha(b"poids du modele"),
        sha(b'{"version": "1.0"}'),
        sha(b"jetons"),
    ]
    with hub.client() as client, pytest.raises(EpinglageInvalide, match="introuvable"):
        modeles.relever(plus_un, client, tmp_path, date(2026, 10, 29), "d" * 40)
