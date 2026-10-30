# Mission 08 — contrôle du palier 1 par l'IeC

**Commit contrôlé** : `afe0c68` (recherche hybride, format 2, jeu v1), revu
contre l'ordre et l'addendum 1 (`385490b`), ainsi que les quatre
confirmations données par message avant le palier. **Verdict : palier 1
accepté. Le palier 2 est ouvert**, avec les deux points ci-dessous à
reprendre dans son commit.

## Revérifié par l'IeC

Dans ton dossier, l'arbre propre sur `afe0c68` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | verts (270 fichiers) |
| `uv run mypy src` | vert, 68 fichiers |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **620 passed** en 6 min, mais **session en échec** : un réessai du registre pendant les tests d'intégration (voir plus bas) |
| `questions verifier` v1, `--racine demo/archive` | 88 : 55 conformes, 10 non calculables, 23 sans attendu |
| idem avec `--entrepot data/demo/lakehouse` | 55 depuis le gold : 55 concordent |

Lus dans le code :
- **`index/lexical.py`** fait ce que l'addendum demande :
  - `K1`, `B` et `LONGUEUR_MOYENNE = 53,29` sont figés ;
  - `|d|` se compte comme la moyenne ;
  - les indices viennent de `blake2b` sur 31 bits, et les collisions
    s'additionnent ;
  - la requête porte la fréquence brute, et l'IDF reste à Qdrant
    (`modifier: idf`).
- **`verifier`** compare le vecteur creux stocké au recalcul, trié, en
  `float32`, et ne lit jamais un score.
- **L'écriture d'un lot** pose le vecteur creux à chaque point. La
  construction et la mise à jour partagent donc le même chemin.
- **Le jeu v1** :
  - les pièges et les deux cas limites sont là (`medical-006`,
    `disponibilite-009`, `-010`, `-011`, `hors_perimetre-006`) ;
  - `avis_has-005` est une réponse avec réserve ;
  - `alternatives-004` est retirée.

La mesure atteint la cible de l'addendum A : l'hybride est au moins égal au
dense pour le bon CIS à 5 et à 10, sur la v0 comme sur la v1. Il retrouve
les deux questions `identite` que le dense manquait, et le rang réciproque
passe de 0,680 à 0,747 sur la v1.

## Écarts tranchés

- **88 questions** : accepté. Chaque catégorie a au moins dix questions, et
  « environ 90 » n'était pas un compte exact. N'en ajoute pas.
- **`doit_citer` et `instant_cite` ne sont pas des champs par question** :
  accepté. Puisque le code rend lui-même les sources, leurs dates et
  l'instant (addendum C), ce sont des invariants de toute réponse, que la
  notation du palier 3 vérifie partout.
- **Les attendus de présentation sont cités à l'archive du 27/10** quand
  `CIS_CIP_bdpm.txt` a changé le 26/10 : accepté. Le gold à l'instant de
  l'index concorde avec eux.
- **Le RRF est fait côté client et non par Qdrant** : accepté, mais **cet
  écart n'est pas déclaré** dans la section « Écarts » de ton rapport, alors
  que l'addendum disait « côté serveur ». La raison est bonne :
  - la constante `k` est explicite dans notre code ;
  - les ex æquo sont tranchés par identifiant, donc l'ordre est
    reproductible ;
  - le coût, deux requêtes au lieu d'une, est négligeable.

  **À faire** : déclare-le dans le rapport du palier 2, et écris-le dans
  l'ADR 0012.

## À reprendre au palier 2

1. **`depense` dans la v1** doit dire ce que l'assistant fera. Aujourd'hui,
   `comportement = "reponse"` avec `calculable_au = "lot4"` se lit comme
   « on attend une réponse », alors que l'assistant s'abstient. Un lecteur
   du fichier, un recruteur par exemple, y verra une contradiction. Pour
   la **v1 seulement**, le parseur accepte `comportement = "abstention"`
   avec `calculable_au = "lot4"`, et les dix questions `depense` passent à
   cette forme. La v0 ne change pas.
2. **Le RRF côté client**, à déclarer (voir plus haut).
3. **La coupure du registre, revenue chez l'IeC.** Ton passage était
   propre, le mien non :
   - **ce qui s'est passé** : `POST /subjects/pharmaflux.test-3b5668ae.bdpm.disponibilite.v1-value/versions`
     a été coupé sans réponse (`RemoteProtocolError`) à
     2026-10-30T15:41:53.4Z ; le réessai a servi, puis la règle de la
     mission 07 a fait échouer la session, comme prévu ;
   - **ce qui diffère de la mission 07** : le journal du courtier ne montre
     **aucune** suppression de topic ni aucune ligne du registre dans les
     13 secondes qui précèdent (les coupures de la mission 07 suivaient de
     15 à 20 ms une suppression). La coupure tombe sur le **premier**
     enregistrement d'un nouveau préfixe de test.

   Ce palier ne touche pas au bus, donc il n'est pas bloqué. Mais **la CI de
   la PR doit passer du premier coup**. Au palier 2, examine une seule piste,
   bornée, et rends-en compte dans le rapport : une connexion HTTP gardée
   ouverte par le client du registre, que Redpanda fermerait après un délai
   d'inactivité plus court que celui du client (le `keepalive_expiry`
   d'httpx). Lis le délai des deux côtés dans la documentation et dans le
   code. Ne change le client que si la piste se confirme, avec un test.
   Sinon, dis-le, et on s'en tient à la règle actuelle.

## La clé de l'API et ta démonstration du palier 2

Ce point modifie l'ordre (décision 6), par l'addendum 2 sur `main`.

- **La clé vit dans le trousseau macOS de beko.** Elle n'est donnée qu'au
  processus que lance `infra/agents/avec-cle.sh`, et **beko seul** lance ce
  script, depuis Terminal.app. Le garde-fou refuse à tous les rôles
  `security find-…` et `avec-cle.sh`. Tu ne trouveras la clé ni dans ton
  environnement, ni dans un fichier.
- **Ta démonstration des cinq questions** : tu prépares les commandes
  (`sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "…"`),
  beko les lance, puis tu cites sa sortie dans le rapport avec le coût réel
  et ce qui reste du plafond. `pharmaflux assistant depenses` ne lit que le
  journal local : tu peux le lancer toi-même.
- **Tes tests et tes essais** passent par le double du client. Aucun appel
  réel ne part de ta session.
- Le code trouve la clé où le SDK la cherche (`ANTHROPIC_API_KEY`), comme
  l'ordre le dit. Rien ne change dans ce que tu codes.

## Si une nouvelle session reprend le palier 2

beko envisage de confier le palier 2 à une session neuve. Dans ce cas, elle
lit, dans cet ordre :
1. l'ordre et ses addenda 1 et 2, sur `main` ;
2. `points-a-trancher.md` ;
3. `palier-1.md` ;
4. ce contrôle.

Ses commits portent le trailer du modèle que nomme l'addendum 2.

## Remarques pour le palier 2, sans correction ici

- **`disponibilite-011`** (« Mon traitement par LARIAM… ») est le piège de
  tes règles de refus : « mon traitement » n'y demande aucune décision. Le
  test « aucun faux refus sur la v1 » doit le laisser passer.
- **`avis_has-005`** porte `date_avis = "20260909"` à l'état brut. Le
  contrôle des dates de la réponse doit relier une date rédigée
  « 09/09/2026 » ou « 9 septembre 2026 » à la forme écrite dans le
  fragment cité. Teste ce cas.
- **La clé de l'API** : beko te dira quand elle est installée de son côté.
  Ne lance aucun appel réel avant son feu vert, et n'en demande jamais la
  valeur.
