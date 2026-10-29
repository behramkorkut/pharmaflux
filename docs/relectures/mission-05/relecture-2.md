# Mission 05 — relecture 2
**Commit relu** : `4fa1cb3` (sommet de `mission-05-silver-et-etat-a-une-date`)
**Verdict** : CONFORME

J'ai relu le commit `4fa1cb3` (fils de `f0aac28`) contre l'ordre et son
addendum 1 (`main`), la relecture 1 et la réponse du codeur
(`reponse-relecture-1.md`). Le bloquant et les quatre points non
bloquants du tour 1 sont corrigés, et je l'ai vérifié en exécutant le
code, pas seulement en lisant la réponse. Ce tour ne trouve aucun
bloquant. Il reste un point non bloquant, dans le code que le correctif
a touché.

## Contrôle des points du tour 1

1. **Bloquant, URI de l'entrepôt** : corrigé.
   - `entrepot.py`, `uri_entrepot` : l'URI est `file://` suivi du chemin
     brut. Un `#` ou un `?` est refusé avant le `mkdir`.
   - Test : `test_entrepot_sous_un_chemin_a_espace_et_accent`. Il vérifie
     que rien n'est écrit à côté de l'entrepôt, que les URI des
     métadonnées sont sous l'entrepôt, que les Parquet existent et que la
     vérification est conforme.
   - Reproduit à la main hors des tests : `evenements` puis `silver
     construire` sur `demo/archive`, dans
     `<scratchpad>/Mon silver é/lakehouse`. Aucun dossier voisin au nom
     encodé (`%`) n'apparaît, et `silver verifier` donne **22/22
     conformes**.
   - L'ADR 0009 dit la règle.
2. **Invariants du SCD2** : corrigé. `test_verifier_voit_chaque_invariant_du_scd2`
   fait tomber chacune des quatre requêtes, avec son message et le code 2.
   Le test vérifie aussi que les trois derniers cas ne déclenchent pas
   « plusieurs versions ouvertes », ce qui prouve que chaque requête
   rend quelque chose par elle-même.
3. **Seconde barrière de `silver sql`** : corrigé. `COPY`, `ATTACH` et
   `INSTALL iceberg` sont passés directement à `con.execute` : chacun lève
   `duckdb.Error` et aucun fichier n'est créé.
4. **`lire_instant`** : corrigé pour les quatre formes citées. Les règles
   d'écriture sont désormais vérifiées par des expressions régulières,
   avec six cas de test ; l'aide de `--a`, la docstring et l'ADR disent
   la même chose. Il reste un trou, voir le point 1 ci-dessous.
5. **Code mort d'`etat.py`** : retiré, et le test appelle
   `colonnes_du_contrat`.
- **Remarques du tour 1**
  - README : les deux `silver sql` ajoutés donnent les chiffres que j'ai
    obtenus en les rejouant sur mon silver. Les présentations ont
    20 898 versions, dont 10 fermées (fermetures datées des 24, 26 et
    27/10). Les informations importantes ont 10 905 versions, aucune
    fermée.
  - L'exemple `3400938844948` rend 1 ligne à `2026-10-24T23:17:11Z` et 0
    à `23:17:12Z`.
  - Les commentaires de `pyproject.toml` sont alignés, et `uv lock
    --check` ne change rien.

## À corriger (non bloquants)

1. `src/pharmaflux/silver/etat.py:44-45` (`lire_instant`, branche « date
   seule »)
   - **Constat** : une date seule bien formée mais impossible
     (`2026-02-30`, `2026-13-45`) passe `_DATE_SEULE`. Elle arrive ensuite
     à `datetime.fromisoformat` sans le `try` de la branche suivante.
     `silver etat --a 2026-02-30` affiche alors une trace Python
     (`ValueError: day is out of range for month`) et sort en **code 1**,
     au lieu d'un refus `SilverRefuse` « illisible ».
   - Le cas testé, `2026-13-26T14:00:00Z`, passe par l'autre branche.
     Le défaut existait déjà avant le correctif, mais la réponse annonce
     « un mois impossible dit illisible », ce qui n'est vrai qu'avec une
     heure.
   - **Attendu** : le même `try` sur la branche « date seule », et un cas
     `("2026-02-30", "illisible")` dans `test_lire_instant_utc_a_la_seconde`.

## Remarques

- `entrepot.py`, `uri_entrepot` : un chemin non imprimable est refusé
  aussi (`not chemin.isprintable()`), mais le message ne parle que de
  `#` et `?`. C'est inoffensif, et on peut le préciser au passage.
- ADR 0009, paragraphe « État à une date » : une ligne dépasse la
  largeur du reste du fichier (« …de la forme compacte ; avant la
  première observation, aucune version ; »). C'est cosmétique.
- Mes mesures, à titre indicatif : `silver construire` sur le jeu prend
  10,4 s et 295 Mo résidents ; `silver verifier` prend 10,8 s et 333 Mo.
  Les deux restent sous le seuil de 512 Mo, comme au palier 1.
- **Périmètre**
  - `git diff --stat main...HEAD` ne contient aucun chemin réservé à
    l'IeC, rien de `data/` et aucun chemin du poste.
  - `relecture-1.md` est commité à l'identique du fichier écrit au
    tour 1.
- **Historique** : les huit commits de la branche portent les trailers
  `Commis-par: codeur` et `Co-Authored-By`, avec des messages en
  français. Le correctif est un nouveau commit, sans réécriture.
- Je n'ai pas rejoué la non-régression sur `~/pharmaflux-data`, qui est
  hors de mon dossier. La réponse la renvoie à `pr.md`, comme le
  demande le contrôle du palier 3.

## Vérifications relancées

Sur `4fa1cb3`, avec un arbre propre et le courtier `pharmaflux-redpanda`
en marche.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 206 files already formatted |
| `uv run mypy src` | Success: no issues found in 51 source files |
| `GITHUB_ACTIONS=true uv run pytest -q` | **500 passed** en 2 min 08 s, intégration comprise, comme la réponse |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | 21 tests, OK |
| `uv lock --check` | Resolved 56 packages, verrou inchangé |
| `uv run pharmaflux demo verifier` | conforme |
| `make -n silver etat` | mêmes recettes qu'au tour 1 |
| `evenements` puis `silver construire` dans un entrepôt sous `Mon silver é/` (dossier de session) | aucun dossier encodé à côté ; 10,4 s, 295 Mo |
| `silver verifier` sur cet entrepôt, `--racine demo/archive` | **22/22 conformes**, invariants conformes ; 10,8 s, 333 Mo |
| `silver sql` (README) sur `presentations` / `infos_importantes` | 20 898 versions, 10 fermées / 10 905 versions, 0 fermée |
| `silver etat --ou code_cip13=3400938844948` à 23:17:11Z / 23:17:12Z | 1 ligne / 0 ligne |
| `lire_instant` sur `2026-02-30`, `2026-13-45` | `ValueError` non capturée (point 1) ; `silver etat --a 2026-02-30` sort en code 1 |

## Alertes

Aucune.
