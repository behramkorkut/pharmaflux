# Mission 03 — contrôle du palier 3 (IeC)

**Commit contrôlé** : `be0ec60`. **Verdict** : palier 3 **accepté sous
réserve d'un correctif léger**, dans un nouveau commit. Ensuite, la mission
part en relecture.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `be0ec60`, avec le courtier du
projet démarré (`pharmaflux-redpanda`, sain) :

- ruff format et mypy (36 fichiers) : verts ;
- ruff check : la seule erreur est l'E501 venue de `main`, corrigée sur
  `main` (voir les réponses ci-dessous) ;
- pytest : 444 tests, tous passent ;
- `pytest -m integration` : 6 tests, verts en 13,9 s ;
- `verifier-bus` sur les topics de la démonstration, avec la sortie de mon
  contrôle du palier 1 (identique octet pour octet à celle du code fusionné) :

| référence | code | topics conformes | durée | mémoire résidente maximale |
|---|---|---|---|---|
| fichiers d'événements | 0 | 12 sur 12, 0 doublon | 10,9 s | 193 Mo |
| `--racine` (archive du Mac) | 0 | 12 sur 12, 0 doublon | 11,6 s | 228 Mo |

Les chiffres du rapport sont reproduits.

## Sur le fond

- **La relecture** fait ce que demande la décision 8 :
  - les partitions sont assignées à la main, sans groupe actif ni commit ;
  - la fin de chaque partition est photographiée avant de lire, et ce qui
    est publié pendant la lecture n'est pas compté ;
  - le préchargement est borné.

  Un consommateur qui ne reçoit plus rien lève une erreur au lieu
  d'attendre sans fin. C'est le bon choix.
- **Le dédoublonnage par `id`** (le premier message gagne) est juste : une
  même clé va toujours dans la même partition, donc l'ordre entre les
  copies est garanti. Les doublons sont rapportés par fichier, sans compter
  comme une différence. C'est ce que montrent les tests de coupure : seul le
  fichier republié produit des doublons, et ce sont des copies exactes.
- **La mémoire** : un seul état complet à la fois, réduit à 32 octets par
  ligne avant de calculer la référence. `appliquer` reçoit des lots, ce qui
  évite de recopier l'état à chaque événement. Aucune cible de mémoire
  n'était fixée pour `verifier-bus` (écart 2) : 190 à 230 Mo, avec la cause
  nommée dans l'ADR, c'est accepté.
- **La configuration vérifiée** inclut `message.timestamp.type` (écart 1),
  et c'est un bon ajout : `CreateTime` sur les événements, `LogAppendTime`
  sur la file des échecs, les deux sont contrôlés.
- **Le job CI `integration`** utilise le compose du dépôt et affiche les
  versions de Docker et de Compose. Il vérifie l'amorçage, montre le journal
  du courtier en cas d'échec et finit par `down -v` dans tous les cas. Les
  deux écarts possibles entre le Mac et la CI sont nommés. La première
  exécution aura lieu au push de beko ; c'est là qu'on saura si le runner
  accepte le bloc `configs: content:`.
- **Remarque, sans correctif** : `ConfigResource` est importé d'un module
  privé (`confluent_kafka.admin._config`). Le commentaire dit pourquoi. Si une
  version future de confluent-kafka casse cet import, l'erreur sera
  immédiate au chargement : le risque est faible.

## Correctif

**Une référence introuvable doit être refusée avant la lecture du bus.**
Sans `--sortie`, la valeur par défaut `data/evenements` n'existe pas dans
ton arbre. `verifier-bus` compare alors chaque topic à une référence vide et
annonce par exemple « 20 895 identités seulement sur le bus ». Le code 2 est
juste, mais le message égare : il fait croire à un bus faux. Pire, un topic
vide comparé à une sortie absente serait déclaré conforme. Le même problème
existe avec `--racine` quand `etat.json` manque ou ne cite pas l'entité.

Avant toute lecture du bus, vérifie que la référence existe :
- sans `--racine`, le dossier des fichiers d'événements de la sortie ;
- avec `--racine`, `etat.json`.

Si elle manque, sors avec le code 2 et le message « référence
introuvable : … », qui nomme le chemin, comme pour
`ReprendreImpossible`. Pour une entité sélectionnée qui n'a ni fichier
d'événements ni entrée dans `etat.json`, dis-le en clair dans la
différence (« aucune référence pour cette entité »), au lieu de la
comparer à un état vide. Un test unitaire par cas suffit.

## Réponses aux questions

1. **L'E501 venue de `main`** : c'était une ligne de mon test,
   `test_continuation_de_ligne`. Je l'ai raccourcie sur `main` et beko la
   commite. Après la fusion de `main` dans ta branche, `ruff check .`
   repassera au vert. Dans le rapport du correctif, cite l'exécution de
   `ruff check .` sur tout le dépôt.
2. **L'ADR 0007 passé à « accepté »** : d'accord. Les décisions qu'il
   décrit sont celles de l'addendum, et elles sont implémentées et
   contrôlées. Les ADR 0004 à 0006 ont été acceptés de la même façon,
   pendant leur mission. Si la relecture change une décision, l'ADR est mis
   à jour.

## Suite

Le correctif dans un commit, avec une réponse courte dans
`docs/rapports/mission-03/palier-3-correctifs.md`. Commite aussi ce
contrôle tel quel. Ensuite, beko lance `/relire-mission 03`.
