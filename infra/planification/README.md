# Planification de la collecte

La collecte tourne **sur le VPS-1 de beko**, toutes les heures à `:17`,
sous un compte dédié `pharmaflux` sans droits d'administration, par un
minuteur systemd. L'archive principale y vit sous
`/home/pharmaflux/pharmaflux-data` ; une **copie** est rapatriée chaque
semaine sur le Mac par `rapatrier.sh` (rsync en tirage, jamais de
suppression). Deux copies, parce que l'archive est irremplaçable.

Fichiers de ce dossier :

| Fichier | Rôle |
|---|---|
| `pharmaflux-collecte.service` | un passage (`pharmaflux collecte`), unité `oneshot` durcie |
| `pharmaflux-collecte.timer` | le déclenche à `*:17:00`, `Persistent=true` |
| `rapatrier.sh` | Mac ← VPS, hôte en paramètre, `rsync -a` sans `--delete` |

Toutes les commandes ci-dessous sont exécutées **par beko** (le codeur ne
touche pas au VPS), depuis son propre compte SSH, **sans jamais changer de
répertoire** : `/home/pharmaflux` n'est pas traversable par les autres
comptes tant que l'étape 2 n'est pas terminée, et chaque commande porte
donc son chemin absolu. `<hote>` désigne le VPS tel que la configuration
SSH du Mac le nomme ; aucune adresse n'est écrite dans le dépôt.

## 1. Prérequis

- VPS Debian ou Ubuntu avec systemd, accès SSH par clé, `sudo`, `git` et
  `curl` installés (`sudo apt install git curl`).
- Sur le Mac : `rsync` et `ssh` (présents d'origine), le dépôt cloné.

## 2. Créer le compte `pharmaflux` et y donner accès en lecture

Compte système, sans mot de passe, sans sudo, sans clé SSH et **sans shell
de connexion** : il ne sert qu'à exécuter la collecte, et toutes les
commandes ci-dessous passent par `sudo -u pharmaflux -H <commande>`, qui
n'a pas besoin de shell.

```bash
sudo useradd --system --create-home --home-dir /home/pharmaflux --shell /usr/sbin/nologin pharmaflux
```

`useradd --create-home` crée `/home/pharmaflux` en `750` (Ubuntu) ou `700`
(Debian). Pour que le compte SSH de beko puisse **lire** l'archive
(vérification à l'étape 6, rapatriement à l'étape 8) sans être root,
l'ajouter au groupe `pharmaflux` et rendre le répertoire traversable par
le groupe :

```bash
sudo usermod -aG pharmaflux <utilisateur-ssh>
sudo chmod 750 /home/pharmaflux
```

**Se déconnecter puis se reconnecter en SSH** pour que le nouveau groupe
prenne effet (`id` doit alors lister `pharmaflux`). L'écriture reste
réservée au compte `pharmaflux`.

## 3. Installer `uv` pour ce compte

La version d'`uv` est **figée dans l'URL** (celle du Mac de beko au moment
de l'écriture, `uv --version` pour la relever) : la même installation
donne le même résultat dans six mois.

```bash
sudo -u pharmaflux -H sh -c 'curl -LsSf https://astral.sh/uv/0.10.10/install.sh | env UV_NO_MODIFY_PATH=1 sh'
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv --version
```

`UV_NO_MODIFY_PATH=1` : le compte n'a pas de shell de connexion, inutile
de toucher à son profil ; `uv` est toujours appelé par son chemin complet.
`uv` installe lui-même Python 3.12 dans le projet (`.python-version`) :
rien d'autre à installer sur le système.

## 4. Cloner le dépôt public et installer le projet

Le dépôt est public : aucune clé de déploiement, aucun jeton.

**Pendant la mission 00**, le collecteur n'est que sur la branche de
mission (la PR n'est fusionnée qu'après 24 h de passages sur le VPS) :
cloner cette branche.

```bash
sudo -u pharmaflux -H git clone --branch mission-00-socle-et-archivage https://github.com/behramkorkut/pharmaflux.git /home/pharmaflux/pharmaflux
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv sync --directory /home/pharmaflux/pharmaflux --frozen --no-dev
sudo -u pharmaflux -H mkdir -p /home/pharmaflux/pharmaflux-data
```

`--directory` tient lieu de `cd` : `uv` travaille dans le dépôt et y crée
`.venv`. `--frozen` installe exactement les versions de `uv.lock` ;
`--no-dev` laisse de côté les outils de développement (ruff, mypy,
pytest), inutiles sur le VPS. Vérifier que la commande répond, et que le
Python de l'environnement est bien celui qu'`uv` a installé sous
`/home/pharmaflux/.local/share/uv/python` (c'est l'un des trois seuls
chemins de `/home` que l'unité rend visibles, étape 5) :

```bash
sudo -u pharmaflux -H /home/pharmaflux/pharmaflux/.venv/bin/pharmaflux --version
sudo -u pharmaflux -H /home/pharmaflux/pharmaflux/.venv/bin/pharmaflux catalogue
sudo -u pharmaflux -H readlink -f /home/pharmaflux/pharmaflux/.venv/bin/python
```

**Après la fusion de la PR sur `main`**, revenir sur `main` (entre deux
passages, voir l'étape 7) ; les mises à jour suivantes se font ensuite par
l'étape 7 :

```bash
sudo -u pharmaflux -H git -C /home/pharmaflux/pharmaflux switch main
sudo -u pharmaflux -H git -C /home/pharmaflux/pharmaflux pull --ff-only
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv sync --directory /home/pharmaflux/pharmaflux --frozen --no-dev
```

## 5. Installer et activer le minuteur

```bash
sudo install -m 644 /home/pharmaflux/pharmaflux/infra/planification/pharmaflux-collecte.service /home/pharmaflux/pharmaflux/infra/planification/pharmaflux-collecte.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pharmaflux-collecte.timer
```

Premier passage tout de suite, sans attendre `:17`, pour valider l'unité
elle-même (compte, chemins, durcissement, réseau) :

```bash
sudo systemctl start pharmaflux-collecte.service
sudo journalctl -u pharmaflux-collecte -n 40 --no-pager
```

Le journal doit se terminer par une ligne `passage <id> : 14 nouveau(x),
0 inchangé(s), 0 non modifié(s) 304, 0 erreur(s)`. Puis relever ce que
l'unité a consommé et son score d'exposition systemd :

```bash
systemctl status pharmaflux-collecte.service --no-pager | grep -E 'Mem peak|CPU:'
systemd-analyze security pharmaflux-collecte.service --no-pager | tail -1
```

`Mem peak` doit rester loin sous le plafond `MemoryMax=256M` (43 Mo
mesurés sous l'unité durcie de la mission 00). Le score d'exposition va de
0 (le plus fermé) à 10 ; l'unité de la mission 01 vise **moins de 3**
(6,3 avant son durcissement). Si un passage est tué pour dépassement
mémoire, `systemctl status` le dit (`oom-kill`), et le minuteur relance à
l'heure suivante : à signaler à l'IeC avant de toucher au plafond.

Si le passage manuel échoue avec la nouvelle unité (code de sortie autre
que 0 ou 1, `SIGSYS`, `Operation not permitted` dans le journal), la
directive en cause se lit dans `journalctl` ; la première à suspecter est
`MemoryDenyWriteExecute=true`, que l'ordre de la mission 01 prévoit de
retirer si Python ne la supporte pas sur le VPS. Le signaler au codeur
avec la ligne du journal, ne pas modifier l'unité à la main.

## 6. Vérifier

```bash
systemctl list-timers pharmaflux-collecte.timer            # prochain et dernier déclenchement
systemctl status pharmaflux-collecte.service --no-pager    # dernier passage : code de sortie, durée
sudo journalctl -u pharmaflux-collecte --since "24 hours ago" --no-pager
sudo -u pharmaflux -H env PHARMAFLUX_DATA=/home/pharmaflux/pharmaflux-data /home/pharmaflux/pharmaflux/.venv/bin/pharmaflux etat
```

Lecture de `pharmaflux etat` : une ligne par fichier, avec l'identifiant
du catalogue, la dernière archive, le dernier changement, la date affichée
par la source, le nombre de passages des 24 dernières heures et la dernière
erreur ; en dessous, les fichiers temporaires `.partiel-*` qu'un passage tué
net aurait laissés sous `bronze/` (normalement aucun). **La mission 00
est close quand la colonne « 24 h » affiche 24 pour les fichiers horaires**
(1 pour les deux entrées quotidiennes : documentation PDF et métadonnées
Open Medic).

Ce qui est normal :

- Le code de sortie est `1` dès qu'une entrée est en erreur (source
  indisponible, lien disparu de la page). `systemctl status` montre alors
  `failed` : c'est voulu, l'erreur doit se voir. Le passage suivant repart
  normalement à `:17`. Le détail est dans `journalctl` et dans la colonne
  « dernière erreur » de `pharmaflux etat`.
- La plupart des passages n'archivent rien (`inchangé`) : la BDPM change
  une à trois fois par semaine.

Place disque : 3,7 Mo compressés par passage qui archive tout ; si tout
changeait chaque jour, 1,3 Go par an. `du -sh /home/pharmaflux/pharmaflux-data`
et `df -h /home` de temps en temps.

Le manifeste est `/home/pharmaflux/pharmaflux-data/manifeste/collecte.jsonl`
(une ligne JSON par fichier et par passage, lisible par le groupe
`pharmaflux`). Chaque ligne porte la version du collecteur qui l'a écrite
(`0.1.0+<commit>`) ; les versions qui ont tourné, et combien de lignes
chacune a écrites :

```bash
grep -o '"version_collecteur": "[^"]*"' /home/pharmaflux/pharmaflux-data/manifeste/collecte.jsonl | sort | uniq -c
```

## 7. Mettre à jour après une fusion sur `main`

Entre deux passages (par exemple entre `:20` et `:10`), ou après avoir
vérifié que rien ne tourne (`systemctl is-active pharmaflux-collecte.service`
répond `inactive` ou `failed`) :

```bash
sudo -u pharmaflux -H git -C /home/pharmaflux/pharmaflux pull --ff-only
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv sync --directory /home/pharmaflux/pharmaflux --frozen --no-dev
```

**Déployer une branche de mission pour la tester** (la mission 01 le
demande au palier 1 : mesurer le score de l'unité durcie avant la fusion) :
même fenêtre entre deux passages, mais la branche remplace `main` jusqu'à
la fusion, puis on revient sur `main` (`switch main` et `pull --ff-only`,
mêmes commandes qu'à l'étape 4) :

```bash
sudo -u pharmaflux -H git -C /home/pharmaflux/pharmaflux fetch origin
sudo -u pharmaflux -H git -C /home/pharmaflux/pharmaflux switch mission-01-profilage-et-contrats
sudo -u pharmaflux -H git -C /home/pharmaflux/pharmaflux pull --ff-only
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv sync --directory /home/pharmaflux/pharmaflux --frozen --no-dev
```

Si `infra/planification/*.service` ou `*.timer` ont changé, réinstaller les
unités, puis un passage manuel pour valider la nouvelle unité avant que le
minuteur ne la déclenche :

```bash
sudo install -m 644 /home/pharmaflux/pharmaflux/infra/planification/pharmaflux-collecte.service /home/pharmaflux/pharmaflux/infra/planification/pharmaflux-collecte.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart pharmaflux-collecte.timer
sudo systemctl start pharmaflux-collecte.service
sudo journalctl -u pharmaflux-collecte -n 40 --no-pager
systemctl status pharmaflux-collecte.service --no-pager | grep -E 'Mem peak|CPU:'
systemd-analyze security pharmaflux-collecte.service --no-pager | tail -1
```

Le passage manuel doit afficher `0 erreur(s)` et des entrées `inchangé`
(rien n'a changé à la source entre deux passages), et le score affiché par
`systemd-analyze security` est celui à reporter dans le contrôle du palier.
Le passage suivant consigne la nouvelle version dans la colonne
`version_collecteur` du manifeste (`0.1.0+<commit>`, étape 6).

## 8. Rapatrier la copie sur le Mac (chaque semaine)

Prérequis : le compte SSH de beko lit l'archive, c'est l'appartenance au
groupe `pharmaflux` posée à l'étape 2. Puis, depuis le dépôt sur le Mac :

```bash
sh infra/planification/rapatrier.sh --simuler <hote>   # montre ce qui serait copié
sh infra/planification/rapatrier.sh <hote>             # copie vers ~/pharmaflux-data (ou $PHARMAFLUX_DATA)
uv run pharmaflux etat                                  # l'état, lu sur la copie
```

`rsync -a` ne copie que ce qui manque ou a changé (les archives sont
immuables : seul le manifeste grandit) ; **jamais `--delete`**, dans aucun
sens. Un transfert coupé laisse son morceau dans un dossier
`.rsync-partiel/` à côté du fichier, jamais sous le nom définitif : la copie
ne contient pas d'archive tronquée, et le passage suivant reprend le
morceau. Si l'archive distante n'est pas au chemin par défaut :
`PHARMAFLUX_VPS_DATA=/autre/chemin sh infra/planification/rapatrier.sh <hote>`.

## 9. Désinstaller

```bash
sudo systemctl disable --now pharmaflux-collecte.timer
sudo rm /etc/systemd/system/pharmaflux-collecte.service /etc/systemd/system/pharmaflux-collecte.timer
sudo systemctl daemon-reload
```

L'archive `/home/pharmaflux/pharmaflux-data` **n'est pas supprimée** : la
rapatrier d'abord (étape 8), et ne la retirer du VPS qu'une fois la copie
vérifiée (`pharmaflux etat` sur la copie).

## Sécurité

- **Aucun port entrant** ouvert pour Pharmaflux : le collecteur n'écoute
  rien, il ne fait que des requêtes sortantes **HTTPS** vers
  `base-donnees-publique.medicaments.gouv.fr` et `www.data.gouv.fr`.
- **Aucun secret sur le VPS** dans cette mission : dépôt public cloné en
  HTTPS sans jeton, aucune clé de déploiement, aucun `.env`. Le compte
  `pharmaflux` n'a ni mot de passe, ni sudo, ni clé SSH, ni shell de
  connexion ; il ne peut écrire que dans l'archive. Le compte SSH de beko
  ne fait que lire l'archive (groupe `pharmaflux`).
- **VPS partagé** : d'autres applications tournent sur la même machine.
  L'unité garantit que la collecte ne les voit pas et ne les gêne pas :
  `ProtectHome=tmpfs` remplace `/home` par un système de fichiers vide,
  dans lequel seuls **trois chemins** sont rendus visibles, le dépôt
  `/home/pharmaflux/pharmaflux` et le Python d'`uv`
  (`/home/pharmaflux/.local/share/uv/python`) en lecture seule
  (`BindReadOnlyPaths`), l'archive `/home/pharmaflux/pharmaflux-data` en
  écriture (`BindPaths`). Plafonds : `MemoryMax=256M` (cinq fois le pic
  mesuré), `CPUQuota=50%` (la moitié d'un cœur, un quart de la machine),
  `Nice=10` et `IOSchedulingClass=idle` (CPU et disque servis après tout
  le monde).
- **Unité durcie** (chaque directive est justifiée d'une ligne dans
  `pharmaflux-collecte.service`) : `NoNewPrivileges`, `ProtectSystem=strict`,
  `PrivateTmp`, `PrivateDevices`, `ProtectKernel*`, `ProtectClock`,
  `ProtectProc=invisible`, aucune capacité (`CapabilityBoundingSet=`),
  appels système limités à `@system-service` sans `@privileged` ni
  `@resources`, aucun espace de noms, familles d'adresses limitées à IP et
  Unix, `UMask=0027` (lisible par le groupe, par personne d'autre). Score
  d'exposition visé : sous 3, mesuré par beko à chaque changement d'unité
  (étape 7). Un passage qui dépasse 55 min est coupé pour ne jamais
  chevaucher le suivant.
- Les données collectées sont publiques ; le manifeste ne contient que des
  URL publiques, des empreintes et des en-têtes HTTP sans cookie.
- Les mises à jour du code sont **manuelles** (étape 7) : rien ne tire
  `main` automatiquement sur le VPS. La version d'`uv` est figée (étape 3).
- Le `User-Agent` identifie le projet et renvoie vers ce dépôt :
  `pharmaflux/<version> (+https://github.com/behramkorkut/pharmaflux)`.
