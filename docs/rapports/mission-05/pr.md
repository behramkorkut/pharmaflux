# Mission 05 — le silver : tables Iceberg SCD2 depuis le bus, « état à une date », vérification contre l'archive, `make silver`

Branche `mission-05-silver-et-etat-a-une-date`, depuis `b5b9420` (le `main`
du départ, qui porte l'addendum 1 ; `main` n'a pas bougé depuis), §0 en
`7103e8b`, cette description en dernier. Ordre de mission :
`docs/missions/mission-05-silver-et-etat-a-une-date.md` (addendum 1,
`b5b9420`). Trois paliers acceptés par l'IeC ; trois contrôles de palier
commis tels quels dans `docs/relectures/mission-05/`. Relecture 1 : **NON
CONFORME**, un bloquant et quatre points, corrigés en `4fa1cb3`
(`reponse-relecture-1.md`). Relecture 2 : **CONFORME**, 0 bloquant, un point
non bloquant corrigé en `c53d714` (`reponse-relecture-2.md`), à vérifier au
contrôle final. Revue finale de l'IeC : à venir sur le commit qui porte cette
description.

## Ce qui est livré

**Le silver depuis les fichiers, l'état à une date, la vérification**
(palier 1, `438ae4e`). Un paquet `pharmaflux.silver` : un entrepôt Iceberg
par dossier (`SqlCatalog` de PyIceberg sur SQLite, `catalogue.sqlite` à la
racine, une table par entité, propriétés `pharmaflux.entite`,
`version_contrat`, `origine`), le schéma des versions (colonnes du contrat,
chaînes telles que servies, plus `identite`, `empreinte_ligne`, `rang`,
`date_source`, `debut_validite`, `fin_validite`, `id_ouverture`,
`id_fermeture`, archives d'ouverture et de fermeture, `version_contrat`,
`etat_initial`, `anomalies`), et **une seule fonction d'application des
événements** (`appliquer_lot`), la même pour les fichiers et pour le bus :
SCD2 sur la date d'observation, borne de fin exclue, identité = clé JSON
compacte (fichier à clé) ou `<empreinte>#<rang>` (ligne à ligne), doublons
reconnus à l'`id` dans le lot et contre la table, un commit Iceberg par lot
(`set_properties` + `delete` + `append` dans une transaction). Commandes :
`silver construire` (depuis `data/<sortie>/evenements`, un lot par fichier,
refuse un dossier non vide), `silver etat --entite --a [--ou colonne=valeur]
[--format jsonl|tableau|csv] [--colonne]` (la règle de validité poussée
entière à PyIceberg ; UTC à la seconde, trois formes acceptées), `silver
sql` (DuckDB sur des jeux Arrow, **sans aucun accès fichier** :
`enable_external_access = false`, configuration verrouillée, un seul
`SELECT` ou `EXPLAIN`), `silver comparer` (deux entrepôts, `EXCEPT ALL` dans
les deux sens), `silver verifier` (chaque archive retenue du bronze est
recalculée en snapshot et comparée, empreinte par empreinte, à l'état du
silver à son instant d'observation ; une archive écartée doit donner l'état
du dernier retenu ; cinq invariants SCD2 en SQL ; code 2 au moindre écart).
`ARROW_DEFAULT_MEMORY_POOL=system` posé avant le premier import de PyArrow.

**Le consommateur du bus** (palier 2, `9223280`). `silver consommer` lit
chaque topic `pharmaflux.<entite>.v1` depuis la position gardée **dans les
propriétés de la table** (`pharmaflux.positions` : par partition, l'offset
suivant et l'`id` du dernier message appliqué), toutes les partitions à la
fois, jusqu'aux offsets de fin lus au départ, par lots de 10 000 ; la
position part dans le même commit Iceberg que le lot (aucune fenêtre entre le
silver et sa position), la plage d'offsets dans le résumé du snapshot
(`pharmaflux.offsets`). Au départ : refus si le bus est vide (rien n'est
créé), si le silver vient des fichiers, si la version de contrat a changé,
si une position est hors des bornes du topic, ou si le message à
`offset − 1` ne porte pas l'`id` gardé (« le bus n'est pas celui qui a
construit le silver ») ; une autre grappe donne un **avertissement**, le
contrôle des `id` décide. Un message qui n'est pas un événement v1 arrête
tout sans rien écrire et n'est jamais sauté. Aucun groupe, aucun commit sur
le courtier. `LecteurKafka` gagne quatre méthodes (`identifiant_grappe`,
`bornes`, `derniers_messages` avec un consommateur dédié à
`fetch.wait.max.ms` 50, `lire_depuis`), rien d'existant ne change.

**`Makefile`, CI, docs** (palier 3, `63118d6`). `make silver` (après
`make demo` : `silver consommer` vers `data/demo/lakehouse`, puis `silver
verifier` contre `demo/archive`, qui a le dernier mot), `make etat`
(`ENTITE`, `A`, `ETAT_OPTIONS`), `make help` et `make rebatir` mis à jour ;
étape `make silver` dans le job `integration` de la CI, après `make demo`,
avant le `down -v`, job `verifier` inchangé. ADR 0009, section « Le silver »
du README avec deux exemples réels du jeu (la présentation `3400938844948`,
déclarée en arrêt de commercialisation, présente le 24/10 à 23:17:11 et
absente à 23:17:12 ; les informations importantes inchangées le 26/10 juste
après 14:17:39, 10 905 versions, 0 fermée), `docs/CONTEXTE.md`, journal (la
première entrée donne la correspondance des hashes de `main` réécrits après
la mission 04).

**Démonstration de beko sur le Mac** (décision 6, palier 3, sur `63118d6`
avant son commit, dans `pharmaflux-codeur/`) : `make rebatir`, `make demo`,
puis `make silver` : **164 106 messages** sur onze topics en 14,4 s, 0
doublon, 24 commits, 10 fermetures (les suppressions de présentations), puis
`silver verifier` **22/22 archives conformes** (18 retenues, 4 écartées),
invariants conformes, 10,4 s. Sortie citée dans `palier-3.md`. Au palier 2,
le codeur avait obtenu sur le bus de la démo : `consommer` 164 106 messages
en 12,9 s, `comparer` identique au silver des fichiers (11 tables),
`verifier` 22/22, seconde exécution 0,3 s et « rien de nouveau ».

**D.1, `down -v` et l'identifiant de grappe** : un entrepôt témoin
(`data/lakehouse-temoin-d1`, hors de `data/demo` et hors git) construit sur
la grappe `redpanda.990d5d4e-…` puis relu après le `make rebatir` de beko :
**la grappe change** (`redpanda.f614c4ee-…`, Redpanda la tire de son
volume), **l'avertissement sort**, et **le contrôle des identifiants conclut
« rien de nouveau »** : les `id` des événements sont des sha256 de leur
contenu et `make demo` republie le même jeu dans le même ordre, donc le
message à `offset − 1` porte l'`id` gardé ; positions inchangées, aucun
commit, code 0. beko efface le témoin.

**Mémoire** (seuil d'alerte 512 Mo par commande, `/usr/bin/time -l`, jeu de
démo, mesures sur `c53d714`) : `construire` 272 Mo (11,7 s), `verifier`
310 Mo (11,4 s), `comparer` 424 Mo (le plus lourd : deux tables en mémoire
et l'`EXCEPT ALL`), `etat` 219 Mo, `sql` 143 Mo, `consommer` sans rien de
nouveau 123 Mo ; `consommer` du bus entier 357 Mo au palier 2. Toutes sous
512 Mo. PyArrow pèse : l'import seul laisse 150 Mo ; l'allocateur système
d'Arrow a fait gagner 100 à 250 Mo par rapport à jemalloc (§0 J). Pour tenir
un jour sous 256 Mo sur le VPS : des lots plus petits et une vérification en
processus séparé, hors mission.

**Dépendances** : `pyiceberg[sql-sqlite] 0.12.0`, `pyarrow 26.0.0`, `duckdb
1.5.6`, `sqlalchemy 2.0.54` et leurs transitifs, 24 paquets ajoutés à
`uv.lock`, tous publiés au 14/10/2026 ou avant, aucun paquet existant
changé ; `pyarrow-stubs` en développement. Règle des deux semaines tenue par
`[tool.uv] constraint-dependencies` (plafonds **temporaires**, chacun
commenté, à remonter à la prochaine mission qui touche aux dépendances).

**Tests** : **500** (470 à la fin de la mission 04), dont 11 d'intégration
marqués `integration`, lancés sur le courtier du Mac et sautés sans lui ;
les autres tournent sans réseau ni conteneur (bus simulé à trois partitions
réparties par la clé, coupures pendant la lecture, entre le `metadata.json`
et SQLite, après le commit ; imports paresseux testés en sous-processus).
mypy strict sans `type: ignore` dans `src/`.

**Documents** : `docs/rapports/mission-05/` (points à trancher, trois
rapports de palier, deux réponses aux relectures), `docs/relectures/mission-05/`
(trois contrôles de palier, deux relectures, commis tels quels), ADR 0009.

## Vérifications locales (commit testé : `c53d714`)

Courtier du projet démarré sur le Mac (`pharmaflux-redpanda`, le bus de la
démo rebâtie par beko). Toute la non-régression de l'ordre en une passe sur
ce commit ; `~/pharmaflux-data` n'a été que lue, aucune requête réseau vers
les sources.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 208 files already formatted |
| `uv run mypy src` | Success: no issues found in 51 source files |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true` | **500 passed** en 2 min 07 s, dont 11 `integration` |
| `uv lock --check` | Resolved 56 packages, verrou inchangé |
| `ruby -ryaml` sur `.github/workflows/ci.yml` ; `make -n silver`, `make -n etat` | yaml ok ; recettes attendues |
| `python3 infra/agents/test_garde_fou.py` / `sh infra/git-hooks/test-crochets.sh` | 21 tests OK / tout est conforme |
| `uv run pharmaflux demo verifier` | conforme |
| `uv run pharmaflux verifier-bus --sortie data/demo --racine demo/archive` | 12/12 conforme |
| `profil` sur `~/pharmaflux-data` | 11 fichiers profilés, 0 anomalie bloquante |
| `questions verifier` sur `~/pharmaflux-data` | 40 questions : 25 conformes, 5 non calculables, 10 sans attendu |
| `evenements` sur `~/pharmaflux-data`, code `1af4ef9` (extrait par `git archive`) et `c53d714`, `diff -r` | identique |
| `silver construire` / `verifier` / `comparer` / `etat` / `sql` / `consommer` sur le jeu | ci-dessus (mémoire), 22/22 conformes, identiques : 11 tables |

Le relecteur a rejoué sur `4fa1cb3` : la suite complète, le silver construit
sous un dossier à espace et accent (22/22 conformes), les exemples du
README. **La CI n'a pas encore tourné** : sa première exécution a lieu au
push. L'étape `make silver` y est estimée à **≈ 30 s** (consommation 14 s,
vérification 10 s sur le Mac) dans le job `integration` ; **la durée mesurée
au premier passage est à reporter ici par beko**.

## Sur le VPS

Rien. La collecte horaire n'est pas touchée, le silver ne vise pas le VPS en
v1 (addendum 1).

## Écarts à l'ordre, acceptés par les contrôles et les relectures

1. **`silver sql` sans `allowed_directories`** (palier 1) : la maquette a
   montré qu'un `COPY … TO` dans le dossier autorisé passait ; DuckDB ne
   reçoit que des jeux Arrow, sans aucun accès fichier, et un seul `SELECT`
   passe. Plus strict que l'addendum ; la connexion elle-même refuse `COPY`,
   `ATTACH`, `INSTALL` et `SET` (testé depuis la relecture 1).
2. **Plafonds de versions temporaires** (palier 1) : `sqlalchemy<2.0.55` et
   `cachetools<7.2.2` en plus de `duckdb<2`, `python-dateutil<3`,
   `tzdata<2026.6`, découverts au verrou comme l'addendum le prévoyait ;
   dits temporaires dans l'ADR 0009.
3. **Premier snapshot sans `ecart`** (palier 1) : `verifier` compte une
   `creee` par ligne bien formée (ADR 0006).
4. **`fetch_arrow_table` remplacé par `to_arrow_table`** (palier 1) : plus
   aucun appel déprécié de DuckDB.
5. **Un consommateur dédié pour relire `offset − 1`** (palier 2) : la
   relecture avec le consommateur de `lire` coûtait jusqu'à 1 s par
   partition (16,5 s pour une exécution sans rien de nouveau) ; 0,3 s avec
   `fetch.wait.max.ms` 50. Les réglages de `lire`, `verifier-bus` et `suivre`
   ne changent pas.
6. **Points de coupure réduits à huit par exécution** (palier 2) : la suite
   atteignait 2 min 43 s avec les coupures à tous les bords de lots ;
   2 min 00 s après.
7. **`bus/client.py` touché** (palier 2) : par quatre méthodes ajoutées
   seulement.
8. **Non-régression `profil` et `questions verifier` non rejouée au
   palier 3** (aucun fichier de `src/` touché) : rejouée ici, en une passe,
   sur le commit testé.
9. **La mesure « plus longue que le jeu »** (§0 J) est **reportée au prochain
   rapatriement** : `~/pharmaflux-data` s'arrête au passage
   `20261027T151708Z`, avec les mêmes 22 archives que le jeu de démo ; il
   n'existe aujourd'hui aucune archive plus longue sur le Mac.
10. **La durée de l'étape CI `make silver`** : connue après la publication,
    à reporter ci-dessus.
11. **Relecture 1** : un bloquant corrigé en `4fa1cb3`, `Path.as_uri()`
    encodait un espace ou un accent du chemin et PyIceberg écrivait Parquet
    et métadonnées dans un dossier voisin ; l'URI est maintenant le chemin
    brut derrière `file://`, `#` et `?` refusés avant toute écriture.
12. **Relecture 2** : une date seule impossible (`2026-02-30`) donnait une
    trace Python en code 1 ; refusée « illisible » en code 2 (`c53d714`).

Aucun refus du garde-fou pendant la mission ; aucun `down -v` lancé par le
codeur (celui de `make rebatir` l'a été par beko).

## Propositions, hors mission

- **`silver consommer --continu`** : consommer en boucle, comme `suivre`,
  pour tenir le silver à jour derrière la collecte (mission VPS). Le code
  d'un passage est déjà idempotent avec reprise ; il manque la boucle, le
  délai et l'arrêt propre.
- **`make etat` avec `A` lu de `data/demo/etat.json`** par défaut (la
  dernière observation), au lieu d'une date fixe.
- **Remonter les plafonds** de `constraint-dependencies` à la prochaine
  mission qui touche aux dépendances (règle des deux semaines).
- **Tenir sous 256 Mo** pour le VPS : vérification en processus séparé,
  lots plus petits (§0 J).
