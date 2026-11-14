# Mission 10 — La mise en service sur le VPS-1 : bus, silver, index, au fil de la collecte

**À :** Claude Fable 5.2 (codeur, session neuve, effort medium, ultracode) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v1.1 §2.2, §4 (Lots 1 à 3), §7.1, §7.2, §9, §10.1 · ADR 0001,
0007, 0009, 0010, 0011 et 0013 · `infra/planification/README.md` ·
`infra/index/README.md` · `docker-compose.yml` · `CLAUDE.md` ·
`docs/agents/processus.md`
**Statut :** ordre rédigé le 14/11/2026 — §0 rendu (`af1314c`), tranché
par l'addendum 1 (en fin d'ordre), qui change la clôture
**Branche :** `mission-10-mise-en-service-vps`, dans `pharmaflux-codeur/`
(préparée par beko avec `preparer-mission.sh`). Trois paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Tu n'as pas codé les missions précédentes dans cette session. Lis, dans
l'ordre :
1. `CLAUDE.md` et `docs/agents/processus.md` ;
2. le PRD v1.1 : §4, §7.1, §7.2, §9 et §10.1 ;
3. l'ADR 0001 (la collecte sur le VPS-1), puis les ADR 0007 (le bus), 0009
   (le silver), 0011 (l'index) et 0013 (les avis HAS) ;
4. `infra/planification/README.md` (comment la collecte a été installée)
   et `infra/index/README.md` (le modèle et l'image Qdrant) ;
5. `docs/rapports/mission-09/pr.md` et
   `docs/relectures/mission-09/controle-iec-final.md` ;
6. cet ordre.

Tes commits portent les trailers `Commis-par: codeur` et
`Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Le relecteur
sera Claude Opus 5.5, un autre modèle que toi.

**Ultracode** : tes sous-agents passent par le même garde-fou que toi et
suivent les mêmes règles. Un refus reçu par un sous-agent se signale comme
le tien. Deux sous-agents n'écrivent jamais les mêmes fichiers, et un seul
agent à la fois agit sur le VPS.

## Constat

Depuis la mission 00, le VPS-1 ne fait que collecter : un passage par heure,
sous un compte dédié, dans une unité durcie. Tout le reste (événements, bus,
silver, gold, index, assistant) n'a jamais tourné que sur le Mac, à la main,
sur le jeu de démo ou sur une copie de l'archive. Deux raisons à cela, qui
tombent aujourd'hui :

1. **Le VPS-1 était partagé** avec la pré-production d'Alamel jusqu'à
   mi-novembre. Elle reste installée, mais **ses conteneurs sont arrêtés**
   et ne redémarrent que pour une maintenance ponctuelle. Le serveur MCP
   d'essai d'Alamel est supprimé.
2. **La chaîne n'existait pas.** Elle est maintenant complète jusqu'à
   l'index, mesurée sous 512 Mo par commande.

**beko ne veut plus de processus Pharmaflux sur son Mac.** Ce que le PRD
appelle « temps réel » n'existe donc pas encore : aucun changement de la
BDPM n'arrive tout seul jusqu'à l'index.

Le VPS-1, relevé le 14/11 (en lecture, par l'IeC) : 2 cœurs, 3,8 Go de
mémoire, dont 2,8 Go disponibles avec Alamel en marche, 2 Go d'échange
presque vides, 28 Go de disque libres sur 38, Ubuntu 26.04, Docker et son
greffon `compose` installés. L'archive y pèse 29 Mo.

**Objectif** : à la fusion, trois choses sont vraies.
- **La chaîne tourne sur le VPS-1**, seule, au fil de la collecte : chaque
  passage qui archive un changement le fait passer en événements, sur le
  bus, dans le silver et dans l'index, sans geste de personne.
- **Elle se vérifie et se reprend** : après une coupure, un redémarrage du
  VPS ou une nouvelle version du code, elle repart et rattrape. Ses
  vérifications (`silver verifier`, `index verifier`) sont conformes sur
  l'archive réelle.
- **Son état se lit en une commande**, avec le délai de chaque étape. Le
  délai de traitement du PRD §2.2 (de la détection à l'index, p95 < 60 s)
  est mesuré sur de vrais changements.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Le VPS-1 porte tout ce qui tourne en continu.** Sur le Mac, il ne reste
  que le développement et les tests de la mission, dans tes sessions. À la
  clôture, aucun conteneur ni aucune tâche planifiée de Pharmaflux ne tourne
  sur le Mac : beko arrête les conteneurs du projet, et ses volumes ne
  s'effacent qu'à sa demande. La copie de l'archive (`~/pharmaflux-data`)
  reste sur le Mac, comme sauvegarde.
- **Le périmètre de la chaîne en service** : la collecte (inchangée),
  `evenements`, `publier`, `silver consommer`, puis la mise à jour de
  l'index, le gold étant calculé à la demande (ADR 0010). Les
  vérifications tournent aussi, à un rythme que tu proposes.
- **Hors de la chaîne en service** :
  - l'assistant et l'API : aucune clé sur le VPS, aucun appel à l'API
    Claude, **budget de la mission 0 $** ;
  - une collecte périodique des avis HAS : les pages déjà collectées
    passent sur le VPS par une copie, faite une fois par beko ;
  - l'observabilité du Lot 5 (traces, tableaux de bord, alertes).
- **L'archive reste la seule source.** Le bronze et les pages d'avis sont
  immuables, et la chaîne ne fait que les lire. Tout le reste (fichiers
  d'événements, bus, silver, Qdrant, cache des vecteurs) est **dérivé et
  reconstructible** depuis l'archive : rien de dérivé n'est sauvegardé.
- **Aucun port entrant.** Tous les services écoutent sur `127.0.0.1`. Rien
  n'est exposé sur Internet dans cette mission.
- **Aucun secret sur le VPS** : le dépôt est public, cloné en HTTPS, sans
  jeton, sans `.env`.
- **Aucun compte de Pharmaflux n'entre dans le groupe `docker`**, qui vaut
  un accès root. La collecte reste sous `pharmaflux`. La chaîne tourne sous
  `pharmaflux-chaine`, qui lit l'archive et parle aux services par leurs
  ports locaux, c'est tout. Les conteneurs sont démarrés par une unité
  système, que beko installe, avec le projet compose `pharmaflux` et des
  fichiers compose qui appartiennent à root.
- **La place d'Alamel est réservée.** Ses conteneurs (`alamel-app`,
  `alamel-postgres`, `alamel-minio`), ses volumes, ses fichiers et ses ports
  (3100, 9100-9101) ne sont ni lus ni touchés. Pharmaflux tient dans
  **2 Go résidents au plus**, conteneurs compris, pour qu'Alamel puisse
  redémarrer à côté le temps d'une maintenance.
- **Une seule commande de la chaîne à la fois.** Deux étapes ne tournent
  jamais en même temps, et un passage ne chevauche jamais le suivant. Le
  plafond de 512 Mo par commande (ADR 0009) devient un plafond de l'unité.
- **Les images et le modèle sont épinglés et vérifiés** : les mêmes
  versions que `docker-compose.yml` (amd64 sur le VPS) et que
  `src/pharmaflux/index/modeles/e5-small-int8.toml`. Ils sont téléchargés
  sur le VPS **par beko**, qui suit ta procédure.
- **La source de vérité de la configuration reste le dépôt.** Ce qui est
  propre au VPS (redémarrage automatique, chemins, plafonds) va dans des
  fichiers du dépôt, jamais en modification à la main sur le VPS. Le
  `docker-compose.yml` du Mac et de la CI ne change pas de comportement.
- **Qui fait quoi** (révisé le 14/11, avant le §0) :
  - **toi** : les fichiers (unités, compose, scripts, commandes), leurs
    tests et la procédure d'installation. **Sur le VPS, tu as un compte à
    toi**, par le seul alias `pharmaflux-vps` (voir plus bas) : tu y déposes
    ton code, tu lances et mesures la chaîne par les unités que polkit
    t'ouvre, et tu lis son journal ;
  - **beko** : tout ce qui demande root sur le VPS. Il crée les comptes,
    télécharge les images et le modèle, installe chaque fichier que root lit
    (unités, compose) depuis le commit que l'IeC a contrôlé, puis l'ouvre
    dans polkit ;
  - **l'IeC** : il contrôle chaque fichier que root lira avant que beko
    l'installe, et lit l'état du VPS par le même alias, en lecture seule.

## L'accès du codeur au VPS-1 (révisé le 14/11, avant le §0)

beko t'ouvre le VPS-1 par la procédure de `infra/agents/vps/README.md`.
Lis-la en entier avant ton §0. Ce qu'elle te donne, et ce qu'elle te refuse :
- **ton compte** n'a ni `sudo`, ni `docker`, ni terminal, ni renvoi de port.
  Ta clé n'ouvre que lui, et seulement par `ssh pharmaflux-vps '<commande>'` :
  le garde-fou refuse tout autre hôte (`vps1` ouvre le compte root de beko),
  toute option qui change le compte ou la clé, toute session interactive, et
  `sudo`, `su`, `docker`, `systemd-run`, `nohup`… derrière ssh ;
- **ton code** se dépose dans `/srv/pharmaflux/code`, par
  `git archive <commit> | ssh pharmaflux-vps 'tar -x -C …'`, avec son
  Python et son environnement, lisibles par le groupe `pharmaflux-chaine`.
  Il ne tourne que sous le compte **`pharmaflux-chaine`**, qui lit l'archive
  et n'écrit que dans `/srv/pharmaflux/derive`. **La collecte reste sous
  `pharmaflux`**, avec le code de `main` que beko met à jour ; tu ne la
  pilotes pas ;
- **tu pilotes** (`start`, `stop`, `restart`, `reset-failed`) les seules
  unités dont le nom est dans la liste polkit, fixée par l'IeC à chaque
  contrôle ;
- **tu lis** le journal de Pharmaflux (`journalctl --namespace=pharmaflux`),
  l'archive, le dérivé, `systemctl status` et `show`. Un filtre réseau te
  ferme les ports d'Alamel, les réseaux de Docker et Internet, sauf HTTPS
  pour `uv sync` ;
- **un seul agent à la fois sur le VPS**, toujours la session principale.
  Tes sous-agents de l'ultracode n'y vont pas ;
- **un fichier que root lira** (unité, compose) ne s'installe jamais depuis
  ton dossier du VPS : tu l'écris dans ta branche, l'IeC le contrôle au
  commit précis, beko l'installe. Ce que l'IeC y vérifie est écrit dans la
  procédure ; écris tes fichiers pour passer ce contrôle.

Ce qui reste à beko, quoi qu'il arrive : root, les images, le modèle, le
pare-feu, polkit, le redémarrage du VPS, la mise à jour de la collecte, et la
clôture du compte à la fin de la mission.
- **Aucune adresse, aucun nom d'hôte, aucun compte SSH** dans le dépôt :
  `<hote>`, comme dans `infra/planification/README.md`.
- **Rien ne change au calcul** : ni le schéma d'événement v1, ni les
  contrats, ni la normalisation, ni les topics, ni le silver, ni le gold, ni
  le format de l'index (4). Si le VPS l'imposait, c'est une question au §0,
  pas une décision prise en codant.
- **Les tests et la CI n'appellent ni le réseau, ni le VPS.** Le jeu de
  démo et la CI ne changent pas.
- **Le colima du Mac est toujours partagé avec Alamel** pendant la mission
  (`alamel-dev-postgres`, `alamel-dev-minio`) : projet `pharmaflux`
  partout, `--pull never`, `make -n` seulement. Toute commande qui efface
  un volume attend la réponse de beko.

## Sources de données pour cette mission

- **L'archive du VPS-1**, lue par la chaîne qui y tourne : le bronze
  depuis le 24/10/2026 et, après la copie par beko, les pages d'avis.
- **La copie du Mac** (`~/pharmaflux-data`, en lecture seule) : pour tes
  mesures de la chaîne sur l'archive réelle, avant l'installation.
- **Le jeu de démo**, pour les tests et la CI.
- Les sorties que beko te donne depuis le VPS.

## §0 — Points à trancher avant de coder

Réponds dans `docs/rapports/mission-10/points-a-trancher.md` : pour chaque
point, ton **constat** (mesuré quand c'est possible), ton **avis** et tes
**questions**. Rien n'est codé avant l'addendum de l'IeC. Au §0, sur le VPS,
tu ne fais que **lire**, par `ssh pharmaflux-vps`. Ce qui demande root (la
mémoire des conteneurs, `docker`, le pare-feu), tu le demandes à beko dans
une section « Commandes pour beko », en tête du §0.

**A. Le VPS tel qu'il est.** Après l'arrêt d'Alamel : la mémoire, le
disque, les versions de Docker et de `compose`, le noyau, `systemd`, le
pare-feu, les ports qui écoutent, l'installation de la collecte (commit,
`uv`, Python), et le dernier passage.

**B. La topologie.**
- Où vit chaque chose : les chemins de l'archive (inchangé), des données
  dérivées, des modèles, du cache des vecteurs, et sous quel compte.
- Comment les conteneurs démarrent et redémarrent (une unité système qui
  lance `docker compose -p pharmaflux`, ou Docker sans root pour un compte
  à part), et comment le fichier propre au VPS s'ajoute à
  `docker-compose.yml` sans en changer le comportement ailleurs.
- Les plafonds de mémoire de chaque conteneur et de chaque unité, et leur
  somme contre les 2 Go.

**C. L'enchaînement.**
- Ce qui déclenche la chaîne après un passage de collecte : l'unité de
  collecte qui en appelle une autre (`OnSuccess=`), un minuteur décalé, ou
  autre chose. Et ce qui se passe quand la collecte sort en code 1 (une
  source en erreur, les autres archivées).
- Un script ou une commande `pharmaflux` qui enchaîne les étapes : l'ordre,
  le verrou, ce qu'une étape en échec arrête, et comment le passage suivant
  reprend (chaque étape est déjà idempotente et reprend : le montrer).
- Ce qui se passe quand rien n'a changé : le coût d'un passage à vide.

**D. Le premier remplissage.**
- Le rejeu complet sur le VPS, depuis le bronze du 24/10 : les étapes, la
  durée et le résident estimés, à partir de ta mesure sur la copie du Mac.
- La copie des pages d'avis par beko : la commande (`rsync` du Mac vers le
  VPS, sans `--delete`), où elles vont, et ce que vérifie `has extraire
  --verifier` une fois sur le VPS.
- L'installation du modèle et des images, vérifiés par empreinte.

**E. Le bus en service.** Le mode `dev-container` relâche la durabilité
(pas de `fsync`). Est-ce acceptable quand le bus est reconstructible depuis
les fichiers d'événements (ADR 0007), ou faut-il un autre mode ? La
rétention, la place sur le disque dans un an, et la console (non installée,
sauf avis contraire).

**F. Le durcissement.**
- Les unités de la chaîne contre le modèle de celle de la collecte : ce qui
  se garde, ce qui doit tomber (par exemple `MemoryDenyWriteExecute` avec
  onnxruntime), et le score de `systemd-analyze security` visé.
- Le réseau d'une unité de la chaîne limité à `127.0.0.1`
  (`IPAddressAllow`, `IPAddressDeny`).
- Comment les unités sont vérifiées sans VPS : `systemd-analyze verify`
  dans la CI, qui tourne sur Ubuntu ?

**G. Les mises à jour.**
- Déployer une nouvelle version entre deux passages (l'étape 7 de la
  procédure actuelle, étendue à la chaîne).
- Ce qui doit être reconstruit quand une version change un format (index,
  silver), et comment la chaîne le dit au lieu de mélanger deux formats.

**H. L'état de la chaîne.** Une commande (`pharmaflux chaine etat` ?) qui dit,
pour chaque étape : la dernière archive traitée, l'heure, le retard sur la
collecte, la dernière erreur. Ce que beko lit chaque matin, et ce qui se lit
dans `journalctl`.

**I. La fraîcheur.** Comment se mesure le délai de traitement du PRD §2.2,
de la détection à l'index, étape par étape, sur de vrais changements. La
BDPM change une à trois fois par semaine : combien de changements faut-il
attendre pour une mesure honnête ?

**J. La sauvegarde.** L'archive est irremplaçable. Aujourd'hui, une copie
part sur le Mac par `rapatrier.sh`, lancé à la main par beko. Est-ce que ça
suffit, sans processus sur le Mac ? Les pages d'avis copiées doivent-elles
revenir dans le même sens ?

**K. Le Mac après la mise en service.** La procédure pour beko : arrêter les
conteneurs du projet, ce qu'on garde (la copie de l'archive, les modèles,
le cache des dépenses), ce qu'on peut effacer, et comment relancer la démo
sur le Mac pour une mission future.

**L. La mémoire et le temps.** Pour chaque étape, sur la copie du Mac (toute
l'archive) : le résident maximal et la durée, d'un passage à vide, d'un
passage avec un changement, et du premier remplissage.

**M. Autre.** Tout ce que cet ordre n'a pas vu, en particulier ce qui
rendrait la cohabitation avec Alamel risquée quand ses conteneurs
redémarrent pour une maintenance.

## Décisions (sous réserve du §0)

1. **La topologie** (§0 B, E) : le fichier compose propre au VPS, les
   chemins, les comptes, les plafonds.
2. **L'enchaînement** (§0 C, G) : la commande ou le script, le déclencheur,
   le verrou, la reprise, les mises à jour.
3. **Les unités** (§0 F) : la ou les unités de la chaîne, celle des
   conteneurs, durcies, vérifiées dans la CI si c'est possible.
4. **L'état et la fraîcheur** (§0 H, I) : la commande d'état, la mesure du
   délai par étape.
5. **La procédure d'installation** (§0 A, D, J, K) : un `README` pas à pas
   pour beko, dans le style de `infra/planification/README.md`, avec la
   vérification de chaque étape, la désinstallation et le retour du Mac au
   repos.
6. **Lancements par beko sur le VPS** :
   - au palier 1 : l'installation des services, puis le premier remplissage
     et ses vérifications ;
   - au palier 2 : l'enchaînement en service, un redémarrage du VPS pendant
     la période d'observation, et la lecture de l'état au fil des jours.
7. **Docs** :
   - ADR 0014, la mise en service sur le VPS-1, et la ligne « complété par »
     de l'ADR 0001 ;
   - `README.md` : la section « État » et un schéma de ce qui tourne où ;
   - `docs/CONTEXTE.md`, et `docs/journal.md` en fin de fichier.

## Paliers

1. **Les services et le premier remplissage** : décisions 1, 3 (unité des
   conteneurs) et 5.
   - Le fichier compose du VPS, les chemins, les plafonds, la procédure.
   - Tes mesures sur la copie du Mac : le rejeu complet, étape par étape.
   - Rapport, commit. **Puis beko installe**, après le contrôle de l'IeC,
     les fichiers que root lit, et les ouvre dans polkit. Tu déposes ton
     code, tu lances le premier remplissage et tu le mesures. Tu cites tout
     dans un commit à part, avant le palier 2 : durées, résidents,
     `silver verifier`, `index verifier`, `index etat`.
2. **L'enchaînement** : décisions 2, 3 et 4.
   - La commande ou le script, le déclencheur, les unités, la commande
     d'état.
   - Les tests : verrou, échec d'une étape, reprise, passage à vide, sur le
     jeu de démo et sans réseau.
   - Rapport, commit. **Puis beko met l'enchaînement en service**.
   - Une observation d'au moins **48 heures**, avec un redémarrage du VPS
     au milieu. Tu cites l'état de la chaîne au début, après le
     redémarrage et à la fin, avec chaque changement réel passé jusqu'à
     l'index et son délai par étape.
3. **Docs et retour du Mac au repos** : décisions 5 (la fin de la
   procédure) et 7.
   - L'ADR 0014 et les docs.
   - beko met le Mac au repos en suivant ta procédure, et te donne la sortie.
   - Rapport, commit.

Après le contrôle du palier 3, la suite est celle du circuit :
1. la relecture (`/relire-mission 10`, Claude Opus 5.5), jusqu'à
   « CONFORME » ;
2. `pr.md` ;
3. la **revue finale écrite de l'IeC** (`controle-iec-final.md`) ;
4. la publication et la fusion par beko ;
5. le passage du VPS sur `main`, entre deux passages.

**La mission est close** quand :
- la chaîne a tourné sur le VPS au moins 48 heures **sans intervention**,
  redémarrage compris, et chaque passage est lisible dans l'état ;
- au moins **un changement réel** de la BDPM est passé de la collecte à
  l'index sans geste de personne, avec son délai mesuré étape par étape.
  Si aucun changement n'arrive en 72 heures, l'IeC décide sur pièces ;
- `silver verifier` et `index verifier` sont conformes sur le VPS, à la
  fin de l'observation ;
- Pharmaflux reste sous 2 Go résidents sur le VPS, mesuré ;
- aucun processus ni conteneur de Pharmaflux ne tourne sur le Mac.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests | `GITHUB_ACTIONS=true uv run pytest -q -rE -rs`, services et modèle présents, **lancé seul** |
| aucune requête réseau dans les tests | la garde de session `tests/conftest.py::reseau_coupe`, citée |
| unités systemd | ce que le §0 F retient (`systemd-analyze verify` dans la CI, ou autre) |
| compose | `docker compose -f … config` des deux combinaisons (Mac, VPS), sans rien démarrer |
| simulation du `Makefile` | `make -n <cible>` pour chaque cible nouvelle ou modifiée |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck | si un `.sh` est touché |
| YAML de la CI | si `ci.yml` est touché |
| non-régression | `demo verifier` ; `silver verifier` 22/22 ; `make gold` sans bloquant ; `index verifier` conforme ; `questions verifier` v0, v1 et v2 inchangés |

## Hors périmètre

- L'assistant, l'API, l'interface, l'évaluation dans la CI, le test de
  fraîcheur par changement injecté (mission 11) ; tout appel à l'API
  Claude ; toute clé sur le VPS.
- Une collecte périodique des avis HAS ; toute requête vers la HAS, la BDPM
  ou data.gouv depuis ta session, les tests ou la CI.
- Tout port ouvert sur Internet ; tout nom de domaine ; tout certificat.
- L'observabilité du Lot 5 ; les indicateurs de dépense du Lot 4.
- Tout changement du calcul (événements, contrats, normalisation, topics,
  silver, gold, format de l'index).
- Sur le VPS, tout ce qui sort de ton compte : root, `docker`, le pare-feu,
  polkit, la collecte, le redémarrage ; toute écriture dans l'archive ; tout
  usage de `vps1`.
- **Tout ce qui touche à Alamel** : ses conteneurs, volumes, fichiers et
  ports sur le VPS-1, les conteneurs `alamel-dev-*` du colima, et les VPS
  qui appartiennent à l'association.

## Addendum 1 — le §0 tranché (14/11/2026)

Réponse au §0 du codeur (`docs/rapports/mission-10/points-a-trancher.md`,
commit `af1314c`). Les avis sont **retenus**, avec les précisions ci-dessous
et **quatre écarts** : plus rien ne tourne sur le Mac, et les vérifications
qui demandent les services passent dans la CI (L), pas de minuteur au démarrage (C),
pas d'attente quand le verrou est tenu (C), pas de `cpus` dans `vps.yml` (F). Ce qui n'est pas cité ici est
retenu tel que proposé.

**Revérifié par l'IeC** (14/11, par `pharmaflux-vps`, en lecture) :
- le manifeste compte 6 116 lignes. Les archives écrites, heure par heure :
  **chaque nuit** depuis le 28/10, vers 00:17 (une à trois), **deux lots le
  mardi** (10 archives le 03/11 à 15 h, 8 le 10/11 à 16 h), et quelques
  archives de jour (27/10, 28/10, 12/11). Le rythme du §0 I est juste ;
- la collecte : dernier passage en succès, code 0, pic de 44,6 Mo ; 3 279 Mo
  disponibles, Alamel arrêté ;
- depuis `67d9d3c`, le code de la collecte n'a changé que dans
  `src/pharmaflux/collecte/manifeste.py` (une porte d'écriture commune aux
  deux manifestes, même format de ligne), et
  `infra/planification/pharmaflux-collecte.service` n'a pas changé ;
- le garde-fou : le trou signalé (`/usr/bin/time -l make <cible>`) était
  réel. Il est fermé sur `main` avec cet addendum : `make` derrière un
  lanceur (`time`, `nice`, `timeout`, `env`, `xargs`, `uv run`…) suit la
  règle de `make` en tête, et `time -p` ne cache plus la commande. Les deux
  commandes que le §0 prévoit sur le VPS passent (l'état lu par l'IeC avec
  ses chemins en variables, la bascule de version sous le verrou) ; tests
  ajoutés.

### Ce que l'addendum change dans l'ordre

- **Les mesures qui comptent se font sur le VPS**, sous cgroup
  (`MemoryPeak` de chaque unité, durées du journal des passages). Un
  résident mesuré sur le Mac (arm64, sans cgroup) ne valide aucun plafond.
  Au palier 1, « tes mesures sur la copie du Mac » se réduisent donc à
  `evenements` (déjà fait, à refaire sur la copie rafraîchie si beko a lancé
  `rapatrier.sh`) ; le rejeu complet est mesuré **étape par étape sur le
  VPS**, par le remplissage. La commande 2 a été faite avant cet addendum :
  beko avait dit oui à l'effacement des volumes, pas à faire tourner la
  chaîne sur le Mac. Tu as effacé les volumes, mesuré une partie de la chaîne
  sur la copie du 27/10, puis arrêté. Ces mesures entrent dans le rapport du
  palier 1, **à titre indicatif** (arm64, sans cgroup), avec l'effacement et
  la construction de l'index interrompue.
- **Rien de Pharmaflux ne tourne plus sur le Mac**, jusqu'à la clôture :
  ni conteneur, ni mesure, ni construction, ni `make up`. Les volumes restent
  tels quels (le bus et le silver de la copie, un index inachevé) ; la démo
  ne se rebâtit pas sur le Mac pendant la mission. Les vérifications locales
  deviennent :
  - sur le Mac, ce qui tourne sans service : lint, types, `uv run pytest -q`
    (les tests d'intégration sautent, et le rapport cite leur nombre),
    crochets, garde-fou, `shellcheck`, `make -n`, et `docker compose config`
    des deux combinaisons, qui ne démarre rien ;
  - **dans la CI**, sur une PR en brouillon que beko ouvre dès le palier 1 et
    pousse à chaque palier : les tests avec services, `make demo`,
    `make silver`, `make gold`, `make index`, et `index verifier` avec le
    vrai modèle. Le rapport cite le run de la CI au commit du palier ;
  - **sur le VPS**, sous les unités : tout ce qui touche à l'archive réelle.

  La relecture suit la même règle : elle lit la CI et ne démarre rien sur le
  Mac.
- **La collecte passe sur `main` au début du palier 1**, par beko, entre
  deux passages (étape 7 de `infra/planification/README.md`), suivie d'un
  passage à la main et de la relecture de son score. L'observation porte
  ainsi sur le code de collecte que la fusion apportera (la mission ne le
  change pas) ; après la fusion, le passage du VPS sur `main` ne concerne
  plus que la chaîne.
- **La clôture change** : voir « La clôture », en fin d'addendum.
- **Le relecteur est Claude Opus 5.5** ; « Fable 5.1 » dans les paliers
  était une erreur, corrigée plus haut.
- **« `silver verifier` 22/22 »**, dans les vérifications locales, vaut pour
  le jeu de démo. Sur le VPS, c'est N/N, N étant le nombre de bilans.
- **« La CI ne change pas »** veut dire : le comportement de l'existant ne
  change pas. La CI peut gagner des contrôles (F).

### Les commandes pour beko

- **1 (`rapatrier.sh`) : maintenant**, et pas seulement pour les mesures :
  72 archives sur 100 n'existent qu'en un exemplaire. Puis chaque semaine.
- 2 : faite (ci-dessus). Les volumes du Mac restent tels quels.
- **Une PR en brouillon dès le palier 1**, poussée à chaque palier, pour que
  la CI fasse les vérifications qui demandent les services.
- 3, 5, 6, 7, 8 et 9 : avant le palier 1. beko colle les sorties au codeur ;
  elles fixent `vps.yml`, l'unité des conteneurs et les commandes `rsync`.
  On y ajoute, pour l'unité des conteneurs (F) :

```bash
sudo ls -l /usr/libexec/docker/cli-plugins/ /usr/lib/docker/cli-plugins/ /root/.docker/cli-plugins/
```

- 4 (`launchctl`) : à la clôture, pour le Mac au repos.

### A. Le VPS

- **Question 1** : 39141 est dans la plage des ports éphémères de Linux
  (32768 à 60999) : un port local qu'un processus prend au démarrage et qui
  change à chaque fois. Rien à réserver, rien à chercher : les ports de
  Pharmaflux sont fixes et sous cette plage.

### B. La topologie

- **Les chemins, le Python, l'unité des conteneurs** (`Type=oneshot`,
  `After=` et `Wants=docker.service`, ni `Requires=` ni `PartOf=`, `stop` à
  l'arrêt), **`vps.yml` en scalaires seulement** : retenus.
- **Question 2** : la règle vise ce que **root** lit ou lance. Une unité de
  la chaîne lance son `ExecStart=` sous `/srv/pharmaflux/code/courante/`,
  c'est son rôle ; elle n'a **ni `EnvironmentFile=`** (systemd le lit en
  root, et suivrait un lien), **ni `WorkingDirectory=`**, et passe ses
  chemins en arguments. `Environment=` ne porte que des valeurs écrites en
  clair. L'unité des conteneurs ne nomme rien sous `/srv/pharmaflux`. La
  liste de contrôle de `infra/agents/vps/README.md` est précisée en ce sens
  sur `main`.
- **Question 3 : le résident mesuré.** Les 2 Go se mesurent comme la somme,
  au pire moment de l'observation, du `MemoryCurrent` des groupes de
  Pharmaflux (les deux conteneurs, l'unité de la chaîne, la collecte), avec
  pour borne haute la somme de leurs `MemoryPeak`. Les plafonds gardent
  chaque groupe ; leur somme en service peut atteindre 2 304 Mo quand une
  étape longue croise la collecte : accepté, la tranche du codeur fermant
  avec la mission.
- **Question 4** : (a), puis (c) si la mesure échoue ; pas (b).
  `OOMPolicy=continue` et `MemorySwapMax=0` : retenus. Si (c) devient
  nécessaire, il est dans le périmètre (il ne touche pas au calcul), à
  condition qu'`index verifier` rende le même verdict sur le jeu de démo, ce
  que le rapport montre.
- **Question 5** : le sien, sous `/srv/pharmaflux/code/python`
  (`UV_PYTHON_INSTALL_DIR`), avec `UV_LINK_MODE=copy`.

### C. L'enchaînement

- **Question 6 : le complément est permis.** « La collecte (inchangée) »
  désigne son code et son fichier d'unité ; un complément qui n'ajoute que
  `OnSuccess=` et `OnFailure=` dans `[Unit]` ne change rien à ce qu'elle
  fait. Il s'installe au palier 2 seulement, après le contrôle de l'IeC.
- **Pas de minuteur au démarrage** (écart) : après un redémarrage, le
  passage de collecte suivant (ou celui que `Persistent=true` rattrape)
  relance la chaîne. Un délai d'une heure au plus, c'est rattraper ; et
  c'est une unité de moins.
- **Question 7 : retenu, à une condition.** La chaîne distingue un échec
  circonscrit (`evenements` 1 sur une archive illisible, `publier` 3) par un
  fichier que l'étape écrit (`etat.json`, les bilans, `publication.json`),
  **jamais en lisant sa sortie texte**. Un cas qu'on ne sait pas distinguer
  ainsi arrête le passage.
- **Question 8** : refuser, et nommer le geste. Retenu.
- **Question 9 : code 0 et une ligne, sans attendre** (écart avec le §0 H).
  Les vérifications finissent bien avant `:17` ; si elles débordaient, ce
  passage sauterait, et le suivant rattraperait. `chaine etat` montre l'âge
  du dernier passage complet : un verrou qui resterait tenu se verrait.
- **Le passage à vide sans court-circuit**, les étapes en sous-processus, le
  test de santé avant chaque étape : retenus. Si le passage à vide mesuré au
  palier 2 dépasse la minute sur le VPS, tu proposes le court-circuit.

### D. Le premier remplissage

- **Les étapes 1 à 8, dans cet ordre**, précédées de l'étape 0 (la collecte
  sur `main`) : retenues.
- **Question 10 : retenu.** `pharmaflux chaine remplir` et
  `pharmaflux-remplissage.service` : même durcissement, même verrou,
  `TimeoutStartSec=6h`. Elle commence par `index modele verifier` et
  `has extraire --verifier`. C'est la seule unité de la liste polkit au
  palier 1 ; l'unité des conteneurs reste à beko.
- **Question 11 : retenu.** L'empreinte de Redpanda (celle de l'index
  multi-architecture, donnée par la commande 3) entre dans
  `docker-compose.yml`, comme celle de Qdrant. Tu vérifies sur le Mac
  (`docker image inspect`) que l'image locale la porte ; sinon, beko la tire
  avant tes tests. La console ne change pas (profil, absente du VPS).
- **Question 12** : encodé sur place. Retenu.
- **Question 28 : copié du Mac** (voie b). Faire tourner du code de ta
  branche sous root est exclu. « Téléchargés sur le VPS par beko » se lit :
  apportés par beko, vérifiés par empreinte. Seul `e5-small-int8` est copié,
  sans `.DS_Store` ; la preuve est `index modele verifier` sous la chaîne,
  code 0.
- **La copie des pages d'avis** : retenue telle qu'écrite (deux sources
  nommées, `--ignore-existing`, sans `--delete`, preuve par `rsync -rnci`),
  aux droits de l'archive (`pharmaflux:pharmaflux`, 750 et 640). C'est la
  seule écriture dans l'archive qui ne vienne pas de la collecte : beko la
  fait une fois, et elle se consigne dans `docs/journal.md`.

### E. Le bus

- **`dev-container` gardé**, rétention infinie, pas de console, rebâtir
  reste un geste écrit : retenus.
- **Question 13 : oui**, `verifier-bus --racine` entre dans les
  vérifications quotidiennes.
- **Question 14 : les valeurs de développement restent.** Mais avec
  `storage_min_free_bytes` à 10 Mo, Redpanda remplirait le disque jusqu'aux
  10 derniers Mo, Alamel compris. `chaine etat` montre donc la place libre
  du disque (un `statvfs` : le dérivé et les volumes de Docker sont sur le
  même disque), et l'ADR 0014 écrit le risque.

### F. Le durcissement

- **Ce qui se garde, ce qui change, ce qui se mesure avant de se décider** :
  retenus. Une directive ne tombe que sur la ligne du journal qui la
  désigne. Score visé sous 3.
- **Question 15 : oui, `ci.yml` peut changer** : les tests statiques, `docker
  compose config` des deux combinaisons, `shellcheck` sur
  `infra/vps/*.sh`. `systemd-analyze` n'entre dans la CI **que s'il échoue
  quand il doit** : ton rapport montre une unité cassée (une fixture) qui
  fait échouer l'étape. S'il faut une racine factice qui vide le contrôle de
  son sens, tu le laisses de côté et tu le dis. Le vrai contrôle est sur le
  VPS : `systemd-analyze verify` sur le fichier déposé, puis
  `systemd-analyze security <unité>` sur l'unité installée, que ton compte
  peut lancer.
- **Question 16** : 100 % pour le passage et la vérification, 150 % pour le
  remplissage, et `CPUWeight=20` sur les trois. **Pas de `cpus` dans
  `vps.yml`** (écart avec la question 27) : Redpanda tient déjà sur un cœur
  (`--smp=1`), et Qdrant ne travaille fort que pendant une construction.
- **Questions 17 et 29** : ne pas toucher à `intra_op_num_threads` ;
  mesurer DuckDB avant de lui poser quoi que ce soit. Retenus.
- **Question 30** : le peu qui tient, sans score visé. Avant
  `ProtectHome=yes`, la commande ajoutée pour beko dit où vit le greffon
  `compose` : s'il est sous `/root`, ce sera `ProtectHome=read-only`.

### G. Les mises à jour

- **Une version par dossier, `VERSION` par `export-subst`, les deux
  dernières versions gardées** : retenus. La bascule est **atomique** (`ln
  -s` vers un nom neuf, puis `mv -T`), sous le verrou de la chaîne : `flock`
  prend un verrou sur un fichier ouvert en lecture, ton compte le peut.
- **Les droits** se prouvent au premier dépôt (`find` : aucun fichier hors
  du groupe `pharmaflux-chaine`). Si `tar` ôte le `setgid`, tu proposes
  l'ACL à l'IeC, qui la fait poser par beko.
- **Question 18 : oui**, un numéro de format du silver dans le témoin, avec
  le test qui échoue quand le schéma des tables change sans lui.
- **Question 19** : `git archive` par beko après la clôture. Le README de la
  mission a une section « Mettre à jour après la clôture ».

### H. L'état de la chaîne

- **Le journal des passages, `chaine etat` en texte et en JSON**
  (question 20) : retenus. L'IeC la lance sans option, ses chemins en deux
  variables devant la commande. Le README dit aussi la commande de beko pour
  le matin, par son compte, une fois le tien clos.
- **Question 21** : chaque jour à 03:40 UTC, plus après chaque dépôt et
  après le remplissage. Retenu.
- **Question 31** : les collections orphelines se comptent dans
  `chaine etat`, sans purge ; la ligne de renvoi dans
  `infra/planification/README.md` : oui.

### I. La fraîcheur

- **Question 22** : les bornes (de `fin` dans le manifeste à la fin de
  l'étape `index` du passage) et la population (les archives qui portent au
  moins un événement, les autres cas nommés à part) : retenues.
- **Question 23 : oui**, cinq passages porteurs d'événements dont un lot du
  mardi, avec une borne : si aucun lot n'est arrivé au deuxième mardi qui
  suit la mise en service, l'IeC décide sur pièces. Chaque délai est rendu,
  avec le médian et le maximum ; le mot « p95 » attend vingt valeurs.
- **La cible de 60 s** se mesure, elle ne se promet pas. Si elle n'est pas
  tenue, tu donnes le chiffre et ce qui la ferait tenir.
- **Pendant l'observation, la liste polkit est vide** : tu lis, tu ne lances
  rien. C'est ce qui rend « sans intervention » vérifiable.
- **Le palier 3 peut s'écrire pendant l'observation** (docs et procédure du
  Mac, rien de déposé sur le VPS). Le commit de l'observation vient quand
  ses conditions sont réunies, avant le contrôle du palier 3.

### J et K. La sauvegarde, le Mac

- **Question 24 : oui**, les deux exclusions et l'affichage du retard dans
  `rapatrier.sh`. Un seul écrivain par famille : le VPS pour la BDPM, le Mac
  pour la HAS.
- **La procédure du Mac** : retenue. À la clôture, les conteneurs du projet
  sont arrêtés ; leurs volumes restent, sauf demande de beko.

### M. Autre

- **Question 27** : `OOMScoreAdjust=500` sur les trois unités de la chaîne,
  rien sur les conteneurs. Le processeur : voir F.
- **Les nettoyages de Docker** (`system prune`, `container prune`, `volume
  prune`) sont interdits sur le VPS, et le README l'écrit : les conteneurs
  d'Alamel y sont arrêtés, donc exactement ce qu'ils effaceraient.
- **`daemon.json` ne se touche pas** : le démon est partagé avec Alamel.
  Après toute mort de Redpanda, `verifier-bus` d'abord.
- **Pas de `fsync` dans le dérivé** : accepté, les vérifications
  quotidiennes le couvrent.
- **Les journaux des conteneurs** sont plafonnés dans `vps.yml`. Retenu.
- **Le report de la mission 03** (refus d'un fichier hors d'ordre) est clos :
  le refus existe, en code 2.
- **Les refus du garde-fou** : `launchctl list` et `docker volume ls` restent
  refusés, beko les lit. Un mot comme `docker` dans un `grep` distant est un
  faux positif connu : la lecture passe dans les commandes pour beko, pas
  dans une autre écriture de la commande. « Jamais de `ssh` depuis un
  sous-agent » reste une consigne : le crochet ne voit pas la différence.

### Ce que tu fais au palier 1

Le fichier `vps.yml`, l'empreinte de Redpanda, l'unité des conteneurs,
`chaine remplir` et son unité, le verrou, la procédure (`infra/vps/README.md`,
étapes 0 à 8, avec la désinstallation), les tests statiques, et la ligne de
renvoi dans `infra/planification/README.md`. Rapport, un commit, tu
t'arrêtes. Après le contrôle de l'IeC et l'installation par beko, tu déposes
ton code, tu lances le remplissage, et tu cites ses mesures dans un commit à
part.

### La clôture

Elle remplace la liste « La mission est close quand » :
- la chaîne a tourné sur le VPS au moins 48 heures **sans intervention**,
  redémarrage compris, et chaque passage se lit dans l'état ;
- **au moins cinq passages porteurs d'événements, dont un lot du mardi**,
  sont allés de la collecte à l'index sans geste de personne, chacun avec
  son délai par étape. Sans lot du mardi au deuxième mardi qui suit la mise
  en service, l'IeC décide sur pièces ;
- `silver verifier`, `index verifier` et `verifier-bus` sont conformes sur
  le VPS à la fin de l'observation ;
- Pharmaflux reste sous 2 Go résidents sur le VPS, mesuré comme au point B ;
- aucun processus ni conteneur de Pharmaflux ne tourne sur le Mac.
