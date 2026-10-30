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
  `max_tokens` 4 000. Un refus du modèle, une réponse tronquée (`max_tokens`) **ou une sortie
  illisible** (bloc texte absent, JSON invalide, clé manquante) deviennent une **abstention
  technique avec son `usage`** : l'appel payé est toujours journalisé, jamais perdu par une
  exception avant le décompte (`interpreter_reponse`, correctif du palier 2). **Aucun modèle de
  repli.** `anthropic` n'est importé qu'à la construction du vrai client ; `cle_presente()`
  répond sans l'importer ni toucher le réseau.
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
  du contenu, du modèle, de l'effort, de `max_tokens` et du schéma). Une **abstention technique
  n'y entre pas** (une reprise retente l'appel) ; son coût reste journalisé (correctif du
  palier 2).
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

À lancer sur le Mac, index au format 2 construit (palier 1), **depuis ce dossier** avec le
script de `main` : `sh ../pharmaflux/infra/agents/avec-cle.sh uv run pharmaflux assistant
demander "<question>"`. Une abstention et un refus sont compris ; trois réponses appellent le
LLM (coût réel), deux décisions sont prises hors LLM (coût nul).

1. `"LARIAM 250 mg, comprimé sécable est-il en rupture de stock ?"` — réponse, statut daté.
2. `"Quel est le taux de remboursement de DOLIPRANE 1000 mg, comprimé, boîte de 8 ?"` — réponse,
   un taux (contrôle des nombres).
3. `"Quel est le SMR du médicament de code CIS 67026956 ?"` — **réponse avec réserve** (CIS hors
   `CIS_bdpm.txt`) ; visait aussi le contrôle de date (« 20260909 » relié à une forme rédigée),
   mais le modèle n'a écrit aucune date (voir ci-dessous).
4. `"Puis-je remplacer LARIAM 250 mg, en rupture, par un autre antipaludique pour mon voyage ?"`
   — **refus médical** (hors LLM, 0 $).
5. `"Quels sont les effets indésirables de DOLIPRANE 1000 mg, comprimé ?"` — **abstention** hors
   périmètre (hors LLM, 0 $).

**Sortie de beko** (recopiée) : 3 appels réels, **0,0432 $** au total, reste **19,9568 $**
(`assistant depenses` : « mission 8 : 3 appel(s), 0.0432 $ ; reste 19.9568 $ »). Instant de
l'index affiché : `2026-10-27T00:17:12Z`.

1. **Abstention**, coût **0,0183 $**. Motif : « le nombre « 13340 » du texte n'est dans aucun
   fragment cité ni la question ». **C'était un faux positif du contrôle** (A, ci-dessous),
   corrigé sur ce commit ; la réponse du modèle, elle, était juste.
2. **Réponse**, coût **0,0126 $**. Taux 65 %, prix public 2,18 €, CIP 3400935955838, et une
   phrase sur la boîte de 100 sans taux ni prix ; cite [2] (CIS 60234100, presentations,
   `CIS_CIP_bdpm.txt` source du 2026-10-23).
3. **Réponse avec réserve**, coût **0,0122 $**. SMR « Important », avis CT-21978, ASMR V ; cite
   [1] (avis) et [3] (identite, `CIS_bdpm.txt` source non datée, voir B). **Aucune date n'est
   écrite en clair** : le cas « 20260909 » (relier une date rédigée à la forme brute) reste
   couvert par les seuls tests.
4. **Refus médical** (« remplacer »), **0 $**, hors LLM.
5. **Abstention** (effets indésirables), **0 $**, hors LLM.

L'effort reste à **`low`** : le seul contrôle en échec était un faux positif du normaliseur, non
une réponse incomplète ou fausse du modèle (G1).

### A. Le « 13340 » de la question 1 : faux positif du normaliseur, corrigé

Relu **sans aucun appel** : la réponse du modèle est dans `data/assistant/cache-reponses.sqlite`
(l'abstention venait du contrôle, pas d'une erreur technique, donc elle a été mise en cache). Le
texte finit par « … une plaquette de 8 comprimés (CIP13 3400933961688) ». Le normaliseur des
nombres (`controle._NOMBRE`) collait le « 13 » du **label** « CIP13 » à l'espace puis aux
premiers chiffres du CIP (« 340… ») et lisait un faux « 13 340 » → `13340`, en coupant le CIP en
« 933961688 ». **Cas (c) : un faux positif.** Correctif (ce commit) : des **frontières de mot**
(`\b`) dans `_NOMBRE`, pour qu'un nombre ne commence pas au milieu d'un code alphanumérique
(« CIP13 », « P01BC02 »). Vérifié sans appel : la recherche rejoue les dix mêmes fragments, et la
réponse du modèle **passe** alors le contrôle (ses nombres — CIS 65999556, CIP 3400933961688,
250, 8 — et ses dates sont tous dans les fragments cités [1] disponibilite et [2] presentations).
Un test de régression fige le cas.

### B. La source « CIS_bdpm.txt (source non datée) » de la question 3 : voulu

Le fragment `identite` d'un CIS absent de `CIS_bdpm.txt` (ici 67026956) est une **fiche
partielle** : `fragments._sources` ajoute `CIS_bdpm.txt` sans date pour **attester l'absence** du
référentiel (la réserve de la réponse), à côté des fichiers qui, eux, citent le CIS (les avis,
datés). C'est **voulu**, pas un défaut de `citer` : il n'y a pas de date pour une absence.

### C. Les jetons de cache : non nuls

Lus dans `depenses.jsonl` : le premier appel **écrit 923 jetons de cache** (`cache_creation`),
les deux suivants en **lisent 923** (`cache_read`). Le cache du prompt système **est donc
effectif** — contrairement à l'attente de la remarque 1 du contrôle (préfixe sous le minimum) :
le préfixe stable atteint le minimum et se met en cache. Le gain reste modeste (923 jetons à
0,20 $/million).

## Correctif (contrôle du palier 2)

Deux corrections avant la démonstration, sur le commit de ce rapport :

1. **Un appel payé entre toujours au journal.** `interpreter_reponse` traduit la réponse du
   SDK : une sortie illisible (bloc texte absent, JSON invalide, clé manquante) devient une
   abstention technique **avec son `usage`**, comme un `refusal` ou un `max_tokens`, au lieu de
   laisser une exception sortir avant `journal.ajouter` — la porte du plafond ne sous-estime
   donc plus la suite. Testé par un faux objet de réponse (bloc absent, JSON invalide, clé
   manquante).
2. **Une abstention technique n'entre pas au cache.** Son coût reste journalisé, mais une
   reprise d'évaluation **retente** l'appel au lieu de figer l'échec. Testé : deux questions
   identiques en abstention technique donnent deux appels et deux lignes au journal.

## Vérifications locales (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 281 fichiers déjà formatés |
| `uv run mypy src` | Success: no issues found in 68 source files (76 avec les ajouts) |
| `GITHUB_ACTIONS=true uv run pytest -q -rE` (unité + intégration + modèle, Qdrant et modèle présents) | **656 passed** (~5 min 45), session verte ; **0 réessai du registre** (sur 30 cycles ; la coupure ne s'est pas reproduite) |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK (21 tests) |
| `questions verifier` v1, `--racine demo/archive` | 88 : 55 conforme, 10 non calculable, 23 sans attendu |
| idem `--entrepot data/demo/lakehouse` | 55 depuis le gold : 55 concordent |
| `questions verifier` v0 (non-régression, + gold) | 25 depuis le gold : 25 concordent |
| chemin de l'assistant contre le **vrai index** (double, sans clé) | refus, abstention (règle), porte structurelle : **0 appel** ; « LARIAM … en rupture ? » : réponse, 1 citation (CIS 65999556, disponibilite, source datée), coût estimé 0,0160 $ |
| diagnostic de la démo, **sans appel** (A) : Q1 relue du cache, recherche rejouée | avec `_NOMBRE` corrigé, la réponse Q1 **passe** le contrôle ; le faux « 13340 » est levé |
| `pharmaflux assistant depenses` (après la démo de beko) | mission 8 : 3 appel(s), 0,0432 $, reste 19,9568 $ |

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
- **`avec-cle.sh`** existe sur `main` (`27b0440`) ; cette branche part d'avant, et le code de
  l'assistant n'est que sur elle, donc beko lance la démonstration **depuis ce dossier** avec le
  script de `main` (`sh ../pharmaflux/infra/agents/avec-cle.sh …`). Le code trouve la clé où le
  SDK la cherche (`ANTHROPIC_API_KEY`) ; sans elle, l'assistant s'arrête avec « clé absente »
  (code 2), sans réseau — testé.
- **`assistant evaluer` et la notation** restent au palier 3 (décision 4) ; le palier 2 livre
  `demander` et `depenses`.

## Questions pour l'IeC — tranchées au contrôle du palier 2

- Piste keep-alive : **d'accord pour ne pas corriger le client** (`controle-palier-2.md`) ; la
  règle de la mission 07 reste en place. Un deuxième cas daté en CI rouvrirait la discussion.
- Les cinq questions de la démonstration : **acceptées** (trois appels réels, un refus et une
  abstention hors LLM).

## Propositions d'évolution (PRD, consignes)

Aucune.
