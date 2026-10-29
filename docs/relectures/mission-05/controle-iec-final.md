# Mission 05 — revue finale de l'IeC

**Commit revu** : `3cb10ba` (`pr.md`), sur le code de `c53d714`. Il est revu
contre l'ordre et l'addendum 1 (`b5b9420`), les trois contrôles de palier et
les deux relectures (la seconde : CONFORME). **Verdict : fusion autorisée,
après un commit de `pr.md` qui apporte les deux corrections ci-dessous.**
Le code n'est pas à reprendre.

## Revérifié par l'IeC

Dans le dossier du codeur, arbre propre sur `3cb10ba` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 51 fichiers |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true`, courtier présent | 500 passed en 2 min 05 s, dont les tests d'intégration |
| `git log origin/main..main` (dans `pharmaflux/`) | vide : `main` est poussé (`b5b9420`) |

**Le correctif fait après la relecture 2** (`c53d714`) est vérifié dans le
code. La date seule et l'instant complet passent par le même `try`. Un
30 février ou un treizième mois donne donc « instant illisible », en
code 2. Le message de `uri_entrepot` nomme aussi les caractères non
imprimables. Deux cas de test le couvrent. Il ne demande pas de troisième
relecture.

**Le circuit est complet** :
- le §0 et l'addendum 1 ;
- trois paliers contrôlés, dont les contrôles sont commis tels quels ;
- la relecture 1 NON CONFORME, avec un bloquant réel (l'URI de l'entrepôt
  encodée), corrigé et testé sous un chemin à espace et accent ;
- la relecture 2 CONFORME.

La clôture de l'ordre est atteinte : beko, sur le Mac, a enchaîné
`make rebatir`, `make demo` puis `make silver`, avec pour résultat 22/22
archives conformes.

## Corrections demandées dans `pr.md`

1. **La base de la branche** (lignes 3 et 4). La branche part de
   `cfc1fea`, pas de `b5b9420`. L'addendum 1 (`b5b9420`) a été commis sur
   `main` après la création de la branche, et il n'est pas dans la branche
   (`git merge-base` donne `cfc1fea`). Écris-le ainsi : « depuis `cfc1fea`
   ; `main` porte en plus l'addendum 1 (`b5b9420`), sans conflit puisque la
   branche ne touche pas à `docs/missions/` ».
2. **La phrase sur PyArrow** (section « Mémoire »). « L'import seul laisse
   150 Mo » se lit comme si l'import pesait 150 Mo. Le §0 J dit : les trois
   bibliothèques importées pèsent **102 Mo**, ce qui **laisse 150 Mo** sous
   la cible des 256 Mo. Reprends la phrase dans ce sens.

## Remarques, sans correction

- **La CI** : la durée de l'étape `make silver` sera reportée par beko après
  le premier passage, comme `pr.md` le dit. Si l'étape échoue sur le runner
  amd64, on traite l'échec par un nouveau commit, comme à la mission 04.
- **Le PRD** : l'IeC reporte au §9, en v0.7 avec l'ordre suivant, que le
  silver tourne sur le Mac en v1, les mesures de mémoire et le seuil de
  512 Mo.
- **Le témoin `data/lakehouse-temoin-d1`** : beko l'efface s'il ne l'a pas
  déjà fait. Il est hors git.
