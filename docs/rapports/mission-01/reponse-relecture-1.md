# Mission 01 — réponse à la relecture 1

Relecture : `docs/relectures/mission-01/relecture-1.md` (commit relu
`7c5d10e`, verdict **CONFORME**, 0 bloquant), commitée telle quelle avec
cette réponse. Corrections par quatre commits, un par sujet : `f527e9c`
(point 1), `7b826d5` (points 2 et 4, même fichier de test), `60be1d2`
(point 3), `f09741e` (remarques).

## Bloquants

Aucun.

## À corriger (non bloquants)

**1. Bornes numériques du profil** — corrigé, `f527e9c`.

- `_lire_nombre` reçoit le type de la colonne et ne rend un `Decimal` que
  si `verifier_valeur` accepte la valeur : « NaN », « 1e9 », « Infinity »,
  « 24.34 » ou « 1,003,48 » restent des anomalies comptées
  (`decimal_illisible`) et n'entrent plus dans le minimum ni le maximum.
  La même règle vaut pour une colonne `entier` (« 1,5 » est hors bornes).
  Le cas particulier « plus d'une virgule » disparaît : il est couvert.
- Les dates ne changent pas : une date lisible mais hors plage (1910)
  reste dans les bornes. C'est voulu : la voir en minimum est l'alerte.
- Test `test_bornes_sans_les_nombres_non_conformes` : les quatre premières
  lignes de la fixture des présentations, trois prix remplacés par « NaN »,
  « 1e9 » et « Infinity » ; les bornes valent le seul prix conforme, quatre
  valeurs distinctes, trois `decimal_illisible`. Avant le correctif, ce test
  levait `decimal.InvalidOperation`, comme ton essai.
- `docs/donnees/` régénéré sur l'archive du 24/10 : identique à la ligne
  « Produit » près. Aucune borne publiée ne reposait sur une valeur non
  conforme.

**2. Décimales non ASCII** — corrigé, `7b826d5`.

- `decimales.isascii()` s'ajoute à `isdigit()`, comme `_entier` le fait
  pour la partie entière. Deux cas dans `test_verifier_valeur` : « 1,²³ »
  et « 1,٢٣ » (chiffres arabo-indiens, `isdigit` vrai aussi).

**3. Archive d'un attendu et contrat nommé** — corrigé, `60be1d2`.

- Option « dossier » retenue, un cran plus stricte : `archive` doit avoir
  exactement la forme `bronze/<source>/<fichier du contrat>/<jour de
  référence>/<nom>.gz`, en cinq segments. Trois messages distincts : le
  dossier (« est un chemin bronze/bdpm/CIS_bdpm.txt/…, le dossier bronze
  de bdpm.specialites »), le jour, le nom. Un `..` ou un segment de trop
  tombe sur le troisième. `Contrat.dossier_bronze` (nouvelle propriété,
  source déduite de l'identifiant comme le profil le fait déjà) porte le
  préfixe.
- Le cache de `verifier_jeu` est indexé par (archive, contrat), pour un
  `Jeu` construit sans passer par le chargeur. Après le chargeur, c'est
  redondant : une archive n'a qu'un dossier, donc qu'un contrat.
- Quatre cas de refus ajoutés (dossier d'un autre fichier, `..`, segment
  de trop, nom sans `.gz`) ; l'ancien cas `silver/` donne le message du
  dossier. Jeu v0 et jeu d'essai inchangés ; sur le Mac, toujours 25
  conformes, 5 non calculables, 10 sans attendu.

**4. Test des règles bloquantes** — corrigé, `7b826d5`.

- `import re` et `REGLES_BLOQUANTES` importés en tête, `CODE_CIS` constante
  du module pour les trois cas `code`. Le test compare l'ensemble aux
  quatre règles ; ruff (SIM300) veut la constante à droite, d'où
  `assert {…} == REGLES_BLOQUANTES`. La « raison » des clés uniques a son
  test, `test_une_cle_unique_n_a_pas_de_raison`, avec l'identifiant du
  contrat en message.

## Remarques

- **`QUESTIONS_PAR_DEFAUT` relatif au dossier courant** — dit, `f09741e`,
  dans l'aide de `--questions` et dans `evaluation/README.md` (lancer
  depuis la racine, ou donner le chemin complet du jeu). Pas de résolution
  par rapport au dépôt : le jeu est un fichier de données, et la commande
  doit marcher là où le dépôt n'est pas (copie rapatriée).
- **Ligne faite de séparateurs** — voulu, dit dans l'ADR 0002
  (conséquences, `f09741e`) : une ligne de blancs ne porte aucune clé et
  ne dit rien d'une colonne ; elle est signalée comme ligne vide, pas
  comme une ligne de valeurs toutes manquantes.
- **`_decoder` ne signale que le premier octet** — inchangé. Tant que
  l'encodage est bloquant, le profil s'arrête de toute façon aux
  anomalies. Reliquat pour le Lot 1 : compter les lignes touchées si un
  jour l'encodage se lit en continuant.
- **Cible d'un lien vérifiée deux fois** — inchangé, reliquat pour le Lot 4
  (Open Medic) : une lecture par archive dans `profiler_racine`.
- **Script jetable cité au §0** — une phrase ajoutée au point 9 de
  `points-a-trancher.md`, marquée comme ajout après la relecture 1 : le
  script n'existe plus, `pharmaflux profil` refait ces chiffres,
  `docs/donnees/` en est la sortie.
- **Historique** — rien à faire.
- **Garde-fou, boucle `for` sur `docs/relectures/`** — pour beko et l'IeC :
  `.claude/` m'est réservé en lecture, je n'y touche pas. Rien n'a été
  contourné de mon côté non plus.

## Vérifications locales (commit testé : `f09741e`, arbre propre hors la relecture non commise)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 94 files already formatted |
| `uv run mypy src` | Success: no issues found in 22 source files |
| `uv run pytest -q` | 237 passed (229 + 8 : un test du profil, deux cas décimaux, un test de clé, quatre cas de refus du jeu) |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 16 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` | rien, code 0 |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` | 11 fichiers, 0 bloquante, code 0 |
| `… profil --markdown <jetable>` puis `diff -r` avec `docs/donnees/` | identiques, à la ligne « Produit » près |
| `uv run pharmaflux questions verifier --racine ~/pharmaflux-data` | 40 questions : 25 conformes, 5 non calculables, 10 sans attendu, code 0 |
| `uv build --wheel` (dossier jetable) | onze contrats TOML, `evaluation/` du paquet et `tomlstrict.py` présents |

Archive du Mac lue seulement ; aucune requête réseau ; aucun refus du
garde-fou pendant ces corrections.

## Reliquats (acceptés ou décidés, pour les missions suivantes)

- `_decoder` : nombre de lignes touchées par un octet illisible (Lot 1).
- `profiler_racine` : une lecture par archive, cibles comprises (Lot 4).
- Jeu v1 (décisions de l'IeC au contrôle du palier 4) : `alternatives-004`
  retirée et remplacée par une question sur le groupe générique (jointure
  GENER × CIP) sans réutiliser l'identifiant ; `avis_has-005` devient une
  réponse avec réserve ; objectif cent questions au Lot 3.
