# ADR-0010 — Le gold : calculé à la demande depuis le silver, typé par les anomalies, trois vues, quatorze contrôles

**Statut :** accepté (mission 06) · **Date :** 2026-10-29 · **Mission :** 06 ·
s'appuie sur les ADR 0002, 0003, 0005, 0006 et 0009
**Remplace / remplacé par :** —

## Contexte

Le silver (ADR 0009) répond « que savait-on à cet instant ? », mais en
chaînes et entité par entité. Une question métier (« cette présentation
est-elle disponible, et quelles alternatives du même groupe le sont ? »)
demandait de joindre cinq tables à la main, aucune date ni aucun prix ne se
comparait comme tel, aucun contrôle ne tournait sur l'état, et le jeu de
questions n'était calculé que depuis le bronze. Le PRD v0.7 (§6.5) demande des
colonnes typées sans deviner une valeur illisible, une fiche médicament et
une disponibilité courante à un instant, des contrôles de qualité classés, et
le jeu de questions recalculé depuis le gold. Mesures du §0 (silver du jeu de
démo, état au 27/10/2026 00:17:12, 164 086 versions) : **une seule** valeur
illisible (`EU/1/17/1235/`, numéro d'autorisation européenne du CIS 61096104) ;
63 CIS dans plusieurs groupes génériques, jusqu'à 37 présentations et 44 avis
SMR par CIS ; 5 562 CIS cités ailleurs et absents de `CIS_bdpm.txt` ; la fiche
de tout le jeu en SQL DuckDB à 552-705 Mo résidents selon le nombre de fils,
en PyArrow à 318 Mo.

## Décision

**Calculé à la demande** (`pharmaflux.gold`). Le gold est une fonction du
silver et d'un instant : aucune table stockée, rien à garder cohérent avec
l'histoire du silver. Il ne lit ni le bus, ni les événements, ni le bronze
(seule exception : la vérification des questions, dont la référence reste le
bronze). Les commandes : `gold etat`, `gold fiche` (`jsonl` ou `texte`),
`gold disponibilite`, `gold alternatives`, `gold qualite`, `gold sql` (la
barrière de `silver sql`, sans la modifier, sur les entités typées et les
trois vues) ; `questions verifier --entrepot`. Imports paresseux, comme le
silver.

**Les instants.** Ceux de `silver etat` (UTC à la seconde, avec un décalage,
ou une date seule) ; par défaut, la dernière observation du silver. Le gold
garde la règle de validité du silver (début inclus, fin exclue). Le **jour**
d'un instant est sa date UTC : c'est lui que le gold compare aux dates de la
source (informations importantes en cours, arrêt annoncé). Les vues et les
contrôles **refusent** un instant où l'une des onze entités n'est pas encore
observée, en donnant le premier instant où elles le sont toutes : avant de
lire le fichier de disponibilité, la vue dirait « aucun signalement » de
toutes les présentations, ce qui serait faux. Le recalcul des questions
n'applique pas cette règle : une question ne lit que la section de son
entité, et il suffit que l'instant soit dans la fenêtre de celle-ci (entre
sa première observation et la dernière du silver).

**Le typage part des anomalies, jamais de la valeur seule**
(`gold/typage.py`). Une valeur vide est nulle. Une valeur dont la version
porte, pour cette colonne, une règle de lisibilité est brute : elle est
nulle, et `colonnes_illisibles` nomme la colonne ; la brute reste dans le
silver avec sa règle. Sinon la valeur est canonique et se convertit par une
règle stricte sur sa forme : `texte`, `code`, `url`, `enumeration` en
`string` (un CIS reste une chaîne) ; `entier` en `int64` (18 chiffres au
plus) ; `decimal` en `decimal128(18, d)`, `d` venant du contrat (un prix reste
exact, jamais `1.1600000000000001`) ; `date` en `date32`, avec un aller-retour
par `strftime`, parce que `strptime` d'Arrow lit le 30 février comme le
2 mars ; `booleen` en `bool` ; `liste` en `list<T>`, découpée sur le
séparateur du contrat, un élément refusé vidant toute la liste, une valeur
vide donnant une liste nulle. Une valeur canonique que la règle refuse rompt
un invariant de la normalisation : elle est comptée (contrôle 3, bloquant),
jamais vidée en silence. Colonnes de version gardées : `identite`, `rang`,
`date_source`, `debut_validite`, `archive_ouverture`, `version_contrat`,
`anomalies`. **`fin_validite`, `id_fermeture` et `archive_fermeture` sont
écartées** : à un instant passé, elles diraient ce qu'on a appris après lui.

**Les vues métier** (`gold/vues.py`), construites en PyArrow et en Python
(tri, décalages de liste, `take` par index), pas en SQL : la fiche entière
tient en 415 Mo au lieu de 552-705.
- **La fiche médicament** : une ligne par CIS cité par au moins une entité,
  avec `dans_referentiel` (21 445 fiches sur le jeu, dont 5 562 partielles) ;
  colonnes plates de la spécialité et du MITM, sections en `list<struct>`
  triées de façon stable (présentations, composition, groupes génériques,
  conditions, avis SMR et ASMR, signalements, informations en cours au jour
  UTC, bornes incluses, fin vide = en cours) ; **tous** les avis SMR et ASMR,
  du plus récent au plus ancien, avec leurs liens (les fichiers n'ont pas
  d'identifiant d'indication : « le plus récent par indication » obligerait
  à deviner l'indication dans le libellé) ; `occurrences` pour les lignes
  répétées ; `provenance` par fichier (date de la source, connu depuis).
- **La disponibilité courante** : une ligne par présentation et par ligne de
  signalement, selon une **priorité écrite** : une ligne en cours la vise,
  directement ou par sa spécialité (ligne sans CIP13, `portee = specialite`)
  → `declare` ; sinon une ligne l'a visée et a été retirée du fichier au plus
  tard à l'instant → `fin_de_publication`, avec la fermeture la plus récente et
  son dernier statut (ADR 0003 : l'ANSM ne publie plus la fiche, ce n'est pas
  une remise à disposition ; seules les versions fermées au plus à l'instant
  sont lues) ; sinon → `aucun_signalement`, qui ne veut pas dire
  « disponible ». S'y ajoutent `occurrences`, `presentation_connue` (une
  ligne qui ne vise aucune présentation connue garde sa ligne),
  `debut_a_venir` (`date_debut > jour`, sans autre interprétation).
- **Les alternatives** : une ligne par groupe générique et présentation d'une
  spécialité du groupe (une ligne sans présentation pour une spécialité qui
  n'en a pas), avec sa disponibilité ; triées par `numero_tri`, l'ordre de la
  BDPM. Elles ne classent ni ne recommandent rien.
- **Le texte de la fiche** (`gold fiche --format texte`) est déterministe et
  lisible par un humain ; il dit « observée depuis …, source du … ». Il sert
  au README et à la ligne de commande, et **n'engage pas** le format des
  fragments du Lot 3.

**Les contrôles de qualité** (`gold/qualite.py`). **La règle qui classe** :
bloquant quand le contrôle vérifie un invariant que la chaîne garantit
(contrats, garde-fou de volume, SCD2, normalisation) ; mesuré quand il
constate un fait de la source, montré, jamais corrigé ni absorbé, affiché
même à 0. Bloquants : 1 unicité des clés déclarées uniques ; 2 une version
par identité ; 3 valeurs canoniques non typables ; 4 entité vide après sa
première observation. Mesurés : 5 présentations dont le CIS est absent des
spécialités ; 6 CIS des autres fichiers absents des spécialités ; 7
spécialités sans présentation ; 8 CIP13 de disponibilité absents des
présentations ; 9 signalements sans CIP13 dont la spécialité n'a aucune
présentation ; 10 dossiers SMR et ASMR sans lien ; 11 lignes répétées des
fichiers sans clé ; 12 valeurs illisibles par colonne ; 13 autres anomalies
de valeur par colonne ; 14 volumes, écart à l'état juste avant le dernier
changement de l'entité (le seul volume bloquant est le vide, contrôle 4).
Code 2 si un bloquant tombe.

**Les questions depuis le gold** (`gold/questions.py`). L'instant est
l'horodatage de l'archive citée ; les lignes attendues, brutes, sont
normalisées par le contrat puis typées ; la comparaison se fait en
multiensemble (le gold ne connaît pas l'ordre du fichier ; le bronze, lui, le
vérifie). Route par la fiche (CIS ou CIP13), par les alternatives (groupe) ou
par les colonnes typées. Avec `--entrepot`, une discordance, ou une question
hors de la fenêtre du silver, donne le code 2, et les deux calculs sont
affichés. **`make gold`** enchaîne `gold qualite` puis `questions verifier
--racine demo/archive --entrepot data/demo/lakehouse` ; la CI le lance dans
le job `integration`, après `make silver`.

**Les vues sont vérifiées contre une référence indépendante** : pour chacune,
une requête DuckDB écrite à part (`tests/references_gold.py`, la fermeture
lue dans toutes les versions du silver et filtrée en SQL) doit rendre le même
multiensemble de lignes, listes comprises, sur les fixtures à trois instants
et sur un échantillon fixe de 28 CIS du jeu (ceux des questions et les cas
limites).

## Conséquences

- Le PRD §6.5 et l'annexe B sont tenus sur le jeu de démo : les quatorze
  contrôles sans bloquant, et **les 25 questions concordantes** depuis le
  gold, 24 par une vue métier, 1 par les colonnes typées.
- Mesures (Mac arm64, jeu de démo, 29/10/2026) : `gold qualite` 1,3 s et
  312 Mo ; `gold fiche --cis` 1,4 s et 421 Mo ; `gold fiche --tout` 3,7 s et
  415 Mo ; `gold disponibilite`, `alternatives`, `sql` 1,4 s et 411-420 Mo ;
  `questions verifier --entrepot` 9,0 s et 452 Mo (sept instants). Toutes
  sous le seuil de 512 Mo de l'ADR 0009. Le test de référence sur le jeu, seul,
  monte à 524 Mo pour tout le processus (rejeu, silver, gold, référence) : le
  seuil vaut pour les commandes, pas pour la suite de tests.
- Coût : chaque commande recalcule les vues (environ 1 s) ; aucune dépendance
  nouvelle ; 35 tests de plus (500 → 535).
- À surveiller : la mémoire quand la copie du Mac s'allongera (le gold
  charge l'état des onze entités, pas l'histoire ; seule la fin de
  publication lit les versions fermées de la disponibilité) ; un statut de
  disponibilité inconnu (`valeur_inconnue`) qui viderait la colonne : le
  contrôle 12 le montre.

## Limites

- **Une illisibilité qui égale la forme canonique de la valeur précédente ne
  se voit pas.** Si la source écrit `24.34` là où elle écrivait `24,34`, la
  détection (ADR 0006) compare les valeurs normalisées, trouve `24.34` des
  deux côtés et ne produit aucun événement. Le silver garde la version sans
  anomalie, le gold type `24.34`, et ni le contrôle 12 ni `silver verifier` ne
  comptent cette illisibilité. C'est le cas même que le typage par les
  anomalies veut empêcher, qui revient par la détection. Le corriger demande
  de comparer aussi les règles d'anomalie d'une ligne, donc de changer le
  Lot 1 : proposé pour une mission à venir (`pr.md` de la mission 06).
- **La date que cite une fiche est celle de la version** : `date_source` vient
  de l'archive qui a ouvert la version. Une valeur inchangée depuis le 24/10
  cite la source du 23/10, même si le fichier a été republié depuis : une
  archive retenue sans changement ne laisse aucune trace dans le silver. La
  fiche le dit (« observée depuis …, source du … ») ; la date du dernier
  fichier retenu par entité est une proposition hors mission.
- **Le gold ne lit pas la file des échecs** et ne type pas une valeur que le
  contrat ne déclare pas (le taux de remboursement reste l'énumération
  `65%` ; un nombre sera une colonne dérivée du Lot 4, ou une nouvelle version
  de contrat).

## Options écartées

| Option | Pourquoi pas |
|---|---|
| une table Iceberg du gold courant | une écriture de plus par lot du silver, un état à tenir synchrone, et « l'état à une date » perdu pour le gold |
| typer par un essai de conversion (`CAST`) | une brute illisible qui a l'air canonique (`12.50` pour `12,50`) serait devinée |
| `float64` pour les décimaux | un prix deviendrait `1.1600000000000001` ; `decimal128` est exact |
| `dictionary` pour les énumérations | rien n'est stocké, le Parquet dictionne déjà ; une gêne pour les concaténations et DuckDB |
| garder `fin_validite` dans le gold | à un instant passé, elle dit ce qu'on a appris après |
| la fiche en SQL DuckDB | 552 à 705 Mo résidents sur le jeu, au-dessus du seuil ; elle reste la référence des tests |
| le plus récent avis par indication | pas d'identifiant d'indication dans les fichiers : il faudrait le deviner dans le libellé |
| une ligne par présentation avec un statut résumé | plusieurs statuts sur une présentation (BEFIZAL L.P.) : résumer, c'est en dire plus que l'ANSM |
| une fiche seulement pour les CIS du référentiel | 5 562 CIS invisibles pour le Lot 3, alors que la « réponse avec réserve » (annexe B) en a besoin |
| les vues à tout instant, même avant d'avoir lu un fichier | « aucun signalement » affirmé avant d'avoir lu la disponibilité |
| les vues gold dans `silver sql` | le silver y est l'histoire entière, le gold un instant : les mêmes noms y diraient deux choses |

## Références

PRD v0.7 §2.1, §6.2, §6.3, §6.5, §7.1, §9, annexe B · ordre de mission 06 et
addendum 1 · `docs/rapports/mission-06/points-a-trancher.md`, `palier-1.md`,
`palier-2.md`, `palier-3.md` · contrôles des paliers · ADR 0002, 0003, 0005,
0006, 0009 · `src/pharmaflux/gold/` · `tests/test_gold*.py`,
`tests/references_gold.py` · `Makefile` (`gold`, `fiche`),
`.github/workflows/ci.yml` (job `integration`).
