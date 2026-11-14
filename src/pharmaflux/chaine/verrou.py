"""Le verrou de la chaîne : une seule commande de la chaîne à la fois.

Le remplissage, le passage horaire et les vérifications prennent le même
verrou, sans attendre : deux étapes ne tournent jamais ensemble. Le verrou est
un ``flock`` sur un fichier du dérivé ; il tombe avec le processus, même tué.
Le fichier n'est jamais vidé ni effacé : qui peut le lire peut prendre le
verrou (la bascule de version le fait, par la commande ``flock``).
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class VerrouTenu(Exception):  # noqa: N818 (nom français voulu)
    """Une autre commande de la chaîne tient le verrou."""


@contextmanager
def verrou(chemin: Path) -> Iterator[None]:
    """Tient le verrou le temps du bloc, ou lève ``VerrouTenu`` tout de suite."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    # En lecture : flock n'a pas besoin d'écrire, et un compte qui ne fait que lire le dérivé
    # prend le même verrou. Le descripteur n'est pas hérité par les étapes (O_CLOEXEC) : c'est
    # le groupe de contrôle de l'unité, sur le VPS, qui garantit qu'elles meurent avec la chaîne.
    try:
        descripteur = os.open(chemin, os.O_RDONLY | os.O_CREAT | os.O_CLOEXEC, 0o640)
    except PermissionError:  # le fichier existe, le dossier n'est pas à nous
        descripteur = os.open(chemin, os.O_RDONLY | os.O_CLOEXEC)
    try:
        try:
            fcntl.flock(descripteur, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise VerrouTenu(f"une autre commande de la chaîne tourne (verrou {chemin})") from exc
        yield
    finally:
        os.close(descripteur)
