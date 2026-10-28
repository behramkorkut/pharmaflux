# Mission 05 — palier 1 : silver depuis les fichiers, état à une date, vérification (décisions 1, 2 et 4)

Addendum 1 lu (`b5b9420`). Python pur : aucune commande `docker`, `colima`
ni `make` ; `~/pharmaflux-data` en lecture seule (non-régression) ; aucune
requête vers les sources ; aucun refus du garde-fou. Le courtier du projet
tournait sur le Mac, les 9 tests d'intégration existants ont donc tourné.

**Fait**

- **Dépendances** (décision 1, A) : `pyiceberg[sql-sqlite]>=0.12.0`,
  `pyarrow>=26.0.0`, `duckdb>=1.5.6` dans `dependencies` ;
  `pyarrow-stubs>=20.0.0.20260819` en dev ; `[tool.uv]
  constraint-dependencies` avec un commentaire par ligne : `duckdb<2`,
  `sqlalchemy>=2.0.54,<2.0.55`, `cachetools<7.2.2`, `python-dateutil<3`,
  `tzdata<2026.6` (2.0.55 est du 16/10, 7.2.2 du 15/10 : deux plafonds de
  plus que ceux prévus par l'addendum). **Audit du verrou** : `git diff
  --stat` → `uv.lock | 895 +`, `pyproject.toml | 15 +` ; `awk` sur les
  couples nom et version, 33 avant, 57 après, **aucun paquet déjà verrouillé
  n'a changé de version**, aucun retiré ; 24 ajoutés, `upload-time` le plus
  ancien de chaque version, **tous au 14/10/2026 ou avant** :

  | paquet | version | publié le | paquet | version | publié le |
  |---|---|---|---|---|---|
  | `pyiceberg` | 0.12.0 | 01/09/2026 | `pyarrow` | 26.0.0 | 09/10/2026 |
  | `duckdb` | 1.5.6 | 28/09/2026 | `sqlalchemy` | 2.0.54 | 15/09/2026 |
  | `pyarrow-stubs` | 20.0.0.20260819 | 19/08/2026 | `pydantic` | 2.14.1 | 11/10/2026 |
  | `pydantic-core` | 2.50.1 | 11/10/2026 | `cachetools` | 7.2.1 | 05/10/2026 |
  | `tenacity` | 9.2.1 | 07/10/2026 | `pyroaring` | 1.2.0 | 02/10/2026 |
  | `charset-normalizer` | 3.5.2 | 30/09/2026 | `mmh3` | 5.3.1 | 30/09/2026 |
  | `pyparsing` | 3.3.3 | 20/09/2026 | `fsspec` | 2026.9.0 | 18/09/2026 |
  | `urllib3` | 2.8.0 | 15/09/2026 | `greenlet` | 3.5.6 | 14/09/2026 |
  | `click` | 8.5.0 | 26/08/2026 | `typing-inspection` | 0.4.4 | 12/08/2026 |
  | `annotated-types` | 0.8.0 | 23/07/2026 | `requests` | 2.34.2 | 14/05/2026 |
  | `zstandard` | 0.25.0 | 14/09/2025 | `six` | 1.17.0 | 04/12/2024 |
  | `python-dateutil` | 2.9.0.post0 | 01/03/2024 | `strictyaml` | 1.7.3 | 10/03/2023 |

  `greenlet` n'était pas dans ma liste du §0 : SQLAlchemy le tire sur
  CPython. **`pyarrow-stubs` est retenu** : `mypy --strict` passe sur 50
  fichiers avec **zéro `type: ignore`**. Les stubs décrivent PyArrow 20 et
  n'ont rien ignoré de ce que le silver emploie (`pa.field`, `pa.table`,
  `from_pylist`, `dataset`, `compute`) ; un seul détour a été nécessaire,
  pour **PyIceberg**, pas pour PyArrow : ses prédicats (`In`, `IsNull`…)
  sont des modèles pydantic dont mypy ne voit que l'init synthétisé des
  champs, et `pharmaflux/silver/expressions.py` les construit une fois pour
  toutes dans des fonctions typées (`dans`, `est_nul`, `egal`,
  `inferieur_ou_egal`, `superieur`, `et`, `ou`).
- **Paquet `pharmaflux.silver`** (décision 2, B et C) : `__init__`
  (constantes, exceptions `SilverRefuse` et `FluxIncoherent`, la variable
  `ARROW_DEFAULT_MEMORY_POOL=system` posée avant tout import de PyArrow) ;
  `entrepot` (catalogue SQL de PyIceberg sur `catalogue.sqlite`, entrepôt
  `file://` absolu, `Entrepot.creer` refuse un dossier non vide, `ouvrir`
  refuse sans catalogue, tables `bdpm.<entite>` avec les propriétés
  `pharmaflux.entite`, `pharmaflux.version_contrat`, `pharmaflux.origine`,
  `chemins_parquet` qui refuse un fichier de suppression) ; `schema` (les
  colonnes du contrat dans l'ordre du contrat, puis les treize colonnes de
  version du §0 B, `identite` en clé JSON du message ou `<empreinte>#<rang>`,
  `anomalies` en `list<struct<colonne, regle>>`, `ColonnesVersion` qui
  accumule les ouvertures en colonnes sans dictionnaire) ; `application`
  (`appliquer_lot` : doublons par `id` contre la table et dans le lot, scan
  des versions ouvertes par identité ou par empreinte, SCD2 dans l'ordre du
  lot, rangs comptés comme `appliquer`, refus `FluxIncoherent` sans rien
  écrire, **une transaction** `set_properties` + `delete` + `append`) ;
  `construction` (`construire` : un lot d'au plus `--lot` événements par
  commit, le nom du fichier dans le résumé du snapshot, refus d'un entrepôt
  non vide ou d'une sortie sans événements).
- **Commandes** (décision 4, E à G) : `silver construire`, `silver etat`
  (instants UTC à la seconde, refus sans fuseau ou avec fraction, date seule
  = minuit UTC ; filtre `--ou colonne=valeur` poussé à PyIceberg ; `--format
  jsonl|tableau|csv`, `--colonne` ; code 0 et message hors de la fenêtre),
  `silver sql` (ci-dessous), `silver comparer A B` (toutes les colonnes de
  données et de version, `EXCEPT ALL` dans les deux sens, exemples cités ;
  snapshots, fichiers et propriétés exclus), `silver verifier` (bilans →
  archives et verdicts ; snapshot recalculé depuis le bronze et réduit ligne à
  ligne sans construire l'état complet ; archive écartée = état du dernier
  retenu ; en attente dite, non vérifiée ; invariants du SCD2 en DuckDB : une
  seule version ouverte par identité, aucun chevauchement, `fin > debut`,
  identifiants d'événements uniques, comptes égaux aux bilans ; code 2).
  Imports paresseux : les cinq commandes importent le silver dans leur corps,
  et un test en sous-processus vérifie que `import pharmaflux.cli` ne charge
  ni `pyarrow`, ni `pyiceberg`, ni `duckdb` (`--version` : 48 Mo résidents,
  45 pour `typer`, `confluent_kafka` et `httpx` seuls).
- **`silver sql` reste au palier 1, en lecture seule**, avec un écart à la
  lettre de l'addendum : sur la maquette, avec `allowed_directories` limité à
  l'entrepôt puis `enable_external_access = false`, les cinq refus demandés
  tenaient, mais **`COPY (SELECT 1) TO '<entrepôt>/x.csv'` passait** : un
  dossier autorisé l'est en écriture aussi. DuckDB ne reçoit donc **aucun
  accès fichier** : chaque table lui est donnée comme un `pyarrow.dataset`
  sur ses Parquet (lu par Arrow, filtres poussés), la connexion naît avec
  `enable_external_access = false` et les deux `autoload`/`autoinstall` à
  faux, puis `SET TimeZone = 'UTC'` et `SET lock_configuration = true` ; une
  requête à la fois, et seulement un `SELECT` ou `EXPLAIN`
  (`duckdb.extract_statements`). Tests de refus : `COPY … TO` (hors et
  **dans** l'entrepôt), `read_csv` hors de l'entrepôt, `ATTACH`, `INSTALL
  iceberg`, `SET` après le verrou (par `executer` et en direct sur la
  connexion : « locked »), `CREATE TABLE`, deux requêtes, `read_parquet`, une
  table inconnue, une requête illisible ; la vue se lit encore après chacun,
  aucun fichier n'est créé.
- **Journal** : la correspondance des hashes de `main` (première entrée),
  puis l'entrée du §0 et du palier 1.

**Vérifications locales** (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 194 files already formatted |
| `uv run mypy src` | Success: no issues found in 50 source files (0 `type: ignore`) |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true` | **490 passed** en 91 s (470 avant ; 20 nouveaux dans `test_silver.py`, `test_silver_construction.py`, `test_silver_demo.py` ; les 9 `integration` ont tourné, courtier présent) |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| `uv run pharmaflux demo verifier` | conforme |
| `profil`, `questions verifier` sur `~/pharmaflux-data` | 0 bloquante ; 25 conformes, 5 non calculables, 10 sans attendu |
| `evenements` sur la copie du Mac, `diff -r` contre la sortie du §0 (code `cfc1fea`, identique à `1af4ef9` sur le code) | identique |
| `silver construire` sur les événements du jeu (`--lot 10000`) | 164 106 événements, 164 096 ouvertures, 10 fermetures, 27 commits, 32 Parquet, 22 Mo ; **9,7 s, 297 Mo** résidents |
| `silver verifier --racine demo/archive` | **22/22 conformes** (18 retenues, 4 écartées), invariants conformes, 10,2 s, **342 Mo** |
| `silver etat --entite bdpm.presentations --a 2026-10-26T14:00:00Z` | 20 895 versions, 1,5 s, **182 Mo** |
| `silver sql "SELECT count(*), count(fin_validite), count(DISTINCT identite) FROM presentations"` | 20 898, 10, 20 898 ; **173 Mo** |
| `silver comparer` (lots de 10 000 contre lots de 25 000) | identiques : 11 tables ; 2,3 s, **432 Mo** |

Toutes les commandes `silver` restent sous le seuil de 512 Mo ; la plus
lourde est `comparer` (deux tables en mémoire et l'`EXCEPT ALL` de DuckDB).
`ARROW_DEFAULT_MEMORY_POOL=system` compte : `pa.set_memory_pool` seul (ce
que K.4 décrivait) laissait `construire` à 406-419 Mo, parce que le scanner
de PyArrow prend l'allocateur C++ par défaut, fixé avant l'import. La suite
de tests passe de 36 à 91 s : le test du jeu de démo (rejeu, construction,
vérification, 11 entités) en prend une trentaine.

**Écarts à l'ordre**

1. `silver sql` sans `allowed_directories` (ci-dessus) : plus strict que
   l'addendum, pour la raison mesurée.
2. Deux plafonds de plus dans `constraint-dependencies` (`sqlalchemy
   <2.0.55`, `cachetools<7.2.2`), découverts au verrou comme l'addendum le
   prévoyait.
3. Le premier snapshot d'une entité n'a pas d'`ecart` dans son bilan : pour
   les comptes attendus, `verifier` prend une `creee` par ligne bien formée
   (ADR 0006), les autres archives donnent `ecart.evenements`.
4. Le dernier appel déprécié de DuckDB (`fetch_arrow_table`) a été remplacé
   par `to_arrow_table` : aucun avertissement dans la suite.

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** : aucune à ce palier ; `--continu` sera
proposé dans `pr.md` comme l'addendum le demande.
