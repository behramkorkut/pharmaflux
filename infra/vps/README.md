# La chaîne sur le VPS-1 : services, premier remplissage, enchaînement

Depuis la mission 10, tout ce qui tourne en continu vit sur le VPS-1 : la
collecte (mission 00, `infra/planification/README.md`), puis la chaîne qui
va de l'archive à l'index. Cette procédure installe les services (Redpanda,
Qdrant) et fait le **premier remplissage** : tout le dérivé rebâti depuis
l'archive, puis vérifié. Puis elle met en service l'**enchaînement** :
chaque passage de collecte lance un passage de la chaîne, et les
vérifications tournent chaque jour à 03:40 UTC.

Fichiers de ce dossier :

| Fichier | Rôle | Installé par |
|---|---|---|
| `vps.yml` | second fichier compose : redémarrage, échange, délai d'arrêt, journaux | beko, sous `/etc/pharmaflux/compose/` |
| `pharmaflux-conteneurs.service` | démarre et arrête les deux conteneurs (`docker compose -p pharmaflux`) | beko, sous `/etc/systemd/system/` |
| `pharmaflux-remplissage.service` | `pharmaflux chaine remplir`, sous le compte `pharmaflux-chaine` | beko, puis ouvert au codeur dans polkit |
| `pharmaflux-chaine.service` | `pharmaflux chaine passer`, le passage horaire | beko, sous `/etc/systemd/system/` |
| `pharmaflux-collecte.service.d/chaine.conf` | complément de la collecte : `OnSuccess=` et `OnFailure=` vers le passage | beko, sous `/etc/systemd/system/pharmaflux-collecte.service.d/` |
| `pharmaflux-verification.service`, `.timer` | `pharmaflux chaine verifier`, chaque jour à 03:40 UTC | beko, sous `/etc/systemd/system/` |
| `mesurer_encodage.py` | le débit de l'encodage selon le nombre de fils (palier 2), lancé par le codeur | rien à installer |

## Qui fait quoi

Trois mains, comme l'écrit `infra/agents/vps/README.md`, qui se lit avant :

- **le codeur** écrit les fichiers dans sa branche, dépose son code sous
  `/srv/pharmaflux/code` par `ssh pharmaflux-vps`, lance le remplissage et
  le mesure. Son compte n'a ni `sudo` ni `docker` ;
- **l'IeC** contrôle chaque fichier que root lira, au commit précis ;
- **beko** installe ces fichiers depuis ce commit, jamais depuis
  `/srv/pharmaflux/code`, et fait tout ce qui demande root.

Dans ce qui suit, `<commit>` est le commit que l'IeC a contrôlé, en entier
(40 caractères). Les commandes de beko se lancent soit **sur le Mac**,
depuis le dépôt, soit **sur le VPS**, dans une session `ssh vps1`. `vps1`
est l'alias SSH qui ouvre le compte de beko, avec sa phrase de passe ;
aucune adresse n'est écrite dans le dépôt.

## Où vit chaque chose

| Quoi | Où | Écrit par | Lu par |
|---|---|---|---|
| Archive (bronze, manifestes, pages d'avis) | `/home/pharmaflux/pharmaflux-data` | la collecte (`pharmaflux`) | la chaîne, le codeur, beko |
| Code, une version par commit | `/srv/pharmaflux/code/versions/<commit>/`, avec son `.venv` | le codeur | la chaîne |
| Version en service | `/srv/pharmaflux/code/courante`, un lien | le codeur | la chaîne |
| Python 3.12 | `/srv/pharmaflux/code/python/` | le codeur (`uv`) | la chaîne |
| Fichiers d'événements, bilans, états | `/srv/pharmaflux/derive/evenements/` | la chaîne | le codeur |
| Silver (Iceberg) | `/srv/pharmaflux/derive/lakehouse/` | la chaîne | le codeur |
| Travail de l'index, cache des vecteurs | `/srv/pharmaflux/derive/index/` | la chaîne | le codeur |
| Verrou, journal des passages | `/srv/pharmaflux/derive/chaine/` | la chaîne | le codeur |
| Fichiers temporaires des étapes | `/srv/pharmaflux/derive/tmp/`, vidé au départ de chaque lancement | la chaîne | — |
| Modèle | `/srv/pharmaflux/modeles/e5-small-int8/<révision>/` | beko | la chaîne |
| Bus, base vectorielle | volumes `pharmaflux-redpanda`, `pharmaflux-qdrant` | les conteneurs | — |
| Fichiers compose | `/etc/pharmaflux/compose/` | beko | root |

L'archive est la seule chose irremplaçable. Tout le reste est **dérivé** :
il se rebâtit depuis l'archive, et rien de dérivé n'est sauvegardé.

## Les plafonds de mémoire

| Groupe | Plafond | Où il est écrit |
|---|---|---|
| Redpanda | 1 Go, sans échange | `mem_limit` (`docker-compose.yml`), `memswap_limit` (`vps.yml`) |
| Qdrant | 512 Mo, sans échange | les mêmes |
| Remplissage, passage, vérification | 512 Mo, sans échange, une seule à la fois (le verrou) | `MemoryMax`, `MemorySwapMax` de chaque unité |
| Collecte | 256 Mo | `pharmaflux-collecte.service` (inchangée) |

Somme pendant le remplissage : 2 048 Mo, et 2 304 Mo pendant les 25
secondes où la collecte de `:17` le croise. Les plafonds gardent chaque
groupe ; ce qui se mesure contre les 2 Go, c'est le résident réel (étape 8).

## Ce qui ne se fait jamais sur ce VPS

- **Aucun nettoyage de Docker** : ni `docker system prune`, ni `container
  prune`, ni `volume prune`. Les conteneurs d'Alamel y sont **arrêtés** :
  c'est exactement ce qu'un nettoyage efface.
- **Aucune commande `docker compose` sans `-p pharmaflux`** et sans les
  deux fichiers de `/etc/pharmaflux/compose/`. Hors de `compose`, seulement
  les lectures écrites ici (`image ls`, `ps`, `stats`, `inspect`) et, à la
  désinstallation, `volume rm` sur les deux volumes nommés, jamais un autre.
- **`/etc/docker/daemon.json` ne se touche pas** : le démon est partagé
  avec Alamel.
- **Rien d'Alamel** : ni ses conteneurs, ni ses volumes, ni ses fichiers,
  ni ses ports (3100, 9100, 9101).
- **Aucune unité modifiée à la main.** Une directive qui gêne se signale au
  codeur avec la ligne du journal ; le fichier corrigé repasse par la
  branche, le contrôle de l'IeC, puis beko.

## Étape 0. La collecte passe sur `main` (beko, sur le VPS)

La collecte tourne encore le code de la mission 01. Elle passe sur `main`
avant tout le reste, **entre deux passages** (entre `:20` et `:10`), pour
que l'observation porte sur le code que la fusion apportera. C'est l'étape 7
de `infra/planification/README.md` ; son unité ne change pas.

```bash
systemctl is-active pharmaflux-collecte.service
```

```bash
df -h /home | tail -1
```

Attendu : `inactive`, et plusieurs Go libres (`uv sync` installe cette fois
toutes les dépendances du projet, quelques centaines de Mo).

```bash
sudo -u pharmaflux -H git -C /home/pharmaflux/pharmaflux pull --ff-only
```

```bash
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv sync --directory /home/pharmaflux/pharmaflux --frozen --no-dev
```

Puis un passage à la main, et la relecture de son score :

```bash
sudo systemctl start pharmaflux-collecte.service; sudo journalctl -u pharmaflux-collecte -n 20 --no-pager
```

```bash
systemctl status pharmaflux-collecte.service --no-pager | grep -E 'Mem peak|CPU:'; systemd-analyze security pharmaflux-collecte.service --no-pager | tail -1
```

Attendu : `0 erreur(s)` et un score de 1,3. Le pic de mémoire se relève :
45 Mo avec le code de la mission 01, jamais mesuré avec celui de `main`. Il
doit rester loin sous les 256 Mo du plafond ; au-dessus de 128 Mo, le dire
à l'IeC.

## Étape 1. Les services (beko)

**1a. Les deux fichiers compose**, sur le Mac, depuis le commit contrôlé :

```bash
git show <commit>:docker-compose.yml | ssh vps1 'sudo tee /etc/pharmaflux/compose/docker-compose.yml > /dev/null && sudo chmod 0644 /etc/pharmaflux/compose/docker-compose.yml'
```

```bash
git show <commit>:infra/vps/vps.yml | ssh vps1 'sudo tee /etc/pharmaflux/compose/vps.yml > /dev/null && sudo chmod 0644 /etc/pharmaflux/compose/vps.yml'
```

Sur le VPS, la lecture de Docker lui-même, à coller à l'IeC :

```bash
sudo docker compose -p pharmaflux -f /etc/pharmaflux/compose/docker-compose.yml -f /etc/pharmaflux/compose/vps.yml config --format json
```

**1b. Les images**, une fois ce contrôle passé. La console est sous un
profil : elle n'est ni tirée ni lancée.

```bash
sudo docker compose -p pharmaflux -f /etc/pharmaflux/compose/docker-compose.yml -f /etc/pharmaflux/compose/vps.yml pull
```

```bash
sudo docker image ls --digests | grep -E 'redpanda|qdrant'
```

Attendu : deux images, et dans la colonne `DIGEST` les deux empreintes
écrites dans `docker-compose.yml` (`image: …@sha256:…`). Docker refuse de
lui-même une image qui ne porte pas l'empreinte demandée.

**1c. L'unité des conteneurs**, sur le Mac :

```bash
git show <commit>:infra/vps/pharmaflux-conteneurs.service | ssh vps1 'sudo tee /etc/systemd/system/pharmaflux-conteneurs.service > /dev/null && sudo chmod 0644 /etc/systemd/system/pharmaflux-conteneurs.service && sudo systemctl daemon-reload'
```

Sur le VPS, la lecture de systemd, à coller à l'IeC **avant** de démarrer :

```bash
systemd-analyze verify /etc/systemd/system/pharmaflux-conteneurs.service; echo "verify -> $?"
```

```bash
systemctl show pharmaflux-conteneurs.service -p User -p Group -p SupplementaryGroups -p Environment -p EnvironmentFiles -p WorkingDirectory -p ExecStart -p ExecStartPre -p ExecStartPost -p ExecStop -p Conflicts -p AllowIsolate -p OnSuccess -p OnFailure -p FailureAction -p SuccessAction -p LogNamespace -p DropInPaths
```

Puis le démarrage, qui attend que les deux conteneurs se disent sains :

```bash
sudo systemctl enable --now pharmaflux-conteneurs.service; systemctl status pharmaflux-conteneurs.service --no-pager | head -12
```

**1d. Vérifier.**

```bash
sudo docker compose -p pharmaflux -f /etc/pharmaflux/compose/docker-compose.yml -f /etc/pharmaflux/compose/vps.yml ps
```

```bash
sudo ss -ltnp | grep -E ':(16333|18081|18082|19092|19644) '
```

```bash
sudo docker ps -a --format '{{.Names}} {{.Status}}'
```

```bash
sudo docker stats --no-stream pharmaflux-redpanda pharmaflux-qdrant
```

Attendu :
- deux conteneurs dont la colonne `STATUS` dit `Up … (healthy)` ;
- cinq lignes, dont l'adresse locale commence par **`127.0.0.1:`** (le
  `0.0.0.0:*` de la colonne suivante est l'adresse distante, c'est normal) ;
  aucune adresse locale en `0.0.0.0:` ni en `[::]:` ;
- les trois conteneurs d'Alamel toujours `Exited` : rien ne les a touchés ;
- au repos, environ 200 Mo pour Redpanda et 100 Mo pour Qdrant (mesuré sur
  le Mac ; les chiffres du VPS vont dans le rapport).

Cette unité n'entre **pas** dans la liste polkit : les conteneurs restent à
beko. Un conteneur tombé ou arrêté à la main se relève par la commande de
l'unité, qui ne touche pas à celui qui est sain :

```bash
sudo docker compose -p pharmaflux -f /etc/pharmaflux/compose/docker-compose.yml -f /etc/pharmaflux/compose/vps.yml up -d --wait --pull never
```

`systemctl restart pharmaflux-conteneurs.service` arrête d'abord **les
deux** conteneurs : il ne se lance jamais pendant un passage de la chaîne,
et il est suivi de `verifier-bus`.

## Étape 2. Le modèle (beko)

Le modèle est copié du Mac, où il est déjà vérifié : aucun code de la
branche ne tourne sous root, et le VPS ne joint pas Hugging Face. Seul
`e5-small-int8` part, quatre fichiers, 134 Mo. Sur le Mac :

```bash
rsync -rt --exclude='.DS_Store' --rsync-path='sudo rsync' ~/pharmaflux-modeles/e5-small-int8/ vps1:/srv/pharmaflux/modeles/e5-small-int8/
```

Sur le VPS, les droits (à root, lisible par le groupe de la chaîne, par
personne d'autre) :

```bash
sudo chown -R root:pharmaflux-chaine /srv/pharmaflux/modeles && sudo find /srv/pharmaflux/modeles -type d -exec chmod 2750 {} + && sudo find /srv/pharmaflux/modeles -type f -exec chmod 0640 {} +
```

```bash
sudo find /srv/pharmaflux/modeles -type f -exec sha256sum {} +
```

Attendu : quatre fichiers, et les quatre empreintes de
`src/pharmaflux/index/modeles/e5-small-int8.toml`. La preuve qui compte est
la première étape du remplissage, `index modele verifier`, sous le compte
de la chaîne : elle recalcule ces empreintes et refuse le moindre écart.

## Étape 3. Les pages d'avis de la HAS (beko)

Les pages d'avis ne sont collectées que sur le Mac (mission 09). Elles
passent sur le VPS par une copie, **une fois** : c'est la seule écriture
dans l'archive qui ne vienne pas de la collecte, et elle se consigne dans
`docs/journal.md`. Deux sources nommées, jamais la racine : le manifeste de
collecte du Mac est ancien, il écraserait celui du VPS.

Sur le VPS, d'abord, l'état du manifeste de collecte, pour le comparer
après la copie :

```bash
sudo wc -l /home/pharmaflux/pharmaflux-data/manifeste/collecte.jsonl; sudo sha256sum /home/pharmaflux/pharmaflux-data/manifeste/collecte.jsonl
```

Sur le Mac, un essai à blanc (`-n` : rien n'est écrit). Le `rsync` du Mac
est `openrsync` : si une option lui manque, il le dit ici, avant toute
écriture dans l'archive, et beko le signale à l'IeC.

```bash
rsync -rtn --ignore-existing --exclude='.DS_Store' --rsync-path='sudo rsync' ~/pharmaflux-data/bronze/has/ vps1:/home/pharmaflux/pharmaflux-data/bronze/has/; echo "essai -> $?"
```

Puis la copie, sans `--delete`, et `--ignore-existing` en garde :

```bash
rsync -rt --ignore-existing --exclude='.DS_Store' --rsync-path='sudo rsync' ~/pharmaflux-data/bronze/has/ vps1:/home/pharmaflux/pharmaflux-data/bronze/has/
```

```bash
rsync -t --ignore-existing --rsync-path='sudo rsync' ~/pharmaflux-data/manifeste/has-pages.jsonl vps1:/home/pharmaflux/pharmaflux-data/manifeste/
```

Sur le VPS, les droits de l'archive :

```bash
sudo chown -R pharmaflux:pharmaflux /home/pharmaflux/pharmaflux-data/bronze/has /home/pharmaflux/pharmaflux-data/manifeste/has-pages.jsonl && sudo find /home/pharmaflux/pharmaflux-data/bronze/has -type d -exec chmod 0750 {} + && sudo find /home/pharmaflux/pharmaflux-data/bronze/has /home/pharmaflux/pharmaflux-data/manifeste/has-pages.jsonl -type f -exec chmod 0640 {} +
```

La preuve à l'octet, sur le Mac (sommes de contrôle, rien n'est écrit) :

```bash
rsync -rnci --exclude='.DS_Store' --rsync-path='sudo rsync' ~/pharmaflux-data/bronze/has/ vps1:/home/pharmaflux/pharmaflux-data/bronze/has/
```

```bash
shasum -a 256 ~/pharmaflux-data/manifeste/has-pages.jsonl; ssh vps1 'sudo sha256sum /home/pharmaflux/pharmaflux-data/manifeste/has-pages.jsonl; sudo find /home/pharmaflux/pharmaflux-data/bronze/has -type f | wc -l'
```

Attendu : aucune ligne de fichier pour la première commande, la même
empreinte des deux côtés, et 724 fichiers (722 pages, `robots.txt`, les
mentions légales). Sur le VPS, le manifeste de collecte relu :

```bash
sudo wc -l /home/pharmaflux/pharmaflux-data/manifeste/collecte.jsonl; sudo sha256sum /home/pharmaflux/pharmaflux-data/manifeste/collecte.jsonl
```

Attendu : la même empreinte qu'avant la copie, ou seulement des lignes en
plus si un passage de `:17` est tombé entre les deux.

Le Mac reste le seul à écrire les pages d'avis et leur manifeste. Avant
toute nouvelle collecte de la HAS sur le Mac, `rapatrier.sh` doit exclure
ces deux chemins (palier 3) : sinon la copie du VPS, plus ancienne,
reviendrait écraser le manifeste du Mac.

## Étape 4. Le code de la chaîne, puis l'unité de remplissage

**4a. Le dépôt du code (le codeur).** Une version par dossier ; le commit
s'écrit seul dans `VERSION` (`export-subst`), et `uv` installe Python 3.12
et l'environnement à côté, lisibles par le groupe de la chaîne.

```bash
git archive --prefix=versions/<commit>/ <commit> | ssh pharmaflux-vps 'tar -x -C /srv/pharmaflux/code'
```

```bash
ssh pharmaflux-vps 'env UV_PYTHON_INSTALL_DIR=/srv/pharmaflux/code/python UV_LINK_MODE=copy uv sync --directory /srv/pharmaflux/code/versions/<commit> --frozen --no-dev --no-editable --compile-bytecode 2>&1 | tail -5'
```

- `--no-editable` : le projet est copié dans l'environnement, qui ne
  dépend plus des sources ;
- `--compile-bytecode` : la chaîne lit le code sans pouvoir y écrire, le
  bytecode se compile donc au dépôt ;
- `UV_LINK_MODE=copy` : sans lui, `uv` lie les fichiers depuis son cache,
  et ils garderaient le groupe du codeur, illisible pour la chaîne.

La bascule, atomique : un lien neuf, puis un renommage, **sous le verrou de
la chaîne**. `flock -n` ne prend le verrou que si aucune commande de la
chaîne ne tourne : sinon il sort en 1 sans rien basculer, et on relance
hors de la minute `:17`. Le passage en cours finirait de toute façon sur sa
version (l'interprète est fixé à son départ) ; le verrou évite qu'un
passage commence entre le lien et le renommage.

```bash
ssh pharmaflux-vps 'ln -sfn versions/<commit> /srv/pharmaflux/code/courante.neuf && flock -n /srv/pharmaflux/derive/chaine/verrou mv -T /srv/pharmaflux/code/courante.neuf /srv/pharmaflux/code/courante'
```

Les droits et la version :

```bash
ssh pharmaflux-vps 'find /srv/pharmaflux/code ! -group pharmaflux-chaine | head -5; find /srv/pharmaflux/code -type d ! -perm -2000 | head -5; echo "hors groupe, ou dossier sans setgid : ci-dessus, rien attendu"'
```

```bash
ssh pharmaflux-vps '/srv/pharmaflux/code/courante/.venv/bin/pharmaflux --version; cat /srv/pharmaflux/code/courante/VERSION; readlink -f /srv/pharmaflux/code/courante/.venv/bin/python'
```

Attendu : aucun fichier hors du groupe `pharmaflux-chaine`, aucun dossier
sans le bit `setgid`, le commit entier, et un Python sous
`/srv/pharmaflux/code/python/`. Si `tar` ou `uv` ont ôté le `setgid` d'un
dossier, la première commande le montre : le codeur s'arrête et le signale
à l'IeC. Les autres comptes n'entrent pas : `/srv/pharmaflux/code` est en
`2750`, quels que soient les modes des fichiers qu'il contient.

Deux versions restent sur le disque, celle en service et la précédente
(revenir en arrière, c'est rebasculer le lien). Une plus ancienne se
retire par son chemin exact, `rm -r /srv/pharmaflux/code/versions/<ancien
commit>`, jamais celle que désigne `readlink /srv/pharmaflux/code/courante`.

Au premier dépôt (palier 1), le verrou n'existait pas encore : le lien a
été posé sans lui (voie a de l'IeC). Le remplissage l'a créé.

**4b. L'unité de remplissage (beko)**, sur le Mac :

```bash
git show <commit>:infra/vps/pharmaflux-remplissage.service | ssh vps1 'sudo tee /etc/systemd/system/pharmaflux-remplissage.service > /dev/null && sudo chmod 0644 /etc/systemd/system/pharmaflux-remplissage.service && sudo systemctl daemon-reload'
```

Sur le VPS, à coller à l'IeC :

```bash
sudo systemd-analyze verify /etc/systemd/system/pharmaflux-remplissage.service; echo "verify -> $?"
```

```bash
systemctl show pharmaflux-remplissage.service -p User -p Group -p SupplementaryGroups -p Environment -p EnvironmentFiles -p WorkingDirectory -p ExecStart -p ExecStartPre -p ExecStartPost -p ExecStop -p Conflicts -p AllowIsolate -p OnSuccess -p OnFailure -p FailureAction -p SuccessAction -p LogNamespace -p DropInPaths
```

```bash
systemd-analyze security pharmaflux-remplissage.service --no-pager | tail -1
```

Attendu : aucune remarque sur l'unité (`sudo`, parce que le compte de beko
ne traverse pas `/srv/pharmaflux/code`, où est la commande), et un score
sous 3 (1,1 hors ligne). Avant d'ouvrir l'unité, le filtre de sortie doit
être chargé : c'est lui, pas l'unité, qui ferme à la chaîne les ports
d'Alamel sur `127.0.0.1`.

```bash
sudo nft list table inet pharmaflux_sortie | grep -c 'skuid'
```

Attendu : `2` (une règle pour la chaîne, une pour le codeur).

Le contrôle passé, beko ajoute `"pharmaflux-remplissage.service"` à la
liste `unites` de `/etc/polkit-1/rules.d/60-pharmaflux-codeur.rules` : le
fichier d'abord, le nom ensuite. C'est la seule unité de la liste à ce
palier.

## Étapes 5 à 8. Le remplissage (le codeur)

Une commande, onze étapes, sous le verrou de la chaîne. Elle s'arrête à la
première étape qui ne rend pas 0.

| Étape | Ce qui tourne | Ce qui doit se lire |
|---|---|---|
| 5 | `index modele verifier`, `has extraire --verifier` | 4 fichiers vérifiés ; 722 pages, 721 extraites, 1 rejetée |
| 6 | `evenements --reprendre`, `schemas enregistrer`, `publier --reprendre`, `verifier-bus --racine` | le bus conforme à l'archive |
| 7 | `silver consommer`, `silver verifier` | N/N, N étant le nombre de bilans |
| 8 | `index construire --archive-has`, `index verifier`, `index etat --complet` | index conforme, format 4, les pages d'avis lues |

Lancer, sans attendre la fin (une à deux heures estimées, six au plus) :

```bash
ssh pharmaflux-vps 'systemctl start --no-block pharmaflux-remplissage.service'
```

Suivre :

```bash
ssh pharmaflux-vps 'journalctl --namespace=pharmaflux -u pharmaflux-remplissage.service -n 25 --no-pager'
```

```bash
ssh pharmaflux-vps 'systemctl show pharmaflux-remplissage.service -p ActiveState -p Result -p ExecMainStatus -p MemoryPeak -p CPUUsageNSec'
```

À la fin, la ligne du journal des passages : la durée, le code, le résident
du plus gros processus et le pic du groupe, étape par étape.

```bash
ssh pharmaflux-vps 'tail -n 1 /srv/pharmaflux/derive/chaine/passages.jsonl'
```

Attendu : `"issue": "complet"`, `"code": 0`, onze étapes, aucun processus tué
par le plafond (`"morts_par_memoire": 0`). `MemoryPeak` ne peut pas dépasser
les 512 Mo du plafond : ce qui compte est la marge. Au-dessus de 450 Mo, le
codeur le signale à l'IeC.
Pendant l'étape 8, beko relève les conteneurs (le compte du codeur ne peut
pas nommer Docker) :

```bash
sudo docker stats --no-stream pharmaflux-redpanda pharmaflux-qdrant
```

Les chiffres vont dans le rapport de la mission, dans un commit à part.

### Relancer

Le remplissage se relance par la même commande, après un échec comme après
un arrêt (`systemctl stop`) : `evenements`, `publier` et `silver consommer`
reprennent où ils en étaient ; l'index se reconstruit, plus vite, ses
vecteurs déjà calculés restant dans son cache. Une unité restée `failed`
se relance telle quelle ; `systemctl reset-failed` n'est pas nécessaire.

### Si une étape échoue

Le journal des passages nomme l'étape et son motif (`"arret"`), et le
journal de l'unité porte la sortie de la commande.

| Ce qui se lit | Ce que c'est | Qui agit |
|---|---|---|
| `<service> injoignable` | un conteneur ne répond pas | beko : la commande `up` de l'étape 1d, qui le relève |
| `tuée par le signal 9`, ou `un processus tué par le plafond de mémoire` | le plafond de 512 Mo | le codeur : la mesure va à l'IeC avant de toucher au plafond |
| une erreur de DuckDB sur un dossier `.tmp` | il a voulu déborder sur le disque | le codeur : la mesure va à l'IeC (addendum 1, question 29) |
| `Operation not permitted`, `SIGSYS` | une directive de durcissement | le codeur, avec la ligne du journal |
| `code 2` | un refus de l'étape, écrit en clair dans sa sortie | le codeur |

Les directives à soupçonner, dans l'ordre : `SystemCallFilter=~@resources`
(affinité des fils), `ProcSubset=pid` (comptage des cœurs : onnxruntime
écrit alors « cpuinfo_initialize failed »), `IPAddressAllow=127.0.0.1` (si
Docker réécrit la destination), `RestrictAddressFamilies`. Une directive ne
tombe que sur la ligne du journal qui la désigne.
`MemoryDenyWriteExecute` n'est plus dans les unités de Python : le
`python3.12` d'uv n'a pas d'en-tête `GNU_STACK`, et la directive empêchait
toute création de fil (mission 10, 14/11).

Après toute mort de Redpanda (mémoire, redémarrage du démon Docker), la
première commande est `verifier-bus` : Redpanda accuse réception avant
d'écrire, et la chaîne croirait publié ce qui ne l'est plus.

## Étape 9. L'enchaînement (beko)

Quatre fichiers, depuis le commit contrôlé : le passage horaire, les
vérifications et leur minuteur, puis le complément de la collecte, en
dernier, parce que c'est lui qui met la chaîne en service. Le code déposé
doit être celui de ce commit, ou un commit dont les unités ne diffèrent pas
(4a, sous le verrou).

**9a. Les unités**, sur le Mac :

```bash
git show <commit>:infra/vps/pharmaflux-chaine.service | ssh vps1 'sudo tee /etc/systemd/system/pharmaflux-chaine.service > /dev/null && sudo chmod 0644 /etc/systemd/system/pharmaflux-chaine.service'
```

```bash
git show <commit>:infra/vps/pharmaflux-verification.service | ssh vps1 'sudo tee /etc/systemd/system/pharmaflux-verification.service > /dev/null && sudo chmod 0644 /etc/systemd/system/pharmaflux-verification.service'
```

```bash
git show <commit>:infra/vps/pharmaflux-verification.timer | ssh vps1 'sudo tee /etc/systemd/system/pharmaflux-verification.timer > /dev/null && sudo chmod 0644 /etc/systemd/system/pharmaflux-verification.timer && sudo systemctl daemon-reload'
```

Sur le VPS, à coller à l'IeC :

```bash
sudo systemd-analyze verify /etc/systemd/system/pharmaflux-chaine.service /etc/systemd/system/pharmaflux-verification.service /etc/systemd/system/pharmaflux-verification.timer; echo "verify -> $?"
```

```bash
systemctl show pharmaflux-chaine.service pharmaflux-verification.service -p User -p Group -p SupplementaryGroups -p Environment -p EnvironmentFiles -p WorkingDirectory -p ExecStart -p ExecStartPre -p ExecStartPost -p ExecStop -p Conflicts -p OnSuccess -p OnFailure -p FailureAction -p SuccessAction -p LogNamespace -p DropInPaths
```

```bash
systemd-analyze security pharmaflux-chaine.service --no-pager | tail -1; systemd-analyze security pharmaflux-verification.service --no-pager | tail -1
```

Attendu : aucune remarque, un score sous 3 pour chacune (le durcissement
est celui du remplissage, 1,2 en ligne), aucun `OnSuccess=` ni
`OnFailure=` sur la chaîne : un échec du passage ne relance rien.

**Avant 9b, le code.** Le codeur dépose le commit contrôlé et bascule
`courante` sous le verrou (4a) ; sans cela, chaque passage lancerait
`chaine passer` sur une version qui ne la connaît pas. beko vérifie que le
lien désigne bien ce commit :

```bash
ls -l /srv/pharmaflux/code/courante
```

**9b. La mise en service**, l'accord de l'IeC donné. Le minuteur d'abord :

```bash
sudo systemctl enable --now pharmaflux-verification.timer
```

Puis une vérification, tout de suite (addendum 1, question 21 : après
chaque dépôt). Elle dure environ quatre minutes ; la commande rend la main
à sa fin :

```bash
sudo systemctl start pharmaflux-verification.service
```

À coller à l'IeC, avec `chaine etat` (ci-dessous, la commande de beko) :

```bash
systemctl show pharmaflux-verification.service -p Result -p ExecMainStatus
```

Attendu : `Result=success`, `ExecMainStatus=0`. Sinon, on s'arrête : le
complément n'est pas posé.

Seulement ensuite, le complément de la collecte, **entre deux passages**
(pas entre `:15` et `:20`). Son dossier :

```bash
ssh vps1 'sudo install -d -m 0755 /etc/systemd/system/pharmaflux-collecte.service.d'
```

```bash
git show <commit>:infra/vps/pharmaflux-collecte.service.d/chaine.conf | ssh vps1 'sudo tee /etc/systemd/system/pharmaflux-collecte.service.d/chaine.conf > /dev/null && sudo chmod 0644 /etc/systemd/system/pharmaflux-collecte.service.d/chaine.conf && sudo systemctl daemon-reload'
```

```bash
systemctl show pharmaflux-collecte.service -p OnSuccess -p OnFailure -p DropInPaths; systemctl list-timers --all --no-pager | grep pharmaflux
```

Attendu : `OnSuccess=pharmaflux-chaine.service`, la même ligne pour
`OnFailure=`, le complément dans `DropInPaths`, et deux minuteurs : la
collecte (`:17`) et les vérifications (03:40 UTC). Le fichier
`pharmaflux-collecte.service` ne change pas d'un octet.

**9c. La liste polkit se vide.** Pendant l'observation, le codeur lit et ne
lance rien (addendum 1, I) : beko retire `"pharmaflux-remplissage.service"`
de la liste `unites` de `/etc/polkit-1/rules.d/60-pharmaflux-codeur.rules`.
Aucune autre unité n'y entre.

Le premier passage part à la fin de la collecte suivante. Il écrit le
témoin des formats (`/srv/pharmaflux/derive/chaine/formats.json`) : le
remplissage du palier 1 l'a précédé.

## L'état de la chaîne

`pharmaflux chaine etat` lit le journal des passages, le manifeste et le
témoin. Il ne lance rien, n'écrit rien et ne joint aucun service. La
première ligne dit tout : `à jour`, `en retard de N passage(s) de
collecte`, ou `en panne (code N, étape X)`.

Le codeur, depuis le Mac :

```bash
ssh pharmaflux-vps '/srv/pharmaflux/code/courante/.venv/bin/pharmaflux chaine etat --racine /home/pharmaflux/pharmaflux-data --derive /srv/pharmaflux/derive'
```

L'IeC, sans option, ses chemins en deux variables devant la commande :

```bash
ssh pharmaflux-vps 'PHARMAFLUX_DATA=/home/pharmaflux/pharmaflux-data PHARMAFLUX_DERIVE=/srv/pharmaflux/derive /srv/pharmaflux/code/courante/.venv/bin/pharmaflux chaine etat'
```

beko, le matin, sur le VPS, par son compte (une fois celui du codeur clos) :

```bash
sudo -u pharmaflux-chaine env PHARMAFLUX_DATA=/home/pharmaflux/pharmaflux-data PHARMAFLUX_DERIVE=/srv/pharmaflux/derive /srv/pharmaflux/code/courante/.venv/bin/pharmaflux chaine etat
```

Le détail, avec la dernière erreur de chaque passage et le délai de chaque
archive : `--format json`. Les lignes de chaque étape sont dans le journal
de Pharmaflux :

```bash
ssh pharmaflux-vps 'journalctl --namespace=pharmaflux -u pharmaflux-chaine.service -u pharmaflux-verification.service -n 40 --no-pager'
```

| Ce qui se lit | Ce que c'est | Qui agit |
|---|---|---|
| `passage sauté : une autre commande de la chaîne tourne` | le verrou est tenu (une vérification, un remplissage) | personne : le passage suivant rattrape. Si l'âge du dernier passage complet grandit, beko et l'IeC regardent |
| `échec circonscrit (… file des échecs …)` | des messages refusés par leur contrat, rangés à part | le codeur, à l'IeC : le bus reste cohérent |
| `refusé avant toute étape (le dérivé a été bâti avec d'autres formats …)` | le code déposé a changé un format | le geste est écrit dans la phrase : remplissage, ou dérivé à rebâtir |
| `"geste"` dans `"arret"` | une étape refuse, par exemple sans index | le geste écrit |

## Les relevés de beko

Le compte du codeur ne peut pas nommer Docker : les conteneurs se mesurent
par beko, sur le VPS, au début de l'observation, après le redémarrage, et à
la fin. La mesure instantanée (`memory.current` − `inactive_file`) :

```bash
sudo docker stats --no-stream pharmaflux-redpanda pharmaflux-qdrant
```

Le pic de chaque conteneur, depuis son démarrage : une borne haute, cache
compris, et non une lecture instantanée. Avec les compteurs `max` (le noyau
a repris de la mémoire au plafond) et `oom_kill` (un processus tué) :

```bash
for c in pharmaflux-redpanda pharmaflux-qdrant; do id=$(sudo docker inspect -f '{{.Id}}' $c); g=/sys/fs/cgroup/system.slice/docker-$id.scope; echo "== $c"; sudo cat $g/memory.peak; sudo grep -E '^(anon|file) ' $g/memory.stat; sudo grep -E '^(max|oom_kill) ' $g/memory.events; done
```

Le redémarrage du VPS, au milieu de l'observation, est à beko (`sudo
reboot`), hors de la minute `:17`. Après lui : les conteneurs reviennent
par leur unité, la collecte rattrape son passage (`Persistent=true`), et ce
passage relance la chaîne. Aucun geste de plus.

## Désinstaller (beko)

L'ordre s'inverse. Le complément de la collecte part d'abord : la chaîne
n'est plus lancée, et la collecte continue seule, comme avant la mission.

```bash
sudo rm /etc/systemd/system/pharmaflux-collecte.service.d/chaine.conf && sudo systemctl daemon-reload
```

Puis les vérifications et le passage :

```bash
sudo systemctl disable --now pharmaflux-verification.timer; sudo systemctl stop pharmaflux-chaine.service pharmaflux-verification.service
```

```bash
sudo rm /etc/systemd/system/pharmaflux-verification.timer /etc/systemd/system/pharmaflux-verification.service /etc/systemd/system/pharmaflux-chaine.service && sudo systemctl daemon-reload
```

Le nom du remplissage sort de polkit s'il y est encore (retirer
`"pharmaflux-remplissage.service"` de la liste `unites` de
`/etc/polkit-1/rules.d/60-pharmaflux-codeur.rules`), puis :

```bash
sudo systemctl stop pharmaflux-remplissage.service; sudo systemctl disable --now pharmaflux-conteneurs.service
```

```bash
sudo rm /etc/systemd/system/pharmaflux-remplissage.service /etc/systemd/system/pharmaflux-conteneurs.service && sudo systemctl daemon-reload
```

Les conteneurs sont alors arrêtés, pas effacés, et leurs volumes restent.
Pour les retirer aussi, **par leur nom**, jamais par un nettoyage :

```bash
sudo docker compose -p pharmaflux -f /etc/pharmaflux/compose/docker-compose.yml -f /etc/pharmaflux/compose/vps.yml down
```

```bash
sudo docker volume rm pharmaflux-redpanda pharmaflux-qdrant
```

```bash
sudo rm /etc/pharmaflux/compose/docker-compose.yml /etc/pharmaflux/compose/vps.yml
```

Les deux images restent sur le disque. Elles se retirent une par une, par
l'identifiant que montre `sudo docker image ls --digests`, jamais par un
nettoyage.

Le dérivé (`/srv/pharmaflux/derive`), le code et le modèle se retirent de
la même façon, à la main. **L'archive ne se retire pas** : ni le bronze, ni
les manifestes, ni les pages d'avis copiées à l'étape 3. La collecte
continue seule, comme avant la mission 10. Les comptes, polkit et le filtre
de sortie se ferment par `infra/agents/vps/README.md` (« Clôture d'une
mission »).

## Sécurité

- **Aucun port entrant.** Les cinq ports de Pharmaflux sont liés à
  `127.0.0.1` ; rien n'est exposé sur Internet.
- **Aucun secret sur le VPS** : ni clé, ni jeton, ni `.env`. L'assistant et
  l'API Claude ne tournent pas ici.
- **Aucun compte de Pharmaflux dans le groupe `docker`.** Les conteneurs
  sont lancés par une unité système dont les deux fichiers appartiennent à
  root : des volumes nommés seulement, aucun montage de l'hôte, aucun
  privilège. `tests/test_vps.py` le vérifie à chaque passage de la CI.
- **La chaîne ne peut pas abîmer l'archive.** Elle tourne sous
  `pharmaflux-chaine`, qui la lit ; l'unité la monte en lecture seule
  (`BindReadOnlyPaths`) et n'ouvre en écriture que `/srv/pharmaflux/derive`.
- **La chaîne ne joint que la boucle locale** : `IPAddressDeny=any`,
  `IPAddressAllow=127.0.0.1`, en plus du filtre de sortie du compte.
- **Le VPS est partagé.** Chaque groupe a son plafond, sans échange ; la
  chaîne passe après tout le monde (`Nice=10`, `CPUWeight=20`,
  `IOSchedulingClass=idle`) et meurt la première si la machine manque de
  mémoire (`OOMScoreAdjust=500`) : elle reprend sans perte.
- **Unité durcie** sur le modèle de celle de la collecte, chaque directive
  justifiée d'une ligne dans le fichier. Score d'exposition visé : sous 3.
