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

## 2026-10-24 — Mission 00, relecture 1 : NON CONFORME, corrigée

Relecture du relecteur sur `07c77a6` (`docs/relectures/mission-00/relecture-1.md`),
deux bloquants reproduits hors dépôt. **Bloquant 1** (`4aef8e4`) :
`TooManyRedirects` et `DecodingError` (dérivés de `RequestError`, pas de
`TransportError`) faisaient sortir l'exception d'`executer_passage`, zéro
ligne de manifeste. `telecharger` convertit toute `httpx.HTTPError`
(définitive sans relance hors transport) ; filet `inattendue: <type>:
<message>` par entrée avec trace ; `projection_datagouv` refuse une
ressource qui n'est pas un objet. **Bloquant 2** (`9cf7710`) : le passage
chargeait tout le manifeste (394 Mo mesurés par le relecteur pour un an,
`MemoryMax=256M` atteint vers l'été 2027). `manifeste.parcourir` (flux,
règles de C2 inchangées) et `etat_connu` (dernière empreinte par
identifiant, collectes du jour) : 18 Mo de `ru_maxrss` pour 122 640 lignes
contre 341 Mo en lecture complète. `etat` reste en lecture complète
(mission 01). **Non bloquants** (`778a8fe`) : `etat` s'appuie sur
`chemin_archive`, `rapatrier.sh` en `--partial-dir=.rsync-partiel`,
docstring d'`executer_passage` exacte, motif du README, assertion
simplifiée. 66 tests. Réponse :
`docs/rapports/mission-00/reponse-relecture-1.md`.

## 2026-10-24 — Mission 00, relecture 2 : CONFORME

Relecture du relecteur sur `1ccc9c0` (`docs/relectures/mission-00/relecture-2.md`) :
les deux bloquants du tour 1 sont levés, aucun point à corriger, cinq
remarques mineures. Fait : `pyproject.toml` ne met plus `-q` dans
`addopts` (avec la commande de `CLAUDE.md`, `-qq` masquait la ligne
`N passed`). Correction de l'entrée précédente : les 122 640 lignes
mesurées représentent environ **14 mois** de manifeste, pas un an ; la
conclusion (plafond atteint vers l'été 2027) ne change pas. Expliqué par
l'IeC et le relecteur : `ruff format` compte aussi les fichiers Markdown,
d'où un nombre qui grandit à chaque rapport. Réponse :
`docs/rapports/mission-00/reponse-relecture-2.md`. `pr.md` attend les
24 h de passages sur le VPS.

## 2026-10-25 — Mission 00 : 24 h de passages, `pr.md`

Relevé de l'IeC le 25/10 à 21:17 UTC : 24 passages planifiés en 24 h sur
les douze entrées horaires, 1 sur les deux quotidiennes, 340 lignes de
manifeste depuis l'installation (trois versions du collecteur : `a8aa07b`,
`07c77a6`, `1ccc9c0`), 0 erreur. Premier changement réel capté :
`CIS_CIP_bdpm.txt` (date source 2026-10-24) et la page, archivés le 24/10 à
23:17Z. Sous l'unité durcie : pic mémoire 43 Mo (plafond 256 Mo), score
d'exposition systemd 6,3. Le critère de clôture de l'ordre est atteint ;
description de la PR : `docs/rapports/mission-00/pr.md` (livré,
vérifications sur `0832dad`, résultat des 24 h, écarts, reports à la
mission 01).

## 2026-10-25 — Mission 00 : CI rouge sur la PR 1, shellcheck

Le shellcheck du runner GitHub (paquet apt, plus ancien que la 0.11.0 du
poste de l'IeC) signale SC2015 sur `rapatrier.sh` (`A && B || C` pris pour
un « si… sinon »). Le script était correct, la ligne est réécrite en `if`.
La CI lance désormais `uvx --from shellcheck-py==0.11.0.1 shellcheck` :
même version qu'en local, le décalage ne peut plus se reproduire. Vérifié
ici avec la même commande : rien à signaler, `sh -n` ok, `usage` rendu
avec le code 2 pour zéro ou trois arguments.

## 2026-10-26 — Mission 01 : §0 tranché, palier 1 (reliquats)

Addendum 1 de l'IeC sur `main` : mes avis du §0 sont retenus (clé
déclarée non unique avec raison, anomalies connues signalées à chaque
profil et jamais masquées, neuf types avec `date` paramétré, ADR 0003
« proposé » revu au plus tard le 07/12/2026, `robots.txt` d'abord pour la
HAS) ; le garde-fou accepte désormais les brouillons du codeur dans le
dossier temporaire de ses propres sessions. Palier 1 : `bronze.py` est la
seule lecture de `bronze/` (ordre chronologique, octets bruts, tout nom
commençant par un point ignoré) ; le collecteur archive même si l'empreinte
de comparaison lève une exception imprévue, consigne les liens nouveaux
sous le filet, et prend l'URL de la documentation PDF dans la page (un
`_v6.pdf` est archivé sous son nom et signalé `lien_change`) ; journal en
UTC ; `etat` lit le manifeste en flux, affiche l'identifiant et les
fichiers `.partiel-*` orphelins ; unité systemd durcie (capacités vides,
filtre d'appels système, `UMask=0027` pour garder la lecture du groupe),
score visé sous 3, mesuré par beko sur le VPS depuis la branche. 80 tests.
Rapport : `docs/rapports/mission-01/palier-1.md`.

## 2026-10-26 — Mission 01 : contrôle du palier 1, correctif C1, palier 2 (contrats)

Palier 1 accepté par l'IeC ; l'unité durcie est mesurée par beko sur le VPS
à 1,3 au score d'exposition (6,3 avant), passage manuel sans erreur,
`MemoryDenyWriteExecute` conservé. Le VPS tourne sur la branche de mission
jusqu'à la fusion. **C1** : une entrée quotidienne archivée sous
`lien_change` ou `lien_absent` était retéléchargée à chaque passage ; les
motifs d'erreur sont maintenant définis une seule fois dans `manifeste`
(`MOTIFS_SIGNALEMENT`, liste fermée) et `Enregistrement.vaut_collecte` dit
ce qu'une ligne vaut. **Palier 2** : onze contrats TOML v0 dans
`src/pharmaflux/contrats/bdpm/` (encodage, fin de ligne, colonnes typées
parmi neuf types, clé avec `unique` et `raison`, liens, source avec sha256
du PDF et archive de référence), chargeur strict (`tomllib`, toute clé
inconnue refusée), vérification d'une archive en anomalies jamais
corrigées (quatre règles bloquantes : encodage, fin de ligne, nombre de
colonnes, clé déclarée unique). Les onze archives du 24/10 passent sans
anomalie bloquante ; les constats du §0 ressortent tels quels (17 016
espaces parasites dans `CIS_bdpm.txt`, 995 prix à virgule des milliers, 52
dates hors plage, 5 lignes en doublon dans Dispo_Spec). Fixtures étendues
de lignes réelles choisies, anomalies fabriquées à part dans
`tests/fixtures/contrats/`. 190 tests. Rapport :
`docs/rapports/mission-01/palier-2.md`.

## 2026-10-26 — Mission 01 : palier 3 (profil, docs/donnees, ADR 0001 à 0004)

Palier 2 accepté sans correctif ; l'IeC et le codeur se parlent désormais
directement pour la routine (messages d'une ligne entre sessions), beko
gardant push, PR, fusion, VPS et toute décision hors de l'ordre. Palier 3 :
`pharmaflux profil` mesure n'importe quelle archive contre son contrat
(conformité groupée par règle avec `valeur_inconnue` en tête, clé,
colonnes, répartitions, bornes, ordre des dates, liens) et écrit un
Markdown par source ; `docs/donnees/` contient les onze profils de
l'archive du 24/10 (0 anomalie bloquante) et un README qui ouvre sur le
constat que `CIS_bdpm.txt` n'est pas le référentiel de tous les CIS. ADR
0001 (collecte horaire sur le VPS-1, consignée), 0002 (contrats TOML, neuf
types, bornes hautes relevées par nouvelle version), 0003 (disponibilité,
« proposé », revue au plus tard le 07/12/2026 avec critère de passage) et
0004 (corpus HAS : pages d'avis d'abord, PDF en second). Les cinq requêtes
HAS permises ont été faites : `robots.txt` n'interdit pas les pages
d'avis, le document d'avis est servi derrière une redirection de mesure
d'audience (non suivie), les mentions légales autorisent la réutilisation
avec source et date. 198 tests.

## 2026-10-26 — Mission 01 : palier 4 (questions de référence)

Palier 3 accepté sans correctif (profils régénérés identiques à
`docs/donnees/`, ADR 0004 validé). Palier 4 : `evaluation/questions-reference-v0.toml`,
quarante questions, cinq par catégorie de l'annexe B du PRD, chacune avec
son comportement attendu (réponse, abstention, refus médical) et, pour une
réponse, l'archive du 24/10 (chemin et sha256), le contrat, la clé, les
colonnes et les lignes attendues, brutes. Deux questions visent un CIS
absent de `CIS_bdpm.txt` (abstention motivée) ; une seule question
Historique porte un début futur, voulu, pour tester la prudence. Les
questions Dépense attendent Open Medic (`calculable_au = "lot4"`).
`uv run pharmaflux questions verifier` relit chaque archive citée, vérifie
son sha256 et son contrat, recalcule les lignes et signale tout écart :
25 conformes, 5 non calculables, 10 sans attendu sur la copie du Mac. La
lecture stricte des TOML est partagée (`tomlstrict.py`) entre contrats et
questions. Docs : `CONTEXTE.md` (contrats, bronze, « on constate, on ne
corrige pas »), `README.md`. 229 tests.

## 2026-10-26 — Mission 01 : relecture 1 CONFORME, quatre correctifs

Relecture à contexte neuf sur `7c5d10e` : CONFORME, aucun bloquant, quatre
points non bloquants, tous corrigés par un commit chacun. Les bornes
numériques du profil ne prennent plus que des valeurs conformes au type
(`Decimal()` lisait « NaN », qui faisait planter le tri, et « 1e9 ») ; le
type `decimal` exige des chiffres ASCII après la virgule comme avant ;
l'archive citée par une question doit être dans le dossier bronze du
contrat qu'elle nomme, en cinq segments exacts (`Contrat.dossier_bronze`),
et le cache du rejeu est indexé par (archive, contrat) ; le test des règles
bloquantes importe ce qu'il teste. Remarques : aide de `--questions`
(chemin relatif au dossier courant), ADR 0002 (une ligne de blancs est une
ligne vide, voulu), §0 (le script jetable cité est remplacé par
`pharmaflux profil`). `docs/donnees/` régénéré identique ; 237 tests.
Réponse : `docs/rapports/mission-01/reponse-relecture-1.md`.
