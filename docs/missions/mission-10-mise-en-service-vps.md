# Mission 10 — La mise en service sur le VPS-1 : bus, silver, index, au fil de la collecte

**À :** Claude Fable 5.2 (codeur, session neuve, effort medium, ultracode) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v1.1 §2.2, §4 (Lots 1 à 3), §7.1, §7.2, §9, §10.1 · ADR 0001,
0007, 0009, 0010, 0011 et 0013 · `infra/planification/README.md` ·
`infra/index/README.md` · `docker-compose.yml` · `CLAUDE.md` ·
`docs/agents/processus.md`
**Statut :** ordre rédigé le 14/11/2026 — **§0 ouvert**
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
1. la relecture (`/relire-mission 10`, Claude Fable 5.1), jusqu'à
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
