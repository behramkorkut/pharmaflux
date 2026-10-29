# Mission 06 — palier 1 : colonnes typées et contrôles de qualité (décisions 1 et 3)

Addendum 1 lu (`36d815e`). Python pur : aucune commande `docker`, `colima`
ni `make` ; `~/pharmaflux-data` en lecture seule ; aucune requête vers les
sources ; aucun refus du garde-fou. Le courtier du projet tournait sur le
Mac : les 11 tests d'intégration ont tourné.

**Fait**

- **`pharmaflux.gold`** (`__init__` : constantes seulement, aucun import de
  PyArrow) : `typage` (état typé d'une entité à un instant), `qualite` (les
  quatorze contrôles), `sql` (la connexion de `silver sql`, sans la modifier,
  avec les entités typées sous leur nom court).
- **Typage** (A.1, A.2, C.1) : depuis les anomalies du silver, jamais depuis
  la valeur seule ; règle stricte sur la forme canonique par type
  (`decimal128(18, d)`, `date32`, `int64`, `bool`, `list<T>`, `string`) ;
  une valeur vide ou illisible est nulle, et `colonnes_illisibles` nomme les
  colonnes vidées ; une valeur canonique que le type refuse est comptée
  (`non_typables`, contrôle 3). Colonnes de version gardées : `identite`,
  `rang`, `date_source`, `debut_validite`, `archive_ouverture`,
  `version_contrat`, `anomalies` ; ni `fin_validite`, ni `id_fermeture`, ni
  `archive_fermeture`.
- **Contrôles** (G, G.1) : 1 à 4 bloquants (clés uniques, une version par
  identité, valeurs canoniques typables, aucune entité vidée), 5 à 14
  mesurés, toujours affichés ; la règle qui classe est portée par chaque
  contrôle. Volumes : lignes à l'instant et écart à l'état juste avant le
  dernier changement de l'entité. Code 2 si un bloquant tombe.
- **Commandes** : `gold etat` (`--entite`, `--a`, `--ou`, `--colonne`,
  `--format`), `gold qualite` (`tableau` ou `jsonl`), `gold sql` ; `--a`
  facultatif, défaut la dernière observation du silver, dite sur la sortie
  d'erreur. Un décimal sort en chaîne exacte (`"1.16"`), une date en
  `AAAA-MM-JJ`.
- **Tests** (`test_gold.py`, 15 ; `test_gold_demo.py`, 3) : chaque type sur
  ses formes canoniques et ses refus ; « `24.35` brut avec anomalie » vide,
  « `24.35` canonique » typé ; un bronze fait des onze extraits réels, puis
  de deux variantes **synthétiques construites en mémoire** (prix à point,
  date d'AMM au 31 février) ; deux silvers corrompus à dessein (événements
  retouchés) qui font tomber les contrôles 3 et 4 en code 2 ; CLI et refus ;
  imports paresseux ; sur le jeu, les quatorze contrôles à leur chiffre du
  §0, et l'état typé à deux instants sans valeur non typable. Le silver du
  jeu est construit **une fois par session** pour le silver et le gold
  (`demo_silver` passé de `test_silver_demo.py` à `conftest.py`).
- **Journal** : la durée de `make silver` en CI (37 s, 38 s), puis le §0 et
  ce palier.

**Vérifications locales** (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 218 files already formatted |
| `uv run mypy src` | Success: no issues found in 55 source files (0 `type: ignore`) |
| `GITHUB_ACTIONS=true uv run pytest -q` | **518 passed** en 129 s (500 avant ; les 11 `integration` ont tourné, courtier présent) |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| `demo verifier` ; `profil`, `questions verifier` sur `~/pharmaflux-data` | conforme ; 0 bloquante ; 25 conformes, 5 non calculables, 10 sans attendu |
| `evenements` sur la copie du Mac, `diff -r` contre la sortie du code fusionné `53f261b` | identique (la copie est encore le jeu : 24, 26, 27/10) |
| `silver verifier` sur le jeu | 22/22 conformes, 10,9 s, 352 Mo |
| `gold qualite` (jeu, dernière observation / 24/10 20:00) | code 0, aucun bloquant ; 1,3 s et **310 Mo** / 1,2 s et 307 Mo |
| `gold etat --entite bdpm.compositions` (32 439 lignes) / une présentation | 1,2 s et 255 Mo / 0,7 s et 144 Mo |
| `gold sql` (jointure présentations × spécialités, somme de décimaux) | 1,1 s et **300 Mo** |

Chiffres du jeu (`gold qualite`, 2026-10-27T00:17:12Z) : 1 à 4 → 0 ;
5 → 4 ; 6 → 5 562 ; 7 → 1 268 ; 8 → 1 ; 9 → 23 ; 10 → 2 375 (SMR 1 023,
ASMR 1 352) ; 11 → 5 ; 12 → 1 ; 13 → 18 383 ; 14 → présentations 20 888,
−7 (−0,03 %) au 27/10, les dix autres à l'état initial. Toutes les commandes
`gold` restent sous 512 Mo.

**Écarts à l'ordre**

1. `demo_silver` déplacé dans `conftest.py` (portée session) : le gold relit
   le silver du jeu au lieu d'en bâtir un second (une vingtaine de secondes).
2. Le détail du contrôle 10 nomme sa somme `smr_plus_asmr` : un dossier cité
   par les deux fichiers y compte deux fois, ce que le nom dit.

**Constats**

1. **`strptime` d'Arrow est indulgent** : `2026-02-30` donne le 2 mars, sans
   erreur. Le typage relit la date et exige la même chaîne ; le test le
   couvre. Sans le test, une date impossible aurait été devinée.
2. **Une brute égale à la forme canonique de la valeur précédente ne fait
   pas d'événement** : si la source écrit `24.34` là où elle écrivait
   `24,34`, la détection (qui compare les valeurs normalisées, ADR 0006) ne
   voit rien, et le silver garde la version et les anomalies de `24,34`. Le
   gold tape alors `24.34`, ce qui est la même valeur ; mais le contrôle 12
   ne verra pas cette illisibilité. C'est hors périmètre (la détection ne
   change pas) ; je le signale pour l'ADR 0010 et pour `pr.md`.

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** : le constat 2, à proposer dans `pr.md`
(comparer aussi l'ensemble des règles d'anomalie d'une ligne, ou le
documenter comme limite).
