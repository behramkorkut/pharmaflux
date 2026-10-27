# Mission 03 — palier 2

**Fait** : décisions 2, 3 et 4. `docker-compose.yml` (Redpanda `v26.2.6`, console `v3.13.1` sous profil, ports sur 127.0.0.1, `dev-container` 768 Mo, volume `pharmaflux-redpanda`). Paquet `pharmaflux.bus` : enveloppe (valeur = ligne JSONL nue, clé = objet `cle` trié, horodatage `date_observation`, en-têtes dont `schema_id`), client `confluent-kafka` (idempotent, zstd, `murmur2_random`, 1 Mo refusé au `produce`, topics créés avec rétention infinie), registre (`BACKWARD_TRANSITIVE`, un sujet par topic), publication (`publication.json` écrit après accusé, `--reprendre`, refus sans forçage d'un fichier modifié, codes 1/2/3) et file des échecs (`illisible`, `trop_gros` tronqué à 64 Ko, `LogAppendTime`). Commandes `pharmaflux publier` et `pharmaflux schemas enregistrer`. Deux schémas draft-07 épinglés par sha256, ADR 0007 au statut proposé, README. 16 tests unitaires sans Docker (bus et registre simulés), 2 tests d'intégration marqués `integration`, sautés avec le motif sans courtier. Contrôle du palier 1 commité tel quel.

**Vérifications locales** (commit testé : ce commit, fils de `6ea3405`, vérifié sur l'arbre commité tel quel)
| commande | résultat |
|---|---|
| `uv run ruff check .` et `ruff format --check .` | verts |
| `uv run mypy src` | vert, 35 fichiers |
| `uv run pytest -q` sans courtier | 430 passed, 2 skipped, motif affiché, saut en 5 s |
| `docker compose -p pharmaflux up -d --pull never --wait` puis `pharmaflux schemas enregistrer` | courtier sain en 11 s ; 12 sujets, identifiants 1 (événements) et 2 (échecs) |
| `uv run pytest -q -m integration` | 2 passed en 3,5 s ; topics et sujets de test supprimés, seul `_schemas` reste |
| `uv run pytest -q` avec le courtier | 432 passed en 18 s |

**Écarts à l'ordre** : aucun. Un correctif pendant l'intégration : préfixe de test par test, et non par session, les deux tests partageant sinon leurs topics. Le détail des choix est dans l'ADR 0007.

**Questions pour l'IeC** : le registre déduplique par contenu, les 11 sujets d'événements partagent donc l'identifiant 1 et l'en-tête `schema_id` vaut 1 partout (2 pour la file). Acceptable, ou faut-il un identifiant par sujet ?

**Propositions d'évolution** : garde-fou : un `sed` dont le texte de remplacement contenait « docker compose » a été refusé (« docker » appelé par « -e ») ; signalé, l'IeC l'affine sur `main`.
