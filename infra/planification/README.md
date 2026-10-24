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
pytest), inutiles sur le VPS. Vérifier que la commande répond :

```bash
sudo -u pharmaflux -H /home/pharmaflux/pharmaflux/.venv/bin/pharmaflux --version
sudo -u pharmaflux -H /home/pharmaflux/pharmaflux/.venv/bin/pharmaflux catalogue
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
0 inchangé(s), 0 non modifié(s) 304, 0 erreur(s)`.

## 6. Vérifier

```bash
systemctl list-timers pharmaflux-collecte.timer            # prochain et dernier déclenchement
systemctl status pharmaflux-collecte.service --no-pager    # dernier passage : code de sortie, durée
sudo journalctl -u pharmaflux-collecte --since "24 hours ago" --no-pager
sudo -u pharmaflux -H env PHARMAFLUX_DATA=/home/pharmaflux/pharmaflux-data /home/pharmaflux/pharmaflux/.venv/bin/pharmaflux etat
```

Lecture de `pharmaflux etat` : une ligne par fichier, avec la dernière
archive, le dernier changement, la date affichée par la source, le nombre
de passages des 24 dernières heures et la dernière erreur. **La mission 00
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

## 7. Mettre à jour après une fusion sur `main`

Entre deux passages (par exemple entre `:20` et `:10`), ou après avoir
vérifié que rien ne tourne (`systemctl is-active pharmaflux-collecte.service`
répond `inactive` ou `failed`) :

```bash
sudo -u pharmaflux -H git -C /home/pharmaflux/pharmaflux pull --ff-only
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv sync --directory /home/pharmaflux/pharmaflux --frozen --no-dev
```

(La première fois, après la fusion de la PR de la mission 00, faire
d'abord le `git switch main` de l'étape 4.) Si
`infra/planification/*.service` ou `*.timer` ont changé, refaire l'étape 5
(`install`, `daemon-reload`, puis
`sudo systemctl restart pharmaflux-collecte.timer`). Le passage suivant
consigne la nouvelle version dans la colonne `version_collecteur` du
manifeste (`0.1.0+<commit>`).

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
sens. Si l'archive distante n'est pas au chemin par défaut :
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
- **Unité durcie** : `NoNewPrivileges`, `ProtectSystem=strict`,
  `ProtectHome=read-only` avec `ReadWritePaths` sur la seule archive,
  `PrivateTmp`, `PrivateDevices`, familles d'adresses limitées à IP et
  Unix. Un passage qui dépasse 55 min est coupé pour ne jamais chevaucher
  le suivant.
- Les données collectées sont publiques ; le manifeste ne contient que des
  URL publiques, des empreintes et des en-têtes HTTP sans cookie.
- Les mises à jour du code sont **manuelles** (étape 7) : rien ne tire
  `main` automatiquement sur le VPS. La version d'`uv` est figée (étape 3).
- Le `User-Agent` identifie le projet et renvoie vers ce dépôt :
  `pharmaflux/<version> (+https://github.com/behramkorkut/pharmaflux)`.
