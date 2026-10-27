# Mission 04 — Rejeu accéléré et démo : jeu archivé fourni, `make demo`, reliquats de la mission 03

**À :** Claude Fable (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.5 §4 (Lot 1), §6.4, §7.1, §7.3, §9 · mission 03
(`pr.md`, `controle-iec-final.md`) · ADR 0006 et 0007 · `CLAUDE.md` ·
`docs/agents/processus.md`
**Statut :** ordre rédigé le 27/10/2026 — **§0 à traiter avant de coder**
**Branche :** `mission-04-rejeu-accelere-et-demo`, dans `pharmaflux-codeur/`
(préparée par beko avec `preparer-mission.sh`). Trois paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Lis d'abord `CLAUDE.md`, puis `docs/agents/processus.md`, puis le PRD v0.5,
puis cet ordre. Le circuit est celui de la mission 03, messages directs
compris.

## Constat

La mission 03 a fini le socle du Lot 1 sur le Mac : la chaîne écrit en flux,
`publier` alimente un Redpanda local, `verifier-bus` retrouve le dernier
snapshot retenu. Mais le PRD §7.3 n'est pas tenu :

1. **Personne d'autre que beko ne peut voir la chaîne tourner.** Il faut
   l'archive du Mac, rapatriée du VPS, et une suite de commandes connue des
   seuls rapports de mission. Le PRD veut un jeu d'archives **fourni** et un
   `make up`.
2. **Le flux ne se voit pas.** `publier` envoie 164 099 messages en
   30 secondes, sans distinguer l'état initial des changements. Le PRD veut
   un **mode rejeu accéléré** : les jours archivés rejoués en quelques
   minutes, dans l'ordre où ils ont été observés.
3. **Le rythme réel est faible.** Du 24/10 19:41 au 26/10 16:17 UTC (copie
   du Mac au 26/10), en dehors de l'état initial, un seul fichier a changé :
   `CIS_CIP_bdpm.txt`, deux fois. S'y ajoute l'incident du 26/10 14:17 :
   `CIS_InfoImportantes.txt` servi vide, écarté par le garde-fou de volume,
   puis republié à 15:17. La démo doit le montrer **tel quel** (PRD §9,
   « mesure honnête publiée »), sans fabriquer de changements.

**Objectif** : à la fusion, trois choses sont vraies.
- Le dépôt contient un **jeu de démo figé** : des fichiers de la BDPM tels
  qu'archivés, avec leur manifeste, leur source et leur date.
- Sur un clone neuf, avec Docker et uv, **`make up` puis `make demo`**
  rejouent ce jeu sur le Redpanda local, en quelques minutes, dans l'ordre
  des observations. La fin de `make demo` est un `verifier-bus` conforme.
- Les trois reliquats de la mission 03 sont soldés.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Le jeu de démo est dans le dépôt**, sous `demo/`, et non dans une
  release ou un téléchargement. Une démo qui dépend du réseau n'est pas
  reproductible, et le jeu est petit : 5,2 Mo compressés pour toute la copie
  du Mac au 26/10, PDF et page HTML compris. C'est la seule exception à
  « rien de `data/` dans git » ; `CLAUDE.md` la cite.
- **Les fichiers ne sont pas modifiés.** La licence de la BDPM demande la
  citation de la source et de la date, sans altération : le jeu reprend les
  archives à l'octet (même sha256 que le manifeste), jamais un extrait ni un
  échantillon. Le jeu est **figé** : un autre jeu serait un nouveau dossier
  versionné, pas une mise à jour de celui-ci.
- **Le schéma d'événement v1, les contrats, la normalisation, l'enveloppe
  et les topics ne changent pas** (ADR 0006 et 0007). Le rejeu accéléré
  publie les mêmes messages que `publier`, avec les mêmes clés et dans le
  même ordre par topic. Seul le **moment** de leur envoi change. Après un
  rejeu accéléré, `verifier-bus` est conforme, exactement comme après
  `publier`.
- **Les fichiers JSONL restent la référence.** Le rejeu accéléré calcule
  les événements avec `evenements`, puis les publie. Il ne crée pas un
  second chemin de calcul.
- **La chaîne tourne sur l'hôte**, avec uv. Les prérequis de la démo sont
  Docker et uv. Une image de la chaîne, nécessaire pour le VPS, est hors
  périmètre.
- **Aucune nouvelle image Docker.** Redpanda `v26.2.6` et la console
  `v3.13.1` sont déjà sur le poste. Toute commande `docker compose` des
  agents garde `--pull never`, comme à la mission 03.
- **`make` est à beko et à la CI.** Les recettes d'un Makefile échappent au
  garde-fou, `docker` compris. Le garde-fou ne permet donc aux agents que
  `make -n <cible>`, qui affiche les commandes sans les lancer. Tu écris le
  `Makefile`, tu en relis la simulation, et tu lances **toi-même** les
  commandes qu'elle affiche. beko lance `make up` et `make demo` pour la
  démonstration (palier 3) ; la CI les lance à chaque push.
- **Le colima est toujours partagé avec Alamel** (`alamel-dev-postgres`
  sur 5432, `alamel-dev-minio` sur 9000-9001). Rien ne change par rapport à
  la mission 03 : projet `pharmaflux` partout, ports sur `127.0.0.1`, aucune
  commande qui vise un autre conteneur, volume ou image. `make` ne contient
  ni `docker system prune`, ni `volume prune`, ni `image prune`.
- **Les tests unitaires restent hors réseau et hors Docker.** Ce qui a
  besoin d'un courtier est marqué `integration`, comme à la mission 03.

## Sources de données pour cette mission

- **L'archive du Mac, en lecture seule** : `$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data`. Tu n'y écris jamais rien. **Avant ton §0**, demande à
  beko un rapatriement (`rapatrier.sh`) : la copie du Mac s'arrête au 26/10
  16:17 UTC, et le VPS archive toutes les heures depuis.
- **Le jeu de démo** est copié depuis cette archive dans `demo/`, par une
  commande du projet ou un script que tu proposes au §0, jamais à la main.
- **Aucune requête réseau vers les sources** (BDPM, data.gouv, HAS). Le seul
  trafic de la mission va vers le Redpanda local.

## §0 — Points à trancher avant de coder

Réponds point par point dans `docs/rapports/mission-04/points-a-trancher.md`,
commite, puis arrête-toi. Pour chaque point : un constat (ce que tu as
vérifié et comment), ton avis, et ta question s'il y en a une.

- **A. Le contenu du jeu de démo.** Sur la copie rapatriée :
  - ce que `evenements` lit vraiment : quelles archives du bronze, quelles
    lignes du manifeste, et quels champs de ces lignes ;
  - ce qui peut rester dehors : le PDF de documentation, la page HTML, les
    métadonnées d'Open Medic ;
  - la **date de coupure** que tu proposes, et pourquoi ;
  - la taille du jeu dans git, compressé et en tout ;
  - la disposition sous `demo/` (même arborescence que l'archive ?) et un
    `demo/README.md` : source, licence, dates couvertes, sha256 ;
  - les lignes du manifeste reprises : toutes celles des fichiers gardés
    jusqu'à la coupure, `inchange` compris ? Une ligne du manifeste porte
    des champs du serveur (`etag`, `last_modified`…) : dis s'il en est un
    qui ne doit pas être publié, et pourquoi.

  Dis enfin comment le jeu est fabriqué (commande, script) et ce qu'un test
  vérifie : chaque fichier a le sha256 de sa ligne de manifeste, chaque
  archive citée existe, rien d'autre n'est présent. `.gitignore` écarte
  aujourd'hui `*.gz` et `data/` : propose l'exception la plus étroite pour
  `demo/`, sans rouvrir ces deux règles ailleurs.
- **B. Ce que la démo montrera.** Sur la copie rapatriée, compte par jour
  et par fichier les archives `nouveau`, et les événements de chacune
  (`evenements` dans un dossier jetable). Dis ce qu'un spectateur verra
  après l'état initial. L'incident du 26/10 14:17 (fichier servi vide,
  snapshot écarté, aucune `supprimee`) est-il visible, et comment ? Les
  bilans restent des fichiers (mission 03, décision 7) : le rejeu peut les
  lire et les dire, sans les publier.
- **C. Le rejeu accéléré.** Propose la commande (nom, options, valeurs par
  défaut). Les points à traiter :
  - **l'ordre global** : les archives de toutes les entités, rangées par
    date d'observation. Montre que l'ordre par topic reste celui de
    `publier` ;
  - **le chemin de publication** : le rejeu appelle-t-il le code de
    `publier` fichier par fichier, avec le même `publication.json` ? Un
    rejeu interrompu se reprend-il avec `publier --reprendre`, ou avec le
    rejeu lui-même ?
  - **la cadence** : la formule qui transforme l'écart entre deux
    observations en pause. La valeur par défaut doit faire tenir le jeu en
    **5 minutes au plus**. Il faut aussi une valeur sans pause, pour la CI ;
  - **l'état initial** : 164 099 messages. Sont-ils publiés d'un bloc avant
    le premier « tic » de l'horloge, ou étalés ?
  - **les passages horaires inchangés** : faut-il les montrer (l'horloge
    avance d'heure en heure, « rien de neuf ») ?
  - **ce que la commande affiche** : une ligne par archive (heure observée,
    fichier, événements par type, ou snapshot écarté et pourquoi), puis un
    résumé ;
  - **un bus qui n'est pas vide**, ou un `publication.json` d'une autre
    sortie : la commande refuse et dit comment rebâtir le bus. Où va sa
    sortie par défaut, hors de git ?
- **D. Un consommateur à regarder.** Proposition : `pharmaflux suivre`, à
  lancer dans un second terminal, affiche une ligne lisible par événement
  reçu (heure observée, entité, type, clé, colonnes changées). Sans groupe
  ni commit, depuis la fin du topic, ou depuis le début avec une option.
  Avis : apporte-t-il assez, à côté de la console de Redpanda, pour son coût
  en code et en tests ? Quelle est sa sortie si un message n'est pas un
  événement v1 ?
- **E. Le `Makefile`.** Propose les cibles (`up`, `demo`, `verifier`,
  `down`, `rebatir`, `console`…), avec leurs commandes exactes. Les points à
  traiter :
  - la vérification des prérequis, avec un message clair : Docker, uv, et
    les images déjà présentes. `make up` ne télécharge jamais rien ;
  - la compatibilité avec le `make` de macOS, **GNU Make 3.81** (2006) :
    pas de fonction plus récente, pas de `.ONESHELL` ;
  - comment `make demo` enchaîne l'enregistrement des schémas, le rejeu et
    `verifier-bus --racine demo/archive`, et ce qui arrive s'il est relancé
    sur un bus qui a déjà reçu la démo.
- **F. Les reliquats de la mission 03** (contrôle final de l'IeC) :
  1. **le tri numérique de l'historique des schémas** : il est encore vide.
     Avis : le faire maintenant, testé avec `2` et `10`, ou attendre le
     premier schéma qui y entre ?
  2. **`Registre.compatible`** : l'utiliser dans `schemas enregistrer`,
     pour vérifier avant d'enregistrer et refuser avec un message clair, ou
     le retirer. Une méthode utilisée par les seuls tests ne reste pas ;
  3. **le refus explicite d'un fichier hors d'ordre dans `publier`** : un
     fichier qui se range avant le dernier fichier publié de son entité est
     refusé. Le rejeu accéléré devient un second appelant de la
     publication : ce refus entre donc dans cette mission, et non dans
     celle du VPS. Donne le code de sortie, et dis s'il couvre aussi le
     rejeu.
- **G. CI.** Proposition : le job `integration` lance `make demo` sans
  pause, après ses tests, sur un bus neuf. Évalue la durée ajoutée, et dis
  si la démo y est vérifiée par `verifier-bus --racine demo/archive`.
  Dis aussi comment tu vérifies ce job **avant** le push, avec un seul
  push par mission. Le YAML des workflows est désormais relu au commit par
  le crochet `pre-commit` (mission 03, écart 7).
- **H. Toute autre chose** que ta lecture du code, des ADR 0006 et 0007 ou
  de la copie rapatriée te fait remarquer.

## Décisions (sous réserve du §0)

1. **Le jeu de démo** (§0 A) : `demo/`, fabriqué par une commande ou un
   script du projet depuis l'archive en lecture seule, figé à la date de
   coupure arrêtée au §0, avec son `README.md`. Un test, sans réseau,
   vérifie sa cohérence : sha256, manifeste, aucun fichier en trop.
2. **Le rejeu accéléré** (§0 B et C) : une commande qui lance `evenements`
   sur le jeu, puis publie les fichiers d'événements dans l'ordre global des
   observations, avec la cadence arrêtée au §0. Elle dit chaque archive, ses
   événements ou son snapshot écarté, puis un résumé. Elle refuse un bus qui
   n'est pas dans l'état attendu. Le refus d'un fichier hors d'ordre
   (§0 F.3) la couvre.
3. **`pharmaflux suivre`** (§0 D), si le §0 le retient.
4. **Le `Makefile`** (§0 E) : prérequis vérifiés, aucun téléchargement,
   compatible avec GNU Make 3.81. `make demo` finit par `verifier-bus
   --racine demo/archive`, et son code de sortie est celui de la démo.
5. **Les reliquats** (§0 F) : soldés comme arrêté au §0, chacun testé.
6. **CI** (§0 G) : la démo sans pause dans le job `integration`. Le job
   `verifier` ne change pas.
7. **Démonstration sur le Mac** :
   - toi, au palier 2 : les commandes affichées par `make -n demo`, lancées
     une à une, avec les temps, les messages par topic et la mémoire du
     rejeu ;
   - beko, au palier 3 : `make up`, puis `make demo` avec la cadence par
     défaut, dont il te transmet la sortie. Tu la cites dans le rapport.
8. **Docs** :
   - ADR 0008 : rejeu accéléré et jeu de démo (contenu, coupure, cadence,
     ordre global, ce que la démo ne montre pas) ;
   - `README.md` : une section « Démo » en tête de « Lancer », lisible par
     quelqu'un qui découvre le dépôt (prérequis, deux commandes, ce qu'on
     voit, ce que le rythme réel permet de voir et ce qu'il ne permet pas) ;
   - `docs/CONTEXTE.md` et `docs/journal.md`, en fin de fichier.

**Outillage** : aucune dépendance nouvelle attendue. Toute dépendance, de
production ou de test, se justifie au §0.

## Paliers

1. **Jeu de démo et reliquats** : décisions 1 et 5.
   - Le jeu fabriqué, son `README.md`, son test.
   - Les trois reliquats et leurs tests.
   - Python pur, aucune commande `docker`.
   - Rapport, commit.
2. **Rejeu accéléré** : décisions 2 et 3.
   - Tests unitaires sur le bus simulé de la mission 03 : ordre global,
     cadence (sans dormir pour de vrai), refus d'un bus inattendu, reprise.
   - Tests d'intégration sur le vrai courtier, avec les fixtures.
   - Ta démonstration de la décision 7.
   - Rapport, commit.
3. **`Makefile`, CI, docs** : décisions 4, 6, 7 (beko) et 8.
   - `make -n` de chaque cible dans le rapport.
   - Le job de CI, vérifié avant le push comme arrêté au §0.
   - L'ADR 0008 et les docs, avec la sortie de `make demo` lancée par beko.
   - Rapport, commit.

Après le contrôle du palier 3, la suite est celle du circuit :
1. la relecture (`/relire-mission 04`), jusqu'à « CONFORME » ;
2. `pr.md` ;
3. la **revue finale écrite de l'IeC** (`controle-iec-final.md`) ;
4. la publication et la fusion par beko.

**La mission est close** quand beko, sur un **clone neuf** du dépôt après la
fusion, enchaîne `make up` et `make demo` sans autre préparation, et que la
démo finit par un `verifier-bus` conforme.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests unitaires | `uv run pytest -q` (les tests d'intégration sautés sans courtier, et dit) |
| tests d'intégration (paliers 2 et 3) | courtier lancé par `docker compose -p pharmaflux up -d --wait --pull never`, puis `uv run pytest -q -m integration` |
| simulation du `Makefile` (palier 3) | `make -n <cible>` pour chaque cible |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck (même version que la CI) | `uvx --from shellcheck-py==0.11.0.1 shellcheck <fichiers .sh touchés>`, si un `.sh` est touché |
| non-régression | `uv run pharmaflux profil` et `uv run pharmaflux questions verifier` sur `~/pharmaflux-data` ; `pharmaflux evenements` sur la copie du Mac, comparé au `diff -r` à la sortie du code fusionné (`4684292`) |

## Hors périmètre

- **Toute exécution sur le VPS**, et toute modification de la collecte. Le
  VPS-1 reste partagé avec la pré-production d'Alamel jusqu'à mi-novembre.
- Une image Docker de la chaîne : mission du VPS.
- Les consommateurs métier (SCD2, Iceberg, « état à une date ») : **Lot 2**.
- Un topic des bilans et les alertes : **Lot 5**.
- Open Medic : **Lot 4**. Jeu de questions v1 : **Lot 3**.
- Tout changement du schéma d'événement v1, des contrats, des règles de
  normalisation, de l'enveloppe ou des topics.
- Des changements fabriqués pour animer la démo, ou un jeu modifié.
- Toute requête vers les sources ; toute écriture dans l'archive ; toute
  utilisation de l'API Claude ; tout téléchargement d'image.
- **Pas d'usage des VPS d'Alamel**, et rien qui touche aux conteneurs
  d'Alamel du colima ni à la pré-production du VPS-1.
