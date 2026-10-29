# Mission 05 — palier 2 : le consommateur du bus (décision 3)

Contrôle du palier 1 lu et commis tel quel (`d22e406`). Aucune commande
`docker compose` d'écriture, aucun `down -v` : le bus de la démo du Mac (celui
de la mission 04, intact, `verifier-bus` 12/12 conforme avant de commencer) a
servi tel quel ; `docker compose -p pharmaflux ps` en lecture seulement. Aucun
refus du garde-fou, aucune requête vers les sources, archive en lecture seule.

**Fait**

- **`pharmaflux/silver/consommation.py`** : `consommer(lecteur, dossier,
  contrats, selection, lot, prefixe)`. Refus avant toute écriture si aucun
  topic de la sélection n'est sur le courtier (« le bus est vide, `make demo`
  d'abord ») ; entrepôt ouvert ou créé ; par entité : table créée (origine
  `bus`, identifiant de grappe gardé dans `pharmaflux.grappe`) ou contrôlée
  (origine `bus` sinon refus « silver construit depuis les fichiers », version
  de contrat, grappe différente → **avertissement**) ; **positions** lues dans
  `pharmaflux.positions` (par partition : offset suivant, `id` du dernier
  message appliqué) et contrôlées contre les bornes du topic (au-delà de la
  fin ou avant le début → refus « rebâtis le silver ») ; le message à
  `offset − 1` de chaque partition est relu et doit porter l'`id` gardé, sinon
  refus « le bus n'est pas celui qui a construit le silver » ; lecture de
  toutes les partitions depuis leur position jusqu'aux offsets de fin lus au
  départ ; lots d'au plus `--lot` (10 000) messages, `appliquer_lot` avec la
  position dans les propriétés de table (même commit) et la plage d'offsets
  du lot dans le résumé du snapshot (`pharmaflux.offsets`). Un message qui
  n'est pas un événement v1, ou qui dit une autre entité que le topic :
  `FluxIncoherent`, rien du lot n'est écrit, la position ne bouge pas, jamais
  sauté. Aucun groupe, aucun commit sur le courtier, rien d'écrit sur le bus.
- **`bus/client.py`, `LecteurKafka`** (ajouts seulement, rien d'existant ne
  change) : `identifiant_grappe()` (`describe_cluster`), `bornes(nom)`
  (watermarks par partition), `derniers_messages(nom, offsets)` (un
  consommateur dédié, `fetch.wait.max.ms` 50, qui relit un message par
  partition d'un coup), `lire_depuis(nom, debuts, fins)` (comme `lire`, depuis
  une position par partition). Un protocole `LecteurSilver` dans
  `consommation.py` ; `fabriquer_lecteur_silver` dans la CLI pour les tests.
- **Commande `silver consommer [--entrepot] [--courtier] [--fichier] [--lot]`** :
  une ligne par entité (messages, doublons, ouvertures, fermetures, commits,
  positions par partition, notes), les avertissements sur la sortie d'erreur,
  la grappe ; codes 1 courtier injoignable, 2 refus.
- **Tests** (8 nouveaux, 498 au total) : `test_silver_consommation.py`, sur
  le `BusSimule` de la mission 03 relu par `LecteurSilverSimule` en **trois
  partitions réparties par la clé** (bronze de synthèse `SUITE`, publié par
  `publication.executer`) : le silver du bus égale celui des fichiers
  (`comparer`) et l'archive (`verifier`), positions et résumé des snapshots ;
  rien de nouveau → aucun commit, `metadata_location` inchangé ; reprise après
  une publication en deux fois, et après une publication coupée puis reprise
  (doublons comptés, silver égal) ; **coupures** pendant la lecture (huit
  points : début, bords du premier et du dernier lot, milieu, fin), **entre le
  `metadata.json` et SQLite** (cale sur `SqlCatalog._write_metadata` de
  PyIceberg 0.12.0, commentée comme l'addendum le demande) et **après le
  commit**, chaque fois reprise puis égalité ; refus (silver des fichiers, bus
  vide sans rien créer, message illisible en tête de partition → aucun snapshot
  ni position, puis après un lot déjà appliqué → la position tient, bus rebâti
  autrement → refus par les `id`, bus rebâti vide → au-delà de la fin, autre
  grappe → avertissement et silver égal, autre version de contrat, `--lot 0`) ;
  la commande (codes 0, 1, 2, avertissement). `test_silver_integration.py`
  (marqués `integration`, fixtures de `conftest`, préfixe unique) : la
  publication des fixtures consommée par `LecteurKafka` égale le silver des
  fichiers, trois partitions reçues, grappe `redpanda.…`, rien de nouveau au
  second passage ; publication coupée puis reprise → doublons reconnus, égal.
- **Journal** : l'entrée du palier 2.

**Démonstration de la décision 6** (bus de la démo du Mac, grappe
`redpanda.990d5d4e-41d8-4ab7-b318-a41701404a42`, `/usr/bin/time -l`) :

| étape | résultat |
|---|---|
| `silver consommer --entrepot data/demo/lakehouse` (entrepôt neuf) | 164 106 messages, 0 doublon, 164 096 ouvertures, 10 fermetures, 24 commits ; positions `presentations` p0 → 6 885, p1 → 6 980, p2 → 7 043 ; **12,9 s, 357 Mo** résidents ; 27 Parquet, 35 `metadata.json`, 21 Mo |
| `silver construire --sortie data/demo` (fichiers, dossier jetable) | 9,6 s, 299 Mo |
| `silver comparer data/demo/lakehouse <fichiers>` | **identiques : 11 tables** ; 2,0 s, 442 Mo |
| `silver verifier --entrepot data/demo/lakehouse --sortie data/demo --racine demo/archive` | **22/22 conformes**, invariants conformes ; 10,3 s, 341 Mo |
| `silver consommer`, seconde fois | 0 message, 0 commit, « rien de nouveau » × 11 ; 0,3 s, 141 Mo |
| `silver sql … FROM presentations` sur le silver du bus | 20 898 versions, 10 fermées |

Toutes les commandes restent sous **512 Mo** ; `consommer` est à 357.

**Vérifications locales** (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 199 files already formatted |
| `uv run mypy src` | Success: no issues found in 51 source files (0 `type: ignore`) |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true` | **498 passed** en 2 min 00 s (490 avant, 91 s), dont 11 `integration` sur le courtier du Mac ; 2 min 43 s avant la réduction des points de coupure (écart 2) |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| `uv run pharmaflux verifier-bus --sortie data/demo --racine demo/archive` | 12/12 conforme (le bus de la démo, avant et après) |

**D.1, l'identifiant de grappe et `down -v`** : non vérifié à ce palier.
Le vérifier demande d'effacer le bus de la démo de beko (`down -v`), que la
démonstration ci-dessus utilise ; l'identifiant courant est
`redpanda.990d5d4e-41d8-4ab7-b318-a41701404a42`, gardé dans les onze tables
de `data/demo/lakehouse`. Au palier 3, beko enchaîne `make rebatir` (qui
contient le `down -v`) et `make demo` : le rapport du palier 3 comparera
l'identifiant de la grappe rebâtie à celui-ci, et dira si la table
construite avant donne bien l'avertissement. Redpanda tire son identifiant
de grappe de son répertoire de données, que le volume porte : l'attente est
qu'il change.

**Écarts à l'ordre**

1. **Relecture du message à `offset − 1`** : la première version relisait
   un message par partition avec le consommateur de `lire` ; en fin de
   partition, chaque relecture coûtait 0,5 à 1 s (`fetch.wait.max.ms`
   500 ms), soit 16,5 s pour une exécution sans rien de nouveau. Un
   consommateur dédié (`fetch.wait.max.ms` 50) relit toutes les partitions
   d'un topic d'un coup : 0,3 s. Les réglages du consommateur de `lire`,
   `verifier-bus` et `suivre` ne changent pas.
2. **La suite de tests** a atteint 2 min 43 s avec les coupures à tous les
   bords de lots ; les points sont réduits à huit par exécution
   (`test_silver_consommation.py` : 70 → 27 s ; suite : 2 min 00 s). Pas de second test sur le jeu entier : la
   démonstration est manuelle, aucune fixture `demo_silver` à partager.
3. **`bus/client.py` est touché**, par quatre méthodes ajoutées à
   `LecteurKafka` ; rien de ce qui existait ne change (publication, enveloppe,
   topics, `lire`, `suivre`).

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** : aucune à ce palier ; `--continu` ira dans
`pr.md`.
