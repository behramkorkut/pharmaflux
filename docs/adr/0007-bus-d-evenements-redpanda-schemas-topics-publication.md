# ADR-0007 — Bus d'événements : Redpanda local, client, schémas, topics, clés, publication idempotente, file des messages en échec

**Statut :** accepté (mission 03 : proposé au palier 2, complété au palier 3
par la vérification, la reprise testée et la CI) · **Date :** 2026-10-27 ·
**Mission :** 03 · s'appuie sur l'ADR 0006 (événements)

## Contexte

Les fichiers JSON Lines de `evenements` sont exacts, rejouables et vérifiés
(ADR 0006, mission 02). Le PRD (§6.4, §7.1) veut ces événements sur un bus,
un topic par entité partitionné par la clé, avec des consommateurs
idempotents, avant le lakehouse (Lot 2). Contraintes de la mission : tout
sur le Mac, dans un colima partagé avec d'autres conteneurs ; **les fichiers
restent la référence**, le bus est alimenté à partir d'eux ; le schéma
d'événement v1 ne change pas ; une seule dépendance de production nouvelle ;
tests unitaires hors réseau et hors Docker. Mesures du §0 : 164 096
événements, ligne la plus longue 3 060 octets ; roues `confluent-kafka`
2.16.0 pour macOS arm64 et Linux x86_64 et aarch64, annotées (`py.typed`).

## Décision

**Courtier.** Un Redpanda mono-nœud dans `docker-compose.yml`, projet
`pharmaflux`, mode `dev-container` (`--smp 1 --memory 768M`, `mem_limit 1g`),
tous les ports sur `127.0.0.1` hors des défauts (19092, 18081, 18082,
19644), volume nommé `pharmaflux-redpanda`, console sous le profil `console`
(18080). Versions épinglées au correctif près dans ce seul fichier, que la
CI réutilise : Redpanda `v26.2.6` (dernier correctif de la branche 26.2, du
23/10/2026) et console `v3.13.1` (du 22/10/2026), choisies par beko le
27/10/2026 ; images multi-architecture (arm64 sur le Mac, amd64 sur le VPS),
jamais `latest` ni suffixe `-arm64`. `dev-container` relâche la durabilité
(pas de fsync) : un bus de développement. Le premier `pull` est à beko, avec
`--profile console` pour que la console, sous profil, soit téléchargée aussi ;
les agents lancent `up -d --pull never`. Les propriétés de grappe viennent
d'un fichier d'amorçage (`.bootstrap.yaml`, bloc `configs` du compose, lu au
premier démarrage seulement) : celles du mode `dev-container`, sauf
`auto_create_topics_enabled`, mis à `false` pour qu'un `produce` vers un
topic non préparé échoue au lieu de créer un topic avec la rétention par
défaut, ce que la décision 5 interdit ; les changer demande `down -v`.

**Client.** `confluent-kafka` (librdkafka), sans extras : producteur
**idempotent** (`enable.idempotence`, donc `acks=all`, réessais, ordre
conservé par partition), `compression.type=zstd`, partitionneur
`murmur2_random` (la même partition que les clients Java, `rpk` et la
console ; le défaut de librdkafka ne l'est pas), `message.max.bytes` 1 Mo :
un message trop gros est refusé **avant l'envoi**. `AdminClient` crée les
topics avec leur configuration. `pharmaflux.bus.client.Bus` est l'interface
que la publication utilise ; les tests unitaires la remplacent par un bus
en mémoire.

**Enveloppe** (`bus/enveloppe.py`). La valeur est la **ligne JSONL nue**,
sans son `\n`, à l'octet près : le bus transporte l'événement sans le
transformer. Topic `pharmaflux.<entite>.v<version_schema>` (onze topics
`…v1`), **3 partitions** figées par cet ADR (les changer redistribuerait
les clés), rétention sans limite (`retention.ms` et `retention.bytes` à
-1, `cleanup.policy=delete`, jamais de compactage : c'est l'histoire que
l'on perdrait), `message.timestamp.type=CreateTime`. Clé : l'objet JSON
`cle` de l'événement, compact, clés triées : tous les événements d'un même
médicament sur la même partition, dans l'ordre du fichier. Horodatage du
message : `date_observation` de l'événement, jamais l'horloge du poste :
deux publications du même fichier donnent le même message. En-têtes de
repère : `id`, `version_schema`, `schema_id`, `entite`, `type`, `archive`,
`fichier` (le JSONL d'origine, l'unité de republication), `producteur`.

**Schémas** (`bus/registre.py`, `bus/schemas/`). JSON Schema draft-07 de
l'événement v1, aussi strict que `deserialiser` (toutes les propriétés
requises, aucune en plus, énumérations prises dans le code et vérifiées par
un test), et du message en échec. Un sujet par topic (`<topic>-value`),
règle **`BACKWARD_TRANSITIVE`** : les consommateurs relisent les topics
depuis le début avec leur schéma du jour. Un changement incompatible est une
nouvelle `version_schema`, donc un nouveau topic, jamais une version de plus
du même sujet ; `bus/schemas/historique/` garde les versions publiées pour
qu'un registre neuf (la CI) refuse une évolution incompatible. Le registre
**n'encode rien** : l'identifiant du schéma voyage dans l'en-tête
`schema_id`. Un identifiant désigne un *contenu* de schéma pour tout le
registre, seule la version est propre au sujet : les onze sujets
d'événements, qui portent le même schéma, partagent donc le même
`schema_id` (1 sur un registre neuf), et ce `1` partout n'est pas une
erreur. Ce que ce choix coûte : un outil qui attend le format Confluent
(cinq octets devant la valeur) ne décode pas par le registre. Le sha256 des
fichiers de schéma est épinglé par un test. `jsonschema` est une dépendance
de **test** seulement.

**Publication** (`bus/publication.py`, `pharmaflux publier`). Les fichiers
de `<sortie>/evenements/`, entités puis noms dans l'ordre, une ligne après
l'autre, en flux. `publication.json` garde par entité la liste des fichiers
publiés (sha256, messages, échecs), réécrit entier puis renommé **après**
l'accusé de réception de tous les messages du fichier. `--reprendre`
publie les fichiers absents de l'état ; sans lui, un état existant fait
refuser. Un fichier publié dont le sha256 a changé, ou qui a disparu, fait
**refuser** la publication, sans option pour forcer : un événement publié
n'est jamais réécrit, la voie est de rebâtir le bus (`down -v`, suppression
de l'état, publication complète). Pas de transaction Kafka : l'état de
publication resterait une écriture séparée après le `commit`, et le PRD
exige de toute façon des consommateurs idempotents ; après une coupure, le
fichier en cours est republié en entier, ses messages déjà acceptés sont en
double, même `id`, même contenu, même horodatage. Codes de sortie : 1
courtier ou registre injoignable, livraison en échec (l'état n'avance pas) ;
2 état illisible, état existant sans `--reprendre`, fichier modifié ; 3 au
moins un message dans la file des échecs.

**File des messages en échec** (`pharmaflux.echecs.v1`, une partition,
`LogAppendTime`, clé = l'entité). Y vont ce que `publier` sait nommer et ne
peut pas publier : une ligne que `deserialiser` refuse (`illisible`) et un
message refusé pour sa taille (`trop_gros`). Le message (`version_echec` 1)
porte le motif, le détail, le fichier, le numéro de ligne, l'identifiant
quand la ligne se lit, la taille réelle et le sha256 de la ligne entière, et
la ligne brute tronquée à 64 Ko. La publication **continue** après un
échec ; un courtier injoignable l'arrête. Les bilans restent des fichiers :
leur topic est une décision du Lot 5, avec les alertes.

**Vérification** (`bus/verification.py`, `pharmaflux verifier-bus`). Chaque
topic est relu depuis le début, toutes ses partitions assignées à la fois,
chacune dans l'ordre de ses offsets jusqu'à l'offset de fin lu au départ ;
pas de groupe actif, pas de commit : rien n'est laissé sur le courtier, et ce
que `publier` écrirait pendant la lecture n'est pas compté. Les messages sont
dédoublonnés par `id` (le premier gagne, les suivants sont comptés avec le
fichier qu'ils citent), appliqués au vide par lots, et l'état obtenu est
réduit à une empreinte sha256 par identité de ligne **avant** que la
référence ne soit calculée : un seul état complet en mémoire. Deux
références : les fichiers d'événements de la sortie, appliqués dans l'ordre
des noms (le défaut, ce que la CI sait faire avec les fixtures), et avec
`--racine` le dernier snapshot retenu d'après `etat.json`, recalculé depuis
l'archive, indépendant des fichiers. Le courtier est aussi interrogé sur ce
que le projet pose à la création : `retention.ms` et `retention.bytes` à -1,
`cleanup.policy` `delete`, `message.timestamp.type`, et le nombre de
partitions. Toute différence, d'état ou de configuration, donne le code 2 ;
un courtier injoignable, 1 ; les doublons sont rapportés sans être une
différence : après une reprise, ils sont attendus.

**Reprise testée et CI.** Les tests d'intégration
(`tests/test_bus_integration.py`, marqueur `integration`, préfixe de topic
unique par test, topics et sujets supprimés à la fin) rejouent contre le
courtier : la publication complète puis `verifier-bus` (aucune différence,
aucun doublon, la configuration lue est celle posée) ; la publication coupée
pendant chacun des trois fichiers puis `--reprendre` (aucune différence ; les
doublons viennent tous du fichier republié et sont des copies exactes, même
valeur, même clé, même horodatage) ; le message impubliable vers la file ; le
`produce` vers un topic non préparé, qui échoue sans rien créer. La CI a un
second job, `integration` : le Redpanda du même fichier compose
(`up -d --wait`), l'amorçage vérifié par `rpk cluster config get`, les
schémas enregistrés sur un registre neuf (historique puis courant), les tests
marqués, le journal du courtier en cas d'échec, `down -v` à la fin. Deux
écarts possibles avec le Mac, affichés par le job : l'architecture (amd64
contre arm64, images multi-architecture) et la version de Compose (le bloc
`configs: content:` demande au moins la 2.23.1).

## Conséquences

- Le Lot 2 lit onze topics ordonnés par médicament, dédoublonne par `id`
  (en-tête ou valeur), et trouve dans `fichier` d'où vient un doublon.
- Rebâtir le bus est une opération normale et documentée ; réécrire un
  événement publié ne l'est jamais.
- Les tests unitaires du bus (enveloppe, schémas, registre simulé,
  publication sur un bus en mémoire) tournent sans Docker ; les tests
  marqués `integration` demandent le Redpanda local et sont sautés sans lui,
  avec le motif ; `uv run pytest -q` attend 5 s de plus quand il est absent.
- Mesures sur la copie du Mac (27/10/2026, onze fichiers, 164 099
  événements) : rejeu complet en flux 8,3 s et 134 Mo résidents, `diff -r`
  identique à la référence du code fusionné ; `publier` 164 099 messages sur
  onze topics en 29,8 s et 59 Mo ; `verifier-bus` conforme, 0 doublon, 11 s
  et 189 Mo (219 Mo avec `--racine`) ; `publier --reprendre` sans nouveau
  fichier 0,4 s. La mémoire de `verifier-bus` vient pour moitié des tampons
  du consommateur et de la fragmentation : l'entité la plus lourde seule
  donne 164 Mo, et un état complet de `compositions` pèse 40 Mo tracés.
- La mission est close quand `evenements --reprendre`, `publier --reprendre`
  et `verifier-bus` se suivent sans anomalie : joué sur le Mac le 27/10/2026
  (0 archive, 0 fichier, conforme).

## Options écartées

| Option | Pourquoi pas |
|---|---|
| `kafka-python` ou `aiokafka` | idempotence du producteur peu éprouvée pour le premier ; un second style de code (asyncio) pour le second ; `confluent-kafka` a l'idempotence mûre, l'`AdminClient`, et des roues binaires pour le Mac et la CI |
| le format Confluent (octet magique + identifiant) dans la valeur | la valeur ne serait plus la ligne du fichier à l'octet ; `verifier-bus` et le Lot 2 relisent avec `deserialiser` |
| un seul topic, ou `cleanup.policy=compact` | l'ordre par médicament est ce que le PRD demande ; le compactage ne garderait que le dernier message par clé |
| partitionneur par défaut de librdkafka | partition différente de celle des outils Java et de la console : incohérent en démonstration |
| transaction Kafka par fichier | n'enlève ni l'étape séparée de l'état ni l'exigence de consommateurs idempotents ; ajoute `transactional.id`, le fencing et `read_committed` pour les lecteurs |
| horloge du poste comme horodatage | deux publications du même fichier donneraient deux messages différents |
| une option `--forcer` pour republier un fichier modifié | un événement publié ne se réécrit pas ; rebâtir est explicite et visible |
| `services:` de GitHub Actions pour Redpanda en CI | une seconde configuration du courtier, différente de celle du Mac ; le fichier compose sert aux deux (palier 3) |
| un topic des bilans dès maintenant | pas de consommateur avant le Lot 5 ; un seul publieur et une seule file dans cette mission |
| `verifier-bus` par un groupe de consommateurs et des offsets commités | laisserait une trace sur le courtier et une position à gérer ; relire depuis le début jusqu'aux offsets de fin est la vérification, pas une consommation |
| lire une partition après l'autre | deux fois plus lent (18 s contre 11) pour rien : l'ordre qui compte est celui d'une clé, donc d'une partition |
| comparer deux états complets | deux fois 40 Mo pour `compositions` ; une empreinte par ligne suffit pour dire quelles identités diffèrent |

## Références

PRD v0.4 §6.4, §7.1 · ordre de mission 03 (§0 C à I, décisions 2 à 6,
addendum 1) · `docs/rapports/mission-03/points-a-trancher.md` · ADR 0006 ·
`docker-compose.yml` · `src/pharmaflux/bus/` · `tests/test_bus.py`,
`tests/test_bus_integration.py`.
