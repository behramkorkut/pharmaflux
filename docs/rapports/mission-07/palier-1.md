# Mission 07 — palier 1 : CI fiable et fragments (décisions 1 et 2)

Addendum 1 lu (`241bff0`). Python pur pour les fragments : aucun modèle,
aucune image téléchargée, aucune requête vers les sources. Le Redpanda du
projet tournait sur le Mac : les tests d'intégration ont tourné. Les seules
commandes `docker` sont des lectures et deux essais de `rpk` dans le
conteneur : le healthcheck, et le niveau `debug` des loggers, posé 5 s puis
revenu de lui-même. Aucun refus du garde-fou.

**Fait**

- **Registre** (A) : `Registre._envoyer` réessaie deux fois, après 0,2 puis
  0,8 s, un appel **coupé sans réponse** (`RemoteProtocolError`,
  `ConnectError`, `ReadError`, `WriteError`). Il ne réessaie jamais une
  réponse, même 5xx, ni un `ReadTimeout`. Chaque réessai :
  - écrit une ligne horodatée à la milliseconde : `registre : POST … coupé
    sans réponse (RemoteProtocolError), essai 2/3 dans 0.2 s (…Z)` ;
  - s'ajoute au compteur du client et à `REESSAIS` (le processus).

  Au 3ᵉ échec, `RegistreIndisponible` dit « (3 essais) ». `schemas
  enregistrer` affiche le total s'il n'est pas nul. `supprimer` tente la
  suppression définitive même quand la douce répond 404.
- **Tests d'intégration** : la fixture de session `a_nettoyer` efface sujets
  et topics **une fois, en fin de session**. `pytest_sessionfinish` fait
  échouer la session si un réessai a servi, et liste les lignes horodatées ;
  vérifié avec un test jetable (code 1, section « réessais du registre »).
  Le **test de reproduction** (30 cycles « créer, effacer les topics,
  enregistrer aussitôt ») affiche son nombre de réessais, puis les retire du
  décompte : **1 réessai sur 30 cycles** au premier passage, récupéré.
- **Compose** : le healthcheck attend Kafka **et** `rpk registry subject
  list`. **CI** :
  - les loggers `schemaregistry`, `pandaproxy`, `pandaproxy/requests`,
    `kafka/client` et `httpd` passent en `debug` par `rpk cluster loggers set`
    (`--expiry-seconds 0`) ;
  - les tests d'intégration tournent avec `-rE` ;
  - en cas d'échec : tout le journal horodaté, `rpk cluster health` et
    `docker stats`, en artefact `diagnostic-courtier`, gardé 14 jours.
- **Fragments** (`pharmaflux.index.fragments`, Python pur) : cinq sections,
  `identite`, `presentations`, `avis`, `disponibilite`, `informations`.
  - Chaque fragment s'ouvre sur la ligne d'identité. Il est découpé par
    élément sous 1 500 caractères, avec « (partie k sur n) » et un sous-titre
    « (suite) ».
  - Identifiant `uuid5("f1/<cis>/<section>/<partie>")`, indépendant du texte.
  - Métadonnées : sources (fichier, date de la source, observée depuis),
    liens, `dans_referentiel`, format, empreinte sha256 du texte.
  - Ni instant, ni lien, ni citation dans le texte. Le titre d'une
    information importante est extrait de sa balise, entités décodées ; le
    lien va en métadonnée.
- **`pharmaflux index fragments`** (`--cis`, `--a`, `--entrepot`, `--sortie`
  écrit entier puis renommé) : sur le jeu, **72 075 fragments pour 21 445
  fiches**, **4,6 s et 418 Mo**, sha256 identique d'un calcul à l'autre.
  Par section :

  | identite | presentations | avis | disponibilite | informations |
  |---|---|---|---|---|
  | 21 496 | 14 693 | 9 222 | 21 445 | 5 219 |

  Aucun fragment au-delà de 1 500 caractères ; 189 sections découpées.
- **Modèles** (K7) : `index/modeles/e5-small-int8.toml` et
  `potion-multilingual-128m.toml` (dépôt, fichiers ; ni révision ni sha256
  encore), et `pharmaflux index modele relever | installer | verifier` :
  - `relever` prend la dernière révision qui a 14 jours, télécharge à sa
    place et affiche le TOML ;
  - `installer` vérifie le sha256 avant de mettre en place ;
  - `verifier` travaille sans réseau.

  Procédure de beko, modèles et image Qdrant épinglée par empreinte
  d'index multi-architecture : [`infra/index/README.md`](../../../infra/index/README.md).
- **Tests** : 30 de plus. `test_bus.py` +5 (réessai, 3 essais, 5xx et délai
  non réessayés, `supprimer`). `test_fragments.py` 16 : chaque règle de
  prudence ; sur le jeu, les nombres, le mot « disponible » et les cinq cas
  réels. `test_modeles.py` 8, hub simulé. Le test de reproduction.
- **Journal** : `make gold` 17 s et `make silver` 40 s en CI sur `main` ; le
  run en échec était celui de `main` (`98505d3`) ; le §0 ; ce palier.

**Le mot « disponible »** sur tout le jeu : hors de la phrase « aucun
signalement », 95 lignes, toutes des valeurs de la source citées mot pour mot.
94 sont des titres d'informations importantes (« Euthyrox sera disponible
jusqu'à fin 2028 » ×81, « stocks disponibles » ×10…), 1 est un libellé de
présentation. Le test l'exige : jamais dans le texte que nous écrivons.

**Vérifications locales** (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 242 files already formatted |
| `uv run mypy src` | Success: no issues found in 61 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE` | **568 passed** en 161 s (538 avant), les 12 `integration` compris, courtier présent |
| `uv run pytest -q -rE -m integration` | 12 passed ; reproduction : 1 réessai sur 30 cycles |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| YAML de `ci.yml` et du compose (`ruby -ryaml`) ; `docker compose -p pharmaflux config --quiet` | lus sans erreur |
| `demo verifier` ; `profil`, `questions verifier` sur `~/pharmaflux-data` | conforme ; 0 bloquante ; 25 conformes, 5 non calculables, 10 sans attendu |
| `evenements` sur la copie du Mac, `diff -r` contre la sortie de `98505d3` (`git archive`, `uv run --offline --frozen`) | identique |
| `silver verifier` sur le jeu | 22/22 conformes, 10,2 s |
| `gold qualite` ; `questions verifier --entrepot` sur le jeu | code 0 ; 25 concordent |
| shellcheck | sans objet, aucun `.sh` touché |

**Écarts à l'ordre**

1. **`index fragments` sort les fragments dans l'ordre des CIS, puis des
   sections, puis des parties**, pas trié par identifiant comme le disait le
   §0 H. Les trier tiendrait 72 000 fragments en mémoire dans le processus du
   gold, déjà à 418 Mo. L'ordre est aussi déterministe.
2. **Les liens d'un fragment découpé** sont ceux de sa section entière, pas
   ceux de sa seule partie (89 fiches, toutes en `informations`).
3. **Les avis gardent la forme de la fiche texte** : date, valeur, motif,
   dossier. Le libellé long de l'avis SMR ou ASMR n'est pas encodé : il
   doublerait la taille de la section, et la mission 08 apporte le corpus
   HAS.
4. **« Aucun signalement » cite `CIS_CIP_Dispo_Spec.txt` sans date** : le
   fichier ne cite pas ce CIS, donc aucune date ne lui est propre. L'instant
   de l'index dit à quel état cela se rapporte. De même pour `CIS_bdpm.txt`
   dans une fiche partielle.

**Questions pour l'IeC**

1. L'addendum demande `upload-artifact` « épinglée par empreinte, comme les
   autres » : **aucune action de `ci.yml` ne l'est**. `checkout@v4` et
   `setup-uv@v6` sont épinglées par étiquette. J'ai mis
   `actions/upload-artifact@v4`, comme les autres : je ne peux pas relever
   une empreinte de commit sans réseau. Épingler les trois par empreinte
   (beko relève les SHA avec `gh api`) : dans cette mission, ou plus tard ?
2. Le healthcheck change la configuration du conteneur : au prochain `make
   up`, Compose **recrée** `pharmaflux-redpanda`. Le volume est gardé, donc
   rien n'est perdu. Je le signale pour que beko ne soit pas surpris.

**Propositions d'évolution** : l'ordre et le PRD v0.8 disent « PR #7 » pour
le run en échec : c'était le run de `main` (déjà noté par l'IeC).

**Pour le contrôle** : beko peut lancer les deux procédures de
[`infra/index/README.md`](../../../infra/index/README.md), puis me transmettre :
- les deux TOML affichés par `relever` ;
- la version, la date et l'empreinte de l'image Qdrant.

Le palier 2 commence par les mesures des deux modèles.
