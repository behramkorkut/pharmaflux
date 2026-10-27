# Mission 03 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Fable 5.1) · **À :** IeC, beko · **Date :** 26/10/2026
**Branche :** `mission-03-bus-d-evenements` (sommet `e9ef1fb`, identique à
`main`) · **Ordre lu sur `main`** (commit `3383db9`), après `CLAUDE.md`,
`docs/agents/processus.md` (version `e9ef1fb`, règles `docker` et `colima`)
et le PRD v0.4 (§4, §6.2 à §6.4, §7.1, §7.3, §9, §10).

**Ce que j'ai lu, et comment.** Le code de la mission 02 (`evenements/`,
`contrats/verification.py`, `bronze.py`, `cli.py`), l'ADR 0006, `pr.md` et
le palier 3 de la mission 02, la CI, `pyproject.toml`. La copie rapatriée
`~/pharmaflux-data` (`PHARMAFLUX_DATA` non posée), **en lecture seule** :
21 fichiers, manifeste de 582 lignes, inchangée depuis la mission 02. Les
mesures : trois sondes jetables, bibliothèque standard et modules du projet
seulement, passées sur l'entrée standard de `uv run python -`, dont la
sortie (rejeux compris) est dans le dossier temporaire de la session, hors
du dépôt. **Aucune commande `docker` ni `colima`, aucune requête réseau,
rien d'écrit dans le dépôt ni dans l'archive. Rien n'a été codé.**

**Un refus du garde-fou, signalé sans variante.** En inventoriant le poste,
la commande suivante a été refusée (« docker appelé par which : lance-le en
tête de commande ») :

```bash
which docker colima 2>&1 | head -3
```

Je n'ai pas cherché d'autre voie. Conséquence : je ne sais pas quelle
version de Docker Compose est installée dans le colima de beko ; les
points H et I supposent Compose v2 (`docker compose`, `--wait`).

**Deux limites de ce §0, dites d'avance.** Sans réseau, je ne peux vérifier
ni les versions courantes des bibliothèques Kafka et de leurs roues, ni la
dernière étiquette de l'image Redpanda : les points C et H donnent ce que
je sais et ce qui sera vérifié **au début du palier 2**, avant d'écrire une
ligne qui en dépend.

**Lecture rapide, les constats qui pèsent sur l'ordre :**

1. **Le pic de mémoire a un seul coupable, et il est transitoire** : la
   sérialisation des 32 439 `creee` de `bdpm.compositions`, qui construit
   32 439 chaînes puis leur concaténation (33,7 Mo) avant d'écrire. Le
   reste (snapshots, liste d'événements) est trois fois plus petit. La
   mémoire résidente ne redescend jamais ensuite : c'est le plafond de
   Python, pas une fuite (point A).
2. **`Suivi.resultats` garde tout** : chaque `Resultat` d'une entité, avec
   ses événements et ses snapshots, jusqu'à la fin de l'entité. Rien ne le
   lit. Sur `bdpm.presentations` (trois archives), la mémoire tracée avant
   écriture monte de 54 à 108 Mo d'une archive à l'autre (point K.1).
3. **La ligne JSON la plus longue fait 3 060 octets** (`bdpm.asmr`) : le
   « message trop gros » de F n'arrivera pas sur ces données, il se teste
   avec une ligne fabriquée (point F).
4. **Le partitionneur par défaut de librdkafka n'est pas celui de Java**
   (`consistent_random`, CRC32, contre murmur2) : il faut le fixer pour que
   la « partition attendue » du point J soit la même pour tout client
   (point D).
5. **Rien ne doit venir de l'horloge, le bus non plus** : sans décision,
   l'horodatage du message Kafka serait l'heure du poste. Je propose
   `date_observation` (point D).

## A. Où va la mémoire

**Méthode.** Deux sondes, archive par archive, sur la copie du Mac.

- *Pas à pas* : pour chacune des 17 archives TSV, dans l'ordre du rejeu,
  `tracemalloc` mesure ce que coûte chaque étape de la chaîne réelle :
  `archive.lire()` (octets bruts), `verifier` (la `Lecture`),
  `depuis_lecture` (le snapshot, la `Lecture` libérée), `comparer`
  (liste d'événements, triée), le tri seul (liste mélangée puis triée, pic),
  la sérialisation (`"".join(serialiser(e) …)`, pic). Le snapshot précédent
  reste en vie, comme dans le rejeu.
- *Rejeu réel* : `rejeu.executer`, `_ecrire_resultat` espionné, une passe
  mesure la mémoire résidente (`ru_maxrss`) avant et après l'écriture de
  chaque archive, une seconde passe `tracemalloc` relève le pic tracé avant
  l'écriture (snapshots, liste) et pendant (sérialisation), remis à zéro à
  chaque archive.
- La commande elle-même : `/usr/bin/time -l uv run pharmaflux evenements
  --sortie <jetable>` : **8,2 s, 474 005 504 octets résidents au pic**
  (474 Mo, le chiffre de la mission 02), et `--reprendre` juste après :
  2,9 s, **121 Mo**. `uv run pharmaflux --version` : 36 Mo.

**Constat 1 — le pic est `bdpm.compositions`, archive
`20261024T194148Z__90a6e8ee286b`, pendant la sérialisation.** Mémoire
tracée (Mo) par étape, les six archives les plus lourdes :

| entité (archive) | octets | `Lecture` | snapshot | événements | liste | par evt | tri (pic) | sérialisation (pic) | pic tracé |
|---|---|---|---|---|---|---|---|---|---|
| compositions (24/10 19:41) | 2,6 | 18,6 | ≈ 8 | 32 439 | 29,0 | 0,9 Ko | 5,2 | 99,7 | **153,5** |
| presentations (24/10 19:41) | 4,0 | 18,0 | 18,3 | 20 898 | 22,5 | 1,1 Ko | 2,7 | 73,6 | 125,2 |
| conditions_prescription | 1,3 | 7,8 | ≈ 7 | 28 532 | 23,1 | 0,8 Ko | 3,9 | 70,1 | 104,8 |
| smr | 4,4 | 13,6 | ≈ 7 | 15 547 | 14,0 | 0,9 Ko | 2,1 | 63,5 | 100,3 |
| specialites | 3,0 | 15,0 | ≈ 2 | 15 883 | 17,2 | 1,1 Ko | 2,1 | 55,5 | 96,1 |
| asmr | 4,4 | 11,5 | 14,6 | 10 117 | 9,2 | 0,9 Ko | 1,4 | 47,4 | 75,4 |

Dans le rejeu réel, le pic tracé de `compositions` est **59 Mo avant
l'écriture** (octets, snapshot, tuple d'événements du `Resultat`) et
**218 Mo pendant** : la sérialisation ajoute 159 Mo, soit la liste des
32 439 chaînes JSON (33,7 Mo) que `"".join` sur un générateur construit
d'abord, la chaîne concaténée (33,7 Mo), et les dictionnaires transitoires
de `en_dict`. La mémoire **résidente** du rejeu réel, archive par archive :
93 Mo avant `asmr`, 185 → **286 Mo** sur `compositions`, 352 Mo après
`conditions_prescription`, puis un plateau (Python ne rend pas ses arènes),
376 et 411 Mo sur les deuxième et troisième archives de `presentations`
(constat 3), 430 après `smr`, 444 après `specialites` ; 474 Mo avec
`uv run` et `time`.

**Constat 2 — ce que pèse chaque pièce.**

- *Les deux snapshots d'une comparaison* : 8 à 25 Mo chacun (les tuples
  de valeurs, partagés entre brutes et normalisées quand rien ne change,
  et les `Ligne`). Ils ne font pas le pic : avec trois snapshots en vie,
  `presentations` reste sous 60 Mo tracés avant écriture.
- *La liste des événements* : 0,8 à 1,1 Ko par `Evenement`, soit 29 Mo
  pour `compositions`. Ce qui pèse, ce sont les deux dictionnaires
  `cle` et `apres` (ou `avant`) par événement, les tuples et l'identifiant.
- *Le tri* : 1 à 5 Mo de pic (les clés de tri, 32 439 tuples), rien à
  gagner là.
- *La sérialisation* : la plus grosse part, 100 à 160 Mo de pic sur
  `compositions`, **toute transitoire**.
- *Ce que garde la `Lecture`* : `lignes`, une liste de (numéro, tuple de
  chaînes), et `anomalies` : 18,6 Mo pour `compositions`. Après
  `depuis_lecture`, la `Lecture` meurt, mais ses tuples de brutes vivent
  dans les `Ligne` du snapshot ; ne sont libérés que la liste et les
  paires (numéro, tuple). Les `octets` (2,6 à 4,4 Mo) restent référencés
  par la boucle de `_traiter_entite` jusqu'à l'archive suivante, et le
  texte décodé par `verifier` est transitoire.

**Constat 3 — ce qui s'accumule.** `Suivi.resultats` (constat 2 de la
lecture rapide) garde tous les `Resultat` d'une entité. Sur
`presentations`, pic tracé avant écriture : 54 Mo (première archive), 83
(deuxième, 2 `supprimee`), 108 (troisième, 1 `supprimee`) : trois
snapshots de 25 Mo et le tuple des 20 898 `creee` de la première. Sans
effet sur le pic global aujourd'hui (le pic est `compositions`, une seule
archive), mais c'est une croissance linéaire avec le nombre d'archives par
fichier, ce que le VPS verra en premier.

**Avis.** La cible est atteignable sans toucher aux snapshots : il suffit
de ne jamais tenir ensemble les 32 439 événements fabriqués ni leur JSON.
Plancher mesuré : `--reprendre` sans rien à faire coûte déjà 121 Mo
résidents (interpréteur, imports, manifeste, le plus gros snapshot
recalculé) ; le rejeu complet en flux ne descendra pas en dessous.

## B. Comment écrire en flux sans changer un octet

**Proposition : garder un tri global, mais sur des squelettes ; fabriquer
chaque événement à l'émission ; écrire ligne à ligne.** C'est la quatrième
piste de l'ordre, et la seule qui donne l'identité à l'octet **par
construction** : la clé de tri reste celle d'aujourd'hui, calculée sur les
mêmes valeurs.

1. **`comparer` devient un générateur** (`Iterator[Evenement]`). Il
   construit d'abord la liste des **squelettes** : un tuple léger par
   événement (type, ligne avant ou `None`, ligne après ou `None`, rang) et
   sa clé de tri, calculée comme `Evenement.cle_de_tri` le fait
   (`valeurs_de_cle`, ordre des types, empreinte, rang signé), à partir
   des `Ligne` du snapshot. Il trie cette liste, puis fabrique et cède les
   `Evenement` un à un (`_Fabrique.evenement`). Coût pour `compositions` :
   32 439 tuples de pointeurs, l'empreinte (64 caractères, calculée une
   fois et réutilisée par la fabrique) et la clé de tri, **≈ 6 Mo** au lieu
   de 29 Mo de liste et 100 à 160 Mo de JSON. Aucun événement n'existe
   avant son écriture, aucun ne survit après.
2. **`Resultat` ne porte plus les événements.** Il garde snapshot, verdict
   et dernier retenu, et expose `evenements()` qui **rappelle** `comparer`
   sur demande (rien n'est stocké, un test peut l'appeler deux fois). Les
   comptes par type que le bilan et le résumé affichent sont faits par
   celui qui écrit (un `Counter` rempli en passant) et transmis à
   `bilan.etablir`. `Suivi.resultats` disparaît (K.1). L'ordre des
   résultats de `traiter` et `clore` ne change pas.
3. **L'écriture atomique ne change pas de forme.** `_ecrire_resultat`
   ouvre `.<nom>.jsonl.partiel`, y écrit chaque ligne JSON dès qu'elle est
   produite (tampon d'écriture de Python), ferme, puis `replace` : même
   nom temporaire, même renommage, même ordre événements, bilan, état. Une
   coupure laisse un `.partiel` ignoré par `lire_evenements` (il ne prend
   que `*.jsonl`), comme aujourd'hui.
4. **`appliquer` ne change pas** : il prend un `Iterable`, et les tests
   l'appellent déjà sur `lire_evenements`, qui lit le disque ligne à
   ligne. Les tests qui font `comparer(a, b)` puis indexent la liste
   passent par `list(comparer(a, b))`. Le test « appliquer sur la sortie
   relue du disque redonne le dernier snapshot retenu » reste tel quel.
5. **Petits gains de bord**, dans le même palier : `octets` et la
   `Lecture` meurent dès que le snapshot est construit (lecture et
   construction dans une fonction, pas dans la boucle) ; rien d'autre.

**Pourquoi pas les autres pistes.** La fusion de deux snapshots triés par
clé et les générateurs par clé donnent le même ordre, mais il faut le
**démontrer** : la clé de tri prend les colonnes de la clé dans l'ordre
alphabétique de leurs noms, pas dans l'ordre du contrat (cinq fichiers ont
une clé à plusieurs colonnes), et un fichier ligne à ligne groupe plusieurs
empreintes sous une même `cle` avec les `supprimee` avant les `creee` et
le rang décroissant ; c'est faisable, c'est plus de code et plus de
risque, pour gagner 6 Mo. Le tri externe suppose un fichier intermédiaire
pour éviter 29 Mo : disproportionné.

**Cible chiffrée.** Mémoire résidente de pointe du rejeu complet des onze
fichiers sur la copie du Mac, mesurée par `/usr/bin/time -l` (le même
chiffre qu'au palier 3 de la mission 02) : **≤ 160 Mo**, soit 96 Mo de
marge sous les 256 Mo de l'unité, et l'attendu réaliste autour de 130 Mo
(plancher 121 Mo). Dans le rapport du palier 1 : le tableau de A rejoué
(pic tracé par archive, avant et pendant l'écriture), le `time -l` avant
(474 Mo, commit `647fb6a`) et après, le `diff -r` contre la référence
produite par le code fusionné (déjà faite aujourd'hui dans le dossier
jetable, à refaire au palier), et les 413 tests sans changement d'attendu.

**Test de mémoire automatique : oui, mais un rapport, pas un seuil
absolu.** Un seuil en mégaoctets résidents dépend de la machine, de la
version de Python et de l'allocateur : fragile. Je propose un test
`tracemalloc` sur deux snapshots **fabriqués** dans le test (20 000 lignes,
aucune fixture, quelques centaines de millisecondes) : il mesure la
mémoire tracée des deux snapshots (M), puis le pic tracé pendant l'écriture
en flux de leur comparaison dans un fichier, et exige que le surplus reste
**sous M / 2** (aujourd'hui il vaut environ 3 M). `tracemalloc` compte des
octets d'objets Python, identiques sur le Mac et sur Linux à version de
Python égale ; la marge est d'un facteur six avec le code actuel et
d'environ quatre avec le code en flux. C'est un test de **structure** (rien
n'est accumulé), pas une mesure du VPS : le rapport garde la mesure
résidente. Si l'IeC préfère éviter tout test chiffré, il reste le rapport.

## C. Client Kafka et schémas

**Ce que je ne peux pas vérifier aujourd'hui** : les versions courantes,
le contenu exact des roues et l'état des annotations de type de chaque
bibliothèque (aucune n'est installée dans l'environnement, et pas de
réseau). Ce qui suit est ma connaissance au 26/10/2026 ; la première
action du palier 2 sera `uv add confluent-kafka`, `uv run mypy src` et
l'inspection de la roue installée, consignées dans le rapport.

| critère | `confluent-kafka` (librdkafka) | `kafka-python` (pur Python) | `aiokafka` (pur Python, asyncio) |
|---|---|---|---|
| livraison, idempotence | producteur idempotent mûr (`enable.idempotence`, `acks=all`, ordre par partition conservé malgré les réessais), rapports de livraison par rappel, `flush()` ; transactions disponibles | longtemps sans producteur idempotent ; ajouté dans la reprise du projet en 2025 (2.1), peu éprouvé | idempotence et transactions, API asynchrone |
| `mypy --strict` | historiquement **sans** annotations ni `py.typed` ; des annotations arrivent dans les versions 2.x récentes, à vérifier ; sinon un **stub local** minimal (`stubs/confluent_kafka/`, la dizaine d'appels utilisés) | sans annotations | annotations livrées (`py.typed`) |
| roues macOS arm64 et Linux CI | roues binaires avec librdkafka embarquée pour macOS arm64 et manylinux x86_64 et aarch64 : rien à compiler | pur Python : partout | pur Python : partout |
| maintenance | Confluent, versions régulières, suit librdkafka | un mainteneur, projet arrêté de 2020 à 2024 puis repris | aio-libs, régulier |
| ce que ça impose | une API synchrone, qui va à une commande `typer` ; `AdminClient` inclus (topics, configuration) | API synchrone | un `asyncio.run` dans la commande, un second style de code à lire pour un recruteur |

**Avis : `confluent-kafka`**, la seule dépendance de production nouvelle,
sans ses extras (`[json]`, `[schemaregistry]` tirent `jsonschema`,
`requests`, `fastavro`… que l'on n'utilise pas). Idempotence éprouvée,
`AdminClient` pour créer les topics avec leur configuration depuis le
projet, et la même bibliothèque C que l'outillage Redpanda. Si les
annotations manquent, le stub local est lisible et borne ce que l'on
utilise : `Producer`, `Consumer`, `AdminClient`, `NewTopic`, `Message`,
`KafkaError`, `TopicPartition`.

**Registre de schémas.** Redpanda en embarque un, API REST compatible
Confluent, sur son port 8081. Proposition :

- **format** : **JSON Schema** de l'événement v1, draft 2020-12 si la
  version épinglée l'accepte, sinon draft-07, fichier
  `src/pharmaflux/evenements/schemas/evenement.v1.schema.json`, versionné
  dans le dépôt. Contenu : toutes les propriétés de `en_dict`, requises,
  `additionalProperties: false` (aussi strict que `deserialiser`),
  `version_schema` à `const 1`, les valeurs de `cle`, `avant`, `apres` en
  chaînes, `anomalies` en liste d'objets `{colonne, regle}` ;
- **sujet** : `<topic>-value` (stratégie par nom de topic), un sujet par
  entité donc, tous avec le même schéma ; un sujet pour la file des échecs
  et un pour les bilans si le point F les retient ;
- **règle de compatibilité** : `BACKWARD_TRANSITIVE`. Les consommateurs
  du Lot 2 relisent les topics **depuis le début** avec leur schéma du
  jour : il faut qu'un schéma nouveau lise toutes les versions passées,
  pas seulement la précédente. Un changement incompatible est une
  nouvelle `version_schema`, donc un nouveau topic (`.v2`) et un nouveau
  sujet, jamais une version de plus du même sujet ;
- **enregistrement** : `uv run pharmaflux schemas enregistrer
  [--registre …]`, qui pose la règle sur le sujet puis enregistre le
  schéma (idempotent : le registre rend le même identifiant pour le même
  schéma) ;
- **ce que vérifie la CI** : dans le job `integration`, la commande
  d'enregistrement tourne contre le registre du conteneur, puis l'appel
  `POST /compatibility/subjects/<sujet>/versions/latest` avec le schéma du
  dépôt ; le registre étant neuf à chaque CI, les versions **publiées**
  du schéma sont gardées dans le dépôt (`schemas/historique/`, pour
  l'instant la seule v1) et enregistrées dans l'ordre avant le schéma
  courant : une évolution incompatible est refusée (HTTP 409) et le job
  échoue. En plus, en unitaire et sans Docker : un test valide **tous les
  événements des fixtures** contre le schéma et refuse un événement mal
  formé (décision 3), et un test épingle le sha256 du fichier de schéma
  pour qu'aucune modification ne soit involontaire.

**Une dépendance de test à justifier** : valider un JSON Schema en
unitaire demande un validateur, et la bibliothèque standard n'en a pas.
Options : (a) `jsonschema` dans le groupe `dev` seulement (pur Python,
organisation python-jsonschema, la référence) ; (b) pas de validateur, la
preuve « fixtures ⊂ schéma » ne se fait qu'en intégration, contre le
registre ; (c) un validateur maison pour le sous-ensemble utilisé, que je
déconseille (c'est réécrire une bibliothèque). **Mon avis : (a)**.
Question : d'accord pour `jsonschema` en dépendance de test ?

**Sur le fil.** Je propose que la **valeur du message soit la ligne JSON
telle quelle** (sans le format « magic byte + identifiant de schéma » du
sérialiseur Confluent, qui préfixe cinq octets à la valeur) : le bus
transporte l'événement de la mission 02 à l'octet près, `verifier-bus` le
relit avec `deserialiser`, et l'identifiant de schéma voyage dans un
en-tête (`schema_id`). Le registre sert alors à ce que le PRD lui demande,
la compatibilité refusée par la CI, et à documenter le flux ; il n'est pas
utilisé pour encoder. L'alternative (format Confluent) rend la valeur
lisible par les outils qui l'attendent, au prix d'une valeur qui n'est
plus la ligne du fichier. Question : lequel ?

## D. Topics, clé de partition, enveloppe

- **Noms** : `pharmaflux.<entite>.v<version_schema>`, soit
  `pharmaflux.bdpm.presentations.v1` … onze topics d'événements ;
  `pharmaflux.echecs.v1` pour la file des messages en échec ;
  `pharmaflux.bilans.v1` si F le retient. Le préfixe `pharmaflux` parce
  que le colima est partagé ; l'identifiant du catalogue tel quel, parce
  que c'est lui que porte l'événement (`entite`) ; la version du schéma
  parce que l'ADR 0006 l'a décidé et qu'un `.v2` incompatible sera un
  autre topic. Points seulement, pas de soulignés (Kafka avertit que les
  deux entrent en collision dans les noms de métriques).
- **Partitions** : **3** par topic d'événements, **1** pour les échecs et
  les bilans. Une partition suffirait au débit (164 096 messages une
  fois, puis quelques-uns par heure) ; trois montrent le routage par clé
  et l'ordre par partition sans peser (33 partitions sur un nœud). Le
  nombre est **figé** par l'ADR 0007 : le changer redistribue les clés et
  casse l'ordre par médicament à la frontière.
- **Rétention** : **sans limite** (`retention.ms = -1`,
  `retention.bytes = -1`), `cleanup.policy = delete`, jamais `compact` :
  le compactage ne garderait que le dernier message par clé, c'est
  l'histoire que l'on perdrait. Les événements sont la matière du Lot 2 et
  `verifier-bus` les relit depuis le début. Producteur en
  `compression.type = zstd` : les 172 Mo de JSON pèseront bien moins sur
  le volume (mesuré à la démonstration).
- **Clé du message** : l'objet JSON `cle` de l'événement, compact et à
  clés triées, en UTF-8 : `{"code_cip13":"3400927849800"}` pour un fichier
  à clé ; `{"code_cis":"60570108","code_dossier_has":"CT-21852"}` pour un
  fichier ligne à ligne (les colonnes de la clé déclarée non unique). La
  même fonction pour les deux, lisible dans une console, sans caractère de
  contrôle ; l'alternative, les valeurs jointes par `\x1f` comme dans
  l'identifiant, est plus courte mais opaque. Question : objet JSON ou
  valeurs jointes ?
- **Ordre garanti par partition, vérifié sur le code** : tous les
  événements d'une même `cle` ont la même clé de message, donc la même
  partition. Dans un fichier JSONL, ils sont écrits dans l'ordre de l'ADR
  0006 (`supprimee` par rang décroissant, puis `creee` par rang
  croissant ; pour une ligne qui change, la `supprimee` de l'ancienne
  empreinte avant la `creee` de la nouvelle, même `cle`). `publier` envoie
  les fichiers d'une entité dans l'ordre des noms, et un fichier dans
  l'ordre de ses lignes ; le producteur idempotent conserve l'ordre
  d'envoi par partition même en cas de réessai (c'est ce que l'idempotence
  de librdkafka garantit, avec au plus cinq requêtes en vol). Donc, pour
  une `cle`, le topic restitue l'ordre du fichier. Entre deux `cle`
  différentes, l'ordre n'est pas garanti : il n'a pas de sens métier.
- **Partitionneur** : `murmur2_random`, fixé dans la configuration du
  producteur. Le défaut de librdkafka (`consistent_random`, CRC32) ne donne
  pas la même partition que les clients Java, Redpanda Console ou `rpk` ;
  la partition attendue du point J est calculée avec murmur2.
- **Horodatage du message** : `date_observation` de l'événement
  (`CreateTime`, posé par le producteur), pas l'horloge du poste : deux
  publications du même fichier donnent le même message, et un consommateur
  peut raisonner sur le temps de la source. Les topics restent en
  `message.timestamp.type = CreateTime`.
- **En-têtes** (chaînes UTF-8) : `id` (dédoublonnage sans lire la
  valeur), `version_schema` (`1`), `schema_id` (celui du registre, si C
  retient la valeur nue), `entite`, `type`, `archive` (chemin relatif de
  l'archive comparée), `fichier` (chemin du JSONL sous la sortie, l'unité
  de republication : un consommateur sait d'où vient un doublon),
  `producteur` (`pharmaflux/<version>`). Rien de l'événement n'est
  dupliqué au-delà de ces repères, et rien n'y entre qui n'y soit déjà.
- **Valeur** : la ligne JSONL sans son `\n` final (C, « sur le fil »).

## E. Publication, idempotence, reprise

**Avis sur la proposition : d'accord, avec un état par fichier plutôt que
« le dernier fichier ».**

- **Producteur** : `enable.idempotence = true` (ce qui impose `acks = all`
  et des réessais), `compression.type = zstd`, `partitioner =
  murmur2_random`, `linger.ms` court, `delivery.timeout.ms` 120 s. Les
  rapports de livraison sont collectés par rappel ; `flush()` à la fin de
  chaque fichier.
- **État de publication** : `publication.json` à côté de `etat.json`,
  version 1, par entité la **liste des fichiers publiés** : chemin relatif,
  sha256 du fichier, nombre de messages, nombre d'échecs. Il est réécrit
  (entier, puis renommé) **après** l'accusé de réception de tous les
  messages du fichier, jamais avant. `publier --reprendre` publie, dans
  l'ordre des noms, chaque JSONL de la sortie qui n'est pas dans l'état ;
  sans `--reprendre`, il refuse de tourner si un état existe (comme
  `evenements` repart de zéro, mais ici repartir de zéro republierait tout
  : il faut le dire), sauf `--sortie` neuve.
- **Après une coupure** : le fichier en cours n'est pas dans l'état, il est
  republié en entier ; ses messages déjà acceptés apparaissent deux fois
  sur le topic, même identifiant, même contenu, même horodatage. Les
  consommateurs dédoublonnent par `id` (PRD §6.4) ; `verifier-bus` les
  compte et les attribue au fichier republié (en-tête `fichier`). Taille
  du pire cas : un fichier, 32 439 messages.
- **Pourquoi pas la transaction Kafka par fichier.** Elle rendrait les
  doublons invisibles aux consommateurs en `read_committed`, mais : (1)
  l'écriture de `publication.json` reste une étape séparée après le
  `commit`, et une coupure entre les deux republie le fichier, donc des
  doublons quand même ; la seule vraie fin des doublons serait de mettre
  l'état de publication **dans Kafka**, dans la transaction (le motif
  « offsets dans la transaction »), bien plus lourd ; (2) il faut un
  `transactional.id` stable et gérer le fencing ; (3) `verifier-bus` et le
  Lot 2 devraient lire en `read_committed` ; (4) le PRD exige de toute
  façon des consommateurs idempotents. La transaction n'enlève donc pas
  l'exigence, elle ajoute du code. Si le Lot 2 en veut, Redpanda les prend
  en charge et le producteur est déjà idempotent : rien à défaire.
- **Quand `evenements` a réécrit un bilan d'archive en attente (F.2).** Sur
  le code de la mission 02, cela ne concerne **que les bilans** : quand une
  archive en attente est tranchée, `Suivi.traiter` rend ses résultats dans
  l'ordre des archives (la tranchée, puis la nouvelle), et les deux JSONL
  sont écrits dans la même exécution, dans cet ordre ; un JSONL n'est
  jamais réécrit ni créé « derrière » un fichier déjà publié. L'état par
  liste de fichiers couvre quand même le cas si la chaîne changeait : un
  fichier absent de l'état est publié, quelle que soit sa place dans
  l'ordre des noms. Le bilan réécrit, lui, change de sha256 : si F retient
  un topic des bilans, il est **republié** (un message de plus pour la
  même archive, avec le verdict définitif ; le consommateur garde le
  dernier), et c'est la seule republication volontaire.
- **Quand un rejeu complet a recalculé la sortie.** Les fichiers sont
  effacés et réécrits : soit **à l'identique** (même sha256 : l'état les
  reconnaît, rien à publier, `--reprendre` est sans effet), soit
  **différents** (contrat changé, règle changée) : le même `id` porterait
  deux contenus sur le topic. Proposition : `publier` **refuse** avec un
  code non nul et nomme le fichier dont le sha256 ne correspond plus ;
  pas d'option pour forcer. La voie documentée est de rebâtir le bus :
  `docker compose -p pharmaflux down -v`, suppression de
  `publication.json`, publication complète (ou un topic `.v2` si le schéma
  a changé). Un événement publié n'est jamais réécrit.
- **Résumé affiché** : par entité, fichiers publiés, messages, échecs,
  doublons possibles (fichier republié), durée ; code 1 courtier
  injoignable ou livraison en échec, code 3 si au moins un message est allé
  dans la file des échecs (visible, jamais absorbé, PRD §7.1), code 2
  état illisible ou fichier modifié. Question : d'accord pour un code non
  nul quand la file des échecs a reçu quelque chose ?

## F. File des messages en échec

**Ce qui y va** (topic `pharmaflux.echecs.v1`, une partition, clé =
`entite`) : ce que `publier` **sait nommer et ne peut pas publier**.

1. **Une ligne JSONL illisible** (`deserialiser` lève
   `EvenementInvalide` : JSON cassé, version de schéma inconnue, champ
   manquant ou mal typé) : elle part dans la file avec sa ligne brute. Sur
   nos propres fichiers, c'est un bogue ou une corruption du disque, et le
   signaler là est exactement le rôle de la file.
2. **Un message refusé par le courtier pour sa taille**
   (`MSG_SIZE_TOO_LARGE`, 1 Mo par défaut) : dans la file, avec la ligne
   brute **tronquée** à 64 Ko, `tronquee: true`, la taille réelle et le
   sha256 de la ligne entière ; un message de 2 Mo dans la file échouerait
   à son tour. Constat : la ligne la plus longue de la sortie actuelle fait
   3 060 octets (`bdpm.asmr`), 2 820 pour `presentations` ; ce cas ne se
   produira pas sur ces données, il est **fabriqué** par le test
   d'intégration de la décision 6.
3. **Un événement refusé par le schéma** : avec la valeur nue (C), rien ne
   valide chaque message contre le registre à la publication, et
   `deserialiser` est déjà aussi strict que le schéma ; le cas 1 le couvre.
   Si l'IeC retient le format Confluent, le sérialiseur valide, et un refus
   va dans la file comme le cas 1.

**Ce qui n'y va pas** : une valeur illisible d'une colonne (PRD §6.2, elle
voyage dans `anomalies`), un snapshot écarté (c'est un bilan), et un
**courtier injoignable ou une livraison en échec** (`delivery.timeout`,
erreur non réessayable) : la file est sur le même courtier, elle n'aurait
pas le message ; `publier` **s'arrête** là, code 1, l'état n'avance pas, le
fichier sera republié.

**Format d'un message en échec** (JSON, clés triées, une version à lui) :

```json
{"version_echec":1,"motif":"illisible","detail":"événement mal formé : KeyError('rang')",
 "entite":"bdpm.smr","fichier":"evenements/bdpm.smr/20261024T194150Z__c2215af6b207.jsonl",
 "ligne":12,"id":null,"taille":1150,"sha256_ligne":"…","ligne_brute":"{…}","tronquee":false}
```

`motif` ∈ {`illisible`, `trop_gros`} ; `id` est rempli quand la ligne se
lit ; en-têtes `entite`, `fichier`, `motif`. L'horodatage du message en
échec est celui du courtier (`LogAppendTime` sur ce seul topic) : il n'y a
pas de date de source pour une ligne cassée, et l'heure de l'échec est une
information.

**La publication continue** après un échec : les lignes suivantes partent,
le fichier entre dans l'état avec `echecs: n`, le résumé le dit, le code de
sortie est non nul (E), et `verifier-bus` trouvera la différence tant que
la cause n'est pas corrigée (un fichier corrigé change de sha256 : c'est
alors le cas « fichier modifié », qui refuse ; la voie est de rebâtir).

**Un topic des bilans : oui**, `pharmaflux.bilans.v1`, une partition, clé
= `{"archive": …, "entite": …}`, valeur = le fichier JSON du bilan tel quel,
en-têtes `entite`, `archive`, `decision`. C'est le même publieur de
fichiers, 60 Ko au total, republié quand le sha256 change (un bilan
d'archive en attente tranchée), et c'est ce que le Lot 5 lira pour alerter
sur un snapshot écarté sans ouvrir le disque du Mac. Les bilans restent
aussi des fichiers : ils sont la référence, comme les événements. Si l'IeC
préfère attendre le Lot 5, rien ne manque à la mission.

## G. Le consommateur de vérification

**Avis : oui, c'est le bon test du PRD §7.1 côté bus**, à condition de dire
ce qu'il prouve : que le **transport** n'a rien perdu, rien altéré et rien
désordonné par clé. L'exactitude de la chaîne elle-même reste prouvée par
les tests de la mission 02 sur les fichiers. Précisions :

- **Deux références, pas une.** Par défaut, `verifier-bus` compare au
  **flux de fichiers** de la sortie (`appliquer` sur `lire_evenements`),
  qui ne demande ni archive ni contrat : c'est ce que la CI peut faire.
  Avec `--racine`, il compare en plus au **dernier snapshot retenu
  recalculé depuis l'archive** (`etat.json` donne son chemin,
  `snapshot.lire` le recalcule, `etat_du_snapshot` le met en forme), ce
  que la démonstration sur le Mac fera.
- **Ce qu'il vérifie par topic** : l'ensemble des `id` du topic égale
  celui des fichiers (aucun manquant, aucun étranger) ; les doublons sont
  listés par `fichier` (en-tête) et comparés à ce que `publication.json`
  permet (seul le fichier républié peut en avoir ; après un passage propre,
  zéro) ; la clé du message égale celle calculée depuis la valeur ; la
  valeur relue est égale à la ligne du fichier à l'octet ; `appliquer`
  dans l'ordre du topic (une partition après l'autre, les clés ne se
  mélangent pas entre partitions) ne lève pas et redonne l'état de
  référence. Code de sortie non nul sur toute différence, résumé par
  topic : messages, doublons, partitions, durée.
- **Lecture** : depuis le début (`auto.offset.reset = earliest`), un
  groupe jetable, **aucun commit d'offset** ; fin détectée par les offsets
  de fin lus à l'ouverture (pas par un délai d'inactivité, fragile).
- **Mémoire** : une entité à la fois ; l'état reconstruit pèse ce que pèse
  un snapshot (≈ 25 Mo au plus), l'ensemble des `id` ≈ 20 Mo pour 164 096 ;
  bien sous la cible de B, et mesuré à la démonstration.
- **Sur les identifiants en double** : les dire, oui ; les refuser, non,
  tant qu'ils viennent du fichier que l'état désigne comme républié et
  que leur contenu est identique à l'octet (sinon c'est une différence).

## H. `docker compose` et Redpanda

- **Image et version** : `docker.redpanda.com/redpandadata/redpanda`,
  étiquette **épinglée au correctif près** (`vAA.B.C`), image multi-arch
  (arm64 pour le Mac, amd64 pour la CI). Je ne peux pas lire la dernière
  étiquette publiée sans réseau : je propose que **beko la choisisse au
  moment du premier `pull`** (la dernière de la branche stable courante,
  25.x), qu'il me la donne, et qu'elle soit écrite dans le compose et dans
  la CI avant mon premier `up`. Un seul endroit la porte : le fichier
  compose, que la CI réutilise (I).
- **Mono-nœud et mémoire** : `redpanda start --mode dev-container
  --smp 1 --memory 768M --reserve-memory 0M --overprovisioned --node-id 0
  --check=false`, et `mem_limit: 1g` sur le conteneur. Le colima a 6 Gio
  partagés avec Alamel (postgres, minio) : moins d'un gigaoctet pour
  Redpanda laisse large. `dev-container` relâche les garanties de
  durabilité (fsync) : c'est un bus local de développement, et le rapport
  le dit.
- **Ports, tous sur `127.0.0.1`** et volontairement hors des défauts pour
  ne rien croiser : Kafka `127.0.0.1:19092 → 9092`, registre de schémas
  `18081 → 8081`, HTTP proxy `18082 → 8082`, admin `19644 → 9644` ; les
  adresses annoncées (`--advertise-kafka-addr 127.0.0.1:19092`, idem
  registre et proxy) doivent correspondre, sinon le client est renvoyé vers
  un port injoignable. Aucune collision avec 5432 et 9000-9001 d'Alamel.
- **Volume nommé** : `pharmaflux-redpanda` sur `/var/lib/redpanda/data` ;
  `down` le garde, `down -v` l'efface (rebâtir le bus, E).
- **Projet** : `name: pharmaflux` dans le fichier **et** `-p pharmaflux`
  dans chaque commande (le garde-fou l'exige) ; pour les agents, `up -d
  --pull never`, le `pull` étant à beko ; le README distingue les deux.
- **Console Redpanda** : **oui, en option**, service `console`
  (`redpandadata/console`, épinglée) sous un **profil Compose** `console`
  : `up -d` ne la lance pas, `--profile console up -d` oui, port
  `127.0.0.1:18080`. Elle montre topics, partitions, clés et en-têtes :
  c'est ce qu'un recruteur verra en démonstration, pour 100 à 150 Mo de
  mémoire quand elle tourne. Une seconde image à tirer pour beko.
- **Savoir que le courtier est prêt** : `healthcheck` du service
  (`rpk cluster health --exit-when-healthy` si la version l'a, sinon
  `rpk cluster info`), toutes les 5 s ; `docker compose … up -d --wait`
  attend `healthy`. Côté tests : une fixture pytest de session essaie de
  joindre `PHARMAFLUX_COURTIER` (défaut `127.0.0.1:19092`) avec
  `AdminClient.list_topics(timeout=5)` ; si ça échoue, **tous les tests
  marqués `integration` sont sautés avec le motif affiché** (`-rs` dans
  `addopts`, pour que `uv run pytest -q` le dise), et le marqueur est
  déclaré dans `pyproject.toml` (`--strict-markers` est déjà là). Les
  topics de test portent un suffixe unique par session et sont supprimés à
  la fin.
- **`Makefile`** : **pas maintenant**. Un service, trois commandes dans le
  README (`pull` pour beko, `up -d`, `down`) ; `make up` viendra quand il y
  aura plusieurs services (Lot 2, Iceberg et DuckDB) et plusieurs
  commandes à enchaîner. Un `Makefile` d'une ligne serait de la décoration.

## I. CI

**Proposition : un second job `integration`, mais avec le fichier compose
du dépôt, pas un conteneur de service de GitHub Actions.** Un `services:`
d'Actions ne permet pas de passer la commande du conteneur, or Redpanda se
lance avec `redpanda start` et ses options (mode, mémoire, adresses
annoncées) ; il faudrait dupliquer la configuration dans une forme
différente de celle du Mac. Docker et Compose v2 sont présents sur
`ubuntu-latest` : le job fait `docker compose -p pharmaflux -f
docker-compose.yml up -d --wait`, `uv run pytest -q -m integration`, puis
`uv run pharmaflux publier` et `verifier-bus` sur la sortie d'un
`evenements` joué sur le bronze des fixtures (la suite de `test_rejeu`),
`docker compose logs` en cas d'échec, `down -v` toujours.

- **Durée estimée** : checkout et `uv sync` 30 s (cache), `pull` de
  l'image 30 à 60 s, démarrage 10 s, tests et commandes moins d'une minute
  : **3 à 4 min**, `timeout-minutes: 10`. Le job actuel ne change pas
  (`verifier`), les deux tournent en parallèle.
- **Version épinglée** : celle du compose, une seule source ; l'image
  amd64 de la même étiquette.
- **Vérifier avant le push** : (1) les mêmes commandes, dans le même ordre,
  avec le même fichier compose, tournent sur le Mac à chaque palier, et le
  rapport les consigne ; (2) les tests d'intégration ne lisent **que** les
  fixtures, jamais `~/pharmaflux-data`, pour que la CI ait exactement le
  même jeu ; (3) ce qui diffère malgré tout, et que je nommerai dans le
  rapport : l'architecture (arm64 contre amd64, d'où l'importance des deux
  roues de `confluent-kafka` et du multi-arch de l'image) et la version de
  Compose du runner (d'où `--wait`, présent depuis Compose 2.1). Un job
  qui ne passerait qu'en CI ne peut venir que de là, et c'est borné.

## J. Exemples de messages

Produits par une sonde sur les fixtures (`presentations_a.txt` et
`tests/fixtures/bdpm/CIS_HAS_SMR_bdpm.txt`), avec les contrats du dépôt,
un chemin d'archive de la forme réelle, et la partition calculée par
murmur2 (Kafka) sur 3 partitions. Première ligne de chaque flux dans
l'ordre du tri.

**Fichier à clé, `bdpm.presentations`** (contrat v1)

| champ | valeur |
|---|---|
| topic | `pharmaflux.bdpm.presentations.v1` |
| clé (UTF-8) | `{"code_cip13":"3400927849800"}` |
| partition attendue (3) | **0** (murmur2 ; 3 sur 6 partitions) |
| horodatage | `CreateTime` 1792870906000 (= `2026-10-24T19:41:46Z`) |
| en-têtes | `id=0db35018bddbb4bf1d482adc4f0a9d64947e271fd350c183026985f3faa952ae` · `version_schema=1` · `schema_id=<du registre>` · `entite=bdpm.presentations` · `type=creee` · `archive=bronze/bdpm/CIS_CIP_bdpm.txt/2026-10-24/20261024T194146Z__99759e97dd01.txt.gz` · `fichier=evenements/bdpm.presentations/20261024T194146Z__99759e97dd01.jsonl` · `producteur=pharmaflux/0.1.0` |

Valeur (la ligne JSONL, sans `\n`) :

```json
{"anomalies":[],"apres":{"agrement_collectivites":"oui","code_cip13":"3400927849800","code_cip7":"2784980","code_cis":"60025054","date_declaration_commercialisation":"2014-06-24","etat_commercialisation":"Déclaration de commercialisation","honoraires_dispensation":"2.76","indications_remboursement":"","libelle_presentation":"plaquette(s) thermoformée(s) polypropylène aluminium de 90 comprimé(s)","prix_medicament":"1466.29","prix_public":"1469.05","statut_administratif":"Présentation active","taux_remboursement":"30%"},"archive":"bronze/bdpm/CIS_CIP_bdpm.txt/2026-10-24/20261024T194146Z__99759e97dd01.txt.gz","archive_precedente":null,"archive_precedente_sha256":null,"archive_sha256":"db4169e32ca19f1733f881324762cced0155c25a61fed41a9d607c71c43adfbd","avant":null,"champs_modifies":[],"cle":{"code_cip13":"3400927849800"},"date_observation":"2026-10-24T19:41:46Z","date_source":"2026-10-24","empreinte_ligne":"b74a3492ff63ec8b25bc218055a86a0ed5dbf39f7023ebe9c5633398450f5d33","entite":"bdpm.presentations","etat_initial":true,"fichier":"CIS_CIP_bdpm.txt","id":"0db35018bddbb4bf1d482adc4f0a9d64947e271fd350c183026985f3faa952ae","identite":"cle","rang":1,"type":"creee","version_contrat":"v1","version_schema":1}
```

**Fichier ligne à ligne, `bdpm.smr`** (contrat v0, clé déclarée non unique
`code_cis`, `code_dossier_has`)

| champ | valeur |
|---|---|
| topic | `pharmaflux.bdpm.smr.v1` |
| clé (UTF-8) | `{"code_cis":"60570108","code_dossier_has":"CT-21852"}` |
| partition attendue (3) | **2** (murmur2 ; 5 sur 6 partitions) |
| horodatage | `CreateTime` 1792870906000 |
| en-têtes | `id=37d12fd48ae75bad6b859b0621994ad7c2c17501b63239fce18d656de9553f1c` · `version_schema=1` · `schema_id=<du registre>` · `entite=bdpm.smr` · `type=creee` · `archive=bronze/bdpm/CIS_HAS_SMR_bdpm.txt/2026-10-24/20261024T194150Z__c2215af6b207.txt.gz` · `fichier=evenements/bdpm.smr/20261024T194150Z__c2215af6b207.jsonl` · `producteur=pharmaflux/0.1.0` |

Valeur (le libellé SMR est abrégé ici, `[…]`, il fait 1 700 caractères ;
la valeur réelle est la ligne entière, 2,2 Ko) :

```json
{"anomalies":[],"apres":{"code_cis":"60570108","code_dossier_has":"CT-21852","date_avis":"2026-06-10","libelle_smr":"Le service médical rendu par PRALUENT (alirocumab) 75 mg et 150 mg, solution injectable en stylo prérempli REFLEX sans bouton d’activation, est important uniquement :<br>• en association à un traitement hypolipémiant optimisé […] ;","motif_evaluation":"Inscription (CT)","valeur_smr":"Important"},"archive":"bronze/bdpm/CIS_HAS_SMR_bdpm.txt/2026-10-24/20261024T194150Z__c2215af6b207.txt.gz","archive_precedente":null,"archive_precedente_sha256":null,"archive_sha256":"1c26586a3b176954eff55c7e84d28ec3e1355cca9896b0fbc0764072a408d230","avant":null,"champs_modifies":[],"cle":{"code_cis":"60570108","code_dossier_has":"CT-21852"},"date_observation":"2026-10-24T19:41:46Z","date_source":"2026-10-24","empreinte_ligne":"805128557b2f1be344dcbc06ad8743393c9ba4c5c692f81e8d5eb0c3c44338df","entite":"bdpm.smr","etat_initial":true,"fichier":"CIS_HAS_SMR_bdpm.txt","id":"37d12fd48ae75bad6b859b0621994ad7c2c17501b63239fce18d656de9553f1c","identite":"ligne","rang":1,"type":"creee","version_contrat":"v0","version_schema":1}
```

Une `supprimee` puis une `creee` d'un même couple (CIS, dossier) dont le
libellé change portent la même clé de message, donc la même partition, dans
cet ordre.

## K. Autres remarques

1. **`Suivi.resultats` est écrit et jamais lu** (`volume.py:138,146` ;
   aucune lecture dans `src/` ni `tests/`). Il retient tous les résultats
   d'une entité, événements et snapshots compris : à retirer au palier 1
   (B.2), c'est la croissance linéaire du constat 3 de A.
2. **Le partitionneur** (D) : sans `partitioner = murmur2_random`, la
   partition d'une clé diffère entre notre producteur et tout client Java
   ou outil Redpanda ; à écrire dans l'ADR 0007.
3. **L'horloge** (D) : l'horodatage du message est une décision, pas un
   défaut ; sans elle, deux publications du même fichier donneraient des
   messages différents.
4. **La taille des messages** (F) : 3 060 octets au plus aujourd'hui ;
   `message.max.bytes` reste au défaut, le cas « trop gros » est fabriqué.
5. **Nouveau code de sortie** (E) : `publier` rend 3 quand la file des
   échecs a reçu un message ; à confirmer.
6. **Stub local de typage** (C) : s'il faut un stub pour `confluent_kafka`,
   il vit dans `stubs/` avec `mypy_path`, en français, limité à ce qui est
   appelé ; ce n'est pas une dépendance.
7. **`uv.lock`** change avec la dépendance : la CI fait `uv sync --frozen`,
   le verrou est dans le commit du palier 2.
8. **Le garde-fou et Compose** : `up`, `run`, `create` exigent
   `--pull never` pour les agents ; le fichier compose n'a donc aucune
   directive `pull_policy`, et le README donne la forme humaine et la forme
   agent. Le refus signalé en tête (`which`) m'empêche de dire quelle
   version de Compose est installée : beko peut le dire d'un
   `docker compose version`.
9. **Tests d'intégration et fixtures** : ils rejouent la suite de
   `test_rejeu` (22 archives) dans un bronze temporaire, puis `publier` et
   `verifier-bus` ; quelques centaines de messages, et les coupures de la
   décision 6 se font en interrompant `publier` après chaque fichier par
   une fonction d'arrêt injectée, comme `test_reprise_apres_chaque_point_d_arret`
   coupe le bronze.
10. **Référence de non-régression** : le rejeu du code fusionné
    (`647fb6a` = `e9ef1fb` pour le code) est déjà dans le dossier jetable
    de la session (`m03/reference`, 172 Mo, `diff -r` à faire au palier 1
    contre le rejeu en flux) ; il sera refait si la session change.
11. **Mémoire de `publier`** (décision 8) : lecture ligne à ligne, un
    fichier à la fois, les rapports de livraison en file ; attendu sous
    100 Mo, mesuré à la démonstration comme pour `evenements`.

## Questions pour l'IeC, en une liste

1. B : la cible **≤ 160 Mo** résidents et le test `tracemalloc` en ratio
   (surplus < M / 2) conviennent-ils, ou le rapport seul ?
2. C : `confluent-kafka` sans extras, avec stub local si besoin ;
   `jsonschema` en dépendance de **test** : d'accord ?
3. C : valeur **nue** (la ligne JSONL, `schema_id` en en-tête) ou format
   Confluent (préfixe de cinq octets) ?
4. C : `BACKWARD_TRANSITIVE`, historique des schémas publiés dans le dépôt
   pour la vérification en CI : d'accord ?
5. D : clé de message = objet JSON `cle`, ou valeurs jointes par `\x1f` ?
   3 partitions figées par l'ADR 0007 ? horodatage = `date_observation` ?
6. E : état par liste de fichiers (sha256, comptes) ; refus sans option de
   forçage quand un fichier publié a changé ; code 3 sur échec dans la
   file : d'accord ?
7. F : topic des bilans **maintenant** (`pharmaflux.bilans.v1`, republié
   quand le bilan change), ou au Lot 5 ?
8. G : double référence (fichiers par défaut, archive avec `--racine`) :
   d'accord ?
9. H : beko choisit l'étiquette Redpanda au premier `pull` et me la
   donne ; console en profil optionnel ; ports 19092/18081/18082/19644 ;
   pas de `Makefile` : d'accord ?
10. I : job `integration` sur le compose du dépôt plutôt que `services:` :
    d'accord ?

## Propositions d'évolution

Aucune sur les chemins réservés. Pour l'ADR 0006, une mise à jour datée
de « Conséquences » viendra avec le palier 1 (décision 9). Pour le PRD, à
la prochaine version : §6.4 pourrait nommer le topic par `version_schema`,
la clé de message et l'horodatage `CreateTime` = `date_observation`, une
fois tranchés.
