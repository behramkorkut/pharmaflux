"""Les fichiers des modèles d'embeddings : épinglés, téléchargés par beko, vérifiés (ADR 0011).

Un fichier TOML par modèle candidat (``index/modeles/<nom>.toml``) : le dépôt
Hugging Face, la **révision** (une empreinte de commit, jamais une branche),
sa date, et pour chaque fichier son chemin et son **sha256**. Les fichiers
vivent hors de git, sous ``$PHARMAFLUX_MODELES`` (défaut
``~/pharmaflux-modeles``), dans ``<nom>/<révision>/<chemin>``.

Trois opérations, dans cet ordre :

- ``relever`` (beko) : la dernière révision qui a au moins **deux
  semaines** (la règle de l'ADR 0009, appliquée aux modèles) ; ses fichiers
  téléchargés à leur place, et leur empreinte, à recopier dans le TOML ;
- ``installer`` (beko, et la CI) : télécharge chaque fichier à la révision
  épinglée, vérifie son sha256, puis seulement le met en place ; refuse un
  modèle qui n'est pas encore épinglé ;
- ``verifier`` (``make up``, le code qui charge un modèle) : sans réseau, la
  présence et l'empreinte de chaque fichier.

Les agents ne lancent jamais ``relever`` ni ``installer`` : ce sont des
téléchargements.
"""

from __future__ import annotations

import hashlib
import os
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.resources import files
from pathlib import Path

import httpx

from pharmaflux.tomlstrict import TableStricte

VARIABLE_MODELES = "PHARMAFLUX_MODELES"
HUB = "https://huggingface.co"
AGE_MINIMAL = timedelta(days=14)
DELAI_S = 60.0
MORCEAU = 1 << 20


class EpinglageInvalide(ValueError):  # noqa: N818 (nom français voulu)
    """Le TOML d'un modèle est mal formé, ou le modèle n'est pas encore épinglé."""


class _Table(TableStricte):
    erreur = EpinglageInvalide


@dataclass(frozen=True, slots=True)
class Fichier:
    chemin: str
    sha256: str | None


@dataclass(frozen=True, slots=True)
class Epinglage:
    nom: str
    depot: str
    licence: str
    revision: str | None
    date_revision: date | None
    fichiers: tuple[Fichier, ...]

    @property
    def epingle(self) -> bool:
        return self.revision is not None and all(f.sha256 for f in self.fichiers)


def racine_modeles() -> Path:
    return Path(os.environ.get(VARIABLE_MODELES) or Path.home() / "pharmaflux-modeles")


def noms() -> list[str]:
    """Les modèles candidats, par nom de fichier."""
    dossier = files("pharmaflux.index") / "modeles"
    return sorted(
        f.name.removesuffix(".toml") for f in dossier.iterdir() if f.name.endswith(".toml")
    )


def lire(nom: str) -> Epinglage:
    if nom not in noms():
        raise EpinglageInvalide(f"modèle inconnu : {nom} (connus : {', '.join(noms())})")
    texte = (files("pharmaflux.index") / "modeles" / f"{nom}.toml").read_text(encoding="utf-8")
    return depuis_toml(tomllib.loads(texte), f"{nom}.toml")


def depuis_toml(brut: object, contexte: str) -> Epinglage:
    table = _Table(brut, contexte)
    epinglage = Epinglage(
        nom=table.texte("nom"),
        depot=table.texte("depot"),
        licence=table.texte("licence"),
        revision=table.texte_facultatif("revision"),
        date_revision=table.date("date_revision", obligatoire=False),
        fichiers=tuple(_fichier(t) for t in table.tables("fichiers", obligatoire=True)),
    )
    table.terminer()
    if not epinglage.fichiers:
        raise EpinglageInvalide(f"{contexte} : aucun fichier")
    return epinglage


def _fichier(table: _Table) -> Fichier:
    fichier = Fichier(table.texte("chemin"), table.texte_facultatif("sha256"))
    table.terminer()
    return fichier


def dossier(epinglage: Epinglage, racine: Path) -> Path:
    if epinglage.revision is None:
        raise EpinglageInvalide(f"{epinglage.nom} : pas encore épinglé (aucune révision)")
    return racine / epinglage.nom / epinglage.revision


# --- relever (beko) ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Releve:
    revision: str
    date_revision: date
    fichiers: tuple[Fichier, ...]

    def en_toml(self, epinglage: Epinglage) -> str:
        """Le TOML complet, à recopier tel quel dans ``index/modeles/<nom>.toml``."""
        lignes = [
            f'nom = "{epinglage.nom}"',
            f'depot = "{epinglage.depot}"',
            f'licence = "{epinglage.licence}"',
            f'revision = "{self.revision}"',
            f"date_revision = {self.date_revision.isoformat()}",
        ]
        for f in self.fichiers:
            lignes += ["", "[[fichiers]]", f'chemin = "{f.chemin}"', f'sha256 = "{f.sha256}"']
        return "\n".join(lignes)


def choisir_revision(commits: Sequence[dict[str, object]], aujourd_hui: date) -> tuple[str, date]:
    """La révision la plus récente qui a au moins ``AGE_MINIMAL`` le jour ``aujourd_hui``."""
    eligibles = []
    for commit in commits:
        quand = datetime.fromisoformat(str(commit["date"]).replace("Z", "+00:00")).date()
        if quand <= aujourd_hui - AGE_MINIMAL:
            eligibles.append((quand, str(commit["id"])))
    if not eligibles:
        raise EpinglageInvalide(f"aucune révision n'a deux semaines au {aujourd_hui}")
    quand, revision = max(eligibles)
    return revision, quand


def relever(epinglage: Epinglage, client: httpx.Client, racine: Path, aujourd_hui: date) -> Releve:
    """Choisit la révision, télécharge chaque fichier à sa place et en relève le sha256.

    Les fichiers relevés sont ceux que l'épinglage désignera : une fois le TOML recopié,
    ``installer`` les trouve en place et ne télécharge rien de plus.
    """
    reponse = client.get(f"{HUB}/api/models/{epinglage.depot}/commits/main")
    reponse.raise_for_status()
    revision, quand = choisir_revision(reponse.json(), aujourd_hui)
    releves = []
    for f in epinglage.fichiers:
        cible = racine / epinglage.nom / revision / f.chemin
        partiel = cible.with_name(cible.name + ".partiel")
        releves.append(Fichier(f.chemin, _telecharger(client, epinglage, revision, f, partiel)))
        partiel.replace(cible)
    return Releve(revision, quand, tuple(releves))


# --- installer (beko, la CI) -------------------------------------------------------------------


def installer(epinglage: Epinglage, client: httpx.Client, racine: Path) -> list[str]:
    """Met en place les fichiers épinglés ; ceux déjà présents et justes ne sont pas retéléchargés.

    Chaque fichier est écrit en ``.partiel``, vérifié, puis renommé : un fichier en place a
    toujours la bonne empreinte. Rend une ligne par fichier.
    """
    if not epinglage.epingle:
        raise EpinglageInvalide(
            f"{epinglage.nom} : pas encore épinglé ; lancer d'abord"
            f" « pharmaflux index modele relever {epinglage.nom} » et recopier sa sortie"
        )
    base = dossier(epinglage, racine)
    lignes = []
    for f in epinglage.fichiers:
        cible = base / f.chemin
        if cible.exists() and _sha256(cible) == f.sha256:
            lignes.append(f"{f.chemin} : déjà en place")
            continue
        partiel = cible.with_name(cible.name + ".partiel")
        assert epinglage.revision is not None  # garanti par epingle
        obtenu = _telecharger(client, epinglage, epinglage.revision, f, partiel)
        if obtenu != f.sha256:
            partiel.unlink()
            raise EpinglageInvalide(
                f"{epinglage.nom}/{f.chemin} : sha256 {obtenu}, attendu {f.sha256} ; rien installé"
            )
        partiel.replace(cible)
        lignes.append(f"{f.chemin} : installé, sha256 vérifié")
    return lignes


def _telecharger(
    client: httpx.Client, epinglage: Epinglage, revision: str, f: Fichier, destination: Path
) -> str:
    """Télécharge ``f`` à ``revision`` dans ``destination`` ; rend son sha256."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = f"{HUB}/{epinglage.depot}/resolve/{revision}/{f.chemin}"
    empreinte = hashlib.sha256()
    with client.stream("GET", url) as reponse:
        reponse.raise_for_status()
        with destination.open("wb") as sortie:
            for morceau in reponse.iter_bytes(MORCEAU):
                empreinte.update(morceau)
                sortie.write(morceau)
    return empreinte.hexdigest()


def client_hub() -> httpx.Client:
    return httpx.Client(timeout=DELAI_S, follow_redirects=True)


# --- verifier (sans réseau) --------------------------------------------------------------------


def verifier(epinglage: Epinglage, racine: Path) -> list[str]:
    """Les écarts entre les fichiers en place et l'épinglage ; vide si tout est juste."""
    if not epinglage.epingle:
        return [f"{epinglage.nom} : pas encore épinglé (révision ou sha256 manquants)"]
    base = dossier(epinglage, racine)
    ecarts = []
    for f in epinglage.fichiers:
        chemin = base / f.chemin
        if not chemin.exists():
            ecarts.append(f"{epinglage.nom}/{f.chemin} : absent de {base}")
        elif _sha256(chemin) != f.sha256:
            ecarts.append(f"{epinglage.nom}/{f.chemin} : sha256 différent de l'épinglage")
    return ecarts


def _sha256(chemin: Path) -> str:
    empreinte = hashlib.sha256()
    with chemin.open("rb") as entree:
        while morceau := entree.read(MORCEAU):
            empreinte.update(morceau)
    return empreinte.hexdigest()


def aujourd_hui() -> date:
    return datetime.now(UTC).date()
