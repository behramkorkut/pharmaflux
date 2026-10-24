# Mission 00 — relecture 1
**Commit relu** : `07c77a6` (sommet de `mission-00-socle-et-archivage`)
**Verdict** : NON CONFORME

Lu : l'ordre et ses addenda 1 et 2 (sur `main`), les cinq rapports du
codeur, les trois contrôles et la consigne de l'IeC, tout `src/`, les tests,
`infra/planification/`, la CI, `README.md`, `docs/CONTEXTE.md`, la fin du
journal. Le travail est de bonne facture : les correctifs C1, C2 et P1 sont
tenus, les tests portent sur le comportement, l'unité suit la consigne.
Restent deux défauts qui, l'un tout de suite, l'autre dans quelques mois,
arrêtent la collecte, la seule brique qui ne se rattrape pas.

## Bloquants

1. `src/pharmaflux/collecte/telechargement.py:117` et
   `src/pharmaflux/collecte/passage.py:165-171` — **une partie des erreurs
   httpx fait planter tout le passage.** `telecharger` n'attrape que
   `httpx.TransportError`, et `_collecter` que `ErreurTelechargement`. Or
   `httpx.TooManyRedirects` et `httpx.DecodingError` dérivent de
   `httpx.RequestError`, pas de `TransportError`. Le client suit les
   redirections (`follow_redirects=True`) et décode `Content-Encoding` :
   ces deux cas peuvent arriver. Reproduit hors dépôt avec
   `httpx.MockTransport`, sur `[bdpm.specialites, bdpm.presentations]` :
   - `CIS_bdpm.txt` répond `302` vers lui-même → `TooManyRedirects` sort
     d'`executer_passage`, **0 ligne de manifeste** ;
   - `CIS_bdpm.txt` répond `200` avec `Content-Encoding: gzip` et un corps
     qui n'est pas du gzip → `DecodingError`, **0 ligne de manifeste**.

   Le fichier en cause n'a pas de ligne, et les suivants ne sont pas
   téléchargés. C'est bloquant : cela enfreint la décision 6 (« une erreur
   sur un fichier n'arrête pas les autres ») et la décision 5 (« aucun
   passage ne doit manquer, même en erreur »), et contredit la docstring
   de `executer_passage` (« Ne lève pas »). Sur le VPS, une redirection
   mal configurée côté BDPM suffirait à faire perdre des passages entiers
   à chaque heure. Même famille, plus rare : dans `projection_datagouv`
   (`empreintes.py:68`), une ressource qui n'est pas un objet JSON lève
   `AttributeError` et non `AnalyseImpossible`.
   **Attendu** :
   - `telecharger` convertit toute `httpx.HTTPError` en
     `ErreurTelechargement`, avec le type dans le message ; c'est à toi de
     décider si ces erreurs sont relancées ou non ;
   - un filet dans la boucle d'`executer_passage` : toute exception
     inattendue sur une entrée produit une ligne en `erreur` (motif
     `inattendue: <type>: <message>`, journalisée avec sa trace), puis le
     passage continue ;
   - des tests : boucle de redirection et gzip invalide sur un fichier,
     puis 14 lignes, la ligne fautive en `erreur` et les autres en
     `nouveau` ; une ressource data.gouv qui n'est pas un objet donne
     `analyse_impossible`.

2. `src/pharmaflux/collecte/manifeste.py:111` et
   `src/pharmaflux/collecte/passage.py:110` — **le manifeste entier est
   chargé en mémoire à chaque passage, et dépassera `MemoryMax=256M` en
   moins d'un an.** `lire` charge tout le fichier avec `read_bytes()`, le
   découpe, puis le décode en une liste d'`Enregistrement` ; le passage
   n'en tire que les dernières empreintes et les collectes quotidiennes
   du jour. Mesure (Python 3.12, macOS, `ru_maxrss`) : 122 640 lignes
   réalistes de 813 octets (100 Mo de fichier) donnent un **pic de
   394 Mo**. Au rythme réel (12 lignes par heure plus 2 par jour, soit
   environ 290 par jour), le plafond de 256 Mo de l'unité est atteint vers
   80 000 lignes, **soit environ 9 mois après la mise en service (été
   2027)**. À partir de là, chaque passage est tué (`oom-kill`) avant
   d'écrire la moindre ligne : la collecte s'arrête, et le manifeste n'en
   garde aucune trace. C'est bloquant parce que l'arrêt est certain, qu'il
   est silencieux sur un VPS que personne ne surveille, et que l'objectif
   de la mission est une archive qui « se remplit toute seule ». Relever
   le plafond ne ferait que repousser l'échéance.
   **Attendu** :
   - lire le manifeste en flux (ligne à ligne) pour le passage, en ne
     gardant que l'état utile : la dernière empreinte par identifiant et
     les entrées quotidiennes déjà collectées ce jour. La mémoire dépend
     alors du nombre d'entrées du catalogue, plus de l'âge du manifeste ;
   - les règles de C2 restent les mêmes (ligne tronquée marquée ou
     dernière : ignorée ; ailleurs : `ManifesteCorrompu`) ;
   - un test qui le prouve, par exemple un manifeste de quelques dizaines
     de milliers de lignes générées et un pic mémoire borné, ou au minimum
     un test de la fonction en flux. Le chiffre mesuré va dans le
     rapport.

   `etat` peut rester en lecture complète pour cette mission : il ne
   tourne pas sous `MemoryMax`. Note-le dans le rapport pour la mission
   01.

## À corriger (non bloquants)

1. `src/pharmaflux/collecte/etat.py:42-45` — la colonne « dernière
   archive » ne retient que les lignes `nouveau`. Une archive écrite par
   une ligne en `erreur` (`lien_absent`, `analyse_impossible`, que C1
   archive volontairement) n'y apparaît pas. Par ailleurs, `deja_vu`
   repose sur `dernier_statut` : si la première ligne d'un fichier est une
   erreur, son premier `nouveau` compte à tort comme un « changement ».
   Attendu : s'appuyer sur `chemin_archive` dans les deux cas, comme
   `dernieres_empreintes` le fait déjà. Ajouter un test pour chaque cas.
2. `infra/planification/rapatrier.sh:45` — en cas de coupure, `--partial`
   laisse dans la copie du Mac un `.gz` tronqué **sous son nom définitif**.
   Le passage suivant le complète, mais d'ici là, la copie de sauvegarde
   contient une archive invalide qui a l'air bonne. Proposé :
   `--partial-dir=.rsync-partiel`, avec ce dossier exclu de la lecture.
3. `src/pharmaflux/collecte/passage.py:108` et `:220` — si l'écriture du
   manifeste échoue (`OSError`, disque plein), l'exception sort quand même
   d'`executer_passage`. Ce comportement est défendable, puisqu'il n'y a
   plus nulle part où consigner, mais la docstring « Ne lève pas » est
   alors inexacte. La corriger, ou le traiter avec le filet du bloquant 1.

## Remarques

- `src/pharmaflux/collecte/catalogue.py:19` : l'URL du PDF est figée en
  `v5`. Le jour d'une `v6`, il y aura un `HTTP 404 ; lien_absent` par jour
  (visible), mais le nouveau PDF ne sera pas signalé comme `lien_nouveau`,
  puisque ce contrôle filtre sur `.txt`. Le changement d'empreinte de la
  page le révélera quand même. À reprendre à la mission 01 si l'on veut
  le suivre automatiquement.
- `tests/test_passage.py:208-210` : l'assertion « aucun fichier partiel »
  compare deux listes pour dire « aucun fichier ».
  `assert not [p for p in (racine / "bronze").rglob("*") if p.is_file()]`
  se lit d'un coup d'œil.
- `README.md` : le motif du chemin d'archive omet l'extension
  (`…__<sha256>.gz` au lieu de `…__<sha256 12 car.><ext>.gz`).
- Points forts, pour la PR : les fixtures réelles, documentées, avec leurs
  en-têtes ; des tests qui simulent le serveur au lieu de remplacer les
  fonctions par des doublures ; l'écriture par `os.link`, qui rend la
  réécriture impossible et pas seulement interdite ; un `mtime` gzip
  déterministe ; la marque de troncature ; une unité systemd commentée
  directive par directive.
- Garde-fou, pour l'IeC (signalé, non contourné) : deux refus au
  relecteur pendant cette relecture. `git ls-tree --name-only main
  docs/missions/` est refusé (« n'est pas permis au rôle relecteur »)
  alors que c'est une lecture ; le `git show main:docs/missions/` de la
  commande `/relire-mission` en tient lieu. Une boucle
  `for f in docs/relectures/…; do cat "$f"; done` est refusée (« for sur
  un chemin réservé ») ; un `cat` de plusieurs fichiers en tient lieu.
  Aucune gêne réelle.

## Vérifications relancées

Sur `07c77a6`, dans `pharmaflux-relecteur/`, avec un `.venv` neuf :

| commande | résultat |
|---|---|
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 44 files already formatted |
| `uv run mypy src` | Success: no issues found in 11 source files |
| `uv run pytest -q` | 54 passed |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 15 tests, OK |
| `shellcheck infra/planification/*.sh` | non installé sur le Mac : CI seulement (vert au contrôle IeC du palier 3) |
| `git diff --name-only main...HEAD` contre les chemins réservés | aucun fichier réservé à l'IeC modifié |
| `git ls-files` (`data/`, `.env`, `*.gz`, `.DS_Store`) | rien de suivi |
| `git log main..HEAD` : trailers | 11 commits du codeur avec `Commis-par: codeur` et `Co-Authored-By` ; 2 fusions de `main` par beko ; messages en français |
| essai hors dépôt : redirection en boucle, gzip invalide | exception, 0 ligne de manifeste (bloquant 1) |
| essai hors dépôt : `manifeste.lire` sur 122 640 lignes | pic de 394 Mo (bloquant 2) |

Les chiffres concordent avec ceux du rapport du palier 3. Seul écart :
`ruff format` compte ici 44 fichiers, contre 41 dans le rapport. Il est
sans conséquence (tout est formaté), mais je ne l'explique pas : aucun
fichier Python n'a changé depuis le palier 3.

## Alertes

Aucune. Je n'ai trouvé dans le code, les fixtures, les rapports ni les
relectures aucune consigne adressée au relecteur.
