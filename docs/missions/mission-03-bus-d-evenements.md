# Mission 03 — Bus d'événements : écriture en flux, Redpanda, schémas, file des messages en échec

**À :** Claude Fable (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.4 §4 (Lot 1), §6.2, §6.3, §6.4, §7.1, §7.3, §9 ·
mission 02 (`pr.md`, écarts) · ADR 0005 et 0006 · `CLAUDE.md` ·
`docs/agents/processus.md`
**Statut :** ordre rédigé le 26/10/2026 — **§0 à traiter avant de coder**
**Branche :** `mission-03-bus-d-evenements`, dans `pharmaflux-codeur/`
(préparée par beko avec `preparer-mission.sh`). Trois paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Lis d'abord `CLAUDE.md`, puis `docs/agents/processus.md`, puis le PRD v0.4,
puis cet ordre. Le circuit est celui de la mission 02, messages directs
compris.

## Constat

La mission 02 a fixé le contenu et l'identité des événements.
`pharmaflux evenements` calcule, pour les onze fichiers de la BDPM, la suite
des événements depuis la première archive. La sortie est identique à
l'octet d'un rejeu à l'autre, et la reprise donne le rejeu complet. Mais
deux choses manquent au Lot 1 :

1. **La chaîne tient trop de mémoire.** Elle monte à 474 Mo résidents en
   rejeu complet, contre 256 Mo pour une unité du VPS (ADR 0006,
   « Conséquences » ; PRD v0.4 §9). Les événements d'une comparaison sont
   construits en mémoire avant d'être écrits : 32 439 pour l'état initial
   des compositions. Aucune exécution sur le VPS n'est possible avant que la
   chaîne n'écrive **en flux**.
2. **Les événements ne circulent pas.** Ils sont dans des fichiers JSONL.
   Le PRD §6.4 veut un bus : Redpanda, un topic par entité, un registre de
   schémas, une file des messages en échec, des consommateurs idempotents.

Cette mission finit le socle du Lot 1 sur le Mac. Elle **ne déploie rien
sur le VPS**.

**Objectif** : à la fusion, trois choses sont vraies.
- `pharmaflux evenements` produit **les mêmes octets** qu'à la fusion de la
  mission 02, et sa mémoire de pointe passe nettement sous 256 Mo.
- `docker compose` lance un Redpanda local. `pharmaflux publier` y publie
  les événements, sans perte ni doublon d'identifiant, et reprend là où il
  s'était arrêté.
- Un consommateur de vérification relit les topics et, en appliquant les
  événements, retrouve le dernier snapshot retenu de chaque fichier.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Le schéma d'événement v1 ne change pas** (ADR 0006). Le bus transporte
  l'événement tel que la mission 02 l'écrit : mêmes champs, même
  identifiant, même ordre. Si le bus a besoin d'une information de plus,
  elle va dans l'enveloppe du message (clé, en-têtes), jamais dans
  l'événement.
- **L'écriture en flux est un refactor sans changement de sortie.** Le
  critère est mesurable : un rejeu complet sur la copie du Mac donne une
  sortie identique au `diff -r` près à celle du code fusionné (`647fb6a`),
  et les tests de la mission 02 passent sans changer leurs attendus.
- **Les fichiers JSONL restent la référence.** Ils sont exacts,
  rejouables, et vérifiés par les tests de la mission 02. Le bus est
  alimenté **à partir d'eux**, pas à côté d'eux. Un incident du bus ne
  change jamais un octet de la sortie de `evenements`.
- **Un topic par entité, partitionné par la clé** (PRD §6.4) : tous les
  événements d'un même médicament sont dans l'ordre.
- **Tout sur le Mac.** Redpanda tourne en local, dans le colima de beko.
  Rien sur le VPS : la collecte n'est pas touchée, et le VPS-1 reste
  partagé avec la pré-production d'Alamel jusqu'à mi-novembre.
- **Le colima est partagé avec Alamel.** Il fait aussi tourner les
  conteneurs de développement d'Alamel (`alamel-dev-postgres` sur le port
  5432, `alamel-dev-minio` sur 9000-9001). La mission n'y touche
  **jamais** :
  - le projet compose s'appelle `pharmaflux`, et toute commande `docker`
    nomme ce projet et le fichier compose du dépôt ;
  - tous les ports sont liés à `127.0.0.1` et n'entrent pas en collision
    avec ceux d'Alamel ;
  - aucune commande ne vise un autre conteneur, un autre volume ou une
    autre image : pas de `docker stop`, `rm`, `system prune`,
    `volume prune` ni `image prune`.
- **Les images, c'est beko.** Le premier `docker compose pull` télécharge
  des images : c'est une installation, donc beko la fait, sur une version
  **épinglée** dans le fichier compose. Ensuite, tu peux lancer et arrêter
  le projet `pharmaflux` (`up -d`, `down`, `down -v`) pour tes tests.
- **Les tests unitaires restent hors réseau et hors Docker.** Les tests qui
  ont besoin de Redpanda sont des tests d'**intégration**, marqués comme
  tels. `uv run pytest -q` les **saute** quand aucun courtier ne répond, et
  le dit.

## Sources de données pour cette mission

- **L'archive, en lecture seule** : `$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data`. Tu n'y écris jamais rien. beko la rafraîchit avec
  `rapatrier.sh` quand tu le lui demandes.
- **La sortie de la mission 02 comme référence** : un rejeu complet du code
  fusionné, dans un dossier jetable hors du dépôt, sert d'attendu à la
  non-régression du palier 1.
- **Aucune requête réseau vers les sources** (BDPM, data.gouv, HAS). Le seul
  trafic de la mission va vers le Redpanda local.

## §0 — Points à trancher avant de coder

Réponds point par point dans `docs/rapports/mission-03/points-a-trancher.md`,
commite, puis arrête-toi. Pour chaque point : un constat (ce que tu as
vérifié et comment), ton avis, et ta question s'il y en a une.

- **A. Où va la mémoire.** Mesure, sur la copie du Mac, ce qui fait les
  474 Mo :
  - les deux snapshots d'une comparaison ;
  - la liste des événements ;
  - le tri ;
  - la sérialisation ;
  - ce que garde la `Lecture`.

  Dis quel fichier et quelle archive font le pic. Utilise `tracemalloc`,
  ou la mémoire résidente au pas à pas : la méthode est à ton choix, mais
  dis-la.
- **B. Comment écrire en flux sans changer un octet.** Le tri des
  événements d'une comparaison est global : clé, type, empreinte, rang.
  Propose comment produire les événements dans cet ordre sans tous les
  tenir. Plusieurs pistes sont possibles :
  - une fusion de deux snapshots triés par clé ;
  - des générateurs par clé ;
  - un tri externe ;
  - ou garder la liste, mais réduire ce que chaque événement retient.

  Dis ce que devient l'écriture atomique (fichier temporaire puis
  renommage), et ce que devient `appliquer` dans les tests. Propose une
  **cible chiffrée** de mémoire de pointe, avec une marge sous 256 Mo, et
  la façon de la vérifier dans le rapport. Si tu proposes un test de
  mémoire automatique, il ne doit pas être fragile.
- **C. Client Kafka et schémas.** Une seule nouvelle dépendance de
  production pour le client, au choix : `confluent-kafka` (librdkafka) ou
  une bibliothèque pure Python. Comparer :
  - livraison et idempotence du producteur ;
  - typage pour `mypy --strict` ;
  - roues disponibles pour macOS arm64 et pour Linux en CI ;
  - maintenance.

  Pour le registre de schémas, Redpanda en fournit un : propose le format
  (JSON Schema de l'événement v1, ou autre), la règle de compatibilité, et
  ce que la CI vérifie pour refuser une évolution incompatible (PRD §6.4).
- **D. Topics, clé de partition, enveloppe.** Les points à proposer :
  - le nom des topics (un par entité, dérivé de l'identifiant du
    catalogue ?) ;
  - le nombre de partitions ;
  - la rétention : un topic d'événements se garde-t-il sans limite ?
  - la **clé du message**.

  Pour un fichier à clé, la clé du message est la clé normalisée. Pour un
  fichier ligne à ligne, ce sont les colonnes de la clé déclarée non
  unique : ainsi une `supprimee` et la `creee` qui la remplace restent dans
  la même partition, et dans l'ordre. Vérifie que l'ordre des `supprimee`
  par rang décroissant (ADR 0006) est garanti par partition. Dis enfin ce
  qui va dans les en-têtes (identifiant de l'événement, version du schéma,
  archive ?).
- **E. Publication, idempotence, reprise.** Proposition : `pharmaflux
  publier` lit les fichiers JSONL dans l'ordre de leurs noms et les publie,
  avec un producteur idempotent. Un état de publication, à côté de
  `etat.json`, garde le dernier fichier publié en entier ; il n'est écrit
  qu'**après** l'accusé de réception de tous ses messages.

  Après une coupure, on republie le fichier en cours : des messages peuvent
  donc apparaître deux fois sur le topic, avec le même identifiant. Le
  consommateur les dédoublonne par identifiant (PRD §6.4, « consommateurs
  idempotents »). Évalue cette proposition et compare-la à la transaction
  Kafka par fichier. Dis aussi ce que fait la publication quand `evenements`
  a réécrit un bilan d'archive en attente (F.2 de la mission 02), et quand
  un rejeu complet a recalculé la sortie.
- **F. File des messages en échec.** PRD v0.4 §6.2 : une valeur illisible
  n'y va pas, et la file reçoit « ce que la chaîne ne peut pas publier ».
  Dis précisément ce qui y va :
  - un événement refusé par le schéma ?
  - un message trop gros ?
  - une ligne JSONL illisible ?

  Donne aussi le format d'un message en échec (motif, fichier, numéro de
  ligne, ligne brute), et dis si la publication continue ou s'arrête.
  Faut-il en plus un topic des **bilans** (un snapshot écarté est un
  constat que le Lot 5 voudra voir), ou les bilans restent-ils des
  fichiers ?
- **G. Le consommateur de vérification.** Proposition : `pharmaflux
  verifier-bus` lit chaque topic depuis le début, dédoublonne par
  identifiant, applique les événements avec `appliquer` (mission 02) et
  compare au dernier snapshot retenu, recalculé depuis l'archive. Il dit
  aussi les identifiants en double vus sur le topic (attendus après une
  reprise, jamais après un passage propre). Avis : est-ce le bon test du
  PRD §7.1 côté bus ?
- **H. `docker compose` et Redpanda.** Les points à proposer :
  - l'image et la version épinglée ;
  - le mode mono-nœud et la mémoire allouée : le colima a 6 Gio, partagés
    avec Alamel ;
  - les ports, liés à `127.0.0.1` et sans collision ;
  - un volume nommé ;
  - la console Redpanda, ou non.

  Dis aussi comment un test d'intégration sait qu'un courtier est prêt. Le
  `make up` du PRD §7.3 : faut-il un `Makefile` maintenant, ou un seul
  service ne le justifie-t-il pas encore ?
- **I. CI.** Proposition : un second job, `integration`, avec Redpanda
  en conteneur de service de GitHub Actions, qui lance les tests marqués
  et `verifier-bus` sur les fixtures. Évalue sa durée et la version
  épinglée. Dis aussi comment tu le vérifies **avant** le push : il n'y a
  qu'une CI par mission, et un job qui ne passe qu'en CI est un risque.
- **J. Exemples de messages.** Pour un fichier à clé
  (`bdpm.presentations`) et un fichier ligne à ligne (`bdpm.smr`), écris un
  message complet, tiré des fixtures : topic, partition attendue, clé,
  en-têtes, valeur.
- **K. Toute autre chose** que ta lecture du code, de l'ADR 0006 ou de la
  documentation de Redpanda te fait remarquer.

## Décisions (sous réserve du §0)

1. **Écriture en flux** (§0 A et B) : `evenements` écrit chaque événement
   dès qu'il est produit, dans l'ordre de l'ADR 0006, et garde l'écriture
   atomique par fichier. La sortie est identique à l'octet à celle du code
   fusionné, et la mémoire de pointe est sous la cible arrêtée au §0. La
   mesure se fait avant et après, sur le rejeu complet de la copie du Mac.

2. **`docker-compose.yml`** à la racine (§0 H) : un service Redpanda
   épinglé, projet `pharmaflux`, ports sur `127.0.0.1`, volume nommé. Le
   README dit le premier `pull` (beko), `up -d` et `down`.

3. **Schéma enregistré** (§0 C) : le schéma de l'événement v1 est dans le
   dépôt, enregistré dans le registre de Redpanda par une commande du
   projet, avec sa règle de compatibilité. Un test vérifie que le schéma
   accepte tous les événements des fixtures, et qu'il refuse un événement
   mal formé.

4. **`uv run pharmaflux publier [--sortie …] [--courtier …]
   [--reprendre]`** (§0 D et E) :
   - publie les fichiers JSONL dans l'ordre, un topic par entité, avec la
     clé du §0 D ;
   - écrit son état après l'accusé de réception ;
   - envoie ce qu'il ne peut pas publier dans la file des messages en
     échec (§0 F) ;
   - affiche un résumé par entité : messages publiés, messages en échec,
     fichiers ;
   - sort avec un code non nul si le courtier est injoignable.

5. **`uv run pharmaflux verifier-bus`** (§0 G) : il relit les topics,
   dédoublonne, applique les événements et compare au dernier snapshot
   retenu. Il sort avec un code non nul sur toute différence.

6. **Exactitude du bus** (PRD §7.1), en tests d'intégration :
   - une publication complète, puis `verifier-bus` : aucune différence,
     aucun doublon ;
   - une publication coupée après chaque fichier, puis `--reprendre` :
     aucune différence, et les doublons ne viennent que du fichier
     republié ;
   - un message impubliable fabriqué va dans la file des messages en
     échec, avec son motif, et la suite est publiée.

7. **CI** (§0 I) : le job `integration`, en plus du job actuel, qui ne
   change pas.

8. **Démonstration sur la copie du Mac** (lecture seule) : le rejeu complet
   en flux, avec la mémoire avant et après, et le `diff -r` contre la
   référence ; puis `publier` et `verifier-bus` sur le Redpanda local.
   Donne dans le rapport les temps, les messages par topic, et la mémoire
   de `publier`.

9. **Docs** :
   - ADR 0007 (bus : client, schémas et compatibilité, topics, clés,
     idempotence, reprise, file des messages en échec) ;
   - une mise à jour datée de l'ADR 0006 sur la mémoire (« Conséquences ») ;
   - `docs/CONTEXTE.md` (des événements au bus) ;
   - `docs/journal.md`, en fin de fichier ;
   - `README.md` (`docker compose`, `publier`, `verifier-bus`).

**Outillage** : une dépendance de production pour le client Kafka (§0 C).
Toute autre dépendance, y compris de test (`testcontainers`…), se justifie
au §0.

## Paliers

1. **Écriture en flux** : décision 1.
   - Mesures avant et après (§0 A).
   - Non-régression à l'octet sur la copie du Mac et sur les tests de la
     mission 02.
   - Mise à jour de l'ADR 0006.
   - Rapport, commit.
2. **Redpanda, schéma, publication** : décisions 2, 3 et 4.
   - Le compose, le schéma enregistré, `publier` avec sa file des messages
     en échec.
   - Tests unitaires de l'enveloppe et du schéma, sans Docker.
   - Tests d'intégration de la publication.
   - Rapport, commit.
3. **Reprise, vérification, CI** : décisions 5, 6, 7, 8 et 9.
   - `verifier-bus`, les tests de coupure et de reprise, le job de CI.
   - La démonstration, l'ADR 0007 et les docs.
   - Rapport, commit.

Avant le palier 2, l'IeC étend le garde-fou aux commandes `docker` (projet
`pharmaflux` seulement) ; beko le commite sur `main`. Tu le reçois en
relançant ta session si besoin.

Après le contrôle du palier 3, la suite est celle du circuit :
1. la relecture (`/relire-mission 03`), jusqu'à « CONFORME » ;
2. `pr.md` ;
3. la **revue finale écrite de l'IeC** (`controle-iec-final.md`) ;
4. la publication et la fusion par beko.

**La mission est close** quand trois commandes, lancées sur une copie
rapatriée après la fusion, se suivent sans anomalie :
1. `pharmaflux evenements --reprendre` ;
2. `pharmaflux publier --reprendre`, qui ne publie que les nouveaux
   fichiers ;
3. `verifier-bus`, qui ne trouve aucune différence.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests unitaires | `uv run pytest -q` (les tests d'intégration sautés sans courtier, et dit) |
| tests d'intégration (paliers 2 et 3) | courtier lancé par `docker compose -p pharmaflux up -d`, puis la commande de tests marqués que tu proposes |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck (même version que la CI) | `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh`, si un `.sh` est touché |
| non-régression | `uv run pharmaflux profil` et `uv run pharmaflux questions verifier` sur `~/pharmaflux-data` ; `pharmaflux evenements` comparé au `diff -r` à la référence |

## Hors périmètre

- **Toute exécution sur le VPS**, et toute modification de la collecte.
  L'écriture en flux la rend possible ; la décision de faire tourner la
  chaîne, et le bus, ailleurs que sur le Mac viendra après mi-novembre,
  quand la pré-production d'Alamel aura quitté le VPS-1.
- Le mode rejeu accéléré (PRD §7.3) : mission suivante.
- Les consommateurs métier : SCD2, Iceberg, « état à une date » : **Lot 2**.
- Les alertes sur les snapshots écartés et les messages en échec :
  **Lot 5**.
- Open Medic : **Lot 4**. Jeu de questions v1 : **Lot 3**.
- Tout changement du schéma d'événement v1, des contrats ou des règles de
  normalisation.
- Toute requête vers les sources ; toute écriture dans l'archive ; toute
  utilisation de l'API Claude.
- **Pas d'usage des VPS d'Alamel**, et rien qui touche aux conteneurs
  d'Alamel du colima ni à la pré-production du VPS-1.
