# Mission 08 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Opus 5.5) · **À :** IeC, beko · **Date :** 30/10/2026
**Branche :** `mission-08-assistant-gouverne` (sommet `e13112a`, identique à
`main`) · **Ordre lu sur `main`** (`e13112a`), avec le PRD v0.9 (§1.6, §2.2,
§4 Lot 3, §6.7, §6.8, §7.4, §7.5, §9, annexe B).

**Ce que j'ai lu, et comment.** L'ordre et le PRD ci-dessus ; le `pr.md` et
les propositions de la mission 07 ; `evaluation/README.md` et
`questions-reference-v0.toml` ; le code de l'index
(`index/qdrant.py`, `index/construction.py`, `index/evaluation.py`,
`index/fragments.py`, `index/encodeur.py`, `index/modeles.py`) ; la structure
des commandes (`cli.py`) ; `pyproject.toml` ; `docs/agents/processus.md`.
J'ai consulté la documentation du SDK `anthropic` et de l'API Messages (hors
ligne, aucun appel) pour fixer la grille de prix, les sorties structurées,
l'effort, le cache et le traitement d'un refus.

**Mesures (aucun appel à l'API).**

- **Le rappel du dense seul** sur le jeu v0, par `index evaluer` contre
  l'index du Mac (collection `pharmaflux-f1-e5-small-int8-20261027T001712Z`,
  instant `2026-10-27T00:17:12Z`), sous `/usr/bin/time -l` :

  ```
  22 questions nomment un médicament
  bon CIS            @1 16/22  @5 20/22  @10 20/22
  bon CIS + section  @1 11/22  @5 17/22  @10 18/22   rang réciproque moyen 0.623
  score du premier   périmètre : médiane 0.905 ; hors périmètre et médicales : médiane 0.873, max 0.897
  5,53 s réel ; résident maximal 436 Mo
  ```

  Les deux seules questions dont le bon CIS n'est **pas** dans les dix
  premiers ont leur réponse dans `identite` : `disponibilite-005`
  (commercialisation d'une spécialité, CIS 68705771) et `avis_has-005`
  (CIS 67026956, hors `CIS_bdpm.txt`). Deux autres manquent la **section**
  sans manquer le CIS (`avis_has-003`, `historique-002`). C'est exactement ce
  que l'ordre annonce : le lexical doit rattraper les noms, les CIS et les
  codes, pas le sens.

- **La longueur des fragments**, lue hors ligne dans `data/index/fragments.jsonl`
  (`uv run python -I`) : 72 296 fragments, texte médian 331 caractères,
  moyen 372, p90 602, p99 1 098, max 1 200. À ≈ 3,8 caractères par jeton pour
  le français, un fragment pèse ≈ 98 jetons en moyenne (≈ 158 au p90). C'est
  la base de l'estimation de coût (G).

Aucune requête réseau, aucun appel à l'API, rien d'écrit dans le dépôt (hors
ce fichier), dans `data/` ni dans l'archive. **Aucun refus du garde-fou.**
**Rien n'a été codé.**

**Les constats qui pèsent sur l'ordre :**

1. **Le client Qdrant est déjà prêt pour le creux.** `qdrant.py` nomme son
   vecteur `dense` « pour qu'un vecteur creux s'ajoute à côté à la mission
   08 » et parle à l'API `/points/query`, qui sait fusionner (RRF) côté
   serveur. Rien à réécrire dans le transport.
2. **Le SDK `anthropic` n'est pas une dépendance** (`pyproject.toml`). Il
   s'ajoute au palier 2, avec la règle des deux semaines (ADR 0009).
3. **`count_tokens` est un appel à l'API** : la porte budgétaire repose sur
   une estimation locale *avant* l'appel, et le journal des dépenses sur
   `response.usage` *après* (exact, déjà payé). Aucun décompte payant au §0.
4. **Le score ne décide pas l'abstention.** Il est serré (0,905 contre 0,873,
   max 0,897) : l'abstention se décide sur une question structurelle — « a-t-on
   des fragments du bon CIS ? » — pas sur un seuil de cosinus.
5. **L'API refuse `temperature`/`top_p`/`top_k` depuis le 21/10/2026.** La
   rédaction du LLM n'est donc pas reproductible à l'octet : la notation
   compare la présence des valeurs et des citations, jamais le texte lettre
   à lettre ; le cache des réponses fige une rédaction par (question, index).

---

## A. La recherche lexicale et la fusion

### Constat

Mesure du dense seul ci-dessus. Le client Qdrant (`qdrant.py`) a été écrit au
palier 2 de la mission 07 avec un vecteur **nommé** `dense` précisément pour
accueillir un vecteur creux, et il appelle `POST /collections/{c}/points/query`,
qui accepte `prefetch` (plusieurs sous-requêtes) et `fusion`. Le nom de la
collection porte le format : `pharmaflux-f{FORMAT}-…` (`FORMAT = 1`
aujourd'hui, `index/fragments.py` et `index/construction.py`). `index verifier`
compare l'index à sa reconstruction, vecteur dense compris (cosinus ≥ 0,99).

### Avis

- **Le moyen : un vecteur creux BM25 dans Qdrant, l'IDF calculé par Qdrant.**
  À l'écriture, pour chaque fragment, je calcule les fréquences de termes
  depuis son `texte` (déjà déterministe) → un vecteur creux `(indices,
  valeurs)`. L'IDF, qui dépend du corpus entier, est laissé à Qdrant
  (`"modifier": "idf"` sur la configuration du vecteur creux) : un IDF tenu
  par nous changerait à chaque ajout ou retrait de fragment et casserait
  l'incrément et `verifier`. Une BM25 entièrement maison (index inversé et
  fréquences documentaires hors Qdrant) est **écartée** pour cette raison.
- **Le tokenizer lexical** (déterministe, testé sans réseau) : minuscules,
  dépliage des accents (NFKD), découpage sur les non-alphanumériques, mais
  **les suites de chiffres restent entières** — un CIS (8 chiffres) et un
  CIP13 (13 chiffres) sont un seul terme. Les dosages donnent les termes
  « 500 » et « mg » ; je normalise les graphies d'unité (`µg`, `mcg`,
  `microgramme(s)` → `ug` ; `mg`, `g`, `ml`…). C'est ce tokenizer, et lui
  seul, qui sert à l'écriture et à la requête.
- **La fusion : RRF côté serveur, en un appel.** `query` avec deux `prefetch`
  (dense exact, comme au palier 2 ; creux) puis `"query": {"fusion": "rrf"}`.
  Le dense reste **exact** (l'approché ne rendait que 82 % des dix premiers,
  mission 07). Le `k` du RRF (60 par défaut) et le nombre de candidats de
  chaque `prefetch` se règlent sur la mesure.
- **Ce que cela change à l'index : format 2, collection neuve, mais zéro
  réencodage.** Le vecteur creux s'ajoute à **chaque** point → la collection
  change de schéma → une reconstruction complète est de toute façon
  nécessaire. Mais le creux est une **fonction déterministe du texte**, qui
  ne change pas : les vecteurs **denses sont relus du cache** (`index etat` :
  « 0 repris » deviendrait « 72 296 repris »), donc pas les 18 minutes
  d'encodage. Je propose de **passer `FORMAT` à 2** : la collection porte un
  vecteur de plus, `verifier` doit apprendre à comparer le creux, et le bump
  force proprement la reconstruction unique dont on a besoin.
- **L'incrément et `verifier` suivent.** `mettre-a-jour` recalcule le creux
  des CIS touchés comme il recalcule leur texte (même déclencheur, même
  déterminisme). `verifier` ajoute la comparaison du vecteur creux **brut**
  (indices et valeurs égaux au recalcul) ; l'IDF étant tenu par Qdrant, il
  n'entre pas dans l'égalité fragment-à-fragment, et aucun score n'est
  comparé.
- **Mémoire et temps.** Le creux, c'est quelques dizaines d'entiers par
  fragment : négligeable en mémoire et en calcul devant l'encodage dense,
  aucun modèle de plus. La reconstruction réécrit 72 296 points avec un champ
  de plus, vecteurs denses relus du cache. À mesurer au palier 1, mais rien
  n'approche le seuil de 512 Mo de ce côté.
- **Mesure attendue.** Le dense seul est mesuré (ci-dessus). Je propose
  d'**étendre `index evaluer`** pour sortir, sur les mêmes questions, le
  rappel @1/5/10 du **dense seul**, du **creux seul** et de l'**hybride**,
  côte à côte. La cible est simple : l'hybride ≥ le dense sur `identite`, et
  jamais en dessous ailleurs.

### Questions

1. **`FORMAT` à 2** : d'accord pour bumper le format (collection neuve,
   reconstruction unique, cache dense réutilisé), ou préfères-tu garder
   format 1 et traiter le creux comme un artefact d'index hors du format des
   fragments ?
2. **IDF à Qdrant** plutôt qu'une BM25 maison : d'accord ? (Cela fixe que
   `verifier` compare la représentation creuse brute, pas un score.)
3. Le tokenizer lexical ci-dessus te convient-il, en particulier garder les
   CIS/CIP13 entiers et normaliser les unités de dosage ?

---

## B. Le chemin d'une question

### Constat

L'ordre fixe l'ordre des étapes et demande, pour chacune, ce qu'elle décide,
journalise et ce qui l'arrête ; et le sort d'un médicament introuvable ou de
deux médicaments. `index.construction.chercher(qdrant, encodeur, question, k)`
rend `(etat, resultats)` avec le score et la charge de chaque fragment.

### Avis

Le chemin, dans l'ordre :

1. **Normalisation de la question** : repérage d'un CIS (8 chiffres), d'un
   CIP13 (13 chiffres), d'un nom de spécialité. Décide : les entités visées.
   Journalise : la question normalisée et les entités.
2. **Règles de refus médical (hors LLM)** : un lexique et des motifs
   français (posologie, dose, « puis-je prendre / remplacer », « pour mon fils
   / ma fille / un patient », interactions, grossesse, effets). Décide :
   `refus_medical`. Arrête : **oui, sans appeler le LLM**. Journalise : le
   motif et le motif déclencheur.
3. **Règles d'abstention dures (hors LLM)** : une question de **dépense**
   (pas de couche sémantique avant le Lot 4) → abstention ; un sujet
   manifestement hors périmètre (tarif d'une complémentaire, conseil d'achat).
   Arrête : oui, sans LLM. Journalise : le motif.
4. **Recherche hybride** → k fragments (A). Décide : les fragments fournis.
   Journalise : les identifiants et les scores.
5. **Lecture du gold si nécessaire** : par défaut, **les fragments suffisent**
   (ils viennent du gold). Seule la catégorie `alternatives` peut réclamer la
   jointure groupe générique × présentations ; les fragments `identite` et
   `presentations` la portent déjà, mais je propose de confirmer par
   `gold alternatives` à cet instant si la question l'exige (voir question 2).
6. **Porte d'abstention structurelle** : si aucun fragment du bon CIS (ou de
   la bonne entité) n'est revenu → abstention « le référentiel ne répond pas
   à cette question ». Le score est un **signal secondaire**, pas un seuil.
7. **Appel au LLM** avec les fragments, l'instant de l'index, le prompt
   système (C).
8. **Contrôle de la réponse** (C) : citations ⊆ fragments fournis ; les
   nombres et dates du texte retrouvés dans les fragments cités. Un échec →
   **abstention**, jamais une réponse non vérifiée. Journalise : la décision
   et la cause.

Cas particuliers :

- **Médicament introuvable** : nom ou CIS sans aucun fragment du bon CIS →
  abstention motivée. Exception de l'annexe B (`avis_has-005`) : un CIS absent
  de `CIS_bdpm.txt` mais présent ailleurs (un avis) → **réponse avec réserve**
  (la donnée, sa source, sa date, **et** « le référentiel des spécialités ne
  connaît pas ce médicament »). Le fragment porte déjà `dans_referentiel`.
- **Deux médicaments** : je penche pour **une abstention motivée** en v1
  (« je traite une question sur un médicament à la fois ; précisez lequel »),
  plus sûr qu'une réponse partielle silencieuse. À trancher (question 3).

### Questions

1. La place du refus médical **tout en tête**, avant la recherche, te
   convient-elle ? (Une question médicale déguisée en disponibilité est alors
   refusée sans jamais toucher à l'index ni au LLM.)
2. **Lecture du gold** : s'en tenir aux fragments pour la mission 08, et ne
   lire le gold (`gold alternatives`) que pour la catégorie `alternatives`,
   ou tout tirer des fragments ?
3. **Deux médicaments** : abstention « un à la fois », ou réponse séparée pour
   chacun quand les deux sont trouvés ?

---

## C. Ce que le LLM reçoit et ce qu'il rend

### Constat

Chaque fragment (payload Qdrant, `index/fragments.py`) porte : `identifiant`,
`code_cis`, `section`, `partie`/`parties`, `denomination`, `dans_referentiel`,
`texte`, `empreinte_texte`, `sources` (`fichier`, `date_source`,
`observee_depuis`), `liens`. L'instant de l'index est tenu une fois dans
l'état et rendu par `chercher`. Le SDK `anthropic` offre les sorties
structurées (`output_config.format` + `messages.parse()`), le `stop_reason:
"refusal"` avec `stop_details.category`, et le cache de préfixe.

### Avis

- **Prompt système (français), stable donc caché** : le rôle (assistant de
  connaissance du médicament de l'assurance santé), les règles — ne rien
  ajouter aux faits, citer chaque phrase factuelle par l'identifiant d'un
  fragment fourni, s'abstenir si les fragments ne répondent pas, jamais de
  conseil médical, la prudence de l'ADR 0003 (« aucun signalement » ≠
  « disponible » ; un arrêt annoncé n'est pas un arrêt ; une fiche partielle
  se dit), dire l'instant de l'index et que l'assistant n'est pas un
  dispositif médical.
- **Fragments fournis** : 8 à 12 (à régler sur coût × rappel), dans l'ordre de
  la fusion (meilleur d'abord), chacun avec son `identifiant`, sa `section`,
  sa `denomination`, `dans_referentiel`, ses `sources` (fichier + date) et son
  `texte`. L'`empreinte_texte` et les vecteurs ne partent pas. L'instant de
  l'index est donné une fois, en tête.
- **Forme de la réponse : sortie structurée** (`output_config.format`, schéma
  JSON, `messages.parse()`) : `{ comportement: "reponse"|"abstention"|
  "refus_medical", texte, citations: [identifiants], motif, orientation? }`.
  Pas de prompt d'assistant préparé (retiré sur Opus 5.5).
- **Contrôle après l'appel** (par le code, pas par le LLM) :
  - chaque identifiant de `citations` est parmi les fragments fournis — sinon
    échec ;
  - les nombres (taux, prix) et les dates du `texte` se retrouvent dans le
    `texte` d'au moins un fragment cité (ou dans le gold lu en B5) — sinon
    échec ;
  - un échec **ne se corrige pas** : la réponse devient une abstention
    journalisée (« réponse non vérifiable »). On ne rend jamais une phrase
    factuelle sans appui.
- **Refus du modèle et erreurs de l'API** : `stop_reason: "refusal"` → traité
  comme une **abstention technique** journalisée avec `stop_details.category`,
  orientation générique (ce n'est pas le `refus_medical` métier). Les erreurs
  réseau/5xx/429 sont réessayées par le SDK ; une erreur 4xx ou une clé
  absente → échec net, journalisé, code de sortie non nul.

### Questions

1. Le schéma de sortie `{comportement, texte, citations, motif, orientation}`
   te convient-il, ou veux-tu y ajouter un champ (par exemple la liste des
   `code_cis` traités, ou un indicateur « réponse avec réserve ») ?
2. **8 à 12 fragments** : un ordre de grandeur acceptable, ou fixes-tu un
   nombre (il pèse sur le coût et sur le rappel) ?
3. Un **échec du contrôle** bascule en abstention : d'accord pour ne jamais
   tenter une seconde rédaction « corrigée » dans cette mission ?

---

## D. L'abstention et le refus médical

### Constat

§2.2 vise 100 % d'abstention hors périmètre/médical et 100 % de réponses
citant source + date. Le score est serré (A). L'annexe B donne les formes
attendues (motif, orientation, renvoi vers un professionnel).

### Avis

- **Règles hors LLM, testées sur fixtures (sans réseau)** :
  - **Refus médical** : lexique + motifs (ci-dessus, B2). Le cas déguisé
    « mon fils peut-il prendre le générique ? » bascule en refus dès la
    présence de « mon fils / pour un patient / puis-je » même si la question
    ressemble à de la disponibilité.
  - **Abstention** : dépense (toujours, avant Lot 4) ; hors périmètre
    (sujets absents des sources : mutuelle, tarifs, conseils d'achat).
  - **Zone grise de la disponibilité « pour moi »** (« dois-je m'inquiéter
    pour mon traitement ? ») : donner le **fait** (statut sourcé et daté) et
    **ne pas** conseiller ni rassurer — pas un refus médical, mais pas de
    conseil non plus.
- **Le rôle du score** : secondaire. L'abstention se décide d'abord sur
  « a-t-on des fragments du bon CIS/de la bonne section ? » (règle
  structurelle, B6). Un premier score très bas **et** aucun fragment du CIS
  visé **confortent** l'abstention ; le score seul ne la déclenche jamais
  (0,905 contre 0,873 ne sépare rien).
- **Forme** : abstention = motif + orientation concrète ; refus médical =
  motif + renvoi explicite vers un médecin ou un pharmacien + « je ne suis pas
  un dispositif médical ». Chaque décision est journalisée avec son motif et
  son déclencheur (règle ou LLM).

### Questions

1. La gestion de la **zone grise** (donner le fait, ne rien conseiller) te
   convient-elle, ou préfères-tu un refus franc dès qu'une question porte une
   implication personnelle ?
2. Veux-tu une **liste figée** des motifs lexicaux de refus médical dans un
   fichier versionné (relu à la relecture), ou dans le code avec ses tests ?

---

## E. Le jeu de questions v1

### Constat

v0 : 40 questions, 5 par catégorie, datées sur l'archive du 24/10. L'assistant
répond à l'**instant de l'index** (ici `2026-10-27T00:17:12Z`). L'annexe B
prévoit pour la v1 : `alternatives-004` retirée et remplacée (groupe
générique, nouvel identifiant) ; `avis_has-005` devient une réponse avec
réserve ; de nouvelles questions par catégorie avec des pièges ; objectif
cent au Lot 3, sans les questions sur le **texte** des avis HAS (mission 09).

### Avis

- **Ce que deviennent les questions v0** : gardées celles qui restent justes à
  l'instant de l'index ; `alternatives-004` retirée, remplacée sous un nouvel
  identifiant par une question sur le groupe générique ; `avis_has-005` passe
  d'`abstention` à **réponse avec réserve** ; les `depense` restent mais sont
  notées **abstention** pour l'assistant (`calculable_au = "lot4"`).
- **Nouvelles questions** : viser ≈ 100 au total sur les huit catégories
  (≈ 12-13 par catégorie), **sans** les questions sur le texte des avis HAS
  (mission 09). Les pièges : un nom proche d'un autre, un CIS hors référentiel,
  une question médicale déguisée en disponibilité (couvre B2/D), un dosage qui
  n'existe pas pour une spécialité donnée.
- **La date de référence** : la v1 date ses attendus à l'**instant de l'index
  du jeu de démo** (`2026-10-27T00:17:12Z`), puisque c'est l'instant auquel
  l'assistant répond et que la notation compare. Les attendus se vérifient
  **sans LLM**, des deux façons de l'annexe B qui doivent concorder : depuis le
  **gold** à cet instant (comme `questions verifier --entrepot`) et depuis le
  **bronze** (archive citée + sha256). La v0 cite l'archive du 24/10 : la v1
  citera l'archive que le silver a appliquée en dernier pour arriver à cet
  instant (voir question 1).
- **Le format** (ajouts au format v0, tout reste rejouable sans LLM) :
  `cis_attendu`, `section_attendue`, `doit_citer` (au moins une source avec sa
  date), `instant_cite` (doit apparaître), `mots_interdits` (par exemple
  « disponible » pour un `aucun_signalement`). Les `valeurs` brutes attendues
  restent le cœur de la vérification.

### Questions

1. **La date de la v1** : datée sur l'instant de l'index du jeu de démo
   (attendus recalculés), ou gardée au 24/10 comme la v0 ? Mon avis : l'instant
   de l'index, car l'assistant y répond.
2. **La cible** : ≈ 100 questions dès cette mission (hors avis HAS), ou un
   palier intermédiaire (par exemple 60-70) en laissant la mission 09 compléter ?
3. Les champs ajoutés au format (`doit_citer`, `instant_cite`,
   `mots_interdits`) te conviennent-ils ?

---

## F. La notation

### Constat

L'IeC penche pour une notation **entièrement déterministe** si elle suffit aux
indicateurs du §2.2. Les conditions de clôture « dures » : aucune citation
invalide, aucun conseil médical sur les questions `medical`.

### Avis

- **Noté sans LLM** : le comportement rendu == le comportement attendu ; les
  valeurs brutes attendues présentes dans le texte ; les citations valides
  (⊆ fournis, pointant le bon CIS/section) ; l'instant cité présent ; les mots
  interdits absents.
- **Juge LLM** : il coûterait un appel de plus par question (ordre de grandeur
  du coût de la réponse elle-même) et introduirait du non-déterminisme. La
  notation déterministe ci-dessus suffit aux indicateurs du §2.2 : **je suis
  d'accord pour ne pas de juge LLM dans cette mission.**
- **Indicateurs rendus** : réponses correctes (% et cible ≥ 85 %), réponses
  citant une source et sa date (% et cible 100 %), abstentions et refus justes
  (% et cible 100 %), **citations invalides** (doit être 0), **conseil médical
  sur `medical`** (doit être 0), coût par question et coût total de
  l'évaluation. `evaluer` les écrit « qu'ils atteignent leur cible ou non ».

### Questions

1. D'accord pour la notation **entièrement déterministe** (pas de juge LLM) ?
2. « Réponse correcte » = comportement attendu **et** toutes les valeurs
   brutes attendues présentes **et** au moins une citation valide ? (Je propose
   cette définition ; dis si tu veux la durcir ou l'assouplir.)

---

## G. Le modèle, l'effort et le coût

### Constat

Modèle par défaut **Claude Opus 5.5** (`claude-opus-5-5`) : 4,00 $/Mt en
entrée, 20,00 $/Mt en sortie, lecture de cache 0,20 $/Mt. Effort par défaut
`medium` sur ce modèle (pensée adaptative toujours active, non désactivable).
`count_tokens` est un appel à l'API. `response.usage` donne les jetons réels
(entrée, sortie, cache) sans coût supplémentaire.

### Avis

- **Estimation hors ligne d'une question** (sans appel) : entrée ≈ système
  (~1 000 jetons) + 10 fragments (~98 jetons de texte + ~40 de métadonnées
  chacun ≈ 1 400) + question (~100) ≈ **~2 500-3 000 jetons** ; sortie ≈ texte
  (~150) + structure, **plus la pensée adaptative** (incertaine, ~500-1 500 au
  `medium`) ≈ **~1 000 jetons**. Coût ≈ 3 000 × 4 $/Mt + 1 000 × 20 $/Mt ≈
  **0,032 $**, disons **0,03-0,05 $/question**. L'incertitude principale est
  le nombre de jetons de pensée.
- **Une évaluation complète** : ≈ 100 questions, dont une partie (dépense,
  hors périmètre, médical, abstentions structurelles) **n'appelle pas le LLM**
  (tranchée par les règles). Au pire ≈ 100 appels → **~3-5 $**. Sous 20 $ :
  **~4-6 évaluations complètes** non cachées, et **illimité** avec le cache
  des réponses (l'instant de l'index est stable).
- **Je ne propose pas d'autre modèle** : Opus 5.5 par défaut. Pour mémoire,
  Sonnet 5.5 (2 $/10 $) ou Haiku 5.5 (0,10 $/0,50 $) rédigeraient à moindre
  coût si le budget devenait tendu — ce qu'il n'est pas. Décision de beko.
- **`count_tokens`** : hors §0 (appel payant). Pour la suite, je **ne le
  propose pas** comme porte budgétaire : la porte repose sur une **estimation
  locale** (caractères × ratio) avant l'appel, et le journal sur
  `response.usage` après. Mesurer exactement coûterait un aller-retour par
  question pour un gain marginal sur une estimation déjà prudente.
- **Effort** : `low` à l'essai (moins de pensée, moins cher), remonté à
  `medium` si la qualité d'une rédaction factuelle courte en pâtit. Réglé au
  palier 2 sur les coûts réels.
- **Cache des prompts** : le système stable porte un `cache_control`
  ephemeral ; les fragments varient par question (peu cachables entre
  questions différentes, cachés sur une reprise de la même question). Gain
  modeste ; l'ordre de rendu `système → fragments → question` met le volatile
  après le point de cache.
- **Cache des réponses (le nôtre)** : clé = empreinte de (question normalisée,
  instant de l'index, format de sortie, modèle, empreinte du prompt système).
  Une question déjà posée sur le même index ne repaye pas — c'est ce qui rend
  les reprises d'évaluation gratuites.
- **Journal des dépenses** : hors git (`data/assistant/depenses.jsonl` ;
  `data/` est ignoré), une ligne par appel (horodatage, identifiant de
  question, modèle, jetons entrée/sortie/cache, coût calculé par la grille).
  `assistant depenses` lit le **total de la mission** et le **reste**. La
  porte : avant chaque appel, estimation locale ; si total + estimation
  > 20 $ → **refus**, rien n'est appelé, code de sortie non nul.
- **Plan de dépense** : palier 1 — **0 $** (aucun appel) ; palier 2 — ma
  démonstration de cinq questions (dont une abstention, un refus) et la mise au
  point de l'effort ≈ **1-2 $** ; palier 3 — une évaluation complète par beko
  ≈ **3-5 $**. Total attendu **~5-7 $**, bien sous 20 $.

### Questions

1. **Effort** : je démarre à `low` et remonte si besoin — d'accord, ou fixes-tu
   `medium` d'emblée ?
2. La **porte budgétaire par estimation locale** (plutôt que `count_tokens`)
   te convient-elle ?
3. L'emplacement du **journal des dépenses** (`data/assistant/depenses.jsonl`,
   hors git) et son contenu te conviennent-ils ?

---

## H. Les commandes

### Constat

Les commandes de l'index forment le groupe `index` (typer), avec `chercher`,
`evaluer`, `etat`… `make index` enchaîne après `make gold`. La CI n'appelle
pas l'API dans cette mission.

### Avis

- **Groupe `pharmaflux assistant`** :
  - `demander "<question>"` : sortie **texte** pour un humain (réponse,
    citations avec fichier + date, instant de l'index, coût) ; `--json` pour
    la sortie structurée brute ;
  - `evaluer [--questions evaluation/questions-reference-v1.toml] [--jsonl]` :
    **JSON Lines** par question pour la notation, puis les indicateurs (F) ;
  - `depenses` : le total de la mission et le reste.
- **Codes de sortie** : `0` pour un résultat obtenu (y compris une abstention
  ou un refus — ce sont des comportements attendus) ; `2` pour une erreur de
  configuration, une clé absente, un dépassement de budget ; pour `evaluer`,
  je propose un code **≠ 0 seulement sur une condition dure** (une citation
  invalide, un conseil médical sur `medical`), les cibles chiffrées étant
  rapportées sans bloquer (le PRD demande de les écrire « qu'elles atteignent
  leur cible ou non »).
- **Makefile** : une cible `make evaluer` qui, **après `make index`**, lance
  `assistant evaluer` sur la v1. Elle **ne va pas dans la CI** (appel API →
  mission 10). `make -n` de chaque cible nouvelle au palier 3.

### Questions

1. Le groupe `assistant` avec `demander` / `evaluer` / `depenses` est-il le
   bon découpage, ou veux-tu une commande de plus (par exemple `expliquer`
   pour dérouler le chemin d'une question) ?
2. **Code de sortie d'`evaluer`** : ≠ 0 seulement sur les conditions dures
   (citation invalide, conseil médical), ou aussi quand un indicateur passe
   sous sa cible ?
3. La cible `make evaluer` hors CI te convient-elle ?

---

## I. La mémoire et le temps

### Constat

`index evaluer` : **436 Mo, 5,5 s** pour 22 questions (mesuré ci-dessus).
`index chercher` : 446 Mo (mission 07). Le modèle e5 pèse l'essentiel. Le SDK
`anthropic` (httpx2 + pydantic) n'est pas encore installé.

### Avis

- `assistant demander` = `chercher` (modèle e5, ~446 Mo) + tokenizer lexical
  (négligeable) + SDK `anthropic` à l'import (quelques dizaines de Mo, à
  mesurer) + l'appel réseau (négligeable en mémoire). Estimation
  **~460-490 Mo**, à confirmer au palier 2. Si cela frôle 512 : l'encodage de
  la requête et l'appel LLM ne sont pas simultanés, on peut séquencer ; mais le
  modèle e5 reste chargé pour encoder la requête dense. Je ne sépare les
  processus **que si la mesure l'impose**.
- `assistant evaluer` sur ~100 questions : même résident (une question à la
  fois) ; la durée est dominée par la latence du LLM (plusieurs secondes par
  question avec la pensée) → **quelques minutes**, acceptable.

### Questions

1. Si la mesure du palier 2 montre `demander` au-dessus de 512 Mo, préfères-tu
   que je sépare l'encodage de la requête de l'appel LLM (deux processus),
   comme l'index sépare déjà l'encodage du calcul des fragments ?

---

## J. Autre

### Constat et avis

- **La clé de l'API** : le client zéro-argument du SDK la trouve où le SDK la
  cherche (l'environnement, ou un profil `ant auth login` de beko). Je ne la
  lis, ne l'affiche, ne l'écris ni ne la demande ; aucun `.env` n'est lu. Si
  elle manque, `assistant` le dit et s'arrête (code ≠ 0). **Rien à trancher**,
  c'est déjà dans l'ordre ; je le confirme.
- **Déterminisme** : l'API refuse `temperature`/`top_p`/`top_k` (21/10/2026) ;
  la rédaction n'est pas reproductible à l'octet. La notation ne compare donc
  **jamais** le texte à l'octet (valeurs et citations seulement), et le cache
  des réponses fige une rédaction par (question, index). À inscrire dans
  l'ADR 0012.
- **Dépendance `anthropic`** : à ajouter au palier 2 avec la règle des deux
  semaines (ADR 0009) et les plafonds du `uv.lock` (comme la mission 07 pour
  l'encodage). Je **propose** la dépendance ; le verrou exact (version et date
  de coupure) est le geste de beko.
- **La CI** : ne change que pour les tests sans API (double déterministe du
  client Claude, derrière la même interface). Aucun secret dans la CI.
- **Non-régression** : la v0 reste rejouable telle quelle ; la recherche
  hybride ne doit pas dégrader le rappel du dense (mesure dense | hybride).

### Questions

1. Y a-t-il un point que cet ordre n'a pas vu et que je devrais traiter au
   palier 1 plutôt que plus tard ?

---

## Propositions d'évolution (PRD, consignes) : aucune pour l'instant

Rien à faire évoluer avant l'addendum. Tout changement de code reste dans le
périmètre de la mission.
