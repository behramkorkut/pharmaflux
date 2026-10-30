# Mission 08 — palier 2 : l'assistant gouverné (décision 3)

Contrôle du palier 1 lu (`1d2c20d`) et addendum 2 lu sur `main`. **Aucun appel réel à l'API
ne part de ma session** : les tests passent tous par le double du client, et la démonstration
des cinq questions (décision 6) est préparée ici pour que **beko la lance** avec
`avec-cle.sh` (addendum 2). Les trois points du contrôle sont repris (voir plus bas).

## Fait

**Le paquet `pharmaflux.assistant`** : un chemin de question gouverné de bout en bout.

- **Le chemin** (`assistant/chemin.py`) suit l'ordre de l'addendum B : lecture de l'état de
  l'index (l'instant, le modèle), puis **refus médical** (tout en tête, hors LLM), puis
  **abstentions dures** (hors LLM), puis **repérage du médicament** et **deux médicaments**
  (abstention « un à la fois »), puis **recherche hybride**, puis **porte structurelle**
  (aucun fragment du médicament visé → abstention), puis le **LLM** (sous le plafond, caché),
  puis le **contrôle** du code. Chaque décision porte son `motif` et sa provenance (la trace
  de `--json`).
- **Les règles hors LLM** (`assistant/regles.py`), un lexique français testé sur la v1
  entière : le refus est réservé au **conseil** (puis-je/dois-je/faut-il + un geste de soin —
  prendre, arrêter, remplacer, doser, associer…) ou à une situation individuelle (grossesse,
  « dans mon cas »). « Mon traitement » qui ne demande aucune décision **n'est pas** un refus
  (la zone grise de D1). Les abstentions dures : dépense (Open Medic, au Lot 4), tarif d'une
  complémentaire, conseil d'achat, effets indésirables (notice et RCP, pas nos données).
- **Le repérage** (`assistant/repere.py`) : un CIS (8 chiffres) ou un CIP13 (13 chiffres)
  explicite, puis les dénominations de l'index dont le premier mot significatif paraît dans la
  question (un dictionnaire `mot → CIS` tiré une fois des fragments `identite`). « Deux
  médicaments » se mesure sur les deux premiers mots d'une dénomination, pour distinguer
  « SUNITINIB BIOGARAN » de « SUNITINIB ZENTIVA » (le piège disponibilite-009 vs -010).
- **Le client et son double** (`assistant/client.py`) : Opus 5.5, sortie structurée
  (`output_config.format`, schéma JSON), pensée adaptative, **effort `low`** au départ (G1),
  `max_tokens` 4 000. Un `stop_reason` `refusal` ou `max_tokens` devient une **abstention
  technique** journalisée avec sa cause. **Aucun modèle de repli.** `anthropic` n'est importé
  qu'à la construction du vrai client ; `cle_presente()` répond sans l'importer ni toucher le
  réseau.
- **Le contrôle** (`assistant/controle.py`) : les citations du LLM sont des **étiquettes**
  (1..k) vérifiées parmi les fragments fournis ; chaque **nombre** et chaque **date** du texte
  se retrouve, après normalisation (« 65 % »/« 65% », « 1 000 »/« 1000 », « 09/09/2026 »/« 9
  septembre 2026 »/« 2026-09-09 »/« 20260909 »), dans un fragment **cité** ou dans la question.
  Un échec devient une **abstention** (« réponse non vérifiable »), jamais une réponse non
  appuyée. **Les sources, leurs dates et l'instant de l'index sont rendus par le code**, pas
  par le LLM (addendum C).
- **Le budget** (`assistant/budget.py`) : grille Opus 5.5 (4 $ / 20 $ / 0,20 $ par million,
  datée et sourcée), plafond **20 $**. Avant chaque appel, une **estimation locale** (entrée
  au caractère + `max_tokens` entier en sortie), jamais `count_tokens` ; si le total déjà
  dépensé plus l'estimation dépasse le plafond, l'appel est **refusé** (rien n'est appelé). Le
  journal `data/assistant/depenses.jsonl` (hors git) garde une ligne par appel réel, avec son
  coût exact lu dans `response.usage`.
- **Le cache des réponses** (`assistant/cache.py`, `data/assistant/cache-reponses.sqlite`) :
  une question déjà posée sur le même index ne repaie pas (clé = empreinte du prompt système,
  du contenu, du modèle, de l'effort, de `max_tokens` et du schéma).
- **Les commandes** : `pharmaflux assistant demander "<question>"` (texte pour un humain, ou
  `--json` pour la trace) et `pharmaflux assistant depenses` (le total de la mission et le
  reste). Les tests injectent le double par `fabriquer_client_llm`.

## Les trois points du contrôle du palier 1

1. **`depense` en v1 → abstention.** Les dix questions `depense` de la v1 passent de
   `comportement = "reponse"` à `comportement = "abstention"`, en gardant `calculable_au =
   "lot4"`. Le parseur accepte ce couple **pour la v1 seulement** (la v0 ne change pas) ; deux
   tests le figent (test_questions). La contradiction « réponse attendue / l'assistant
   s'abstient » est levée.
2. **Le RRF est côté client**, et non par Qdrant comme l'addendum le disait (écart déclaré
   ici). La raison : la constante `k` est explicite dans le code, les ex æquo sont tranchés par
   identifiant (ordre reproductible), et le coût (deux requêtes au lieu d'une) est négligeable.
   **À écrire aussi dans l'ADR 0012** (décision 7, palier 3).
3. **La coupure du registre — piste keep-alive, examinée et bornée.**
   - **Côté client** (`bus/registre.py`, lu) : un `httpx.Client` **persistant** par client du
     registre, sans `limits` explicite, donc le `keepalive_expiry` par défaut d'httpx **0.28.1
     = 5,0 s** (confirmé) ; les connexions sont **mises en commun et réutilisées** d'un appel à
     l'autre ; un `RemoteProtocolError` est **réessayé** deux fois (et a servi chez l'IeC).
   - **Côté serveur** : la documentation de Redpanda **ne chiffre pas** le délai d'inactivité
     d'une connexion keep-alive du registre de schémas. Elle mentionne seulement l'ajout d'un
     TCP keepalive aux API HTTP en 25.3.2+ (sans valeur) et des délais de l'API **Kafka** (pas
     HTTP).
   - **Lecture** : le symptôme décrit par l'IeC — coupure sur le **premier** enregistrement
     d'un nouveau préfixe (après une pause), **sans** suppression de topic dans les secondes
     qui précèdent — est **cohérent** avec la réutilisation d'une connexion que Redpanda a
     fermée de son côté pendant que le client la croyait encore valable (dans les 5 s de son
     `keepalive_expiry`). C'est une **piste**, pas une preuve : le délai serveur reste inconnu
     et je ne peux pas le reproduire de façon déterministe hors d'un vrai Redpanda.
   - **Décision** : conformément au contrôle (« ne change le client que si la piste se confirme,
     avec un test ; sinon, dis-le, et on s'en tient à la règle actuelle »), **je ne change pas
     le client**. Le réessai existant recouvre déjà la coupure ; la règle de la mission 07
     (la session des tests d'intégration échoue s'il reste un réessai) reste en place. Piste à
     confirmer côté serveur (valeur du délai, ou reproduction) avant tout changement ; si elle
     se confirmait, un `keepalive_expiry` bas (voire la non-réutilisation) l'éteindrait sans
     risque, le volume d'appels du registre étant faible.

## La démonstration des cinq questions (décision 6, lancée par beko)

À lancer sur le Mac, index au format 2 construit (palier 1), par
`sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "<question>"`. Une abstention
et un refus sont compris ; trois réponses appellent le LLM (coût réel), deux décisions sont
prises hors LLM (coût nul).

1. `"LARIAM 250 mg, comprimé sécable est-il en rupture de stock ?"` — réponse, statut daté.
2. `"Quel est le taux de remboursement de DOLIPRANE 1000 mg, comprimé, boîte de 8 ?"` — réponse,
   un taux (contrôle des nombres).
3. `"Quel est le SMR du médicament de code CIS 67026956 ?"` — **réponse avec réserve** (CIS hors
   `CIS_bdpm.txt`), une date d'avis (contrôle « 20260909 » relié à une date rédigée).
4. `"Puis-je remplacer LARIAM 250 mg, en rupture, par un autre antipaludique pour mon voyage ?"`
   — **refus médical** (hors LLM, 0 $).
5. `"Quels sont les effets indésirables de DOLIPRANE 1000 mg, comprimé ?"` — **abstention** hors
   périmètre (hors LLM, 0 $).

**Sortie, coût réel et reste du plafond : à citer ici quand beko aura lancé les commandes** (et
l'effort remonté à `medium` seulement si le contrôle échoue ou si une réponse est incomplète,
G1). `pharmaflux assistant depenses` lit alors le total et le reste.

## Vérifications locales (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 281 fichiers déjà formatés |
| `uv run mypy src` | Success: no issues found in 68 source files (76 avec les ajouts) |
| `uv run pytest -q` (unité + intégration + modèle, Qdrant et modèle présents) | **649 passed** en 5 min 48 ; **0 réessai du registre sur 30 cycles** (la coupure ne s'est pas reproduite) |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK (21 tests) |
| `questions verifier` v1, `--racine demo/archive` | 88 : 55 conforme, 10 non calculable, 23 sans attendu |
| idem `--entrepot data/demo/lakehouse` | 55 depuis le gold : 55 concordent |
| `questions verifier` v0 (non-régression, + gold) | 25 depuis le gold : 25 concordent |
| chemin de l'assistant contre le **vrai index** (double, sans clé) | refus, abstention (règle), porte structurelle : **0 appel** ; « LARIAM … en rupture ? » : réponse, 1 citation (CIS 65999556, disponibilite, source datée), coût estimé 0,0160 $ |
| `pharmaflux assistant depenses` | mission 8 : 0 appel, 0 $, reste 20 $ (aucun appel réel de ma session) |

L'index n'a pas changé depuis le palier 1 (format 2) : la construction, `index verifier` et
`index evaluer` restent ceux du palier 1, non rejoués ici. Le test « clé absente » (addendum J)
passe dans la suite (code 2, sans réseau).

## Écarts à l'ordre

- **RRF côté client** et non côté serveur (point 2 ci-dessus), déclaré ; à porter dans
  l'ADR 0012 au palier 3.
- **`anthropic` et `uv.lock`** : la dépendance est ajoutée à `pyproject.toml`
  (`anthropic>=1.0,<2`), verrouillée **au 16/10/2026** (`uv lock --exclude-newer`), avec les
  plafonds `anthropic<=1.15.0`, `jiter<=0.17.0`, `opentelemetry-api<=1.45.1` ; le `uv.lock` ne
  touche **aucun** paquet déjà verrouillé (seuls `anthropic` et ses transitifs nouveaux —
  `jiter`, `sniffio`, `docstring-parser`, `opentelemetry-api` — sont ajoutés). beko installe et
  pousse.
- **`avec-cle.sh`** (réservé à l'IeC) n'existe pas encore dans le dépôt : la démonstration en
  dépend. Le code trouve la clé où le SDK la cherche (`ANTHROPIC_API_KEY`) ; sans elle,
  l'assistant s'arrête avec « clé absente » (code 2), sans réseau — testé.
- **`assistant evaluer` et la notation** restent au palier 3 (décision 4) ; le palier 2 livre
  `demander` et `depenses`.

## Questions pour l'IeC

- La piste keep-alive (point 3) : d'accord pour la laisser **non corrigée** et s'en tenir à la
  règle actuelle, faute de pouvoir confirmer le délai côté serveur hors d'un vrai Redpanda ?
- Le choix des cinq questions de la démonstration te convient-il (une abstention et un refus
  compris) ?

## Propositions d'évolution (PRD, consignes)

Aucune.
