# Mission 06 — contrôle du palier 2 (IeC)

**Commit contrôlé** : `b9b4712` (fils de `8823759`, qui porte le contrôle du
palier 1 tel quel). Il est contrôlé contre l'ordre et l'addendum 1
(`36d815e`). **Verdict : conforme, passe au palier 3.**

## Revérifié par l'IeC

Dans le dossier du codeur, arbre propre sur `b9b4712` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 58 fichiers |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true`, courtier présent | 535 passed en 2 min 25 s, dont les tests d'intégration |

Relu dans le code (`gold/vues.py`, disponibilité courante) :

- **La priorité de l'exigence 2 est tenue par construction.** Les lignes en
  cours remplissent `declarees` en premier. Une ligne fermée n'est retenue
  que pour une cible absente de `declarees`, et seule la fermeture la plus
  récente compte. `aucun_signalement` ne va qu'aux présentations couvertes
  ni par l'une ni par l'autre.
- **Rien d'appris après l'instant.** `fermees` ne lit que les versions dont
  `fin_validite` est au plus l'instant. Un changement de statut
  (`supprimee` puis `creee` de la même ligne) ne donne pas de fausse fin de
  publication : la nouvelle ligne couvre la même cible, et l'ancienne est
  donc écartée.
- **L'expansion** : une ligne sans CIP13 vise toutes les présentations
  connues de la spécialité, et `portee` le dit. Une ligne qui ne vise
  aucune présentation connue garde une ligne, avec
  `presentation_connue = false`.

**L'exigence 1 est tenue** : chaque vue est égale à sa requête DuckDB de
référence, écrite à part dans `tests/references_gold.py` :
- sur les fixtures, à trois instants ;
- sur le jeu, sur 28 CIS, cas limites du §0 compris.

**L'objectif central de la mission est atteint dans la démonstration** :
les 25 questions concordent depuis le gold (9,0 s, 452 Mo). La fiche de la
présentation `3400938844948` la montre présente le 24/10 à 20:00 et absente
au 27/10.

## Écarts du rapport

1. **Les alternatives gardent une spécialité du groupe sans présentation**
   (`code_cip13` vide) : accepté. Le groupe générique est une donnée de la
   BDPM, et une spécialité sans présentation en fait partie. La vue le
   montre sans rien recommander.
2. **Refus d'un instant où une entité n'est pas encore observée** :
   accepté, et c'est la bonne règle. Sans elle, la vue dirait « aucun
   signalement » de toutes les présentations avant d'avoir lu le fichier de
   disponibilité, ce qui serait une affirmation fausse. Deux demandes :
   - le message de refus donne le **premier instant où les onze entités
     sont observées**, pour que l'utilisateur sache quoi taper ;
   - l'ADR 0010 écrit la règle et la distingue du recalcul des questions,
     qui ne lit que la fenêtre de son entité.
3. **Sortie JSON par lots de 500** : accepté. `gold fiche --tout` passe de
   552 à 415 Mo.
4. **`conftest.py` importe `pharmaflux.silver` en premier** : accepté. Un
   commentaire dans `conftest.py` doit dire pourquoi : l'allocateur système
   d'Arrow doit être posé avant le premier import de PyArrow, sinon la
   mémoire passe de 524 à 945 Mo. Sans ce commentaire, le premier ménage
   venu supprimera cet import « inutile ».
5. **Un seul fil pour la connexion de référence des tests** : accepté. Le
   code de production ne change pas.

**La mémoire du test de l'exigence 1** (524 Mo pour le processus entier)
dépasse le seuil de 512 Mo. Ce seuil vaut pour les **commandes**, pas pour
la suite de tests, et le runner de la CI a plusieurs gigaoctets : ce n'est
pas bloquant. `pr.md` donne ce chiffre tel quel.

## Pour le palier 3

- **`make gold`** (qualité, puis questions avec `--entrepot`) et
  **`make fiche CIS=… A=…`** : `make -n` dans le rapport. L'étape de CI vient
  juste après « make silver ».
- **La séquence de beko** : `make rebatir`, `make demo`, `make silver`, puis
  `make gold`. Clôture : aucun bloquant, et 25 questions concordantes.
- **L'ADR 0010**, avec sa section « Limites » (constat 2 du palier 1), la
  règle des instants (écart 2), le jour UTC, `fin_validite` hors du gold, et
  le texte de la fiche qui n'engage pas le Lot 3.
- **Le README**, avec ses deux exemples réels : la fiche de `63830632` aux
  deux instants, et la disponibilité de LARIAM (`3400933961688`), couverte
  par une ligne sans CIP13.
- Les demandes des écarts 2 et 4 ci-dessus.
