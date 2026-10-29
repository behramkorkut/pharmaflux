"""``python -m pharmaflux`` : la même ligne de commande que ``pharmaflux``.

L'index lance le calcul des fragments dans un sous-processus (ADR 0011) par
``sys.executable -m pharmaflux``, sans dépendre du script installé.
"""

from pharmaflux.cli import application

application()
