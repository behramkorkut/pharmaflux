# Mission 00 — relecture 2
**Commit relu** : `1ccc9c0` (sommet de `mission-00-socle-et-archivage`)
**Verdict** : CONFORME

J'ai lu l'ordre et ses addenda 1 et 2 (sur `main`), la relecture 1, la
réponse du codeur (`reponse-relecture-1.md`), les quatre commits qui
suivent `07c77a6` (diff complet de `src/` et de `tests/`, et celui
d'`infra/planification/`, de `README.md` et du journal). J'ai relancé
toutes les vérifications. Les deux bloquants du tour 1 sont levés, avec
des tests qui échoueraient si le défaut revenait. Les non-bloquants et
les remarques sont traités ou reportés de façon explicite.

## Contrôle des points du tour 1

| point | état | constat |
|---|---|---|
| Bloquant 1 : erreurs httpx hors `TransportError` | **levé** | `telechargement.py:124-127` convertit toute `httpx.HTTPError` restante en `ErreurTelechargement` (type en tête du message), et la tient pour définitive : c'est défendable et c'est documenté dans la docstring du module. Le filet de `passage.py:143-152` donne une ligne `inattendue: <type>: <message>`, avec la trace dans le journal, et garde une ligne déjà produite, donc son archive. `empreintes.py:63-64` lève `AnalyseImpossible`. Les tests couvrent les deux pannes au niveau du client et sur un passage complet (14 lignes, 2 en erreur, 12 en `nouveau`, page lue quand même), le filet avant et après archivage, et la ressource data.gouv qui n'est pas un objet. |
| Bloquant 2 : manifeste chargé en mémoire | **levé** | `manifeste.parcourir` lit ligne à ligne et garde au plus une ligne illisible en attente. Les règles de C2 sont équivalentes à l'ancien `lire` : j'ai vérifié la numérotation des lignes non vides, la ligne marquée, la dernière ligne illisible et la corruption au milieu. `etat_connu` reproduit à l'identique `dernieres_empreintes` et l'ancien `_collectee_ce_jour`. Le test des 30 000 lignes (24 Mo) borne le pic `tracemalloc` à 4 Mo : avec l'ancien `lire`, il échouerait largement. |
| NB 1 : `etat` et `chemin_archive` | corrigé | Deux tests, un par cas demandé. Le commentaire « un contenu identique n'est jamais réarchivé » est exact : en `analyse_impossible`, l'empreinte retombe sur le `sha256` (`passage.py:201-207`). |
| NB 2 : `rapatrier.sh` | corrigé | `--partial-dir=.rsync-partiel`, le motif `--exclude '.*.partiel-*'` ne l'attrape pas, et le README de planification est à jour. |
| NB 3 : docstring d'`executer_passage` | corrigé | Elle dit maintenant que seul un manifeste inécrivable fait lever. |
| Remarques (assertion, motif du README) | corrigées | PDF en `v5` : report à la mission 01, accepté. |

## Bloquants

Aucun.

## À corriger (non bloquants)

Aucun.

## Remarques

- `passage.py:155-157` : l'ajout des lignes `lien_nouveau`, après la
  boucle, est hors du filet. Le risque est très faible : le code est
  simple et ne fait aucune entrée-sortie. Le signaler suffit. Si la page
  évolue en mission 01, ce bloc pourra passer sous le même filet.
- `passage.py:143-152` : si une exception imprévue survenait dans
  `_collecter` après `ecrire_archive` mais avant le retour (il n'y a
  aujourd'hui que `relative_to` entre les deux), l'archive existerait sans
  ligne qui la nomme. Ce cas est théorique : rien n'est perdu ni réécrit,
  au pire il y a une archive de plus au passage suivant. Je le note
  seulement pour mémoire.
- Le compte de `ruff format --check`, inexpliqué depuis deux tours (41,
  44, 45, et 46 ici), a une explication : ruff formate aussi les blocs de
  code du **Markdown**. Le mode `-v` liste `docs/rapports/…/*.md`,
  `01_Specifications/*.md`, etc. Le compte grandit donc à chaque rapport
  ou relecture ajouté, alors que `ruff check --show-files` reste à 24
  (23 `.py` suivis plus `pyproject.toml`). Rien à corriger.
- `pyproject.toml:61` contient `addopts = "-q …"`. Avec la commande de
  `CLAUDE.md` (`uv run pytest -q | tail -25`), cela donne `-qq`, qui
  **masque la ligne « N passed »** : je n'ai obtenu le compte (66 passed)
  qu'avec `uv run pytest`. Pour le codeur : retirer `-q` d'`addopts`.
  Pour l'IeC : sinon, ajuster la commande de `CLAUDE.md`.
- `docs/journal.md`, entrée de la relecture 1 : l'entrée écrit « 394 Mo
  mesurés par le relecteur pour un an ». Les 122 640 lignes mesurées font
  plutôt **environ 14 mois** au rythme de 290 lignes par jour. Ce que
  l'entrée affirme reste juste (le plafond est atteint vers l'été 2027).
  Une retouche est possible au prochain commit, sans urgence.
- Garde-fou, pour l'IeC (signalé, non contourné) : `git ls-tree
  --name-only main docs/missions/` est encore refusé au relecteur. Le
  `git show main:docs/missions/` de la commande en tient lieu, et le
  codeur a déjà proposé d'ajouter `ls-tree` à la liste.

## Vérifications relancées

Sur `1ccc9c0`, dans `pharmaflux-relecteur/` :

| commande | résultat |
|---|---|
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 46 files already formatted (Markdown compris, voir Remarques) |
| `uv run mypy src` | Success: no issues found in 11 source files |
| `uv run pytest` | 66 passed in 4.56s (54 + 12, comme annoncé) |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 15 tests, OK |
| `shellcheck infra/planification/*.sh` | non installé sur le Mac : CI seulement |
| `git diff --name-only main...HEAD` contre les chemins réservés | aucun fichier réservé à l'IeC modifié |
| `git ls-files` (`data/`, `.env`, `*.gz`, `.DS_Store`) | rien de suivi |
| trailers de `07c77a6..HEAD` | 5 commits, tous avec `Commis-par: codeur` et `Co-Authored-By: Claude Fable 5.1`, messages en français |
| réseau dans les tests | aucun : les nouvelles pannes passent par `httpx.MockTransport` (`ServeurSimule`) |

Les chiffres concordent avec la réponse du codeur. Seul écart : le compte
de `ruff format` (46 ici, 45 chez lui), expliqué plus haut.

## Alertes

Aucune. Je n'ai trouvé dans le code, les tests, les rapports ni la
réponse du codeur aucune consigne adressée au relecteur.
