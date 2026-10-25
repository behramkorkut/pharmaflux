# Mission 00 — socle du dépôt et archivage horaire des sources

Branche `mission-00-socle-et-archivage`, 21 commits depuis `main` (dont deux fusions de `main`), du §0
(`fdd550e`) à la réponse à la relecture 2 (`0832dad`). Ordre de mission :
`docs/missions/mission-00-socle-et-archivage.md` (addenda 1 et 2).
Relecture 2 : **CONFORME**, 0 bloquant (`docs/relectures/mission-00/relecture-2.md`).

## Ce qui est livré

**Socle** (palier 1, `474b608`) : `pyproject.toml` (Python 3.12, `uv`,
`httpx`, `typer` ; ruff, mypy strict, pytest en dev), `uv.lock`,
`.gitignore` (`data/`, `.venv/`, caches, réglages locaux), CI GitHub
Actions (ruff, mypy, pytest, shellcheck, tests des garde-fous), `README.md`,
`docs/CONTEXTE.md`, `docs/adr/0000-modele.md`, `docs/journal.md`.

**Collecteur** (palier 2, `91f4c62`), `uv run pharmaflux collecte` :

- catalogue de 14 entrées : la page de téléchargement de la BDPM et ses
  onze fichiers `.txt` à chaque passage, le jeu Open Medic de data.gouv et
  la documentation PDF des formats une fois par jour ;
- archive bronze immuable, compressée, sous
  `bronze/<source>/<fichier>/<AAAA-MM-JJ>/<horodatage>__<sha256, 12 car.>.<ext>.gz`,
  écrite dans un fichier temporaire (`.<nom>.partiel-<pid>`, `fsync`) puis
  publiée par **lien dur** (`os.link`), qui échoue si le nom existe déjà :
  jamais de fichier partiel visible, et une réécriture est impossible, pas
  seulement interdite ;
- empreinte de comparaison par fichier (octets, ou projection de la page
  et du JSON data.gouv) : un contenu identique n'est pas réarchivé, un
  `304` est consigné sans téléchargement ;
- manifeste `manifeste/collecte.jsonl` en ajout seul (`fsync`), une ligne
  par tentative, statuts `nouveau` / `inchange` / `non_modifie_304` /
  `erreur`, motifs enchaînés (`HTTP 404 ; lien_absent`), version du
  collecteur `0.1.0+<commit>` ; une ligne coupée par une panne est marquée
  et ignorée, une ligne illisible au milieu arrête la lecture
  (`ManifesteCorrompu`) ;
- téléchargement avec trois essais sur erreur de transport ; une erreur
  HTTP 4xx, une redirection en boucle ou un corps indécodable sont
  définitifs ; toute exception imprévue sur une entrée finit dans le
  manifeste (`inattendue: …`) et le passage continue ;
- `uv run pharmaflux etat` : tableau par fichier (dernière archive,
  dernier changement, date source, passages des 24 h, dernière erreur).

**Planification** (palier 3, `891efb6`, durcie en `a8aa07b` et `07c77a6`),
`infra/planification/` : unité systemd `oneshot` sous un compte dédié,
minuteur horaire (`*:17`), `ProtectHome=tmpfs` avec les trois seuls chemins
nécessaires, `MemoryMax=256M`, `CPUQuota=50%`, entrées-sorties en priorité
basse ; `rapatrier.sh` (rsync par SSH, sans `--delete`, morceaux de
transfert dans `.rsync-partiel/`) ; `README.md` d'installation sans `cd`,
chemins absolus, mise à jour, rapatriement, désinstallation, sécurité d'un
VPS partagé.

**Tests** : 66, sur fixtures (`tests/fixtures/`, extraits réels datés du
24/10/2026), serveur simulé par `httpx.MockTransport`, aucun appel réseau.
Couverts : premier passage, inchangé, `304`, erreur réseau puis succès,
erreur définitive, archive déjà existante, écriture interrompue, manifeste
tronqué ou corrompu, lien absent ou nouveau sur la page, pannes httpx hors
transport, filet par entrée, lecture du manifeste en flux à mémoire bornée
(30 000 lignes, pic sous 4 Mio).

**Documents** : `docs/rapports/mission-00/` (points à trancher, trois
rapports de palier, correctif de l'unité, deux réponses de relecture),
`docs/relectures/mission-00/` (trois contrôles de l'IeC, une consigne,
deux relectures, commités tels quels), journal à jour.

## Vérifications locales (commit testé : `0832dad`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 48 files already formatted |
| `uv run mypy src` | Success: no issues found in 11 source files |
| `uv run pytest -q 2>&1 \| tail -25` | 66 passed in 4.63s |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK |
| `shellcheck infra/planification/*.sh` | non installé sur le Mac : CI seulement ; `sh -n` ok |

Le compte de `ruff format` inclut les blocs Python des fichiers Markdown ;
il grandit avec chaque rapport.

## Résultat des 24 h de passages sur le VPS

Relevé par l'IeC avec `pharmaflux etat` le 25/10/2026 à 21:17 UTC, sous
l'unité durcie :

| mesure | valeur |
|---|---|
| passages planifiés en 24 h | 24, sur les douze entrées horaires ; 1 sur les deux quotidiennes |
| lignes de manifeste depuis l'installation | 340 (14 en `a8aa07b`, 24 en `07c77a6`, 302 en `1ccc9c0`) |
| erreurs | 0 |
| premier changement réel capté | `CIS_CIP_bdpm.txt` (date source 2026-10-24) et la page, archivés le 24/10 à 23:17Z ; les autres fichiers inchangés |
| pic mémoire | 43 Mo, pour un plafond de 256 Mo |
| score d'exposition `systemd-analyze security` | 6,3 |

Les trois versions du manifeste correspondent aux mises à jour successives
du VPS par beko (étape 7 du README) pendant la relecture. Le critère de
clôture de l'ordre (au moins 24 h de passages planifiés visibles dans
`etat`) est atteint.

## Écarts à l'ordre et interprétations

Tous consignés dans les rapports de palier et acceptés par les contrôles :

1. `typer` plutôt qu'`argparse`. Les fichiers de l'IeC (`.claude/`,
   `infra/agents/`) suivent la configuration ruff du projet : l'exclusion
   posée au palier 1 a été retirée au palier 2, à la demande du contrôle.
2. Quatorzième entrée du catalogue : la documentation PDF des formats,
   douzième lien de la page, quotidienne ; URL figée en `v5`.
3. `lien_absent` : le fichier est quand même archivé s'il est nouveau, la
   ligne est en `erreur` pour alerter. Une entrée quotidienne déjà
   collectée le jour même n'écrit pas de ligne « différé ».
4. Manifeste : champ `identifiant`, `chemin_archive` relatif à la racine,
   marque de troncature en fin d'une ligne coupée (interprétation de C2,
   acceptée).
5. `ExecStart` appelle `.venv/bin/pharmaflux` directement ; `uv sync
   --frozen --no-dev` sur le VPS. Un passage avec une entrée en erreur
   sort en code 1 : l'unité passe en `failed`, le minuteur relance.
6. Une `OSError` à l'écriture du manifeste sort du passage (plus rien où
   consigner) ; une erreur httpx hors transport n'est pas relancée.
7. Les unités n'ont pas été exécutées sur le Mac ; elles le sont sur le
   VPS depuis le 24/10, voir ci-dessus.
8. Depuis la création de la branche, `main` a reçu deux lignes dans `.claude/hooks/garde_fou.py`
   et `infra/agents/test_garde_fou.py` (`git ls-tree` et `git check-ignore`
   permis) : la branche ne les touche pas, la fusion les conserve.

## Reporté à la mission 01 (accepté par l'IeC ou le relecteur)

- `etat` : lecture du manifeste en flux (le passage l'est déjà, `etat`
  fait encore une lecture complète), affichage de l'identifiant du
  catalogue, signalement des `.partiel-*` orphelins, exclusion des
  dossiers `.rsync-partiel/` de toute lecture de `bronze/`.
- Journal `logging` en UTC (au prochain passage dans `cli.py`).
- URL du PDF : la prendre dans la page plutôt que la figer en `v5`.
- `passage.py` : lignes `lien_nouveau` sous le filet ; archiver même si
  l'empreinte de comparaison lève autre chose qu'`AnalyseImpossible`.
- Unité : viser un score d'exposition sous 3 (`SystemCallFilter`,
  `CapabilityBoundingSet=`, `RestrictNamespaces`…) ; alerte sur échec
  (`OnFailure=`).

Hors périmètre, inchangé : profilage, contrats de schéma, ADR du PRD
§10.2, jeu de questions (mission 01) ; CSV Open Medic, Redpanda, Docker,
API Claude (lots suivants).
