# Mission 08 — palier 1 : recherche hybride et jeu v1 (décisions 1 et 2)

Addendum 1 lu (`385490b`). **Aucun appel à l'API.** Qdrant et le vrai modèle
étaient présents sur le Mac ; l'index a été reconstruit au format 2 et mesuré.
Aucun refus du garde-fou. Le jeu v1 a été rédigé puis vérifié sans LLM.

## Fait

**Le tokenizer lexical** (`index/lexical.py`, Python pur) : minuscules, accents
dépliés (NFKD), suites alphanumériques entières (un CIS à 8 chiffres et un
CIP13 à 13 chiffres restent un seul jeton), unités de dose ramenées à une
graphie (`µg`, `mcg`, `microgramme(s)` → `ug`). **Ni racinisation, ni liste de
mots vides** (addendum A3 : les noms et les codes sont la cible, l'IDF écrase
les mots communs). Un test fige la sortie sur dix cas et `|d|` sur un cas.

**Le vecteur creux BM25** : l'indice d'un terme vient d'un `blake2b` sur
**31 bits** (pas de `hash()`), les collisions s'additionnent (0 collision sur
les 65 363 termes distincts du jeu). La valeur est le terme « document » de
BM25, `f·(K1+1) / (f + K1·(1 − B + B·|d|/avgdl))`, avec **`K1 = 1,2`,
`B = 0,75` et la longueur moyenne `avgdl = 53,29` figées** dans le code et
l'ADR (mesurée une fois sur les 72 296 fragments du jeu, puis jamais
recalculée). L'**IDF est laissé à Qdrant** (`modifier: idf`) : la valeur
stockée ne dépend donc que du texte, et l'incrément comme `verifier` restent
justes. La requête porte la fréquence brute de ses termes.

**Format 2** (`index/fragments.py`, `index/qdrant.py`) : le texte des fragments
ne change pas, mais chaque point porte un vecteur creux nommé `lexical` à côté
du `dense`. Le bump de format force une reconstruction unique ; les **72 296
vecteurs denses sont relus du cache (0 réencodé), en 38 s**, résident 419 Mo.
Deux constructions depuis le jeu donnent **le même instant**
`2026-10-27T00:17:12Z` (la seconde écrit la collection `…-bis`, l'index
restant lisible).

**La fusion** (`index/construction.py`) : un **RRF côté client**, `k = 60`,
**50 candidats par voie** (dense exact + creux), les ex æquo tranchés par
identifiant. **Aucun réglage sur le jeu d'évaluation.** `index chercher` est
désormais hybride par défaut ; `--mode` n'est pas exposé (un `mode` interne
sert à la mesure).

**`index evaluer`** sort le rappel du **dense seul, du creux seul et de
l'hybride**, côte à côte, sur les questions qui nomment un médicament.

**`index verifier`** compare aussi le **vecteur creux** au recalcul depuis le
texte (indices égaux, valeurs égales en `float32`), sans jamais lire un score
multiplié par l'IDF. Sur l'index du Mac au format 2 : **conforme** (0 manquant,
0 orphelin, 0 texte/métadonnée, 0 vecteur dense, 0 vecteur creux différent,
cosinus minimal 0,9954), 413 et 416 Mo.

**Le jeu v1** (`evaluation/questions-reference-v1.toml`, `version = "v1"`,
`instant = "2026-10-27T00:17:12Z"`) : **88 questions, au moins 10 par
catégorie** (disponibilite 12, remboursement 12, avis_has 11, historique 11,
hors_perimetre 11, medical 11, alternatives 10, depense 10). Les attendus sont
datés à l'instant de l'index et vérifiés **sans LLM**, depuis le bronze du jeu
de démo (sha256) et depuis le gold à cet instant, les deux concordant. Reprise
de la v0 (identifiants stables), avec : `alternatives-004` **retirée**,
remplacée par une question sur le groupe générique (`alternatives-006`) ;
`avis_has-005` qui passe d'abstention à **réponse avec réserve** (`reserve =
true` : le SMR CT-21978 du CIS 67026956, absent de `CIS_bdpm.txt`). Les
**pièges** : un nom proche (`disponibilite-009`, SUNITINIB BIOGARAN vs
ZENTIVA), un CIS hors référentiel (`disponibilite-005`), une médicale déguisée
en disponibilité (`medical-006`, refus), deux médicaments (`disponibilite-010`,
abstention « un à la fois »). Les **deux cas limites sans refus** (addendum D) :
une disponibilité « pour mon traitement » (`disponibilite-011`, réponse, le
fait sans conseil) et une question d'effets indésirables (`hors_perimetre-006`,
abstention hors périmètre). Les champs de notation (`cis_attendu`,
`section_attendue`, `reserve`, `mots_interdits`) sont posés sur les réponses
(par exemple `mots_interdits = ["disponible"]` pour un « aucun signalement »).
`questions verifier` lit la v1 comme la v0 ; la v0 reste intacte et rejouable.

## Mesure du rappel — dense seul, creux seul, hybride

Sur les questions qui nomment un médicament (`index evaluer`). Cible de
l'addendum A : l'hybride au moins égal au dense pour le bon CIS à 5 et à 10, et
meilleur sur `identite`. Atteinte.

**Jeu v0** (22 questions) :

| mode | bon CIS @1/5/10 | bon CIS + section @1/5/10 | rang réciproque |
|---|---|---|---|
| dense | 16 / 20 / 20 | 11 / 17 / 18 | 0,623 |
| creux | 20 / 22 / 22 | 10 / 17 / 19 | 0,591 |
| **hybride** | **21 / 22 / 22** | **12 / 20 / 21** | **0,679** |

**Jeu v1** (47 questions) :

| mode | bon CIS @1/5/10 | bon CIS + section @1/5/10 | rang réciproque |
|---|---|---|---|
| dense | 37 / 45 / 45 | 27 / 39 / 41 | 0,680 |
| creux | 43 / 47 / 47 | 25 / 39 / 42 | 0,642 |
| **hybride** | **45 / 47 / 47** | **30 / 42 / 46** | **0,747** |

Les deux questions `identite` que le dense ratait (`disponibilite-005`,
`avis_has-005`) sont retrouvées par l'hybride. Le creux seul gagne le bon CIS à
1 mais perd la bonne section et le rang réciproque ; l'hybride prend le meilleur
des deux.

## Vérifications locales (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 269 files already formatted |
| `uv run mypy src` | Success: no issues found in 68 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **620 passed** (601 au départ de la mission) |
| `uv run pytest -q -rE -m "integration or modele"` | 17 passed |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK (21 tests) |
| `questions verifier --questions …v1.toml --racine demo/archive` | 88 : 55 conforme, 10 non calculable, 23 sans attendu |
| `questions verifier …v1.toml … --entrepot data/demo/lakehouse` | 55 depuis le gold : 55 concorde |
| `questions verifier` (v0, non-régression) | 25 conformes, 5 non calculables, 10 sans attendu ; 25 concordent |
| `index construire` (format 2, cache dense) | 72 296 fragments, 0 encodé, 72 296 repris, 38 s, 419 Mo |
| `index verifier` (format 2) | conforme, cosinus minimal 0,9954, 413 et 416 Mo |
| `index evaluer` (v0 puis v1) | tableaux ci-dessus, 431 et 470 Mo |

## Écarts à l'ordre

- **88 questions** au lieu d'« environ 90 » : toutes les catégories restent
  au-dessus du seuil de dix (deux à dix, six à onze ou douze). Un onzième
  `alternatives` ou `depense` s'ajoute sans peine si l'IeC le veut.
- **`depense`** garde l'encodage de la v0 : `comportement = "reponse"` avec
  `calculable_au = "lot4"`. Le couple « abstention + `calculable_au` » est
  refusé par le parseur (`calculable_au` n'a de sens que pour une réponse) ;
  `calculable_au = "lot4"` est la forme valide que la notation du Lot 3 lira
  comme « l'assistant s'abstient avant le Lot 4 ».
- **`doit_citer` / `instant_cite`** (listés à l'addendum E3) ne sont **pas** des
  champs par question : pour une réponse, « citer une source et sa date » et
  « dire l'instant de l'index » sont des invariants que la notation du Lot 3
  appliquera à toute réponse, non une option à régler question par question.
  Les champs posés par question sont `cis_attendu`, `section_attendue`,
  `reserve` et `mots_interdits`. À confirmer au Lot 3 (notation).
- **Questions sur présentations** : `CIS_CIP_bdpm.txt` ayant changé le 26/10,
  les attendus `remboursement`/`historique` portant sur une présentation citent
  l'archive du **27/10** (l'instant de l'index), pas celle du 24/10 ; les
  fichiers inchangés dans la fenêtre restent cités au 24/10.

## Questions pour l'IeC

- Faut-il un onzième `alternatives` et `depense` pour atteindre 90 pile, ou 88
  convient-il (≥ 10 par catégorie) ?

## Propositions d'évolution (PRD, consignes)

Aucune.
