# Mission 04 — contrôle final de l'IeC

**Sommet contrôlé** : `513a226` (code testé : `cd7810e` ; depuis, seuls
`pr.md` et le journal ont changé). **Verdict** : **fusion autorisée après
un commit de `pr.md`** (trois corrections, ci-dessous). Le code n'est pas
à reprendre.

## Le circuit

- Le §0 a été tranché par l'addendum 1 sur `main` (`aceb5ba`).
- Trois paliers ont été acceptés, le troisième après un correctif
  (`7c9e6a8`). Les trois contrôles sont commis tels quels.
- La relecture 1 est **CONFORME**, sans bloquant. Son point non bloquant
  côté code et trois remarques sont corrigés en `cd7810e`. La réponse
  explique pourquoi la quatrième remarque (le geste `--profile console
  pull`) est gardée : un seul téléchargement, celui du README. Accepté.
- La branche compte 9 commits depuis `f1750dc`, avec les trailers partout.
  `main` a avancé de trois commits (`aceb5ba`, `714b673`, `9ad4b14`), qui ne
  touchent que des chemins réservés à l'IeC. La branche n'en touche aucun,
  donc la PR fusionne sans conflit, et il n'y a pas de fusion de `main` à
  faire avant.
- `git diff f1750dc 513a226` ne touche aucun chemin réservé, et rien sous
  `data/`. Il ne contient aucune IP hors `127.0.0.1` (l'URL de la console
  locale) et aucun chemin personnel.

## Vérifications rejouées sur `513a226`

Sur une extraction du commit (`git archive`), avec le courtier du projet
démarré :

| commande | résultat |
|---|---|
| `uv run ruff check .`, `ruff format --check .` | verts |
| `uv run mypy src` | vert, 40 fichiers |
| `uv run pytest -q` | 470 passed (35,8 s), intégration comprise |
| `shellcheck infra/demo/prerequis.sh` | rien à signaler |
| `sh infra/demo/prerequis.sh` ; avec `PHARMAFLUX_IMAGES=exemple/absente:1` | code 0 ; « prérequis : NON » avec le geste |
| `uv run pharmaflux demo verifier` | conforme |

## Les correctifs de la relecture

1. **`config --images` en échec** : le `if … elif ! images=$(…)` fait
   suivre à ce chemin la règle commune (refus, geste, « prérequis : NON »,
   code 1). Le cas n'a pas été exercé, parce que le garde-fou a refusé
   `chmod +x` sur une cale de test. Ce refus est juste : il est signalé et
   n'a pas été contourné. L'IeC ne fait pas non plus le test à la place du
   codeur. Le chemin tient en quelques lignes, il est relu, et c'est accepté.
2. **`Entree` à arguments nommés**, **message d'assertion tiré de
   `n_pres`**, **attente de 1,5 s** (un cycle de `DELAI_SUIVI_S` plus une
   marge) : conformes.

## À corriger dans `pr.md` (un commit `docs(m04)`)

1. **La démonstration de beko n'a pas commencé par un refus.** `pr.md`
   écrit que `make demo` « sur le bus qui portait la démo du palier 2 a
   refusé (code 2…) », puis que beko a lancé `make rebatir` et
   `make demo`. Or la sortie transmise par l'IeC commence après
   `make rebatir`, avec un registre neuf. Le refus a été montré au
   palier 3, par le codeur, avec les commandes de `make -n demo` lancées
   une à une. Écrire les faits ainsi : refus montré au palier 3 ; sur
   `7c9e6a8`, beko a lancé `make rebatir` puis `make demo`.
2. **La dernière ligne du tableau des vérifications** dit « `make up` puis
   `make demo` (beko) ». Il faut écrire « `make rebatir` puis
   `make demo` ».
3. **Les propositions de la fin sont déjà faites.** `git count-objects` est
   permis en lecture à tous les rôles (`714b673`), et `make --version`,
   seul, est permis (`9ad4b14`). Les deux sont sur `main`. Remplacer
   « à trancher par l'IeC » par ces deux commits. L'écart 8 peut le dire
   aussi.

Facultatif : « 9 commits depuis `main` (`f1750dc`) » serait plus juste en
« depuis `f1750dc` », puisque `main` a avancé.

L'IeC relit ce seul commit, puis `pr.md` peut être publié tel quel.

## Remarques

1. **La première exécution de l'étape `make demo` en CI** a lieu au push.
   `pr.md` en donne les limites : amd64, GNU Make 4.3 pour un fichier écrit
   pour la 3.81, le Compose du runner, et environ 1 min 30 s estimée. Si
   l'étape échoue pour l'une de ces raisons, le correctif passe par la
   branche avant la fusion. Le temps mesuré est à reporter dans la PR.
2. **Les mesures Q5** (145 Mo résidents pour `demo rejouer`, `tracemalloc`
   de 0,7 à 35,8 Mo par entité, 4 min 03 s pour 67 h 35 min) entreront au
   §9 du PRD v0.6, que l'IeC écrira après la fusion, avec l'ordre suivant,
   comme pour la v0.5.
3. **Le dossier `.git/worktrees/pharmaflux-codeur/`** contient un fichier
   `refs` de 64 octets, signalé comme garbage par `git count-objects`. Il
   est à nettoyer par beko après la fusion, au démontage des worktrees.

## Pour beko

Après le commit de `pr.md` et sa relecture par l'IeC : `sh
infra/agents/publier-mission.sh 04-rejeu-accelere-et-demo`. Fusionne
seulement quand les deux jobs sont verts, `integration` compris, puisque
c'est lui qui lance `make demo`.
