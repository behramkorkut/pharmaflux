# Mission 00 — correctif : durcissement de l'unité pour un VPS partagé

Consigne : `docs/relectures/mission-00/consigne-unite-vps.md`. Le
comportement du collecteur ne change pas ; aucun fichier Python touché.

**Fait dans `infra/planification/pharmaflux-collecte.service`** :

- `ProtectHome=tmpfs` remplace `ProtectHome=read-only` ; `ReadWritePaths`
  disparaît. `BindReadOnlyPaths=/home/pharmaflux/pharmaflux
  /home/pharmaflux/.local/share/uv/python` (dépôt et Python d'`uv`),
  `BindPaths=/home/pharmaflux/pharmaflux-data` (archive, en écriture). De
  `/home`, le service ne voit que ces trois chemins.
- `MemoryMax=256M`, `CPUQuota=50%`, `IOSchedulingClass=idle`, `Nice=10`
  conservé. Chaque directive porte son commentaire d'une ligne, et l'en-tête
  liste les trois chemins supposés.

**Ce qui est lu sous `/home` pendant un passage** (vérifié dans `src/`) :

- `cli.py` : la racine vient de `PHARMAFLUX_DATA` (posée dans l'unité) ;
  `Path.home()` ne sert que si la variable manque. Archive : couverte par
  `BindPaths`.
- `passage.py`, `version_collecteur()` : `git -C <dossier du module>
  rev-parse --short HEAD`. Le module est dans `src/` du dépôt (installation
  éditable), `.git` aussi : couvert par `BindReadOnlyPaths`, et
  `rev-parse` n'écrit rien. Sans `~/.gitconfig` ni `~/.config/git`, git
  fonctionne à l'identique. Si git échouait, la version retomberait sur
  `0.1.0` sans arrêter le passage.
- `httpx` : le magasin de certificats est celui de `certifi`, dans `.venv`
  du dépôt. Aucun `~/.netrc` ni fichier personnel n'est requis.
- Python : `.venv/bin/python` est un lien vers le Python installé par `uv`
  sous `~/.local/share/uv/python` (`pyvenv.cfg` y pointe aussi) : couvert.
  Le site utilisateur (`~/.local/lib/python3.12`) est absent, ce qui est
  sans effet. Le README demande un `readlink -f` à l'étape 4 pour
  confirmer ce chemin sur le VPS.

**Fait dans `infra/planification/README.md`** : étape 4, `readlink -f`
du Python ; étape 5, `Mem peak`/`CPU:` de `systemctl status` et
`systemd-analyze security … | tail -1` après le premier passage, conduite
à tenir en cas d'`oom-kill` ; étape 6, chemin du manifeste et commande des
versions distinctes de `version_collecteur` (`grep -o … | sort | uniq -c`,
sur le JSON tel que `json.dumps` l'écrit) ; étape 7, séquence explicite
pour une unité modifiée (`pull`, `uv sync`, `install`, `daemon-reload`,
`restart` du minuteur, passage manuel, relevés) : c'est la séquence à
suivre pour appliquer ce correctif ; section Sécurité, rubrique « VPS
partagé » (trois chemins visibles, plafonds), sans nommer l'autre
application.

**Vérifications locales** : pas de systemd sur le Mac. Directives relues
contre `systemd.exec(5)` (`ProtectHome=tmpfs` avec `BindPaths`/
`BindReadOnlyPaths`, `IOSchedulingClass`, `Nice`) et
`systemd.resource-control(5)` (`MemoryMax`, `CPUQuota`), toutes
disponibles bien avant systemd 259. `sh infra/git-hooks/test-crochets.sh` :
tout est conforme. Ruff, mypy et pytest non relancés (aucun fichier Python
modifié). Sur le VPS, par beko : `systemd-analyze verify`, passage manuel
(`0 erreur(s)`, entrées `inchangé`), `Mem peak` sous 256 Mo, score
d'exposition.

**Remarques** :

1. `CPUQuota=50%` étale les 2,35 s de CPU sur au moins 4,7 s de temps
   réel, négligeable devant les 29 s du passage (attente réseau).
2. `IOSchedulingClass=idle` n'a d'effet qu'avec un ordonnanceur disque qui
   gère les classes (BFQ) ; avec `mq-deadline` ou `none`, fréquents sur
   les disques virtuels, il est ignoré sans erreur. La collecte écrit
   3,7 Mo par passage au plus : le risque réel est faible de toute façon.
3. Les chemins de `BindReadOnlyPaths` ne portent pas le préfixe `-`
   (ignorer si absent) : si le Python d'`uv` n'était pas à ce chemin, mieux
   vaut que l'unité refuse de démarrer, avec le motif dans `journalctl`,
   plutôt qu'un chemin silencieusement absent. Le `readlink -f` de
   l'étape 4 le vérifie avant.
4. Dépassement mémoire : le processus est tué (`SIGKILL`, `oom-kill` dans
   `systemctl status`), le passage en cours est perdu sans corrompre
   l'archive (écriture par fichier temporaire puis renommage ; manifeste
   en ajout seul, dernière ligne tronquée ignorée), et le minuteur relance
   à l'heure suivante.
