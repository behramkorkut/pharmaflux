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

## 2026-10-26 — Mission 02 : normalisation et événements (paliers 1 à 3)

Branche `mission-02-normalisation-et-evenements`. §0 répondu sur mesures
(archive du Mac en lecture seule, aucune requête réseau), tranché par
l'addendum 1. **Palier 1** : `contrats/normalisation.py` (forme canonique par
type, en chaînes ; lisibilité → brute, forme ou vraisemblance → canonique),
`presentations.toml` v1 (`milliers = ","` sur les prix, lecture vérifiée par
prix public = prix + honoraires sur 13 620 lignes sur 13 623 ; `canonique`
des taux), chargeur v0/v1, `fichier_vide` non bloquante, compte des lignes
touchées par un octet illisible, `evenements/snapshot.py` (lignes figées
partageant les tuples de la lecture, à clé ou multiensemble, bilan, écarté
avec motif), ADR 0005 ; `decimal_illisible` 995 → 0 sur `CIS_CIP_bdpm.txt`,
seule différence de non-régression. Contrôle : signe de `-0,50`, chiffres
ASCII des milliers, clé normalisée ambiguë → écarté. **Palier 2** :
`schema.py` (événement v1 tout en chaînes, identifiant sha256 sur les chemins
relatifs des deux archives, JSON stable relu), `comparaison.py` (à clé et
ligne à ligne avec rangs, tri déterministe, `appliquer`), `volume.py`
(seuil 1 %, vide et bloquant écartés sans appel, attente confirmée par un
passage inchangé ou l'archive suivante), `bilan.py`, six archives
fabriquées. Contrôle : rien ne dépend de l'ordre d'un objet JSON (ordre
alphabétique des colonnes), `deserialiser` strict. **Palier 3** :
`rejeu.py` et `pharmaflux evenements [--fichier] [--racine] [--sortie]
[--reprendre]`, sortie par archive écrite atomiquement (événements, bilan,
état), reprise depuis les archives (snapshots jamais sérialisés), bilan
d'une archive en attente réécrit quand elle est tranchée, `--reprendre`
refusé après un changement de version de contrat ; tests : deux rejeux
identiques à l'octet, reprise après chacun des treize points d'arrêt,
`etat.json` supprimé, aucun identifiant en double, `appliquer` sur la sortie
relue du disque. Démonstration sur la copie du Mac : 164 096 `creee`
initiales (172 Mo), 3 `supprimee` réelles de `CIS_CIP_bdpm.txt` (arrêts de
commercialisation), le vide du 26/10 à 14:17 écarté et le 15:17 identique
au 24/10 (zéro événement), 995 prix lus grâce à `milliers`, 7,9 s, 474 Mo
de mémoire résidente ; `--reprendre` ensuite : 0 archive, 2,9 s. ADR 0006,
`CONTEXTE.md`, `README.md`. 399 tests.

**Relecture 1** (26/10) : deux bloquants corrigés. La dernière archive
traitée de l'état suit désormais chaque verdict définitif, et non le seul
dernier résultat : une archive en attente tranchée par une archive
elle-même en attente ne reste plus en arrière, ce qui faisait relire et
effacer ses événements à `--reprendre`. Les `supprimee` d'une même ligne
sortent du rang le plus haut au plus bas, pour qu'un consommateur qui suit
le flux, comme `appliquer`, voie un compte toujours juste quand une ligne
perd plusieurs occurrences. `deserialiser` exige de vraies listes. La suite
des tests de reprise passe à vingt-deux archives (deux pertes en attente
qui se suivent, dans les deux sens ; une ligne en triple ramenée à une puis
remontée à trois). Sur la copie du Mac, la sortie est identique à l'octet
à celle du palier 3. 413 tests.

**Relecture 2** (26/10) : **CONFORME**, 0 bloquant. Un point non bloquant,
les trois fixtures ajoutées à la relecture 1 signalées dans
`tests/fixtures/README.md`. Le relecteur signale deux refus du garde-fou
(une sonde dans son dossier temporaire, un `cmp` sur `docs/relectures/`)
et propose à l'IeC d'autoriser le dossier temporaire au relecteur.
`docs/rapports/mission-02/pr.md` écrit. Fin de la mission 02 : 413 tests,
21 commits depuis `main`.

## 2026-10-27 — Mission 03 : bus d'événements (paliers 1 à 3)

Branche `mission-03-bus-d-evenements`. §0 répondu sur mesures (rejeu de la
copie du Mac : 474 Mo résidents, la sérialisation des 32 439 `creee` de
`compositions` en cause), tranché par l'addendum 1 (cible 160 Mo,
`confluent-kafka` seule dépendance de production, valeur nue, `schema_id` en
en-tête, `BACKWARD_TRANSITIVE`, topics `pharmaflux.<entite>.v1` à trois
partitions, rétention posée par le projet et vérifiée, codes 1/2/3, pas de
topic des bilans, double référence, projet `pharmaflux` sur un colima partagé,
CI par le fichier compose). **Palier 1** : écriture en flux (`comparer` rend
un itérateur, un seul snapshot retenu vivant par entité, valeurs répétées
partagées et comparées avec `==`), 118 à 143 Mo contre 474, sortie identique
à l'octet, test `tracemalloc` en ratio, ADR 0006 mis à jour. **Palier 2** :
fichier compose (Redpanda v26.2.6, console v3.13.1 sous profil, ports
127.0.0.1, `dev-container` 768 Mo), paquet `pharmaflux.bus` (enveloppe, client
idempotent, registre, publication avec état écrit après l'accusé, file des
échecs), schémas draft-07 épinglés, `publier`, `schemas enregistrer`,
ADR 0007. Trois correctifs du contrôle : création automatique des topics
coupée par un `.bootstrap.yaml` du bloc `configs` (rpk n'a plus `--set` en
v26.2 ; `down -v` pour l'appliquer), topic pris du dossier, sha256 des octets
publiés. **Palier 3** : `verifier-bus` (relecture sans commit, fin par les
offsets, dédoublonnage par `id`, états réduits en empreintes, référence
fichiers ou `--racine`, rétention, politique, horodatage et partitions
vérifiés), tests de coupure pendant chacun des trois fichiers puis
`--reprendre` (doublons du seul fichier republié, copies exactes), job CI
`integration` par le compose du dépôt, CONTEXTE, README. Démonstration sur la
copie du Mac : rejeu 8,3 s et 134 Mo, `diff -r` identique ; `publier`
164 099 messages sur onze topics en 29,8 s et 59 Mo ; `verifier-bus`
conforme, 0 doublon, 11 s et 189 Mo (219 avec `--racine`) ; clôture :
`evenements --reprendre` 0 archive, `publier --reprendre` 0 fichier,
`verifier-bus` conforme. 444 tests, dont 6 d'intégration. Deux faux positifs
du garde-fou signalés et affinés sur `main` (un argument qui contenait le nom
du moteur de conteneurs, un `find` sur un chemin réservé).

Relecture 1 (sur `d4db1de`) : CONFORME, 0 bloquant ; trois points non
bloquants corrigés en `57b9be6` (saut d'intégration en échec en CI, courtier
vérifié au départ de `publier`, ADR 0006). Critère de clôture rejoué sur la
copie du Mac : 0 archive, 0 fichier, 12 topics conformes. 446 tests.
`pr.md` écrit, publication à beko.

## 2026-10-27 — Mission 04 : rejeu accéléré et démo (paliers 1 à 3)

Ordre : un jeu de démo figé dans le dépôt, `make demo` qui rejoue la chaîne
en accéléré sur une donnée réelle, les reliquats de la mission 03. §0
(`ab31fd3`) tranché par l'addendum 1 : coupure au passage `20261027T151708Z`
inclus, facteur 1 000, passages affichés, `demo` dépend de `up`, `suivre`
minimal, journal de `evenements` sur stderr, deux mesures de mémoire,
prérequis par `config --images`, clôture sur clone neuf (ou refus puis
`make rebatir` sur une machine qui a déjà le volume). **Palier 1**
(`642998b`) : `pharmaflux demo fabriquer` / `verifier` (`demo/jeu.py`,
`manifeste.parcourir_brut`), `demo/archive` (22 archives, 11 entités, 781
lignes, 71 passages, 6,7 Mo, exception `.gitignore`), `demo/README.md` et sa
table des sha256 relue par `test_demo.py` ; reliquats F.1 (tri numérique de
l'historique), F.2 (`SchemaIncompatible` avant d'enregistrer), F.3 (refus
hors d'ordre avant le premier message), fichier d'événements vide publié et
compté. **Palier 2** (`aa079da`) : `pharmaflux demo rejouer`
(`demo/rejeu_accelere.py` : état du bus jugé avant tout, ordre global par
(horodatage, entité), passages sans archive, horloge sans pause négative,
reprise), `publication` découpée en `preparer` et `publier_fichier`,
`pharmaflux suivre` (`bus/suivi.py`, topic absent attendu), tests unitaires
sur bus simulé (ordre global sur trois entités et sept archives, cadence
sans dormir, refus, reprise, hors d'ordre), trois tests d'intégration dont
F.2 contre le vrai registre ; fixtures d'intégration dans `conftest.py`.
Démonstration sur bus rebâti : 164 106 messages en 4 min 03 s, 145 Mo
résidents, `verifier-bus` conforme sur les deux références, relance
refusée. `tracemalloc` par entité de 0,7 à 35,8 Mo. **Palier 3** :
`Makefile` (GNU Make 3.81 : `up`, `demo`, `verifier`, `suivre`, `console`,
`down`, `rebatir`, `verifications`, `help`), `infra/demo/prerequis.sh`
(Docker, Compose, images des seuls services lancés, `uv`), étape CI `make
demo DEMO_OPTIONS=--sans-pause`, ADR 0008, README « Démo », CONTEXTE. Deux
refus du garde-fou signalés sans variante : `git count-objects -vH` (beko
mesure : 6,68 Mio en vrac, pack de 836 Kio avant le jeu) et
`make --version` (seul `make -n` est permis).

**Clôture de la mission 04** (27/10). Contrôle 3 : seuls les topics
exacts de la démo font refuser `demo rejouer` (les topics des tests
d'intégration ne comptent plus) ; « dix présentations supprimées, en trois
fois (2, 1, 7) » dans le README et l'ADR 0008 (`7c9e6a8`). Démonstration
de beko sur le Mac, après `make rebatir` : `make demo` 164 106 messages,
4 min 03 s, `verifier-bus` 12/12 conforme, code 0. Relecture 1 CONFORME,
0 bloquant : `prerequis.sh` refuse proprement si `config --images`
échoue, entrée de passage à arguments nommés, test de `suivre` relu
(`cd7810e`) ; un refus du garde-fou de plus, `chmod +x` sur une cale de
test, signalé. `pr.md` écrit ; revue finale de l'IeC, puis publication
par beko.

**Contrôle final de la mission 04** (27/10, `controle-iec-final.md` sur
`513a226`) : fusion autorisée, code non repris, trois corrections de
rédaction dans `pr.md` (la démonstration de beko a suivi `make rebatir`,
le refus ayant été montré au palier 3 ; `git count-objects` et
`make --version` sont déjà permis sur `main`, `714b673` et `9ad4b14`).
Publication par beko ensuite.

**Premier passage de la CI de la mission 04** (27/10) : `integration`
vert, `verifier` rouge sur `test_commandes_demo_fabriquer_et_verifier`.
Typer affiche une erreur d'option dans un cadre Rich de 80 colonnes, en
couleur sur le runner, et la coupure de ligne dépend de la longueur du
chemin dans le message : « pas un dossier vide » était coupé sur le runner,
pas sur le Mac. Correctif dans les tests seuls : `texte_nu` (codes ANSI,
cadre, blancs) devant toute assertion sur le texte d'une erreur à code 2 ;
suite complète avec `GITHUB_ACTIONS=true` et balayage de la longueur du
dossier temporaire de 0 à 60, verts.

**Mission 05, correspondance des hashes de `main`** (28/10). Après la
fusion de la mission 04 (PR #5, `1af4ef9`), les trois commits suivants de
`main` ont été réécrits par un rebase : `aceb5ba` → `38589dc` (addendum 1
de la mission 04), `714b673` → `5167314` (`git count-objects` permis en
lecture à tous les rôles), `9ad4b14` → `5c3fe5a` (`make --version`, seul,
permis). Les documents de la mission 04 citent les anciens.

**Mission 05, §0 et palier 1** (28/10). Ordre : le silver (Lot 2, PRD
v0.6 §6.5), une table Iceberg par entité, versions SCD2 sur la date
d'observation, « état à une date », vérification contre l'archive, puis un
consommateur du bus (palier 2) et `make silver` (palier 3). §0 (`7103e8b`) :
mesures sur une maquette hors dépôt (PyIceberg 0.12.0, PyArrow 26.0.0,
DuckDB 1.5.6, catalogue SQL sur SQLite) ; silver du jeu en 6,5 s, 18/18
conforme, mémoire de 276 à 610 Mo selon l'allocateur d'Arrow ; la copie du
Mac est le jeu de démo. Addendum 1 (`b5b9420`) : contraintes de versions
(`constraint-dependencies`) au lieu d'un `exclude-newer` global, `silver
sql` en lecture seule verrouillée ou rien, `pyarrow-stubs`, identité en clé
JSON, anomalies en liste de structures, lots de 10 000, seuil d'alerte
512 Mo, le silver ne vise pas le VPS en v1. **Palier 1** : paquet
`pharmaflux.silver` (`entrepot`, `schema`, `expressions`, `application`,
`construction`, `etat`, `sql`, `comparaison`, `verification`) et les
commandes `silver construire`, `etat`, `sql`, `comparer`, `verifier` ;
imports paresseux (testés), allocateur système d'Arrow posé avant le
premier import de PyArrow ; DuckDB sans aucun accès fichier (jeux Arrow,
`enable_external_access = false`, verrou, `SELECT` seul) après qu'un
`COPY … TO` dans le dossier autorisé a passé sur la maquette ; 24 paquets
ajoutés au verrou, tous publiés au 14/10/2026 ou avant, aucun paquet
existant changé ; 490 tests (20 nouveaux). Sur le jeu : `construire` 9,7 s
et 297 Mo, `verifier` 22/22 conforme en 10,2 s et 342 Mo, `etat` 182 Mo,
`sql` 173 Mo, `comparer` 432 Mo.

**Mission 05, palier 2** (28/10). Le consommateur du bus :
`pharmaflux silver consommer` lit chaque topic depuis la position gardée
dans les propriétés de sa table (`pharmaflux.positions` : par partition,
l'offset suivant et l'`id` du dernier message appliqué), toutes les
partitions à la fois, jusqu'aux offsets de fin lus au départ ; un commit
Iceberg par lot, qui porte la position (aucune fenêtre entre le silver et
sa position), la plage d'offsets dans le résumé du snapshot ; doublons
reconnus à l'`id`. Refus : silver des fichiers, position hors des bornes,
message à `offset − 1` qui ne porte pas l'`id` gardé (bus rebâti
autrement), autre version de contrat, message qui n'est pas du v1 (jamais
sauté), bus vide ; identifiant de grappe différent = avertissement.
`LecteurKafka` gagne `identifiant_grappe`, `bornes`, `derniers_messages`
(consommateur dédié, `fetch.wait.max.ms` 50 : la relecture d'un message en
fin de partition coûtait une seconde avec le consommateur de `lire`),
`lire_depuis`. Tests sur un bus simulé à trois partitions réparties par la
clé : égalité avec le silver des fichiers et avec l'archive, reprise après
publication en deux fois et après doublons, coupures pendant la lecture, entre
le `metadata.json` et SQLite (cale sur `SqlCatalog._write_metadata`,
PyIceberg 0.12.0) et après le commit, refus, commande ; deux tests
d'intégration sur le courtier. Démonstration sur le bus de la démo du Mac
(grappe `redpanda.990d5d4e-…`) : 164 106 messages en 12,9 s et 357 Mo,
`comparer` identique au silver des fichiers, `verifier` 22/22 conforme ;
seconde exécution 0,3 s, rien de nouveau. 498 tests.

**Mission 05, palier 3** (28/10). `make silver` (après `make demo` :
`silver consommer` vers `data/demo/lakehouse`, puis `silver verifier`
contre `demo/archive`, qui a le dernier mot) et `make etat` (`ENTITE`,
`A`, `ETAT_OPTIONS`) ; l'étape `make silver` dans le job `integration` de
la CI, après `make demo` ; ADR 0009 ; la section « Le silver » du README
avec les deux exemples réels du jeu (une présentation présente à 23:17:11
et absente à 23:17:12 le 24/10, les informations importantes inchangées
le 26/10 juste après 14:17:39) ; `CONTEXTE.md`. beko a enchaîné `make
rebatir`, `make demo`, `make silver` sur le Mac : 164 106 messages en
14,4 s, 22/22 archives conformes en 10,4 s, mêmes comptes et positions
qu'au palier 2. D.1 tranché par un entrepôt témoin construit avant le
`down -v` et relu après : l'identifiant de grappe change
(`redpanda.990d5d4e-…` → `redpanda.f614c4ee-…`), l'avertissement sort, et
le contrôle des identifiants conclut « rien de nouveau », parce que les
`id` des événements sont des sha256 de leur contenu et que `make demo`
republie le même jeu dans le même ordre. 498 tests.

**Mission 05, relectures et `pr.md`** (29/10). Contrôle du palier 3
(`f0aac28`) : conforme, mission à la relecture. Relecture 1 NON CONFORME,
un bloquant : `Path.as_uri()` encodait un espace ou un accent du chemin de
l'entrepôt et PyIceberg 0.12.0, qui prend le chemin de l'URI à la lettre,
écrivait Parquet et métadonnées dans un dossier voisin (`Mes%20projets`) ;
l'URI est maintenant le chemin brut derrière `file://`, `#` et `?` refusés
avant toute écriture, test sous un dossier à espace et accent. Quatre points
non bloquants : un test fait tomber chacun des quatre invariants SQL du
SCD2, `COPY`/`ATTACH`/`INSTALL` refusés par la connexion DuckDB elle-même,
`lire_instant` limité à trois formes, code mort retiré (`4fa1cb3`).
Relecture 2 CONFORME, 0 bloquant : une date seule impossible est refusée en
code 2 au lieu d'une trace (`c53d714`). Non-régression complète rejouée sur
`c53d714` pour `pr.md` : `evenements` sur `~/pharmaflux-data` identique à
`1af4ef9` par `diff -r`, `profil` 0 bloquante, `questions verifier` 25/5/10,
`demo verifier` et `verifier-bus` conformes ; mémoire de toutes les commandes
silver sous 512 Mo (`comparer` 424 Mo, le plus lourd). 500 tests. Revue
finale de l'IeC, puis publication par beko.

## 2026-10-29 — Mission 06 : gold et qualité

**Durée de `make silver` dans la CI** (reportée par `pr.md` de la mission
05) : **37 s** sur la PR #6, **38 s** sur `main` après la fusion ; dans le
même job `integration`, `make demo` dure 1 min 50 s.

**Mission 06, §0 et palier 1** (29/10). Ordre : le gold (Lot 2, PRD v0.7
§6.5), calculé à la demande depuis le silver à un instant, sans table
stockée. Le §0 a mesuré, sur un silver du jeu construit hors dépôt, une
seule valeur illisible dans tout l'état (`EU/1/17/1235/`, numéro
d'autorisation européenne du CIS 61096104) et une fiche médicament de tout
le jeu en 0,10 s et 318 Mo en PyArrow, contre 552 à 705 Mo en SQL DuckDB ;
l'addendum 1 a tout retenu, avec une requête DuckDB de référence pour
chaque vue (palier 2). Palier 1 : le typage (`pharmaflux.gold.typage`),
qui part des anomalies du silver et non de la valeur seule (un `24.35`
brut a l'air canonique, il reste vide en typé), avec `decimal128(18, 2)`,
`date32`, `list<string>` ; les quatorze contrôles de qualité, quatre
bloquants et dix mesurés, tous à leur chiffre du §0 sur le jeu, aucun
bloquant ne tombe ; `gold etat`, `gold qualite`, `gold sql`. Un test l'a
montré : `strptime` d'Arrow lit `2026-02-30` comme le 2 mars, d'où un
aller-retour de la date avant de la tenir pour lisible.

**Mission 06, palier 2** (29/10). Les trois vues métier, construites en
PyArrow et en Python : la fiche médicament (21 445 fiches, dont 5 562
partielles hors de `CIS_bdpm.txt`), la disponibilité courante (20 918 lignes :
914 signalements en cours, dont 878 dépliés depuis une ligne sans CIP13,
20 004 « aucun signalement »), les alternatives (groupe générique ×
présentations × disponibilité). La priorité « déclaré, puis fin de
publication, puis aucun signalement » est testée branche par branche sur un
fichier de disponibilité synthétique, et chaque vue est égale, en
multiensemble, à une requête DuckDB de référence écrite à part (fixtures à
trois instants, et 28 CIS du jeu). `questions verifier --entrepot` :
**les 25 questions concordent depuis le gold**, 24 par une vue, 1 par les
colonnes typées. Deux garde-fous de plus : un instant où l'une des onze
entités n'est pas encore observée est refusé (sinon « aucun signalement »
serait affirmé avant d'avoir lu le fichier), et la sortie JSON se fait par
lots (la fiche entière passait de 552 à 415 Mo).

**Mission 06, palier 3** (29/10). `make gold` (`gold qualite`, puis
`questions verifier --entrepot`) et `make fiche CIS=… A=…` ; l'étape « make
gold » dans le job `integration`, après « make silver ». ADR 0010, avec ses
limites (une brute illisible égale à la forme canonique précédente ne fait pas
d'événement), la règle des instants et le jour UTC ; README (la fiche de
63830632 à 23:17:11 et 23:17:12 le 24/10, la disponibilité de LARIAM couverte
par une ligne sans CIP13), `CONTEXTE.md`. Le refus d'un instant non observé
donne le premier instant où les onze entités le sont.

**Mission 06, contrôle du palier 3 et relecture 1** (29/10). Contrôle du
palier 3 : conforme, clôture atteinte ; la section « État » du README remise
à jour (missions 00 à 06, tableau des lots). Relecture 1 CONFORME, 0
bloquant, trois points corrigés : deux fermetures au même instant se
départagent comme dans la référence DuckDB (un champ vide perd ; cas ajouté
au fichier synthétique, deux tests tombaient avant) ; un CIS, un CIP13 ou un
groupe inconnu fait refuser `gold disponibilite` et `gold alternatives` au
lieu d'une réponse vide ; un prix absent s'écrit « — » sans unité. Les
validités de chaque table ne sont plus lues qu'une fois par `gold qualite`.
538 tests.
