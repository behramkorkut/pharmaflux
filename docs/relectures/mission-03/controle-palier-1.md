# Mission 03 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `eb79940` (le commit `6ea3405` ne change qu'une ligne
du rapport). **Verdict** : palier 1 **accepté**, sans correctif. Le partage
des valeurs répétées est gardé. Passe au palier 2.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au sommet `6ea3405` (même code que
`eb79940`) :

- ruff check et format : vert ;
- mypy, 30 fichiers : vert ;
- pytest : 414 tests, tous passent, dont `tests/test_memoire.py` ;
- rejeu complet des onze fichiers avec `/usr/bin/time -l`, sorties hors du
  dépôt :

| exécution | mémoire résidente maximale | durée | sortie |
|---|---|---|---|
| référence : code de `main` (src identique à `647fb6a`) | 458 Mo | 7,7 s | 30 fichiers, 173 Mo |
| palier 1, exécution 1 | 114 Mo | 7,9 s | `diff -r` vide |
| palier 1, exécution 2 | 134 Mo | 7,8 s | `diff -r` vide |
| palier 1, exécution 3 | 139 Mo | 7,9 s | `diff -r` vide |
| `--reprendre` sur cette sortie | 107 Mo | — | code 0 |

La cible de 160 Mo est tenue à chaque exécution. Les chiffres du rapport
sont reproduits, à la variation près que le rapport signale déjà.

## Sur le fond

- **La comparaison en flux** est juste. La clé de tri d'un squelette
  reprend exactement `Evenement.cle_de_tri` : les colonnes de la clé par
  ordre de leur nom, l'ordre des types, l'empreinte, puis le rang signé.
  Le tri est stable, et les squelettes sont produits dans le même ordre
  qu'avant : l'ordre écrit est donc le même **par construction**, ce que
  le `diff -r` confirme.
- **`Resultat.evenements()` recalculé à la demande** : c'est la bonne
  façon de retirer `Suivi.resultats` (K.1) sans changer ce que les tests
  vérifient. Le bilan reçoit les comptes de celui qui écrit. Sans comptes,
  il recompte, et le cas d'une archive écartée donne toujours un écart
  sans événements.
- **`_traiter_archive`** pour que tout meure au retour : bien vu, et le
  rapport mesure ce que cela évite (trois snapshots vivants, 200 Mo).
  Ses neuf paramètres ne gênent pas pour l'instant (écart 4). Pas de
  regroupement à faire dans cette mission.
- **Les tests** : le diff ne touche que la forme (`list(…)`,
  `evenements()`, les résultats rendus par `traiter`). Aucun attendu ne
  change. L'assertion « recalculés à chaque demande » est un bon ajout.
- **Le test de mémoire** compare un ratio, pas un seuil en mégaoctets :
  c'est ce qu'avait demandé l'addendum. 4 000 lignes au lieu de 20 000
  (écart 2) : accepté, le ratio est du même ordre et la suite reste
  rapide.
- **L'ADR 0006** est mis à jour, daté, avec les options écartées.

## Réponse à la question (écart 1)

**Le partage des valeurs répétées est gardé.** Le flux seul laissait
171 Mo, au-dessus de la cible, et la cause est mesurée : deux snapshots de
`presentations` qui coexistent. Le remède tient en deux lignes et ne
change aucune valeur : il ne fait que partager des objets chaîne. La sortie
est identique, aucun attendu ne change, et les invariants `brutes is` et
`normalisees is brutes` sont conservés. Toucher `contrats/verification.py`
est justifié ici. Une seule condition : ce partage ne doit jamais devenir
une condition de justesse. Aucun code ne doit comparer des valeurs avec
`is`, seulement avec `==`.

## Pour la suite

- **Rapport de palier** : le modèle de `docs/agents/processus.md` demande
  quinze lignes au plus. Celui-ci en fait plus de cent. Pour le palier 2,
  mets le détail dans l'ADR ou le journal, et garde dans le rapport ce qui
  sert au contrôle : ce qui est fait, les vérifications, les écarts et les
  questions.
- **Palier 2** : avant toute commande `docker compose up`, attends que
  beko ait choisi les tags des images et fait le premier
  `docker compose pull`. Le garde-fou refuse le téléchargement aux agents.
  Écrire le fichier compose ne demande aucune commande docker.
