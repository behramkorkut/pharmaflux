# Mission 10 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Fable 5.2) · **À :** IeC, beko · **Date :** 14/11/2026
**Branche :** `mission-10-mise-en-service-vps` (sommet `d841630`) · **Ordre lu sur `main`** (`d841630`), avec
`CLAUDE.md`, `docs/agents/processus.md`, `infra/agents/vps/README.md` en entier, le PRD v1.1
(§2.2, §4, §7.1, §7.2, §9, §10.1), les ADR 0001, 0006, 0007, 0009, 0010, 0011 et 0013,
`infra/planification/`, `infra/index/README.md`, `docker-compose.yml`, le `pr.md` et le contrôle
final de la mission 09.

## Commandes pour beko

Ce que mon compte ne peut pas lire, et ce qui demande ton geste. Rien n'est urgent pour trancher
le §0, sauf les deux premières, qui conditionnent les mesures du palier 1.

**Sur le Mac**

1. Rafraîchir la copie de l'archive (elle date du 27/10) :

```bash
sh infra/planification/rapatrier.sh --simuler <hote>
```

```bash
sh infra/planification/rapatrier.sh <hote>
```

2. **Une décision, pas une commande** : puis-je lancer `docker compose -p pharmaflux down -v` sur
   le Mac ? La commande efface les volumes `pharmaflux-redpanda` et `pharmaflux-qdrant` (le bus et
   l'index de la démo, reconstructibles par `make demo` à `make index`). Sans elle, je ne peux pas
   publier l'archive réelle sur un bus qui porte déjà les topics de la démo. Les conteneurs
   `alamel-dev-*` ne sont pas concernés. Je ne la lance pas sans ta réponse.
3. L'empreinte multi-architecture de l'image Redpanda, qui n'est épinglée que par son étiquette
   (§0 D) :

```bash
docker buildx imagetools inspect docker.redpanda.com/redpandadata/redpanda:v26.2.6 | head -8
```

4. Les tâches planifiées du Mac (le garde-fou me refuse `launchctl`, même en lecture) :

```bash
launchctl list | grep -i pharmaflux
```

```bash
ls ~/Library/LaunchAgents | grep -i pharmaflux
```

5. La version de `rsync` du Mac, pour la copie des pages d'avis (§0 D : `--chown` n'existe pas
   dans toutes les versions) :

```bash
rsync --version | head -1
```

**Sur le VPS** (session `ssh vps1`)

6. Docker, que je ne peux pas nommer derrière `ssh` :

```bash
sudo docker --version
```

```bash
sudo docker compose version
```

```bash
sudo docker info --format 'pilote={{.Driver}} cgroup={{.CgroupDriver}}/{{.CgroupVersion}} journaux={{.LoggingDriver}} live-restore={{.LiveRestoreEnabled}}'
```

```bash
cat /etc/docker/daemon.json
```

   Ce dernier fichier dit si le relais en espace utilisateur (`userland-proxy`) est coupé : le
   filtrage par adresse des unités en dépend (§0 F). Fichier absent : réglages par défaut, relais
   actif.
7. Le pare-feu et le filtre de sortie :

```bash
sudo ufw status verbose
```

```bash
sudo nft list table inet pharmaflux_sortie
```

8. Le type de `/tmp` (un `tmpfs` compterait dans la mémoire d'une unité, §0 F) :

```bash
findmnt -no FSTYPE /tmp
```

9. La mémoire par groupe, Alamel arrêté :

```bash
systemd-cgtop -1 -m --depth=2 | head -15
```

## Synthèse

**Fait** : rien n'est codé, aucun appel à l'API, aucune requête vers les sources.
- **Le VPS, lu par `ssh pharmaflux-vps`** (lecture seule, session principale) : 3,8 Go dont
  3,25 Go disponibles, 28 Go de disque libres, systemd 259, noyau 7.0, cgroup v2, 2 cœurs Haswell
  (AVX2, sans VNNI). La collecte tourne le code de la **mission 01** (`67d9d3c`, 26/10) : dernier
  passage en 25 s, code 0, pic de 44,6 Mo, score 1,3. L'archive : 29 Mo, 100 archives, 6 116
  lignes de manifeste, **aucune page d'avis**.
- **Le dépôt, lu par huit sous-agents** (lecture seule, sans VPS ni réseau), puis recoupé.
- **Quatre mesures sur le Mac**, sans service : `evenements` en rejeu complet, à vide et avec de
  vrais changements, et `has extraire --verifier` (jamais mesuré jusqu'ici).

Convention : « Mo » et « Go » sont ici en puissances de deux, comme dans les rapports précédents.
Tout ce qui est écrit « je propose » ou « mon avis » attend l'addendum de l'IeC : rien n'est décidé.

**Les six constats qui changent l'ordre** :
1. **La copie du Mac s'arrête au 27/10** (860 lignes de manifeste contre 6 116). Les mesures « sur
   toute l'archive » du §0 L demandent d'abord un `rapatrier.sh` par beko.
2. **Mesurer le bus, le silver et l'index sur le Mac demande d'effacer les volumes** de la démo
   (`down -v`) : j'attends la réponse de beko. Ces mesures passent donc au palier 1, comme l'ordre
   le prévoit ; le §0 L donne ce qui est mesuré et ce qui est estimé, sans les mélanger.
3. **`OnSuccess=` ne suffit pas** : la collecte peut sortir en code 1, donc `failed`, alors
   qu'elle a archivé (lu dans le code ; jamais arrivé sur le VPS, aucune ligne `erreur` en 6 116).
   Et le bon critère d'un changement est `chemin_archive` non nul, pas `statut = nouveau`.
4. **Les 512 Mo sont un seuil mesuré par processus sur le Mac, pas un plafond de cgroup** :
   `index verifier` est à 502 Mo, `index construire` a atteint 624 Mo une fois, et `MemoryMax=`
   compte tout le groupe. La somme des plafonds fait 2 048 Mo en passage horaire, 2 304 Mo quand
   un passage de collecte croise une étape longue.
5. **Trois étapes ne reprennent pas seules dans tous les cas** : un bus vidé, un Qdrant vidé, un
   format changé demandent un geste (`construire`, « rebâtis le silver »). La chaîne doit le dire,
   pas le deviner.
6. **Un p95 n'a pas de sens sur 48 heures** : le manifeste du VPS montre un changement presque
   chaque nuit, et un gros lot le mardi après-midi. Je propose de rendre chaque délai un par un.

**Cinq refus du garde-fou** (quatre de rôle, un de forme), signalés plus bas, aucun contourné.
**Une décision pour beko** (effacer les volumes de la démo sur le Mac) et **31 questions pour
l'IeC**, récapitulées à la fin. Le document est long (≈ 1 200 lignes) : treize points, des
relevés du VPS que l'IeC ne peut pas tous refaire, et les corrections de quatre relecteurs
adverses (sous-agents en lecture seule) passées avant le commit.

## Refus du garde-fou (signalés, non contournés)

| # | Commande | Refus | Ce que j'ai fait |
|---|---|---|---|
| 1 | `ssh pharmaflux-vps '… docker --version …'` | « sudo, su, docker… ne passent jamais par ssh » | relevé relancé sans rien de Docker ; les versions sont la commande 6 pour beko |
| 2 | `ssh pharmaflux-vps '… $D/.local/bin/uv --version …'` | « une commande cachée dans une variable n'est pas jugeable » | chemins écrits en clair, ce que la règle demande ; je n'ai pas lancé l'`uv` du compte de la collecte |
| 3 | `docker volume ls` (Mac) | « hors compose, docker ne fait que lire (ps, images…) » | abandonné ; `docker ps -a` suffit |
| 4 | `launchctl list` (Mac) | « launchctl touche au système » | commande 4 pour beko |

Un cinquième refus tient à ma façon d'écrire, pas à mon rôle : une redirection vers `$S/…`
(« cible d'écriture non jugeable (variable) »), réécrite vers `data/m10/` (hors git).

**À signaler à l'IeC, sans l'avoir essayé** : d'après la lecture du crochet, `/usr/bin/time -l make
<cible>` ne serait pas vu par la règle `make` (la tête jugée est `time`). Je ne m'en sers pas. De
même, rien dans le crochet ne distingue un sous-agent de la session principale : « jamais de ssh
depuis un sous-agent » ne tient qu'à la consigne, que mes huit lecteurs ont reçue et suivie.

---

## A. Le VPS tel qu'il est

### Constat (relevé le 14/11 entre 18:16 et 18:40 UTC)

| Quoi | Valeur |
|---|---|
| Système | Ubuntu 26.04 LTS, noyau 7.0, systemd 259, cgroup v2 |
| Docker, `compose`, règles du pare-feu | non relevés : commandes 6 et 7 pour beko |
| Processeur | 2 cœurs, Intel Haswell sans TSX : `avx`, `avx2`, `fma`, `sse4_2` ; ni AVX-512 ni VNNI |
| Mémoire | 3 814 Mo ; 561 utilisés, 3 253 disponibles ; pression mémoire nulle |
| Échange | 2 047 Mo, 0 utilisé ; `swappiness` 60 ; `overcommit_memory` 0 |
| Disque | 38 Go, 11 utilisés (28 %), 28 libres ; 5 % des inodes |
| Horloge | UTC, synchronisée (NTP) |
| Services | `ufw` actif, `fail2ban` actif, `nftables.service` inactif (voulu), `pharmaflux-sortie` actif, `polkit` actif, `containerd` actif |
| Ports en écoute | 22, 80 et 443 ; 53 (résolveur local) ; un port local élevé (39141) |
| Aucun port de Pharmaflux | ni 16333, ni 18081, 18082, 19092, 19644 : aucun conteneur du projet n'existe encore |
| Redémarrage automatique | aucune ligne `Automatic-Reboot` ; pas de `/var/run/reboot-required` |
| Outils | `uv` 0.10.10 (`/usr/local/bin/uv`), `python3` 3.14.4 (système), `git`, `rsync`, `tar`, `sha256sum`, `flock`, `systemd-analyze` |

**Mon compte** : groupes `pharmaflux` et `pharmaflux-chaine`, `umask 0027`, tranche (`slice`)
plafonnée à 512 Mo (`MemoryHigh` 384 Mo, 200 tâches). `/srv/pharmaflux/{code,derive,modeles}` existent, vides,
aux droits de la procédure. `/etc/pharmaflux/compose/` est vide. Le journal `pharmaflux` existe,
vide. Le filtre de sortie ouvre les cinq ports attendus.

**La collecte** :
- dépôt sur `main`, au commit **`67d9d3c`** (fusion de la mission 01, 26/10) ; `version_collecteur`
  `0.1.0+67d9d3c` dans le manifeste ;
- Python 3.12.13 installé par `uv` sous `/home/pharmaflux/.local/share/uv/python` ;
- dernier passage : 14/11 de 18:17:01 à 18:17:26 UTC, **25 s**, code 0, `MemoryPeak` 44,6 Mo,
  1,50 s de CPU ; score `systemd-analyze security` **1,3** ;
- prochain passage à 19:17 ; l'unité n'écrit pas dans l'espace de journal `pharmaflux`.

**L'archive** : 29 Mo ; `bronze/bdpm` et `bronze/openmedic` seulement ; 6 116 lignes de manifeste,
dont **100 archives** (`nouveau`) et 6 016 `inchange`, aucune `erreur`.

### Avis

- Le VPS a la place : 3,25 Go disponibles pour 2 Go demandés, 28 Go de disque pour 4 à 7 Go dans
  un an (décompte au §0 E).
- **Le processeur est le point faible** : le modèle e5 quantifié en entiers 8 bits profite de VNNI,
  que ce Haswell n'a pas. Le premier remplissage de l'index serait long (estimé au §0 D).
- Les ports qui ne sont pas à Pharmaflux, je n'y touche pas et je ne cherche pas à qui ils sont.
  Ceux de Pharmaflux (16333, 18081, 18082, 19092, 19644) sont libres.

### Questions

1. Le port local 39141 est-il réservé ? Je veux seulement savoir qu'il n'est pas à prendre.

---

## B. La topologie

### Constat

- **Tous les chemins de la chaîne se règlent déjà** par option ou par variable, sans rien changer
  au code : `--racine` ou `PHARMAFLUX_DATA`, `--sortie`, `--entrepot`, `--travail`,
  `--archive-has`, `PHARMAFLUX_MODELES`. Les défauts sont relatifs au dossier courant, ou au
  dossier personnel : inutilisables sur le VPS, il faut tout passer en absolu.
- **L'entrepôt Iceberg grave son chemin absolu** dans ses métadonnées (`silver/entrepot.py`,
  ADR 0009) : il ne se copie pas du Mac, il se rebâtit sur place, et son chemin se choisit une fois.
- **L'état de l'index vit dans Qdrant** (un point de la collection `pharmaflux-index-etat`), pas
  dans un fichier.
- **Aucun fichier temporaire système** dans le code : les écritures sont des `.partiel` à côté de
  la cible. Le dossier de travail de l'index doit rester inscriptible, même pour `index verifier`.
- **Le compose n'a ni `restart:`, ni limite des journaux, ni `memswap_limit`**. Ses plafonds :
  Redpanda `mem_limit: 1g` (`--memory=768M`), Qdrant `512m`. Résidents mesurés au repos sur le Mac
  (mission 07) : 201 Mio et 99 Mio.
- **Dans un second fichier compose**, les listes (`ports`, `volumes`) s'additionnent, `command` et
  `healthcheck.test` se remplacent en entier, les scalaires se remplacent.
- **La procédure du VPS exige des volumes nommés**, sans montage de l'hôte : les données de
  Redpanda et de Qdrant vivront sous `/var/lib/docker/volumes`, pas sous `/srv/pharmaflux/derive`.
- **Le Python** : le système a 3.14, le projet veut 3.12. Celui qu'`uv` installerait pour mon
  compte irait dans mon dossier personnel, que `pharmaflux-chaine` ne lit pas.

### Avis

**Les chemins**

| Quoi | Où | Écrit par | Lu par |
|---|---|---|---|
| Archive (bronze, manifestes, pages d'avis) | `/home/pharmaflux/pharmaflux-data` (inchangé) | `pharmaflux` | chaîne, codeur, beko |
| Code, une version par commit | `/srv/pharmaflux/code/versions/<commit>/` avec son `.venv` | codeur | chaîne |
| Version en service | `/srv/pharmaflux/code/courante` (lien vers une version) | codeur | chaîne |
| Python 3.12 d'`uv` | `/srv/pharmaflux/code/python/` (`UV_PYTHON_INSTALL_DIR`) | codeur | chaîne |
| Fichiers d'événements, bilans, états | `/srv/pharmaflux/derive/evenements/` | chaîne | codeur |
| Silver | `/srv/pharmaflux/derive/lakehouse/` | chaîne | codeur |
| Travail de l'index, cache des vecteurs | `/srv/pharmaflux/derive/index/` | chaîne | codeur |
| Journal des passages, verrou | `/srv/pharmaflux/derive/chaine/` | chaîne | codeur |
| Modèle | `/srv/pharmaflux/modeles/e5-small-int8/<révision>/` | beko (root) | chaîne |
| Bus, base vectorielle | volumes `pharmaflux-redpanda`, `pharmaflux-qdrant` | conteneurs | — |
| Fichiers compose | `/etc/pharmaflux/compose/docker-compose.yml` et `vps.yml` | beko (root) | root |

Les noms `versions/<commit>`, `courante`, `vps.yml`, `pharmaflux-chaine.service` et `infra/vps/`
sont ceux que supposent déjà les tests du garde-fou : je les reprends.

**Les conteneurs** : une unité système, pas Docker sans root.
- `pharmaflux-conteneurs.service`, `Type=oneshot` avec `RemainAfterExit=yes` :
  `docker compose -p pharmaflux -f … -f … up -d --wait --pull never` au démarrage, `stop` à
  l'arrêt, jamais `down -v`.
- Son lien avec Docker serait `After=` et `Wants=docker.service`, **ni `Requires=` ni
  `PartOf=`** : sinon une mise à jour du paquet Docker arrêterait l'unité, `stop` marquerait les
  conteneurs arrêtés à la main, et `unless-stopped` ne les relèverait plus.
- La chaîne s'y lierait par `After=` et `Wants=` seulement : elle teste elle-même la santé des
  services, et une dépendance dure la ferait échouer sans une ligne dans son journal.
- `--wait-timeout`, `TimeoutStartSec=` et `TimeoutStopSec=` (plus long que `stop_grace_period`)
  explicites. Un conteneur arrêté à la main se relève par `restart` de l'unité : la procédure le
  dirait.
- Docker sans root ajouterait un second démon, sa mémoire et sa surface, pour un gain que la
  règle « tout fichier que root lit passe par l'IeC puis beko » donne déjà.
- `restart: unless-stopped` dans `vps.yml` relève un conteneur qui tombe ; l'unité les lance au
  démarrage du VPS et sert de point de pilotage et d'ordre (`After=`) pour la chaîne. Les deux se
  complètent, à condition que l'arrêt de l'unité soit `stop`.

**Le fichier `vps.yml`** ne porte que des scalaires qui se remplacent proprement :
`restart`, `mem_limit`, `memswap_limit` égal à `mem_limit` (pas d'échange), `stop_grace_period`,
`logging` plafonné, et peut-être `cpus` (voir M). **Ni `ports`, ni `volumes`, ni
`command`, ni `image`** : un test hors Docker le vérifie, avec la liste de contrôle de l'IeC
(volumes nommés, ports sur `127.0.0.1`, aucun privilège). `docker-compose.yml` ne change pas, sauf
si l'empreinte de Redpanda y entre (§0 D).

**Les plafonds**

| Groupe | Plafond proposé | Résident connu |
|---|---|---|
| Redpanda | 1 Go (inchangé) | 201 Mio au repos (Mac) |
| Qdrant | 512 Mo (inchangé) | 99 Mio au repos, avant les vecteurs creux et les avis |
| Unité de la chaîne (passage horaire) | `MemoryMax=512M`, `MemorySwapMax=0` | 56 à 502 Mo selon l'étape (Mac, par processus) |
| Unité de vérification, unité de remplissage | 512 Mo chacune ; même verrou que le passage, donc jamais deux à la fois | 444 à 502 Mo ; 624 Mo vus une fois |
| Collecte | 256 Mo (inchangé) | 44,6 Mo |
| Tranche du codeur, tant que le compte est ouvert | 512 Mo (posé par beko) | `uv sync`, `chaine etat` |
| **Somme, passage horaire** | **2 048 Mo** (1 024 + 512 + 512) | — |
| **Somme, une étape longue croise la collecte de `:17`** | **2 304 Mo** | — |
| **Somme, avec une session du codeur en plus** | **2 816 Mo** | — |

La collecte part à `:17` quoi que fasse la chaîne : le remplissage, une vérification ou un passage
de plus d'une heure la croisent. Le résident réel reste loin de ces sommes (300 Mo de conteneurs
au repos, 45 Mo de collecte), mais les plafonds, eux, dépassent 2 Go dans ces deux cas.

Je ne propose pas de baisser le plafond de Redpanda : `--memory` est dans `command`, qu'il
faudrait recopier en entier dans `vps.yml`, au risque d'une dérive entre le Mac, la CI et le VPS.

**Le point dur** : `index verifier` a été mesuré à **502 Mo** chez beko (mission 09), et
`index construire` à 415 à 493 Mo, avec un pic de **624 Mo** vu une fois à la mission 07, jamais
expliqué ni reproduit. Ce sont des résidents d'un processus, sur le Mac. Un `MemoryMax=512M`
compte tout le groupe : la commande `chaine`, l'étape, son sous-processus quand ils coexistent,
et le cache de pages. Au dépassement, le noyau tue un processus du groupe ; par défaut systemd
arrête alors toute l'unité (`OOMPolicy=stop`), et la chaîne n'écrirait ni sa ligne de journal ni
le geste à faire. Je propose `OOMPolicy=continue` : la commande `chaine` voit l'étape tuée, l'écrit
et sort en 1. Trois sorties possibles pour le plafond lui-même :
- (a) mesurer d'abord sous cgroup au palier 1 (`MemoryPeak`, `memory.events`), et ne rien changer
  si la mesure passe ;
- (b) donner à l'unité de vérification un plafond à part (640 Mo), ce qui porte la somme des
  plafonds à 2,2 Go alors que le résident réel reste loin dessous ;
- (c) reprendre le correctif reporté par la mission 09 (réencoder l'échantillon par lots plus
  petits ou en sous-processus), qui touche le code sans toucher au calcul.
Mon avis : (a), puis (c) si la mesure échoue. Pas (b).

### Questions

2. La règle du contrôle, « aucun `Environment`, `WorkingDirectory` ou fichier lu par root ne pointe
   vers `/srv/pharmaflux/code` ou `/srv/pharmaflux/derive` », vise-t-elle aussi les variables d'une
   unité en `User=pharmaflux-chaine` ? Son `ExecStart=` est forcément sous `code/courante`, et ses
   chemins de données sous `derive`. Je propose : pas de `WorkingDirectory=` (donc `/`), et les
   chemins passés en arguments de la commande plutôt qu'en `Environment=`.
3. Les « 2 Go » portent-ils sur la somme des plafonds (2 048 Mo en passage horaire, 2 304 Mo
   quand la collecte croise une étape longue) ou sur le résident mesuré ? Mon avis : sur le
   résident mesuré, les plafonds servant de garde par groupe.
4. Pour `index verifier` et `index construire` : (a) puis (c), comme proposé, et
   `OOMPolicy=continue` ?
5. Le Python de la chaîne : le sien, sous `/srv/pharmaflux/code/python` (indépendant de la
   collecte, 100 Mo de plus), ou celui de la collecte, lisible par le groupe `pharmaflux` ? Mon
   avis : le sien.

---

## C. L'enchaînement

### Constat

**Le déclencheur**
- `pharmaflux collecte` sort en **1** dès qu'une ligne a le statut `erreur`. Ce statut couvre un
  échec, mais aussi une archive **écrite et signalée** (`lien_absent`, `lien_change`,
  `analyse_impossible`) et un simple signalement (`lien_nouveau`), qui se répètent à chaque passage
  tant que le catalogue n'est pas corrigé dans le code. L'unité finit alors `failed`, ce que le
  README assume.
- Un `OnSuccess=` seul ne partirait donc pas dans ce cas, peut-être pendant des jours, alors que
  des archives arrivent. Le cas est lu dans le code : en trois semaines, le manifeste du VPS ne
  compte aucune ligne `erreur`.
- **Le code 1 est ambigu** : il couvre aussi un passage avorté avant toute collecte (manifeste
  illisible).
- **Le critère d'un changement est `chemin_archive` non nul** dans le manifeste (c'est déjà celui
  de `pharmaflux etat`), pas `statut = "nouveau"`.
- Le manifeste n'a pas de ligne de fin de passage : la fin se lit à l'arrêt de l'unité.
- Un passage dure 25 s (douze entrées, deux secondes de pause entre elles).

**Les étapes, telles qu'elles sont**

| Étape | Commande | Reprise | Codes |
|---|---|---|---|
| 1 | `evenements --reprendre` | `etat.json` par entité ; sans état, rejeu complet ; fichiers écrits entiers puis renommés | 1 archive illisible (les autres entités continuent), ou exception non attrapée (manifeste corrompu, fichier intrus dans le bronze) ; 2 contrat changé |
| 2 | `schemas enregistrer` | idempotent | 1 registre injoignable **ou** schéma incompatible |
| 3 | `publier --reprendre` | `publication.json` par fichier ; le fichier coupé est republié, ses doublons portent le même `id` | 1 bus injoignable ; 2 refus ; 3 file des échecs |
| 4 | `silver consommer` | position dans la table Iceberg, dans la même transaction que les données | 1 bus injoignable ; 2 refus (bus vide, bus rebâti, contrat) |
| 5 | `index mettre-a-jour` | `vise` puis `instant` dans l'état ; verrou `flock` | 0 « rien à faire » ; 2 refus, verrou tenu **et** Qdrant injoignable |

- **Les codes ne suffisent pas à classer une panne** : un service injoignable donne 1 pour le bus
  et 2 pour l'index ; le code 1 couvre aussi toute trace Python (disque plein, catalogue).
- **La reprise, étape par étape** :
  - `evenements` : prouvée sur le Mac aujourd'hui. Un rejeu jusqu'au 26/10, puis `--reprendre` sur
    les archives du 27/10, donne une sortie **identique à l'octet** au rejeu complet (`diff -rq`
    vide). Le test `tests/test_rejeu.py` coupe après chaque archive d'une suite de 22 ;
  - `publier` : testée pour une coupure dans chaque fichier (`tests/test_bus_integration.py`,
    ADR 0007) ;
  - `silver consommer` : trois points de coupure testés par exception simulée, **pas par arrêt du
    processus** (mission 05) ;
  - `index mettre-a-jour` : le jeu en quatre tranches (`tests/test_index_tranches.py`).
  Aucune de ces preuves n'est un `kill` sur amd64 : un arrêt forcé pendant le remplissage serait
  à faire au palier 1.
- **Un seul verrou existe** dans le code, celui de l'index. `evenements` et `publier` ont un
  fichier temporaire à nom fixe ; `silver consommer` n'a que le verrou optimiste du catalogue.
- **Le garde-fou de volume ne bloque jamais** : un fichier servi vide est archivé, écarté, code 0,
  aucun événement. Le cas est réel : le manifeste du VPS compte 29 archives de
  `bdpm.infos_importantes`.
- **Ce qui ne reprend pas seul** :
  - `silver consommer` refuse (2) si aucun topic n'existe, ou si le bus a été rebâti autrement ;
  - `index mettre-a-jour` refuse (2) sans index, sur un autre format, un autre extracteur ;
  - `make index` choisit entre construire et mettre à jour par un test qui confond « pas d'index »
    et « Qdrant injoignable », les deux en code 2 ;
  - une construction coupée laisse une collection orpheline que rien n'efface.

### Avis

**Le déclencheur** : un fichier de complément (`drop-in`) de l'unité de collecte, livré dans
`infra/vps/`, installé par beko sous `/etc/systemd/system/pharmaflux-collecte.service.d/` :
`OnSuccess=` **et** `OnFailure=` vers `pharmaflux-chaine.service`.
- La chaîne part à la fin exacte du passage, quel que soit son code : après un succès, un code 1,
  un délai dépassé ou un dépassement mémoire. Si la collecte n'a rien archivé, la chaîne passe à
  vide. Pas de boucle possible : la chaîne n'a aucun `OnFailure=` en retour.
- **Le manifeste ne sert pas à sauter des étapes** (voir « le passage à vide ») : il sert au
  journal des passages et à la mesure de fraîcheur, par le critère `chemin_archive`.
- systemd passe à l'unité déclenchée le nom et le résultat de celle qui l'appelle
  (`MONITOR_UNIT`, `MONITOR_SERVICE_RESULT`, `MONITOR_EXIT_STATUS`) : de quoi remplir le champ
  « déclencheur » du journal.
- Le fichier `pharmaflux-collecte.service` du dépôt et du VPS ne change pas d'un octet ; le
  complément se retire d'un `rm`.
- Un petit minuteur (`OnBootSec=2min`) relancerait la chaîne après un redémarrage, pour finir un
  passage coupé sans attendre `:17`. Avec `Persistent=true` côté collecte, la chaîne peut alors
  partir deux fois au démarrage : la seconde trouve le verrou ou passe à vide.
- Limites connues : un `systemctl stop` de la collecte en cours déclenche aussi la chaîne (sans
  dommage) ; un déclenchement perdu n'est rejoué qu'à l'heure suivante.
- Si l'IeC lit « la collecte (inchangée) » comme « aucun complément non plus », le repli est une
  unité `.path` sur `manifeste/collecte.jsonl` avec `After=pharmaflux-collecte.service`, qui attend
  la fin du passage en cours (mais ne part jamais si la collecte meurt avant sa première ligne).
  Je préfère le complément : il part une fois, au bon moment.

**La commande** : `pharmaflux chaine passer`, en Python, pas un script shell.
- Elle prend un verrou `flock` non bloquant sur `derive/chaine/verrou`. Verrou tenu : une ligne de
  journal, code 0, ce n'est pas une panne.
- Elle lance chaque étape **dans un sous-processus** (`python -m pharmaflux …`), avec les mêmes
  commandes et les mêmes options que beko taperait. Rien ne change dans le calcul, les codes de
  sortie restent ceux des commandes, et le pic du groupe est celui d'une étape, pas leur somme.
- Elle écrit une ligne par passage dans `derive/chaine/passages.jsonl` (§0 H).
- Elle teste la santé du bus, du registre et de Qdrant **avant** chaque étape qui s'en sert : une
  panne de service se classe par ce test, pas par le code de la commande (Qdrant injoignable
  sort en 2 comme un refus).

**Ce qu'une étape en échec arrête**

| Cas | Suite du passage | Code de la chaîne |
|---|---|---|
| `evenements` 1, avec son résumé par entité (une archive illisible) | continue : les autres entités sont justes, l'aval reprend par fichier | 1, signalé |
| `evenements` 1 sans résumé (trace Python) | s'arrête | 1 |
| `publier` 3 (file des échecs) | continue : le bus reste cohérent | 1, signalé |
| service injoignable au test de santé (bus, registre, Qdrant) | s'arrête ; le passage suivant reprend | 1 |
| étape tuée (mémoire, délai) | s'arrête ; le passage suivant reprend | 1 |
| code 2 d'une étape, services sains (refus) | s'arrête ; ne se réparera pas seul | 2, avec la phrase du refus et le geste à faire |

L'unité finit `failed` dans tous ces cas : l'erreur se voit dans `systemctl`, comme pour la
collecte. Le passage suivant repart de l'étape 1, chacune sautant ce qu'elle a déjà fait.

**Sans index** : en service, je propose que `chaine passer` ne construise pas. Elle refuserait (2)
en nommant la commande de remplissage (§0 D). Une construction durerait sans doute plus d'une
heure sur ce VPS (estimé) : elle ne doit pas partir seule d'un passage horaire.

**Le passage à vide** : pas de court-circuit au palier 2. Chaque étape est lancée et répond
« rien à faire » : c'est ce qui prouve la reprise à chaque heure, sans chemin particulier.
Coût sur le Mac, par étape : 3,1 s et 135 Mo (`evenements`, mesuré aujourd'hui), 0,1 à 0,4 s
(`publier`), 0,3 s et 141 Mo (`silver consommer`), 2,5 s et 422 Mo (`index mettre-a-jour`, sans
les avis). Soit environ 6 s mesurées sur le Mac, **sans les avis**. Avec `--archive-has`, chaque
passage réextrait les pages rattachées (8 s pour les 722 pages, mesuré aujourd'hui hors index) :
sans doute 10 à 15 s sur le Mac, jamais mesuré, à multiplier par deux à quatre sur le VPS. Si la
mesure du palier 1 dépasse la minute, je proposerai un court-circuit sur le manifeste.

### Questions

6. Le complément `OnSuccess=` et `OnFailure=` de l'unité de collecte est-il permis, ou la collecte
   « inchangée » l'exclut-elle (repli : unité `.path`) ?
7. Les quatre règles d'arrêt du tableau conviennent-elles, en particulier « continuer » après
   `evenements` 1 et `publier` 3 ?
8. `chaine passer` sans index : refuser et nommer le geste (mon avis), ou construire seule ?
9. Verrou tenu : code 0 et une ligne (mon avis), ou code non nul ?

---

## D. Le premier remplissage

### Constat

- **Volumes au 14/11** : 73 archives des onze fichiers sur le VPS (22 sur la copie du Mac), dont
  29 d'`infos_importantes` et 19 de `presentations`. Sur le Mac, 724 fichiers d'avis (722 pages,
  `robots.txt`, mentions légales), 13 Mo, et `manifeste/has-pages.jsonl` (724 lignes, 588 180
  octets).
- **Les pages d'avis doivent être là avant la première construction** : un index bâti sans
  `--archive-has` ignore ensuite l'option en silence, et faire entrer 722 pages par incrément
  ferait encoder pendant l'écriture, le cas que la mission 09 a mesuré à 586 Mo.
- **Un `rsync` de la racine écraserait le manifeste vivant** : `manifeste/collecte.jsonl` du Mac
  date du 27/10.
- **Ce que vérifie `has extraire --verifier`** : elle relit le manifeste, prend la dernière
  archive de chaque page et la réextrait. Quatre contrôles : la non-altération (un second
  lecteur), le déterminisme (deux extractions, même empreinte), l'empreinte du texte contre celle
  du manifeste sous la version d'extracteur consignée, et les changements de statut d'une version
  à l'autre. Elle **n'écrit rien dans l'archive**. Codes : 0 conforme, 1 écart, 2 aucune page ou
  manifeste corrompu.
- La sortie normale, relevée aujourd'hui sur le Mac : « 722 page(s) : 721 extraite(s),
  1 rejetée(s) (dossier_incoherent 1) ; extracteur v2 », dix « sans contrôle de dossier », et
  des lignes « statut changé » de la v1 à la v2. C'est ce que beko doit retrouver sur le VPS.
- Elle ne compare **pas** le sha256 des octets au manifeste ; c'est l'index qui le fait, pour les
  pages rattachées.
- **Le modèle** : quatre fichiers épinglés par sha256, 134 Mo. Le code ne télécharge rien à
  l'exécution : il vérifie les empreintes et refuse (code 2) si un fichier manque.
- **Les images** : Qdrant est épinglée par l'empreinte de son index multi-architecture ; Redpanda
  et la console ne le sont que par leur étiquette.

### Avis

**Les étapes**, dans cet ordre, la chaîne horaire ne pouvant pas s'y glisser (même verrou) :

| # | Qui | Quoi | Vérification |
|---|---|---|---|
| 1 | beko | fichiers compose (contrôlés), puis images, puis unité des conteneurs | empreintes des images ; `up --wait` sain ; cinq ports sur `127.0.0.1` |
| 2 | beko | modèle | `index modele verifier e5-small-int8` : code 0 |
| 3 | beko | pages d'avis copiées du Mac | 724 fichiers ; manifeste de même sha256 ; `rsync -rnci` sans ligne de fichier |
| 4 | codeur | dépôt du code, `uv sync` | aucun fichier hors du groupe `pharmaflux-chaine` ; `pharmaflux --version` sous l'unité |
| 5 | chaîne | `has extraire --verifier` | code 0 ; 721 extraites, 1 rejetée |
| 6 | chaîne | `evenements --reprendre`, `schemas enregistrer`, `publier --reprendre` | `verifier-bus --racine` |
| 7 | chaîne | `silver consommer` | `silver verifier` : N/N |
| 8 | chaîne | `index construire --archive-has` | `index verifier` conforme ; `index etat --complet` |

Je propose que les étapes 5 à 8 soient une commande, `pharmaflux chaine remplir`, lancée par une
unité à part (`pharmaflux-remplissage.service`, même durcissement, délai de plusieurs heures,
quota de processeur plus large), que je piloterais par polkit si l'IeC l'y inscrit, et que je
mesurerais par `MemoryPeak` et le journal.

**Durées et résidents estimés**

| Étape | Mac, mesuré | VPS, estimé | Résident |
|---|---|---|---|
| `has extraire --verifier` (722 pages) | 8,1 s (aujourd'hui) | 20 à 30 s | 56 Mo |
| `evenements` complet | 9,6 s pour 22 archives (aujourd'hui) | 1 à 2 min pour 73 archives | 200 Mo |
| `publier` complet | 29,8 s (mission 03) | 1 à 2 min | 59 Mo |
| `silver consommer` complet | 12,9 s (mission 05) ; 14,2 s par `make silver` (mission 06) | 30 à 60 s | 357 Mo |
| `silver verifier` | 10 à 11 s pour 22 archives | 2 à 4 min pour 73 archives | 310 à 341 Mo |
| `index construire`, cache vide | 18 min (fiches) et environ 6 min (avis) | **1 h 15 à 2 h, sur deux cœurs** | 415 à 493 Mo ; 624 Mo une fois, non reproduit (mission 07) |
| `index verifier` | 28 à 55 s | 2 à 4 min | 444 à 502 Mo |

L'estimation du VPS est un facteur deux à quatre, cinq pour l'encodage (Haswell sans VNNI) :
**aucune étape n'a jamais tourné sur amd64 hors de la CI**. Elle suppose les deux cœurs : sous un
quota d'un seul (§0 F), l'encodage serait plus long encore. Les mesures du palier 1 la
remplaceront.

**Le cache des vecteurs** : mon avis est de ne pas le copier du Mac (question 12). L'encoder sur
place prouve que tout le dérivé se reconstruit depuis l'archive, et sur l'architecture qui
servira. Une fois bâti, il reste : une reconstruction de l'index depuis le cache prend moins d'une
minute sur le Mac.

**La copie des pages d'avis**, par beko, depuis le Mac. Deux sources nommées, jamais la racine.
`<hote>` est ici l'alias qui ouvre le compte de beko (`sudo`), donc avec sa phrase de passe :

```bash
rsync -a --ignore-existing --exclude='.DS_Store' --chown=pharmaflux:pharmaflux --chmod=D750,F640 --rsync-path='sudo rsync' ~/pharmaflux-data/bronze/has/ <hote>:/home/pharmaflux/pharmaflux-data/bronze/has/
```

```bash
rsync -a --ignore-existing --chown=pharmaflux:pharmaflux --chmod=F640 --rsync-path='sudo rsync' ~/pharmaflux-data/manifeste/has-pages.jsonl <hote>:/home/pharmaflux/pharmaflux-data/manifeste/
```

La preuve à l'octet, ensuite (sommes de contrôle, sans propriétaire ni mode) : aucune ligne de
fichier attendue.

```bash
rsync -rnci --exclude='.DS_Store' --rsync-path='sudo rsync' ~/pharmaflux-data/bronze/has/ <hote>:/home/pharmaflux/pharmaflux-data/bronze/has/
```

- Sans `--delete`, avec `--ignore-existing` en garde.
- `--chown` n'existe pas dans tous les `rsync` (commande 5 pour beko). Repli : la même copie sans
  `--chown` ni `--chmod`, puis un `chown -R` et un `chmod` par beko sur `bronze/has` et
  `has-pages.jsonl` seulement.
- C'est la seule écriture dans l'archive qui ne vienne pas de la collecte : elle se ferait une
  fois, par beko, et se consignerait dans le journal.

**Le modèle** : l'ordre dit « téléchargé sur le VPS par beko ». Deux voies, à trancher
(question 28) :
- (a) le télécharger sur le VPS avec la commande du dépôt, sous root (le filtre de sortie ne
  concerne pas root) :
  `PHARMAFLUX_MODELES=/srv/pharmaflux/modeles … pharmaflux index modele installer e5-small-int8`.
  C'est la lettre de l'ordre, mais c'est faire tourner sous root du code de ma branche ;
- (b) le copier du Mac, où il est déjà vérifié, sans accès au Hub de Hugging Face depuis le VPS :

```bash
rsync -a --chown=root:pharmaflux-chaine --chmod=D2750,F640 --rsync-path='sudo rsync' ~/pharmaflux-modeles/e5-small-int8/ <hote>:/srv/pharmaflux/modeles/e5-small-int8/
```

Dans les deux cas la preuve est la même : `index modele verifier e5-small-int8` sous
`pharmaflux-chaine`, qui recalcule les quatre sha256 du fichier
`src/pharmaflux/index/modeles/e5-small-int8.toml`. Mon avis : (b).

**Les images** : `docker compose … pull` par beko, une fois les fichiers compose installés, puis
la lecture des empreintes (`docker image inspect --format '{{.RepoDigests}}'`). Attendu pour
Qdrant : `sha256:b7b0444c…927ad`, celle du compose. Pour Redpanda, aucune empreinte n'est écrite
dans le dépôt : c'est la commande 3 pour beko. Je propose de l'**épingler dans
`docker-compose.yml`**, comme Qdrant : le fichier change, pas son comportement, et la CI
vérifierait alors à chaque passage l'image amd64 qui tourne sur le VPS.

### Questions

10. `chaine remplir` et son unité à part : d'accord, ou le remplissage reste une suite de commandes
    que beko et moi lançons une par une ?
11. L'empreinte de Redpanda dans `docker-compose.yml` (mon avis), ou vérifiée seulement dans la
    procédure ?
12. Le cache des vecteurs encodé sur place (mon avis), ou copié du Mac pour gagner une à deux
    heures ?
28. Le modèle : téléchargé sur le VPS par beko, comme l'écrit l'ordre, ou copié du Mac (mon avis) ?

---

## E. Le bus en service

### Constat

- Le mode `dev-container` et le bloc d'amorçage posent `write_caching_default: true` : l'accusé de
  réception part avant l'écriture durable. Ces propriétés ne sont lues qu'au premier démarrage.
- **Rétention infinie**, sans compactage, posée à la création des topics : douze topics, 34
  partitions, plus `_schemas`. Les schémas vivent dans le même volume.
- **Aucun groupe de consommateurs** : les positions du silver sont dans Iceberg.
- `publier` ne compare jamais son état au contenu du bus. Bus vidé et état intact : « rien à
  publier », code 0. Ce qui le détecte : `silver consommer` (position au-delà de la fin : code 2)
  et `verifier-bus`.
- Rebâtir le bus est « une opération normale et documentée » (ADR 0007) : volume effacé,
  `publication.json` effacé, schémas, publication complète : 30 s sur le Mac.
- **La taille du volume Redpanda n'a jamais été relevée.** Les fichiers d'événements pèsent
  173 Mo pour l'état initial ; le producteur compresse en zstd.
- Le code n'utilise ni le proxy HTTP (18082) ni le port d'administration (19644).

### Avis

- **Mon avis : garder `dev-container`.** Le bus se reconstruit depuis les fichiers d'événements, qui
  restent la référence. Changer de mode obligerait à réécrire `command` et l'amorçage dans
  `vps.yml` : la CI ne testerait plus ce qui tourne.
- **Le vrai risque** n'est pas de perdre le bus, c'est de perdre **en silence** une queue de
  messages accusés, après une coupure brutale ou un dépassement mémoire, alors que
  `publication.json` dit « publié ». Deux parades :
  - `verifier-bus --racine` entre dans les vérifications périodiques de la chaîne ;
  - `stop_grace_period` assez long dans `vps.yml` pour qu'un arrêt propre vide le cache.
- **Rebâtir resterait un geste**, écrit dans la procédure : beko efface le volume (root), la
  chaîne efface son état de publication et republie. Rien d'automatique : un bus perdu doit se
  voir. La même règle vaut après toute mort de Redpanda (mémoire, redémarrage de Docker) :
  `verifier-bus` d'abord.
- **La rétention** : infinie, conservée. Le bus est petit, et un topic qui oublierait ne pourrait
  plus servir à rebâtir le silver.
- **La console** : non installée. Elle coûterait 100 à 150 Mo et son port n'est pas dans le filtre.
- Les journaux des conteneurs ne se lisent qu'avec Docker : la dernière erreur de Redpanda ou de
  Qdrant reste une lecture de beko.

**Le disque dans un an**, poste par poste. Seules les trois premières lignes sont mesurées ; le
reste est un ordre de grandeur, à remplacer par les relevés du palier 1.

| Poste | Aujourd'hui | Dans un an | D'où vient le chiffre |
|---|---|---|---|
| Archive BDPM | 29 Mo en trois semaines | 0,5 Go | 1,4 Mo par jour, mesuré sur le VPS |
| Pages d'avis | 13 Mo | 13 Mo | pas de collecte périodique |
| Fichiers d'événements | 173 Mo (état initial, Mac) | 0,3 à 0,5 Go | les changements sont de quelques lignes par nuit ; le lot du mardi n'est pas mesuré |
| Volume du bus | jamais relevé | moins de 0,5 Go | les mêmes messages, compressés ; à relever par beko |
| Silver | 21 Mo (Mac, mission 05) | 0,5 à 2 Go | chaque fermeture réécrit un fichier de 1 à 3 Mo, jamais supprimé ; ni compactage ni expiration |
| Travail de l'index, cache des vecteurs | 222 Mo (Mac) | 0,3 à 0,5 Go | le cache ne grossit que des textes nouveaux |
| Volume de Qdrant | jamais relevé | moins de 1 Go | deux collections pendant une construction ; à relever par beko |
| Code, deux versions avec leur environnement | 0 | 1 Go | l'environnement du Mac pèse 487 Mo avec les outils de développement |
| Python, modèle | 0 | 0,25 Go | 100 Mo et 134 Mo |
| Images | 0 | 0,5 Go | 85 et 298 Mo sur le Mac |
| Journaux (conteneurs plafonnés, espace `pharmaflux`) | 0 | 0,3 Go | 200 Mo de plafond pour le journal, posé par beko |
| **Total** | — | **4 à 7 Go**, sur 28 libres | — |

Le poste à surveiller est le silver : il n'a ni compactage ni expiration, et y toucher serait
changer le silver, hors périmètre. `silver verifier` affiche déjà le nombre de fichiers et
d'instantanés par table.

### Questions

13. `verifier-bus` parmi les vérifications périodiques, alors que l'ordre ne nomme que
    `silver verifier` et `index verifier` ?
14. Les valeurs de développement `storage_min_free_bytes` (10 Mo) et `log_segment_size_min` (1)
    restent-elles ? Les changer demande un bloc d'amorçage propre au VPS. Mon avis : les garder.

---

## F. Le durcissement

### Constat

- L'unité de collecte, score 1,3, tient avec `MemoryDenyWriteExecute`, `SystemCallFilter` sans
  `@privileged` ni `@resources` (refus en `EPERM`), `ProtectProc=invisible`, `ProcSubset=pid`,
  `ProtectHome=tmpfs` et trois chemins liés.
- **DuckDB, PyArrow, PyIceberg, onnxruntime et librdkafka n'ont jamais tourné sous ces
  directives**, ni sous un plafond de cgroup.
- Le code ne règle aucun nombre de fils : onnxruntime, DuckDB et Arrow comptent les cœurs
  eux-mêmes. `ProcSubset=pid` cache `/proc/cpuinfo` et `/proc/meminfo`.
- `@resources` contient `sched_setaffinity`, `setpriority` et `mbind`, qu'onnxruntime et
  librdkafka peuvent appeler.
- La CI n'a aucun contrôle des unités, ni de `docker compose config`, et `shellcheck` n'y couvre
  que `infra/planification/*.sh`. `ubuntu-latest` n'est pas épinglé.
- `systemd-analyze` est présent sur le VPS (259) et mon compte peut le lancer.

### Avis

**Ce qui se garde**, tel quel : `NoNewPrivileges`, `PrivateTmp`, `PrivateDevices`,
`ProtectSystem=strict`, `ProtectHome=tmpfs`, les `ProtectKernel*`, `ProtectClock`,
`ProtectHostname`, `ProtectControlGroups`, `RestrictSUIDSGID`, `RestrictRealtime`,
`RestrictNamespaces`, `LockPersonality`, les capacités vides, `SystemCallArchitectures=native`,
`RemoveIPC`, `UMask=0027`, `Nice=10`, `IOSchedulingClass=idle`.

**Ce qui change**
- `User=pharmaflux-chaine`, `LogNamespace=pharmaflux`.
- L'archive en **lecture seule** (`BindReadOnlyPaths=`), le code et le modèle aussi ; une seule
  écriture, `ReadWritePaths=/srv/pharmaflux/derive`.
- `MemoryMax=512M`, `MemorySwapMax=0`, `OOMPolicy=continue` (§0 B), `OOMScoreAdjust=` positif
  (voir M).
- `CPUQuota=100%` (un cœur sur deux) pour le passage horaire, plutôt que 50 % ; un quota plus
  large (150 à 200 %) pour la seule unité de remplissage, Alamel étant arrêté. onnxruntime ouvre
  deux fils parce qu'il voit deux cœurs : sous un quota d'un seul, ils se gênent (question 17).
- `TimeoutStartSec=50min` pour un passage ; plusieurs heures pour le remplissage.
- Le réseau : `IPAddressDeny=any` et `IPAddressAllow=127.0.0.1`,
  `RestrictAddressFamilies=AF_INET AF_UNIX`. Il doublerait le filtre `nftables` de beko, dans
  l'unité elle-même.

**L'unité des conteneurs** tourne en root et lance le client `docker`, qui parle au démon par son
socket : presque rien du modèle ne s'y applique sans la casser, et le démon reste hors de l'unité
de toute façon. Je propose le peu qui tient (`ProtectHome=yes`, `PrivateTmp`,
`ProtectKernel*`, `NoNewPrivileges`, `RestrictAddressFamilies=AF_UNIX`, aucun `Environment`),
sans viser de score : il serait élevé, et trompeur. Sa vraie garde est ailleurs : des fichiers
compose à root, contrôlés par l'IeC, et les tests statiques de la liste de contrôle. Les minuteurs
n'exécutent rien : rien à durcir.

**Ce qui doit se mesurer avant de se décider**, dans cet ordre de soupçon :
1. `MemoryDenyWriteExecute` avec onnxruntime ;
2. `~@resources` (un refus en `EPERM` ne tue pas, mais peut ralentir ou se taire) ;
3. `ProcSubset=pid` (comptage des cœurs et de la mémoire) ;
4. `IPAddressAllow=127.0.0.1` si Docker réécrit la destination vers l'adresse du conteneur. Avec
   le relais en espace utilisateur (le défaut), la connexion reste sur la boucle locale et la
   règle suffit. S'il est coupé, il faudrait figer le sous-réseau du projet dans `vps.yml` (ce
   qui sort du « scalaires seulement ») ou renoncer à `IPAddressDeny=`, le filtre de beko restant
   alors la seule barrière. La commande 6 pour beko le dit ;
5. DuckDB n'a ni `memory_limit` ni dossier de débordement : il se règle sur la mémoire de la
   machine, pas sur celle du groupe, et serait tué avant de se restreindre ;
6. si `/tmp` est un `tmpfs`, tout fichier temporaire d'une bibliothèque sous `PrivateTmp` compte
   dans le plafond de mémoire (commande 8 pour beko).

Je propose d'écrire l'unité complète, de lancer une étape réelle au palier 1, et de ne retirer une
directive que sur la ligne du journal qui la désigne. **Score visé : sous 3**, comme la collecte ;
je m'attends à 1,5 à 2.

**La vérification sans VPS**, en trois niveaux :
1. **des tests `pytest` statiques**, sur le Mac comme en CI : ils lisent les unités et `vps.yml`
   et appliquent la liste de contrôle de l'IeC (compte, pas de `+` ni de `!`, pas de `Conflicts=`,
   espace de journal, volumes nommés, ports locaux, aucune clé interdite dans `vps.yml`) ;
2. **`systemd-analyze verify` et `security --offline`** dans la tâche `verifier` de la CI,
   précédés de `systemctl --version`. Cinq limites que je ne veux pas cacher : le binaire
   d'`ExecStart=` n'existe pas sur la machine de la CI (il faut une racine factice, `--root=`,
   avec l'unité de collecte et son complément dans le même arbre) ; je ne connais pas la version
   de systemd de cette machine aujourd'hui ; une directive inconnue d'une version plus ancienne
   n'est qu'un avertissement ; la note n'est pas celle du VPS ; et sans `--threshold=`, la
   commande sort en 0 quelle que soit la note ;
3. **la vraie vérification sur systemd 259**, par `ssh pharmaflux-vps 'systemd-analyze verify …'`
   sur le fichier déposé, que je cite dans le rapport, puis le score sur l'unité installée, relevé
   par beko.

### Questions

15. Une étape systemd dans la tâche `verifier`, `docker compose … config` des deux combinaisons,
    et `shellcheck` élargi à `infra/vps/*.sh` : accord pour toucher `ci.yml` ?
16. `CPUQuota=100%` pour le passage horaire et 150 à 200 % pour le remplissage : d'accord, ou 50 %
    comme la collecte ?
17. `intra_op_num_threads` d'onnxruntime n'est pas réglé. Le fixer d'après le quota est-il un
    « changement du calcul » ? Mon avis : ne pas y toucher ; `index verifier` tolère un cosinus
    de 0,99, mais le cache fige les vecteurs.
29. Poser `memory_limit` et un dossier de débordement à DuckDB, pour qu'il se restreigne avant
    d'être tué : est-ce un « changement du calcul » ? Mon avis : mesurer d'abord, ne rien poser.
30. « Durcies » s'applique-t-il à l'unité des conteneurs au-delà de ce que je propose ?

---

## G. Les mises à jour

### Constat

- La procédure actuelle (étape 7) : `git pull` et `uv sync` **en place**, « entre `:20` et
  `:10` », sans verrou, sans arrêt du minuteur.
- La chaîne se dépose par `git archive`, donc **sans `.git`** : la version du code retombe à
  `0.1.0`, sans commit. Rien ne dit quel code tourne.
- Les imports de la CLI sont paresseux : remplacer le code sous un passage en cours mélangerait
  deux versions.
- **Ce que le code refuse déjà** quand un format change : `evenements --reprendre` (version de
  contrat, code 2), `silver consommer` (contrat, origine), `index mettre-a-jour` (format,
  extracteur des pages, modèle) et `index etat --complet` (format, extracteur, pages d'avis
  absentes, index réduit ; pas le modèle).
- **Ce qu'il ne voit pas** : le silver n'a aucun numéro de format. Un changement de ses colonnes
  ou de sa façon d'appliquer, à contrat égal, passerait.

### Avis

**Déployer** : je propose une version par dossier, une bascule par lien.
1. `git archive --prefix=versions/<commit>/ <commit> | ssh pharmaflux-vps 'tar -x -C
   /srv/pharmaflux/code'` : `tar` crée le dossier de la version. Le commit s'écrit tout seul dans
   un fichier `VERSION` suivi par git et marqué `export-subst` (`$Format:%H$`) : rien à écrire à
   la main, et la chaîne sait quel code tourne ;
2. `uv sync --frozen --no-dev --no-editable --compile-bytecode` dans ce dossier : le code est en
   lecture seule pour la chaîne, donc le bytecode, projet compris, se compile au dépôt ;
3. bascule du lien `courante`, **sous le verrou de la chaîne** (ou, si mon compte ne peut pas le
   prendre, unité inactive et hors de la minute `:17`). Le passage suivant prend la nouvelle
   version, le passage en cours finit sur celle où il a commencé : la commande résout son propre
   chemin au départ ;
4. un passage manuel, lu dans `chaine etat` ;
5. les deux dernières versions restent ; les plus anciennes s'effacent.

**Les droits, à prouver au premier dépôt** : `chmod` m'est refusé à distance, tout repose sur
l'`umask 0027` et le bit `setgid` du dossier. Deux pièges :
- `uv` installe par liens physiques depuis son cache quand il est sur le même disque : les
  fichiers garderaient alors le groupe de mon compte, illisible pour la chaîne. Je poserais
  `UV_LINK_MODE=copy` ;
- `tar` peut ôter le `setgid` des dossiers qu'il crée. Si c'est le cas, je proposerais à l'IeC
  une ACL par défaut posée par beko sur `/srv/pharmaflux/code`.
La vérification : aucun fichier de la version ni du Python hors du groupe `pharmaflux-chaine`
(`find`), puis `pharmaflux --version` sous l'unité.

Revenir en arrière, c'est rebasculer le lien. Un fichier que root lit (unité, compose) ne suit
jamais ce chemin : branche, contrôle de l'IeC, beko.

**L'étape 7 de la collecte** reste à beko, telle quelle (`git pull`, `uv sync`, entre deux
passages). Après la fusion, l'ordre serait : la collecte d'abord, un passage manuel, puis le code
de la chaîne. Les deux codes n'ont pas à être au même commit : la chaîne ne lit que l'archive.

**Dire quand il faut reconstruire** : la chaîne écrit un témoin, `derive/chaine/formats.json`
(commit, format de l'index, extracteur des pages, modèle, versions de contrat). Au départ de
chaque passage, elle le compare à ce que porte le code :
- tout concorde : elle passe ;
- un format a changé : elle refuse (2) avant toute écriture, et nomme ce qu'il faut rebâtir
  (« index : `chaine remplir --index` », « silver et index », « tout ») ;
- seul le commit a changé : elle passe, et `chaine etat` montre « dérivé bâti par `abc`, code
  courant `def` ».

**Après la fusion** : la collecte passe de `67d9d3c` à `main`, son premier changement de code en
trois semaines (voir M). Mon compte étant clos, quelqu'un d'autre dépose le code de la chaîne :
c'est la question 19.

### Questions

18. Le silver n'a pas de numéro de format. Faut-il en ajouter un dans le témoin de la chaîne (hors
    du silver, donc sans toucher au calcul), que le codeur d'une mission future devra penser à
    incrémenter ? Mon avis : oui, avec un test qui échoue quand le schéma des tables change sans lui.
19. Après la clôture, le code de la chaîne se dépose-t-il par `git archive` depuis le Mac de beko,
    ou par un clone de `main` comme la collecte ? Mon avis : `git archive` par beko, le même geste
    que pendant la mission.

---

## H. L'état de la chaîne

### Constat

- `pharmaflux etat` lit le manifeste de collecte : c'est l'horloge de référence.
- Chaque étape a un état, mais **aucun ne porte d'heure**, et aucune commande ne les rapproche :
  `etat.json` (dernière archive traitée, retenue, en attente), `publication.json` (fichiers
  publiés), les positions du silver (dans les tables, affichées seulement par `consommer`),
  l'état de l'index (instant, format, fragments par section).
- La dernière erreur d'une étape n'existe que sur sa sortie d'erreur. Aucune commande d'état n'a
  de sortie JSON.
- L'IeC ne peut lancer sur le VPS que `pharmaflux etat`, `--version`, `chaine etat` et
  `index etat`, **sans option**.
- `derive` n'est ouvert à mon compte et à celui de l'IeC qu'en lecture ; or ouvrir le catalogue
  du silver (SQLite, par PyIceberg) peut vouloir y écrire.

### Avis

**Un journal des passages**, `derive/chaine/passages.jsonl`, en ajout seul, une ligne par passage :
identifiant, déclencheur, commit, début et fin, les archives nouvelles vues dans le manifeste, et
pour chaque étape son début, sa fin, sa durée (horloge monotone), son code, son résumé et la fin
de sa sortie d'erreur. À la fin, un résumé des positions du silver et de l'instant de l'index,
pour que l'état se lise sans ouvrir le catalogue. C'est de la plomberie : aucun format existant
ne change.

**`pharmaflux chaine etat`** lirait ce journal, le manifeste et les états des étapes, sans rien
lancer ni écrire. En texte, et en JSON avec `--format json` (la dernière erreur de chaque étape
y figure ; le texte ne montre que la plus récente) :

```text
chaîne : à jour ; dernier passage 14/11 18:17:26Z, 26 s, code 0 ; code 3f2a1bc, dérivé bâti par 3f2a1bc
collecte      dernière archive 20261113T001706Z (presentations)   dernier passage 18:17:26Z, code 0
evenements    traitée jusqu'à 20261113T001706Z   fin 18:17:31Z  retard 0 passage (0 min)  en attente 0, écartées 0
publier       161 fichiers, 164 318 messages     fin 18:17:32Z  retard 0 passage (0 min)  échecs 0
silver        observation 20261113T001706Z       fin 18:17:34Z  retard 0 passage (0 min)
index         instant 20261113T001706Z, format 4 fin 18:17:52Z  retard 0 passage (0 min)  77 350 fragments
vérifications silver 73/73 le 14/11 03:44Z ; index conforme le 14/11 03:52Z ; bus conforme
dernière erreur : 12/11 09:17Z, publier, code 1 (courtier injoignable) ; aucune depuis
```

(Les chiffres de cet exemple sont inventés.) Le retard se compte en passages de collecte non
traités, et en minutes. Sans option sur le VPS, la commande trouverait ses chemins dans deux
variables posées devant elle, ce que le garde-fou de l'IeC permet.

**Ce que beko lit le matin** : la première ligne. **Dans `journalctl --namespace=pharmaflux`** :
une ligne par étape (début, fin, code, résumé), et la sortie des commandes telle quelle.

**Les vérifications** : une fois par jour, vers 03:40 UTC, loin de minuit où tombent les
changements. Une unité à elles (`pharmaflux-verification.service` et son minuteur : une unité n'a
qu'une commande), même durcissement, **même verrou** que le passage, pour ne jamais se chevaucher.
Si elles débordent sur `:17`, le passage horaire trouverait le verrou tenu : je propose qu'il
attende alors quelques minutes plutôt que de sauter une heure. Plus une fois après chaque
déploiement et après le remplissage.

### Questions

20. Texte et `--format json` : d'accord ?
21. Vérifications quotidiennes à 03:40 UTC : d'accord, ou un autre rythme ?

---

## I. La fraîcheur

### Constat

- Le PRD §2.2 : « délai de traitement d'un événement, de sa détection à l'index vectoriel
  (p95) < 60 s ». Il ne fixe ni la borne de départ, ni la population. Le délai de collecte
  (≤ 60 min) est un autre indicateur.
- **Aucun événement ne porte d'heure de traitement** : « rien ne vient de l'horloge ».
  `date_observation` est l'instant du téléchargement, repris par l'horodatage Kafka et par le
  silver.
- Le manifeste donne, par archive, `debut` (avant le téléchargement) et `fin` (archive écrite).
- La première entrée d'un passage attend environ 25 s la fin du passage.
- **Ce que le manifeste du VPS montre depuis le 1er novembre** (14 jours) :
  - `bdpm.presentations` change presque chaque nuit, à 00:17 UTC (10 nuits sur 14) ;
  - `bdpm.infos_importantes` : 11 archives, dont une partie de fichiers servis vides ;
  - **un gros lot le mardi après-midi** : 03/11 à 15:17 UTC (neuf fichiers) et 10/11 à 16:17 UTC
    (sept fichiers).
  « Une à trois fois par semaine » sous-estime donc le rythme : c'est un changement par jour, et
  un lot par semaine.

### Avis

**Les bornes**
- **Départ** : `fin` de la ligne du manifeste, l'instant où le collecteur a détecté et archivé le
  changement.
- **Arrivée** : la fin de l'étape `index` du passage qui a porté l'archive, quand l'instant de
  l'index a atteint sa `date_observation`.
- **Par étape** : les durées du journal des passages. Je donne aussi le délai « depuis la fin du
  passage de collecte », qui retire l'attente des autres téléchargements.

**La population** : les archives des onze fichiers qui ont produit au moins un événement. À part,
et nommés : les snapshots écartés (fichier vide), les archives de même contenu (aucun événement),
les snapshots confirmés après attente (une heure de plus, par construction, ADR 0006).

**Combien de changements** : je propose **au moins cinq passages porteurs d'événements, dont un
lot du mardi** (l'unité de compte est le passage ; un lot de neuf fichiers compte pour un).
L'observation devrait donc chevaucher le premier mardi qui suit la mise en service, entre 15 h et
17 h UTC : le 17/11 si l'enchaînement tourne d'ici là, ce qui me paraît peu probable, sinon le
24/11. Sur cinq à dix valeurs, un p95 ne veut rien dire : je rendrais chaque délai, le médian et
le maximum, et je réserverais le mot « p95 » à vingt valeurs ou plus. **Cela change la condition
de clôture de l'ordre** (« au moins un changement réel », « 72 heures ») : c'est à l'IeC de la
réécrire, ou de la garder.

**Ce que j'attends** (estimé, rien n'est mesuré sur le VPS) : un passage à vide coûterait 20 à
60 s sur le VPS ; avec jusqu'à 25 s d'attente de la fin du passage, un changement de nuit
passerait en **45 à 90 s**. La cible de 60 s est donc déjà incertaine pour un petit changement,
et **le lot du mardi la dépasserait sans doute** : il faut réencoder les fragments des fiches
touchées, sans VNNI. Le PRD §7.2 demande la fraîcheur mesurée, pas promise : si la cible n'est
pas tenue, je le dirai avec le chiffre, et avec ce qui la ferait tenir.

### Questions

22. Les bornes et la population proposées conviennent-elles ?
23. Cinq passages porteurs d'événements dont un lot du mardi, plutôt qu'« au moins un » :
    d'accord ? Cela place la fin de l'observation au premier mardi soir qui suit la mise en
    service, et modifie la condition de clôture.

---

## J. La sauvegarde

### Constat

- `rapatrier.sh` tire du VPS vers le Mac, par `rsync -a` sans `--delete`, à la main. Le PRD §10.1
  et l'ADR 0001 disent « chaque semaine ».
- **La copie du Mac a 18 jours de retard** (27/10). 72 des 100 archives du VPS n'existent qu'en
  un exemplaire.
- Aucune vérification après copie, aucune alerte de retard, aucune troisième copie.
- Les pages d'avis ne sont aujourd'hui que sur le Mac. Leur manifeste est en ajout seul, et
  `rsync -a` écrase un fichier par sa date et sa taille.

### Avis

- **Un lancement à la main n'est pas un processus sur le Mac** : il reste compatible avec la
  décision de beko. Une copie poussée par le VPS vers un stockage externe demanderait un secret
  sur le VPS, ce que l'ordre exclut.
- **Ce qui manque, c'est de voir le retard.** Je propose que `rapatrier.sh` affiche, avant et
  après, le dernier passage de la copie et celui du VPS, et que la procédure du matin rappelle le
  geste hebdomadaire. Rien de plus dans cette mission.
- **Les pages d'avis ne reviennent pas par `rapatrier.sh`.** Tant qu'aucune collecte des avis ne
  tourne sur le VPS, le Mac reste leur original et le VPS leur copie. Une règle simple : **un seul
  écrivain par famille**, le VPS pour la BDPM, le Mac pour la HAS. Je propose donc deux exclusions
  dans `rapatrier.sh` (`bronze/has/` et `manifeste/has-pages.jsonl`), pour qu'un manifeste plus
  ancien du VPS n'écrase jamais celui du Mac après une future collecte.

### Questions

24. Les deux exclusions dans `rapatrier.sh` et l'affichage du retard : d'accord ? Le script est
    sous `infra/planification/`, que je peux écrire.

---

## K. Le Mac après la mise en service

### Constat

- Les conteneurs `pharmaflux-redpanda` et `pharmaflux-qdrant` sont déjà **arrêtés depuis six
  jours**. `alamel-dev-postgres` et `alamel-dev-minio` tournent.
- Sur le Mac : `~/pharmaflux-data` (21 Mo), `~/pharmaflux-modeles` (640 Mo, dont 506 Mo d'un
  second modèle que la chaîne n'utilise pas), `data/index` (222 Mo, dont 163 Mo de cache des
  vecteurs), `data/demo` (193 Mo), `data/assistant` (journal des dépenses, cache des réponses).

### Avis

**La procédure pour beko**, en fin de palier 3 :
1. `docker compose -p pharmaflux down` : arrête et retire les conteneurs, **garde les volumes** ;
2. vérifier : `docker ps -a` ne montre plus aucun `pharmaflux-*` ; la commande 4 pour beko ne
   trouve aucune tâche planifiée ;
3. **on garde** : `~/pharmaflux-data` (la sauvegarde), `~/pharmaflux-modeles/e5-small-int8`,
   `data/assistant` (le compte du budget), `data/index/cache-vecteurs.sqlite` (environ 24 minutes
   d'encodage) ;
4. **on peut effacer**, à la demande de beko seulement : les deux volumes (`down -v`),
   `data/demo`, le second modèle ;
5. **relancer la démo** pour une mission future : `make up`, `make demo`, `make silver`,
   `make gold`, `make index`, puis `make down`.

Aucune commande de la procédure ne nomme autre chose que le projet `pharmaflux`.

### Questions

Aucune.

---

## L. La mémoire et le temps

### Constat

**Mesuré aujourd'hui** sur le Mac (arm64, `/usr/bin/time -l`), sur la copie telle qu'elle est :
22 archives des onze fichiers (du 24/10 au 27/10) et les 722 pages d'avis.

| Étape | Cas | Durée | Résident max |
|---|---|---|---|
| `evenements` | rejeu complet, 22 archives, 164 106 événements (164 096 `creee`, 10 `supprimee`) | 9,6 s | 200 Mo |
| `evenements --reprendre` | à vide | 3,1 s | 135 Mo |
| `evenements --reprendre` | **avec changements** : 7 archives du 27/10 (1 retenue avec 7 `supprimee`, 3 retenues sans événement, 3 écartées) | 4,5 s | 167 Mo |
| `has extraire --verifier` | 722 pages, code 0 | 8,1 s | 56 Mo |

La sortie de la reprise est identique à l'octet à celle du rejeu complet. Les fichiers
d'événements pèsent 173 Mo. Le changement mesuré est un changement de nuit (sept événements),
**pas un lot du mardi** : aucun n'est dans la copie.

**La grille demandée**, étape par étape. « m » : mesuré aujourd'hui ; « mNN » : repris du rapport
de la mission NN (Mac, jeu de démo, soit la même période) ; « — » : jamais mesuré, à faire au
palier 1.

| Étape | À vide | Avec un changement | Premier remplissage | Résident max |
|---|---|---|---|---|
| `evenements --reprendre` | 3,1 s (m) | 4,5 s (m) | 9,6 s (m) | 135 / 167 / 200 Mo (m) |
| `schemas enregistrer` | — | sans objet | — | — |
| `publier --reprendre` | 0,1 à 0,4 s (m03) | — | 29,8 s (m03) | 59 Mo (m03) |
| `silver consommer` | 0,3 s (m05) | — | 12,9 s (m05) | 141 Mo à vide ; 357 Mo (m05) |
| `index mettre-a-jour` | 2,5 s, sans les avis (m07) | — | sans objet | 422 Mo (m07) |
| `index construire` | sans objet | sans objet | 18 min, fiches ; 6 min, avis ; 37 à 46 s depuis le cache (m07, m09) | 415 à 493 Mo ; 624 Mo une fois (m07) |
| `has extraire --verifier` | 8,1 s (m) | sans objet | 8,1 s (m) | 56 Mo (m) |
| `silver verifier` | 10,3 à 11,4 s (m05) | — | — | 310 à 341 Mo (m05) |
| `index verifier` | 28 à 55 s (m07, m09) | — | — | 444 à **502 Mo** (m09) |
| `verifier-bus --racine` | 11 à 12 s (m03) | — | — | 219 à 230 Mo (m03) |
| Conteneurs | au repos : Redpanda 201 Mo, Qdrant 99 Mo (m07) | — | — | — |

### Ce qui n'est pas mesuré, et pourquoi

| Trou | Raison | Quand |
|---|---|---|
| Toute l'archive (73 archives) | la copie du Mac s'arrête au 27/10 | après la commande 1 de beko |
| `publier`, `silver`, `index` sur l'archive réelle | les volumes portent la démo ; `down -v` attend beko | palier 1 |
| `publier`, `silver consommer` et `index mettre-a-jour` **avec un changement** ; `schemas enregistrer` | jamais mesurés, dans aucune mission | palier 1 |
| Un lot du mardi (sept à neuf fichiers) | aucun dans la copie du Mac | après la commande 1 de beko |
| `index mettre-a-jour` à vide **avec les avis** | jamais mesuré | palier 1 |
| Les conteneurs pendant une publication et une construction | `docker stats` m'est refusé | beko, ou `MemoryCurrent` de leur groupe sur le VPS |
| Tout, sur amd64 et sous cgroup | aucune étape n'y a tourné | palier 1, sur le VPS |

### Avis

- Le résident de `evenements` (200 Mo) dépasse les 118 à 185 Mo des rapports : même archive, code
  d'aujourd'hui. Il reste loin de 512 Mo, mais je le remesure au palier 1.
- Ce qui grandit avec le temps, à suivre à un an : le manifeste relu en entier par `evenements`,
  le sha256 de tous les fichiers publiés recalculé par `publier`, `silver verifier` qui relit
  chaque archive. Aucun n'est un risque à l'horizon de la mission.

### Questions

25. Les mesures complètes au palier 1, sur le Mac puis sur le VPS, plutôt qu'au §0 : d'accord,
    compte tenu des deux blocages (la copie du 27/10, et l'effacement des volumes de la démo, qui
    attend la réponse de beko) ?

---

## M. Autre

**Ce que l'ordre n'a pas vu**

1. **La collecte tourne le code de la mission 01.** Le passage sur `main` après la fusion sera son
   premier changement en trois semaines, et `uv sync --no-dev` installera dans son environnement
   PyArrow, DuckDB, onnxruntime et le reste (plusieurs centaines de Mo) dont elle n'a pas besoin.
   Un passage manuel et un relevé du score s'imposeraient ce jour-là, à écrire dans la procédure.
2. **`docker system prune`, `container prune` et `volume prune` sont interdits sur le VPS** : les
   conteneurs d'Alamel y sont *arrêtés*, donc exactement ce qu'un nettoyage efface. La procédure
   n'emploie que `docker compose -p pharmaflux …`, et l'écrit en toutes lettres.
3. **Qui meurt en premier quand la mémoire manque.** Si Alamel redémarre pour une maintenance
   pendant une construction d'index, le noyau choisit sa victime dans toute la machine. Je
   propose un `OOMScoreAdjust=` positif et fort sur les unités de la chaîne, qui reprennent sans
   perte, et **rien sur Redpanda** : le tuer, c'est le risque du §0 E (messages accusés non
   écrits). Ce réglage ne joue que pour un manque global ; un dépassement de plafond tue dans son
   propre groupe.
   `MemorySwapMax=0` et `memswap_limit` gardent les pages de Pharmaflux hors de l'échange. Ils
   n'empêchent pas Pharmaflux, sous pression, d'y pousser celles d'Alamel : ce qui protège
   Alamel, c'est une somme de plafonds qui tienne à côté de lui (§0 B).
4. **Le processeur pendant une maintenance d'Alamel** : deux cœurs, un quota de 100 % pour la
   chaîne et aucun pour les conteneurs. Un `CPUWeight=` bas sur les unités et `cpus` dans
   `vps.yml` laisseraient la priorité à Alamel.
5. **Un redémarrage du démon Docker** (par beko, pour Alamel ou une mise à jour) arrête aussi le
   bus et Qdrant si `live-restore` est coupé (commande 6). Avec `write_caching`, la suite serait
   `verifier-bus`.
6. **Le premier remplissage chevaucherait des passages de collecte** (sans doute plus d'une
   heure). La collecte est légère (25 s, 45 Mo) et la chaîne horaire trouverait le verrou tenu :
   rien à faire, mais c'est compté dans les plafonds du §0 B.
7. **Les collections orphelines de Qdrant** : une construction coupée en laisse une, que seule une
   construction au même instant efface. Or le silver avance. Les compter dans `chaine etat` ne
   touche à rien ; les purger, c'est toucher à l'index (question 31).
8. **Les écritures du dérivé n'ont pas de `fsync`** (`etat.json`, `publication.json`, les fichiers
   d'événements). Après une coupure de courant, un fichier peut être dit traité et se trouver
   tronqué. Le dérivé se reconstruit : je n'y touche pas, et je m'appuie sur les vérifications
   quotidiennes.
9. **Les journaux des conteneurs** grossissent sans limite avec le pilote par défaut : `vps.yml`
   les plafonnerait.
10. **Aucun nom d'unité nouvelle ne contiendrait `pharmaflux-collecte`** : le garde-fou m'en
   interdirait le pilotage.
11. **Le report de la mission 03** (refus explicite, dans `publier`, d'un fichier hors d'ordre),
   promis pour « la mission du VPS », n'est pas dans l'ordre. Le refus existe déjà dans le code
   (code 2) : je ne vois rien à ajouter.

**Les contradictions de l'ordre**

- **Le relecteur** : « Claude Opus 5.5 » en tête, « Claude Fable 5.1 » dans la section Paliers.
- **« `silver verifier` 22/22 »** dans les vérifications locales ne vaut que pour le jeu de démo ;
  sur le VPS, c'est N/N, N étant le nombre de bilans (73 aujourd'hui).
- **« Le plafond de 512 Mo par commande (ADR 0009) »** : l'ADR parle d'un seuil d'alerte, et dit
  que le silver ne tourne pas sur le VPS. L'ADR 0014 aurait à le corriger, avec une ligne « complété
  par » dans l'ADR 0009 comme dans l'ADR 0001.
- **`infra/planification/README.md`** dit « le codeur ne touche pas au VPS » et installe les
  unités depuis le clone. Le README de la mission suivrait la procédure de l'IeC ; je propose une
  ligne de renvoi dans l'ancien.
- **« Le jeu de démo et la CI ne changent pas »** contre la décision 3 (« vérifiées dans la CI si
  c'est possible ») : je lis « la CI ne change pas de comportement pour l'existant ».

### Questions

26. Le relecteur est-il Claude Opus 5.5 ou Claude Fable 5.1 ?
27. `OOMScoreAdjust=` positif sur les unités de la chaîne, rien sur Redpanda ; `CPUWeight=` bas et
    `cpus` pour laisser la priorité à Alamel : d'accord ?
31. Compter les collections orphelines dans `chaine etat` (mon avis), les purger, ou les laisser ?
    Et une ligne de renvoi dans `infra/planification/README.md` vers le README de la mission ?

---

## Propositions d'évolution (chemins réservés, à l'IeC)

- **Garde-fou** : `/usr/bin/time -l make <cible>` échapperait à la règle `make` (lu, non essayé) ;
  `launchctl list` et `docker volume ls` sont refusés alors qu'ils ne font que lire ; d'après la
  lecture du crochet (non essayé), un mot comme `docker` dans un `grep` distant le serait aussi.
- **`infra/agents/vps/README.md`** : dire où vont le Python et le cache d'`uv` du codeur
  (`UV_PYTHON_INSTALL_DIR`), et préciser la règle de la question 2.
- **Ordre de mission** : les deux noms du relecteur ; « 22/22 » ; le rythme des changements.
- **PRD §2.2** : fixer les bornes et la population du délai de traitement, une fois mesuré.

## Récapitulatif des questions

| # | Point | Question | Mon avis |
|---|---|---|---|
| 1 | A | Qui tient `127.0.0.1:39141` ? | — |
| 2 | B | La règle sur `Environment` et `WorkingDirectory` vaut-elle pour une unité non root ? | pas de `WorkingDirectory=`, chemins en arguments |
| 3 | B | Les 2 Go : somme des plafonds (2 048 Mo, 2 304 avec la collecte) ou résident mesuré ? | résident mesuré |
| 4 | B | `index verifier` (502 Mo) et `index construire` sous 512 | mesurer, puis le correctif reporté ; `OOMPolicy=continue` |
| 5 | B | Quel Python pour la chaîne ? | le sien, sous `code/python` |
| 6 | C | Complément `OnSuccess=` et `OnFailure=` de la collecte ? | oui ; repli `.path` |
| 7 | C | Les règles d'arrêt | continuer après `evenements` 1 et `publier` 3 |
| 8 | C | Sans index, en service | refuser et nommer le geste |
| 9 | C | Verrou tenu | code 0 |
| 10 | D | `chaine remplir` et son unité | oui |
| 11 | D | Empreinte de Redpanda | dans `docker-compose.yml` |
| 12 | D | Cache des vecteurs | encodé sur place |
| 13 | E | `verifier-bus` périodique | oui |
| 14 | E | Valeurs de développement du bus | les garder |
| 15 | F | Toucher `ci.yml` (systemd, compose, shellcheck) | oui |
| 16 | F | `CPUQuota` | 100 % par passage, 150 à 200 % au remplissage |
| 17 | F | `intra_op_num_threads` | ne pas y toucher |
| 18 | G | Un numéro de format du silver dans le témoin | oui, avec un test |
| 19 | G | Dépôt du code après la clôture | `git archive` par beko |
| 20 | H | Texte et JSON | oui |
| 21 | H | Vérifications à 03:40 UTC, chaque jour | oui |
| 22 | I | Bornes et population du délai | `fin` du manifeste → fin de l'étape `index` |
| 23 | I | Cinq passages porteurs d'événements dont un lot du mardi (change la clôture) | oui |
| 24 | J | Exclusions et retard dans `rapatrier.sh` | oui |
| 25 | L | Mesures complètes au palier 1 | oui |
| 26 | M | Le relecteur | — |
| 27 | M | `OOMScoreAdjust=` sur la chaîne seule ; priorité du processeur à Alamel | oui |
| 28 | D | Le modèle : téléchargé sur le VPS ou copié du Mac | copié du Mac |
| 29 | F | `memory_limit` de DuckDB | mesurer d'abord |
| 30 | F | Durcissement de l'unité des conteneurs | le peu qui tient, sans score |
| 31 | M | Collections orphelines ; renvoi dans l'ancien README | les compter ; oui |

À part, pour beko : l'accord pour effacer les volumes de la démo sur le Mac (commande 2).
