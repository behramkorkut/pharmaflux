# Mission 09 — relecture 1
**Commit relu** : `4eaea81` (sommet de `mission-09-corpus-des-avis-has`)
**Verdict** : CONFORME

Relecteur : Claude Fable 5.1, session neuve, le 31/10/2026, dans `pharmaflux-relecteur/`
sur le sommet détaché. Relu contre l'ordre de mission et son addendum 1 (`main`, `a7df8ef`),
les deux décisions sur la question 2, les quatre contrôles de palier, les douze rapports du
codeur et le code des 19 commits (`5cb8f9d` à `4eaea81`).

**Ce qui tient.** Chaque décision de l'ordre et de l'addendum est dans le code et éprouvée par
un test : la politesse du client (pause tenue avant toute requête, réessai compris ; aucune
redirection suivie ; plafond vérifié avant l'envoi ; arrêt au premier 429 ou à la seconde
défaillance d'affilée ; `Crawl-delay` qui n'allonge que), `robots.txt` et les mentions légales à
chaque passage, l'archive à l'octet et le manifeste en ajout seul avec l'empreinte du texte, la
reprise sans requête, l'extraction déterministe à douze rejets motivés et son second lecteur
sans code commun, l'index au format 4 à deux horloges, le LLM qui ne voit aucune adresse et le
code qui rend la page avec ses trois dates, le refus de la posologie par les règles, la v1
reprise à l'identique dans la v2, les questions neuves figées par une empreinte **avant** chaque
retouche (ordre des commits vérifié : `bbb9809` < `ee2f0a6`, `c80b795` < `5bbf3a8`,
`34dca25` < `aba5173`, et aucun commit de retouche ne touche au fichier des questions), la
constante 1,7, le budget (3,82 $ sur 10 $, tout parti le 31/10). Les écarts sont tous déclarés
dans les rapports et acceptés par l'IeC (un lien de document suivi au lieu de trois ; 19
questions sur le texte au lieu d'environ 24 ; quatre précisions du palier 1 ; le palier 4 ouvert
par l'IeC). Les douze requêtes du §0 sont les seules parties d'une session d'agent : le journal
en compte douze, toutes vers `www.has-sante.fr`, et le script refuse la treizième.

## Bloquants

Aucun.

## À corriger (non bloquants)

1. `README.md:65`, `README.md:418-421`, `evaluation/README.md:215`, `evaluation/README.md:220`,
   `docs/CONTEXTE.md:477`, `evaluation/questions-reference-v2.toml:59` (`description`) — les
   chiffres de la v2 sont ceux d'**avant le palier 4** : « 138 questions, dont 50 nouvelles »,
   « 84 réponses correctes sur 87 », « la page d'avis rendue sous les 22 réponses », « 2,09 $ ».
   La v2 livrée compte 144 questions (56 nouvelles), et l'évaluation finale (`cf04a7e`) donne
   88/91, 26/26 liens rendus, 3,82 $ de dépense pour la mission. — Le `README` est la première
   page qu'un recruteur lit, et il contredit `pr.md` ; la `description` du jeu v2 se charge et
   s'affiche. — Attendu : les quatre fichiers aux chiffres de `pr.md` (144, 56, 88/91, 26/26 ;
   la dépense totale, en disant que la relance après le palier 4 en est 1,62 $), et une ligne
   dans le `README` sur la limite des pages sans fiche du référentiel (121 sur 721), qui est
   le fait saillant du palier 4.

2. `docs/journal.md:835` — l'entrée s'intitule « Mission 09, paliers 1 à 3 » et s'arrête au
   palier 3 : ni la décision de l'IeC sur la question 2, ni le format 4 (16,8 % des pages de la
   première étape hors de l'index), ni les deux évaluations ne sont au journal. — L'ordre
   (décision 8) demande le journal en fin de fichier, et c'est la décision la plus lourde de la
   mission pour qui lira l'historique du projet. — Attendu : une entrée pour le palier 4 et
   l'évaluation finale (commits `9694be7` à `cf04a7e`), et l'en-tête corrigé.

3. `docs/adr/0013-corpus-has-collecte-extraction-fragments-liens.md:3` (« Date : 2026-11-01 »),
   `docs/donnees/has.pages_avis.md:9` (« le 01/11/2026 »), `docs/journal.md:835` (« 31/10 et
   01/11 ») — les 19 commits de la branche sont tous du 31/10/2026 (heure de Paris, le dernier à
   22:59), comme l'ordre, la collecte, la démonstration et les évaluations. — Une ADR datée du
   lendemain de son commit, et un profil « lu le 01/11 » dans un dépôt qui s'arrête au 31/10,
   c'est une incohérence qu'un lecteur attentif relève. — Attendu : 2026-10-31 aux trois
   endroits. Dans le même fichier, `0013:15-19` (« Mesures de la mission ») et `0013:87`
   donnent les chiffres du **format 3** (1 543 et 6 165 fragments d'avis ; 493 et 496 Mo) sans
   le dire, alors que l'index livré est au format 4 (1 255 et 5 054 ; 425 et 444 Mo sur la
   première étape, et jusqu'à 502 Mo pour `index verifier` sur le jeu chez beko) : à dater
   par le format, ou à mettre aux chiffres livrés.

4. `src/pharmaflux/index/fragments.py:394` (`couper_ligne`) et `:417` (`_decouper_avis`) —
   aucun test direct de la propriété que la docstring et l'ADR 0013 affirment : « les morceaux
   rejoints par une espace redonnent la ligne », chaque morceau sous la limite, la coupe après
   une fin de phrase quand il y en a une. `test_le_texte_de_la_page_mot_pour_mot` ne la
   couvre pas (KALYDECO n'a aucune ligne coupée) et `test_aucun_fragment_avis_has_du_jeu_ne_depasse_la_fenetre`
   ne mesure que la longueur. — C'est la preuve de non-altération au niveau de l'index, celle
   que la licence de la HAS exige ; aujourd'hui elle ne repose que sur une lecture du code. Je
   l'ai vérifiée moi-même sur les 150 pages du jeu (ligne la plus longue 1 781 caractères ;
   545 découpes à trois limites, 0 qui ne redonne pas la ligne). — Attendu : un test de
   quelques lignes, sur la ligne de 1 781 caractères de `p_3700800` ou sur une ligne fabriquée
   (coupe après « . », coupe à une espace quand il n'y a pas de fin de phrase, un mot plus long
   que la limite laissé entier).

5. `src/pharmaflux/has/client.py:128-129` — la branche « après une défaillance » est
   inatteignable : `_defaillance_precedente` est remis à faux à la fin de tout `demander` qui
   rend une réponse, et quand il reste à vrai c'est qu'un `ArretNet` ou un `PlafondAtteint` a
   été levé, ce qui arrête le passage. La docstring du module (`client.py:13`, « sur la même URL
   ou sur la suivante ») et le §0 (C) décrivent donc un comportement que le code n'a pas : une
   défaillance isolée sur une URL, réessayée avec succès, puis une défaillance sur la suivante
   donne un second réessai, pas un arrêt. Le comportement réel (deux défaillances d'affilée
   sur la même URL) est poli et accepté par l'IeC (C1) ; c'est la lettre qui ne colle pas. —
   Attendu : supprimer la branche morte et écrire la règle réelle dans la docstring, ou tenir le
   drapeau d'une URL à la suivante si c'est ce que l'on veut ; dans les deux cas un test.

## Remarques

- `src/pharmaflux/has/collecte.py:332-336` — une page de mentions légales reçue en 200 mais sans
  `<main>` est consignée avec le statut `nouveau`, une `erreur` « HTTP 200 » et aucune archive :
  partout ailleurs `nouveau` veut dire « archivée ». Le cas est déclaré au palier 1 et ne s'est
  pas présenté ; un statut à lui (ou `type_inattendu`) rendrait le manifeste plus lisible.
- `src/pharmaflux/index/pages_has.py:159-167` — le contrôle de dossier de l'état porte sur tous
  les dossiers qui lient la page, les fragments le refont fiche par fiche : une page liée par
  deux dossiers dont un seul est nommé par le document serait comptée « rejetée » dans l'état
  tout en donnant des fragments à la fiche nommée. Aucune des 722 pages de la première étape
  n'a plus d'un dossier BDPM ; à garder en tête quand le corpus s'étendra, le commentaire le
  dit déjà.
- Historique : plus d'un commit par palier, mais c'est l'ordre qui le demande (les questions
  figées dans un commit qui précède la retouche, les sorties de beko dans un commit à part) ;
  les 19 messages sont en français et portent les deux trailers.
- `evaluation/questions-reference-v2.toml` : le commentaire d'en-tête (point 3) ne liste pas
  `avis_has-051` à `-056`, qui n'ont que le commentaire de leur bloc (ligne 2357). À reprendre
  avec le point 1.
- `evaluation/README.md:245` dit « deux blocs » quand l'addendum dit trois : c'est cohérent
  avec la CLI (la v1 se note par son fichier), mais une demi-phrase de plus l'expliquerait.
- Les deux limites du rendu des liens (le même lien rendu trois fois sous la réponse KALYDECO ;
  les liens d'un fragment cité non filtrés par le dossier de la question, `avis_has-044`) sont
  écrites dans l'ADR 0013 et dans `pr.md`, avec une proposition : rien à corriger ici.
- `ruff format --check` compte 341 fichiers chez moi contre 340 dans `pr.md` : sans importance.
- Lisibilité : noms, commentaires et docstrings en français, identifiants sans accents, pas de
  dépendance nouvelle (`pyproject.toml` et `uv.lock` inchangés), les scripts de tirage
  (`evaluation/choisir_*.py`) disent leur règle en tête et un test vérifie qu'aucun test ne les
  importe. Les tests éprouvent des comportements sur des pages réelles, avec des valeurs
  attendues fixées (empreintes, sha256, dates) : je n'ai trouvé aucun test qui ne puisse pas
  échouer.

## Vérifications relancées

Dans `pharmaflux-relecteur/`, arbre propre sur `4eaea81` ; Redpanda, Qdrant et les fichiers du
modèle présents sur le Mac. L'archive du Mac (`~/pharmaflux-data`) et le journal des dépenses
du codeur ont été **lus**, jamais écrits.

| commande | résultat |
|---|---|
| `uv run ruff check .` ; `uv run ruff format --check .` | All checks passed ; 341 files already formatted |
| `uv run mypy src` | Success: no issues found in 89 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **913 passed** en 6 min 44, aucun saut, code 0 (intégration et modèle compris) |
| aucune requête réseau dans les tests | `tests/conftest.py::reseau_coupe` (portée session, automatique : résolution et connexion refusées hors de la machine) et `tests/test_reseau.py` (httpx, urllib, une adresse IP, `ClientHas` sans transport simulé) ; la suite entière passe sous cette garde |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK (24 tests) |
| `make -n index` ; `make -n evaluer` (avec et sans `JEU_QUESTIONS`) ; `make -n demo` | les commandes attendues ; `index` passe `--archive-has demo/archive` aux trois sous-commandes |
| `uv run pharmaflux demo verifier` | conforme : la BDPM et 150 pages d'avis, 150 lignes de manifeste, 2 574 863 octets compressés |
| `has extraire --verifier --page …` (les 11 pages HTML des fixtures) | 10 extraites, 1 rejetée (`jsonld_absent` : la page de mesure d'audience) ; 10 conformes, 0 écart, 0 divergence |
| `has extraire --verifier --racine ~/pharmaflux-data` (lecture) | 722 pages : 721 extraites, 1 rejetée (`dossier_incoherent`) ; 721 conformes, 0 écart, 0 divergence ; 714 empreintes égales au manifeste, 7 statuts changés (rejetée → extraite 7, extraite → rejetée 0) ; 10 contrôles de dossier impossibles ; code 0. Ce que `correction-extracteur-v2.md` et `pr.md` annoncent |
| `has collecter --simuler --racine ~/pharmaflux-data` | 746 dossiers, 720 avec un lien, 722 pages ; **722 déjà archivées**, 0 orpheline, 0 en erreur ; 2 requêtes seulement seraient envoyées (`robots.txt`, mentions) ; aucune requête n'est partie, le manifeste du Mac compte toujours 724 lignes |
| `uv run pharmaflux index etat` (le Qdrant du Mac) | format 4 ; 21 445 fiches, 73 551 fragments dont 1 255 `avis_has` ; pages collectées jusqu'au 2026-10-31T13:07:40Z, manifeste lu jusqu'à la ligne 150, extracteur v2 ; 149 extraites, 1 rejet ; 5 contrôles impossibles ; 18 pages sans fiche du référentiel, listées |
| `questions verifier --racine demo/archive` sur la v2 ; sur la v1 | 144 : 91 conformes (dont les 24 pages d'avis, vérifiées sans gold), 10 non calculables, 43 sans attendu ; 88 : 50 conformes, 10 non calculables, 28 sans attendu |
| `profil --racine ~/pharmaflux-data` | 11 fichiers profilés, 0 anomalie bloquante |
| `questions verifier --racine ~/pharmaflux-data` (v0) | 40 : 25 conformes, 5 non calculables, 10 sans attendu |
| journal des dépenses du codeur (`data/assistant/depenses.jsonl`, lu, résumé par mission) | mission 9 : **190 appels, 3,8244 $**, tous du 2026-10-31 ; mission 8 : 65 appels, 1,0309 $. Les chiffres de `pr.md` |
| la découpe des lignes longues (contrôle hors dépôt, pages du jeu) | 150 pages ; ligne la plus longue 1 781 caractères ; 545 découpes à trois limites, **0** qui ne redonne pas la ligne ; morceau le plus long 890 caractères |
| `git diff --stat main...HEAD` ; `git diff --name-only` | 261 fichiers ; aucun chemin réservé à l'IeC, rien de `data/`, aucun secret (la valeur de `JSESSIONID` est `<retiré>` dans les 11 `.headers`), `pyproject.toml` et `uv.lock` inchangés ; le socle (`silver/`, `gold/`, `evenements/`, `bus/`, `contrats/`) intact, seul `collecte/manifeste.py` est factorisé |
| trailers et messages des 19 commits | `Commis-par: codeur` et `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` sur chacun ; français |

**Non rejoué ici** : `index verifier`, `silver verifier`, `gold qualite`, `evenements` contre
`beba0c8` et `assistant evaluer --estimer`, qui demandent le silver et le gold du jeu
(`data/demo/lakehouse`), absents de mon dossier et que je ne reconstruis pas (`make` m'est
fermé hors `-n`, et `demo rejouer` écrirait dans le bus partagé). L'IeC les a rejoués dans le
dossier du codeur à chaque palier (`controle-palier-4.md` : 913 tests, `index etat`, `questions
verifier` 91/10/43, `--estimer`), et `pr.md` cite la séquence de beko (`index verifier`
conforme, cosinus minimal 0,9955). Le code de l'index, lu, est couvert par
`tests/test_index_has.py` (mise à jour égale à la reconstruction, position exigée, fiche qui
entre au référentiel) et par les tests `modele` (les 1 255 fragments d'avis du jeu sous 512
jetons), tous passés ici.

## Alertes

Aucune : aucune consigne adressée au relecteur dans le code, les rapports, les fixtures ou les
pages archivées.
