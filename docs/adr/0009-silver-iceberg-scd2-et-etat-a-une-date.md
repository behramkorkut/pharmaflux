# ADR-0009 — Le silver : tables Iceberg locales, versions SCD2 sur la date d'observation, positions du bus dans le commit, vérification contre l'archive

**Statut :** accepté (mission 05) · **Date :** 2026-10-28 · **Mission :** 05 ·
s'appuie sur les ADR 0006 (événements) et 0007 (bus)
**Remplace / remplacé par :** —

## Contexte

Le Lot 1 fait de chaque changement de la BDPM un événement daté, publié une
fois sur Redpanda et vérifié (ADR 0006, 0007, 0008). L'objectif 2 du PRD
(« que savait-on le JJ/MM à HH:MM ? ») n'est pas tenu : l'histoire est dans
les fichiers d'événements et sur le bus, rien ne l'interroge, et l'indicateur
« reconstruction de l'état à une date passée » n'a pas de mesure. Le PRD
(§6.5) arrête une table Iceberg par entité, en Parquet, dans un entrepôt
local lu par DuckDB, des versions SCD2 **sur la date d'observation**, les
valeurs en chaînes (le typage est au gold, mission 06), un consommateur du
bus idempotent, et une vérification contre le snapshot normalisé de chaque
archive. Contraintes : aucun service (ni catalogue, ni stockage objet, ni
image Docker, ni extension DuckDB téléchargée), tout sur le Mac, le colima
partagé avec Alamel, les tests unitaires hors réseau. Mesures du §0 (maquette,
jeu de démo : 164 106 événements, 164 086 versions ouvertes à la fin) :
silver construit en 6,5 s, vérification conforme 18/18 en 10 s, mémoire
résidente de 276 à 610 Mo selon l'allocateur d'Arrow ; les trois bibliothèques
importées pèsent 102 Mo avant toute donnée ; `duckdb 2.0.0` et `sqlalchemy
2.1.6`, publiées sept jours avant l'ordre, trop neuves.

## Décision

**Bibliothèques** (`pyproject.toml`) : `pyiceberg[sql-sqlite] 0.12.0`,
`pyarrow 26.0.0`, `duckdb 1.5.6`, `sqlalchemy 2.0.54` (le catalogue) ;
`pyarrow-stubs` en dev (`mypy --strict` passe sans `type: ignore`). **Règle
des deux semaines** : un paquet ajouté ou mis à jour a au moins deux semaines
le jour du verrou, appliquée par `[tool.uv] constraint-dependencies` (bornes
hautes commentées : `duckdb<2`, `sqlalchemy<2.0.55`, `cachetools<7.2.2`,
`python-dateutil<3`, `tzdata<2026.6`), sans `exclude-newer` global, qui aurait
fait redescendre `ruff`, `pluggy`, `certifi` et `ast-serialize` déjà
verrouillés. **Ces plafonds sont temporaires** : ils bloquent aussi les
correctifs de sécurité ; à chaque mission qui touche aux dépendances, on les
remonte jusqu'à la dernière version qui a deux semaines, et le rapport du
palier donne les paquets ajoutés ou changés avec leur date de publication.
Les bibliothèques ne s'importent que dans les commandes `silver` (imports
paresseux, testés en sous-processus) ; `pharmaflux --version` reste à 48 Mo.
L'**allocateur système d'Arrow** est posé par `ARROW_DEFAULT_MEMORY_POOL=system`
avant le premier import de PyArrow (`setdefault`, l'utilisateur garde la
main) : 100 à 250 Mo résidents de moins que jemalloc sur le jeu.

**Entrepôt et catalogue** (`silver/entrepot.py`). Un dossier sous `data/`,
hors de git (`data/lakehouse` par défaut, `data/demo/lakehouse` pour la
démo) : `catalogue.sqlite` à la racine (le `SqlCatalog` de PyIceberg sur
SQLite, le seul catalogue persistant sans serveur), les tables dessous
(`bdpm/presentations/…`). Le commit est atomique : le nouveau `metadata.json`
est écrit, puis la ligne SQLite mise à jour **si elle pointe encore vers
l'ancien**. PyIceberg veut un entrepôt `file://` absolu, qu'il écrit dans
chaque métadonnée : un entrepôt déplacé ne se relit pas, on le rebâtit
(`make rebatir` pour la démo). Cet URI est le chemin **brut** derrière
`file://`, pas `Path.as_uri()` : PyIceberg 0.12.0 prend le chemin de l'URI à
la lettre, et l'encodage d'un espace ou d'un accent (`Mes%20projets`) lui
ferait écrire dans un dossier voisin, hors de l'entrepôt (relecture 1). Un
`#` ou un `?` dans le chemin, qu'il lirait comme la fin de l'URI, est refusé
avant toute écriture ; aucune commande n'efface un entrepôt,
`construire` refuse un dossier non vide et le nomme. Chaque table porte
`pharmaflux.entite`, `pharmaflux.version_contrat`, `pharmaflux.origine`
(`fichiers` ou `bus`) et, pour le bus, `pharmaflux.grappe` et
`pharmaflux.positions`. Pas de MinIO : celui du colima est à Alamel.

**Schéma d'une table** (`silver/schema.py`), une table par entité,
identifiant Iceberg `bdpm.<entite>` : les colonnes du contrat, dans son
ordre, toutes en chaînes (la valeur de l'événement, canonique ou brute), puis
treize colonnes de version : `identite` (la clé JSON compacte du message pour
un fichier à clé, `<empreinte>#<rang>` sinon), `empreinte_ligne`, `rang`,
`date_source`, `debut_validite` et `fin_validite` (`timestamptz` à la
seconde, UTC, la `date_observation` des événements qui ouvrent et ferment ;
fin nulle = version ouverte, **borne de fin exclue**), `id_ouverture`,
`id_fermeture`, `archive_ouverture`, `archive_fermeture`, `version_contrat`,
`etat_initial`, `anomalies` (`list<struct<colonne, regle>>`). Aucun
partitionnement, aucun tri : 164 000 versions, 21 Mo de Parquet. Un
changement de version du contrat fait **refuser** (rebâtir) : la forme des
événements change avec lui.

**Application d'un lot** (`silver/application.py`, `appliquer_lot`), la
même fonction pour le bus et pour les fichiers : les doublons sont ignorés
(un `id` déjà en ouverture ou en fermeture, dans la table ou dans le lot) ;
une `creee` ouvre une version ; une `modifiee` ferme la version ouverte de
son identité et en ouvre une autre ; une `supprimee` ferme ; pour un fichier
ligne à ligne, les rangs se comptent comme dans `appliquer` (ADR 0006).
Refus (`FluxIncoherent`, rien du lot n'est écrit) : fermante sans version
ouverte, `creee` sur une identité ouverte, rang incohérent, plusieurs versions
ouvertes pour une identité, autre version de contrat. **Une transaction
Iceberg par lot** : `set_properties` (la position), `delete` des versions
fermées par leur `id_ouverture`, `append` des versions fermées réécrites et
des versions ouvertes ; PyIceberg écrit en copie, le fichier Parquet qui
portait une version fermée est réécrit sans elle (0,1 s pour quelques
lignes), et un commit qui ferme produit deux snapshots (`delete`, `append`)
dans un seul `metadata.json`. **L'ordre par clé du bus suffit** : toutes les
versions d'une identité, et tous les rangs d'une même empreinte, ont la même
clé de message, donc une seule partition dans l'ordre du temps ; entre deux
identités, rien ne dépend de l'ordre. Lot de 10 000 par défaut (`--lot`).

**Depuis les fichiers** (`silver construire`) : les fichiers de
`<sortie>/evenements/<entite>/` dans l'ordre des noms, le nom du fichier dans
le résumé du snapshot. **Depuis le bus** (`silver consommer`,
`silver/consommation.py`) : chaque topic lu depuis la **position** gardée
dans les propriétés de sa table (par partition : l'offset suivant à lire et
l'`id` du dernier message appliqué), toutes les partitions à la fois jusqu'aux
offsets de fin lus au départ, un commit par lot qui porte la position et la
plage d'offsets du lot dans le résumé du snapshot. Il n'y a pas de fenêtre
entre le silver et sa position : après une coupure à n'importe quel point
(avant le `metadata.json`, entre lui et SQLite, après le commit), la reprise
relit le lot interrompu et donne le même silver. Aucun groupe de
consommateurs, aucun commit sur le courtier, rien d'écrit sur le bus, pas de
`--continu`. Refus avant toute écriture : silver construit depuis les fichiers
(sans position), position au-delà de la fin ou avant le début d'une
partition, message à `offset − 1` qui ne porte pas l'`id` gardé (le bus n'est
pas celui qui a construit le silver), bus vide ; un identifiant de grappe
différent donne un avertissement, parce qu'un bus rebâti à l'identique
produit les mêmes offsets et les mêmes `id`, et le silver est juste. Un
message qui n'est pas un événement v1 arrête tout sans rien écrire et n'est
jamais sauté : la voie est de rebâtir le bus depuis les fichiers.

**« État à une date »** (`silver etat`) : les versions dont
`debut_validite <= a` et (`fin_validite` nulle ou `> a`), la règle entière
poussée à PyIceberg ; instants en UTC à la seconde, sous trois formes
seulement (`AAAA-MM-JJThh:mm:ssZ`, avec un décalage `±hh:mm`, ou une date
seule qui vaut minuit UTC) : refus d'un instant sans fuseau, d'une fraction
même nulle, d'une heure sans les secondes, de la forme compacte ; avant la première observation, aucune version ;
après la dernière, les versions ouvertes ; code 0 et un message dans les deux
cas. Le temps de la connaissance est **l'horodatage de l'archive**, à la
seconde, pas celui du passage de collecte (l'archive du 27/10 est à
00:17:12, le passage à 00:17:08). **SQL** (`silver sql`) : DuckDB ne reçoit
que des jeux de données Arrow (jamais un chemin), naît sans accès externe,
sans extension ni téléchargement, en UTC, puis verrouillé ; une requête à la
fois, seulement `SELECT` ou `EXPLAIN`. Pas d'`allowed_directories` : un
dossier autorisé l'est aussi en écriture (`COPY … TO` y passait).
**Comparaison** (`silver comparer`) : toutes les colonnes de données et de
version de chaque table, `EXCEPT ALL` dans les deux sens ; exclus parce
qu'ils ne peuvent pas être égaux, les snapshots, les fichiers Parquet et les
propriétés de table.

**Vérification contre l'archive** (`silver verifier`) : les archives et leurs
verdicts viennent des bilans de `evenements`, jamais des événements ; le
snapshot d'une archive retenue ou confirmée est recalculé depuis le bronze et
réduit à une empreinte par identité (valeurs triées, occurrences, la
réduction de `verifier-bus`), l'état du silver à son horodatage est réduit
de même et comparé ; une archive écartée doit laisser l'état du dernier
retenu ; une archive en attente est dite, non vérifiée. S'y ajoutent les
invariants du SCD2 en DuckDB : une seule version ouverte par identité, aucun
chevauchement de validités, `fin > debut`, identifiants d'événements uniques
en ouverture et en fermeture, comptes égaux à ceux des bilans (le premier
snapshot : une `creee` par ligne bien formée). Code 2 à la moindre
différence. **`make silver`** enchaîne `consommer` puis `verifier` sur le jeu
de démo après `make demo` ; la CI le lance dans le job `integration`.

**Ce que le silver ne fait pas** : typer les colonnes, calculer des vues
métier, contrôler la qualité (mission 06) ; lire la file des échecs ; suivre
le bus en continu ; tourner sur le VPS (la cible des 256 Mo ne vaut pas pour
lui en v1 : il tourne là où est le bus, sur le Mac).

## Conséquences

- L'objectif 2 du PRD est tenu sur le jeu de démo : `make silver` finit par
  une vérification conforme sur les 18 archives retenues (et les 4 écartées),
  et `silver etat` répond à la seconde.
- Mesures (Mac arm64, jeu de démo, 28/10/2026) : `construire` 9,7 s et
  297 Mo ; `consommer` 164 106 messages en 12,9 s et 357 Mo, puis 0,3 s sans
  rien de nouveau ; `verifier` 22/22 en 10,3 s et 341 Mo ; `etat` 182 Mo ;
  `sql` 173 Mo ; `comparer` 442 Mo. Seuil d'alerte : 512 Mo par commande.
- Coût : 24 paquets de plus dans le verrou (233 Mo de `site-packages`, dont
  PyArrow 123) ; la suite de tests passe de 36 s à 2 min (le jeu entier
  construit et vérifié une fois par session) ; les fichiers Parquet
  s'accumulent par lot (27 pour le jeu), sans compactage à ces volumes ;
  les fichiers de métadonnées orphelins d'un commit interrompu ne sont pas
  nettoyés.
- À surveiller : le nombre de fichiers et de snapshots par table (affiché par
  `verifier`) ; la mémoire de `comparer` et de `consommer` quand la copie
  s'allongera ; les plafonds de `constraint-dependencies`, à remonter à
  chaque mission qui touche aux dépendances ; la cale des tests de reprise
  sur `SqlCatalog._write_metadata`, qui cassera à une montée de version de
  PyIceberg, à dessein ; la question D.1 (un `down -v` change-t-il
  l'identifiant de grappe), tranchée au palier 3 de la mission 05.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| un catalogue REST, Hive, Glue ou PostgreSQL | un service ; le PRD veut un entrepôt local sans rien à lancer |
| `InMemoryCatalog` ou `StaticTable` pour écrire | rien ne survit au processus pour le premier ; le second ne lit que |
| les snapshots Iceberg comme axe du temps | ils datent l'écriture, qui diffère de l'observation dès qu'on rejoue (PRD §6.5) |
| typer les colonnes du silver | il faudrait choisir quoi faire d'une valeur illisible ; c'est le gold |
| `upsert` de PyIceberg pour fermer une version | une jointure de toute la table pour des versions connues par leur `id_ouverture` |
| réécrire la table entière à chaque lot | 20 898 lignes relues pour en toucher 7 |
| `exclude-newer` global dans uv | ferait redescendre quatre paquets déjà verrouillés, dont `ruff` |
| l'extension `iceberg` de DuckDB | se télécharge à la première utilisation ; les Parquet se lisent sans elle |
| `allowed_directories` limité à l'entrepôt pour `silver sql` | un dossier autorisé l'est en écriture : `COPY … TO` y passait |
| les positions dans un groupe de consommateurs Kafka | une trace sur le courtier et une fenêtre entre le commit Kafka et le commit Iceberg |
| les positions dans un fichier à côté de l'entrepôt | la même fenêtre, et un fichier de plus à garder cohérent |
| sauter un message illisible sur le bus | une version perdue en silence ; le bus v1 ne doit porter que du v1 |
| l'identifiant de grappe en refus | un bus rebâti à l'identique serait refusé alors que le silver est juste ; les `id` décident |
| une option qui efface l'entrepôt | une commande qui supprime un dossier de données n'a pas sa place ici ; `make rebatir` est explicite |
| `--continu` | pas de flux vivant à suivre avant le Lot 5 ; proposé dans `pr.md` |

## Références

PRD v0.6 §2.1, §2.2, §6.5, §7.1, §9, §10.1 · ordre de mission 05 et
addendum 1 · `docs/rapports/mission-05/points-a-trancher.md`, `palier-1.md`,
`palier-2.md`, `palier-3.md` · contrôles des paliers · ADR 0006, 0007, 0008 ·
`src/pharmaflux/silver/`, `src/pharmaflux/bus/client.py` (`LecteurKafka`) ·
`tests/test_silver*.py` · `Makefile` (`silver`, `etat`),
`.github/workflows/ci.yml` (job `integration`).
