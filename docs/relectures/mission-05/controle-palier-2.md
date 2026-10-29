# Mission 05 — contrôle du palier 2 (IeC)

**Commit contrôlé** : `9223280` (fils de `d22e406`, qui porte le contrôle du
palier 1 tel quel). Il est contrôlé contre l'ordre et l'addendum 1
(`b5b9420`). **Verdict : conforme, passe au palier 3**, avec une précision
sur D.1 (ci-dessous).

## Revérifié par l'IeC

Dans le dossier du codeur, arbre propre sur `9223280` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 51 fichiers |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true`, courtier présent | 498 passed en 2 min 02 s, dont les tests d'intégration |

Relu dans le code (`silver/consommation.py`, ajouts de `bus/client.py`) :

- **Pas de fenêtre entre le silver et sa position.** La position de chaque
  partition est calculée sur le lot et passée à `appliquer_lot` dans
  `proprietes_table`. Elle est donc écrite dans le même commit que les
  données. Un lot entièrement en doublon fait avancer la position sans
  créer de snapshot.
- **Un lot qui mêle plusieurs partitions** est appliqué dans l'ordre
  d'arrivée. C'est juste : toutes les versions d'une identité, comme tous
  les rangs d'une même empreinte, sont sur une seule partition, et dans
  l'ordre.
- **Les contrôles de départ sont faits avant toute lecture** :
  - une partition disparue, une position au-delà de la fin ou avant le
    début donnent un refus ;
  - le message à `offset − 1` est relu, et s'il ne porte pas l'`id`
    attendu, c'est un refus ;
  - une grappe différente donne un avertissement.

  Un message illisible, ou qui dit une autre entité que le topic, arrête
  tout sans rien écrire de son lot.
- **Le consommateur ajouté pour la relecture** (`derniers_messages`) a un
  groupe jetable, aucun commit automatique, et il est fermé dans un
  `finally`. Aucune écriture sur le bus, et rien ne change dans les
  méthodes existantes de `LecteurKafka`.
- **La démonstration de la décision 6** est faite sur le bus de la démo,
  sans `down -v` :
  - le silver du bus est identique au silver des fichiers (11 tables) ;
  - la vérification est conforme sur les 22 archives ;
  - la seconde exécution ne commet rien ;
  - `consommer` monte à 357 Mo, sous le seuil.

## Écarts du rapport

1. **Un consommateur dédié pour relire `offset − 1`** : accepté. Les
   réglages de `lire`, `verifier-bus` et `suivre` ne changent pas.
2. **Huit points de coupure par exécution** au lieu de tous : accepté. Ces
   points sont aux bords des lots, et ce sont eux qui comptent. Le cas
   « entre le `metadata.json` et SQLite » et le cas « après le commit »
   restent testés.
3. **`bus/client.py` touché par ajouts seulement** : accepté.
   L'interdiction de l'ordre porte sur la publication, l'enveloppe et les
   topics, qui ne changent pas.

## D.1 : à corriger dans le plan du palier 3

Le rapport prévoit, après le `make rebatir` de beko, de voir si « la table
construite avant » donne l'avertissement. Mais `make rebatir` fait
`rm -rf data/demo` : il efface aussi `data/demo/lakehouse`. On ne peut pas
non plus copier l'entrepôt ailleurs, car ses chemins absolus empêchent de
le relire (K.3).

**La marche à suivre au palier 3** :

1. **Avant** que beko lance la séquence, construis un entrepôt témoin hors
   de `data/demo` :

   ```
   uv run pharmaflux silver consommer --entrepot data/lakehouse-temoin-d1 --fichier bdpm.presentations
   ```

   Il porte la grappe actuelle (`redpanda.990d5d4e-…`).
2. beko lance `make rebatir`, `make demo` puis la cible du silver, et te
   transmet la sortie.
3. Après sa séquence, relance la même commande sur l'entrepôt témoin. Le
   rapport dit :
   - si l'identifiant de grappe a changé ;
   - si l'avertissement est sorti ;
   - ce que le contrôle des `id` a décidé. Si le bus rebâti est identique,
     c'est « rien de nouveau » ; sinon, c'est un refus. Les deux sont des
     réponses justes, mais il faut dire laquelle.
4. Ne supprime pas l'entrepôt témoin toi-même : dis-le à beko, qui
   l'effacera.

Le plan du palier 3 ne change pas pour le reste : `make -n` des cibles,
l'étape de CI, l'ADR 0009 (avec la règle des plafonds temporaires du
contrôle du palier 1), le README et ses deux exemples (« 26/10 juste après
14:17:39 »), puis `docs/CONTEXTE.md`.
