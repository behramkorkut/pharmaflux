# Mission 04 — relecture 1
**Commit relu** : `7c9e6a8` (sommet de `mission-04-rejeu-accelere-et-demo`)
**Verdict** : CONFORME

Relu contre l'ordre de la mission 04 et son addendum 1 (version de `main`),
les rapports `points-a-trancher.md`, `palier-1.md` à `palier-3.md` (réponse
au contrôle 3 comprise) et les trois contrôles de l'IeC. Premier tour : pas
de relecture précédente.

## Bloquants

Aucun.

## À corriger (non bloquants)

1. **Décision 7, part de beko : pas encore faite.** L'ordre (palier 3) veut
   l'ADR 0008 et les docs « avec la sortie de `make demo` lancée par
   beko », et l'addendum (correction 2) fixe la clôture sur le Mac :
   `make demo` refuse, puis `make rebatir` et `make demo` finissent par un
   `verifier-bus` conforme. Au commit relu, le refus est montré (commandes
   de `make -n demo` lancées une à une, palier 3), mais `make rebatir` puis
   `make demo` ne l'ont pas encore été. Le contrôle 3 renvoie cette sortie
   à `pr.md`. Le codeur n'y est pour rien. À tenir avant
   `controle-iec-final.md` : la sortie de beko sur `7c9e6a8` (ou le commit
   qui suivra), citée dans `pr.md`.
2. `infra/demo/prerequis.sh:54` — `images="${PHARMAFLUX_IMAGES:-$($compose
   $profil config --images)}"` sous `set -eu` : si `config --images` échoue
   (option absente d'un Compose ancien, par exemple), le script s'arrête sur
   l'affectation. Il n'affiche alors ni « prérequis manquant », ni le geste
   à faire, ni « prérequis : NON ». Le cas est peu probable, puisque
   `config --quiet` vient de réussir juste avant, mais c'est le seul chemin
   d'échec du script qui ne suit pas sa règle (« chacun avec le geste à
   faire »). Attendu : `if ! images=$(…); then refus … ; fi`, ou une
   justification dans le commentaire.

## Remarques

- `infra/demo/prerequis.sh:60` : pour une image absente, le geste proposé
  est toujours `… --profile console pull`, même pour `make up`, qui n'a
  pas besoin de la console. C'est cohérent avec le README (« une fois »),
  mais le message pourrait dépendre de `$profil`.
- `src/pharmaflux/demo/rejeu_accelere.py:312` : l'`Entree` d'un passage est
  construite avec huit arguments positionnels (`"", None, None, "", False,
  (), None`). Des arguments nommés se liraient mieux, et une erreur dans
  l'ordre se verrait.
- `tests/test_demo_integration.py:105` : le message d'assertion dit
  « au vingtième message » alors que le test attend `n_pres` messages. Ce
  nombre est figé par la fixture, mais le texte décrochera s'il change.
- `tests/test_demo_integration.py:101` : `time.sleep(2.5)` pour constater que
  `suivre` attend un topic absent. Ce test ne peut pas échouer à tort (il
  vérifie seulement que rien n'est arrivé), mais il ajoute 2,5 s à chaque
  passage.
- `docs/CONTEXTE.md` : la décision 8 dit « en fin de fichier ». La section
  « La démo » est bien ajoutée à la suite des sections de mission, mais
  « Où sont les choses » et l'outillage sont modifiés en place. C'est
  logique pour un document de référence, et le contrôle 3 l'a accepté. Je
  le signale pour que l'écart soit dit dans `pr.md`.
- Le contrôle 3 est bien corrigé : `verifier_etat_du_bus` ne compte plus que
  `topics_de_la_demo`. Le test élargi échouerait avec l'ancien filtre :
  `pharmaflux.test-0000abcd.…`, un topic `bdpm.smr` hors sélection et un
  autre projet sur le courtier, sans état, puis un rejeu complet attendu.
  Le nombre de tests reste à 470, parce que le test existant a été étendu.
  C'est cohérent avec le rapport.
- Le fond est conforme :
  - **ordre global** : les tests vérifient les instants et le même ordre
    par topic que `publier`, contre un témoin rejoué par `publier` ;
  - **cadence** : les pauses sont vérifiées au facteur 1 000 et au
    facteur 100, avec rattrapage sans pause négative, et sans dormir ;
  - **refus** : la table des refus a quatre cas ;
  - **F.1 à F.3** : chacun est testé, F.2 contre le vrai registre et F.3
    sur les deux reprises ;
  - **jeu figé** : le README est relu par `test_demo.py` ;
  - **Makefile** : compatible GNU Make 3.81, toujours `--pull never`,
    projet `pharmaflux` seul ;
  - **CI** : l'étape est placée entre les tests d'intégration et
    `down -v`.

## Vérifications relancées

Sur `7c9e6a8`, dans `pharmaflux-relecteur/`. Le courtier `pharmaflux-redpanda`
était démarré, donc les tests d'intégration ont tourné.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts (175 fichiers formatés) |
| `uv run mypy src` | vert, 40 fichiers |
| `uv run pytest -q` | **470 passed** (37,6 s), intégration comprise : comme le rapport |
| `uv run pharmaflux demo verifier` | conforme |
| `make -n` des dix cibles | codes 0 ; `demo` = prérequis, `up --pull never`, schémas, `demo rejouer`, `verifier-bus --racine demo/archive` ; `rebatir` = `down -v` du seul projet `pharmaflux`, `rm -rf data/demo`, `up` |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/demo/prerequis.sh` | rien à signaler |
| `python3 infra/agents/test_garde_fou.py` | 21 tests OK |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `uv run pharmaflux profil` (`~/pharmaflux-data`) | 11 fichiers, 0 anomalie bloquante |
| `uv run pharmaflux questions verifier` | 25 conforme, 5 non calculable, 10 sans attendu : inchangé |
| `pharmaflux evenements` au sommet et sur `4684292` (`git archive`, scratchpad), puis `diff -r` | identique |
| `git diff --stat main...HEAD` sur les chemins réservés à l'IeC et `data/` | aucun |
| trailers des 7 commits (`Commis-par: codeur`, `Co-Authored-By`) | présents partout, messages en français |
| recherche de secrets, d'IP et de chemins personnels dans le diff | rien |

Non relancés : `make up` et `make demo` (réservés à beko et à la CI), et le
job de CI (aucun push).

## Alertes

Aucune.
