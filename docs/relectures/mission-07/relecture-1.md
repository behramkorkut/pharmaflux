# Mission 07 — relecture 1
**Commit relu** : `041b4d1` (sommet de `mission-07-fragments-et-index`)
**Verdict** : CONFORME

Relu contre l'ordre de la mission 07 et son addendum 1 (sur `main`), les
rapports `points-a-trancher.md` et `palier-1.md` à `palier-3.md`, et les
trois contrôles de l'IeC. Premier tour : aucune relecture précédente.

## Bloquants

Aucun.

## À corriger (non bloquants)

1. `src/pharmaflux/index/construction.py:246` — **une collection orpheline
   après une coupure entre l'alias et l'état.** Dans ce cas, l'alias désigne
   la nouvelle collection C et l'état décrit l'ancienne O. La reconstruction
   que demande le message d'`etat_exige` prend `ancienne = C`. Elle écrit
   `C-bis`, puis efface C. **O n'est jamais effacée** : elle reste dans
   Qdrant jusqu'au prochain `down -v`. Avec 72 296 points de 384 dimensions,
   charges comprises, sous `mem_limit: 512m`, ce n'est pas anodin.
   `test_une_coupure_entre_l_alias_et_l_etat_fait_refuser_la_lecture`
   (`tests/test_index_maj.py:205`) ne regarde pas les collections qui
   restent. Aujourd'hui, Qdrant sur le Mac n'en a que deux (l'index et
   l'état) : rien n'est à nettoyer. **Attendu** : `construire` efface aussi
   la collection que l'état décrit, si ce n'est ni la nouvelle ni celle de
   l'alias. Le test vérifie la liste des collections après la reprise.

2. `src/pharmaflux/index/construction.py:242` — **un index réduit
   (`construire --cis`) ne se reconnaît pas.**
   - Son état donne `fiches = fiches_total`, soit 21 445 sur le jeu, pour
     quelques dizaines de fragments, et `index etat` l'affiche tel quel.
   - Si `make index` passe ensuite, il voit un index lisible et lance
     `mettre-a-jour`. Celle-ci ajoute les CIS touchés, même hors de la
     réduction.
   - `verifier` signale alors des milliers de manquants : rien n'est donc
     silencieux, mais le diagnostic est trompeur.

   En CI, l'index réduit est construit en dernier, donc le cas n'arrive
   pas. Sur le Mac, il suffit d'un `index construire --cis …` pour essayer.
   **Attendu** : l'état garde la liste `cis` (ou un drapeau « réduit »).
   `etat` le dit. `mettre-a-jour` refuse un index réduit (code 2), et
   `make index` reconstruit alors en entier.

3. `src/pharmaflux/cli.py:1868` et `construction.py:148` — **`index
   verifier` ne prend pas le verrou, mais écrit dans le dossier de travail.**
   Son sous-processus écrit `data/index/fragments.jsonl.partiel`, puis le
   renomme en `fragments.jsonl`, et écrit aussi `.bilan.json`. Ce sont les
   mêmes fichiers que ceux de `construire` et de `mettre-a-jour`, qui
   tiennent le verrou. Un `verifier` lancé dans un autre terminal pendant
   les 18 minutes d'une construction peut tomber pendant leur calcul de
   fragments. Deux écrivains ouvrent alors le même `.partiel` en mode `w`,
   et chaque processus peut lire le bilan de l'autre. La fenêtre est
   courte (environ 5 s), mais réelle. **Attendu** : `verifier` prend le
   verrou (il écrit dans `travail`), ou chaque appel écrit sous un nom à
   lui.

## Remarques

- **La perte du cache des vecteurs.** Si `data/index/cache-vecteurs.sqlite`
  disparaît, `verifier` déclare NON CONFORME (« vecteurs absents du cache »,
  `construction.py:564`) un index pourtant juste. Le seul moyen d'en sortir
  est `index construire`, qui réencode tout (18 min). C'est cohérent avec la
  règle du contrôle 2, mais ni l'ADR 0011 ni `infra/index/README.md` ne le
  disent, et le message de `verifier` ne donne pas la commande. Une ligne
  suffirait.
- `construction.py:566-568` : avec l'encodeur de test, un même identifiant
  peut entrer deux fois dans `vecteurs_differents` (une fois pour le cache,
  une fois pour le réencodage), et le compte affiché est alors doublé.
  Sans effet sur le verdict.
- `src/pharmaflux/index/qdrant.py:119` : `Qdrant.supprimer` (suppression par
  filtre) ne sert qu'aux tests (`tests/test_index_integration.py:100`). Il
  vaut mieux le dire dans sa docstring, ou le déplacer.
- `fragments.py:45-47` : la mise en forme de `FORMAT = (\n    1  # …\n)`
  vient de `ruff format` sur un commentaire trop long. Un commentaire
  au-dessus de la ligne se lirait mieux.
- Le healthcheck du registre (`docker-compose.yml`) se contente d'une
  lecture (`rpk registry subject list`). L'ordre (§0 A) parlait d'un
  registre « qui accepte une écriture ». L'addendum a retenu la proposition
  telle quelle, et le réessai strict en test couvre le reste : à garder en
  tête si la coupure revient en CI.
- Dans la section « L'index », le README donne 415 Mo pour l'encodage (une
  mesure du palier 2). La clôture du journal donne 411 Mo : les deux
  chiffres sont justes, mais un lecteur verra l'écart. On peut citer la
  clôture.
- Lu avec soin et juste :
  - le réessai du registre : sans réponse seulement, jamais sur un
    `ReadTimeout`, horodaté, strict en test, et le test de reproduction
    retire ses propres réessais du décompte ;
  - les bornes des bascules du jour (`changements.py`) ;
  - l'ordre « écrire puis retirer » de la mise à jour, avec `vise` d'abord
    et l'instant à la fin ;
  - le parcours de la vérification par pages de 100 ;
  - le vecteur nommé `dense` ;
  - la recherche exacte, mesurée et justifiée ;
  - les dépendances plafonnées selon l'ADR 0009 ;
  - les actions de la CI épinglées par empreinte.
- Les tests de prudence portent sur le comportement, sur des cas réels du
  jeu (LEVOCARNIL sans CIP13, NEVIRAPINE TEVA annoncé, ZEJULA illisible, une
  fiche partielle), et sur le mot « disponible » dans tout le jeu. Leurs
  nombres en dur (95, 662, 21 445 − 679) en font aussi des tests de
  non-régression du jeu figé : c'est voulu, mais un changement du jeu les
  fera tomber.

## Vérifications relancées

Dans `pharmaflux-relecteur/`, détaché sur `041b4d1`, arbre propre, avec
Redpanda et Qdrant (sains) et les fichiers du modèle présents.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 261 files already formatted |
| `uv run mypy src` | Success: no issues found in 67 source files |
| `uv run pytest -q -rE` | **599 passed** en 4 min 27 s ; reproduction : 0 réessai sur 30 cycles |
| `GITHUB_ACTIONS=true uv run pytest -q -rE` | **599 passed** en 4 min 22 s ; 0 réessai |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | 21 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/demo/prerequis.sh` | rien à signaler |
| YAML de `ci.yml` (`ruby -ryaml`) | lu sans erreur |
| `uv run pharmaflux demo verifier` | conforme |
| `uv run pharmaflux questions verifier` (`~/pharmaflux-data`) | 25 conformes, 5 non calculables, 10 sans attendu |
| `uv run pharmaflux index etat` (index du Mac) | 2026-10-27T00:17:12Z, aucune mise à jour en suspens, format 1, e5-small-int8, 72 296 fragments |
| `uv run pharmaflux index chercher "Quel est le taux de remboursement de LEVOCARNIL ?" -k 3` | 1er : CIS 60016589, présentations, source et date citées |
| collections de Qdrant (`GET /collections`, lecture) | l'index et l'état, aucune orpheline |

Non relancés :
- `index verifier` : sans le cache du dossier du codeur, il conclurait à
  tort à des vecteurs absents ;
- `make index` : réservé à beko ;
- `profil`, `evenements` contre `98505d3`, `silver verifier` : déjà
  rapportés par le codeur et par l'IeC.

Périmètre et historique :
- `git diff --stat main...HEAD` : aucun chemin réservé à l'IeC, rien de
  `data/`, aucun secret ;
- tests hors réseau, sauf ceux marqués `integration` ou `modele` ;
- dix commits, tous avec `Commis-par: codeur` et
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, messages en
  français ;
- un commit par palier, plus les contrôles et deux compléments annoncés
  (`22a2d6e`, `97c09fd`).

## Alertes

Aucune.
