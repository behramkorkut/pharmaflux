# Mission 06 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `57e1ccd` (fils de `74c52e4`), contre l'ordre et
l'addendum 1 (`36d815e`). **Verdict : conforme, passe au palier 2.**

## Revérifié par l'IeC

Dans le dossier du codeur, arbre propre sur `57e1ccd` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 55 fichiers |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true`, courtier présent | 518 passed en 2 min 09 s, dont les tests d'intégration |

Relu dans le code (`gold/typage.py`, `gold/qualite.py`) :

- **Le typage part des anomalies** (A.1). Une colonne qui porte une règle
  de lisibilité est vidée avant toute conversion. Une valeur canonique que
  la règle stricte refuse est comptée dans `non_typables`, puis vidée, et
  le contrôle 3 la tient pour bloquante. Rien n'est vidé en silence.
- **Les motifs restent dans leurs types** :
  - un entier a au plus 18 chiffres, ce que tient un `int64` ;
  - un décimal a au plus 16 chiffres avant la virgule et exactement `d`
    après, ce que tient un `decimal128(18, d)`, l'échelle venant du
    contrat.
- **Les dates** : le motif ISO, puis `strptime`, puis un aller-retour par
  `strftime` qui doit redonner la chaîne. Le constat est bon : `strptime`
  d'Arrow lit le 30 février comme le 2 mars. Sans cet aller-retour, le gold
  aurait deviné une date. Le test le couvre.
- **Les listes** : un élément refusé vide toute la liste, et une valeur
  vide donne une liste nulle, pas une liste vide.
- **Le gold ne montre pas la fin d'une version** : `COLONNES_VERSION_GOLD`
  ne contient ni `fin_validite`, ni `id_fermeture`, ni `archive_fermeture`
  (C.1).
- **Les contrôles** : 1 à 4 bloquants, 5 à 14 mesurés, et chaque contrôle
  porte la règle qui le classe. Sur le jeu, les quatorze sont au chiffre
  du §0. Deux silvers corrompus à dessein font tomber les contrôles 3 et 4
  en code 2 : la qualité sait échouer.
- **Les données synthétiques sont construites en mémoire** dans les tests,
  et dites synthétiques. Aucun fichier sous `tests/fixtures/` ne se fait
  passer pour une archive réelle.

## Écarts du rapport

1. **`demo_silver` en portée session, dans `conftest.py`** : accepté. Une
   condition : le silver partagé est **en lecture seule** pour les tests.
   Aucun test n'écrit dedans, sinon l'ordre des tests changerait leurs
   résultats. C'est le cas aujourd'hui ; garde-le ainsi au palier 2.
2. **Le nom `smr_plus_asmr` du contrôle 10** : accepté, le nom dit ce qu'il
   compte.

## Le constat 2 : une limite du Lot 1, à garder visible

Le constat est juste, et il pèse plus qu'un détail. Prenons une source qui
écrit `24.34` là où elle écrivait `24,34`. La détection compare les valeurs
normalisées (ADR 0006) : elle trouve `24.34` des deux côtés, donc ne produit
aucun événement. Le silver garde la version sans anomalie, et le gold type
alors `24.34`. C'est exactement le cas que le typage par les anomalies veut
empêcher (« un `CAST` le lirait comme 12,50 € : ce serait deviner »), qui
revient par la détection. `silver verifier` ne le voit pas non plus,
puisqu'il compare les mêmes valeurs.

La corriger demanderait de changer la détection : comparer aussi les règles
d'anomalie d'une ligne, ce qui produirait un nouveau genre de `modifiee`.
Cela sort du périmètre de cette mission, qui ne touche pas au Lot 1. Donc :
- **ADR 0010** : une section « Limites », qui décrit ce cas avec l'exemple
  et dit que le contrôle 12 ne le compte pas ;
- **`pr.md`** : en proposition, une mission de détection qui compare aussi
  les anomalies, avec une nouvelle version du schéma d'événement si elle
  est nécessaire. L'IeC la portera au PRD.

## Pour le palier 2

- **L'exigence 1 de l'addendum** : chaque vue PyArrow est vérifiée contre
  sa requête DuckDB de référence, sur les fixtures et sur l'échantillon
  fixe du jeu. Le rapport donne la mémoire de ce test.
- **L'exigence 2** : la priorité « déclaré, puis fin de publication, puis
  aucun signalement », avec un test par branche.
- Les 25 questions concordantes, chaque commande `gold` sous 512 Mo, et ta
  démonstration de la décision 6.
