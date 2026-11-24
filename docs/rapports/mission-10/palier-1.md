# Mission 10 — palier 1 : les services et le premier remplissage

## Synthèse

**Fait** : `infra/vps/` (`vps.yml`, l'unité des conteneurs, l'unité de remplissage, la procédure
des étapes 0 à 8 avec la désinstallation), `pharmaflux chaine remplir` (verrou, étapes en
sous-processus, sondes, journal des passages), `VERSION` rempli par `git archive`, l'empreinte
de Redpanda, les tests de la liste de contrôle de l'IeC, trois étapes de CI, la ligne de renvoi.
**Vérifié sur le VPS** (systemd 259, mon compte) : `systemd-analyze verify` sans remarque, hors
le binaire pas encore déposé ; score hors ligne **1,1** pour le remplissage (collecte : 1,3).
**Vérifications locales** (commit testé : celui de ce palier, arbre propre) : vertes, sans
service ; 977 tests passent, 14 d'intégration sautés. **Non vérifié** : `chaine remplir` n'a
jamais tourné contre un bus ; c'est le rôle de la CI de la PR en brouillon.
**Écarts** : quatre, déclarés (pas de `Wants=` vers les conteneurs ; verrou tenu, code 2 ;
`systemd-analyze` hors de la CI ; le témoin des formats au palier 2).
**Questions pour l'IeC** : deux (le délai de six heures ; la CI qui démarre `vps.yml`).
**Propositions** : une (garde-fou, lecture de la mémoire des conteneurs).
Plus de 200 lignes : les sorties de beko et la relecture adverse y sont consignées.
Ensuite : contrôle de l'IeC, installation par beko ; puis je dépose le code, je lance le
remplissage et je cite ses mesures dans un commit à part.

## Ce qui est livré

| fichier | rôle |
|---|---|
| `infra/vps/vps.yml` | ce qui s'ajoute à `docker-compose.yml` sur le VPS : `restart: unless-stopped`, `memswap_limit` égal à `mem_limit`, `stop_grace_period` (1 min pour Redpanda), journaux plafonnés à 2 × 10 Mo. Ni image, ni commande, ni port, ni volume, ni `cpus` |
| `infra/vps/pharmaflux-conteneurs.service` | `docker compose -p pharmaflux` avec les deux fichiers de `/etc/pharmaflux/compose/` : `up -d --wait --pull never` au démarrage, `stop` à l'arrêt ; `After=` et `Wants=docker.service` |
| `infra/vps/pharmaflux-remplissage.service` | `chaine remplir` sous `pharmaflux-chaine`, durcie sur le modèle de la collecte ; chemins en arguments ; archive en lecture seule |
| `infra/vps/README.md` | la procédure : étapes 0 à 8, relance, pannes, désinstallation, sécurité |
| `src/pharmaflux/chaine/` | `chemins`, `verrou`, `etapes`, `sante`, `journal`, `passage`, `remplissage` |
| `VERSION`, `.gitattributes` | le commit écrit par `git archive` (`export-subst`) |
| `tests/test_chaine.py`, `tests/test_vps.py` | 45 et 27 tests, sans service |
| `.github/workflows/ci.yml` | `docker compose config` des deux combinaisons ; `shellcheck` élargi à `infra/vps/` ; un bus neuf démarré avec `vps.yml`, puis `chaine remplir` deux fois sur le jeu |
| `docker-compose.yml` | l'empreinte de Redpanda, à côté de son étiquette |

## La commande `chaine remplir`

Onze étapes, chacune une commande existante lancée par `python -m pharmaflux …` : rien n'est
calculé dans la chaîne.

| # | étape | commande | services sondés avant |
|---|---|---|---|
| 1 | `modele` | `index modele verifier e5-small-int8` | — |
| 2 | `pages-has` | `has extraire --verifier` | — |
| 3 | `evenements` | `evenements --reprendre` | — |
| 4 | `schemas` | `schemas enregistrer` | registre |
| 5 | `publier` | `publier --reprendre` | courtier, registre |
| 6 | `verifier-bus` | `verifier-bus --racine` | courtier |
| 7 | `silver` | `silver consommer` | courtier |
| 8 | `silver-verifier` | `silver verifier` | — |
| 9 | `index` | `index construire --archive-has` | Qdrant |
| 10 | `index-verifier` | `index verifier --archive-has` | Qdrant |
| 11 | `index-etat` | `index etat --complet` | Qdrant |

- **Arrêt à la première étape qui ne rend pas 0.** Le remplissage se relance à la main : je n'ai
  pas repris ici la règle « continuer après `evenements` 1 ou `publier` 3 », qui est celle du
  passage horaire (palier 2).
- **Aucune décision sur une sortie texte** (question 7). La chaîne ne connaît d'une étape que
  son code, le signal qui l'a tuée, et la réponse des services sondés avant de la lancer
  (trois essais espacés de cinq secondes). Qdrant injoignable sort donc en 1, pas en 2.
- **Codes** : 0 tout est bâti et conforme ; 1 panne (service, étape en échec ou tuée, passage
  interrompu) ; 2 refus (chemins, verrou tenu, étape qui rend 2).
- **Le journal des passages** (`derive/chaine/passages.jsonl`, une ligne par lancement) porte,
  par étape : début, fin, durée, code, signal, résident du plus gros processus (`wait4`), pic
  du groupe systemd après l'étape (`memory.peak`), dernière ligne de sa sortie, fin de sa
  sortie d'erreur ; et pour le passage : commit, issue, étape et motif de l'arrêt, étapes non
  lancées, processus tués par le plafond (`memory.events`). C'est de là que viendront les
  mesures du remplissage.
- **SIGTERM, SIGINT ou SIGHUP** arrêtent l'étape en cours et ce qu'elle a lancé (elle est chef
  de son groupe de processus), et le passage s'écrit quand même au journal, avec l'issue
  `interrompu`. Une erreur imprévue de la chaîne laisse aussi sa ligne.
- **Une étape tuée par le plafond de mémoire est une panne**, même quand elle rend 2 :
  `index construire` rend 2 si son sous-processus meurt. La chaîne compare le compteur
  `oom_kill` du noyau avant et après l'étape, jamais sa sortie.
- **Les étapes tournent dans `derive/tmp`**, vidé au départ sous le verrou : un chemin relatif
  pris par défaut par une bibliothèque (le débordement de DuckDB, `.tmp`) tombe dans le
  dérivé, sans `WorkingDirectory=` dans l'unité.
- **`pic_groupe_mo` est cumulé** depuis le départ de l'unité : il ne dit rien d'une étape plus
  petite que celles d'avant. Pour celles-là, il reste le résident du plus gros processus.
- **Une étape reste sur la version où le passage a commencé** : l'interprète est résolu au
  départ, sans passer par le lien `courante`.

Essai sur le jeu de démo, sur le Mac, sans service (`--racine demo/archive --modele test`) :
`pages-has` code 0 en 1,8 s (60 Mo), `evenements` code 0 en 9,5 s (201 Mo), puis l'arrêt
attendu, code 1 : « arrêté à l'étape schemas (registre injoignable (…/subjects :
ConnectError)) ».

## Les unités, lues par systemd sur le VPS

J'ai copié les deux fichiers dans mon dossier personnel du VPS (`m10-verif/`, mêmes sha256
que dans la branche), sans rien installer, pour les faire lire par systemd 259. Refait sur les
fichiers de ce commit, puis le dossier a été retiré : il ne reste rien de moi sur le VPS.

| commande | résultat |
|---|---|
| `systemd-analyze verify ./pharmaflux-conteneurs.service` | aucune remarque sur l'unité |
| `systemd-analyze verify ./pharmaflux-remplissage.service` | une seule : « Command /srv/pharmaflux/code/courante/.venv/bin/pharmaflux is not executable: No such file or directory » (le code n'est pas déposé) |
| `systemd-analyze security --offline=yes ./pharmaflux-remplissage.service` | **1,1** |
| `systemd-analyze security --offline=yes ./pharmaflux-conteneurs.service` | 4,8 |
| `systemd-analyze security pharmaflux-collecte.service` (installée) | 1,3, inchangé |

Ce que le score du remplissage garde ouvert : le réseau de l'hôte (limité à `127.0.0.1` par
`IPAddressAllow`), `AF_INET` et `AF_UNIX`, les fichiers lisibles par le groupe (`UMask=0027`,
voulu). Le score des conteneurs est celui d'un client Docker lancé par root : il ne dit rien
de ce que font les conteneurs, et l'addendum n'en vise aucun.

Relevé au passage : **`/tmp` est un `tmpfs`** sur le VPS (commande 8 du §0, lue par moi). Un
fichier temporaire y compterait dans `MemoryMax` : l'unité pose
`TMPDIR=/srv/pharmaflux/derive/tmp` (demandé par l'IeC le 14/11), que la commande crée, et le
journal des passages relève la mémoire partagée du groupe (`shmem` de `memory.stat`).

## Les sorties de beko (commandes 3 et 5 à 9), transmises par l'IeC

- **L'empreinte de Redpanda** : `sha256:8b1076e0…891ce`, l'index multi-architecture de
  v26.2.6. Deux sources concordantes, relevées par l'IeC : l'API publique de Docker Hub, et
  l'identifiant de l'image locale du Mac (`docker images --no-trunc`), que j'avais lu aussi.
  Elle est dans `docker-compose.yml` ; un pull d'une image qui ne la porte pas échouerait.
- **`rsync` du Mac** : `openrsync`, protocole 29, sans `--chown`. La procédure copie par
  `rsync -rt`, puis pose propriétaire et modes sur le VPS. Je n'ai pas vérifié qu'`openrsync`
  accepte `--ignore-existing`, `-c` et `-i` : l'essai à blanc de l'étape 3 le dira.
- **Docker 29.1.3, Compose 2.40.3, pas de `daemon.json`** : le relais en espace utilisateur est
  actif, `IPAddressAllow=127.0.0.1` suffit ; la preuve sera la première étape qui joint un
  service sous l'unité. Le greffon `compose` est sous `/usr/libexec` : `ProtectHome=yes` tient.
- **`live-restore=false`** : un redémarrage du démon arrête les deux conteneurs ;
  `stop_grace_period` s'y applique, `unless-stopped` les relève, `verifier-bus` reste la parade.
- **Le filtre de sortie** compte dix paquets rejetés pour mon compte : aucune de mes
  commandes sur le VPS n'a ouvert de connexion (lectures, `systemd-analyze`), ce sont les
  essais d'isolement de beko.

## Vérifications locales

Sur le Mac, sans aucun service de Pharmaflux (aucun conteneur du projet ne tourne).

| commande | résultat |
|---|---|
| `uv run ruff check .` ; `uv run ruff format --check .` | conformes |
| `uv run mypy src` | aucune erreur, 97 fichiers |
| `uv run pytest -q` | 977 passent, 14 sautés (12 sans courtier, 2 sans Qdrant), en 5 min 55 s |
| garde réseau | `tests/conftest.py::reseau_coupe`, inchangée |
| `sh infra/git-hooks/test-crochets.sh` | conforme |
| `python3 infra/agents/test_garde_fou.py` | 29 tests, OK |
| `docker compose -p pharmaflux -f docker-compose.yml config --quiet` | code 0 |
| `docker compose -p pharmaflux -f docker-compose.yml -f infra/vps/vps.yml config --quiet` | code 0 ; la fusion ne change que les quatre réglages de `vps.yml` |
| `make -n` | sans objet : le `Makefile` ne change pas |
| `shellcheck` | sans objet : aucun `.sh` touché |
| YAML de la CI | relu par `yaml.safe_load` : 11 et 21 étapes |

**Ce qui n'est pas vérifié** : tout ce qui demande un service. `chaine remplir` contre un bus,
un registre et Qdrant ; les tests marqués `integration` et `modele` ; `make demo`, `silver`,
`gold`, `index`. C'est le rôle de la CI de la PR en brouillon ; je citerai son run.

## La relecture adverse avant le commit

Quatre sous-agents, en lecture seule, sans VPS ni service (unités, code, procédure, tests et
CI) : une quarantaine de constats, aucun bloquant. Corrigés dans ce commit, entre autres : le
commentaire de l'unité qui prêtait à `IPAddressAllow` l'isolement d'Alamel (c'est le filtre de
sortie qui le fait, et la procédure le fait vérifier avant polkit) ; `find -perm /o=rwx`, que
tout lien symbolique fait mentir ; `systemd-analyze verify` sans `sudo` à l'étape 4b ; `restart`
de l'unité des conteneurs, qui arrête aussi le conteneur sain ; les tests statiques passés de
listes d'interdits à des listes fermées (directives des unités, clés du compose, commandes
Docker de la procédure). **Laissés** : un test hors ligne de `has extraire --verifier` sur le
jeu (je l'ai lancé à la main : code 0) ; un pic de mémoire par étape (échantillonnage) ; les
exclusions de `rapatrier.sh`, au palier 3, que la procédure annonce à l'étape 3.

## Écarts, déclarés

1. **Pas de `Wants=` vers l'unité des conteneurs** (mon §0 B proposait `After=` et `Wants=`).
   Avec `Wants=`, lancer le remplissage, et demain le passage de chaque heure, relèverait des
   conteneurs que beko aurait arrêtés exprès pour laisser la mémoire à Alamel. `After=` seul
   garde l'ordre au démarrage du VPS ; la commande sonde les services et dit lequel manque.
2. **Verrou tenu : le remplissage sort en 2**, pas en 0. L'addendum (question 9) tranche
   « code 0 et une ligne » pour le passage horaire, qui ne doit pas se dire en panne quand
   une vérification déborde. Un remplissage lancé à la main qui ne fait rien doit se voir.
3. **`systemd-analyze` n'entre pas dans la CI.** Sur le runner, `verify` s'arrêterait sur le
   binaire absent, comme ici sur le VPS ; une racine factice viderait le contrôle de son
   sens, et je ne peux pas montrer sur le Mac qu'une unité cassée ferait échouer l'étape. Le
   contrôle est fait sur le VPS (ci-dessus), et sera refait sur les fichiers installés.
4. **Le témoin `formats.json`** (§0 G, question 18) vient au palier 2, avec `chaine passer` qui
   le compare. Le journal des passages porte déjà le commit du remplissage.

Deux précisions prises en codant :
- la copie du modèle et des pages d'avis n'emploie ni `--chown` ni `--chmod` de `rsync`
  (absents du `rsync` du Mac) : `rsync -rt`, puis `chown` et `chmod` explicites sur le VPS ;
- `tests/test_vps.py` lit le YAML avec PyYAML, présent dans `uv.lock` par une dépendance de
  développement (`tokenizers`), sans l'ajouter à `pyproject.toml` : le verrou ne bouge pas.

## Questions pour l'IeC

1. **Le délai de six heures.** La construction interrompue sur le Mac a consommé 3 101 s de
   processeur en 812 s d'horloge, sans finir. La mission 07 donne 24 minutes sur le Mac pour
   une construction entière, sur quatre cœurs environ. Sur le VPS (un cœur et demi de quota,
   Haswell sans VNNI), mon estimation passe de « 1 h 15 à 2 h » à **deux à cinq heures**.
   `TimeoutStartSec=6h` tient, sans grande marge. Le cache des vecteurs est écrit par lots de
   256 fragments : une construction coupée reprend, elle ne recommence pas. Je garde 6 h.
2. **La CI démarre le bus avec `vps.yml`** avant `chaine remplir` : c'est la seule façon
   d'éprouver la combinaison du VPS avant le VPS. Si l'IeC préfère que la CI ne démarre que
   `docker-compose.yml`, l'étape se réduit d'une option.

## Les mesures du Mac, à titre indicatif

Prises au §0, avant l'addendum : beko avait dit oui à l'effacement des volumes, pas à faire
tourner la chaîne sur le Mac. Arm64, sans cgroup : elles ne valident aucun plafond.
Copie de l'archive tronquée au 26/10 (trois entités publiées, 164 099 messages).

| étape | durée | résident max | note |
|---|---|---|---|
| effacement des volumes du projet (`down -v`) | — | — | fait une fois, sur le oui de beko |
| `evenements` | 9,2 s | 160 Mo | |
| `schemas enregistrer` | 0,5 s | 59 Mo | registre neuf |
| `publier` | 59,8 s | 77 Mo | voir ci-dessous |
| `silver consommer` | 16,8 s | 352 Mo | |
| `index construire` | arrêté à 13 min 32 s | 493 Mo | 3 101 s de processeur ; jamais fini |

`publier` : 59,8 s contre 29,8 s à la mission 03, pour le même nombre de messages. Le code de
publication n'a pas changé depuis la mission 05 (`git log`), et la durée est du temps de
processeur (54 s en mode utilisateur), pas de l'attente. Je ne sais pas dire si c'est la
machine, chargée ce jour-là, ou une régression : la mesure du VPS et celle de la CI
trancheront, je ne mesure plus rien sur le Mac.

## Refus du garde-fou (signalés, non contournés)

- L'écriture d'une note dans la mémoire du projet, hors du dossier du codeur : refusée,
  laissée à l'IeC.
- Un sous-agent de la relecture a voulu lire le manuel de `rsync` (`man rsync`) : refusé, non
  contourné. Les options d'`openrsync` ne sont donc pas vérifiées ; la procédure commence
  l'étape 3 par un essai à blanc (`-n`), avant toute écriture dans l'archive.
- Une commande dont un chemin passait par une variable (`rm -rf "$D"`, puis `--derive "$D"`) :
  « une commande cachée dans une variable n'est pas jugeable ». Relancée avec ses chemins en
  clair, sans `rm`, vers `data/m10/` : c'est ce que le refus demande.

## Proposition d'évolution

- **Garde-fou** : le compte du codeur ne peut pas lire la mémoire des conteneurs
  (`/sys/fs/cgroup/system.slice/docker-….scope/memory.peak`), le mot `docker` étant refusé
  derrière `ssh`. La procédure passe par beko (`docker stats`). Une lecture seule de ces
  fichiers rendrait autonome la mesure des 2 Go que l'IeC a précisée le 14/11 (`memory.current`
  moins `inactive_file`, par groupe) ; sans exception, les deux conteneurs restent à beko.
