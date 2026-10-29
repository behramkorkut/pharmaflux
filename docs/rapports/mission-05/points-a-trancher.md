# Mission 05 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Fable 5.1) · **À :** IeC, beko · **Date :** 28/10/2026
**Branche :** `mission-05-silver-et-etat-a-une-date` (sommet `cfc1fea`, identique
à `main`) · **Ordre lu sur `main`** (`cfc1fea`), après `CLAUDE.md`,
`docs/agents/processus.md` et le PRD v0.6 (§2, §4 Lot 2, §5, §6.3 à 6.5,
§7.1, §9, §10.1).

**Ce que j'ai lu, et comment.** Le code des missions 02 à 04
(`evenements/`, `bus/`, `demo/`, `cli.py`), les ADR 0006 à 0008, `pr.md` et
le contrôle final de la mission 04, `demo/README.md`, le `Makefile`, la CI,
`pyproject.toml` et `uv.lock`, le garde-fou. Les mesures : PyPI interrogé
(métadonnées JSON, pas de source de données) ; un **venv jetable dans le
dossier temporaire de la session** avec `pyiceberg[sql-sqlite] 0.12.0`,
`pyarrow 26.0.0`, `duckdb 1.5.6` et une installation de `pharmaflux` depuis
le dépôt, pour y lancer trois scripts de mesure (hors dépôt) sur les
événements du jeu de démo, calculés dans ce même dossier par `pharmaflux
evenements --racine demo/archive`. **Aucune commande `docker`, `colima` ni
`make`, aucune requête vers les sources, rien d'écrit dans le dépôt, dans
`data/` ni dans `~/pharmaflux-data` (lue pour la comparer au jeu), aucun refus
du garde-fou. Rien n'a été codé** : les scripts de mesure sont des brouillons,
pas le code de la mission.

**Lecture rapide, les constats qui pèsent sur l'ordre :**

1. **La copie du Mac est le jeu de démo.** `~/pharmaflux-data` s'arrête au
   passage `20261027T151708Z`, avec les mêmes 22 archives TSV : la mesure
   « sur plus long que le jeu » (§0 J) n'existe pas encore ; elle viendra avec
   le prochain rapatriement.
2. **Le jeu donne 164 106 événements** (164 096 `creee`, 10 `supprimee`),
   donc **164 086 versions ouvertes** à la fin, 18 archives retenues sur 22 ;
   rejeu 9,6 s, 185 Mo résidents (inchangé depuis la mission 04).
3. **PyArrow pèse 123 Mo installés et 33 Mo résidents importé** ; les trois
   bibliothèques importées ensemble, 102 Mo avant la première ligne de
   données. `pharmaflux --version` pèse 37 Mo aujourd'hui : les imports du
   silver doivent être **paresseux**, dans les seules commandes `silver`.
4. **Le silver SCD2 du jeu entier se construit en 6,5 s** depuis les
   fichiers d'événements (27 commits Iceberg, 21 Mo de Parquet), et **la
   vérification contre le bronze est conforme 18/18 en 10 s**, sur une
   maquette de mesure. Fermer quelques versions coûte 0,1 s : la réécriture
   du fichier Parquet qui les porte.
5. **La mémoire résidente est le point dur** : 276 à 406 Mo pour la
   construction, 321 à 610 Mo construction et vérification enchaînées, selon
   l'allocateur d'Arrow (point J). Rien de tout cela ne tient sous 256 Mo.
6. **Deux versions trop récentes** à la date de l'ordre : `duckdb 2.0.0`
   (21/10) et `sqlalchemy 2.1.6` (21/10). Je propose `duckdb 1.5.6` (28/09)
   et `sqlalchemy 2.0.46` (21/01), et une règle d'`uv` qui fait respecter les
   deux semaines à toute la résolution (point A).
7. **L'horodatage d'une archive n'est pas celui du passage** : l'archive du
   27/10 est `20261027T001712Z`, le passage `20261027T001708Z`. Le temps de
   la connaissance est celui de l'archive, à la seconde (points F et G).

## A. Les bibliothèques et le catalogue

**Versions proposées** (PyPI interrogé le 28/10/2026 ; roues CPython 3.12,
tailles des fichiers `.whl`) :

| paquet | version | publiée le | macOS arm64 | Linux x86_64 (manylinux) | remarque |
|---|---|---|---|---|---|
| `pyiceberg[sql-sqlite]` | **0.12.0** | 01/09/2026 | 568 Ko | 781 Ko (`_2_28`) | `py.typed` ; exige Python ≥ 3.10 |
| `pyarrow` | **26.0.0** | 09/10/2026 (19 jours) | 36,3 Mo | 53,9 Mo (`_2_28`) | pas de `py.typed` ; exige Python ≥ 3.11 |
| `duckdb` | **1.5.6** | 28/09/2026 | 15,5 Mo | 21,6 Mo (`_2_26`/`_2_28`) | `py.typed` ; `2.0.0` du 21/10 a 7 jours : refusée |
| `sqlalchemy` (catalogue SQL) | **2.0.46** | 21/01/2026 | 2,2 Mo | 3,3 Mo | `2.1.6` du 21/10 a 7 jours : refusée |

Si l'IeC préfère une marge plus large sur PyArrow, `25.0.1` (10/08/2026,
35,9 et 50,1 Mo) convient aussi ; PyIceberg 0.12.0 demande seulement
`pyarrow ≥ 18`. La maquette a tourné avec 26.0.0 sans avertissement.

**Ce que ces quatre paquets tirent** : 23 paquets nouveaux dans `uv.lock`
(32 aujourd'hui), dont `pydantic`, `requests` (à côté de `httpx`, pour le
catalogue REST que nous n'utilisons pas), `fsspec`, `mmh3`, `pyroaring`,
`zstandard`, `tenacity`, `strictyaml`, `click`. Installés : 233 Mo de
`site-packages`, dont PyArrow 123, SQLAlchemy 17, pydantic 8. Quatre
transitifs résolus aujourd'hui ont moins de deux semaines (`python-dateutil
3.0.0` et `sqlalchemy 2.1.6` du 21/10, `cachetools 7.2.6` du 26/10, `tzdata
2026.6` du 28/10). **Proposition** : `[tool.uv] exclude-newer =
"2026-10-14"` dans `pyproject.toml`, qui fait respecter « au moins deux
semaines » à toute la résolution, transitifs compris, et se relit dans l'ADR
0009 ; la date avance à chaque mission. À défaut, j'épingle `sqlalchemy<2.1`
et je laisse les trois autres.

**Le catalogue.** PyIceberg 0.12 offre, sans serveur : `SqlCatalog`
(SQLAlchemy sur SQLite ou PostgreSQL), `InMemoryCatalog` (un `SqlCatalog`
sur `sqlite:///:memory:` : rien ne survit au processus), et
`StaticTable.from_metadata` (lecture seule d'un `metadata.json`, sans
catalogue). Les autres (REST, Hive, Glue, DynamoDB, BigQuery) sont des
services. **Avis : `SqlCatalog` sur un fichier SQLite dans l'entrepôt**
(`data/lakehouse/catalogue.sqlite`, entrepôt `file://<chemin absolu>`). C'est
le seul chemin d'écriture persistant sans service, et son commit est
**atomique** : le nouveau `metadata.json` est écrit, puis la ligne de la
table est mise à jour **si et seulement si** elle pointe encore vers
l'ancien (`UPDATE … WHERE metadata_location = ancien`, relu dans
`catalog/sql.py`) ; un second écrivain lève `CommitFailedException`. Coût :
SQLAlchemy (17 Mo installés, 2 à 3 Mo de roue). `StaticTable` reste utile
pour relire une table sans ouvrir le catalogue (tests, `etat`), pas pour
écrire. Ce que la maquette a vérifié : création de 11 tables, 27 commits,
rechargement, `metadata.json` numérotés (`00000-…` à `00015-…`), rien d'autre
que le dossier de l'entrepôt.

**Lecture par DuckDB sans l'extension `iceberg`.** Vérifié : avec
`autoinstall_known_extensions = false` et `autoload_known_extensions = false`
à la connexion, `iceberg_scan` répond « not in the catalog, but it exists in
the iceberg extension » sans rien télécharger ; `parquet` et `json` sont
liés statiquement (`duckdb_extensions()` : `STATICALLY_LINKED`). Trois voies
mesurées sur la plus grosse table, `compositions` (32 439 versions, 13,0 Mo
en Arrow, 2,8 Mo en Parquet) :

| voie | temps | ce que ça coûte |
|---|---|---|
| `table.scan().to_arrow()` puis `con.register(nom, arrow)` | scan 0,01 à 0,03 s, requête < 5 ms | la table entière en mémoire (13 Mo Arrow), le filtre Iceberg s'applique avant |
| `DataScan.to_duckdb(nom, connection=con)` (PyIceberg) | 0,01 à 0,03 s | la même chose, en une ligne |
| `read_parquet([chemins de table.scan().plan_files()])` | < 5 ms | rien en mémoire côté Python, DuckDB lit les fichiers ; valable tant qu'il n'y a **aucun fichier de suppression** (copie à l'écriture, point C) |

**Avis** : la première voie pour « état à une date » (le filtre de validité
passe par PyIceberg, qui élague les fichiers par leurs bornes et pousse le
reste à Arrow), la troisième pour une commande SQL libre (point F), avec un
contrôle que `plan_files()` ne rend aucun fichier de suppression. Mémoire :
l'import de DuckDB seul, 38 Mo résidents ; la plus grosse table en Arrow,
13 Mo ; l'ensemble imports compris, 102 Mo avant toute donnée.

**Questions A.1** : `exclude-newer` au 14/10/2026, ou épinglage de
`sqlalchemy<2.1` seul ? **A.2** : PyArrow n'a pas de `py.typed` ; `mypy
--strict` refusera `import pyarrow`. Soit `pyarrow-stubs` en dépendance de
**dev** (ce qui demande ta justification), soit un bloc
`[[tool.mypy.overrides]] module = "pyarrow.*"` avec `ignore_missing_imports`.
Je propose les stubs : ils typent vraiment ce que le silver manipule.

## B. Le schéma d'une table du silver

**Constat.** Un événement porte tout ce qu'une version demande ; un `cle`
vide n'existe pas (les trois fichiers sans clé unique déclarent une clé non
unique). Les 50 noms de colonnes des onze contrats sont en minuscules à
soulignés et **aucun n'entre en collision** avec les colonnes de version
ci-dessous (`rang`, `identite`, `anomalies`, `date_source`… n'y figurent pas).

**Proposition.** Une table par entité, les colonnes du contrat **dans l'ordre
du contrat**, toutes `string` optionnelles (la valeur de l'événement, forme
canonique ou brute), puis les colonnes de version :

| colonne | type Iceberg | sens |
|---|---|---|
| `identite` | `string`, requis | fichier à clé : l'objet JSON `cle` compact à clés triées, **égal à la clé du message** ; fichier ligne à ligne : `<empreinte_ligne>#<rang>` |
| `empreinte_ligne` | `string`, requis | sha256 de la ligne normalisée (celui de l'événement) |
| `rang` | `int`, requis | occurrence (1 sauf doublon) |
| `date_source` | `string` | `date_source` de l'événement qui ouvre, AAAA-MM-JJ ou nul |
| `debut_validite` | `timestamptz`, requis | `date_observation` de l'événement qui ouvre |
| `fin_validite` | `timestamptz` | `date_observation` de l'événement qui ferme ; nul = version ouverte |
| `id_ouverture` | `string`, requis | `id` de la `creee` ou `modifiee` qui ouvre |
| `id_fermeture` | `string` | `id` de la `modifiee` ou `supprimee` qui ferme |
| `archive_ouverture`, `archive_fermeture` | `string` | chemins relatifs des deux archives, comme l'événement |
| `version_contrat` | `string`, requis | celle de l'événement qui ouvre |
| `etat_initial` | `boolean`, requis | la version vient d'une `creee` d'état initial |
| `anomalies` | `list<struct<colonne: string, regle: string>>` | les anomalies de la ligne après (celles de l'événement) |

L'alternative pour `identite` est la chaîne canonique du projet
(`schema.identite_de_ligne`, valeurs jointes par `\x1f`) ; je préfère la
clé du message : lisible, interrogeable en SQL, et un message du bus se
rapproche de sa version sans calcul. Les deux voies de l'identité (clé ou
empreinte et rang) restent celles du PRD §6.3, et `appliquer` du Lot 1 fait
déjà ce rapprochement. Pour un fichier sans clé unique, l'**état à une
date** se réduit comme `appliquer` : empreinte → nombre de versions valides
(les rangs), ce que la vérification compare au snapshot (point G).

**Changement de version du contrat** : la table porte `pharmaflux.entite` et
`pharmaflux.version_contrat` dans ses propriétés ; un événement d'une autre
version fait **refuser** (code 2, « le contrat bdpm.presentations est passé
de v1 à v2 : rebâtis le silver »), comme `evenements --reprendre`. Ni
nouvelle table ni colonnes ajoutées : la forme des événements change avec
le contrat, et le silver se rebâtit en quelques secondes depuis les
fichiers. La colonne `version_contrat` par version reste, pour qu'un
futur rejeu multi-versions soit lisible.

**Partitionnement : aucun**, ni ordre de tri : 164 000 versions, 21 Mo de
Parquet. Un fichier Parquet par lot (point C) ; `compositions` en fait 4 avec
des lots de 10 000. Pas de compactage dans cette mission.

**Noms** : espace de noms `bdpm`, table `presentations` : l'identifiant
Iceberg `bdpm.presentations` est l'identifiant de l'entité et du contrat.
Vues DuckDB du même nom court (`presentations`).

**Question B.1** : `identite` en clé JSON (ma préférence) ou en chaîne
canonique `\x1f` ? **B.2** : `anomalies` en liste de structures (Iceberg et
DuckDB la lisent nativement) ou en chaîne JSON compacte, comme l'événement ?

## C. L'application d'un lot d'événements (SCD2)

**Algorithme**, une fonction `appliquer_lot(table, evenements, positions)`
pour le bus et les fichiers :

1. **Doublons** : un scan de la table filtré `id_ouverture IN ids OR
   id_fermeture IN ids` (deux colonnes) ; tout événement dont l'`id` est déjà
   une ouverture ou une fermeture est **ignoré** et compté. Un lot entièrement
   en doublon ne touche pas aux données ; seule la position avance (point D).
2. **Fermantes** (`modifiee`, `supprimee`) : un scan filtré `identite IN … AND
   fin_validite IS NULL` rend les versions ouvertes ; il doit en rendre
   **exactement une par identité**. La version est réécrite avec
   `fin_validite`, `id_fermeture`, `archive_fermeture` de l'événement.
3. **Ouvrantes** (`creee`, `modifiee`) : une version nouvelle, ouverte. Une
   `creee` dont l'identité a déjà une version ouverte est refusée. Pour un
   fichier ligne à ligne, le rang suit la règle d'`appliquer` : créer le
   rang r demande r − 1 versions ouvertes de la même empreinte, supprimer le
   rang r demande r versions ouvertes ; c'est ce que le scan de l'étape 2
   compte.
4. **Une transaction Iceberg** : `set_properties(positions)`, `delete(id_ouverture
   IN fermées)`, `append(fermées réécrites + ouvertes)`. Un seul commit, un
   seul `metadata.json`.

**Refus** (code **2**, rien de ce lot n'est écrit, les lots précédents
restent, la position ne bouge pas) : `modifiee` ou `supprimee` sans version
ouverte, `creee` sur une identité ouverte, rang incohérent, plusieurs
versions ouvertes pour une identité (le silver est corrompu). Le message
nomme l'entité, le type, l'`id`, l'identité, l'archive et la
`date_observation` de l'événement, et pour le bus le topic, la partition et
l'offset ; puis la voie : rebâtir le silver. C'est la sémantique des
`ValueError` d'`appliquer` (ADR 0006), avec le même vocabulaire.

**L'ordre par clé suffit.** Toutes les versions d'une identité ont la même
clé de message : pour un fichier à clé, c'est la clé ; pour un fichier ligne
à ligne, l'empreinte couvre la ligne entière, donc les colonnes de la clé
déclarée non unique, et deux occurrences d'une même ligne (rangs 1 et 2)
ont la même clé. Donc tous les événements d'une identité, et tous ceux des
rangs d'une même empreinte, sont sur **une partition, dans l'ordre des
fichiers**, qui est l'ordre du temps (le nom d'un fichier commence par
l'horodatage de son archive). Le SCD2 n'a besoin que de cet ordre : fermer
puis ouvrir une identité, dans l'ordre de ses observations. Entre deux
identités, aucune dépendance : une `supprimee` et la `creee` qui la
remplace dans un fichier sans clé (ADR 0006) ont deux identités distinctes,
deux versions indépendantes, et leur ordre relatif ne change ni le silver ni
« l'état à une date », qui ne regarde que les bornes. Le seul ordre
inter-identités qu'`appliquer` exige, celui des rangs d'une même empreinte,
est intra-partition. La **lecture** : comme `verifier-bus`, toutes les
partitions d'un topic assignées ensemble, chacune dans l'ordre de ses
offsets.

**L'écriture dans Iceberg.** PyIceberg n'écrit qu'en **copie à l'écriture**
(aucun fichier de suppression), ce qui garde la voie `read_parquet`
ouverte. Trois façons de fermer une version, mesurées :

| façon | ce qu'elle fait | état initial (164 096 ouvertures) | 2, 1 et 7 fermetures |
|---|---|---|---|
| `overwrite(df, overwrite_filter=In(…))` | supprime puis ajoute, en une transaction | ajout pur : **6,5 s** pour les onze tables en lots de 10 000 (0,04 à 1,4 s par table) | 0,40 s la première fois, puis identique à la ligne suivante |
| transaction `delete(In(…))` + `append` | la même chose, à la main, avec `set_properties` dans le même commit | idem | **0,09 à 0,10 s** : le fichier Parquet de 2,2 Mo qui porte les lignes est réécrit sans elles, un fichier de 12 Ko ajouté ; `total-records` reste 20 898 |
| `upsert(df, join_cols=…)` | lit les lignes jointes, calcule les différences, puis `overwrite` | un ajout aussi sur table vide, mais une jointure de 164 096 lignes pour rien | inutile : les versions à fermer sont connues par leur `id_ouverture` |
| réécriture de la table entière | lire tout, modifier, `overwrite()` | le même ajout | lire et réécrire 20 898 lignes pour en toucher 7 : non |

**Avis** : la transaction `delete` + `append`, parce qu'elle porte aussi la
position (point D). Chaque commit produit **deux snapshots** (un `delete`,
un `append`) dans **un** `metadata.json` : c'est ainsi que PyIceberg écrit,
l'atomicité est celle du commit ; l'ADR le dit pour qu'un lecteur de
`metadata.json` ne s'en étonne pas. Un lot sans fermante est un `append`
seul, un snapshot.

**Taille d'un lot, et ce qui fait un commit** : depuis les **fichiers**, un
lot = un fichier d'événements (une archive comparée), un commit par archive,
le nom du fichier dans le résumé du snapshot ; un fichier vide ne commit
rien. Depuis le **bus**, un lot = ce qu'un cycle de lecture rend, au plus
`LOT = 10 000` messages (mesuré : 27 commits et 32 fichiers Parquet à
10 000 ; 91 commits, 99 fichiers et 11,9 s à 2 000), ou la fin du topic ;
un commit par entité et par lot. Les lots de 10 000 lignes pèsent 0,1 à
0,2 s d'`append`. Les doublons d'un lot (`id` déjà appliqué) sont comptés
et affichés, jamais écrits : la maquette a rejoué le dernier fichier de
`presentations` (7 `supprimee`), 7 doublons, aucun snapshot nouveau.

**Question C.1** : `LOT = 10 000` ? **C.2** : la propriété « exactement une
version ouverte par identité » est-elle à vérifier à chaque lot (un scan de
plus) ou seulement par `silver verifier` (point G) ? Je propose : au lot,
sur les seules identités du lot (c'est le scan de l'étape 2, gratuit) ; sur
toute la table, à la vérification.

## D. Le consommateur du bus

**Commande** : `pharmaflux silver consommer [--entrepot data/lakehouse]
[--courtier …] [--fichier …, répétable] [--lot 10000]`. Il lit chaque topic
d'entité depuis la position connue, toutes les partitions ensemble, applique
par lots (point C), et s'arrête aux offsets de fin lus au départ. Sortie :
une ligne par lot (entité, messages, doublons, ouvertures, fermetures,
positions), un résumé ; codes **1** courtier injoignable, **2** refus
(ci-dessous). Jamais de groupe de consommateurs, jamais de commit
d'offset sur le courtier, jamais d'écriture sur le bus.

**Les positions lues.** Avis : **d'accord avec la proposition de l'IeC**, avec
une précision. La position va dans le **même commit** que les données, en
propriété de **table** (`pharmaflux.positions` : par partition, l'offset
suivant à lire et l'`id` du dernier message appliqué), posée par
`set_properties` dans la transaction du lot ; le résumé du **snapshot** porte
en plus la plage d'offsets du lot (`pharmaflux.offsets`), pour l'audit
(« ce snapshot a appliqué les offsets 0 à 9 999 de la partition 1 »). La
maquette a vérifié les deux : `set_properties` dans la transaction, la
propriété relue à `table.properties`, le résumé relu à
`current_snapshot().summary`. Pourquoi la propriété de table en plus des
snapshots : un lot entièrement en doublon (republication après coupure) ou
un lot qui ne ferme rien d'ouvert ne doit pas être relu à chaque démarrage ;
`set_properties` seul produit un commit **sans snapshot** (vérifié :
17 → 17 snapshots, un `metadata.json` de plus), et la position avance. Au
redémarrage, la position se lit dans la table, sans parcourir les snapshots.
**Alternatives écartées** : le commit d'offset sur le courtier (une trace
sur le bus, une fenêtre entre le commit Kafka et le commit Iceberg dans un
sens ou dans l'autre ; après une coupure, soit des doublons, soit des
pertes rattrapées par rien) ; un `positions.json` dans l'entrepôt (la même
fenêtre, et un fichier de plus à garder cohérent). Avec la position dans le
commit, il n'y a **pas de fenêtre** : le silver et sa position avancent ou
n'avancent pas.

**Fin d'une exécution** : **jusqu'aux offsets de fin lus au départ**, comme
`verifier-bus`. C'est testable, cela finit, et `make silver` a une fin. Un
`--continu` (boucle de `poll` sans fin, lots à l'échéance d'un délai) tient
en vingt lignes et se propose pour la mission qui aura un flux vivant à
suivre (Lot 5, ou la collecte branchée sur le bus) ; pas dans cette mission,
sauf avis contraire.

**Un message qui n'est pas un événement v1 lisible** (`deserialiser`
refuse, ou l'entité de la ligne n'est pas celle du topic) : **arrêt, code 2**,
rien de ce lot n'est écrit, la position ne bouge pas ; le message dit topic,
partition, offset, les premiers octets et le motif. Il n'est jamais sauté :
sauter, c'est perdre une version en silence, et un bus d'événements v1 ne
doit porter que du v1 (`publier` envoie l'illisible dans la file). La voie
est de rebâtir le bus depuis les fichiers, qui restent la référence. Le
consommateur restera arrêté sur ce message jusque là : c'est voulu.

**Refus** (code 2, avant toute écriture) :

- **entrepôt construit depuis un autre bus, ou bus rebâti après le
  silver** : la table garde, à la création, l'identifiant de grappe du
  courtier (`AdminClient.describe_cluster()`, disponible dans
  `confluent-kafka 2.16`) et, à chaque lot, l'`id` du dernier message appliqué
  par partition. Au départ : grappe différente → refus ; position au-delà
  de l'offset de fin, ou en deçà de l'offset de début (rétention) → refus ;
  le message à `offset − 1` de chaque partition est relu et doit porter l'`id`
  gardé, sinon refus (« le bus n'est pas celui qui a construit le silver :
  rebâtis le silver »). Un bus rebâti **à l'identique** (mêmes fichiers,
  mêmes clés, donc mêmes offsets et mêmes `id`) passe le contrôle des `id`
  et serait refusé par l'identifiant de grappe ; le silver serait pourtant
  juste. Je propose que l'identifiant de grappe soit un **avertissement**
  et le contrôle des `id` le refus ; à vérifier au palier 2 qu'un `down -v`
  change bien l'identifiant de grappe de Redpanda ;
- **entrepôt construit depuis les fichiers** (point E) : il n'a pas de
  position ; le consommateur le refuse (« silver construit depuis les
  fichiers : pas de position de bus ; un autre entrepôt »), et
  réciproquement `construire` refuse un entrepôt du bus. L'origine est une
  propriété de table (`pharmaflux.origine` : `bus` ou `fichiers`) ;
- **version de contrat** différente (point B) ; **entrepôt illisible**
  (catalogue absent alors que le dossier n'est pas vide) ;
- **bus vide** (aucun topic de la démo) : refus avec « `make demo` d'abord ».

**Question D.1** : identifiant de grappe en refus ou en avertissement ?
**D.2** : `--continu` hors mission ?

## E. La construction depuis les fichiers d'événements

**Commande** : `pharmaflux silver construire --sortie data/demo [--entrepot …]
[--fichier …]`. Les fichiers de `<sortie>/evenements/<entite>/` dans l'ordre
des noms, un lot et un commit par fichier, par la **même** `appliquer_lot` ;
le résumé du snapshot porte le nom du fichier. Elle **refuse** un entrepôt
non vide (code 2, « supprime <dossier> ou choisis un autre entrepôt ») :
pas de `--reprendre` depuis les fichiers dans cette mission (le rejeu
complet dure 6,5 s), et jamais d'effacement par la commande elle-même.

**Le test des deux chemins** : les mêmes fixtures (`tests/test_rejeu.py`,
`SUITE` : oscillation, perte confirmée, triple ramené à un…) rejouées puis
publiées sur le `BusSimule` de la mission 03 ; un silver construit par
`consommer` sur le `LecteurSimule`, un autre par `construire` sur les
fichiers ; les deux tables lues entières, triées par (`identite`,
`debut_validite`), **toutes les colonnes de données et de version égales**
(versions, validités, identifiants des événements qui ouvrent et ferment,
archives, anomalies). **Exclus et dits** : les identifiants, horodatages et
résumés des snapshots, le nombre de snapshots et de fichiers Parquet, leurs
noms, les propriétés `pharmaflux.positions`, `pharmaflux.offsets`,
`pharmaflux.origine` et l'identifiant de grappe. La fonction de comparaison
vit dans le paquet (`silver/comparaison.py`) : le test et ma démonstration du
palier 2 l'appellent ; une commande `silver comparer A B` qui l'expose coûte
dix lignes, je la propose pour la décision 6 (beko la verra tourner).

## F. « État à une date »

**Commande** : `pharmaflux silver etat --entite bdpm.presentations --a
2026-10-26T14:00:00Z [--entrepot …] [--ou code_cip13=3400930000000, répétable]
[--format jsonl|tableau|csv] [--colonnes …]`. Elle lit la table par PyIceberg
avec le filtre `debut_validite <= a AND (fin_validite IS NULL OR fin_validite
> a)` (élagage par les bornes des fichiers, puis Arrow), applique `--ou`
(égalité sur la chaîne normalisée, toute colonne du contrat), et écrit les
versions valides : `jsonl` par défaut (une version par ligne, colonnes du
contrat puis colonnes de version), `tableau` pour le terminal, `csv`. Sur la
sortie d'erreur : l'instant, le nombre de versions valides, les bornes du
silver (première et dernière observation). Mesuré : 0,01 à 0,03 s par
requête sur `presentations`.

**Les instants** : ISO 8601 à la seconde, **UTC** : `2026-10-26T14:00:00Z`
ou avec décalage (`+02:00`, converti en UTC), une date seule vaut minuit
UTC. **Refusés** (code 2) : un instant sans fuseau (le projet est en UTC
partout, et une heure de Paris nue serait ambiguë), une fraction de seconde
(les observations sont à la seconde), tout ce que `datetime.fromisoformat`
ne lit pas. Détail d'implémentation : PyIceberg refuse le littéral `…Z`
(« Invalid timestamp with zone ») ; on lui passe `+00:00`.

**Avant la première observation** de l'entité : **aucune version, code 0**,
et sur la sortie d'erreur « aucune version : l'instant précède la première
observation (2026-10-24T19:41:46Z) ». C'est une réponse vraie (on ne savait
rien), et une faute de frappe sur l'année se voit. **Après la dernière
archive** : l'état des versions ouvertes, code 0, et « le silver s'arrête à
la dernière observation (2026-10-27T13:17:31Z) » : ce qu'on savait à cette
date est ce qu'on sait encore. Si l'IeC préfère un code 2 pour « hors de la
fenêtre observée », c'est une ligne.

**Une commande SQL.** `pharmaflux silver sql "SELECT … FROM presentations
WHERE fin_validite IS NULL" [--entrepot …] [--format …]` : chaque table du
catalogue devient une vue DuckDB sur ses fichiers Parquet
(`read_parquet` des chemins de `plan_files()`, refus s'il y a un fichier de
suppression), extension `iceberg` ni installée ni chargée. **Avis : ça vaut
son coût** (une quarantaine de lignes, DuckDB est déjà là) : c'est ce que
le README montrera (« combien de présentations avaient une version ouverte
le 26/10 ? »), ce que la mission 06 réutilisera pour le gold, et ce que le
relecteur peut lancer. Elle ne connaît pas le temps : « état à une date »
reste `etat`, qui porte la règle de validité.

**Question F.1** : code 0 avec message, ou code 2, hors de la fenêtre ?
**F.2** : `silver sql` au palier 1, ou hors mission ?

## G. La vérification contre l'archive

**Commande** : `pharmaflux silver verifier --entrepot … --sortie data/demo
--racine demo/archive [--fichier …]`. Pour chaque entité, les archives et
leur verdict viennent des **bilans** de la sortie
(`<sortie>/bilans/<entite>/*.json`, champ `decision` : `retenu`, `confirme`,
`ecarte`), jamais des événements ; le snapshot de chaque archive retenue ou
confirmée est **recalculé depuis le bronze** (`snapshot.lire`, comme
`verifier-bus --racine`), réduit à ses empreintes (`etat_du_snapshot` puis la
réduction de `bus/verification.py`, une empreinte par identité sur les
valeurs triées et les occurrences) ; l'état du silver à l'horodatage de
l'archive est lu par le filtre de validité, réduit **de la même façon**
(pour un fichier ligne à ligne : empreinte → nombre de versions valides), et
comparé identité par identité, avec les exemples cités comme `verifier-bus`
(`_comparer`). Toute différence : code **2**. Référence introuvable (pas de
bilans, pas d'entrepôt) : refus avant toute lecture, code 2. Maquette sur le
jeu : **18/18 conformes, 9,6 à 10,6 s**, 0,04 s (disponibilité) à 1,0 s
(présentations) par archive, le temps allant au recalcul du snapshot et aux
empreintes, pas au silver (0,01 à 0,03 s par état).

**Snapshots écartés** : l'état à leur horodatage doit être **égal au dernier
retenu avant eux** (aucune version ne bouge) ; c'est vérifié aussi, au prix
d'un état de plus par archive écartée (4 dans le jeu : les quatre
`CIS_InfoImportantes.txt` vides). **En attente puis confirmé** : ses
événements portent la `date_observation` de son archive (PRD §6.3), donc
l'état à cet horodatage est son snapshot, et la règle est la même que pour
un retenu ; entre son archive et celle qui le confirme, l'état est déjà le
sien, ce qui est le sens du PRD (« un vrai rétrécissement coûte une heure
de retard, les événements gardant la date de leur archive »). **En attente
à la fin du bronze** : pas d'événement, pas de version, pas vérifié, dit en
clair.

**« Juste après » une observation, à la seconde.** Les `date_observation`
sont à la seconde, le silver aussi. L'état à `t` vaut pour tout `t` entre
l'horodatage d'une archive **inclus** et celui de la suivante de la même
entité **exclu** ; une seconde après, c'est encore le même état ; une
seconde avant, c'est le précédent. L'horodatage est celui du nom de
l'archive, l'instant du téléchargement, **pas** celui du passage : le 27/10,
l'archive `20261027T001712Z` suit le passage `20261027T001708Z` de quatre
secondes, et l'état « à 00:17:08 » est encore celui d'avant (20 896
présentations, pas 20 888 ; mesuré). Le README le dira pour ses deux
exemples : « le 26/10 juste après 14:17:39 » (l'archive vide écartée), pas
« après 14:17 ».

**Durée et mémoire attendues sur le jeu** : une dizaine de secondes ; en
processus séparé, 102 Mo d'imports plus le snapshot recalculé et son état
(`compositions` : 40 Mo tracés à la mission 03) plus l'état Arrow (13 Mo) ;
mesuré dans le même processus que la construction : **+45 Mo** avec
l'allocateur système d'Arrow, **+180 Mo** avec jemalloc (point J).

**Ce que le jeu ne contient pas** (aucune `modifiee` ni `creee` après l'état
initial, aucun snapshot en attente ou confirmé) est couvert par les
**fixtures** de `tests/test_rejeu.py` (`SUITE` : A → B → A → B donne des
`modifiee` et des `creee` après l'état initial, des pertes en attente
confirmées par l'archive suivante ou par un passage inchangé, écartées par
B, une ligne en triple ramenée à une puis remontée) : les événements sont
rejoués, le silver construit, et `verifier` passe sur ce bronze de synthèse ;
plus des événements construits à la main pour les refus (modifiée sans
version ouverte, créée sur identité ouverte, rang faux, doublon, deuxième
version de contrat).

**Comparer aussi le silver au bus ou aux fichiers** : la comparaison des deux
chemins (point E) couvre bus contre fichiers ; `verifier-bus` couvre déjà bus
contre archive. Ce qui apporte quelque chose de plus et ne coûte rien, ce
sont les **invariants du SCD2**, en DuckDB sur les fichiers Parquet, dans
`silver verifier` : une seule version ouverte par identité ; aucun
chevauchement de validités pour une identité ; `fin_validite > debut_validite`
partout ; chaque `id` d'événement au plus une fois en ouverture et une fois
en fermeture ; le nombre de fermetures égal au nombre de `modifiee` et
`supprimee` des bilans. Je propose de les ajouter à la vérification, code 2
sur l'un d'eux.

## H. La reprise et la reconstruction

**Oui, à tout point de coupure.** Un lot est **un** commit, qui porte les
données et la position (point D). Le commit du `SqlCatalog` écrit le nouveau
`metadata.json` puis met à jour la ligne SQLite si elle pointe encore vers
l'ancien. Trois cas : coupure **avant** l'écriture du `metadata.json` → le
silver et la position sont ceux d'avant le lot, la reprise relit le lot
depuis la position et l'applique à l'identique (et les doublons par `id`
sont le second filet) ; coupure **entre** le `metadata.json` et la mise à
jour SQLite → un fichier de métadonnées orphelin, la table pointe encore
vers l'ancien, cas identique au premier ; coupure **après** → le lot est
appliqué, position comprise, la reprise commence au lot suivant. Les fichiers
Parquet écrits avant un commit interrompu sont des orphelins que rien ne lit
(un nettoyage n'est pas dans cette mission ; dit dans l'ADR).

**Le test, sans coupure de processus** : (1) un `LecteurSimule` qui lève
après N messages, pour chaque N d'un flux de quelques dizaines
d'événements (comme `BusCoupe` de la mission 03), puis une seconde
exécution ; (2) une cale sur `SqlCatalog.commit_table` qui lève **après**
`_write_metadata` et **avant** la mise à jour SQLite (le cas « entre ») ;
(3) une exécution interrompue par un refus (message illisible), puis le bus
corrigé. Après chaque reprise, le silver est comparé (point E) à celui d'une
exécution sans coupure et à celui des fichiers : égaux. Plus : deux
exécutions de suite sans rien de nouveau ne commettent rien.

**Rebâtir de zéro** : effacer le dossier de l'entrepôt. Pour la démo,
`make rebatir` le fait déjà (`rm -rf data/demo`, l'entrepôt de la démo étant
`data/demo/lakehouse`). Les commandes **n'effacent rien** : `construire`
refuse un entrepôt non vide et nomme le dossier ; `consommer` refuse ce qui
n'est pas le sien (point D). Pas d'option `--rebatir` : une commande qui
supprime un dossier de données n'a pas sa place dans ce dépôt.

## I. `Makefile` et CI

**Cibles proposées** (GNU Make 3.81, mêmes variables) :

```make
ENTREPOT_DEMO = $(SORTIE_DEMO)/lakehouse

silver:
	$(PHARMAFLUX) silver consommer --entrepot $(ENTREPOT_DEMO)
	$(PHARMAFLUX) silver verifier --entrepot $(ENTREPOT_DEMO) --sortie $(SORTIE_DEMO) --racine $(JEU)

etat:
	$(PHARMAFLUX) silver etat --entrepot $(ENTREPOT_DEMO) --entite $(ENTITE) --a $(A) $(ETAT_OPTIONS)
```

`make silver` **après** `make demo` : il ne dépend pas de la cible `demo`
(on ne rejoue pas la démo pour construire le silver ; le refus « bus vide,
`make demo` d'abord » fait le lien), et `verifier` a le dernier mot.
`make rebatir` ne change pas : `rm -rf data/demo` emporte l'entrepôt.
`make etat ENTITE=bdpm.presentations A=2026-10-26T14:00:00Z` pour le
README ; `make help` mis à jour. `make verifications` ne change pas.

**CI** : une étape « Silver du jeu (make silver) » dans le job
`integration`, après `make demo`, avant `down -v`. **Durée ajoutée,
estimée** : sur le Mac, lecture de 164 106 messages ≈ 11 s (comme
`verifier-bus`), écriture ≈ 7 s (mesurée depuis les fichiers), vérification
≈ 10 s, soit **≈ 30 s** ; sur le runner amd64, 45 s à 1 min, plus la roue
PyArrow de 54 Mo dans `uv sync` (en cache après le premier passage). Le job
`integration` est à 15 min, `make demo` y est estimé à 1 min 30 s : marge
large. Le job `verifier` ne change pas, hors les tests nouveaux (une
dizaine de secondes).

## J. La mémoire

Mesures sur le Mac (`/usr/bin/time -l`, `ru_maxrss`), jeu de démo, maquette :

| quoi | résident |
|---|---|
| Python 3.12 nu | 13 Mo |
| `import pyarrow` | 33 Mo (0,04 s) |
| `import duckdb` | 38 Mo (0,05 s) |
| `import pyiceberg.catalog.sql, pyiceberg.table` (pydantic, SQLAlchemy) | 69 Mo (0,38 s) |
| les trois ensemble | **102 Mo** (0,36 s) |
| construction du silver depuis les fichiers, lots de 10 000, allocateur jemalloc d'Arrow (défaut) | 276 à 406 Mo selon l'exécution |
| la même, lots de 2 000 | 269 Mo |
| la même, **`ARROW_DEFAULT_MEMORY_POOL=system`** | **276 Mo** |
| construction puis vérification, jemalloc | 448 à 610 Mo |
| construction puis vérification, allocateur système | **348 Mo** (vérification : +45 Mo) |

Le consommateur du bus ajoute les tampons de librdkafka (8 Mo de
préchargement, comme `verifier-bus`) : à mesurer au palier 2, estimation
300 à 450 Mo. La vérification seule, en processus séparé : ≈ 102 + 60 à
80 Mo, à mesurer. **La copie du Mac est le jeu** (constat 1) : pas de mesure
« plus longue » possible aujourd'hui.

**Pour tenir un jour sous 256 Mo sur le VPS** (sans le faire ici) : l'import
seul laisse 150 Mo ; il faudrait l'allocateur système d'Arrow (déjà −100 à
−250 Mo ici, à poser par variable d'environnement dans l'unité systemd ou
`pa.set_memory_pool(pa.system_memory_pool())`), des lots de 2 000, ne pas
tenir d'état Python par lot (passer de `json.loads` à des colonnes Arrow
dès la lecture), et retirer SQLAlchemy et pydantic du chemin critique, ce
qui veut dire un autre catalogue ou `pyiceberg-core` (Rust) : hors de
portée du Lot 2. L'honnête : le silver ne tourne pas sur le VPS en v1 ; il
tourne là où le bus est, sur le Mac, et le VPS continue de collecter. La
ligne « Mémoire de pointe » du PRD §9 est à compléter de ces chiffres.

## K. Autres remarques

1. **Imports paresseux.** PyIceberg et PyArrow ne s'importent que dans les
   commandes `silver` (module `pharmaflux.silver`, importé dans la fonction
   de commande), pour que `pharmaflux --version`, `collecte` et le reste
   gardent leurs 37 Mo et leur démarrage.
2. **Petits fichiers.** Un fichier Parquet par lot (32 pour le jeu à
   10 000, 99 à 2 000) et deux snapshots par commit de fermeture : rien à
   compacter à ces volumes, mais `verifier` affichera le nombre de fichiers
   et de snapshots par table, pour qu'on le voie grandir.
3. **Chemins absolus.** PyIceberg veut un entrepôt `file://` absolu et écrit
   ce chemin dans chaque `metadata.json` et manifeste : un entrepôt déplacé
   ne se relit pas (l'ADR le dira ; `make rebatir` est la voie). Les
   rapports ne citeront aucun chemin de poste : `data/demo/lakehouse`, pas
   `/Users/…`.
4. **Allocateur d'Arrow.** Les commandes `silver` poseront
   `pa.set_memory_pool(pa.system_memory_pool())` au démarrage, puisque la
   mesure est nette (point J) ; la variable d'environnement reste possible.
5. **Journal, correspondance des hashes** : vérifiée sur `main`
   (`38589dc`, `5167314`, `5c3fe5a`), elle sera la première entrée du palier 1.
6. **Le filtre de validité est juste côté PyIceberg** : ma première maquette
   comptait 10 au lieu de 20 898 par un `pc.or_` non Kleene sur les
   `fin_validite` nulles ; le filtre poussé à PyIceberg (`IsNull` dans un
   `Or`) compte juste. Le code de la mission passe la règle entière à
   PyIceberg, pas un masque Arrow maison, et un test le couvre (versions
   ouvertes et fermées à la même date).
7. **Horodatages Iceberg** : `timestamptz` en microsecondes ; nos
   observations sont à la seconde ; `etat` refuse les fractions (point F).
8. **La file des échecs** n'est pas lue par le silver (tranché) ;
   `verifier` affichera quand même son compte, comme `verifier-bus`, pour
   qu'une démo avec un message en échec ne passe pas inaperçue.
9. **`demo/README.md` et l'ADR 0008** disent « 14:17 » pour l'archive vide
   écartée : la seconde (14:17:39) compte pour l'exemple du README de cette
   mission (point G) ; je ne touche pas aux documents de la mission 04.

**Rien n'a été codé. J'attends l'addendum.**
