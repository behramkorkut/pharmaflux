# Contexte technique — point d'entrée

Ce fichier dit ce qu'il faut savoir avant de toucher au code. Il est tenu
à jour à chaque mission ; les décisions durables sont dans `docs/adr/`, le
fil des travaux dans `docs/journal.md`.

## Ce que fait le projet

Transformer des publications d'état (fichiers BDPM, bases Open Medic) en
un flux d'événements daté et rejouable. Tout repose sur une **archive
brute immuable** (couche bronze) : chaque fichier reçu est conservé à
l'octet près, horodaté, avec son empreinte, et n'est jamais réécrit.

## Règles qui ne se discutent pas

- **L'archive est irremplaçable.** La BDPM n'a pas d'historique : un jour
  sans collecte est un jour perdu pour toujours. On ne supprime jamais une
  archive, on ne la réécrit jamais, on ne la « nettoie » jamais. Une copie
  hors du serveur de collecte est tenue à jour chaque semaine
  (`infra/planification/rapatrier.sh`, rsync sans `--delete`).
- **Octets bruts.** Le contenu archivé est exactement ce que le serveur a
  envoyé, compressé (gzip), jamais converti ni réencodé : la licence BDPM
  interdit l'altération, et le rejeu du Lot 1 en dépend.
- **Aucune donnée dans git.** `data/` et `*.gz` sont ignorés ; l'archive
  vit sous `PHARMAFLUX_DATA` (défaut `~/pharmaflux-data`). Aucune donnée
  personnelle, nulle part.
- **Les tests n'appellent jamais le réseau.** Les sources sont un service
  public, pas un banc d'essai : un téléchargement réel sert à constituer
  des fixtures (`tests/fixtures/`), puis on travaille dessus.
- **Temps en UTC**, ISO 8601, partout dans l'archive et le manifeste. Les
  dates affichées par les sites sources sont des dates locales (Paris), au
  jour près : elles sont conservées telles quelles, dans un champ à part.
- **Français** dans les docs, les commits, les commentaires et les
  identifiants de code (sans accents dans le code).

## Ce que l'on sait des sources (mesuré le 24/10/2026)

Détail et chiffres : `docs/rapports/mission-00/points-a-trancher.md`.

- **BDPM** : onze fichiers texte tabulés sans en-tête, 28,7 Mo bruts par
  passage complet (3,7 Mo gzip). Le serveur n'envoie **ni `Last-Modified`,
  ni `ETag`, ni `Content-Length`** : aucune requête conditionnelle n'est
  possible, chaque passage télécharge tout. La page de téléchargement
  affiche une date de mise à jour et une taille par fichier (sauf
  `CIS_InfoImportantes.txt`, généré à la demande et non trié).
- **Encodages hétérogènes** : la plupart des fichiers sont en
  Windows-1252 avec fins de ligne CRLF, mais `CIS_CIP_bdpm.txt` et
  `CIS_InfoImportantes.txt` sont en UTF-8 avec LF. Les en-têtes HTTP
  n'annoncent aucun charset. Les contrats de schéma (mission 01) portent
  l'encodage et la fin de ligne par fichier.
- **Open Medic (data.gouv.fr)** : les dates `last_modified` par ressource
  sont celles du robot de data.gouv, pas de la Cnam ; les dates utiles
  sont `created_at` de la ressource et `last_modified` du jeu.

## Contrats de schéma et lecture du bronze (mission 01)

- **Un contrat TOML par fichier** (`src/pharmaflux/contrats/bdpm/<nom>.toml`,
  version `v0`, et `v1` pour les présentations depuis la mission 02 :
  virgule des milliers des prix et graphie canonique des taux, ADR 0005) :
  encodage, fin de ligne, colonnes typées (neuf types,
  ADR 0002), clé déclarée unique ou non avec sa raison, liens de mesure
  vers d'autres fichiers, documentation PDF et archive de référence avec
  leurs sha256. Le chargeur est strict : toute clé inconnue est refusée.
  À partir de la fusion de la mission 01, **tout changement de contenu
  d'un contrat, lien compris, passe par une nouvelle version**.
- **On constate, on ne corrige pas** (PRD §6.2). `pharmaflux profil`
  vérifie une archive contre son contrat et signale les anomalies : quatre
  règles bloquantes (encodage, fin de ligne, nombre de colonnes, clé
  déclarée unique non unique) et quinze non bloquantes (valeur inconnue,
  date hors plage, décimal illisible, espace parasite…). Rien n'est
  jamais réécrit : les prix à virgule des milliers, les dates de 1949 et
  les espaces de fin restent tels quels dans le bronze, et c'est au Lot 1
  de normaliser. Ce que l'on sait des fichiers est dans `docs/donnees/`.
- **Le bronze se lit par `pharmaflux.bronze`** (`lister`, `derniere`,
  `lire_archive`), jamais par le système de fichiers directement : les noms
  qui commencent par un point (temporaires, `.rsync-partiel/`) sont
  ignorés, les archives rendues sont les octets bruts décompressés.
- **Jeu de questions de référence** (`evaluation/`, PRD annexe B) :
  quarante questions dont la réponse attendue est lue dans une archive
  précise par la clé et les colonnes du contrat ; `pharmaflux questions
  verifier` la recalcule. Les lignes attendues sont brutes elles aussi.

## Du bronze aux événements (mission 02)

- **Normalisation** (`contrats/normalisation.py`, ADR 0005) : une valeur
  conforme prend sa forme canonique en chaîne (date ISO, décimal à point,
  `true`/`false`, graphie canonique d'une énumération, espaces de bord
  retirés) ; une valeur que le type ne lit pas reste brute avec sa règle ;
  une anomalie de forme ou de vraisemblance (`espace_parasite`,
  `date_hors_plage`) laisse passer la forme canonique et reste consignée.
  La forme vient du type et du contrat (`milliers`, `canonique`), jamais du
  code seul. Les brutes restent dans le bronze et dans chaque `Ligne`.
- **Snapshot** (`evenements/snapshot.py`) : une archive lue une fois par son
  contrat, dictionnaire clé normalisée → ligne, ou multiensemble de lignes
  pour SMR, ASMR et Dispo_Spec ; **écarté** avec son motif sur une
  anomalie bloquante ou une clé normalisée ambiguë, jamais une exception ;
  un bilan par archive (lignes, entités, anomalies, graphies).
- **Événements** (`evenements/schema.py`, `comparaison.py`, ADR 0006) :
  `creee`, `modifiee`, `supprimee`, schéma v1 tout en chaînes, identifiant
  sha256 sur les chemins relatifs des deux archives, une ligne JSON stable
  par événement ; une `creee` par entité à l'état initial. Rien ne dépend de
  l'ordre d'un objet JSON : l'identité et le tri prennent les colonnes dans
  l'ordre alphabétique de leur nom.
- **Garde-fou de volume** (`evenements/volume.py`) : le vide et le bloquant
  sont écartés sans appel ; une perte de plus de 1 % des lignes met
  l'archive en attente, confirmée par un passage inchangé du manifeste ou
  par l'archive suivante ; rien n'émet des milliers de `supprimee` sur une
  réponse incomplète (cas réel du 26/10/2026).
- **`pharmaflux evenements`** (`evenements/rejeu.py`) : rejeu complet ou
  `--reprendre`, sortie par archive (`evenements/<entite>/*.jsonl`,
  `bilans/<entite>/*.json`, `etat.json`), écriture atomique dans l'ordre
  événements, bilan, état ; les snapshots ne sont jamais sérialisés, la
  reprise les recalcule depuis leur archive ; `--reprendre` refuse après un
  changement de version de contrat. Deux rejeux donnent les mêmes octets,
  une reprise après n'importe quel point d'arrêt aussi, et appliquer les
  événements au vide redonne le dernier snapshot retenu (tests).
- **Sortie par défaut** : `data/evenements/`, hors git ; jamais sous la
  racine de l'archive, qui ne s'écrit pas.

## Des événements au bus (mission 03)

- **Écriture en flux** (`evenements/rejeu.py`, `comparaison.py`, ADR 0006
  mis à jour) : chaque événement est écrit dès qu'il est produit, un seul
  snapshot retenu vivant par entité, valeurs répétées partagées (comparées
  avec `==`, jamais `is`) ; le rejeu complet de la copie du Mac tient en
  118 à 143 Mo résidents (474 avant), sortie identique à l'octet.
- **Courtier** (`docker-compose.yml`, ADR 0007) : Redpanda mono-nœud
  épinglé, projet `pharmaflux`, ports sur `127.0.0.1` (19092, 18081, 18082,
  19644), volume `pharmaflux-redpanda`, mode `dev-container`, console sous
  profil ; propriétés de grappe par `.bootstrap.yaml` (bloc `configs`),
  création automatique des topics coupée. Premier `pull` par beko ; les
  agents n'ajoutent que `--pull never`. Le colima est partagé : on ne touche
  qu'au projet `pharmaflux`.
- **Enveloppe et topics** (`bus/enveloppe.py`, `bus/client.py`) : un topic
  par entité, `pharmaflux.<entite>.v1`, 3 partitions, clé = objet JSON `cle`
  compact trié, `murmur2_random`, valeur = la ligne JSONL **nue** à l'octet,
  horodatage `date_observation` (`CreateTime`), en-têtes `id`, `schema_id`,
  `entite`, `type`, `archive`, `fichier`, `producteur` ; rétention sans
  limite posée à la création ; producteur idempotent, zstd, 1 Mo refusé au
  `produce`. Le topic vient du dossier du fichier, jamais de la ligne.
- **Schémas** (`bus/registre.py`, `bus/schemas/`) : JSON Schema draft-07 de
  l'événement et du message en échec, un sujet par topic,
  `BACKWARD_TRANSITIVE`, historique du dépôt enregistré avant le courant ;
  l'identifiant voyage dans l'en-tête, et un même contenu a le même
  identifiant sur tous les sujets.
- **`pharmaflux publier`** (`bus/publication.py`) : fichiers dans l'ordre,
  `publication.json` (sha256 des octets publiés, comptes) écrit après
  l'accusé de réception de chaque fichier ; `--reprendre` ne publie que les
  nouveaux ; un fichier publié modifié ou disparu fait refuser, sans
  forçage ; codes 1, 2, 3 ; file `pharmaflux.echecs.v1` (`illisible`,
  `trop_gros` tronqué à 64 Ko, `LogAppendTime`). Après une coupure, le
  fichier en cours est republié entier : doublons de même `id`, même
  contenu, même horodatage.
- **`pharmaflux verifier-bus`** (`bus/verification.py`) : relecture depuis
  le début sans commit d'offset, fin par les offsets, dédoublonnage par
  `id`, `appliquer` au vide et comparaison à la référence (fichiers par
  défaut ; `--racine` pour le dernier snapshot retenu, recalculé depuis
  l'archive) ; vérifie rétention, politique, type d'horodatage et
  partitions ; code 2 sur toute différence.
- **Mission close** quand `evenements --reprendre`, `publier --reprendre`
  et `verifier-bus` se suivent sans anomalie sur une copie rapatriée.

## La démo : jeu figé et rejeu accéléré (mission 04)

- **Jeu de démo** (`demo/archive`, `demo/README.md`, ADR 0008) : une
  archive Pharmaflux réduite aux onze fichiers TSV, coupée au passage
  `20261027T151708Z` inclus, fabriquée par `pharmaflux demo fabriquer`
  depuis la copie du Mac et copiée à l'octet (22 archives, 11 entités,
  781 lignes de manifeste, 71 passages, 6,7 Mo). Seule exception à « rien
  de `data/` dans git » (`.gitignore` : `!demo/archive/bronze/**/*.gz`).
  `pharmaflux demo verifier` et `tests/test_demo.py` la contrôlent sur un
  clone neuf. Un jeu ne se met pas à jour : on en fabrique un autre.
- **`pharmaflux demo rejouer`** (`demo/rejeu_accelere.py`) : juge l'état du
  bus (vide sans état → rejeu ; publié avec état → `--reprendre` ; non vide
  sans état ou état sans bus → code 2, `make rebatir`), lance `evenements`
  vers `data/demo`, puis publie par le code de `publier`
  (`publication.preparer`, `publier_fichier`) dans l'ordre global des
  observations (horodatage de l'archive, puis entité ; les passages sans
  archive sont affichés), à la cadence `t_reel_depart + (t_obs −
  t_obs_premiere) / facteur`, facteur 1 000 (`--sans-pause` en CI). Même
  ordre par topic que `publier`. Codes de `publier`.
- **`pharmaflux suivre`** (`bus/suivi.py`, `LecteurKafka.suivre`) : une
  ligne lisible par événement, onze topics depuis leur fin, un topic absent
  attendu, `--nombre`, `--depuis-le-debut` ; illisibles sur stderr et
  comptés, code 0.
- **`Makefile`** (GNU Make 3.81) : `up`, `demo`, `verifier`, `suivre`,
  `console`, `down`, `rebatir`, `verifications`, `help` ;
  `infra/demo/prerequis.sh` vérifie Docker, Compose, les images des seuls
  services que la cible lance (`config --images`) et `uv`, sans rien
  télécharger. Les agents ne lancent que `make -n`. La CI joue `make demo
  DEMO_OPTIONS=--sans-pause` dans le job `integration`.
- **Mesures** (27/10/2026, Mac arm64) : démo entière 4 min 03 s au facteur
  1 000 pour 67 h 35 min observées, 164 106 messages, 145 Mo résidents ;
  `evenements` sous `tracemalloc` de 0,7 à 35,8 Mo par entité ;
  `verifier-bus --racine demo/archive` conforme en 11,6 s.
- **Mission close** quand un clone neuf enchaîne `make up` et `make demo`
  jusqu'à un `verifier-bus` conforme ; sur une machine qui a déjà un volume
  `pharmaflux`, `make demo` refuse d'abord, puis `make rebatir`, `make demo`.

## Pièges connus

- Deux sources changent d'octets sans changer de fond (ordre des lignes
  d'InfoImportantes, compteurs du JSON data.gouv, `nonce` de la page
  HTML) : la décision « nouveau / inchangé » se prend sur une **empreinte
  de comparaison** déclarée par entrée du catalogue, alors que l'archive
  et le `sha256` du manifeste restent ceux des octets bruts.
- La page de téléchargement porte aussi un lien vers la documentation PDF
  du format (v5 au 24/10/2026) : il entre dans l'empreinte de la page (un
  changement de version sera vu) mais pas dans le contrôle « lien nouveau »,
  réservé aux fichiers `.txt`.
- Un lien que la page n'affiche plus (`lien_absent`) est quand même
  téléchargé et archivé : la ligne de manifeste est en `erreur` pour alerter,
  mais l'archive ne perd rien.
- `CIS_InfoImportantes.txt` : deux téléchargements à 76 min d'écart le
  24/10/2026 étaient identiques à l'octet près (même ordre des lignes) ;
  seul le nom dans `Content-Disposition` change. L'empreinte sur lignes
  triées reste en place, par prudence et à coût nul.
- Le `User-Agent` identifie le projet :
  `pharmaflux/<version> (+https://github.com/behramkorkut/pharmaflux)`.
  Téléchargements en série, pause de 2 s, une fois par heure à `:17`.

## Où sont les choses

| Quoi | Où |
|---|---|
| Spécifications (PRD) | `01_Specifications/` |
| Code | `src/pharmaflux/` : `cli.py`, `bronze.py` (lecture de l'archive), `tomlstrict.py` ; `collecte/` : `catalogue.py` (14 entrées), `page.py` (lecture de la page BDPM), `empreintes.py`, `telechargement.py`, `archive.py`, `manifeste.py`, `passage.py` (orchestration), `etat.py` ; `contrats/` : `modele.py`, `chargeur.py`, `verification.py`, `normalisation.py`, `profil.py`, `rendu.py`, `bdpm/*.toml` ; `evaluation/` : `questions.py`, `verification.py` ; `evenements/` : `snapshot.py`, `schema.py`, `comparaison.py`, `volume.py`, `bilan.py`, `rejeu.py` ; `bus/` : `enveloppe.py`, `client.py`, `registre.py`, `publication.py`, `verification.py`, `suivi.py`, `schemas/` ; `demo/` : `jeu.py`, `rejeu_accelere.py` ; `silver/` : `entrepot.py`, `schema.py`, `expressions.py`, `application.py`, `construction.py`, `consommation.py`, `etat.py`, `sql.py`, `comparaison.py`, `verification.py` ; `gold/` : `typage.py`, `qualite.py`, `vues.py`, `questions.py`, `rendu.py`, `sql.py` |
| Tests et fixtures | `tests/`, `tests/fixtures/` |
| Démo : jeu figé, Makefile, prérequis | `demo/` (archive et `README.md`), `Makefile`, `infra/demo/prerequis.sh` |
| Planification de la collecte (systemd, rapatriement) | `infra/planification/` |
| Décisions d'architecture | `docs/adr/` (gabarit : `0000-modele.md`) |
| Journal | `docs/journal.md` (ajout en fin de fichier) |
| Profil des sources | `docs/donnees/` (mission 01) |
| Jeu de questions de référence | `evaluation/` (PRD annexe B) |
| Circuit de travail, ordres, rapports, relectures | `docs/agents/`, `docs/missions/`, `docs/rapports/`, `docs/relectures/` |

## Outillage

Python 3.12 géré par `uv` (`.python-version`), `httpx`, `typer`,
`confluent-kafka` (mission 03), `pyiceberg[sql-sqlite]`, `pyarrow` et `duckdb`
(mission 05, avec `sqlalchemy` pour le catalogue ; `jsonschema` et
`pyarrow-stubs` en dev ; un paquet ajouté a au moins deux semaines, par
`constraint-dependencies`) ; `ruff` (lint et format), `mypy --strict` sur
`src/`, `pytest` (marqueur `integration`). Redpanda et sa console viennent
de `docker-compose.yml`. La CI (`.github/workflows/ci.yml`) a deux jobs :
`verifier` rejoue les mêmes commandes plus les tests des garde-fous du
circuit ; `integration` démarre le Redpanda du fichier compose, lance les
tests marqués, un saut y étant un échec (`PHARMAFLUX_INTEGRATION_EXIGEE`),
puis `make demo DEMO_OPTIONS=--sans-pause`. `make` (GNU 3.81 sur le Mac, 4.3
sur le runner) n'ajoute aucune dépendance ; `shellcheck` est tiré par `uvx` à
la demande. Aucun appel réseau vers les sources.

## Le silver : tables Iceberg SCD2 et « état à une date » (mission 05)

- **Entrepôt local** (`silver/entrepot.py`, ADR 0009) : un dossier sous
  `data/` (`data/lakehouse`, `data/demo/lakehouse` pour la démo), le
  catalogue SQL de PyIceberg sur `catalogue.sqlite`, une table Iceberg par
  entité (`bdpm.presentations`), chemins `file://` absolus (un entrepôt
  déplacé se rebâtit, `make rebatir` pour la démo). Aucun service, aucune
  extension DuckDB, pas de MinIO. Propriétés de table : entité, version du
  contrat, origine (`fichiers` ou `bus`), grappe et positions pour le bus.
- **Versions SCD2 sur la date d'observation** (`silver/schema.py`,
  `application.py`) : les colonnes du contrat en chaînes, puis `identite`
  (clé JSON du message, ou `<empreinte>#<rang>`), `debut_validite`,
  `fin_validite` (nulle = ouverte, borne exclue), les `id` et archives qui
  ouvrent et ferment, `version_contrat`, `etat_initial`, `anomalies`.
  `appliquer_lot` : doublons par `id`, SCD2 dans l'ordre du lot, rangs comptés
  comme `appliquer`, refus sans rien écrire, une transaction par lot
  (`set_properties`, `delete`, `append`). Le temps de la connaissance est
  **l'horodatage de l'archive**, à la seconde.
- **Commandes** : `silver construire` (fichiers d'événements, entrepôt
  neuf), `silver consommer` (le bus, position dans le commit, reprise à tout
  point, refus si le bus n'est pas celui du silver), `silver etat` (UTC à la
  seconde, `--ou`, `--format`), `silver sql` (DuckDB sans accès fichier,
  verrouillé, `SELECT` seul), `silver comparer`, `silver verifier` (snapshot
  recalculé par archive retenue, archives écartées, invariants du SCD2,
  code 2). Imports paresseux ; allocateur système d'Arrow.
- **`make silver`** après `make demo`, `make etat` ; la CI lance `make
  silver` dans le job `integration`. Mesures (28/10/2026) : `consommer`
  164 106 messages en 12,9 s et 357 Mo, `verifier` 22/22 en 10,3 s et
  341 Mo, `construire` 9,7 s et 297 Mo ; seuil d'alerte 512 Mo.
- **Mission close** quand `make rebatir`, `make demo` puis `make silver`
  finissent sur une vérification conforme des 18 archives retenues.

## Le gold : état typé, vues métier, contrôles (mission 06)

- **Calculé à la demande** (`gold/`, ADR 0010) : une fonction du silver et
  d'un instant, rien de stocké, ni bus ni événements ni bronze. Instants de
  `silver etat`, défaut la dernière observation ; le **jour** d'un instant
  est sa date UTC. Les vues et `gold qualite` refusent un instant où l'une des
  onze entités n'est pas encore observée (le message donne le premier instant
  où elles le sont toutes).
- **Typage par les anomalies** (`gold/typage.py`) : vide ou illisible → nul,
  et `colonnes_illisibles` le nomme ; sinon règle stricte sur la forme
  canonique (`decimal128(18, d)`, `date32` avec aller-retour, `int64`, `bool`,
  `list<T>`, `string`). Colonnes de version gardées : `identite`, `rang`,
  `date_source`, `debut_validite`, `archive_ouverture`, `version_contrat`,
  `anomalies` ; jamais `fin_validite` (ce qu'on a appris après l'instant).
- **Vues** (`gold/vues.py`, PyArrow et Python, pas de SQL) : fiche
  médicament (une ligne par CIS connu, `dans_referentiel`, sections en
  `list<struct>`, tous les avis, `provenance`) ; disponibilité courante
  (priorité `declare` > `fin_de_publication` > `aucun_signalement`, `portee`,
  `occurrences`, `debut_a_venir`) ; alternatives (groupe × présentation ×
  disponibilité, par `numero_tri`). Chaque vue a une requête DuckDB de
  référence dans `tests/references_gold.py`.
- **Contrôles** (`gold/qualite.py`) : 1 à 4 bloquants (invariants de la
  chaîne, code 2), 5 à 14 mesurés (faits de la source, toujours affichés).
- **Questions** (`gold/questions.py`) : `questions verifier --entrepot`,
  instant de l'archive citée, attendus normalisés puis typés, multiensemble ;
  code 2 sur une discordance ou hors de la fenêtre du silver.
- **`make gold`** après `make silver` (qualité, puis questions), `make fiche
  CIS=… A=…` ; la CI lance `make gold` dans le job `integration`. Mesures
  (29/10/2026) : `gold qualite` 312 Mo, `gold fiche --tout` 415 Mo,
  `questions verifier --entrepot` 452 Mo ; seuil 512 Mo.
- **Limite connue** : une brute illisible égale à la forme canonique de la
  valeur précédente (`24.34` pour `24,34`) ne fait pas d'événement, donc pas
  d'anomalie au silver ni au gold (ADR 0010, « Limites »).
- **Mission close** quand `make rebatir`, `make demo`, `make silver` puis
  `make gold` finissent sans bloquant et avec les 25 questions concordantes.
- **Tests** : `conftest.py` importe `pharmaflux.silver` en premier
  (allocateur système d'Arrow) ; `demo_silver` est construit une fois par
  session et reste en lecture seule.
