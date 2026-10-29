# Mission 07 — revue finale de l'IeC

**Commit revu** : `883442b` (`pr.md`), sur le code de `50e7533`. Il est revu
contre l'ordre et l'addendum 1 (`241bff0`), les trois contrôles de palier,
les décisions prises par messages pendant le palier 2, et la relecture 1
(CONFORME). **Verdict : fusion autorisée, après un commit de `pr.md` qui
apporte la correction ci-dessous.** Le code n'est pas à reprendre.

## Revérifié par l'IeC

Dans ton dossier, arbre propre sur `883442b`, Redpanda, Qdrant et les
fichiers du modèle présents :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts (264 fichiers) |
| `uv run mypy src` | vert, 67 fichiers |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **601 passed** en 4 min 26 s, sans erreur ni réessai compté |
| `git merge-base HEAD origin/main` | `69b2df1`, comme le dit `pr.md` |
| `git diff --stat origin/main...HEAD` sur les chemins réservés et `data/` | vide |

**Les corrections de la relecture** (`50e7533`), vues dans le code :
- `construire` efface, après la bascule, la collection de l'ancien alias
  **et** celle que l'ancien état décrivait. Après une coupure entre la
  bascule et l'état, il ne reste plus d'orpheline, et le test vérifie la
  liste des collections.
- L'index réduit se déclare :
  - `cis_reduits` est dans l'état, et `fiches` compte les seules fiches de
    l'index réduit ;
  - `index etat` le dit, et `etat --complet` sort en code 2. `make index`
    s'en sert pour reconstruire en entier ;
  - `mettre-a-jour` refuse un index réduit ;
  - `verifier` le compare à la reconstruction de ses seuls CIS.
- `verifier` prend le verrou, comme `construire` et `mettre-a-jour`.
- Les remarques sont faites : la perte du cache est dite par `verifier`
  avec la commande pour en sortir, et le double compte est retiré.

Ces corrections ne demandent pas de second tour de relecture.

**La clôture est atteinte**, sur le Mac de beko :
- le cache des vecteurs vidé, puis `make rebatir`, `make demo`,
  `make silver` (22/22) et `make gold` (aucun bloquant, 25 concordantes) ;
- le premier `make index` construit : 72 296 fragments encodés en 18 min,
  **411 Mo** pour l'encodage et **416 Mo** pour les fragments. `verifier`
  est conforme ;
- le second met à jour, ne trouve rien à faire, et `verifier` est
  conforme.

Tous les résidents restent sous 512 Mo. Les 624 Mo du palier 2 ne se sont
pas reproduits, et l'ADR 0011 garde la question ouverte.

**Le circuit est complet** :
- le §0, l'addendum 1, et les décisions du palier 2 (SentencePiece pris en
  amont, potion écarté, recherche exacte, diagnostic de la mémoire) ;
- trois paliers contrôlés, dont les contrôles sont commis tels quels ;
- la relecture 1 CONFORME.

## Correction demandée dans `pr.md`

**La dernière proposition** (« Le PRD v0.8 dit “PR #7” pour le run en
échec ») n'est plus vraie. Le §9 du PRD est corrigé sur `main` depuis
`241bff0` : il parle de la CI de `main` après la fusion de la mission 06.
La seule « PR #7 » qui reste dans le PRD désigne, à bon droit, la PR de la
mission 06. **Retire cette proposition.**

## Remarques, sans correction

- **La CI de la PR doit passer du premier coup**, c'est une condition de la
  clôture de l'ordre. Si elle tombe, on lit l'artefact `diagnostic-courtier`
  et les lignes horodatées des réessais **avant** toute relance.
- **La durée de l'étape `make index` dans la CI** est à reporter, avec les
  deux étapes du modèle (à froid, puis en cache), dans la première entrée du
  journal de la mission suivante.
- **Le PRD** : l'IeC reporte, avec l'ordre de la mission 08 :
  - le point 5 du §10.2, tranché (Qdrant, ADR 0011) ;
  - le §6.7 : l'instant de l'index rendu avec chaque résultat, la recherche
    exacte, les deux processus ;
  - le §9 : la mémoire de l'index (411 à 470 Mo) ;
  - pour la mission 08 : le score dense serré, et les questions dont la
    réponse est dans `identite`.
- **La remarque de la relecture sur le healthcheck** : il ne fait qu'une
  lecture, alors que l'ordre parlait d'un registre « qui accepte une
  écriture ». Elle est gardée en tête. Si la coupure revient en CI, c'est la
  première chose à revoir.
