# Mission 04 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `642998b` (fils de `ab31fd3`), contre l'ordre et
l'addendum 1 (`aceb5ba`). **Verdict : conforme, passe au palier 2.**

## Revérifié par l'IeC

Sur une extraction du commit (`git archive 642998b`), hors du dossier du
codeur :

| commande | résultat |
|---|---|
| `uv run pytest -q` | 458 passed |
| `uv run ruff check .` / `uv run mypy src` | verts (38 fichiers) |
| `uv run pharmaflux demo verifier` | conforme : 781 lignes, 71 passages, 22 archives, 11 entités |

Relu dans le code :

- **F.1** : le tri numérique de l'historique (motif ancré, `re.escape`)
  est correct.
- **F.2** : le schéma courant passe par `compatible` avant
  l'enregistrement. Un sujet neuf (404) est jugé compatible
  (`absent_ok`). L'historique s'enregistre sans contrôle, comme il se doit.
- **F.3** : `_verifier_ordre` refuse tout le lot avant le premier message.
  Les chemins d'une entité partagent leur dossier, donc la comparaison
  des chaînes revient à comparer les noms.
- **Manifeste copié** : il contient 21 champs, et aucun ne donne un hôte
  ou une IP. La seule adresse est l'URL publique de la BDPM. Le README et
  le rapport ne citent aucun chemin personnel.
- **Le README du jeu** donne la source, la licence et la commande de
  fabrication. `test_demo.py` vérifie sa table de sha256 et ses nombres
  contre le manifeste, comme le demande l'addendum.

## Écarts du rapport

1. **`git count-objects -vH` refusé** : c'est l'erreur de l'IeC.
   L'addendum demandait une preuve que le garde-fou du codeur interdit.
   Tu as bien fait de ne pas chercher de variante. beko fera la mesure.
   La modification du garde-fou (permettre `git count-objects` en lecture
   à tous les rôles) est proposée à beko. Tu n'as rien à faire.
2. **Le contrôle « rien après la dernière archive » est abandonné** :
   accepté, c'est la conséquence de Q1.
3. **Le journal sur la sortie d'erreur** : accepté (Q4).
4. **F.2 testé sur le simulateur** : accepté pour ce palier. Le test
   `integration` contre le vrai registre, avec un schéma sans propriété
   requise et `compatible` faux attendu, **devient une obligation du
   palier 2**.
5. **Les noms commençant par un point sont ignorés par `verifier`** :
   accepté, c'est la règle de `pharmaflux.bronze`.

## Pour le palier 2

- **Rapport** : le modèle de `processus.md` demande quinze lignes au
  plus, et celui-ci en fait 93. Garde les détails dans le message de
  commit et les tests. Le rapport doit donner les mesures, les
  vérifications, les écarts et les questions.
- **F.3 passe dans `preparer`** : teste le refus sur
  `publier --reprendre` et sur `demo rejouer --reprendre` (addendum 1).
- **La mémoire de `demo rejouer`** : mesure `tracemalloc` par entité et la
  mémoire résidente maximale. Au-delà de 256 Mo, arrête-toi et signale-le.
- **`down -v`** : préviens beko avant d'effacer le bus de la mission 03.
