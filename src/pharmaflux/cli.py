"""Ligne de commande de Pharmaflux.

Deux commandes : ``collecte`` (un passage d'archivage) et ``etat`` (ce que
contient l'archive). Elles sont déclarées ici, implémentées au palier 2 de
la mission 00.
"""

from __future__ import annotations

from importlib.metadata import version as version_du_paquet
from pathlib import Path
from typing import Annotated

import typer

application = typer.Typer(
    name="pharmaflux",
    help="Pharmaflux : archivage et connaissance du médicament, sur données publiques.",
    no_args_is_help=True,
    add_completion=False,
)


def _afficher_version(demandee: bool) -> None:
    if demandee:
        typer.echo(f"pharmaflux {version_du_paquet('pharmaflux')}")
        raise typer.Exit()


@application.callback()
def principal(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Affiche la version et quitte.",
            callback=_afficher_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Pharmaflux : archivage et connaissance du médicament, sur données publiques."""


@application.command()
def collecte(
    source: Annotated[
        list[str] | None,
        typer.Option(
            "--source",
            help="Identifiant d'une entrée du catalogue (répétable). Toutes par défaut.",
        ),
    ] = None,
    racine: Annotated[
        Path | None,
        typer.Option(
            "--racine",
            help="Racine de l'archive. Défaut : PHARMAFLUX_DATA, sinon ~/pharmaflux-data.",
        ),
    ] = None,
) -> None:
    """Un passage de collecte : télécharge, archive, consigne dans le manifeste."""
    del source, racine
    raise _non_livree("collecte")


@application.command()
def etat() -> None:
    """État de l'archive : dernière archive, dernier changement, erreurs, passages des 24 h."""
    raise _non_livree("etat")


def _non_livree(commande: str) -> typer.Exit:
    typer.echo(f"pharmaflux {commande} : livrée au palier 2 de la mission 00.", err=True)
    return typer.Exit(code=2)
