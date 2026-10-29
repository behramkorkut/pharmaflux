# Mission 06 — le gold : colonnes typées, fiche médicament, disponibilité courante, contrôles de qualité, questions recalculées, `make gold`

Branche `mission-06-gold-et-qualite`, depuis `aedf134` (le `main` du départ ;
`main` porte en plus l'addendum 1, `36d815e`, sans conflit : la branche ne
touche pas à `docs/missions/`). §0 en `74c52e4`, cette description en
dernier. Ordre de mission : `docs/missions/mission-06-gold-et-qualite.md`
(addendum 1, `36d815e`). Codeur : Claude Opus 5.5. Trois paliers acceptés par
l'IeC ; trois contrôles commis tels quels dans `docs/relectures/mission-06/`.
Relecture 1 : **CONFORME**, 0 bloquant, trois points non bloquants corrigés en
`6cadc6f` (`reponse-relecture-1.md`), à vérifier au contrôle final ; pas de
tour 2. Revue finale de l'IeC : à venir sur le commit qui porte cette
description.

## Ce qui est livré

Le gold (Lot 2, PRD v0.7 §6.5 et annexe B, ADR 0010) : **une fonction du
silver et d'un instant**, sans table stockée. Il ne lit ni le bus, ni les
événements, ni le bronze, hors la vérification des questions, dont la
référence reste le bronze.

**Colonnes typées et contrôles de qualité** (palier 1, `57e1ccd`). Le typage
part des **anomalies** du silver, jamais de la valeur seule. Une valeur vide
ou illisible est nulle, `colonnes_illisibles` la nomme, et la brute reste dans
le silver. Sinon, une règle stricte s'applique sur la forme canonique :
`decimal128(18, d)` (un prix reste exact), `date32` avec un aller-retour
(`strptime` d'Arrow lit le 30 février comme le 2 mars), `int64`, `bool`,
`list<T>`, `string`. Une valeur canonique que le type refuse est comptée,
jamais vidée en silence. `fin_validite` n'entre pas dans le gold : à un instant
passé, elle dirait ce qu'on a appris après. Quatorze contrôles : quatre
**bloquants** (invariants de la chaîne, code 2) et dix **mesurés** (faits de la
source, toujours affichés). Commandes : `gold etat`, `gold qualite` et
`gold sql`, qui reprend la barrière de `silver sql` sans la modifier.

**Vues métier et questions** (palier 2, `b9b4712`), construites en PyArrow et
en Python. Faite en SQL DuckDB, la fiche montait à 552-705 Mo.
- **La fiche médicament** a une ligne par CIS connu : 21 445 sur le jeu, dont
  5 562 fiches partielles, marquées `dans_referentiel = false`. Ses sections
  sont des `list<struct>` triées. Elle garde tous les avis SMR et ASMR, porte
  sa `provenance`, et peut se rendre en texte (`gold fiche --format texte`).
- **La disponibilité courante** suit la priorité `declare`, puis
  `fin_de_publication` (lue dans les seules versions fermées au plus à
  l'instant), puis `aucun_signalement`. Elle porte `portee`, `occurrences`,
  `presentation_connue` et `debut_a_venir`.
- **Les alternatives** croisent groupe générique, présentations et
  disponibilité, triées par `numero_tri`, sans classement.

Chaque vue est égale, en multiensemble, à une **requête DuckDB de référence**
écrite à part (`tests/references_gold.py`), sur les fixtures à trois instants
et sur un échantillon fixe de 28 CIS du jeu. Chaque branche de la priorité a son
test, sur un fichier de disponibilité **synthétique construit en mémoire**.
`questions verifier --entrepot` recalcule les 25 questions depuis le gold, à
l'instant de leur archive, et les compare en multiensemble, avec le code 2 sur
une discordance ou hors de la fenêtre du silver : **les 25 concordent**,
24 par une vue métier, 1 par les colonnes typées.

**`Makefile`, CI, docs** (palier 3, `c3c36de` ; `d2c8748`) :
- `make gold` lance `gold qualite`, puis `questions verifier --entrepot` ;
  `make fiche CIS=… A=…` affiche une fiche en texte ;
- la CI ajoute une étape « make gold » dans le job `integration`, après
  « make silver » ;
- l'ADR 0010 a sa section « Limites » et la règle des instants ;
- le README a une section « Le gold », avec la fiche de 63830632 à 23:17:11 et
  23:17:12 le 24/10 et la disponibilité de LARIAM ; sa section « État » est
  remise à jour ;
- `CONTEXTE.md` et le journal sont complétés, dont la durée de `make silver`
  en CI (37 s sur la PR #6, 38 s sur `main`).

## Vérifications locales (commit testé : `6cadc6f`)

Arbre propre, en une passe, dans `pharmaflux-codeur/`. Le courtier du projet
tournait.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 232 files already formatted |
| `uv run mypy src` | Success: no issues found in 58 source files (0 `type: ignore`) |
| `GITHUB_ACTIONS=true uv run pytest -q` | **538 passed** en 146 s (500 à la fin de la mission 05) |
| `uv run pytest -q -m integration` | 11 passed |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| `uv run pharmaflux profil` (sur `~/pharmaflux-data`) | 11 fichiers profilés, 0 anomalie bloquante |
| `uv run pharmaflux questions verifier` (sur `~/pharmaflux-data`) | 25 conforme, 5 non calculable, 10 sans attendu |
| `pharmaflux evenements` sur la copie du Mac, `diff -r` contre la sortie du code fusionné `53f261b` | identique (la copie est encore le jeu : 24, 26, 27/10) |
| `uv run pharmaflux demo verifier` | conforme |
| `silver verifier --entrepot data/demo/lakehouse --sortie data/demo --racine demo/archive` | **22/22** conformes, 10,3 s |
| les deux commandes de `make gold` sur `data/demo/lakehouse` | `gold qualite` code 0, aucun bloquant ; `questions verifier --entrepot` code 0, **25 concorde** |

## Démonstration de beko

Le 29/10/2026, sur le Mac, dans `pharmaflux-codeur/` : `make rebatir`, `make
demo`, `make silver`, puis `make gold` (sortie citée dans `palier-3.md`).
- **`make demo`** : 22 archives, 18 fichiers publiés, 4 écartés, 67 h 35 min
  rejouées en 4 min 03 s ; `verifier-bus` conforme.
- **`make silver`** : 164 106 messages en 14,2 s ; 22/22 conformes.
- **`make gold`** : « 14 contrôles à 2026-10-27T00:17:12Z : 4 bloquants, 10
  mesurés ; aucun bloquant ne tombe », puis « 25 question(s) depuis le gold :
  25 concorde. »

**La mission est close au sens de l'ordre.**

## Mémoire (Mac arm64, jeu de démo ; seuil de 512 Mo par commande, ADR 0009)

| commande | résident maximal |
|---|---|
| `gold qualite` | 312-315 Mo |
| `gold fiche --cis …` / `gold disponibilite` / `gold alternatives` / `gold sql` | 411-421 Mo |
| `gold fiche --tout` | 415 Mo (552 avant la sortie par lots) ; 424 Mo mesurés par la relecture |
| `questions verifier --entrepot` | 452 Mo ; **470 Mo mesurés par la relecture 1**, une quarantaine de mégaoctets de marge sur la commande la plus lourde |
| test de l'exigence 1 sur le jeu, seul (rejeu, silver, gold et référence dans un même processus) | **524 Mo**. Le seuil vaut pour les commandes, pas pour la suite de tests ; sur un silver déjà bâti, 411 Mo pour les vues et 436 Mo avec la référence |

## Durée de l'étape `make gold` dans la CI

À compléter après la publication. Estimée à 5-10 s au §0. Pour comparaison,
l'étape make silver dure 37 s (PR #6).

## Écarts acceptés

- **Palier 1** :
  - `demo_silver` est construit une fois par session, dans `conftest.py`, et
    reste en lecture seule pour tous les tests ;
  - le détail du contrôle 10 s'appelle `smr_plus_asmr`.
- **Palier 2** :
  - les alternatives gardent une ligne pour une spécialité du groupe sans
    présentation ;
  - un instant où l'une des onze entités n'est pas encore observée est refusé
    par les vues et par `gold qualite`, et le message donne le premier instant
    où elles le sont toutes ;
  - la sortie JSON se fait par lots de 500 ;
  - `conftest.py` importe `pharmaflux.silver` en premier (allocateur système
    d'Arrow : 524 Mo contre 945), avec un commentaire qui dit pourquoi ;
  - la connexion de référence des tests tourne sur un seul fil.
- **Relecture 1** (`6cadc6f`) :
  - deux fermetures au même instant se départagent comme dans la référence
    (un champ vide perd), et le cas est testé ;
  - `gold disponibilite` et `gold alternatives` refusent un code inconnu au
    lieu de répondre vide ;
  - un prix absent s'écrit « — » sans unité ;
  - `gold qualite` lit les validités de chaque table une seule fois ;
  - l'ADR 0010 écrit la règle de l'information à début illisible, et que la
    fiche ne dit que l'en-cours.

## Propositions

1. **Une mission de détection qui compare aussi les anomalies.** Si la source
   écrit `24.34` là où elle écrivait `24,34`, la détection compare les valeurs
   normalisées et ne produit aucun événement. Le silver garde alors la version
   sans anomalie, et le gold type la brute illisible. Comparer aussi les règles
   d'anomalie d'une ligne, avec une nouvelle version du schéma d'événement si
   elle est nécessaire (ADR 0010, « Limites »).
2. **La date du dernier fichier retenu par entité, portée par le silver**
   (une propriété de table, par exemple). Aujourd'hui, une fiche cite la source
   de l'ouverture de la version : une valeur inchangée depuis le 24/10 cite le
   23/10, même si le fichier a été republié depuis.
3. **La fin de publication dans la fiche, à régler au Lot 3**, quand la fiche
   sera indexée. Pour l'instant, elle ne donne que les signalements en cours,
   et la fin de publication se lit dans `disponibilite_courante` (ADR 0010).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
