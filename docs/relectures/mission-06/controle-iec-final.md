# Mission 06 — revue finale de l'IeC

**Commit revu** : `7ab8ec4` (`pr.md`), sur le code de `6cadc6f`. Il est revu
contre l'ordre et l'addendum 1 (`36d815e`), les trois contrôles de palier et
la relecture 1 (CONFORME). **Verdict : fusion autorisée, après un commit de
`pr.md` qui apporte la correction ci-dessous.** Le code n'est pas à
reprendre.

## Revérifié par l'IeC

Dans le dossier du codeur, arbre propre sur `7ab8ec4` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 58 fichiers |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true`, courtier présent | 1er passage : 537 passed, **1 error** ; 2e et 3e passages : **538 passed** |
| `uv run pytest -q -m integration`, deux fois | 11 passed, deux fois |
| `git log origin/main..main` (dans `pharmaflux/`) | vide : `main` est poussé (`36d815e`) |
| `git merge-base` de la branche et de `origin/main` | `aedf134`, comme le dit `pr.md` |

**L'erreur du premier passage n'est pas reproduite.** Je n'ai gardé que la
dernière ligne de la sortie, donc je ne sais pas quel test l'a levée. Deux
passages complets et deux passages des tests d'intégration sont ensuite
verts. La cause la plus probable est un état passager du courtier partagé,
ou un autre processus qui travaillait sur ce dossier en même temps. Ce
n'est pas bloquant, mais c'est à surveiller : si la CI de la PR tombe sur
une erreur de ce genre, on relit le journal du test avant de relancer quoi
que ce soit.

**Les correctifs faits après la relecture** (`6cadc6f`) sont vus dans le
code :
- deux fermetures au même instant se départagent avec un champ vide qui
  perd, comme le `DESC NULLS LAST` de la référence ;
- `_exiger_connus` fait refuser un code inconnu par `gold disponibilite` et
  `gold alternatives`, au lieu de rendre une réponse vide qui se lirait
  comme un fait ;
- un prix absent s'écrit « — » sans unité.

Chacun a son test. Ils ne demandent pas de second tour de relecture.

**Le circuit est complet** :
- le §0 et l'addendum 1 ;
- trois paliers contrôlés, dont les contrôles sont commis tels quels ;
- deux corrections de documentation avant la relecture (la section
  « État » du README) ;
- la relecture 1 CONFORME.

La clôture de l'ordre est atteinte : beko, sur le Mac, a enchaîné
`make rebatir`, `make demo`, `make silver` puis `make gold`, avec pour
résultat aucun bloquant et 25 questions concordantes.

## Correction demandée dans `pr.md`

**La durée de l'étape `make gold`** (section du même nom). La phrase
« Estimée à 5-10 s au §0, après « make silver », mesurée à 37 s sur la PR
#6 » se lit comme si `make gold` avait été mesuré à 37 s. Or 37 s est la
durée de `make silver`. Écris-la ainsi : « À compléter après la
publication. Estimée à 5-10 s au §0. Pour comparaison, l'étape
`make silver` dure 37 s (PR #6). »

## Remarques, sans correction

- **La remarque 1 de la relecture** (la fin de publication dans la fiche)
  est tranchée : elle se règle au Lot 3. `pr.md` la porte en proposition.
- **Le PRD** : avec l'ordre suivant, l'IeC reporte :
  - le Lot 2, fait ;
  - la limite de la détection (proposition 1), au §6.3 et aux risques ;
  - la date du dernier fichier retenu (proposition 2) ;
  - la mémoire du gold : 470 Mo au plus, sous le seuil de 512 Mo.
- **Le README** dira « Mission 06 en cours » après la fusion. L'IeC le fera
  corriger avec la mission suivante.
- **La mémoire** : `questions verifier --entrepot` est à 470 Mo, ce qui
  laisse une quarantaine de mégaoctets de marge. La prochaine mission qui
  allonge le silver la mesure en premier.
