# Mission 07 — palier 2 : index et recherche (décision 3)

Contrôle du palier 1 lu (`62bbbb9`), et les décisions de l'IeC prises
pendant le palier, par messages directs :
- SentencePiece, d'abord converti puis pris en amont ;
- potion écarté ;
- recherche exacte ;
- diagnostic de la mémoire.

beko a fait tous les téléchargements : les deux modèles, `sentencepiece.bpe.model`
(`relever --revision`), l'image Qdrant et les empreintes des actions. Les
conteneurs `pharmaflux-redpanda` (recréé par le nouveau healthcheck) et
`pharmaflux-qdrant` tournent sur le Mac.

**Trois refus du garde-fou**, aucun contourné :
- `docker stats` et `docker compose stats` : beko a relevé la mémoire des
  conteneurs ;
- `git rm` sur un fichier jamais commité : inutile, il a suffi de l'effacer.

## Fait

- **Épinglages** :
  - les TOML relevés par beko, recopiés ;
  - `sentencepiece.bpe.model` ajouté à e5 à la même révision `761b726…` ;
  - `index modele relever --revision` : il reprend sans téléchargement les
    fichiers déjà en place et justes ;
  - les trois actions de la CI épinglées par SHA (`checkout` v4.4.0,
    `setup-uv` v6.8.0, `upload-artifact` v4.6.2) ;
  - Qdrant `v1.19.2@sha256:b7b0444c…` dans le compose : REST sur
    `127.0.0.1:16333`, volume `pharmaflux-qdrant`, télémétrie coupée,
    `mem_limit: 512m`, healthcheck sur `/readyz` (en bash : l'image n'a ni
    curl ni wget).
- **Dépendances** : `numpy` 2.5.4, `onnxruntime` 1.31.0 et `sentencepiece`
  0.2.2 ; `tokenizers` 0.23.3 en développement seulement, référence d'un test.
  - Toutes sont publiées avant le 15/10, avec des plafonds pour les
    transitifs plus récents (`uv lock --exclude-newer 2026-10-15` donne
    les mêmes versions).
  - Aucun paquet déjà verrouillé n'a bougé.
- **Encodeur** (`index/encodeur.py`) :
  - e5 par ONNX Runtime, avec le tokenizer SentencePiece d'origine et le
    décalage de fairseq ;
  - moyenne masquée, puis normée ;
  - quatre formes de lot fixes de 1 024 jetons ;
  - arène et motifs mémoire coupés ;
  - un encodeur de test déterministe.
- **Qdrant** (`index/qdrant.py`), un client `httpx` à nous :
  - vecteur nommé `dense` ;
  - alias `pharmaflux-fragments` ;
  - état dans `pharmaflux-index-etat` (un point sans vecteur) ;
  - un **espace** qui préfixe tout, pour que les tests d'intégration ne
    touchent jamais l'index du Mac ;
  - **recherche exacte** (voir plus bas).
- **Construction** (`index/construction.py`) : deux processus.
  - Le sous-processus des fragments : `python -m pharmaflux index
    fragments`, qui écrit un `.bilan.json`.
  - L'encodage, par lots de 256 : cache sqlite (modèle, révision, sha256 du
    texte) et verrou, sous `data/index`.
  - Une collection neuve, puis la bascule de l'alias, puis l'état, puis
    l'ancienne effacée. Reconstruire au même instant écrit sous « -bis » :
    la collection lue n'est jamais effacée.
- **Commandes** : `index construire`, `chercher` (`-k`, `--cis`,
  `--section`, `--format texte|jsonl`), `etat` et `evaluer`.
- **Tests** : 17 de plus.
  - `test_index.py`, 11 : contre un Qdrant simulé en mémoire, dont la
    construction de tout le jeu en ligne de commande.
  - `test_index_integration.py`, 2 : contre le vrai Qdrant, dont le
    parcours en pages et la suppression par filtre du palier 3.
  - `test_encodeur_modele.py`, 3 : marqueur `modele`, sauté sans les
    fichiers du modèle. Il contient le test d'égalité des jetons
    (40 questions et 145 fragments).
  - `test_modeles.py`, 1.
- **Corrections du contrôle 1** : « PR #7 » devient le run de `main` sur
  `98505d3` dans `a_nettoyer` et dans `ci.yml` ; seconde voie
  `docker image inspect … RepoDigests` dans `infra/index/README.md`.

## Les deux modèles (règle C1)

Encodage des 72 296 fragments du jeu :

| | potion-multilingual-128m | e5-small-int8 |
|---|---|---|
| durée | 6,2 s | 921 s (tokenizer d'origine), puis 1 091 s (construction réelle) |
| résident, tokenizer d'origine (`tokenizers`) | 1 099 Mo | 2 185 Mo |
| rappel à 5, bon CIS et bonne section (22 questions) | **5/22** | **17/22** |
| rappel à 5, bon CIS seul | 8/22 | 20/22 |
| décision | écarté (règle 1, et qualité) | retenu |

D'où venait la mémoire :
- `tokenizers` charge le vocabulaire Unigram en 384 Mo (e5, 250 002 jetons)
  et en 540 Mo (potion, 500 353 jetons) ;
- la session ONNX Runtime coûte 330 Mo à elle seule ;
- ONNX Runtime garde de la mémoire pour chaque forme de lot qu'il a vue :
  avec des lots de largeur libre, plus de 2 Go.

Ce qui a fait tenir e5 :
- le tokenizer SentencePiece publié avec le modèle, quelques Mo ;
- quatre formes de lot fixes, (16, 64), (8, 128), (4, 256) et (2, 512) :
  500 Mo à 2 048 jetons par lot, 477 Mo à 1 024, au même débit, sur les
  1 000 fragments les plus longs.

**Le seuil n'est pas relevé.**

**Jetons** : `sentencepiece.bpe.model`, avec le décalage de fairseq, contre
`tokenizer.json`. Identiques sur les 40 questions, et sur **72 295 fragments
sur 72 296**. Le seul écart est une égalité de score : « 3333 » se découpe en
`33`+`333` ou en `333`+`33`, en autant de jetons (ICAZ LP, CIS 65664910). Il
est sans effet sur la cohérence de l'index, qui encode fragments et questions
avec le même tokenizer, et ira dans l'ADR 0011 comme écart connu.

**La borne de découpe est recalée** sur le tokenizer, avant de figer le
format 1. À 1 500 caractères, 34 fragments dépassaient 512 jetons (581 au
plus), et le pire rapport était de 2,48 caractères par jeton. À 1 200 :
- **72 296 fragments**, 477 jetons au plus, aucun tronqué ;
- par section :

  | identite | presentations | avis | disponibilite | informations |
  |---|---|---|---|---|
  | 21 584 | 14 735 | 9 237 | 21 445 | 5 295 |

- 365 sections découpées ; 8,44 millions de jetons en tout.

## La mémoire, mesurée sur une construction complète (addendum 1 J)

Le diagnostic demandé par l'IeC. Résident maximal (`getrusage`), sur le jeu
entier :

| mesure | résident maximal | durée |
|---|---|---|
| encodage seul des 72 296 fragments, par lots de 256 | **460 Mo**, atteints avant 2 048 ; résident courant de 177 à 245 Mo ensuite | 1 075 s |
| construction avec l'encodeur de test (vrai Qdrant, sans ONNX) | **60 Mo**, plat | 9 s |
| **`index construire`, cache vide, vrai Qdrant** : encodage | **415 Mo**, atteints avant 2 048, plat jusqu'à 72 296 | **1 091 s** (18 min 11 s) |
| idem, sous-processus des fragments (gold) | **416 Mo** | (compris) |
| `index chercher` (trois questions) | 443 à 446 Mo | 0,8 à 0,9 s |
| `index evaluer` (40 questions) | 470 Mo | 5,0 s |

Courbe de la construction, tous les 2 048 fragments (fragments, secondes ;
résident maximal constant à 415 Mo) :

| fragments | 2 048 | 10 240 | 20 480 | 30 720 | 40 960 | 51 200 | 61 440 | 71 680 |
|---|---|---|---|---|---|---|---|---|
| secondes | 32 | 165 | 324 | 478 | 630 | 780 | 930 | 1 082 |

**Non expliqué** : la première construction complète, avec le tokenizer
converti depuis `tokenizer.json` (sinon le même code), avait atteint
**624 Mo**. Je ne l'ai pas reproduit : la seule différence est le fichier du
tokenizer, qui pèse quelques Mo dans les deux cas. La marge mesurée est de
97 Mo. Je propose de remesurer à la clôture, à la construction lancée par
beko.

Mémoire des conteneurs, relevée par beko au repos, après la construction de
mesure (`docker stats --no-stream`) :
- `pharmaflux-qdrant` : 99,2 Mio sur 512 Mio ;
- `pharmaflux-redpanda` : 200,8 Mio sur 1 Gio.

## La recherche (addendum 1 G)

**Exacte** : sur les 40 questions, l'index HNSW de Qdrant rendait la liste
exacte des dix premiers dans ces proportions :

| réglage | 10 premiers retrouvés | listes identiques | ms par requête |
|---|---|---|---|
| défaut | 82 % | 20/40 | 3 |
| `hnsw_ef` 128 | 87 % | 23/40 | 3 |
| `hnsw_ef` 256 | 92 % | 25/40 | 4 |
| `hnsw_ef` 512 | 95 % | 27/40 | 6 |
| exacte | 100 % | 40/40 | 7 |

Revenir à l'approché quand le volume rendra l'exact trop lent (le corpus HAS
complet, par exemple) : ce sera dans l'ADR.

`index evaluer` sur l'index du jeu :
- 22 questions nomment un médicament ;
- bon CIS : 16/22 au rang 1, 20/22 dans les 5 premiers, 20/22 dans les 10 ;
- bon CIS et bonne section : 11/22, **17/22**, 18/22 ; rang réciproque moyen
  0,623 ;
- score du premier résultat : médiane **0,905** pour les questions du
  périmètre, **0,873** (max 0,897) pour les questions hors périmètre et
  médicales.

Le score dense seul ne fera pas une abstention : c'est une donnée pour la
mission 08.

Questions manquées dans les dix premiers :
- `disponibilite-005`, `avis_has-005` : la réponse est dans `identite`
  (état de commercialisation, statut) ;
- `alternatives-003`, `avis_has-003` (bonne section manquée), et
  `historique-002`.

## Démonstration (décision 6)

```
$ uv run pharmaflux index etat
instant           2026-10-27T00:17:12Z (dernière observation du silver appliquée)
mise à jour       aucune en suspens
format            1
modèle            e5-small-int8@761b726dd34fb83930e26aab4e9ac3899aa1fa78 (384 dimensions)
collection        pharmaflux-f1-e5-small-int8-20261027T001712Z-bis (alias pharmaflux-fragments)
fiches            21445
fragments         72296

$ uv run pharmaflux index chercher "LARIAM 250 mg est-il en rupture de stock ?" -k 3
1. score 0.901 — CIS 65999556, disponibilite
   sources : CIS_CIP_Dispo_Spec.txt (source du 2026-10-21, observée depuis le 2026-10-24T19:42:01Z) ; CIS_MITM.txt (source du 2026-10-13, …)
   état de l'index au 2026-10-27T00:17:12Z
   | CIS 65999556 — LARIAM 250 mg, comprimé sécable
   | Médicament d'intérêt thérapeutique majeur (ATC P01BC02, liste publiée le 2024-12-18).
   | Disponibilité, signalements en cours dans le fichier de l'ANSM (1) :
   |   - Rupture de stock depuis le 2026-06-25 ; mis à jour le 2026-10-08 ; vise la spécialité entière (toutes ses présentations), aucune présentation (CIP13) n'est nommée
2. score 0.892 — CIS 65999556, presentations   (taux 65 %, prix public 29.19 €)
3. score 0.891 — CIS 65999556, avis            (SMR important, CT-15590)

$ uv run pharmaflux index chercher "Quel est le taux de remboursement de LEVOCARNIL ?" -k 3
1. score 0.889 — CIS 60016589, presentations   (5 ampoules ; taux 65% ; prix public 7.06 €)
2. score 0.882 — CIS 67578132, presentations   (LEVOCARNIL 100 mg/ml, solution buvable)
3. score 0.880 — CIS 67578132, avis

$ uv run pharmaflux index chercher "Quelles informations de sécurité sur les analogues du GLP-1 ?" -k 3
1. score 0.853 — CIS 65503469, informations    (fiche partielle : « Analogues du GLP-1 : point sur la surveillance… »)
2. score 0.852 — CIS 60000229, informations, partie 2/2
3. score 0.851 — CIS 64420351, informations
```

## Vérifications locales (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 253 files already formatted |
| `uv run mypy src` | Success: no issues found in 66 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **585 passed** en 183 s (568 au palier 1), courtier, Qdrant et modèle présents |
| `uv run pytest -q -rE -m "integration or modele"` | 17 passed ; reproduction : 0 réessai sur 30 cycles |
| services | `docker compose -p pharmaflux up -d --wait --pull never` : Redpanda et Qdrant `Healthy` |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| YAML (`ruby -ryaml`) ; `docker compose -p pharmaflux config --quiet` | lus sans erreur |
| `demo verifier` ; `profil`, `questions verifier` sur `~/pharmaflux-data` | conforme ; 0 bloquante ; 25 conformes, 5 non calculables, 10 sans attendu |
| `evenements` sur la copie du Mac, `diff -r` contre `98505d3` | identique |
| `silver verifier` ; `gold qualite` ; `questions verifier --entrepot` (jeu) | 22/22 ; code 0 ; 25 concordent |
| `index modele verifier e5-small-int8` | 4 fichiers en place, sha256 vérifiés |
| shellcheck | sans objet, aucun `.sh` touché |

## Écarts à l'ordre

1. **La recherche est exacte**, pas approchée, sur décision de l'IeC (tableau
   ci-dessus).
2. **Le vecteur d'un texte dépend un peu de ses voisins de lot** : la
   quantification dynamique d'e5 prend son échelle sur tout le lot. Mesuré :
   cosinus ≥ 0,997 et écart absolu de 0,013 au plus. Il est le même d'un
   calcul à l'autre pour les mêmes lots, et le cache le fige. **Pour le
   palier 3** : `index verifier` doit comparer les vecteurs réencodés avec
   une tolérance (cosinus ≥ 0,99), ou contre le cache. L'égalité stricte vaut
   seulement avec l'encodeur de test.
3. **potion est retiré du code** (son TOML, son encodeur) : ses mesures vont
   dans l'ADR 0011. Ses fichiers restent dans `~/pharmaflux-modeles`, à beko
   de les effacer s'il le souhaite.
4. `infra/demo/prerequis.sh` ne vérifie pas encore l'image Qdrant ni les
   fichiers du modèle. Je le fais au palier 3 avec `make index` (décision
   I). D'ici là, `make up` sans l'image échoue au démarrage de Qdrant
   (`--pull never`), avec le message de Compose.

## Questions pour l'IeC

1. Les 624 Mo non reproduits : la remesure à la clôture, sur la construction
   de beko, te suffit-elle ?
2. La tolérance de `verifier` sur les vecteurs du vrai modèle (écart 2) :
   cosinus ≥ 0,99 contre un réencodage, ou égalité contre le cache ?

## Propositions d'évolution

La CI ne fait pas tourner les tests `modele`, faute des fichiers : ils sont
sautés et dits. L'étape du modèle épinglé, avec cache, arrive au palier 3
(décision 5).
