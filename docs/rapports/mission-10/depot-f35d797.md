# Mission 10 — dépôt de `f35d797` sur le VPS-1

## Synthèse

Le code de `f35d797` (retouches du palier 2, contrôle `controle-palier-2-retouches.md`) est
déposé. `courante` est basculé **sous le verrou de la chaîne**, le 15/11 à 17:50:23 UTC.
- La CI est verte : run `43732456597`, à la tentative 3. Les deux premières ont échoué sur la
  règle A2, le réessai du registre, noté pour la mission 11.
- La version `95a35ac`, jamais mise en service, est retirée. `eecc9f3` reste, pour un retour
  en arrière.
- La condition de la question 2 tient : `src/` ne change que dans `chaine/` et `cli.py`
  depuis `eecc9f3`.

Ce commit corrige aussi le README (« Avant 9b, le code » : `sudo ls -l`), et porte le fichier
de contrôle tel quel.

## Détail

| commande (par `ssh pharmaflux-vps`) | résultat |
|---|---|
| `git archive --prefix=versions/f35d797…/ f35d797 \| … tar -x -C /srv/pharmaflux/code` | fait |
| `uv sync --directory …/versions/f35d797… --frozen --no-dev --no-editable --compile-bytecode` (`UV_PYTHON_INSTALL_DIR`, `UV_LINK_MODE=copy`) | fait |
| `ln -sfn versions/f35d797… …/courante.neuf && flock -n /srv/pharmaflux/derive/chaine/verrou mv -T …/courante.neuf …/courante` | `bascule -> 0` ; `readlink` : `versions/f35d79702a8d66fa8cb1ca2f1c09b41e062fe79b` |
| `rm -r /srv/pharmaflux/code/versions/95a35ac19195111f276949a54b654ec0bab00192` | fait ; il reste `eecc9f3…` et `f35d797…` |
| `find /srv/pharmaflux/code ! -group pharmaflux-chaine` | rien |
| `find /srv/pharmaflux/code -type d ! -perm -2000` | rien |
| `…/courante/.venv/bin/pharmaflux --version` | `pharmaflux 0.1.0` |
| `cat …/courante/VERSION` | `f35d79702a8d66fa8cb1ca2f1c09b41e062fe79b` |
| `readlink -f …/courante/.venv/bin/python` | `/srv/pharmaflux/code/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12` |

**La condition de la question 2** : `git diff --stat eecc9f3 f35d797 -- src`.

```text
 src/pharmaflux/chaine/chemins.py      |   5 +
 src/pharmaflux/chaine/etapes.py       |   3 +
 src/pharmaflux/chaine/etat.py         | 357 ++++++++++++++++++++++++++++++++++
 src/pharmaflux/chaine/formats.py      | 100 ++++++++++
 src/pharmaflux/chaine/horaire.py      | 221 +++++++++++++++++++++
 src/pharmaflux/chaine/passage.py      |  64 +++++-
 src/pharmaflux/chaine/remplissage.py  |  42 ++++
 src/pharmaflux/chaine/verification.py |  51 +++++
 src/pharmaflux/cli.py                 | 146 +++++++++++++-
 9 files changed, 973 insertions(+), 16 deletions(-)
```

Rien hors de `chaine/` et `cli.py` : aucun format du dérivé bâti par `eecc9f3` n'a changé, et
le témoin qu'écrira le premier passage dira vrai.

**`chaine etat`**, depuis la version en service, avant la mise en service :

```text
chaîne : jamais lancée ; code f35d797, dérivé bâti par inconnu (pas de témoin)
collecte             dernier passage 20261115T171703Z ; 0 non traité(s) par la chaîne
remplissage          2026-11-14T23:28:34Z, 13885.1 s, complet, code 0
disque               22.4 Gio libres sur 37.6 Gio
formats              pas de témoin (écrit au premier passage complet)
dernière erreur      aucune
```

**Au premier passage horaire**, je surveille deux choses :
- le résident de l'étape `index` : il atteint 481 Mo en CI. Au-dessus de 450 Mo, ou si un
  processus est tué, je le signale aussitôt à l'IeC ;
- la durée du passage à vide : 10 s en CI. Au-delà d'une minute, je propose le court-circuit.
