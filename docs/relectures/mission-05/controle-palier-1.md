# Mission 05 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `438ae4e` (fils de `7103e8b`), contre l'ordre et
l'addendum 1 (`b5b9420`). **Verdict : conforme, passe au palier 2.**

## Revérifié par l'IeC

Dans le dossier du codeur, arbre propre sur `438ae4e` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 50 fichiers |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true` | 490 passed en 92 s |

Relu dans le code :

- **`appliquer_lot`** suit les règles d'`appliquer` du Lot 1
  (`evenements/comparaison.py`). Supprimer le rang r demande exactement
  r occurrences ouvertes, et créer le rang r en demande r − 1. Le tri des
  événements (`cle_de_tri` : rangs décroissants pour les `supprimee`) garde
  ce compte juste dans l'ordre du flux. Tous les refus sont levés avant la
  transaction, donc un lot refusé n'écrit rien. Un lot entièrement en
  doublon ne pose que les propriétés de table, sans snapshot.
- **Le filtre de validité** (`etat.filtre_validite`) est la règle de
  l'ordre : début inclus, fin exclue, et une fin nulle veut dire une
  version ouverte. Il est passé à PyIceberg en entier, comme le demandait
  K.6.
- **`lire_instant`** refuse un instant sans fuseau ou avec une fraction de
  seconde, et convertit tout en UTC.
- **La vérification** : les archives et leurs verdicts viennent des
  bilans. Le snapshot attendu est recalculé depuis le bronze pour chaque
  archive retenue ou confirmée. Une archive écartée est comparée au
  dernier snapshot retenu. Le test des fixtures passe par `ecarte` et par
  `confirme`, et `test_verifier_voit_une_version_qui_manque` montre que la
  vérification sait échouer.
- **L'allocateur d'Arrow** est posé par `os.environ.setdefault` avant tout
  import de PyArrow : une valeur choisie par l'utilisateur reste prioritaire.
- **Le journal** commence bien par la correspondance des hashes.

## Écarts du rapport

1. **`silver sql` sans `allowed_directories`** : accepté. C'est plus strict
   que l'addendum, et la raison est mesurée : un dossier autorisé l'est
   aussi en écriture. DuckDB ne reçoit que des jeux de données Arrow, la
   connexion naît sans accès externe, puis elle est verrouillée, et seuls
   `SELECT` et `EXPLAIN` passent. L'ADR 0009 donne cette raison, en une
   phrase.
2. **Deux plafonds de plus** (`sqlalchemy<2.0.55`, `cachetools<7.2.2`) :
   accepté, l'addendum le prévoyait. Une remarque pour l'ADR 0009 : ces
   plafonds ne sont pas permanents. Ils bloquent aussi les correctifs de
   sécurité. La règle à écrire : à chaque mission qui touche aux
   dépendances, on remonte les plafonds jusqu'à la dernière version qui a
   deux semaines.
3. **Le premier snapshot sans `ecart`** : accepté. Une `creee` par ligne
   bien formée, c'est la règle de l'ADR 0006.
4. **`fetch_arrow_table` remplacé** : rien à dire.

## Pour le palier 2

- **D.1** : le rapport dit si un `down -v` change l'identifiant de grappe
  de Redpanda.
- **Mesure de `consommer`** : sous le seuil de 512 Mo, ou arrêt et
  signalement avant le commit.
- **La démonstration de la décision 6** : construire le silver depuis le
  bus de la démo, le comparer (`silver comparer`) à celui construit depuis
  les fichiers, puis le vérifier contre l'archive, avec les temps et la
  mémoire. Si elle demande un `down -v`, préviens beko en une ligne
  avant : il efface le bus de la démo.
- **La suite de tests** passe de 36 à 92 s. Ce n'est pas bloquant, mais si
  le palier 2 ajoute un second test sur le jeu entier, partage la fixture
  `demo_silver` (portée `module` ou `session`) plutôt que de reconstruire.
