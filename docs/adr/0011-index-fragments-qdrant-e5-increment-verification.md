# ADR-0011 — L'index de l'assistant : fragments du gold, Qdrant, e5-small-int8, incrément vérifié

**Statut :** accepté (mission 07) · **Date :** 2026-10-29 · **Mission :** 07 ·
s'appuie sur les ADR 0003, 0004, 0007, 0009 et 0010
**Remplace / remplacé par :** —

## Contexte

Le gold (ADR 0010) donne, à un instant, la fiche médicament de chaque CIS.
Le Lot 3 a besoin d'un **index** où l'assistant de la mission 08 cherchera
des passages à citer. Le PRD v0.8 (§6.7) en fixe les règles :
- un texte déterministe, sans LLM, qui garde la prudence du gold ;
- l'état courant seulement ;
- une mise à jour incrémentale, jamais en avance sur le silver ;
- un index égal à sa reconstruction complète ;
- des embeddings calculés localement, par un modèle épinglé.

Le point 5 du §10.2 (Qdrant ou pgvector) restait ouvert. Le seuil de 512 Mo
par commande (ADR 0009) vaut aussi ici.

Mesures sur le jeu de démo, état au 27/10/2026 00:17:12 :
- 21 445 fiches, dont 5 562 partielles ;
- 679 CIS signalés, 662 lignes sans CIP13, un seul début à venir ;
- la fiche de tout le jeu en 3,8 s et 419 Mo.

## Décision

### Les fragments (`index/fragments.py`)

**Une fonction de la fiche du gold, et de rien d'autre** : ni horloge, ni LLM,
ni ordre de dictionnaire. Les mêmes fiches donnent les mêmes fragments, à
l'octet, et les mêmes identifiants.

**Cinq fragments par fiche au plus** :
- `identite` : spécialité, composition, groupes génériques, conditions de
  prescription, ou la phrase d'une fiche partielle ;
- `presentations` ;
- `avis` : SMR et ASMR de la BDPM ;
- `disponibilite` : MITM et signalements en cours, ou « aucun signalement » ;
- `informations` : informations importantes en cours.

`identite` et `disponibilite` existent pour toute fiche ; les autres,
seulement si leur section n'est pas vide. Chaque fragment s'ouvre sur la
ligne d'identité (`CIS … — dénomination`), pour qu'il se comprenne seul.

**Découpe par élément**, jamais au milieu d'une ligne, sous **1 200
caractères**. Chaque partie dit « (partie k sur n) » et répète le sous-titre
avec « (suite) ».
- La borne est recalée sur le tokenizer du modèle. À 1 500, 34 fragments
  dépassaient 512 jetons (581 au plus). À 1 200 : 477 jetons au plus.
- Sur le jeu : **72 296 fragments**, 8,44 millions de jetons, 365 sections
  découpées.

**Ce que le texte ne contient pas** :
- l'instant de l'état, tenu une fois par l'index et rendu avec chaque
  résultat, sans quoi chaque observation réécrirait tous les textes ;
- les liens (en métadonnée) ;
- les citations (en métadonnée : fichier, date de la source, observée
  depuis) ;
- une valeur absente ou illisible : la phrase est omise, jamais devinée, et
  le fragment nomme la colonne illisible.

**La prudence du gold, en toutes lettres** :
- `aucun_signalement` devient : « Aucun signalement dans le fichier de
  disponibilité de l'ANSM. Cela ne veut pas dire « disponible » : le fichier
  ne liste que les ruptures, tensions, arrêts et remises à disposition
  déclarés. » Un test vérifie, sur tout le jeu, que le mot « disponible »
  ne vient jamais de notre texte. Ses 95 autres occurrences sont des valeurs
  de la source, citées mot pour mot.
- Une ligne sans CIP13 « vise la spécialité entière ».
- Un début à venir est « annoncé à partir du …, pas encore commencé au jour
  de l'état ».
- Une fiche partielle dit que le référentiel ne connaît pas ce CIS.

**Le titre d'une information importante** est extrait de sa balise HTML,
entités décodées, mot pour mot : la forme change, pas le sens, comme à la
normalisation. La licence BDPM le permet, et la valeur brute reste dans le
silver.

**Identifiant** : `uuid5("f1/<cis>/<section>/<partie>")`, indépendant du
texte. Un fragment qui change garde son identifiant ; un fragment qui
disparaît est retiré. L'empreinte sha256 du texte est une métadonnée.

**Version du format** : `1`. Elle change dès que, pour les mêmes fiches, un
texte, un identifiant ou une métadonnée changerait. Elle est dans
l'identifiant et dans le nom de la collection.

**Hors des fragments** :
- les alternatives (elles changent avec la disponibilité de tout le groupe) ;
  la mission 08 les lit dans le gold au moment de répondre ;
- le libellé long des avis.

### La base vectorielle : Qdrant (`index/qdrant.py`)

`qdrant/qdrant:v1.19.2@sha256:b7b0444c…` (empreinte de l'index
multi-architecture) dans le compose du projet :
- REST sur `127.0.0.1:16333`, gRPC non exposé ;
- volume `pharmaflux-qdrant`, télémétrie coupée, `mem_limit: 512m` ;
- 99 Mio au repos avec l'index du jeu.

**Un client `httpx` à nous**, une dizaine d'appels, testé contre un Qdrant
simulé et contre le vrai. `qdrant-client` aurait apporté gRPC et protobuf
pour eux.

- **Vecteur nommé** `dense` (cosinus) : un vecteur creux s'ajoutera à côté
  à la mission 08.
- **Une collection par (format, modèle, construction)**, désignée par
  l'alias `pharmaflux-fragments`. Une construction remplit une collection
  neuve, puis bascule l'alias d'un seul appel : on ne lit jamais un index à
  moitié construit.
- **L'état de l'index** est un point sans vecteur dans
  `pharmaflux-index-etat` : instant, mise à jour en suspens (`vise`), format,
  modèle et révision, collection, nombres. Un `down -v` efface l'index et son
  état ensemble.
- **L'alias et l'état doivent se décrire l'un l'autre.** Une coupure entre
  la bascule de l'alias et l'écriture de l'état les mettrait en désaccord.
  `etat`, `chercher`, `mettre-a-jour` et `verifier` refusent alors (code 2)
  et disent de reconstruire.
- **Recherche exacte**, mesurée sur les 40 questions v0 :

  | réglage | 10 premiers retrouvés | ms par requête |
  |---|---|---|
  | HNSW, réglages par défaut | 82 % | 3 |
  | `hnsw_ef` 128 | 87 % | 3 |
  | `hnsw_ef` 256 | 92 % | 4 |
  | `hnsw_ef` 512 | 95 % | 6 |
  | exacte | 100 % | 7 |

  L'exacte est déterministe, et la vérification compare de l'exact à de
  l'exact. **Revenir à l'approché** quand le volume rendra l'exact trop lent :
  le corpus HAS complet de la mission 08, par exemple.

### Le modèle : multilingual-e5-small, int8, ONNX (`index/encodeur.py`)

Deux candidats mesurés sur les 72 296 fragments (règle de l'addendum 1 :
d'abord sous 512 Mo, puis le meilleur rappel à 5, et au plus une heure) :

| | potion-multilingual-128M (Model2Vec) | e5-small-int8 |
|---|---|---|
| encodage du jeu | 6,2 s | 1 091 s (construction réelle) |
| résident, avec `tokenizers` | 1 099 Mo | 2 185 Mo |
| résident, retenu | — | **415 Mo** (construction complète) |
| rappel à 5, bon CIS et bonne section (22 questions) | 5/22 | **17/22** |
| rappel à 5, bon CIS seul | 8/22 | 20/22 |
| décision | écarté | **retenu** |

**Épinglage** (`index/modeles/e5-small-int8.toml`) : dépôt
`Xenova/multilingual-e5-small`, révision `761b726…` du 22/07/2025, sha256 de
chaque fichier :
- `onnx/model_quantized.onnx` ;
- `tokenizer.json` (la référence d'un test) ;
- `config.json` ;
- `sentencepiece.bpe.model`.

Les fichiers vivent sous `$PHARMAFLUX_MODELES` (défaut `~/pharmaflux-modeles`),
hors de git. `index modele relever | installer | verifier` les relèvent,
les installent après vérification, ou les vérifient sans réseau. Seul beko
télécharge ; la CI aussi, par `installer`.

**Ce qui a fait tenir la mémoire** (mesuré) :
- **le tokenizer SentencePiece** publié avec le modèle, au lieu de
  `tokenizer.json` lu par `tokenizers`, qui construisait le vocabulaire
  Unigram de 250 002 jetons en 384 Mo (540 Mo pour les 500 353 de potion).
  Les identifiants sont ceux de `tokenizer.json`, avec le décalage de
  fairseq (`<s>` 0, `<pad>` 1, `</s>` 2, `<unk>` 3, puis l'identifiant
  SentencePiece plus un) ;
- **quatre formes de lot fixes**, (16, 64), (8, 128), (4, 256) et (2, 512),
  de 1 024 jetons, avec l'arène et les motifs mémoire d'ONNX Runtime coupés.
  ONNX Runtime garde de la mémoire pour chaque forme de lot qu'il a vue : avec
  des lots de largeur libre, l'encodage passait 2 Go. La session elle-même
  coûte 330 Mo.

**Préfixes** `passage: ` et `query: `, moyenne des états sur les jetons
réels, vecteur normé de 384 dimensions.

**Un encodeur de test** déterministe (32 dimensions, tiré du sha256 du
texte), derrière la même interface : les tests unitaires, et toute la chaîne
du jeu en CI.

### Deux processus, chacun sous 512 Mo

Le calcul des fragments (le gold : PyArrow, DuckDB) tourne dans un
sous-processus, `python -m pharmaflux index fragments`. Il écrit un JSON
Lines et un `.bilan.json` (instant, CIS touchés). L'encodage et Qdrant
tournent dans le processus de la commande, qui n'importe ni PyArrow ni
DuckDB.

Chaque `construire`, `mettre-a-jour` et `verifier` affiche le résident
maximal des deux. Sur une construction complète du jeu, cache vide :
- **415 Mo** pour l'encodage et **416 Mo** pour les fragments ;
- 18 min 11 s ;
- `chercher` : 446 Mo ; `verifier` : 422 Mo ; `evaluer` : 470 Mo.

**Le cache des vecteurs** est une table sqlite, clé (modèle et révision,
sha256 du texte encodé), sous `data/index`, hors de `data/demo` :
`make rebatir` ne l'efface pas. Un texte déjà encodé par ce modèle ne l'est
plus (PRD §7.5). Le **verrou** vit au même endroit.

### La mise à jour incrémentale : depuis le silver (`index/changements.py`)

L'index suit **le silver**, pas le bus : il lit le gold, il ne peut donc pas
être en avance sur le silver, et il n'a pas de position de bus à garder.

Entre l'instant de l'index `t0` et la dernière observation du silver `t1`,
un CIS est touché :
- par une **version** ouverte ou fermée dans `]t0, t1]` dans une entité de
  la fiche (son `code_cis`) ;
- par un **lien vers un avis de la CT** changé (les CIS dont un avis porte
  ce dossier, à `t0` et à `t1`) ;
- par une **bascule du jour**, sans aucune version :
  - un signalement dont le début annoncé tombe dans `]jour(t0), jour(t1)]` ;
  - une information importante qui entre dans sa fenêtre ou en sort.

Sans les bascules, l'index divergerait de la reconstruction au premier jour
franchi.

Pour chaque lot de 256 CIS touchés :
- les fragments recalculés depuis le gold à `t1` sont écrits s'ils sont
  nouveaux ou si leur charge a changé (vecteur repris du cache ou encodé) ;
- puis les points de ces CIS qui ne sont plus dans le nouvel ensemble sont
  retirés. On écrit avant de retirer : un CIS n'est jamais vide.

**L'ordre de l'état assure la reprise** :
- d'abord `vise = t1`, l'instant restant `t0` ;
- à la fin seulement, `instant = t1`.

Une coupure à n'importe quel point laisse `t0`, et la commande suivante
refait l'intervalle. Chaque étape est idempotente. « Rien à faire » est un
succès. Un silver en arrière de l'index est refusé.

### La vérification (`index verifier`)

Elle compare l'index à **sa reconstruction complète depuis le gold à
l'instant de l'index** :
- mêmes identifiants, ni manquant ni orphelin ;
- mêmes charges (texte et métadonnées, en JSON canonique) ;
- chaque vecteur égal, à l'octet, à l'entrée du cache pour son texte ;
- un échantillon fixe de 100 fragments réencodé à un cosinus d'au moins
  0,99 (sur le jeu : 0,9954 au plus bas) ;
- aucune mise à jour en suspens.

Avec l'encodeur de test, chaque vecteur est réencodé et doit être égal.
Codes : 0 conforme, 1 écart, 2 refus.

**Le test par tranches** : le jeu publié au silver en quatre tranches, du
24/10 au 27/10. L'index est construit, puis mis à jour après chaque tranche,
et `verifier` est conforme à chaque étape. À la fin, l'index est égal, point
pour point, à celui construit en une fois.

### `index evaluer`, une donnée pour la mission 08

Sur les 22 questions v0 qui nomment un médicament :
- **bon CIS et bonne section** : 11/22 au rang 1, **17/22** dans les 5
  premiers, 18/22 dans les 10 premiers ; rang réciproque moyen 0,623 ;
- **bon CIS seul** : 16/22, 20/22, 20/22.

Le score du premier résultat a pour médiane **0,905** pour les questions du
périmètre, et **0,873** (max 0,897) pour les questions hors périmètre ou
médicales. **Le score dense seul ne fera pas une abstention.**

## Conséquences

- `make index`, après `make gold`, construit l'index s'il n'y en a pas de
  lisible, sinon le met à jour (sa sortie dit lequel), puis le vérifie.
  `make up` démarre Qdrant ; `make rebatir` efface son volume.
  `prerequis.sh index` vérifie aussi les fichiers du modèle.
- La CI fait tourner toute la chaîne du jeu avec l'encodeur de test (deux
  `make index`). Puis elle passe le vrai modèle, téléchargé et vérifié, sur
  ses tests, sur un index réduit aux CIS des questions et sur trois
  recherches.
- La mission 08 lit l'alias, l'état et l'instant, et ajoute un vecteur creux
  dans un format 2.

## Limites

- **Le vecteur d'un texte dépend un peu de ses voisins de lot** : la
  quantification dynamique d'e5 prend son échelle sur tout le lot (cosinus
  ≥ 0,997 mesuré). Il est le même pour les mêmes lots, et le cache le fige.
  D'où la tolérance de la vérification sur l'échantillon réencodé.
- **Un écart connu de jetons** : sur les 72 296 fragments du jeu, un seul
  diffère de `tokenizer.json`. C'est une égalité de score entre deux
  découpages de « 3333 », `33`+`333` ou `333`+`33`, en autant de jetons
  (ICAZ LP 5 mg, CIS 65664910). Il est sans effet sur la cohérence de
  l'index, qui encode fragments et questions avec le même tokenizer.
- **Une mesure non expliquée** : la première construction complète, avec un
  tokenizer converti depuis `tokenizer.json` (abandonné pour le fichier
  amont), avait atteint 624 Mo. Les reconstructions suivantes ont tenu en
  415 Mo, sans que l'écart soit expliqué. D'où l'affichage du résident à
  chaque construction.
- **L'état courant seulement** : « que savait-on le JJ/MM ? » reste une
  question pour le gold.
- **Le score dense est serré**, et les questions dont la réponse est dans
  `identite` (état de commercialisation, statut) sont les plus manquées.

## Options écartées

- **pgvector** : un second Postgres sur un colima qui en héberge déjà un
  (celui d'Alamel). Il aurait apporté la transaction entre l'état et les
  fragments, et le lexical français (`tsvector`).
- **LanceDB, DuckDB `vss`** dans le processus : la mémoire du processus est
  déjà prise par le gold ou le modèle ; `vss` télécharge une extension à
  l'exécution ; la mission 09 aura besoin d'un serveur.
- **Le bus comme source de l'incrément** : un événement lu avant que le
  silver l'ait appliqué ferait calculer une fiche qui ne le contient pas ; et
  il faudrait une position de bus cohérente avec celle du silver.
- **potion-multilingual-128M** : 5/22 dans les 5 premiers, 1 099 Mo.
- **`fastembed`, `sentence-transformers`** : téléchargement implicite des
  modèles, ou PyTorch.
- **Le tokenizer converti en SentencePiece par le code** : il marchait (les
  mêmes identifiants), mais c'était un fichier dérivé. Le fichier amont,
  publié dans le même dépôt et à la même révision, s'épingle comme les
  autres.

## Références

- PRD v0.8 §2.2, §6.7, §7.5, §9, §10.2 point 5.
- Mission 07 : ordre et addendum 1, contrôles des paliers 1 et 2, rapports
  des paliers (`docs/rapports/mission-07/`).
- `infra/index/README.md` : la procédure de téléchargement, modèle et image.
