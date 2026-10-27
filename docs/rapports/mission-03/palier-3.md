# Mission 03 — palier 3

**Fait** : décisions 5 à 9. `pharmaflux verifier-bus` (`bus/verification.py`, lecteur `LecteurKafka` dans `bus/client.py`, `rejeu.dernier_retenu`) : relecture de chaque topic depuis le début, toutes les partitions à la fois, sans commit, fin par les offsets ; dédoublonnage par `id` ; application par lots ; états réduits à une empreinte par ligne, un seul état complet en mémoire ; référence fichiers par défaut, `--racine` pour le dernier snapshot retenu recalculé depuis l'archive ; rétention, politique, type d'horodatage et partitions vérifiés ; codes 1 et 2, doublons rapportés. Tests : 7 unitaires de plus (`tests/test_bus_verification.py` : bus en mémoire, coupure pendant chaque fichier puis `--reprendre`, toute différence, les deux références sur le bronze des tests du rejeu, CLI) et 3 d'intégration de plus (publication complète puis vérification avec la configuration lue sur le courtier ; coupure pendant chacun des trois fichiers puis `--reprendre` : doublons du seul fichier republié, copies exactes). Job CI `integration` : compose du dépôt, versions de Docker et Compose affichées, `up -d --wait`, amorçage vérifié, schémas sur registre neuf, tests marqués, journal du courtier en cas d'échec, `down -v`. ADR 0007 complété et passé à « accepté », `CONTEXTE.md`, journal, README. Contrôle des correctifs commité tel quel.

**Démonstration** (copie du Mac, lecture seule) : rejeu complet 8,3 s et 134 Mo, `diff -r` identique à la référence du code fusionné ; `publier` 164 099 messages sur onze topics, 29,8 s, 59 Mo ; `verifier-bus` conforme, 0 doublon, 11,0 s et 189 Mo (fichiers), 11,8 s et 219 Mo (`--racine`) ; clôture : `evenements --reprendre` 0 archive, `publier --reprendre` 0 fichier en 0,4 s, `verifier-bus` conforme.

**Vérifications locales** (commit testé : ce commit, fils de la fusion `0c5a043`, sur l'arbre commité tel quel)
| commande | résultat |
|---|---|
| `uv run ruff check .` | **1 erreur** : E501 dans `infra/agents/test_garde_fou.py:354` (101 caractères), arrivée de `main` par la fusion `0c5a043`, fichier réservé à l'IeC ; `ruff check src tests` vert |
| `uv run ruff format --check .`, `uv run mypy src` | verts, 36 fichiers |
| `uv run pytest -q` avec le courtier | 444 passed (sans courtier : 6 sautés, motif affiché) |
| `uv run pytest -q -m integration` | 6 passed en 14 s ; topics et sujets de test supprimés |
| `python3 infra/agents/test_garde_fou.py`, `sh infra/git-hooks/test-crochets.sh` | 20 OK ; conformes |
| `rpk cluster config get auto_create_topics_enabled` | `false` |

**Écarts à l'ordre** : `message.timestamp.type` vérifié en plus de la rétention et des partitions. Aucune cible de mémoire pour `verifier-bus` : 189 Mo mesurés, cause nommée dans l'ADR (tampons du consommateur, fragmentation ; 164 Mo pour l'entité la plus lourde seule). Les deux écarts Mac / CI, que le job affiche : architecture arm64 sur le Mac, amd64 sur `ubuntu-latest` (images multi-architecture, roues `confluent-kafka` pour les deux) ; Compose 5.1.4 sur le Mac, v2 récente sur le runner, le bloc `configs: content:` demandant au moins la 2.23.1. La CI ne se lance pas d'ici : la même séquence a été rejouée sur le Mac, avec `--pull never`.

**Questions pour l'IeC** : l'erreur ruff venue de `main` fera échouer le job `verifier` au push ; à corriger sur `main` avant la publication ? L'ADR 0007 passé à « accepté » par ce palier : d'accord ?

**Propositions d'évolution** : aucune.
