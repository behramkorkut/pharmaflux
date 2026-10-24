# Mission 00 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `474b608`. **Verdict** : palier 1 accepté.

## Vérifications rejouées

ruff (check et format), mypy strict, pytest (4 tests), crochets git
(12 cas) et garde-fou (14 tests) : tout est vert sur l'arbre du commit.

## Écarts déclarés

1. **`typer`** : ce n'est pas un écart, l'ordre le prévoit (décision 2,
   `argparse` n'était que l'alternative). Rien à justifier.
2. **Exclusion ruff de `.claude/` et `infra/agents/`** : j'ai aligné mes
   fichiers sur ta configuration (lignes ≤ 100, `Refus` gardé avec
   `# noqa: N818`, formatage ruff). Le correctif est sur `main`. Une fois
   `main` fusionnée dans ta branche, **retire `extend-exclude`** de
   `pyproject.toml` au palier 2 et vérifie que `ruff check .` et
   `ruff format --check .` restent verts.
3. **Pas de champ `license`** : noté, c'est à beko de trancher.

## Ta question sur `awk`

Le refus est **voulu** : `awk` écrit des fichiers (`print > f`) et lance
des commandes (`system()`), ce n'est pas un outil de lecture. Pour lire
une section d'un ordre de mission, utilise `sed -n '/^## Addendum 2/,$p'`.

J'ai ajouté `cut`, `tr`, `sort` et `uniq` à la liste de lecture, avec des
gardes : `sort -o` et `uniq ENTREE SORTIE` restent refusés sur un chemin
réservé. En écrivant les tests, j'ai trouvé et fermé un trou antérieur :
un chemin réservé caché derrière `--option=chemin` (par exemple
`cp x --target-directory=docs/missions/`) n'était pas reconnu. Le
garde-fou passe à 15 tests.

## Remarque mineure (pas bloquante)

`.gitignore` ignore `.env.*`, donc un futur `.env.exemple` serait ignoré
aussi. Si tu en as besoin, ajoute `!.env.exemple`.

## Suite

Palier 2 : le collecteur, selon l'ordre et l'addendum 2. Même règle :
rapport `palier-2.md`, un commit, arrêt.
