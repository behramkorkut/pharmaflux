# Mission 07 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Opus 5.5) · **À :** IeC, beko · **Date :** 29/10/2026
**Branche :** `mission-07-fragments-et-index` (sommet `69b2df1`, identique à
`main`) · **Ordre lu sur `main`** (`69b2df1`), avec le PRD v0.8 (§2.2, §4
Lot 3, §5, §6.7, §7.1, §7.3, §7.5, §9, §10.2).

**Ce que j'ai lu, et comment.** Le journal du run de CI
`data/ci/run-40881334581-tentative-1.log` (1 366 lignes, lu par `grep`/`awk`
ciblés), `bus/registre.py`, `bus/client.py` (`supprimer_topics`),
`tests/conftest.py` (fixtures `bus`, `registre`), `docker-compose.yml`,
`.github/workflows/ci.yml`, le `Makefile`, `gold/vues.py` (fiche,
signalements, informations, provenance), `gold/rendu.py`, `silver/schema.py`.
Les mesures :

- **les tests d'intégration**, 15 fois de suite, contre le Redpanda du projet
  déjà en marche sur le Mac (`pharmaflux-redpanda`, sain depuis 12 h ; aucun
  `up`, aucun `down`) : `uv run pytest -q -rE -m integration`, puis
  `docker compose -p pharmaflux logs --since … --until … redpanda` autour de
  l'erreur ;
- **les fiches du jeu** : `pharmaflux gold fiche --tout --entrepot
  data/demo/lakehouse` (l'entrepôt de `make silver`, lu sans écrire) vers le
  dossier temporaire de la session, sous `/usr/bin/time -l`, puis trois
  scripts de mesure hors dépôt (`uv run python -I`) qui relisent ce JSON
  Lines et appellent `gold.rendu.fiche_en_texte`.

Aucune requête vers les sources, aucun téléchargement, rien d'écrit dans le
dépôt (hors ce fichier), dans `data/` ni dans l'archive. **Un refus du
garde-fou** : `docker image ls …` (« docker image interdit ») ; j'ai lu la
même information par `docker images`, que le message cite comme permis.
**Rien n'a été codé.**

Sauf mention contraire, les chiffres sont l'état du jeu à sa dernière
observation, `2026-10-27T00:17:12Z`.

**Lecture rapide, les constats qui pèsent sur l'ordre :**

1. **La coupure du registre se reproduit sur le Mac**, avec la même
   signature que dans la CI : 1 passage sur 15 (1 mise en place de la
   fixture `registre` sur 120 environ), toujours un `POST /subjects/…/versions`, toujours **15 à 20 ms après la
   suppression des topics du test précédent**. Ce déclencheur n'existe que
   dans les tests : la chaîne réelle (`make demo`) ne supprime aucun topic.
2. **Le journal transmis vient de `main`, pas de la PR** : le run
   `40881334581` extrait `98505d3` vers `refs/remotes/origin/main`, le commit
   de fusion. Ça ne change pas l'analyse, mais la CI de la PR #7 était passée.
3. **Le temps d'encodage est le vrai risque de la mission**, pas la mémoire :
   le jeu donne **21 445 fiches** et, au grain que je propose (D), environ
   **72 000 fragments**, 37 millions de caractères avant nettoyage. Avec un
   transformeur multilingue sur le processeur, l'estimation va de la dizaine
   de minutes à plus d'une heure. Je ne peux pas le mesurer sans les fichiers
   d'un modèle (C) ; c'est la première mesure à faire, avant de figer le
   grain.
4. **L'instant de l'état ne peut pas être dans le texte d'un fragment** : la
   fiche dit « État au … » ; si chaque fragment le répétait, chaque nouvelle
   observation du silver changerait tous les textes, et l'incrément serait
   une reconstruction complète, embeddings compris (D, E).
5. **Deux parties de la fiche dépendent du jour, pas seulement du silver** :
   un signalement « annoncé, pas encore commencé » (`debut_a_venir`) et les
   informations importantes « en cours » (`date_debut <= jour <= date_fin`).
   Un incrément qui ne suivrait que les versions du silver manquerait ces
   bascules et divergerait de la reconstruction (E).

---

## A. Les coupures du registre

### Constat (mesuré)

**Dans la CI** (job `integration`, `uv run pytest -q -m integration`) :
`........EEE`, 8 réussis, 3 erreurs **à la mise en place de la fixture
`registre`**, dans les 230 ms qui suivent :

| test (préfixe) | appel coupé | `Request Count` de la connexion |
|---|---|---|
| `528e4049` | `POST /subjects/…disponibilite.v1-value/versions` | 4 |
| `1f22dac8` | `POST /subjects/…disponibilite.v1-value/versions` | 4 |
| `84986d22` | `POST /subjects/…presentations.v1-value/versions` | 5 |

L'erreur est `httpcore.RemoteProtocolError: Server disconnected without
sending a response`, traduite en `RegistreIndisponible` par `_appeler`. Le
délai de 10 s n'est pas en cause : tout tient en quelques millisecondes.

**Le journal du courtier**, à la seconde près (`--tail=100` n'en garde que
les 4 dernières secondes, mais elles suffisent) :

- 13:23:17,603 : `Delete topics [… test-ddc15c0b …]` (la fin du 8ᵉ test),
  puis l'effacement des segments jusqu'à 17,671 ;
- 17,621-17,622 : pour `528e4049`, le `POST /compatibility/…` et le
  `POST /subjects/…` (recherche) répondent 404, comme prévu (sujet neuf) ;
- le `POST …/versions` qui suit : **aucune ligne**, ni réussite ni échec ;
- même suite à 17,760 (`1f22dac8`) et 17,848-17,855 (`84986d22`, dont
  l'enregistrement de `disponibilite` a **réussi** avant que celui de
  `presentations` soit coupé).

Le décompte `Request Count` concorde avec le client : `PUT /config`,
`POST /compatibility`, `POST /subjects` (recherche), `POST …/versions` = 4
requêtes sur une connexion neuve (un `Registre` par test). Pour le 3ᵉ, 5
requêtes : la première connexion a été fermée proprement après la recherche,
et la seconde a servi l'enregistrement réussi, puis les trois appels de
`presentations`.

**Sur le Mac** (Redpanda `v26.2.6`, arm64, image `8b1076e0d61b`, même
compose), 15 passages de la suite d'intégration, 22 à 25 s chacun :
**l'erreur est revenue une fois, au passage 3** (`..E........`) ; les 14
autres passages sont verts. Même message, sur
`POST /subjects/pharmaflux.test-91789a21.bdpm.presentations.v1-value/versions`,
`Request Count: 5`. Le journal du courtier :

```
14:02:35,578  Delete topics [… test-33067fef …]        (fin du test précédent)
14:02:35,595  compatibilité puis recherche, disponibilite : 404 (attendu)
               POST …disponibilite…/versions : rien au journal (réussi)
14:02:35,615  compatibilité puis recherche, presentations : 404 (attendu)
               POST …presentations…/versions : rien au journal (coupé)
14:02:35,842  le test suivant (30704c59) : tout passe
```

### Ce que j'en sais, et ce qui reste une hypothèse

**Établi** :

- seul l'appel qui **écrit** dans le registre (`POST …/versions`, qui
  produit dans le topic interne `_schemas`) est coupé ; les lectures du même
  instant répondent ;
- le registre coupe **sans réponse et sans rien journaliser** au niveau
  par défaut, alors qu'il journalise en `WARN` chaque 404 ;
- les quatre coupures observées (3 en CI, 1 sur le Mac) tombent **dans les
  20 à 270 ms qui suivent la suppression des topics** (et, juste avant, des
  sujets, effacés en deux temps, le second définitif) du test précédent ;
- ce n'est ni un démarrage incomplet (l'étape « Schémas » a écrit dix sujets
  juste avant, et huit tests sont passés), ni la mémoire du conteneur seule
  (sur le Mac, le Redpanda tournait depuis 12 h sans incident) ;
- ce n'est pas propre à l'amd64 de GitHub ni à son Docker : le Mac le
  reproduit, à une fréquence plus faible.

**Hypothèse, non établie** : pendant l'effacement des topics, le client
Kafka interne du registre voit un changement de métadonnées (ou une
collision sur `_schemas` après les suppressions définitives du test
précédent), et le chemin d'erreur ferme la connexion HTTP au lieu de rendre
un 5xx. Je n'ai pas le journal au niveau `debug` qui le prouverait ; je ne
l'affirme pas.

**Conséquence** : le déclencheur observé n'existe **que dans les tests**
(suppression des topics et des sujets du test précédent). `make demo`,
`schemas enregistrer` et la publication ne suppriment rien.

### Avis : deux corrections, et la limite du réessai

**1. Retirer le déclencheur des tests.** La fixture `registre` efface ses
sujets et ses topics à la fin de **chaque** test, et le test suivant écrit
dans le registre dans la foulée. Je propose qu'elle les **accumule** et que
le nettoyage se fasse **une fois, en fin de session** (une fixture de session
qui reçoit la liste). Les préfixes sont déjà uniques ; en CI le courtier est
jeté (`down -v`) ; sur le Mac le nettoyage de fin de session garde le bus
propre. Les tests y gagnent aussi une seconde ou deux.

**2. Un réessai borné dans le client, pour la chaîne réelle.**

- **Quand** : seulement quand **aucune réponse HTTP n'a été reçue** :
  `httpx.RemoteProtocolError` (coupé sans réponse), `httpx.ConnectError`,
  `httpx.ReadError`, `httpx.WriteError`. **Jamais sur une réponse**, même
  5xx : une réponse est un fait du registre, elle remonte telle quelle. Pas
  sur `ReadTimeout` non plus : 10 s sans réponse est une panne, pas une
  coupure.
- **Pour quels appels** : tous ceux du client, parce que tous sont sûrs à
  rejouer :
  - `GET …/versions/latest`, `POST /compatibility/…`, `POST /subjects/…`
    (recherche) : des lectures ;
  - `PUT /config/…` : pose une valeur, idempotent ;
  - `POST …/versions` du **même schéma** : le registre rend le même
    identifiant s'il l'avait enregistré (c'est déjà ce sur quoi
    `schemas enregistrer` compte) ; le réessai ne crée jamais de version de
    plus ;
  - `DELETE /subjects/…` puis `?permanent=true` : rejoués, ils rendent 404
    si la première tentative avait abouti. **Un défaut actuel à corriger au
    passage** : `supprimer` ne lance la suppression définitive que si la
    suppression douce a répondu ; si la douce avait abouti avant une coupure,
    le réessai reçoit 404 et le sujet reste « supprimé en douceur » pour
    toujours. La suppression définitive doit être tentée dans les deux cas.
- **Combien** : 3 essais au total, attentes de 0,2 puis 0,8 s (une seconde
  au plus) : la fenêtre observée dure moins de 300 ms. Une connexion neuve à
  chaque essai (httpx la rouvre d'office, la précédente étant fermée).
- **Ce qui est écrit** : à chaque réessai, une ligne sur la sortie d'erreur,
  horodatée en UTC à la milliseconde pour la recouper avec le journal du
  courtier : `registre : POST /subjects/…/versions coupé sans réponse
  (RemoteProtocolError), essai 2/3 dans 0,2 s (2026-10-29T13:23:17.622Z)`.
  Le client compte ses réessais ; `schemas enregistrer` affiche le total à la
  fin s'il n'est pas nul.
- **La limite** : un registre arrêté échoue au 3ᵉ essai, en une seconde, avec
  le message d'aujourd'hui et le nombre d'essais. Un registre qui répond mal
  n'est jamais réessayé. Et **la CI échoue si un réessai a servi pendant les
  tests d'intégration** une fois le déclencheur retiré (la fixture de session
  vérifie que le compteur est nul) : le réessai protège la chaîne réelle, il
  ne doit pas rendre les tests aveugles à une nouvelle cause. À discuter :
  c'est strict ; l'alternative est un simple avertissement dans le résumé.

**Les tests** : unitaires, par `httpx.MockTransport` (déjà le moyen du
client) : une coupure puis une réponse donne la réponse et un réessai
compté ; trois coupures donnent `RegistreIndisponible` avec « 3 essais » ;
un 500 n'est pas réessayé ; un `ReadTimeout` non plus ; `supprimer` tente la
suppression définitive après un 404 de la douce. Plus un test d'intégration
de **reproduction** : 30 cycles « créer des topics, enregistrer, supprimer
les topics, enregistrer aussitôt » ; il doit passer **avec** le réessai, et
il dit combien de réessais ont servi (c'est la mesure de la fréquence
qu'on n'a pas aujourd'hui). Question : on le garde dans la suite
d'intégration (≈ 10 s) ou derrière un marqueur à part ?

### Ce que la CI et le compose doivent attendre

- Le healthcheck ne regarde que Kafka. J'ajoute le registre : `rpk cluster
  info … && rpk registry subject list -X registry.hosts=localhost:8081`
  (rpk est dans l'image ; pas de `curl` à supposer). Je le dis franchement :
  **ce n'est pas la cause ici** (l'étape « Schémas » avait déjà écrit dix
  sujets), mais `make up` doit rendre un registre prêt, pas seulement un
  Kafka.
- L'étape « Schémas » de la CI reste la preuve qu'**une écriture** passe
  avant les tests.

### Comment on saura, à la prochaine coupure

- `pytest -q -rE -m integration` (les erreurs de mise en place dans le
  résumé) ;
- avant les tests, en CI seulement, le journal du registre au niveau
  `debug` : `rpk redpanda admin config log-level set schemaregistry
  pandaproxy kafka/client --level debug --expiry-seconds 0` (par l'API
  d'administration, sans toucher au compose du Mac) ;
- en cas d'échec : **tout** le journal du courtier (pas `--tail=100`, qui
  n'a gardé que 4 s ici), plus `rpk cluster health` et `docker stats
  --no-stream pharmaflux-redpanda`, déposés comme **artefact** du run
  (`actions/upload-artifact`, épinglé par empreinte comme les autres actions)
  plutôt que dans le journal du job ;
- les lignes de réessai, horodatées, qui donnent la minute à chercher dans
  ce journal.

**Questions A** :
1. Nettoyage en fin de session plutôt qu'à chaque test : d'accord ?
2. Réessai : 3 essais, attentes 0,2 et 0,8 s, seulement sans réponse ; un
   réessai pendant les tests d'intégration fait échouer la CI : strict ou
   simple avertissement ?
3. `--memory=768M` et `--smp=1` : je ne propose pas de les changer, rien ne
   les accuse. D'accord ?

---

## B. La base vectorielle

### Constat

Ce qu'il faut ranger, au grain proposé (D) : environ **72 000 fragments**,
37 Mo de texte brut avant nettoyage ; à 384 dimensions en `float32`, 110 Mo
de vecteurs (le double à 768).

### Les options

| | Qdrant (compose) | pgvector (compose) | dans le processus (LanceDB, DuckDB `vss`) |
|---|---|---|---|
| Alamel | conteneur à part, port non standard | **un second Postgres**, port ≠ 5432 : risque de confusion avec `alamel-dev-postgres` | rien à lancer |
| image, épinglage | une image, versions au correctif près | une image `pgvector/pgvector:pgN` | une dépendance Python ; `vss` charge une extension téléchargée à l'exécution (contraire à « `make up` ne télécharge rien ») |
| mémoire au repos | quelques dizaines de Mo (à mesurer) | une centaine de Mo | celle du processus, déjà à 420 Mo pour le gold |
| hybride (mission 08) | vecteurs denses + creux nommés dans le même point, fusion RRF côté serveur (`query` + `prefetch`) ; le creux (BM25) se calcule côté client | `tsvector` français (racinisation native) + `vector` : le meilleur lexical français des trois | LanceDB : plein texte (tantivy) ; DuckDB : FTS à part |
| remplacer / supprimer un médicament | `upsert` par identifiant, `delete` par filtre sur `code_cis` (index de charge utile) | SQL, transactionnel | selon la bibliothèque |
| instant et position | un point d'état dans une petite collection à part (voir plus bas) | une table, **dans la même transaction** que les fragments | un fichier |
| lecture concurrente (API, mission 09) | oui, c'est un serveur | oui | délicat en écriture concurrente |

### Avis : Qdrant, dans le compose, et un client HTTP à nous

- **Qdrant**, comme le penche l'IeC et le dit le PRD : un service, un port,
  pas de second Postgres sur un colima qui en a déjà un. pgvector garde un
  vrai avantage (la transaction entre l'état et les fragments, le lexical
  français) ; je le note dans l'ADR 0011 comme l'alternative écartée, avec
  ce prix.
- **Compose** : service `qdrant`, `container_name: pharmaflux-qdrant`, port
  REST `127.0.0.1:16333:6333` (gRPC non exposé), volume `pharmaflux-qdrant`,
  `mem_limit: 512m`, télémétrie coupée (`QDRANT__TELEMETRY_DISABLED=true`),
  healthcheck sur `/readyz`. Les vecteurs restent en mémoire (110 Mo) ; si
  la mesure du palier 2 dépasse, `on_disk: true`.
- **Image** : `qdrant/qdrant:v1.X.Y`, la dernière version de correctif qui a
  **deux semaines** le jour du téléchargement, épinglée par **empreinte**
  (`@sha256:…`) dans le compose. beko la télécharge ; je n'invente pas le
  numéro aujourd'hui (je ne peux pas vérifier la date de publication sans
  réseau). La procédure est au palier 2.
- **Client** : je propose **de ne pas prendre `qdrant-client`**. Il apporte
  `grpcio`, `protobuf`, `portalocker`, `pydantic`, pour une dizaine d'appels
  REST (créer une collection et ses index, `upsert`, `delete` par filtre,
  `scroll`, `query`, alias, compter). `httpx` est déjà là, et c'est déjà
  ainsi qu'on parle au registre. C'est un module de 150 à 200 lignes, testé
  par `MockTransport` ; l'API REST de Qdrant est stable et documentée. Si
  l'IeC préfère la bibliothèque officielle, elle passe sous la règle des deux
  semaines comme le reste.
- **Collections** : une par **(version du format des fragments, modèle)**,
  par exemple `pharmaflux-fragments-f1-<modele court>`, et un **alias**
  `pharmaflux-fragments` qui désigne la collection courante. `index
  construire` remplit une collection neuve puis bascule l'alias (atomique
  côté Qdrant) : jamais d'index à moitié construit sous le nom que lisent
  `chercher` et, plus tard, l'API. Un changement de format ou de modèle est
  une collection de plus, jamais un mélange.
- **Instant et position** : une collection `pharmaflux-index-etat` d'un
  point (charge utile seule) par collection de fragments : instant appliqué,
  instant visé pendant une mise à jour, format, modèle (nom, révision,
  empreinte), nombre de fragments. **Dans Qdrant, pas dans un fichier** :
  un `down -v` efface l'index et son état ensemble, jamais l'un sans
  l'autre. Pas de transaction avec les fragments : l'ordre d'écriture et
  l'idempotence en tiennent lieu (E).

**Questions B** : 1. Qdrant avec un client `httpx` maison, plutôt que
`qdrant-client` ? 2. Le port `16333` ? 3. Le nom de la collection d'état
(ou une autre place pour l'état) ?

---

## C. Le modèle d'embeddings

### Constat

Je n'ai aucun fichier de modèle sur le Mac (ni cache Hugging Face, ni
`fastembed`), et je n'en télécharge pas : **je ne peux donner aujourd'hui
ni mémoire, ni temps, ni qualité mesurés**. Ce qui suit vient des fiches des
modèles, à vérifier au téléchargement.

Le volume à encoder, lui, est mesuré : environ 72 000 fragments ; une fois
retirées du texte encodé les lignes de citation et les balises HTML (D),
autour de 25 millions de caractères, soit de l'ordre de **7 à 8 millions de
jetons** (estimation à 3,5 caractères par jeton, à remplacer par le vrai
décompte du tokenizer).

| candidat | paramètres | dimension | fenêtre | licence | fichiers | remarque |
|---|---|---|---|---|---|---|
| `intfloat/multilingual-e5-small` | 118 M (dont ~96 M d'embeddings de vocabulaire) | 384 | 512 | MIT | ONNX ~470 Mo en float32, ~120 Mo quantifié int8 | préfixes `passage: ` / `query: ` ; bon en français dans MTEB |
| `minishlab/potion-multilingual-128M` (Model2Vec, statique) | 128 M (une table) | 256 | sans limite pratique | MIT | safetensors | **pas de transformeur** : des ordres de grandeur plus rapide ; qualité nettement plus basse ; mémoire de la table à vérifier (≈ 500 Mo en float32) |
| `intfloat/multilingual-e5-base` | 278 M | 768 | 512 | MIT | ONNX ~1,1 Go float32, ~280 Mo int8 | référence de qualité ; probablement trop lent et trop lourd pour le seuil |

Écartés : `bge-m3` (568 M), `gte-multilingual-base` et `arctic-embed-m-v2.0`
(305 M, trop près du seuil), `jina-embeddings-v3` (licence non commerciale),
`paraphrase-multilingual-MiniLM-L12-v2` (fenêtre de 128 jetons).

**Le temps est l'inconnue.** Un ordre de grandeur, à confirmer : e5-small
fait ~40 MFLOP par jeton ; 7 à 8 millions de jetons, c'est quelques centaines
de TFLOP, soit **de 15 à 60 minutes** sur le processeur du Mac selon le
débit réel d'ONNX Runtime, et plus sur les deux vCPU de la CI. C'est
au-delà des 10 minutes de `make up` (PRD §2.2) et du `timeout-minutes: 15`
du job `integration`.

### Avis

- **Bibliothèque** : `onnxruntime` + `tokenizers` (Rust, sans PyTorch),
  avec `numpy` déjà là par PyArrow. Le pooling (moyenne masquée), la
  normalisation et les préfixes d'e5 tiennent en quarante lignes, que je
  préfère écrire et tester plutôt que de prendre `fastembed` ou
  `sentence-transformers` : `fastembed` télécharge lui-même ses modèles et
  apporte `huggingface-hub`, `requests`, `loguru`… ; `sentence-transformers`
  apporte PyTorch. Pour Model2Vec, `safetensors` + `tokenizers` suffisent
  (pas besoin du paquet `model2vec`).
- **Épinglage** : un fichier `infra/modeles/<nom>.toml` dans le dépôt : dépôt
  Hugging Face, **révision** (empreinte de commit, pas une branche), et pour
  chaque fichier (`model_quantized.onnx` ou équivalent, `tokenizer.json`,
  configuration) son chemin et son **sha256**. Le code refuse de charger un
  fichier dont l'empreinte diffère, et la met dans l'état de l'index.
- **Où** : hors de git, sous `$PHARMAFLUX_MODELES`, par défaut
  `~/pharmaflux-modeles/<nom>/<révision>/`, à côté de `~/pharmaflux-data`
  (pas dans `data/` du dépôt, qu'un `make rebatir` vide).
- **Téléchargement** : un script `infra/modeles/telecharger.sh <nom>` que
  **beko** lance, qui lit le TOML, télécharge chaque fichier à la révision
  donnée (`curl` vers `https://huggingface.co/<dépôt>/resolve/<révision>/
  <fichier>`), vérifie le sha256, et n'installe qu'après vérification.
- **`make up`** : `infra/demo/prerequis.sh` vérifie la présence et les
  empreintes des fichiers (sans réseau), et dit la commande à lancer s'ils
  manquent.
- **CI** : le même script dans le job `integration`, avec `actions/cache`
  sur la révision ; un fichier altéré fait échouer l'étape. Mais vu le
  temps, je propose que **la CI n'encode pas tout le jeu avec le vrai
  modèle** : la chaîne complète du jeu (fragments, construction, incrément,
  vérification) avec l'encodeur de test, et le vrai modèle sur un
  sous-ensemble fixe (les CIS du jeu de questions v0, quelques centaines de
  fragments) pour prouver qu'il se charge, que ses empreintes tiennent et que
  la recherche rend le fragment attendu.
- **Cache des vecteurs** : une table locale `(modèle, sha256 du texte) →
  vecteur`, sous `data/` (hors du volume Qdrant). §7.5 dit déjà qu'un texte
  inchangé n'est pas recalculé ; ce cache l'étend à `make rebatir` et à un
  changement de format qui ne touche pas certains textes. Un encodage
  complet ne se paierait qu'une fois par modèle.

**Ce que je propose pour trancher le modèle** : que beko télécharge, selon
une procédure que j'écris en tête du palier 2, **e5-small (int8) et
potion-multilingual-128M**, et que le palier 2 commence par une mesure
écrite (mémoire, temps sur tout le jeu, rang du fragment attendu sur les
questions v0) **avant** de figer le modèle. Le choix se rend dans le
rapport du palier 2, et l'ADR 0011 l'enregistre.

**Questions C** : 1. Le choix du modèle peut-il se faire au début du
palier 2, sur mesure, plutôt qu'au §0 ? 2. La CI : chaîne complète avec
l'encodeur de test, vrai modèle sur un sous-ensemble : d'accord ? 3. Le
cache des vecteurs : dans la mission, ou plus tard ? 4. `~/pharmaflux-modeles`
pour les fichiers ?

---

## D. Les fragments

### Constat : la fiche du jeu

`pharmaflux gold fiche --tout` : **21 445 fiches**, 3,8 s, **419 Mo**
résidents, 67 Mo de JSON Lines. Dont **5 562 fiches partielles** (hors
référentiel), 7 855 MITM, **679 CIS avec un signalement** de disponibilité,
**662 lignes de signalement sans CIP13**, **un seul début à venir** (CIS
66890524, arrêt annoncé au 01/07/2027), une seule valeur illisible
(CIS 61096104, déjà vue à la mission 06).

Le texte de `fiche_en_texte` sur tout le jeu : 35 millions de caractères,
**1 535 en médiane**, 4 623 au 99ᵉ centile, 11 184 au plus ; **7 144 fiches
dépassent 1 800 caractères**, soit ~512 jetons : **la fiche entière ne tient
pas dans la fenêtre d'e5** pour un tiers du jeu. Une section par fragment,
à l'inverse, donnerait environ 117 000 fragments, dont beaucoup de quelques
dizaines de caractères (les conditions de prescription : 45 en médiane), qui
ne disent rien sans le nom du médicament.

### Avis : cinq fragments par fiche au plus

Chaque fragment commence par la ligne d'identité (`CIS … — dénomination`),
pour qu'il se comprenne seul et qu'une question sur un nom le trouve. Les
sections se regroupent par rythme de changement et par usage :

| fragment | contenu | fiches | médiane | > 1 500 car. |
|---|---|---|---|---|
| `identite` | spécialité, composition, groupes génériques, conditions de prescription (ou « fiche partielle ») | 21 445 | 599 | 55 |
| `presentations` | présentations, taux, prix | 14 619 | 369 | 45 |
| `avis` | SMR et ASMR | 9 205 | 403 | 93 |
| `disponibilite` | MITM et signalements, **ou** « aucun signalement » | 21 445 | 317 | 0 |
| `informations` | informations importantes en cours | 5 128 | 834 | 937 |

**71 842 fragments** (tailles mesurées avec la ligne d'identité et une
ligne de citation de 120 caractères). Un fragment `disponibilite` existe
**pour chaque fiche**, même sans signalement : c'est lui qui doit répondre
« aucun signalement, ce n'est pas “disponible” » à « X est-il disponible ? ».

**Ce qui dépasse la fenêtre** se découpe **par élément**, jamais au milieu
d'une ligne : les éléments s'ajoutent dans l'ordre du gold jusqu'à une borne
(proposée : 1 500 caractères, à recaler sur le décompte réel du tokenizer
au palier 2), puis une partie suivante commence, qui répète la ligne
d'identité et dit « (suite, partie 2 sur 3) ». Environ 1 100 fiches ont au
moins une section à découper, presque toutes par les informations
importantes.

**Le texte encodé ne contient ni l'instant de l'état, ni les liens, ni les
lignes de citation** : ils sont dans les métadonnées, rendus à côté du texte
par `chercher` (et plus tard par l'assistant). Les informations importantes
sont aujourd'hui du HTML brut (`<a target='_blank' title="Lien direct vers
l'information importante sur le site de l'ANSM - Nouvelle fen&ecirc;tre"
href='…'>Titre</a>`) : le texte encodé garde **le titre**, le lien va dans
les métadonnées. Le libellé n'est pas modifié, seulement extrait de sa
balise ; je le pose en question, à cause de la clause « sans altération »
de la licence BDPM.

### Exemple réel : CIS 60016589, fragment `disponibilite`

```
CIS 60016589 — LEVOCARNIL 1 g/5 ml, solution injectable en ampoule
Médicament d'intérêt thérapeutique majeur (ATC A16AA01, liste publiée le 2024-12-18).
Disponibilité, signalements en cours (1) :
  - Remise à disposition depuis le 2026-07-15, mis à jour le 2026-07-16 ;
    vise la spécialité entière (toutes ses présentations), aucune
    présentation (CIP13) n'est nommée.
```

métadonnées : `code_cis` `60016589`, `section` `disponibilite`, `partie` 1/1,
`sources` = [`CIS_CIP_Dispo_Spec.txt`, source du 2026-10-21, observée depuis
le 2026-10-24T19:42:01Z ; `CIS_MITM.txt`, source du 2026-10-13, observée
depuis le 2026-10-24T19:42:03Z], `liens` = [la page ANSM],
`format` `1`, `empreinte_texte` (sha256).

### La prudence du gold, cas réels du jeu

| cas | CIS | texte proposé |
|---|---|---|
| ligne sans CIP13 | 60016589 | « vise la spécialité entière (toutes ses présentations), aucune présentation (CIP13) n'est nommée » |
| début à venir | 66890524 | « Arrêt de commercialisation **annoncé à partir du 2027-07-01, pas encore commencé** au jour de l'état (mis à jour le 2026-08-07) » |
| fiche partielle | 60000229 | fragment `identite` : « CIS 60000229, absent du référentiel des spécialités (CIS_bdpm.txt) : fiche partielle, faite des seuls fichiers qui citent ce CIS (ici : informations importantes) » |
| `aucun_signalement` | 60002283 | « Aucun signalement dans le fichier de disponibilité de l'ANSM. **Cela ne veut pas dire “disponible”** : le fichier ne liste que les ruptures, tensions, arrêts et remises à disposition déclarés. » |
| valeur illisible | 61096104 | la colonne est **absente** du texte, et une phrase dit : « valeur illisible dans la source, non reprise : numéro d'autorisation européenne » |

Le mot « disponible » n'apparaît que dans « remise à disposition » (libellé
de la source) et dans la phrase de prudence : un test le vérifie sur tout le
jeu.

### Identifiant, métadonnées, version du format

- **Identifiant** : `uuid5(ESPACE_PHARMAFLUX, "f<format>/<cis>/<section>/<partie>")`
  (Qdrant veut un UUID ou un entier). Il ne dépend **pas** du texte :
  un fragment qui change garde son identifiant (l'`upsert` le remplace) ;
  un fragment qui disparaît (une section vidée, une partie de moins) est
  retiré. L'empreinte du texte (sha256) est une métadonnée, qui décide du
  recalcul du vecteur.
- **Métadonnées** : `code_cis`, `denomination`, `section`, `partie`,
  `parties`, `sources` (fichier, date de la source, observée depuis), `liens`,
  `dans_referentiel`, `format`, `empreinte_texte`. **L'instant de l'état est
  celui de l'index**, tenu une fois dans l'état de l'index et rendu avec chaque
  résultat, pas copié dans chaque fragment : sinon chaque nouvelle
  observation réécrirait 72 000 charges utiles, et un fragment non touché
  par l'incrément porterait un autre instant que dans la reconstruction.
  C'est un écart à la lettre de l'ordre (« chacun porte … l'instant de
  l'état ») : je le pose en question.
- **Version du format** (`format = 1`) : elle change dès que, pour les mêmes
  fiches, le texte, l'identifiant ou les métadonnées changeraient : grain,
  regroupement, borne de découpe, formulation, champs. Elle est dans
  l'identifiant et le nom de la collection : un nouveau format est une
  nouvelle collection, construite en entier.

**Questions D** : 1. Les cinq fragments par fiche ? 2. L'instant au niveau
de l'index et non de chaque fragment ? 3. Le titre extrait du HTML des
informations importantes, le lien en métadonnée ? 4. Les **alternatives**
(mêmes groupes génériques, avec leur disponibilité) **hors des fragments** :
elles changent avec la disponibilité de **tous** les membres du groupe, ce
qui ferait d'un signalement un recalcul de tout le groupe ; la mission 08
les lira dans le gold au moment de répondre. D'accord ?

---

## E. La mise à jour incrémentale

### Avis : depuis les versions du silver

D'accord avec l'IeC. L'index lit le gold, qui lit le silver : suivre le
silver garantit par construction que l'index n'est jamais en avance, sans
position de bus à garder cohérente avec celle du silver. Le bus resterait un
détour : un événement lu avant que le silver l'ait appliqué ferait calculer
une fiche qui ne le contient pas encore.

### Les CIS touchés entre l'instant de l'index `T0` et l'instant visé `T1`

`T1` est lu **une fois**, au début : la dernière observation du silver. Les
versions touchées sont celles **ouvertes ou fermées** dans `]T0, T1]`
(`debut_validite` ou `fin_validite` dans l'intervalle). De chacune :

| entité | CIS touchés |
|---|---|
| spécialités, présentations, compositions, conditions, SMR, ASMR, MITM, informations importantes | le `code_cis` de la ligne |
| disponibilité, avec ou sans CIP13 | le `code_cis` de la ligne (il est présent même quand le CIP13 est vide) |
| groupes génériques | le `code_cis` de la ligne seulement : la fiche ne montre que les groupes du CIS, pas ses voisins (alternatives hors des fragments, D4) |
| liens vers les avis de la CT | les CIS dont un avis SMR ou ASMR porte ce `code_dossier_has`, **à `T0` et à `T1`** (un avis qui change de dossier touche l'ancien et le nouveau) |

**Plus les bascules du jour**, sans aucune version du silver :

- les signalements dont `date_debut` est dans `]jour(T0), jour(T1)]` (un
  début annoncé devient en cours) ;
- les informations importantes dont `date_debut` est dans
  `]jour(T0), jour(T1)]` ou `date_fin` dans `[jour(T0), jour(T1)[` (elles
  entrent dans la fiche, ou en sortent).

Sans elles, l'index divergerait de la reconstruction au premier jour qui
franchit une de ces dates. Elles se lisent dans l'état du silver à `T1`.

### Remplacement, suppression, reprise

Pour chaque CIS touché, les fragments sont **recalculés depuis le gold à
`T1`** (tout le gold est calculé, puis filtré sur ces CIS : c'est ce que fait
déjà la fiche, en 3,8 s) :

1. au début : l'état reçoit `vise = T1` (l'instant appliqué reste `T0`) ;
2. pour chaque CIS, par lots : `upsert` des fragments dont l'empreinte du
   texte a changé (vecteur recalculé) ou dont seules les métadonnées ont
   changé (vecteur repris du point existant ou du cache) ; puis suppression
   des points de ce CIS **dont l'identifiant n'est plus dans le nouvel
   ensemble** (filtre `code_cis` + `must_not has_id`). Jamais de « tout
   supprimer puis tout réécrire » : un CIS n'est jamais vide entre les deux ;
3. un CIS qui n'existe plus à `T1` (aucune ligne dans aucune entité) : tous
   ses points sont retirés ;
4. à la fin seulement : `instant = T1`, `vise` effacé.

**Reprise** : une coupure à n'importe quel point laisse `instant = T0` ; la
commande suivante relit `T1' >= T1` et refait `]T0, T1']`. Chaque étape est
idempotente (`upsert` par identifiant, suppression par différence) : refaire
une partie déjà faite ne change rien. Un `vise` présent au démarrage est dit
dans la sortie (« reprise d'une mise à jour interrompue »).

**Rien n'a changé** (`T1 == T0`, ou aucun CIS touché) : aucun appel au
modèle, l'instant avance à `T1`, code 0, et la sortie le dit.

**Silver en arrière de l'index** (`T1 < T0`, un silver reconstruit plus
court) : refus, code 2 ; c'est à `index construire` de repartir.

**Questions E** : 1. Les bascules du jour dans l'incrément, d'accord ?
2. Le gold calculé en entier puis filtré (simple, 3,8 s et 419 Mo) plutôt
qu'un gold restreint à quelques CIS (plus rapide, mais un second chemin de
calcul à tenir égal au premier) ?

---

## F. La vérification

`pharmaflux index verifier` recalcule **tous** les fragments depuis le gold
à l'instant de l'index (pas à la dernière observation du silver : on vérifie
ce que l'index dit être) et compare à ce que contient la collection :

- **ensemble des identifiants** : manquants (dans le calcul, pas dans
  l'index) et **orphelins** (dans l'index, pas dans le calcul) ;
- pour chaque identifiant commun : **texte** (par l'empreinte, puis le texte
  lui-même s'ils diffèrent), **métadonnées** (toutes, comparées en JSON
  canonique) ;
- **vecteurs** : présents, de la bonne dimension, et **égaux au cache ou à
  l'encodage de leur texte** sur un échantillon fixe (100 fragments, tirés
  par identifiant trié) : comparer tous les vecteurs demanderait de
  réencoder tout le jeu. Avec l'encodeur de test (déterministe), on compare
  tous les vecteurs ;
- l'**état** : pas de `vise` en suspens, format et modèle égaux à ceux de la
  collection.

Codes : **0** conforme ; **1** écart (liste des identifiants en cause, au
plus 20 par catégorie, et les nombres) ; **2** refus (pas d'index, Qdrant
injoignable, modèle aux empreintes fausses, instant de l'index plus récent
que le silver).

**Le test par tranches** (intégration, Qdrant requis, encodeur de test) :
les fichiers d'événements du jeu de démo (18 archives retenues) appliqués au
silver d'un dossier jetable **par tranches** (une archive, puis plusieurs),
`index mettre-a-jour` après chacune, et à chaque étape `index verifier`
conforme **et** l'égalité avec un `index construire` dans une seconde
collection au même instant. Plus des tests unitaires, sur un faux Qdrant en
mémoire derrière la même interface : coupure simulée après chaque étape de
la mise à jour puis reprise ; un CIS qui disparaît ; une section qui se
vide ; un découpage qui passe de 3 parties à 2 ; une bascule du jour ; rien
de changé.

**Question F** : l'échantillon de 100 vecteurs avec le vrai modèle, tous avec
l'encodeur de test : suffisant ?

---

## G. La recherche

`pharmaflux index chercher "question" [-k 5] [--cis …] [--section …]
[--format texte|jsonl]` : la question préfixée (`query: ` pour e5), encodée,
les `k` plus proches (cosinus) dans l'alias courant, avec leur **score**,
leur **CIS et dénomination**, leur **section**, leurs **sources** (fichier,
date de la source, observée depuis) et l'**instant de l'index**. Les filtres
`--cis` et `--section` sont des filtres de Qdrant sur les métadonnées
indexées ; ils serviront à la mission 08 (« la disponibilité de ce CIS »).
Pas de seuil, pas d'abstention, pas de réponse.

**Ce que je mesure pour la mission 08** : pour les questions du jeu v0 qui
nomment un médicament, le **rang du premier fragment du bon CIS et de la
bonne section** (rappel à 1, 5 et 10, et le rang moyen réciproque), et le
score du premier résultat pour les questions hors périmètre (pour voir s'il
se distingue ; c'est une donnée pour l'abstention, pas une règle). Une
commande `index evaluer` qui écrit ce tableau, ou un script de test : je
préfère la commande, la mission 09 la mettra dans la CI.

**Question G** : `index evaluer` dans cette mission ?

---

## H. Les commandes

Le groupe `pharmaflux index`, sur le modèle des groupes `silver` et `gold` :

| commande | ce qu'elle fait | sortie | codes |
|---|---|---|---|
| `index fragments [--a …] [--cis …]` | les fragments depuis le gold, sans index ni modèle (palier 1) | JSON Lines, un fragment par ligne, triés par identifiant | 0 ; 2 refus |
| `index construire` | collection neuve, tous les fragments, encodage (cache), bascule de l'alias, état | une ligne de bilan (fragments, encodés, repris du cache, durée, instant) | 0 ; 2 refus |
| `index mettre-a-jour` | `]T0, T1]` (E) | bilan : CIS touchés (dont bascules du jour), fragments remplacés, ajoutés, retirés, inchangés, encodés | 0 (y compris « rien à faire ») ; 2 refus |
| `index verifier` | F | conforme, ou les écarts | 0 ; 1 écart ; 2 refus |
| `index chercher` | G | texte (défaut) ou JSON Lines | 0 ; 2 refus |
| `index etat` | instant, `vise` en suspens, format, modèle (nom, révision, empreinte), collection et alias, nombre de fragments par section | texte ou JSON | 0 ; 2 pas d'index |
| `index evaluer` (G, si retenu) | rangs sur le jeu v0 | tableau | 0 ; 2 refus |

Options communes : `--entrepot` (comme `gold`), `--qdrant` (défaut
`http://127.0.0.1:16333`, variable `PHARMAFLUX_QDRANT`), `--modele` (le nom
du TOML épinglé). `construire` et `mettre-a-jour` refusent si un autre
processus tient l'index (verrou fichier sous `data/`), pour ne pas mélanger
deux mises à jour.

---

## I. `Makefile`, compose et CI

- **Compose** : le service `qdrant` (B), lancé par `make up`
  (`--wait`, son healthcheck), arrêté par `make down`, effacé par `make
  rebatir` (`down -v` efface déjà tous les volumes du projet, donc
  `pharmaflux-qdrant` aussi). Une procédure de téléchargement de l'image dans
  l'en-tête du compose, comme pour Redpanda.
- **`infra/demo/prerequis.sh`** : vérifie l'image Qdrant présente (`docker
  images`, comme pour Redpanda) et les fichiers du modèle présents avec leurs
  empreintes ; dit la commande de beko sinon.
- **Cible `make index`** : `index mettre-a-jour` si l'index existe, sinon
  `index construire`, puis `index verifier`. Elle vient après `make gold`.
  `make demo` ne l'enchaîne pas (le temps d'encodage).
- **CI, job `integration`** : Qdrant démarre avec Redpanda (même `up
  --wait`) ; après `make gold`, une étape « Index du jeu, encodeur de test,
  par incréments, vérifié » (construire sur un premier état, mettre à jour,
  vérifier), puis « Modèle épinglé sur un sous-ensemble » (téléchargement
  épinglé avec cache, empreintes, quelques centaines de fragments,
  `chercher` sur trois questions). Estimation : 1 à 2 min pour la première
  (72 000 fragments, `upsert` par lots de 512), 1 min pour la seconde avec
  le cache chaud, 2 à 3 min à froid. `timeout-minutes` passe de 15 à 20.
  Le job `verifier` ne change pas.

**Question I** : `make index` qui choisit entre `construire` et
`mettre-a-jour`, ou deux cibles explicites ?

---

## J. La mémoire et le temps

**Mesuré** : `gold fiche --tout`, **419 Mo**, 3,8 s. Le calcul des fragments
partira de là (la fiche, puis du texte par lots), donc ~420-440 Mo.

**Estimé, à mesurer** : ONNX Runtime + e5-small int8, ~150 à 250 Mo
résidents ; en float32, ~550 Mo. Model2Vec en float32, ~550 Mo, ~300 Mo en
float16. **Le gold et le modèle dans le même processus dépasseraient le seuil
de 512 Mo.**

**Avis : deux processus.** `index construire` et `mettre-a-jour` lancent
`pharmaflux index fragments` dans un **sous-processus** (gold, PyArrow,
DuckDB), qui écrit les fragments en JSON Lines dans un fichier temporaire de
`data/`, écrit entier puis renommé ; le processus parent, qui n'importe ni
PyArrow ni DuckDB, lit ce fichier, encode et écrit dans Qdrant. Chacun est
mesuré à part et doit tenir sous 512 Mo. `index verifier` fait de même ;
`index chercher` n'a besoin que du modèle et de Qdrant.

Le temps total de `construire` est l'inconnue de C ; `mettre-a-jour` sur un
jour réel du jeu (quelques CIS) devrait tenir en quelques secondes plus les
3,8 s du gold.

---

## K. Autre

1. **Le journal de CI vient du run de `main`** après la fusion (`98505d3`),
   pas de la PR #7 (constat 2). La première entrée du journal le dira.
2. **Le job `verifier`** passe 3 min 37 s dans `pytest -q`, dont une bonne
   part à tenter de joindre un courtier qui n'existe pas (`Connection
   refused` en boucle de librdkafka avant le saut). Hors périmètre, mais une
   proposition : le saut décidé par une seule tentative courte, une fois par
   session. À trancher plus tard.
3. **Les informations importantes sont partagées par beaucoup de CIS**
   (CIS 60000229 : douze actualités ANSM sur les analogues du GLP-1, que
   d'autres CIS citent aussi). Au grain proposé, le même titre est encodé
   dans autant de fragments que de CIS : le cache par empreinte de texte ne
   le factorise pas (la ligne d'identité diffère). C'est le prix de
   fragments autonomes ; j'en mesurerai le poids au palier 2.
4. **Les 5 562 fiches partielles** : faut-il les indexer ? Elles ne viennent
   que de fichiers qui citent un CIS absent du référentiel (souvent les
   informations importantes). Je propose oui, avec la phrase de prudence :
   une question sur un CIS hors référentiel doit trouver qu'il l'est.
5. **La relance d'un test en CI** : aucun `--reruns` (pas de
   `pytest-rerunfailures`) ; une relance n'est pas une correction, et un
   rerun automatique cacherait exactement ce que A veut voir.
6. **Dépendances nouvelles** proposées : `onnxruntime`, `tokenizers`
   (et `safetensors` si Model2Vec reste candidat). Aucune pour Qdrant (client
   `httpx`). Chacune à la dernière version qui a deux semaines le jour du
   verrou, avec les plafonds de l'ADR 0009 ; je justifierai les versions dans
   le rapport du palier où elles entrent (2).
7. **Paliers** : le palier 1 tient tel quel (registre, fragments, `index
   fragments`, journal). Le palier 2 commence par la mesure des deux modèles
   (C), qui demande les fichiers : beko les télécharge pendant le contrôle du
   palier 1, selon la procédure que j'écris au palier 1 si l'IeC est d'accord
   (c'est un fichier TOML et un script, sans exécution de ma part).

## Récapitulatif des questions

| # | question | mon avis |
|---|---|---|
| A1 | nettoyage des sujets et topics de test en fin de session | oui |
| A2 | réessai 3 essais, 0,2 et 0,8 s, sans réponse seulement ; un réessai en test d'intégration fait échouer la CI | oui, strict |
| A3 | ne pas toucher `--memory`, `--smp` | oui |
| A-test | test de reproduction (30 cycles) dans la suite d'intégration | oui |
| B1 | Qdrant, client `httpx` maison | oui |
| B2 | port `16333`, volume `pharmaflux-qdrant` | oui |
| B3 | état de l'index dans une collection Qdrant à part, alias pour la collection courante | oui |
| C1 | modèle choisi au début du palier 2, sur mesure (e5-small int8 et potion-multilingual-128M) | oui |
| C2 | CI : encodeur de test sur tout le jeu, vrai modèle sur un sous-ensemble | oui |
| C3 | cache des vecteurs par empreinte de texte | oui, dans la mission |
| C4 | fichiers du modèle sous `~/pharmaflux-modeles` | oui |
| D1 | cinq fragments par fiche, découpe par élément | oui |
| D2 | instant de l'état au niveau de l'index | oui |
| D3 | titre extrait du HTML, lien en métadonnée | oui, si la licence le permet |
| D4 | alternatives hors des fragments | oui |
| E1 | bascules du jour dans l'incrément | oui (nécessaire) |
| E2 | gold entier puis filtré | oui |
| F | 100 vecteurs vérifiés avec le vrai modèle | oui |
| G | `index evaluer` dans la mission | oui |
| I | `make index` choisit entre construire et mettre à jour | oui |
| K7 | procédure de téléchargement du modèle écrite au palier 1 | oui |
