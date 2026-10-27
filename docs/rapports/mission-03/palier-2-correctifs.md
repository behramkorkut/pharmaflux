# Mission 03 — palier 2, réponse au contrôle

Contrôle du commit `ab015b2` ; les trois correctifs sont dans ce commit, son fils, et le contrôle est commité tel quel.

1. **Création automatique des topics coupée.** En v26.2, `rpk redpanda start` n'a plus d'option `--set` ; la voie documentée pour une propriété de grappe avant l'amorçage est `.bootstrap.yaml`, lu au premier démarrage seulement. Le compose le fournit par un bloc `configs` (contenu en ligne) monté en `/etc/redpanda/.bootstrap.yaml` : les propriétés du mode `dev-container` et `auto_create_topics_enabled: false`. Appliqué par `down -v` puis `up -d --pull never --wait`. Vérifié : `docker compose -p pharmaflux exec redpanda rpk cluster config get auto_create_topics_enabled` → `false` ; `group_topic_partitions` 3, `log_segment_size_min` 1, `write_caching_default` "true" conservés. Le `redpanda.yaml` que rpk réécrit dit encore `true` pour cette clé : c'est la configuration de grappe qui compte, pas ce fichier. Test d'intégration ajouté : un `produce` vers un topic inconnu rend « Broker: Unknown topic or partition (3) » et aucun topic n'apparaît. librdkafka attend 30 s (`topic.metadata.propagation.max.ms`) avant de trancher : `BusKafka` prend ce délai en paramètre, défaut inchangé, le test le met à 2 s.
2. **Le topic vient du dossier.** `envelopper` reçoit l'entité du dossier ; le topic en vient, et une ligne dont l'`entite` diffère lève `EvenementInvalide` en nommant les deux. Elle part dans la file des échecs, motif `illisible` ; un test unitaire sur l'enveloppe, un sur la publication.
3. **Le sha256 est celui des octets publiés.** Calculé ligne à ligne pendant la lecture qui publie, lignes vides comprises ; `_verifier_inchanges` lit par blocs de 1 Mio. La publication n'importe plus `sha256_hex`.

Retouche : la docstring de `PublicationRefusee` nomme les trois refus réels (état illisible, état présent sans `--reprendre`, fichier changé ou disparu). ADR 0007 : une phrase sur le `schema_id` partagé par contenu, un paragraphe sur l'amorçage.

**Vérifications locales** (commit testé : ce commit, fils de `ab015b2`, sur l'arbre commité tel quel)
| commande | résultat |
|---|---|
| `uv run ruff check .` et `ruff format --check .` | verts |
| `uv run mypy src` | vert, 35 fichiers |
| `docker compose -p pharmaflux down -v` puis `up -d --pull never --wait` | courtier sain ; `rpk cluster config get auto_create_topics_enabled` → `false` |
| `uv run pytest -q -m integration` | 3 passed en 7,8 s ; seul `_schemas` reste sur le courtier |
| `uv run pytest -q` avec le courtier | 434 passed en 19 s |

**Écarts à l'ordre** : aucun. **Questions pour l'IeC** : aucune. **Propositions d'évolution** : aucune.
