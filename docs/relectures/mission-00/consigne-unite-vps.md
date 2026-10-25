# Mission 00 — consigne : durcir l'unité pour un VPS partagé (IeC)

**Contexte** : le VPS-1 accueille aussi, jusqu'à mi-novembre, la
pré-production d'une autre application de beko (conteneurs Docker, sans
donnée confidentielle). La collecte y est installée depuis `a8aa07b` et le
premier passage manuel est conforme : `14 nouveau(x), 0 erreur(s)`, 29 s,
2,35 s de CPU, **pic mémoire 46,9 Mo**. Le VPS a 2 cœurs, 3,7 Go de
mémoire, dont une partie déjà en swap.

Deux objectifs, sans changer le comportement du collecteur :

1. le service ne doit **voir** que ce dont il a besoin dans `/home` ;
2. il ne doit **jamais gêner** l'autre application (mémoire, CPU, disque).

## Ce qui est demandé dans `pharmaflux-collecte.service`

**Visibilité de `/home`.** Remplacer `ProtectHome=read-only` et
`ReadWritePaths=` par :

- `ProtectHome=tmpfs` ;
- `BindReadOnlyPaths=` sur le dépôt `/home/pharmaflux/pharmaflux` **et** sur
  le Python qu'`uv` a installé, dans `/home/pharmaflux/.local/share/uv/python`.
  `.venv/bin/python` est un lien vers ce dossier : sans lui, le service ne
  démarre pas ;
- `BindPaths=/home/pharmaflux/pharmaflux-data`, en écriture.

Vérifie dans le code que rien d'autre n'est lu sous `/home` pendant un
passage. Le `git rev-parse` de `version_collecteur()` lit `.git`, qui est
dans le dépôt : c'est couvert. Git ne trouvera pas de `~/.gitconfig`, et
c'est sans effet.

**Ressources.** Ajouter :

- `MemoryMax=256M`, soit environ cinq fois le pic mesuré ;
- `CPUQuota=50%`, soit un quart de la machine ;
- `IOSchedulingClass=idle`.

Garder `Nice=10`. Chaque directive porte un commentaire d'une ligne qui
dit pourquoi elle est là, dans le style des commentaires actuels.

## Ce qui est demandé dans `README.md`

- **Section Sécurité** : la cohabitation avec une autre application, et
  ce que l'unité garantit. Le service ne voit de `/home` que trois chemins,
  et il a un plafond mémoire et CPU. Ne nomme pas l'autre application.
- **Étape 5** : après le premier passage, ajouter
  `systemd-analyze security pharmaflux-collecte.service --no-pager | tail -1`
  (le score d'exposition) et la lecture de `Mem peak` dans
  `systemctl status`.
- **Étape 6 ou 8** : le manifeste est
  `/home/pharmaflux/pharmaflux-data/manifeste/collecte.jsonl`. Donne une
  commande qui affiche les valeurs distinctes de `version_collecteur`.
- **Étape 7** (mise à jour) : elle couvre déjà le cas d'une unité
  modifiée. Vérifie qu'elle se suit telle quelle pour appliquer ce
  correctif : `pull`, `install`, `daemon-reload`, puis un passage manuel.

## Vérifications

Tu ne peux pas exécuter systemd sur le Mac : relis les directives contre
`man systemd.exec` et `man systemd.resource-control` (systemd 259 sur le
VPS). C'est beko qui fera la vérification réelle :

- `systemd-analyze verify` ;
- un passage manuel, qui doit afficher `0 erreur(s)` et des entrées
  `inchangé` ;
- un `Mem peak` sous le plafond ;
- le score d'exposition.

Lance ruff, mypy et pytest seulement si tu touches au code Python.

## Suite

1. Un commit « durcissement de l'unité pour un VPS partagé », avec un
   court rapport `docs/rapports/mission-00/correctif-unite.md`. Commite
   aussi cette consigne, sans la modifier. Puis arrêt avec « correctif
   unité `<sha>` ».
2. beko pousse, applique l'étape 7 sur le VPS entre deux passages, et me
   colle les sorties.
3. Ensuite seulement, il lance le relecteur, pour qu'il relise l'unité
   définitive. `pr.md` attend toujours les 24 h de passages.
