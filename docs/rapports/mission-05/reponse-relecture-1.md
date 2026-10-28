# Mission 05 — réponse à la relecture 1

Relecture du commit `f0aac28`, verdict NON CONFORME, un bloquant et quatre
points non bloquants. Tout est corrigé dans ce commit, son fils ; la
relecture est commitée telle quelle. Aucun refus du garde-fou.

## Bloquant

1. **`Path.as_uri()` encodait le chemin de l'entrepôt, PyIceberg l'écrivait
   à la lettre.** Reproduit avant de corriger, dans le dossier temporaire de
   la session (effacé) : sous `dossier avec espace é`, seul `catalogue.sqlite`
   était dedans, Parquet et métadonnées dans le voisin
   `dossier%20avec%20espace%20%C3%A9`. **Correction** (`entrepot.py`) :
   `uri_entrepot(absolu)` rend `file://` suivi du chemin **brut**, et refuse
   avant toute écriture (`Entrepot.creer` le vérifie avant le `mkdir`) un
   chemin qui contient `#` ou `?`, que PyIceberg lirait comme la fin de
   l'URI (essayé : `#` fait écrire les métadonnées dans un fichier nommé
   comme le dossier parent, `?` casse l'URL SQLite) ; essayés et sans effet :
   l'espace, l'accent, `%`, `;`, `'`. **Test**
   `test_entrepot_sous_un_chemin_a_espace_et_accent` : `construire` sous
   `tmp_path / "Mes projets é" / "lakehouse"`, le dossier temporaire ne
   contient que ce dossier, `metadata_location` de chaque table sous
   `file://<dossier>/`, les `chemins_parquet` existent et sont tous sur le
   disque sous l'entrepôt, `verifier` conforme ; `Entrepot.creer` refuse
   `dièse#1` et `quoi?` sans rien créer. Les entrepôts déjà construits sous
   un chemin sans caractère réservé (`data/demo/lakehouse` du Mac) portent
   exactement le même URI qu'avant et se relisent : `silver sql` et `etat`
   rejoués dessus. **ADR 0009** : le paragraphe sur l'entrepôt `file://`
   absolu dit maintenant pourquoi le chemin est brut et ce qui est refusé.

## À corriger

2. **Invariants du SCD2 jamais mis en échec.**
   `test_verifier_voit_chaque_invariant_du_scd2` : pour chacun des quatre
   invariants SQL, un silver des présentations est construit puis une ou
   deux versions fautives sont ajoutées par un `append` direct (une copie
   d'une ligne existante dont quelques colonnes changent) : la même
   identité ouverte deux fois ; une fin une heure avant le début ; deux
   versions fermées d'une même identité qui se recouvrent d'une heure ; les
   `id` d'une version existante repris sous une autre identité. Chaque cas
   donne le code 2 et le message attendu (`1 identité(s) avec plusieurs
   versions ouvertes`, `1 version(s) dont la fin ne suit pas le début`,
   `1 chevauchement(s) de validités`, `identifiants d'événements répétés : 1
   en ouverture, 1 en fermeture`) ; les trois derniers ne déclenchent pas
   « plusieurs versions ouvertes », et les comptes contre les bilans tombent
   aussi. Les quatre requêtes ont donc chacune rendu quelque chose.
3. **Seconde barrière de `silver sql`.** Dans
   `test_sql_lit_les_vues_et_refuse_tout_le_reste`, `COPY … TO`, `ATTACH`
   et `INSTALL iceberg` sont maintenant passés **directement** à
   `con.execute` : `duckdb.Error` les trois fois, et aucun fichier créé,
   comme pour le `SET`.
4. **`lire_instant` acceptait quatre formes limites.** Refusées : trois
   formes seulement passent, par expression régulière avant
   `fromisoformat`, la date seule (`AAAA-MM-JJ`), `AAAA-MM-JJThh:mm:ssZ` et
   `AAAA-MM-JJThh:mm:ss±hh:mm`. Une fraction écrite, même `.000`, dit
   « fraction » ; sans fuseau dit « sans fuseau » ; sans les secondes,
   l'espace à la place du `T`, la forme compacte, un décalage sans
   deux-points et un mois impossible disent « illisible » avec les formes
   acceptées. Six cas ajoutés à `test_lire_instant_utc_a_la_seconde` ; la
   docstring du module, l'aide de `--a` et l'ADR 0009 disent la règle.
5. **Code mort dans `etat.py`** : `colonnes_de_donnees` et la réexportation
   de `COLONNES_VERSION` retirées ; le test appelle `colonnes_du_contrat`.

## Remarques

- **README, second exemple** : deux lignes de `silver sql` suivent, avec
  leurs résultats en commentaire : `presentations` 20 898 versions dont 10
  fermées (les suppressions des 24, 26 et 27/10), `infos_importantes`
  10 905 versions dont **0 fermée** sur neuf archives, dont quatre servies
  vides et écartées : la démonstration que l'état n'a pas bougé se lit
  sans rejouer le jeu. Rejouées sur `data/demo/lakehouse`.
- **`pyproject.toml`** : commentaires des contraintes alignés ; `tzdata`
  gardée (elle ne sert que sous Windows, dit dans son commentaire) ;
  `uv lock --check` inchangé.
- **Non-régression sur `~/pharmaflux-data`** : rejouée en une passe pour
  `pr.md`, sur le commit testé, comme l'IeC l'a demandé au contrôle 3.

**Vérifications locales** (commit testé : ce commit, fils de `f0aac28`,
courtier du Mac en marche)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 205 files already formatted |
| `uv run mypy src` | Success: no issues found in 51 source files (0 `type: ignore`) |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true` | **500 passed** (498 + 2) en 2 min 06 s, intégration comprise |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| `uv lock --check` | Resolved 56 packages, verrou inchangé |
| `silver etat … --a 2026-10-26T14:00Z` et `… --a 2026-10-26T14:00:00.000Z` | code 2, « illisible » / « fraction » |

**Écarts à l'ordre** : aucun nouveau.
