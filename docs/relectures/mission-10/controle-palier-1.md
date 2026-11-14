# Mission 10 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `13168f5da3bc880473242d6d6b7f8f71c3d73a0f` · **Date** : 14/11/2026
**Verdict : accepté.** Les quatre fichiers que root lira sont conformes à ce
commit, et beko peut les installer. Le dépôt du code et le remplissage
attendent deux choses : la correction des unités de mesure (ci-dessous), et
la CI verte de la PR en brouillon sur le commit déposé.

## Ce que l'IeC a relu

- **Les quatre fichiers que root lira**, en entier : `docker-compose.yml`
  (le seul changement est l'empreinte de Redpanda), `infra/vps/vps.yml`,
  `infra/vps/pharmaflux-conteneurs.service` et
  `infra/vps/pharmaflux-remplissage.service`.
- **La fusion des deux fichiers compose, lue par Docker** (`docker compose
  -p pharmaflux -f docker-compose.yml -f infra/vps/vps.yml config`, sans
  rien démarrer) :
  - deux services seulement : la console reste sous son profil ;
  - deux volumes nommés, aucun montage de l'hôte ;
  - les cinq ports liés à `127.0.0.1` ;
  - les deux images épinglées par leur empreinte ;
  - `memswap_limit` égal à `mem_limit`, `unless-stopped`, journaux de
    2 × 10 Mo ;
  - aucun `privileged`, `cap_add`, `user`, `network_mode` ni `pid`.
- **La procédure** `infra/vps/README.md`, commande par commande, pour ce que
  beko lance en root.
- **Le code de `chaine`** : le verrou, les étapes, le passage, le
  remplissage et les chemins. Les tests sont lus par leurs noms seulement :
  la CI les fait tourner.

## Les fichiers que root lira

| Fichier | Verdict | Ce qui a été vérifié |
|---|---|---|
| `docker-compose.yml` | conforme | L'empreinte de Redpanda (`8b1076e0…891ce`) est celle de l'index multi-architecture de la v26.2.6. Deux sources indépendantes la donnent : l'API de Docker Hub et l'identifiant de l'image du Mac. Rien d'autre ne change. |
| `infra/vps/vps.yml` | conforme | Il ne porte que le redémarrage, l'échange, les délais d'arrêt et les journaux. Ni image, ni commande, ni port, ni volume, ni `cpus`. |
| `pharmaflux-conteneurs.service` | conforme | `up -d --wait --pull never` au démarrage et `stop` à l'arrêt, avec les deux fichiers de `/etc/pharmaflux/compose/`. Jamais `down`, `rm` ni `-v`. Rien sous `/srv/pharmaflux`, aucun `Environment`. `After=` et `Wants=docker.service`, sans `Requires=` ni `PartOf=`. `TimeoutStartSec` (240 s) dépasse `--wait-timeout` (180 s), et `TimeoutStopSec` (120 s) dépasse les délais d'arrêt cumulés (60 + 30 s). L'unité n'entre pas dans polkit. |
| `pharmaflux-remplissage.service` | conforme | `User=pharmaflux-chaine`, et `ExecStart=` sous `code/courante`, chemins en arguments. Ni `EnvironmentFile=` ni `WorkingDirectory=`. Deux `Environment=` en clair (`PYTHONUNBUFFERED`, `TMPDIR`). L'archive en lecture seule, une seule écriture (le dérivé). Plafonds, `OOMPolicy=continue`, `OOMScoreAdjust=500`, `CPUQuota=150%`, `CPUWeight=20` comme l'addendum. Le réseau limité à `127.0.0.1`. Score hors ligne 1,1. |

**Le code de la chaîne** reprend les règles de l'addendum :
- une étape tourne dans son propre groupe de processus, arrêté avec elle ;
- la chaîne ne décide jamais d'après la sortie texte d'une étape ;
- une étape tuée pour la mémoire est reconnue par le compteur `oom_kill` du
  noyau ;
- le dérivé ne peut pas se trouver dans l'archive, ni l'archive dans le
  dérivé, liens résolus ;
- le commit se lit dans `VERSION`, à côté de l'environnement Python ;
- l'interprète est fixé au départ, si bien qu'une bascule de version ne
  coupe pas un passage en cours.

## Les écarts : acceptés

1. **Pas de `Wants=` vers l'unité des conteneurs.** Bonne raison : un
   remplissage ne doit pas relever des conteneurs que beko a arrêtés exprès.
2. **Un verrou tenu fait sortir le remplissage en 2.** Un lancement à la main
   qui ne fait rien doit se voir. Le passage horaire garde le code 0
   (addendum, question 9).
3. **`systemd-analyze` reste hors de la CI**, comme le prévoit l'addendum. La
   vérification se fait sur le VPS, et se refait sur les fichiers installés
   (étapes 1c et 4b).
4. **Le témoin `formats.json` vient au palier 2.**

## Les deux questions

1. **Le délai de 6 h : on le garde.** Le cache des vecteurs s'écrit par lots
   de 256 fragments : une construction coupée par le délai reprend au
   lancement suivant, elle ne recommence pas. Six heures servent à couper ce
   qui serait bloqué.
2. **La CI démarre le bus avec `vps.yml` : oui.** C'est la seule épreuve de
   la combinaison du VPS avant le VPS.

## La mémoire des conteneurs : pas d'exception au garde-fou

La proposition est refusée, pour trois raisons :
- `docker stats` calcule exactement la mesure fixée le 14/11
  (`memory.current` − `inactive_file`) ;
- relier un scope `docker-<id>.scope` à son conteneur sans Docker demande
  de lire les processus d'autres comptes ;
- un motif `docker-*.scope` lirait aussi ceux d'Alamel quand ses
  conteneurs tournent.

Les conteneurs se mesurent donc par beko, aux moments qui comptent :
- pendant l'étape 8 du remplissage, le pire moment de Qdrant (la procédure
  le prévoit) ;
- aux trois moments de l'observation : au début, après le redémarrage et à
  la fin.

À la fin, beko relève aussi le `memory.peak` des deux scopes. C'est une borne
haute, cache compris, sur toute la durée de l'observation. Le README du
palier 2 écrit ces commandes pour beko.

## À corriger avant le dépôt (le code seulement)

1. **Les unités de mesure.** `pic_groupe_mo`, `resident_mo` et
   `partage_groupe_mo` divisent par 1 000 000. Or `MemoryMax=512M` compte
   en puissances de deux (512 Mio), comme la convention de ton §0 : un pic
   de 530 « Mo » décimaux paraîtrait dépasser un plafond qu'il ne touche
   pas. Passe à 2²⁰ (1 048 576), et teste-le. Ce changement ne touche aucun
   fichier que root lit.
2. **La bascule de version sous le verrou** (README, 4a) : prends la forme
   éprouvée par les tests du garde-fou, `ln -sfn … courante.neuf && flock
   -n /srv/pharmaflux/derive/chaine/verrou mv -T …`, plutôt que `flock … -c
   '<la bascule>'`, dont la chaîne passée en argument échappe à la lecture
   du garde-fou. Ce point peut attendre le palier 2.
3. Si `index etat --complet` a besoin des chemins (`--entrepot`,
   `--travail`), la CI le dira : tu corriges, sans repasser par l'IeC.

Le commit que tu déposes pour le remplissage peut donc différer de
`13168f5`, à deux conditions :
- `git diff 13168f5 <commit> -- docker-compose.yml infra/vps/vps.yml
  infra/vps/*.service` est vide ;
- la CI est verte sur ce commit.

Tu cites ce diff vide et le run de la CI dans le commit des mesures.

## La suite

1. **beko** pousse la branche et ouvre la PR en brouillon. La CI tourne.
2. **beko** fait les étapes 0, 1a, 1b, puis 1c jusqu'à la lecture de
   systemd (`verify`, `show`), sans démarrer, et colle les sorties à l'IeC.
3. **Une fois l'accord de l'IeC donné**, beko fait `enable --now` puis les
   étapes 1d, 2 et 3.
4. **Le codeur** corrige les unités de mesure. Quand la CI est verte sur ce
   commit, il le dépose (4a).
5. **beko** installe l'unité de remplissage depuis `13168f5` (4b), colle la
   lecture de systemd et le score, puis ajoute l'unité à polkit après
   l'accord de l'IeC.
6. **Le codeur** lance le remplissage, le mesure, et cite tout dans un commit
   à part, avec les relevés de beko (`docker stats` pendant l'étape 8).
