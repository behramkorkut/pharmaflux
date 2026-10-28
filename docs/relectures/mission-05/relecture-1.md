# Mission 05 — relecture 1
**Commit relu** : `f0aac28` (sommet de `mission-05-silver-et-etat-a-une-date`)
**Verdict** : NON CONFORME

Relu contre l'ordre de mission et son addendum 1 (`main`), les rapports
des paliers 1 à 3 et les trois contrôles de l'IeC. Les décisions 1 à 7
sont tenues, les écarts annoncés sont justifiés et ont été acceptés par
l'IeC. Un seul bloquant, trouvé en exécutant le code hors du chemin du
Mac : le silver écrit hors de son entrepôt quand le chemin du clone
contient un espace ou un accent.

## Bloquants

1. `src/pharmaflux/silver/entrepot.py:121-125` (`_catalogue`, `warehouse=absolu.as_uri()`)
   — **constat** : `Path.as_uri()` encode les caractères réservés
   (`dossier avec espace é` → `dossier%20avec%20espace%20%C3%A9`), et
   PyIceberg 0.12.0 écrit ses fichiers au chemin encodé **pris à la
   lettre**. Reproduit en dehors du dépôt : `Entrepot.creer(<tmp>/"dossier
   avec espace é")`, une table, un `append` d'une ligne ; le dossier
   demandé ne contient que `catalogue.sqlite`, et les Parquet comme les
   `metadata.json` sont dans un dossier **frère**,
   `<tmp>/dossier%20avec%20espace%20%C3%A9/`. La lecture marche quand même
   (PyIceberg et `chemins_parquet` relisent le même chemin encodé), donc
   rien ne le signale.
   — **pourquoi c'est bloquant** : l'ordre fixe le silver dans « un
   dossier sous `data/`, hors de git ». Pour un clone sous `~/Mes
   projets/pharmaflux` (ou tout chemin accentué, courant sur un Mac
   français), `make silver` écrit dans `~/Mes%20projets/pharmaflux/…`,
   hors du dépôt : hors du `.gitignore` de `data/`, hors de portée de
   `make rebatir`, et `Entrepot.creer` ne voit pas le reliquat. C'est le
   parcours d'un recruteur qui clone le projet.
   — **attendu** : un URI d'entrepôt qui désigne le dossier réel (par
   exemple `"file://" + str(absolu)`, à vérifier contre PyIceberg), ou un
   refus explicite d'un chemin que `as_uri()` modifierait ; puis un test
   sous `tmp_path / "avec espace é"` qui construit une table et vérifie que
   **tous** les fichiers écrits sont sous le dossier de l'entrepôt, et que
   `chemins_parquet` rend des chemins qui existent. Une ligne dans l'ADR
   0009 (paragraphe sur les chemins absolus, K.3).

## À corriger (non bloquants)

2. `src/pharmaflux/silver/verification.py:221-262` — sur les cinq
   invariants du SCD2, **un seul** est montré capable d'échouer (les
   comptes contre les bilans, `test_verifier_voit_une_version_qui_manque`).
   Les requêtes « plusieurs versions ouvertes », « fin ≤ début »,
   « chevauchement » et « identifiants répétés » ne tombent dans aucun
   test : une faute dans leur SQL (une jointure qui ne rend jamais rien)
   passerait inaperçue, et l'addendum (G) en fait un motif de code 2.
   Attendu : un test qui ajoute à une table construite, par un `append`
   direct, une version fautive pour chaque invariant, et vérifie le
   message et le code 2.
3. `tests/test_silver_construction.py:181-193` — `COPY … TO`, `ATTACH` et
   `INSTALL iceberg` sont refusés par le filtre de type d'énoncé
   d'`executer`, **avant** d'atteindre DuckDB : la seconde barrière
   (`enable_external_access = false` sur la connexion) n'est démontrée que
   pour `read_csv`, `read_parquet` et `SET`. Attendu : les mêmes trois
   énoncés passés directement à `con.execute(…)`, avec `duckdb.Error` et
   aucun fichier créé, comme c'est déjà fait pour le `SET`.
4. `src/pharmaflux/silver/etat.py:35-51` (`lire_instant`) — acceptés alors
   que la règle retenue est « UTC, à la seconde, refus d'une fraction » :
   `2026-10-26T14:00:00.000Z` (une fraction écrite, nulle),
   `2026-10-26T14:00Z` (sans les secondes), `2026-10-26 14:00:00Z` et
   `20261026T140000Z`. Soit les refuser (fraction écrite, forme
   compacte), soit écrire dans l'aide et l'ADR ce qui est accepté ; un cas
   de test dans `test_lire_instant_utc_a_la_seconde` dans les deux cas.
5. `src/pharmaflux/silver/etat.py:30,172-185` — `colonnes_de_donnees` ne
   sert qu'à un test (`test_silver_construction.py:129`), et `__all__`
   réexporte `COLONNES_VERSION`, importé seulement pour cela. Code mort
   léger : à retirer (le test peut appeler `colonnes_du_contrat`).

## Remarques

- README, second exemple : `A=2026-10-26T14:17:39Z` est l'instant même de
  l'archive écartée, ce qui est juste (début inclus), mais la commande seule
  ne **montre** pas que « l'état n'a pas bougé ». Une seconde commande à
  `14:17:38Z` qui rend le même compte (ou `silver sql` sur les fins de
  validité de ce jour-là) rendrait la démonstration autoportante.
- `pyproject.toml` : la contrainte `tzdata<2026.6` vise un paquet absent de
  `uv.lock` (il n'est tiré que sous Windows) ; elle est sans effet ici et
  inoffensive. Les commentaires des contraintes ne sont pas alignés
  (ligne `sqlalchemy`).
- Le contrôle du palier 3 demande de rejouer **toute** la non-régression
  de l'ordre sur le commit testé de `pr.md` (`profil`, `questions
  verifier`, `evenements` contre `1af4ef9`) : je ne l'ai pas rejouée sur
  `~/pharmaflux-data` (hors de mon dossier), seulement `demo verifier`.
- Relus sans remarque : `appliquer_lot` (refus avant la transaction, rangs
  d'un fichier ligne à ligne, doublons par `id` dans le lot et contre la
  table), le consommateur (position dans le même commit que le lot,
  contrôles de départ, aucun groupe ni commit sur le courtier), la clé de
  partition (la clé du médicament : toutes les occurrences d'une empreinte
  vont sur la même partition, l'ordre par partition suffit), `silver sql`
  (connexion sans accès externe, puis verrouillée), le test des imports
  paresseux, le `Makefile` (GNU Make 3.81) et l'étape de CI (après `make
  demo`, avant le `down -v`, job `verifier` inchangé).
- Périmètre : aucun chemin réservé à l'IeC dans `git diff --stat
  main...HEAD` (les contrôles de `docs/relectures/` sont commis tels
  quels), rien de `data/`, aucun secret, aucun chemin du poste dans le
  diff ; tests unitaires hors réseau, tests du courtier marqués
  `integration`. Historique : un commit par palier, trailers `Commis-par:
  codeur` et `Co-Authored-By` sur les sept commits, messages en français.

## Vérifications relancées

Sur `f0aac28`, arbre propre, courtier `pharmaflux-redpanda` en marche.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 204 files already formatted |
| `uv run mypy src` | Success: no issues found in 51 source files |
| `GITHUB_ACTIONS=true uv run pytest -q` | **498 passed** en 2 min 10 s (tests `integration` compris, courtier présent) — comme les rapports |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | 21 tests, OK |
| `uv run pharmaflux demo verifier` | conforme |
| `make -n silver etat` | `silver consommer --entrepot data/demo/lakehouse`, `silver verifier … --sortie data/demo --racine demo/archive`, `silver etat … --entite bdpm.presentations --a 2026-10-26T14:00:00Z` |
| reproduction du bloquant 1 (entrepôt sous un chemin à espace et accent, dans le dossier temporaire de la session, effacé ensuite) | Parquet et métadonnées écrits dans le dossier frère encodé `%20…%C3%A9` |
| `lire_instant` sur quatre formes limites (point 4) | les quatre acceptées |

## Alertes

Aucune.
