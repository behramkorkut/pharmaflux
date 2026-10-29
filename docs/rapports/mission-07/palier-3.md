# Mission 07 — palier 3 : incrément, vérification, `make index`, CI, docs (décisions 4, 5, 7)

Contrôle du palier 2 lu et commité (`738b1b0`). Les deux demandes de l'IeC
pour ce palier sont faites :
- le désaccord entre l'alias et l'état fait refuser la lecture ;
- `mettre-a-jour` affiche le résident de ses deux processus.

Qdrant et Redpanda tournaient sur le Mac. Aucun refus du garde-fou. La
séquence de clôture (`make rebatir`, `make demo`, `make silver`, `make gold`,
puis deux `make index`) est à beko (décision 6).

## Fait

- **Les CIS touchés** (`index/changements.py`, dans le sous-processus du
  gold), entre l'instant de l'index `t0` et le silver `t1` :
  - versions ouvertes ou fermées dans `]t0, t1]` ;
  - liens vers les avis de la CT (les CIS de leurs avis, à `t0` et à `t1`) ;
  - **bascules du jour** : un début annoncé qui commence, une information
    qui entre dans sa fenêtre ou en sort.

  `index fragments --depuis T0` n'écrit que leurs fragments, et leur liste
  dans le `.bilan.json`. Un silver en arrière de l'index est refusé
  (code 2).
- **`index mettre-a-jour`** :
  - l'état reçoit `vise` d'abord, l'instant à la fin seulement ;
  - les CIS sont traités par lots de 256 : écrire les fragments nouveaux ou
    changés (vecteur du cache ou encodé), puis retirer les autres ;
  - les CIS disparus perdent tous leurs points ;
  - « rien à faire » est un succès ; la reprise est dite ;
  - le bilan donne les CIS touchés (par une version, par le jour), les
    fragments ajoutés, remplacés, retirés, inchangés, encodés, et le résident
    des deux processus.
- **`index verifier`** (règles de l'IeC au contrôle 2) : l'index comparé à
  sa reconstruction depuis le gold, à son instant :
  - identifiants, ni manquant ni orphelin ;
  - charges, en JSON canonique ;
  - **chaque vecteur égal à l'octet à l'entrée du cache** ;
  - **100 fragments tirés de façon fixe réencodés, cosinus ≥ 0,99** ;
  - avec l'encodeur de test, **chaque** vecteur réencodé et égal ;
  - une mise à jour en suspens est un écart.

  Codes 0, 1, 2 ; vingt identifiants cités au plus par catégorie d'écart.
- **L'alias et l'état** (demande du contrôle 2) : `etat_exige` refuse un
  alias que l'état ne décrit pas. `etat`, `chercher`, `verifier` et
  `mettre-a-jour` sortent alors en code 2, avec le message « une
  construction a été coupée entre la bascule de l'alias et l'écriture de
  l'état ; relancer « pharmaflux index construire » ». `make index`
  reconstruit dans ce cas : `index etat` y échoue.
- **Mémoire de la vérification** : elle montait à **815 Mo**. J'ai mesuré
  ses étapes :
  - la table des charges attendues, gardée en JSON : 185 Mo ;
  - le parcours de Qdrant par pages de 1 000 : 446 Mo à lui seul,
    l'allocateur gardant les gros blocs des réponses.

  Corrections : une empreinte de 32 octets par fragment attendu, et des
  pages de 100 (82 Mo pour tout le parcours). Résultat : **422 Mo**.
- **`make index`** : `prerequis.sh index $(INDEX_MODELE)`. Ensuite :
  - si `index etat` répond, `mettre-a-jour`, avec la ligne « make index : un
    index existe, mise à jour par incréments (index mettre-a-jour) » ;
  - sinon `construire`, avec la ligne « … aucun index lisible, construction
    complète (index construire) » ;
  - puis `verifier`, qui a le dernier mot.

  `INDEX_MODELE=test` pour l'encodeur de test. `make help` et `make rebatir`
  le disent ; le cache, sous `data/index`, survit à `rebatir`.
- **`prerequis.sh index MODELE`** : il vérifie aussi les fichiers du modèle,
  sans réseau (`index modele verifier`) ; rien pour `test`. L'image Qdrant
  était déjà couverte par la liste du compose.
- **`index construire --cis`** : un index réduit, pour la CI.
- **CI, job `integration`** (`timeout-minutes` 20), après `make gold` :
  - deux `make index INDEX_MODELE=test` : une construction, puis rien à
    faire, chacun vérifié ;
  - `index modele installer e5-small-int8` (sha256 vérifiés) ;
  - `pytest -m modele`, avec `PHARMAFLUX_MODELE_EXIGE=1` ;
  - un index réduit aux 16 CIS des questions v0, puis trois `chercher`.

  Les étapes de démarrage et d'arrêt nomment Redpanda **et** Qdrant.
- **Docs** :
  - **ADR 0011** : fragments, Qdrant (recherche exacte et quand en
    revenir), modèle (les mesures des deux candidats, les 2 185 Mo d'avant
    et leurs causes), deux processus, cache, incrément, vérification, écarts
    connus (jetons, voisins de lot, 624 Mo), options écartées ;
  - **README** : « État » (mission 06 fusionnée, Lot 2 fait, mission 07),
    une section « L'index » avec une recherche réelle, les commandes ;
  - `CONTEXTE.md` ; le journal.
- **Tests** : 14 de plus.
  - `test_index_maj.py`, 13 :
    - la mise à jour égale la reconstruction (section vidée, parties en
      moins, CIS disparu, nouveau, inchangé) ;
    - « rien à faire » ;
    - un silver en arrière ;
    - **une coupure à chacune des quatre étapes, puis la reprise** ;
    - la coupure entre l'alias et l'état (API et ligne de commande) ;
    - chaque écart de `verifier` ;
    - une mise à jour en suspens ;
    - les bascules du jour ;
    - les refus de Qdrant.
  - **`test_index_tranches.py`** : le jeu publié en quatre tranches.
  - Le Qdrant simulé sait couper le *n*-ième appel d'une forme donnée, et
    trie son parcours une fois.

## Le jeu en tranches (décision 4)

Silver construit archive par archive, index mis à jour après chaque tranche
(encodeur de test), `verifier` conforme à chaque étape :

```
tranche 1 (…20261024T194206Z) : index construit, 72 303 fragments
tranche 2 (…20261024T231712Z) : 2 CIS touchés (2 par une version, 0 par le jour) ; 0 ajouté, 0 remplacé, 2 retirés, 5 inchangés ; 72 301 fragments
tranche 3 (…20261026T151731Z) : 1 CIS touché ; 0 ajouté, 1 remplacé, 0 retiré, 2 inchangés ; 72 301 fragments
tranche 4 (…20261027T131731Z) : 7 CIS touchés ; 0 ajouté, 2 remplacés, 5 retirés, 20 inchangés ; 72 296 fragments
```

À la fin, l'index mis à jour pas à pas est égal, point pour point (charges et
vecteurs), à celui construit en une fois : 72 296 points. Le jeu n'a aucune
bascule du jour entre le 24 et le 27/10 ; les bascules sont couvertes par des
tests à part.

## Sur l'index réel du Mac (e5-small-int8)

| commande | résultat | résident maximal (encodage / fragments) | durée |
|---|---|---|---|
| `index mettre-a-jour` | rien à faire, 72 296 fragments | 422 / 423 Mo | 2,5 s |
| `index verifier` | conforme ; 0 manquant, 0 orphelin, 0 différent ; 100 réencodés, cosinus minimal 0,9954 | 422 / 419 Mo | 28 s |
| `index verifier`, avant la correction des pages | conforme | **815** / 424 Mo | 20 s |

## `make -n` des cibles nouvelles ou modifiées

```
$ make -n index
sh infra/demo/prerequis.sh index e5-small-int8
if uv run pharmaflux index etat > /dev/null 2>&1; then \
		echo "make index : un index existe, mise à jour par incréments (index mettre-a-jour)"; \
		uv run pharmaflux index mettre-a-jour --entrepot data/demo/lakehouse --modele e5-small-int8; \
	else \
		echo "make index : aucun index lisible, construction complète (index construire)"; \
		uv run pharmaflux index construire --entrepot data/demo/lakehouse --modele e5-small-int8; \
	fi
uv run pharmaflux index verifier --entrepot data/demo/lakehouse --modele e5-small-int8
```

`make -n index INDEX_MODELE=test` donne les mêmes lignes avec `--modele test`
(prérequis `index test`). `make -n help` : 21 lignes `echo`, dont les trois
de `make index` et les deux de `make rebatir`, mises à jour. `rebatir`
lui-même ne change pas : `down -v` efface déjà tous les volumes du projet,
donc `pharmaflux-qdrant`.

## Vérifications locales (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 259 files already formatted |
| `uv run mypy src` | Success: no issues found in 67 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **599 passed** en 264 s (585 au palier 2), courtier, Qdrant et modèle présents |
| `uv run pytest -q -rE -m "integration or modele"` | 17 passed |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/demo/prerequis.sh` | rien à signaler |
| YAML de `ci.yml` et du compose (`ruby -ryaml`) | lus sans erreur |
| `sh infra/demo/prerequis.sh index e5-small-int8` | prérequis : OK |
| `demo verifier` ; `profil`, `questions verifier` sur `~/pharmaflux-data` | conforme ; 0 bloquante ; 25 conformes, 5 non calculables, 10 sans attendu |
| `evenements` sur la copie du Mac, `diff -r` contre `98505d3` | identique |
| `silver verifier` ; `gold qualite` ; `questions verifier --entrepot` (jeu) | 22/22 ; code 0 ; 25 concordent |

## Écarts à l'ordre

1. **Le modèle de la CI n'est pas en cache.** Le cache demande
   `actions/cache`, à épingler par SHA comme les trois autres actions, et je
   ne peux pas relever son empreinte. Je l'ai demandée à l'IeC. En attendant,
   l'étape télécharge environ 140 Mo à chaque run, chaque fichier vérifié par
   son sha256 avant d'être mis en place. J'ajoute le cache dès que beko
   donne l'empreinte.
2. **Le test par tranches tourne dans le job `verifier`**, contre le Qdrant
   simulé, en 100 s. Il n'a besoin ni de Docker ni du modèle ; le job
   `integration` fait la même chaîne contre le vrai Qdrant avec `make index`.
3. **`make index` choisit entre construction et mise à jour par `index
   etat`.** Un Qdrant injoignable fait donc tenter une construction, qui
   échoue à son tour en code 2, avec le message de Qdrant.

## Questions pour l'IeC

1. L'empreinte d'`actions/cache` (écart 1) : dans cette mission, ou à la
   suivante ?

## Propositions d'évolution

- **Le job `verifier`** passera d'environ 4 à 6 min, à cause des tests
  du jeu en tranches. Le K2 du §0 (le saut du courtier absent, plus rapide)
  en regagnerait une partie.
- **Le PRD v0.8** dit « PR #7 » pour le run en échec : c'était le run de
  `main` (déjà noté par l'IeC).

## Pour la clôture (beko)

```bash
make rebatir && make demo && make silver && make gold && make index && make index
```

- Le premier `make index` construit, et donne la durée de l'encodage et le
  résident des deux processus. C'est le second point de mesure demandé par
  l'IeC : il ne doit pas dépasser 512 Mo.
- Le second ne trouve rien à faire, puis `verifier` est conforme.
- `make rebatir` recrée Qdrant vide ; le cache des vecteurs, sous
  `data/index`, reste. Si le cache est plein, la première construction ne
  réencode rien : pour mesurer l'encodage, vider `data/index/cache-vecteurs.sqlite`
  avant.
