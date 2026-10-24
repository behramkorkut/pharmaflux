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
touche pas au VPS). `<hote>` désigne le VPS tel que la configuration SSH
du Mac le nomme ; aucune adresse n'est écrite dans le dépôt.

## 1. Prérequis

- VPS Debian ou Ubuntu avec systemd, accès SSH par clé, `sudo`, `git` et
  `curl` installés (`sudo apt install git curl`).
- Sur le Mac : `rsync` et `ssh` (présents d'origine), le dépôt cloné.

## 2. Créer le compte `pharmaflux`

Compte système, sans mot de passe, sans sudo, sans clé SSH : il ne sert
qu'à exécuter la collecte.

```bash
sudo useradd --system --create-home --home-dir /home/pharmaflux --shell /bin/bash pharmaflux
```

## 3. Installer `uv` pour ce compte

```bash
sudo -u pharmaflux -H sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv --version
```

`uv` installe lui-même Python 3.12 dans le projet (`.python-version`) :
rien d'autre à installer sur le système.

## 4. Cloner le dépôt public et installer le projet

Le dépôt est public : aucune clé de déploiement, aucun jeton.

```bash
sudo -u pharmaflux -H git clone https://github.com/behramkorkut/pharmaflux.git /home/pharmaflux/pharmaflux
cd /home/pharmaflux/pharmaflux
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv sync --frozen --no-dev
sudo -u pharmaflux -H mkdir -p /home/pharmaflux/pharmaflux-data
```

`--frozen` installe exactement les versions de `uv.lock` ; `--no-dev`
laisse de côté les outils de développement (ruff, mypy, pytest), inutiles
sur le VPS. Vérifier que la commande répond :

```bash
sudo -u pharmaflux -H /home/pharmaflux/pharmaflux/.venv/bin/pharmaflux --version
sudo -u pharmaflux -H /home/pharmaflux/pharmaflux/.venv/bin/pharmaflux catalogue
```

## 5. Installer et activer le minuteur

```bash
sudo install -m 644 infra/planification/pharmaflux-collecte.service infra/planification/pharmaflux-collecte.timer /etc/systemd/system/
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
cd /home/pharmaflux/pharmaflux
sudo -u pharmaflux -H git pull --ff-only
sudo -u pharmaflux -H /home/pharmaflux/.local/bin/uv sync --frozen --no-dev
```

Si `infra/planification/*.service` ou `*.timer` ont changé, refaire
l'étape 5 (`install`, `daemon-reload`, puis
`sudo systemctl restart pharmaflux-collecte.timer`). Le passage suivant
consigne la nouvelle version dans la colonne `version_collecteur` du
manifeste (`0.1.0+<commit>`).

## 8. Rapatrier la copie sur le Mac (chaque semaine)

Prérequis, une fois : l'utilisateur SSH de beko sur le VPS doit pouvoir
lire l'archive. Le plus simple est de l'ajouter au groupe `pharmaflux`
et de rendre le répertoire traversable par le groupe :

```bash
sudo usermod -aG pharmaflux <utilisateur-ssh>
sudo chmod 750 /home/pharmaflux
```

Puis, depuis le dépôt sur le Mac :

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
  `pharmaflux` n'a ni mot de passe, ni sudo, ni clé SSH ; il ne peut écrire
  que dans l'archive.
- **Unité durcie** : `NoNewPrivileges`, `ProtectSystem=strict`,
  `ProtectHome=read-only` avec `ReadWritePaths` sur la seule archive,
  `PrivateTmp`, `PrivateDevices`, familles d'adresses limitées à IP et
  Unix. Un passage qui dépasse 55 min est coupé pour ne jamais chevaucher
  le suivant.
- Les données collectées sont publiques ; le manifeste ne contient que des
  URL publiques, des empreintes et des en-têtes HTTP sans cookie.
- Les mises à jour du code sont **manuelles** (étape 7) : rien ne tire
  `main` automatiquement sur le VPS.
- Le `User-Agent` identifie le projet et renvoie vers ce dépôt :
  `pharmaflux/<version> (+https://github.com/behramkorkut/pharmaflux)`.
