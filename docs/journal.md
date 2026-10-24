# Journal du projet

Une entrée par étape marquante, en fin de fichier. Les chiffres cités sont
mesurés ; la commande ou le rapport qui les produit est indiqué.

## 2026-10-23 — Cadrage

PRD v0.1 rédigé (`01_Specifications/`). Deux axes : transformer des
publications d'état en flux d'événements rejouable ; une IA gouvernée qui
cite et s'abstient. Lot 0 découpé en deux missions : archivage d'abord
(mission 00), profilage ensuite (mission 01).

## 2026-10-24 — Mission 00, §0 : les sources telles qu'elles sont

Treize requêtes HTTP, une par URL (`docs/rapports/mission-00/points-a-trancher.md`) :

- un passage complet BDPM = 11 fichiers, 28,7 Mo bruts, 3,7 Mo gzip ; si
  tout changeait chaque jour, 1,3 Go par an compressés ;
- aucun validateur HTTP (`Last-Modified`, `ETag`, `Content-Length`) sur
  les téléchargements : pas de requête conditionnelle possible ;
- la page de téléchargement affiche une date et une taille par fichier,
  dans le même élément HTML que le lien ;
- `CIS_InfoImportantes.txt` est généré à la demande, non trié ; les
  métadonnées Open Medic de data.gouv portent des dates de robot.

Tranché (addendum 2) : collecte horaire à `:17` sur le VPS de beko
(systemd), copie hebdomadaire sur le Mac ; empreinte de comparaison par
entrée du catalogue ; métadonnées Open Medic une fois par jour.

## 2026-10-24 — Mission 00, palier 1 : socle

`pyproject.toml` (uv, httpx, typer, ruff, mypy strict, pytest), squelette
`src/pharmaflux/`, CLI déclarée (`collecte`, `etat`, `--version`), CI en
un job, `.gitignore`, README, `docs/CONTEXTE.md`, gabarit d'ADR. Le
collecteur arrive au palier 2.

## 2026-10-24 — Mission 00, palier 2 : collecteur

Catalogue déclaratif (13 entrées), téléchargement httpx (60 s, trois
essais, `User-Agent` du projet), archive bronze immuable (temporaire puis
`os.link`, jamais de réécriture), manifeste JSONL en ajout seul, `collecte`
et `etat` réels. 45 tests sans réseau sur des extraits réels
(`tests/fixtures/`). Seconde requête autorisée sur
`CIS_InfoImportantes.txt` : fichier identique à l'octet près 76 min plus
tard, l'ordre des lignes n'a pas bougé. Découverte : la page offre un
douzième lien, la documentation PDF du format (v5).

## 2026-10-24 — Mission 00, correctifs du contrôle du palier 2

C1 : une ligne qui a écrit une archive laisse toujours son empreinte
connue, quel que soit son statut ; `analyse_impossible` compare sur les
octets ; `lien_absent` s'ajoute à l'erreur existante (`HTTP 404 ;
lien_absent`) au lieu de l'écraser. Sans cela, un lien disparu ou une page
illisible aurait réarchivé le même contenu 24 fois par jour. C2 : une
dernière ligne tronquée du manifeste (coupure pendant l'écriture) est
ignorée avec un avertissement, `ajouter` repart sur une ligne propre ; une
ligne illisible au milieu reste une erreur franche. Quatorzième entrée du
catalogue : la documentation PDF du format BDPM, quotidienne, empreinte
octets (une requête réelle pour la fixture, 4 Ko conservés).

## 2026-10-24 — Mission 00, palier 3 : planification et premier passage réel

`infra/planification/` : `pharmaflux-collecte.service` (oneshot durci,
compte `pharmaflux`, `PHARMAFLUX_DATA` dans l'unité) et `.timer`
(`*-*-* *:17:00`, `Persistent=true`), `rapatrier.sh` (Mac ← VPS, rsync en
tirage, jamais `--delete`), procédure complète pour beko dans le README du
dossier. **Un passage réel sur le Mac** (18:27:36 UTC, racine temporaire
hors dépôt) : 14 requêtes, 14 `nouveau`, 0 erreur, **30 s** de bout en bout
(pause de 2 s comprise entre entrées), 29,1 Mo bruts, 3,7 Mo archivés
(gzip), 14 lignes de manifeste, aucun fichier partiel. Troisième
observation de `CIS_InfoImportantes.txt` (5 h après la première) : toujours
le même sha256 `a27b30e12c83…`. Dates affichées par la page ce jour :
`CIS_CIP_bdpm.txt` 23/10, `CIS_CIP_Dispo_Spec.txt` 21/10, `CIS_MITM.txt`
13/10, les autres 29/09.

## 2026-10-24 — Mission 00, correctifs du contrôle du palier 3

Contrôle de l'IeC (`docs/relectures/mission-00/controle-palier-3.md`) :
correctifs C1/C2 et marque de troncature acceptés, palier 3 accepté sous
réserve de P1. **P1** : la procédure échouait à l'étape 4, `cd
/home/pharmaflux/pharmaflux` étant lancé par le compte SSH de beko avant
son entrée dans le groupe `pharmaflux` (répertoire en `750` ou `700`).
`infra/planification/README.md` réécrit sans aucun `cd` : chemins absolus
partout, `uv sync --directory`, `git -C … pull --ff-only`, `install` avec
les chemins complets ; ajout au groupe et `chmod 750` remontés à l'étape 2
avec la reconnexion SSH. Ajouté : clonage depuis la branche de mission
(`git clone --branch mission-00-socle-et-archivage`), puis retour sur
`main` après la fusion (`git -C … switch main`, `pull --ff-only`, `uv
sync`). Remarques mineures prises : `--shell /usr/sbin/nologin` (et
`UV_NO_MODIFY_PATH=1` à l'installation d'`uv`), version d'`uv` figée dans
l'URL (`0.10.10`, celle du Mac). Propositions (a), (b), (c) acceptées pour
la mission 01 ou le prochain passage dans `cli.py`. `pr.md` attend les
24 h de passages sur le VPS.

## 2026-10-24 — Mission 00, durcissement de l'unité pour un VPS partagé

Consigne de l'IeC (`docs/relectures/mission-00/consigne-unite-vps.md`) :
le VPS héberge aussi une autre application jusqu'à mi-novembre ; premier
passage réel sur le VPS conforme (14 `nouveau`, 29 s, 2,35 s de CPU, pic
mémoire 46,9 Mo). `pharmaflux-collecte.service` : `ProtectHome=tmpfs`,
`BindReadOnlyPaths` sur le dépôt et le Python d'`uv`, `BindPaths` sur
l'archive (trois chemins visibles dans `/home`), `MemoryMax=256M`,
`CPUQuota=50%`, `IOSchedulingClass=idle`, `Nice=10` conservé. Vérifié dans
`src/` que rien d'autre n'est lu sous `/home` (racine par variable,
`git rev-parse` dans le dépôt, certificats `certifi` dans `.venv`).
README : `readlink -f` du Python, `Mem peak` et score
`systemd-analyze security`, chemin du manifeste et versions distinctes,
séquence de mise à jour d'une unité, rubrique « VPS partagé ». Rapport :
`docs/rapports/mission-00/correctif-unite.md`.
