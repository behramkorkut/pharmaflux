# Mission 00 — palier 3 : planification et premier passage réel

**Correctifs du contrôle du palier 2** : commit `3b805c7`.
C1 : `dernieres_empreintes` retient toute ligne qui a un `chemin_archive`,
quel que soit son statut ; `analyse_impossible` compare sur le `sha256` des
octets (une page de maintenance identique n'est archivée qu'une fois) ;
`_appliquer_page` enchaîne les motifs (`HTTP 404 ; lien_absent`) au lieu
d'écraser. C2 : une dernière ligne tronquée est ignorée avec avertissement ;
`ajouter` écrit d'abord une **marque de troncature** puis `\n`, de sorte
que la ligne coupée reste ignorée même quand d'autres lignes la suivent
(sans la marque, elle serait « au milieu » dès le passage suivant et
`lire` lèverait l'erreur franche que tu demandes) ; toute autre ligne
illisible lève `ManifesteCorrompu`. 14e entrée `bdpm.documentation_formats`
(quotidienne, octets ; fixture : 4 Ko du PDF, une requête réelle). Neuf
tests ajoutés (54), dont les deux que tu décris et le cas 404 + lien absent.

**Fait** (décision 8, addendum 2) : `infra/planification/` —
`pharmaflux-collecte.service` (oneshot, `User=pharmaflux`,
`PHARMAFLUX_DATA` dans l'unité, `ExecStart=.venv/bin/pharmaflux collecte`,
`TimeoutStartSec=55min`, durcissement : `ProtectSystem=strict`,
`ProtectHome=read-only` + `ReadWritePaths` sur la seule archive,
`NoNewPrivileges`, `PrivateTmp`), `pharmaflux-collecte.timer`
(`OnCalendar=*-*-* *:17:00`, `Persistent=true`), `rapatrier.sh` (POSIX sh,
`rsync -a -v --partial`, `--simuler`, hôte en paramètre, exclusion des
`.partiel-*`, jamais `--delete`, aucune adresse), `README.md` (compte,
`uv`, clone public, `uv sync --frozen --no-dev`, minuteur, vérification,
mise à jour, rapatriement, désinstallation, rubrique Sécurité). README et
`docs/CONTEXTE.md` pointent dessus. Journal : chiffres du passage réel.

**Passage réel, un seul, sur le Mac** (18:27:36 UTC, racine temporaire
hors dépôt, dans le dossier temporaire de session) : 14 requêtes, **14 `nouveau`, 0 erreur,
30 s** de bout en bout, 29,1 Mo bruts → 3,7 Mo archivés, 14 lignes de
manifeste, `etat` lisible, aucun fichier partiel. `CIS_InfoImportantes.txt`
identique pour la troisième fois (5 h après la première).

**Vérifications locales** (arbre committé comme fils de `3b805c7`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 41 files already formatted |
| `uv run mypy src` | Success: no issues found in 11 source files |
| `uv run pytest -q` | 54 passed |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 15 tests, OK |
| `shellcheck infra/planification/*.sh` | non installé sur le Mac : CI seulement ; `sh -n` et chemin d'usage testés |

**Écarts à l'ordre et interprétations** :

1. `ExecStart` appelle directement `.venv/bin/pharmaflux` (créé par
   `uv sync`) plutôt que `uv run` : rien à résoudre ni à écrire au moment
   du passage, compatible avec `ProtectHome=read-only`. `uv` ne sert qu'à
   l'installation et aux mises à jour.
2. `uv sync --frozen --no-dev` sur le VPS (l'addendum dit `--frozen`) :
   ruff, mypy et pytest n'y servent à rien.
3. C2 : la marque de troncature (`\t# ligne tronquee par une coupure,
   ignoree`, ajoutée en fin de la ligne coupée, jamais de réécriture) est
   mon interprétation pour concilier « ligne tronquée ignorée » et « ligne
   illisible au milieu = erreur franche ».
4. Le code de sortie 1 en cas d'erreur fait passer l'unité en `failed` dans
   `systemctl status` : voulu, documenté (le minuteur relance quand même).
5. Les unités ne sont pas exécutées ici (pas de systemd sur le Mac, aucun
   accès au VPS) : relecture à la main des directives, pas de test.

**Questions pour l'IeC** : la marque de troncature (point 3) te convient-elle,
ou préfères-tu un simple `\n` et une tolérance de `lire` étendue ?

**Propositions d'évolution** : (a) `etat` : la colonne « fichier » s'élargit
avec le nom du PDF (72 caractères) ; afficher l'identifiant du catalogue
plutôt que `source/fichier` ; (b) `etat` pourrait signaler un fichier
`.partiel-*` orphelin (ta remarque mineure), à la mission 01 ; (c) le
journal `logging` affiche l'heure locale alors que le manifeste est en UTC :
passer le format du journal en UTC au prochain palier qui touche `cli.py`.
