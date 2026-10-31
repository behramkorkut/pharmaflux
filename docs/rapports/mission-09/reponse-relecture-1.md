# Mission 09 — réponse à la relecture 1

La relecture 1 (Claude Fable 5.1, sur `4eaea81`) est **CONFORME, avec 0 bloquant**. L'IeC a
tranché ses cinq points non bloquants : quatre sont corrigés, et le cinquième est écrit comme
piste, sans toucher au client. Aucun appel payant n'a été fait. Le fichier de la relecture est
committé tel quel, avec cette réponse.

Il y a trois commits :
- **`1c88fe7`** porte les points 1 à 3. Il ne touche que les docs et le jeu v2 (son en-tête et
  sa description), sans changer aucune question.
- **`881300b`** porte le point 4 : un test direct, sans toucher au code.
- **Le commit de cette réponse** porte le point 5 (dans `pr.md`), le fichier de la relecture et
  `pr.md` mis à jour.

Il n'y a pas de second tour de relecture. Le verdict est CONFORME, et l'IeC vérifiera ces
corrections à la revue finale.

## À corriger

1. **Les chiffres d'avant le palier 4** : corrigés (`1c88fe7`), aux chiffres de `pr.md`.
   - `README.md` passe à 144 questions dont 56 nouvelles, 88/91, la page rendue sous les 26
     réponses qui l'attendent, et 3,82 $ en tout, dont 1,62 $ pour la relance de la v1 et de la
     v2 après le palier 4. Une phrase ajoute la limite du palier 4 : 121 pages sur 721
     (16,8 %) restent dans l'archive, mais hors de l'index.
   - `evaluation/README.md` passe à 144 et 56, et ajoute les six questions du rattachement. La
     porte budgétaire de 105 appels est datée du palier 3. Une demi-phrase dit pourquoi la v2
     rend deux blocs : la v1 se note par son propre fichier, et c'est le troisième bloc.
   - `docs/CONTEXTE.md` passe à 144 questions, avec l'évaluation finale (88/91, 26/26, 3,82 $).
   - La `description` de `questions-reference-v2.toml` passe à 56 et 144. Son en-tête liste
     `avis_has-051` à `-056` (la remarque du relecteur).
     - **Les empreintes ne bougent pas** : `tests/test_questions_v2.py` est vert, avec 6 tests,
       dont les empreintes des 18, des 5 et des 6.
     - **La clé du cache ne bouge pas** : `assistant evaluer --estimer` sur la v2 donne « 144
       questions, 33 décidées hors LLM, 111 en cache, **0 appel(s) à faire** ».

   La règle de l'IeC est appliquée : un chiffre d'avant ne reste que s'il est présenté comme
   tel (palier 3, format 3). L'entrée du journal « paliers 1 à 3 », qui donne 138 questions au
   palier 3, reste donc exacte pour sa date.

   La docstring d'un test du modèle (`test_encodeur_modele.py`) donnait aussi le compte du
   format 3 (1 543 fragments d'avis). Elle passe à 1 255, en `881300b`.
2. **Le journal** : corrigé (`1c88fe7`). Une entrée est ajoutée en fin de fichier : « Mission
   09, les évaluations et le palier 4 ». Elle couvre :
   - la première évaluation ;
   - la démonstration et la question 2 ;
   - la décision de l'IeC (voie C) ;
   - les commits `9694be7` à `a1ae12a` ;
   - l'évaluation finale (`cf04a7e`) : aucune question perdue, 6/6 sur le rattachement, 88/91,
     26/26, la réponse MOUNJARO limitée à l'avis Diabète, 3,82 $ en 190 appels, et `index
     verifier` à 502 Mo.

   La date de l'en-tête des paliers 1 à 3 est corrigée au point 3.
3. **Les dates** : corrigées (`1c88fe7`). La date du 31/10/2026 remplace le 01/11 dans
   l'ADR 0013 (« Date : 2026-10-31 »), dans le profil de la page d'avis (« le 31/10/2026 ») et
   dans le journal (« (31/10) »).

   L'ADR 0013 date aussi ses mesures par format, comme le relecteur le demande :
   - les fragments d'avis : 1 255 sur le jeu et 5 054 sur la première étape au format 4, 1 543
     et 6 165 au format 3 ;
   - la mémoire au format 3 : 493 et 496 Mo sur le jeu, 471 et 483 Mo sur la première étape ;
   - la mémoire au format 4 : 488 Mo sur le jeu, puis **502 Mo chez beko** (une marge de 10 Mo),
     et 425 et 444 Mo sur la première étape.

   Sa section « Le coût » date du palier 3 le refus de la v2 seule. Elle ajoute la constante
   vérifiée sur les 190 appels : aucun n'est sous-estimé, +15 % en moyenne.
4. **`couper_ligne`** : un test direct, sans toucher au code (`881300b`,
   `tests/test_index_has.py`). L'assertion commune vérifie que les morceaux rejoints par une
   espace redonnent la ligne **à l'identique**. Chaque morceau tient sous la limite, sauf le
   dernier quand il commence par un mot plus long qu'elle, laissé entier. Elle porte sur :
   - **toutes les lignes des pages d'avis des fixtures** (187 lignes), à trois limites, avec des
     coupes à chacune ;
   - **la ligne de 1 781 caractères de `p_3700800`**, la plus longue du jeu, lue dans
     `demo/archive`, à trois limites ;
   - **des lignes fabriquées** :
     - une fin de phrase l'emporte sur une espace plus loin ;
     - sans fin de phrase, la coupe se fait à la dernière espace de la fenêtre ;
     - **un mot de 400 caractères sans espace** reste entier, seul ou au milieu d'une ligne.

   Six tests en tout, tous verts.
5. **La branche inatteignable de `has/client.py`** (lignes 128-129, « après une défaillance ») :
   **non corrigée, sur décision de l'IeC**. Le client a servi à la vraie collecte, et on n'y
   touche pas. Le constat du relecteur est juste.
   - `_defaillance_precedente` passe à vrai avant le réessai.
   - Si le réessai échoue, `ArretNet` arrête le passage. Si le plafond est atteint,
     `PlafondAtteint` l'arrête aussi.
   - S'il réussit, le drapeau revient à faux à la fin de `demander`.

   **La règle réelle** : deux défaillances d'affilée **sur la même URL** arrêtent le passage. Une
   défaillance réessayée avec succès, puis une défaillance sur l'URL suivante, donnent un second
   réessai, et non un arrêt. C'est le comportement que l'IeC a accepté (C1). Seule la lettre de
   la docstring du module (« sur la même URL ou sur la suivante ») et du §0 C ne colle pas. Le
   passage réel de beko n'a eu aucune défaillance : 724 réponses en 200, au premier essai.

   **Écrit dans les pistes de `pr.md`** : à la prochaine évolution du client, supprimer la
   branche et écrire la règle réelle dans la docstring, avec un test. Une autre voie serait de
   tenir le drapeau d'une URL à la suivante, si c'est la règle voulue.

## Remarques

- **Les mentions légales reçues en 200, mais sans `<main>`** (`collecte.py:332-336`) : la ligne
  porte le statut `nouveau` et aucune archive. Le cas est déclaré au palier 1 et ne s'est pas
  présenté. Rien n'est changé, pour la même raison qu'au point 5 : le code de la collecte a servi
  au passage réel. Un statut à lui est ajouté aux pistes de `pr.md`.
- **Le contrôle de dossier de l'état** (`pages_has.py:159-167`) porte sur tous les dossiers de
  la page, alors que les fragments le refont fiche par fiche. Aucune des 722 pages n'a plus d'un
  dossier BDPM, et le commentaire le dit déjà. C'est à reprendre quand le corpus s'étendra : ce
  point est ajouté aux pistes de `pr.md`.
- **L'en-tête du jeu v2** et **les « deux blocs »** d'`evaluation/README.md` : faits avec le
  point 1.
- **`ruff format --check` compte 341 fichiers chez le relecteur**, contre 340 dans `pr.md`. Le
  compte inclut les fichiers Markdown (ruff 0.17.2 : `ruff format --check pr.md` rend « 1 file
  already formatted »). Il y en avait 340 sur `cf04a7e`, 341 avec `pr.md`, et 343 avec ce
  commit.
- L'historique, les limites des liens rendus et la lisibilité : rien à faire.

## Vérifications locales

Elles sont faites sur le sommet de ces corrections et sont détaillées dans `pr.md`. La suite
complète est lancée **seule**, sans autre commande.
