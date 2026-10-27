# Mission 04 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Fable 5.1) · **À :** IeC, beko · **Date :** 27/10/2026
**Branche :** `mission-04-rejeu-accelere-et-demo` (sommet `f1750dc`, identique
à `main`) · **Ordre lu sur `main`** (`f1750dc`), après `CLAUDE.md` (exception
`demo/`), `docs/agents/processus.md` (`make` en simulation, `git archive`,
`git config` en lecture) et le PRD v0.5 (§4, §6.4, §7.1, §7.3, §9).

**Ce que j'ai lu, et comment.** Le code de la mission 03 (`evenements/`,
`bus/`, `bronze.py`, `collecte/manifeste.py`, `cli.py`), les ADR 0006 et
0007, `pr.md` et le contrôle final de la mission 03, la CI, le fichier
compose, `.gitignore`, le garde-fou (`make`, `git add`). La copie rapatriée
`~/pharmaflux-data` (`PHARMAFLUX_DATA` non posée), **en lecture seule** :
28 archives, manifeste de 860 lignes, 71 passages du 24/10 19:41 au 27/10
15:17 UTC. Les mesures : deux sondes sur le manifeste et les bilans
(bibliothèque standard, `uv run python -`), et trois `pharmaflux evenements`
dont la sortie est dans le dossier temporaire de la session, hors du dépôt
(deux rejeux complets, `diff -r` identique, et deux rejeux d'une seule
entité pour la mémoire). **Aucune commande `docker`, `colima` ni `make`,
aucune requête réseau, rien d'écrit dans le dépôt ni dans l'archive, aucun
refus du garde-fou. Rien n'a été codé.**

**Lecture rapide, les constats qui pèsent sur l'ordre :**

1. **La copie du 27/10 donne 164 106 événements** : 164 096 `creee` d'état
   initial (inchangé) et **10 `supprimee`**, toutes sur `CIS_CIP_bdpm.txt`
   (2 le 24/10 à 23:17, 1 le 26/10 à 00:17, **7 le 27/10 à 00:17**, cette
   dernière archive est nouvelle depuis la mission 03). Rejeu complet :
   9,6 s, 185 Mo résidents (point H.1).
2. **L'alternance du 27/10 n'a produit aucun événement** (point B) : les
   trois archives vides sont `ecarte` sans appel, les trois archives
   pleines sont `retenu` avec le motif « identique au dernier retenu », donc
   un fichier d'événements **vide**. Aucune `supprimee`, aucun second état
   initial : les 10 905 `creee` du fichier datent toutes du 24/10.
3. **L'ordre global par date d'observation est l'ordre par topic de
   `publier`** (point C) : les fichiers d'événements s'appellent
   `<horodatage>__<sha12>.jsonl`, `publier` les trie par nom, donc par
   horodatage ; un tri global par (horodatage, entité) restreint à une
   entité redonne cette suite.
4. **Les onze archives de l'état initial sont espacées de 2 à 3 s** (19:41:43
   à 19:42:06) : à un facteur de 1 000, elles se suivent sans pause
   visible, sans cas particulier dans le code (point C).
5. **`pharmaflux evenements` n'affiche pas son journal par archive** : la
   commande ne pose pas `configurer_journal()`, donc les lignes « archive :
   décision (motif) ; types » existent dans le code et sont perdues. Le
   rejeu accéléré doit afficher les siennes (point H.2).
6. **Cinq archives de même contenu, cinq fichiers `.gz` différents** : le
   collecteur écrit l'horodatage dans l'en-tête gzip. Le jeu reste « à
   l'octet », et git fera des deltas entre ces blobs (point A).

## A. Le contenu du jeu de démo

**Ce que `evenements` lit vraiment.**

- Du bronze : les archives des **onze** fichiers TSV, par
  `bronze.lister(racine, "bdpm", <fichier>)` : le chemin
  `bronze/bdpm/<fichier>/<jour>/<horodatage>__<sha12>.txt.gz`, l'horodatage
  et le sha12 **du nom**, puis les octets décompressés. Rien d'autre sous
  `bronze/` n'est ouvert.
- Du manifeste (`rejeu._Manifeste.lire`) : les lignes `nouveau` qui ont un
  `chemin_archive`, pour `date_source_affichee` (la `date_source` de
  l'événement) et `empreinte_comparaison` ; les lignes `inchange` qui ont
  une `empreinte_comparaison`, pour `identifiant`, `empreinte_comparaison`
  et `fin` (la confirmation d'un snapshot en attente par un passage
  inchangé, ADR 0006). Les champs `identifiant` et `statut` servent au tri.
  Aucun autre champ n'est lu.

**Ce qui reste dehors** : `telechargement.html` (4 archives, le contenu
change chaque nuit, 32 Ko), le PDF de documentation (252 Ko) et les
métadonnées d'Open Medic (16 Ko). Leurs lignes de manifeste sortent avec
eux : sinon le test « chaque archive citée existe » échouerait. Le jeu ne
porte donc que les trois entrées que `evenements` ne lit pas en moins ;
`pharmaflux etat --racine demo/archive` y verra onze fichiers.

**Date de coupure proposée : le passage `20261027T151708Z` inclus**, le
dernier de la copie rapatriée (27/10 15:17 UTC). Le jeu couvre alors du
24/10 19:41:41 au 27/10 15:17 UTC, 71 passages. Pourquoi là et pas à la
dernière archive (13:17:31) : les deux passages `inchange` de 14:17 et 15:17
montrent que le fichier est resté complet après l'alternance, et une coupure
à la fin de la copie se dit en une ligne (« la copie du Mac au 27/10 15:17,
moins trois entrées »). Un passage est l'unité : tout ce qu'il a consigné
entre, ou rien.

**Taille dans git**, mesurée sur ce choix :

| contenu | compté | octets |
|---|---|---|
| 22 archives `.txt.gz` (les 11 fichiers, 22 lignes `nouveau`) | compressé | 6 223 606 |
| les mêmes, décompressées | brut | 59 138 184 |
| `manifeste/collecte.jsonl` : 781 lignes (22 `nouveau`, 759 `inchange`) | texte | 615 459 |
| `demo/README.md` | texte | ≈ 4 000 |

Soit **6,85 Mo extraits**, et moins dans le pack : le manifeste se compresse
dix fois, et quatre des cinq archives de `CIS_InfoImportantes.txt` ne
diffèrent de la première que par l'horodatage de l'en-tête gzip (git fait
un delta). Estimation : **6 Mo dans le pack**, chiffre exact au palier 1
(`git count-objects -vH` avant et après). Le jeu est figé : il ne grossit
plus.

**Disposition** : `demo/archive/`, **la même arborescence que l'archive**
(`bronze/bdpm/<fichier>/<jour>/…`, `manifeste/collecte.jsonl`), pour que
toute commande qui prend `--racine` marche sans rien de neuf :
`evenements`, `verifier-bus --racine demo/archive`, `etat`, `profil`, et
`questions verifier` (les 25 archives qu'il cite sont du 24/10 19:41 et du
24/10 23:17, toutes dans le jeu). À côté, `demo/README.md` : la source
(BDPM, URL de la page de téléchargement), la licence (celle du README,
section « Licences des données »), la date et la commande de fabrication,
les dates couvertes et la coupure, ce que le jeu montre et ne montre pas, et
la table des 22 archives avec leur sha256 complet (repris du manifeste, qui
reste la référence). Pas de fichier de sommes à part : le manifeste les
porte déjà.

**Les lignes du manifeste reprises** : **toutes** celles des onze entités
jusqu'à la coupure, `inchange` compris, **à l'octet**. Les `inchange` sont
lus par `evenements` (confirmation d'un snapshot en attente ; aucun dans
cette copie, mais la règle doit valoir sur le jeu), affichés par `etat`, et
le rejeu accéléré les dira (« passage de 03:17 : rien de neuf », point C).
Les champs du serveur : `etag` et `last_modified` sont nuls sur les 860
lignes ; `content_disposition_nom` porte un horodatage du serveur
(`CIS_InfoImportantes_20261027131731_bdpm.txt`), `url`, `http_statut`,
`essais`, `taille_affichee_ko`, `debut` et `fin`, `version_collecteur`
(six commits de ce dépôt public). **Aucun n'est à retirer** : rien de
personnel, rien de secret, tout vient d'un service public ou de ce dépôt.
Et retirer un champ casserait « à l'octet » : le test vérifie que chaque
ligne du jeu **est** une ligne du manifeste source. Si l'IeC en veut un
dehors malgré tout, ce sera une réécriture de la ligne, à dire dans le
README.

**Fabrication** : une commande du projet, groupe `pharmaflux demo` (module
`pharmaflux/demo/`), jamais à la main :

```bash
uv run pharmaflux demo fabriquer --racine ~/pharmaflux-data \
  --destination demo/archive --jusqu-au-passage 20261027T151708Z
```

Elle lit le manifeste en flux, garde les lignes des onze entités (`--fichier`
pour en choisir moins) dont `passage_id` ≤ la coupure, copie telles quelles
les archives citées par les lignes `nouveau` (`shutil.copyfile`, octets
inchangés), écrit le manifeste filtré octet pour octet, **refuse une
destination non vide** et n'écrit jamais dans la racine. La même commande
lancée sur un autre dossier donne un second jeu, jamais une mise à jour.

**Ce que vérifie le test** (`tests/test_demo.py`, sans réseau, ≈ 0,5 s),
par une fonction `demo.verifier(racine)` que `pharmaflux demo verifier`
expose aussi, pour un clone neuf :

- chaque ligne `nouveau` cite une archive qui existe, dont les octets
  décompressés ont le `sha256` de la ligne et dont le nom porte ses 12
  premiers caractères ;
- chaque fichier sous `bronze/` est cité par exactement une ligne ; rien
  d'autre n'est présent (ni fichier, ni dossier, en dehors de `bronze/` et
  de `manifeste/collecte.jsonl`) ;
- le manifeste se lit (`manifeste.parcourir`), toutes les lignes sont dans
  l'ordre des passages, aucune n'est en erreur, aucune n'est postérieure à
  la dernière archive ;
- sur le jeu du dépôt : 22 archives, 11 entités, 781 lignes (les nombres
  du README).

Un second test fabrique un jeu depuis un bronze de test (l'aide `peupler`
de `tests/test_rejeu.py`) : la coupure est respectée, les octets sont ceux
de la source, une destination non vide est refusée, et `evenements` sur le
jeu donne la même sortie que sur la source tronquée.

**`.gitignore`**, l'exception la plus étroite, sous la règle `*.gz` :

```
*.gz
!demo/archive/bronze/**/*.gz
```

`data/` ne change pas (le jeu n'est pas sous `data/`, la sortie du rejeu
l'est). Git accepte cette réinclusion parce qu'aucun dossier parent n'est
ignoré. Le garde-fou laisse passer `git add demo/…` (seuls les chemins
réservés sont refusés) ; le crochet `pre-commit` aussi.

## B. Ce que la démo montrera

Sur la copie rapatriée, par jour et par fichier, les archives `nouveau`
des onze entités et les événements de chacune (`evenements` dans un dossier
jetable, bilans relus) :

| observé (UTC) | fichier | décision | événements |
|---|---|---|---|
| 24/10 19:41:43 → 19:42:06 | les onze fichiers | retenu (premier snapshot) | 164 096 `creee` (état initial) |
| 24/10 23:17:12 | `CIS_CIP_bdpm.txt` | retenu, 20 896 lignes | 2 `supprimee` |
| 26/10 00:17:12 | `CIS_CIP_bdpm.txt` | retenu, 20 895 lignes | 1 `supprimee` |
| 26/10 14:17:39 | `CIS_InfoImportantes.txt` | **écarté** : vide, aucune ligne bien formée | 0 |
| 26/10 15:17:31 | `CIS_InfoImportantes.txt` | retenu : identique au dernier retenu (24/10) | 0 (fichier vide) |
| 27/10 00:17:12 | `CIS_CIP_bdpm.txt` | retenu, 20 888 lignes | 7 `supprimee` |
| 27/10 08:17:31 | `CIS_InfoImportantes.txt` | **écarté** : vide | 0 |
| 27/10 09:17:31 | `CIS_InfoImportantes.txt` | retenu : identique au dernier retenu (26/10 15:17) | 0 |
| 27/10 10:17:31 | `CIS_InfoImportantes.txt` | **écarté** : vide | 0 |
| 27/10 11:17:31 | `CIS_InfoImportantes.txt` | retenu : identique au dernier retenu (27/10 09:17) | 0 |
| 27/10 12:17:31 | `CIS_InfoImportantes.txt` | **écarté** : vide | 0 |
| 27/10 13:17:31 | `CIS_InfoImportantes.txt` | retenu : identique au dernier retenu (27/10 11:17) | 0 |

Le 25/10 n'a aucune archive : 24 passages, tous `inchange`. Résumé de
`evenements` : `bdpm.infos_importantes 9 archive(s) lue(s), 5 retenue(s),
4 écartée(s), 0 en attente ; événements : creee 10905` ;
`bdpm.presentations 4 archive(s) lue(s), 4 retenue(s) ; creee 20898,
supprimee 10`.

**Ce qu'un spectateur verra après l'état initial** : trois nuits, trois
fois quelques présentations retirées (2, 1, puis 7 messages sur
`pharmaflux.bdpm.presentations.v1`), et huit lignes sur
`CIS_InfoImportantes.txt` qui ne donnent **aucun message**. Il ne verra ni
`modifiee`, ni `creee` après l'état initial : la copie n'en contient pas.
C'est le rythme réel, et la démo le dira (ADR 0008, README).

**L'alternance du 27/10, ce que le garde-fou de volume et `evenements` en
ont fait**, lu dans les bilans :

- les trois archives vides (08:17, 10:17, 12:17, sha256 `e3b0c442…`, zéro
  octet) : `ecarte`, motif « vide : aucune ligne bien formée », **sans
  appel** (`volume.evaluer`, `lignes == 0` avant toute comparaison) : jamais
  en attente, jamais retenues, donc le dernier retenu ne bouge pas ;
- les trois archives pleines (09:17, 11:17, 13:17, sha256 `a27b30e1…`) :
  `retenu`, motif « identique au dernier retenu », parce que leurs 10 905
  lignes égalent celles du dernier retenu et que le sha256 est le même ;
  elles **deviennent** le dernier retenu (le motif de 11:17 cite 09:17, celui
  de 13:17 cite 11:17), et la comparaison ne produit rien : un fichier
  d'événements de zéro octet, un bilan avec `evenements: {}` ;
- **aucune `supprimee`** : le vide n'est jamais comparé ;
- **pas de double état initial** : `etat_initial` ne vaut vrai que quand le
  dernier retenu est `None`, c'est-à-dire pour la première archive du
  24/10 ; le compte total de `creee` du fichier reste 10 905 ;
- l'incident du 26/10 (14:17 vide, 15:17 plein) est traité à l'identique :
  c'est le même scénario, joué une fois au lieu de trois.

**Comment la démo le montre** : dans le terminal du rejeu, une ligne par
archive, lue dans le bilan (« écarté : vide, aucune ligne bien formée »,
puis « retenu : identique au dernier retenu, 0 événement »), à 3,6 s
d'intervalle au facteur par défaut ; **sur le bus, rien** : le consommateur
`suivre` ne reçoit aucun message, et `verifier-bus` ne voit que l'état du
24/10. Les bilans restent des fichiers (mission 03, décision 7) : le rejeu
les lit et les dit, il ne les publie pas. C'est l'incident **tel quel** :
pas de message fabriqué pour le rendre visible.

## C. Le rejeu accéléré

**Commande** : `pharmaflux demo rejouer`, dans le groupe `demo` avec
`fabriquer` et `verifier` (module `pharmaflux/demo/rejeu_accelere.py`).
Options et valeurs par défaut :

| option | défaut | rôle |
|---|---|---|
| `--racine` | `demo/archive` | l'archive rejouée (lecture seule) ; `~/pharmaflux-data` pour rejouer la vraie copie |
| `--sortie` | `data/demo` | sortie de `evenements` et `publication.json` ; hors git (`data/`), jamais sous la racine |
| `--fichier` | les onze | comme `evenements` |
| `--facteur` | `1000` | une heure observée dure 3 600 / facteur secondes : 3,6 s |
| `--sans-pause` | faux | aucune attente (CI) |
| `--sans-passages` | faux | tait les passages horaires sans archive nouvelle |
| `--reprendre` | faux | continue un rejeu interrompu |
| `--courtier`, `--registre` | comme `publier` | |

Les défauts diffèrent des autres commandes (`~/pharmaflux-data`,
`data/evenements`) parce que la commande est faite pour le jeu du dépôt :
`make demo` tient en une ligne sans option.

**Ce qu'elle fait, dans l'ordre** :

1. vérifie le courtier et le registre (comme `publier` : code 1 sans
   courtier, code 2 sans schéma enregistré, avec le conseil `schemas
   enregistrer`) ;
2. vérifie l'état attendu du bus et de la sortie (plus bas) ;
3. lance `rejeu.executer` (le code de `evenements`, rejeu complet ou
   `--reprendre`) sur la racine vers la sortie : les fichiers JSONL restent
   la référence, il n'y a pas de second chemin de calcul ;
4. construit l'**ordre global** : une entrée par bilan (chaque archive lue
   en laisse un, écartée ou non), triée par (horodatage de l'archive,
   entité), avec son fichier d'événements s'il existe ; et, si les passages
   sont affichés, une entrée par passage du manifeste sans archive nouvelle ;
5. déroule : pour chaque entrée, attend l'instant de l'horloge de la démo,
   affiche la ligne, et publie le fichier d'événements par le code de
   `publier` ;
6. affiche le résumé.

**L'ordre global et l'ordre par topic.** Le tri par (horodatage, entité)
restreint à une entité est le tri par horodatage de ses fichiers, c'est-à-
dire le tri par nom de `publication.lister_fichiers`, parce que le nom
commence par l'horodatage. Un test unitaire le montre sur une sortie à trois
entités et sept archives entrelacées : la suite des fichiers publiés par
entité est la même que celle de `publier`. Sur le bus, l'ordre par partition
est donc celui de `publier` ; seul l'entrelacement entre topics change, et il
ne compte pour personne.

**Le chemin de publication : celui de `publier`, fichier par fichier, avec
le même `publication.json`.** `publication.executer` est découpé en deux
fonctions publiques, `preparer` (courtier, schémas, topics, état, contrôles
d'inchangé et d'ordre) et `publier_fichier` (un fichier, ses accusés de
réception, l'état réécrit) ; `publier` enchaîne les fichiers par entité puis
nom, `rejouer` par ordre global. Un seul code pour l'enveloppe, la file des
échecs, l'état et les refus (F.3 compris). **Un rejeu interrompu se reprend
avec `demo rejouer --reprendre`** : il relance `evenements --reprendre`
(rien de nouveau sur un jeu figé), puis publie dans l'ordre global les
fichiers absents de `publication.json`, le fichier coupé en entier (ses
doublons sont ceux de la mission 03, même `id`). `publier --reprendre
--sortie data/demo` marche aussi et donne le même bus (même état, même ordre
par topic), mais sans l'horloge : c'est une reprise, pas une démo. Les deux
sont dits dans le README.

**La cadence.** La démo a une horloge : pour chaque entrée observée à
`t_obs`, l'instant réel visé est
`t_reel_depart + (t_obs − t_obs_premiere) / facteur`, et la commande dort
jusqu'à lui (jamais de pause négative : si la publication précédente a pris
plus que la pause, elle enchaîne et l'horloge rattrape). Les pauses sont
donc des différences d'observation divisées par le facteur, et le temps de
publication ne s'ajoute pas. Sur le jeu, 22 observations distinctes,
65,6 h d'étendue :

| facteur | pauses totales | plus longue (le 25/10, 25 h sans archive) | une heure | durée de `make demo` estimée |
|---|---|---|---|---|
| 720 | 328 s | 125 s | 5 s | ≈ 6 min |
| **1 000** | **236 s** | **90 s** | **3,6 s** | **≈ 4 min 15 s**, 4 min 30 avec `verifier-bus` |
| 1 200 | 197 s | 75 s | 3 s | ≈ 3 min 45 s |
| 2 000 | 118 s | 45 s | 1,8 s | ≈ 2 min 30 s |

Estimation : `evenements` 10 s avant que l'horloge parte, publication de
l'état initial 30 s qui recouvre la première pause (13 s), puis les pauses.
**Défaut proposé : 1 000**, le plus lisible (« une heure vaut 3,6 s, un
jour 86 s ») sous les 5 minutes. `--sans-pause` pour la CI : le facteur
infini, toutes les pauses à zéro, ≈ 45 s. Les tests unitaires reçoivent
l'horloge et la fonction de sommeil en paramètres : ils vérifient les
instants visés sans dormir.

**L'état initial** : ni d'un bloc, ni étalé par une règle à part. Les onze
archives du 24/10 sont onze entrées de l'ordre global espacées de 2 à 3 s
observées, soit 2 à 3 ms au facteur 1 000 : elles s'enchaînent, et la
publication (30 s pour 164 096 messages) est ce que le spectateur voit,
onze lignes avec leurs comptes. Le premier « tic » de l'horloge est la
première archive. Si l'IeC préfère qu'elles passent **avant** l'horloge,
c'est une option de plus que je ne propose pas.

**Les passages horaires inchangés : oui, par défaut**, une ligne par passage
du manifeste sans archive nouvelle pour les entités rejouées (49 sur 71 ;
24 le 25/10) : « 25/10 03:17  passage : 11 fichiers inchangés, rien de
neuf ». Sans elles, les 90 s du 25/10 sont un écran immobile ; avec elles,
l'horloge avance d'heure en heure et le rythme réel se voit. `--sans-passages`
pour les taire (et pour un rejeu de la vraie copie, où ils seront des
milliers).

**Ce que la commande affiche**, une ligne par entrée, à l'heure observée :

```
24/10 19:41:43  bdpm.specialites             état initial : creee 15883 → pharmaflux.bdpm.specialites.v1 (15883 messages, 2,8 s)
…
24/10 23:17:12  bdpm.presentations           supprimee 2 → pharmaflux.bdpm.presentations.v1 (2 messages)
25/10 00:17     passage : 11 fichiers inchangés, rien de neuf
…
26/10 14:17:39  bdpm.infos_importantes       snapshot écarté : vide, aucune ligne bien formée (rien publié)
26/10 15:17:31  bdpm.infos_importantes       retenu : identique au dernier retenu, 0 événement (rien publié)
```

puis le résumé : archives rejouées, écartées, en attente, messages par
topic, messages en échec, durée observée (65 h 36 min) contre durée réelle,
facteur, et l'état (`data/demo/publication.json`). Codes de sortie : ceux
de `publier` (1 courtier ou livraison, 2 refus, 3 file des échecs), 0 sinon.

**Un bus qui n'est pas vide, ou un `publication.json` d'une autre sortie :
refus, code 2, avant toute publication**, avec la voie de retour :

| topics `pharmaflux.*.v1` sur le courtier | `publication.json` dans la sortie | sans `--reprendre` | avec `--reprendre` |
|---|---|---|---|
| aucun | absent | rejeu complet | rejeu complet (rien à reprendre) |
| présents | présent et cohérent (mêmes fichiers, mêmes sha256) | refus : « le bus a déjà reçu une publication : `make rebatir` » | reprise |
| présents | absent | refus : « bus non vide sans état : `make rebatir` » | refus, même message |
| aucun | présent | refus : « état sans bus : supprime `data/demo` (`make rebatir`) » | refus, même message |

« Cohérent » est le contrôle de `publier` (fichier disparu ou modifié :
refus). La liste des topics vient de `verifier_courtier`, déjà dans le
protocole `Bus`. La sortie par défaut, `data/demo/`, est sous `data/`, donc
hors git ; `make rebatir` l'efface avec le volume.

## D. Un consommateur à regarder : `pharmaflux suivre`

**Avis : oui, à retenir, en version minimale.** Ce qu'il apporte que la
console n'apporte pas : il tient dans un second terminal, sans navigateur ni
profil compose, et il dit l'événement en une ligne lisible (heure observée,
entité, type, clé, colonnes changées) au lieu d'un JSON de trois kilo-octets
dont il faut lire `champs_modifies` à la main. Pendant la démo, c'est lui qui
rend le flux visible ; la console reste pour fouiller un message. Ce qu'il
coûte : un module `bus/suivi.py` d'une centaine de lignes, une méthode
`suivre(topics, depuis_le_debut)` sur `LecteurKafka` (assignation manuelle,
sans groupe ni commit, départ aux offsets de fin ou au début, boucle de
`poll` jusqu'à l'arrêt), le formatage testé sur des `MessageLu` fabriqués, et
un test d'intégration (publier trois événements, lire trois lignes). Pour le
rendre testable et utile en CI : `--nombre N` arrête après N messages ; sans
lui, `Ctrl-C` arrête proprement avec un résumé et le code 0.

**La ligne** : `24/10 23:17:12  bdpm.presentations  supprimee  cip7=3400930000000  cis=60000000`
pour une clé ; pour une `modifiee`, les noms de `champs_modifies` ; pour une
identité `ligne`, l'empreinte et le rang. L'heure vient de l'horodatage du
message (`date_observation`), pas de l'horloge.

**Un message qui n'est pas un événement v1** (valeur illisible, `entite` ou
`version_schema` autre) : une ligne sur la sortie d'erreur, « message
illisible pharmaflux.bdpm.x.v1/2@18 : <motif> », comptée dans le résumé, et
la lecture continue ; le code reste 0 : `suivre` regarde, `verifier-bus`
juge. Il lit les onze topics d'événements par défaut (`--fichier` pour
moins), jamais la file des échecs (une option `--echecs` plus tard, si on en
a besoin). À lancer **avant** `make demo` quand on part de la fin du topic ;
le README le dira, et `make suivre` existe.

## E. Le `Makefile`

Cibles et commandes exactes (variables en tête : `COMPOSE = docker compose
-p pharmaflux`, `PHARMAFLUX = uv run pharmaflux`, `DEMO_OPTIONS ?=`) :

| cible | commandes |
|---|---|
| `help` (défaut) | la liste des cibles en une ligne chacune |
| `prerequis` | `sh infra/demo/prerequis.sh` |
| `up` | `prerequis`, puis `$(COMPOSE) up -d --wait --pull never` |
| `demo` | `up`, puis `$(PHARMAFLUX) schemas enregistrer`, `$(PHARMAFLUX) demo rejouer $(DEMO_OPTIONS)`, `$(PHARMAFLUX) verifier-bus --sortie data/demo --racine demo/archive` |
| `verifier` | `$(PHARMAFLUX) verifier-bus --sortie data/demo --racine demo/archive` |
| `suivre` | `$(PHARMAFLUX) suivre` |
| `console` | `$(COMPOSE) --profile console up -d --pull never`, puis l'URL `http://127.0.0.1:18080` |
| `down` | `$(COMPOSE) down` |
| `rebatir` | `$(COMPOSE) down -v`, `rm -rf data/demo`, puis `up` |
| `verifications` | `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q` |

Toutes `.PHONY`. `make` s'arrête à la première commande en échec : le code
de sortie de `make demo` est celui de la démo, et `verifier-bus` est le
dernier mot. Aucune cible ne contient `prune`, aucune ne nomme un autre
projet, un autre conteneur ou un autre volume que `pharmaflux`.

**Les prérequis** (`infra/demo/prerequis.sh`, POSIX `sh`, relu par
shellcheck 0.11.0.1), chacun avec un message qui dit quoi faire :

1. `docker` présent (`command -v`) et le démon répond (`docker info
   --format '{{.ServerVersion}}'`) : sinon « lance Docker (colima start) » ;
2. Compose comprend le fichier : `docker compose -p pharmaflux config
   --quiet`, qui valide le bloc `configs: content:` sans rien télécharger ;
   sinon « Compose 2.23.1 au moins » ;
3. les images du fichier compose sont **déjà présentes** (`docker image
   inspect` sur chaque `image:` lu par `grep` dans `docker-compose.yml`) :
   sinon « télécharge-les une fois : `docker compose -p pharmaflux --profile
   console pull` ». `make up` ne télécharge donc jamais : `--pull never`, et
   le refus vient avant ;
4. `uv` présent.

Le garde-fou ne me laisse pas lancer `make up` ; je lance une à une les
commandes que `make -n up` affiche, et les commandes du script sont des
lectures (`docker info`, `config`, `image inspect`) que le garde-fou permet.

**GNU Make 3.81** : recettes en tabulations, `.PHONY`, `?=`, `$(shell …)`
seulement s'il le faut, `ifeq` au besoin ; rien de 3.82 ou 4.x (`.ONESHELL`,
`!=`, `::=`, `$(file …)`, `undefine`, `.RECIPEPREFIX`). `make -n` sur le
Mac est le 3.81 lui-même : il lit tout le fichier avant d'afficher, donc une
construction inconnue de 3.81 se voit au palier 3, avant le push. Le
runner Ubuntu a GNU Make 4.3, qui lit tout ce que 3.81 lit.

**`make demo` relancé sur un bus qui a déjà reçu la démo** : `schemas
enregistrer` est idempotent ; `demo rejouer` refuse (C, deuxième ligne de la
table), code 2, message « le bus a déjà reçu une publication : `make
rebatir` » ; `verifier-bus` n'est pas atteint. Pour revérifier sans rejouer :
`make verifier`. Pour tout refaire : `make rebatir && make demo`.

**Question (Q2)** : `demo` dépend de `up` dans ma proposition (un `up -d
--wait` sur un courtier déjà démarré prend deux secondes), pour que `make
demo` seul marche aussi. L'ordre dit « `make up` puis `make demo` » : les
deux restent vrais. Si l'IeC préfère `demo` sans dépendance, c'est une
ligne.

## F. Les reliquats de la mission 03

1. **Tri numérique de l'historique des schémas : maintenant.** Trois
   lignes dans `registre.historique` (la clé de tri devient l'entier entre
   le nom du schéma et `.json`), un test avec `evenement.v1.schema.2.json`
   et `.10.json` dans un dossier temporaire (`dossier_schemas` remplacé),
   qui attend l'ordre 2 puis 10. Le point 2 touche le même module ; le faire
   ici évite de le retrouver dans la mission qui fera entrer le premier
   schéma, où il n'aura plus de test naturel.
2. **`Registre.compatible` : l'utiliser, pas le retirer.** Dans
   `enregistrer_tout`, avant d'enregistrer le schéma **courant** d'un sujet
   (l'historique s'enregistre sans contrôle : c'est le passé), appeler
   `compatible(sujet, schema)` ; si faux, lever `SchemaIncompatible` avec un
   message qui nomme le sujet et la règle (« le schéma du dépôt est
   incompatible avec les versions enregistrées de `<sujet>`
   (`BACKWARD_TRANSITIVE`) : une évolution incompatible est une nouvelle
   `version_schema`, donc un nouveau topic, ADR 0007 »), et `schemas
   enregistrer` sort code 1. Pourquoi plutôt que le 409 du registre : le
   409 arrive après que les sujets précédents ont été enregistrés, avec un
   texte HTTP ; le contrôle avant est lisible et testable sur le registre
   simulé (`RegistreSimule` répond déjà à `/compatibility`, il recevra un
   cas `is_compatible: false`). Test : un schéma qui retire une propriété
   requise est refusé, rien n'est enregistré pour ce sujet.
3. **Refus explicite d'un fichier hors d'ordre dans `publier` : dans cette
   mission, code 2.** Dans `preparer` (C), après le contrôle d'inchangé,
   pour chaque fichier à publier : si l'état de son entité contient un
   fichier dont le nom se range **après** lui, `PublicationRefusee` :
   « `bdpm.presentations` : `20261024T231712Z__a6da566e8036.jsonl` se range
   avant le dernier fichier publié (`20261026T001712Z__276207db5783.jsonl`) ;
   un événement publié n'est jamais réordonné : rebâtis le bus ». Le
   contrôle porte sur tout le lot **avant** le premier message : rien n'est
   publié, l'état ne bouge pas. Il **couvre le rejeu** : `demo rejouer`
   passe par `preparer` avec le même état. Par construction, `evenements` ne
   produit jamais ce cas (les résultats sortent dans l'ordre des archives,
   et un snapshot en attente tranché écrit son fichier avant celui de
   l'archive qui le tranche) ; le refus attrape un JSONL copié à la main ou
   une sortie recomposée de deux archives. Test unitaire sur le bus simulé :
   publier B, déposer A < B, `--reprendre` refuse, l'état est inchangé, le
   bus n'a rien reçu ; et le même sur `rejouer`.

## G. CI

**Proposition** : dans le job `integration`, après l'étape des tests, une
étape « Démo sans pause (make demo, bus neuf) » :

```yaml
      - name: Démo sans pause (make demo, bus neuf)
        run: make demo DEMO_OPTIONS=--sans-pause
```

Le bus est neuf au sens du rejeu : les tests d'intégration effacent leurs
topics et sujets (préfixes uniques), il ne reste aucun `pharmaflux.*.v1`.
Les images sont déjà là (l'étape `up` du job les a tirées), `prerequis.sh`
passe, `up -d --wait --pull never` ne fait rien, `schemas enregistrer` est
idempotent, et `verifier-bus --racine demo/archive` finit l'étape : **oui,
la démo y est vérifiée par la référence indépendante des fichiers**, et son
code de sortie est celui de l'étape. L'étape `down -v` reste en `always()`.

**Durée ajoutée**, d'après le Mac (arm64) et un runner amd64 compté une
fois et demie plus lent : `evenements` 10 → 15 s, publication 30 → 45 s,
`verifier-bus --racine` 12 → 20 s, soit **≈ 1 min 30 s** ; le job tient dans
ses 15 minutes (les tests prennent 14 s), je ne touche pas au délai. Le job
`verifier` ne change pas ; `pytest -q` y gagne `tests/test_demo.py`
(≈ 0,5 s sur `demo/archive`).

**Vérifier le job avant le push, avec un seul push** :

1. le YAML : le crochet `pre-commit` le relit au commit (`ruby -ryaml`), et
   je le relance à la main avant ;
2. la nouvelle étape est une ligne `make` : ce qui tourne en CI est le
   `Makefile`, le même que sur le Mac. Je rejoue `make -n demo
   DEMO_OPTIONS=--sans-pause`, puis ses commandes une à une sur un bus
   rebâti (`down -v`), avec la sortie dans le rapport du palier 3 ; beko
   lance ensuite le vrai `make demo` (décision 7) ;
3. `shellcheck` 0.11.0.1 sur `prerequis.sh`, la version de la CI ;
4. les tests d'intégration avec `PHARMAFLUX_INTEGRATION_EXIGEE=1`, comme en
   CI.

Ce que cela ne couvre pas, à dire d'avance : l'architecture amd64, la
version de Compose du runner (la mission 03 a tranché ces deux points à son
push : le job `integration` est passé) et GNU Make 4.3 contre 3.81 (un
fichier écrit pour 3.81 se lit en 4.3). Il n'existe pas d'outil dans le
dépôt pour rejouer un workflow en local, et je n'en installe pas.

## H. Autres remarques

1. **Mémoire du rejeu complet : 185 Mo sur la copie du 27/10**, deux fois
   de suite, contre 118 à 149 Mo mesurés à la mission 03 sur la copie du
   26/10 (cible de 160). Seul : `bdpm.infos_importantes` (9 archives,
   10 905 lignes de texte long) 105 Mo, `bdpm.compositions` 83 Mo. La
   cause n'est pas isolée (trois archives de plus pour les informations
   importantes, dont trois pleines ; ou le plateau de l'allocateur). C'est
   une mesure, pas une régression de code : le code est celui de `main`.
   Le VPS garde sa marge sous 256 Mo. **Proposition** : mesurer au palier 2
   sous `tracemalloc` par entité, consigner dans l'ADR 0008 et le PRD §9 ;
   ne rien changer à `evenements` dans cette mission sauf ordre contraire
   (Q5).
2. **`pharmaflux evenements` perd son journal** (constat 5) : une ligne
   `configurer_journal()` au début de la commande, comme `publier`, le
   rendrait visible. C'est hors de l'ordre et c'est le code de la mission
   02 : je le propose, je ne le fais pas sans accord (Q4). Le rejeu
   accéléré affiche ses lignes lui-même, quelle que soit la réponse.
3. **`questions verifier --racine demo/archive`** marchera (A) : le README
   de la démo peut le dire, c'est une seconde preuve que le jeu est l'archive
   à l'octet.
4. **Le jeu de questions et les fixtures ne changent pas** : les tests
   unitaires du rejeu accéléré se font sur des sorties fabriquées et le bus
   simulé (`tests/test_bus.py`), les tests d'intégration sur les fixtures de
   la mission 03, jamais sur `demo/archive` (sauf `test_demo.py`, qui lit
   le jeu sans courtier).
5. **Aucune dépendance nouvelle** : `make` est sur le Mac (outils de ligne
   de commande) et sur le runner ; le reste est la bibliothèque standard et
   le code du projet. `shellcheck` reste tiré par `uvx` à la demande.
6. **L'ADR 0008** dira ce que la démo ne montre pas : aucune `modifiee` ni
   `creee` hors état initial sur cette copie, aucun snapshot en attente, et
   la file des échecs vide (la copie n'a ni ligne illisible ni message trop
   gros ; le cas reste testé sur les fixtures).

## Questions à trancher

- **Q1** (A) : coupure au passage `20261027T151708Z` (fin de la copie), ou à
  la dernière archive `20261027T131731Z` ?
- **Q2** (E) : `make demo` dépend de `up`, ou non ?
- **Q3** (D) : `pharmaflux suivre` retenu en version minimale (`--nombre`,
  `--depuis-le-debut`, onze topics, code 0) ?
- **Q4** (H.2) : poser `configurer_journal()` dans `evenements`, hors de
  l'ordre ?
- **Q5** (H.1) : la mémoire à 185 Mo, mesurer et consigner seulement ?
- **Q6** (C) : facteur par défaut 1 000, passages horaires affichés par
  défaut, groupe `pharmaflux demo` (`fabriquer`, `verifier`, `rejouer`) :
  d'accord sur les noms ?

Sans réponse contraire, je pars sur mes propositions à chaque point.
