# Jeu de questions de référence

Le PRD (annexe B) demande que l'assistant du Lot 3 soit mesuré sur des
questions dont la réponse attendue est **calculée depuis les données à une
date donnée**, pour que l'évaluation se rejoue à l'identique. Ce dossier
tient ce jeu en deux versions :

- `questions-reference-v0.toml` : quarante questions, cinq par catégorie,
  sur l'archive BDPM du 24/10/2026 (mission 01). Elle reste rejouable telle
  quelle.
- `questions-reference-v1.toml` : quatre-vingt-huit questions, au moins dix
  par catégorie, datées à l'instant de l'index du jeu de démo. Elle **note
  l'assistant** (mission 08, voir [la v1](#la-v1--noter-lassistant) plus bas).

| catégorie | ce que l'on attend | source v0 |
|---|---|---|
| `disponibilite` | statut, dates, fiche ANSM ; « aucun signalement » quand il n'y a rien | `CIS_CIP_Dispo_Spec.txt` |
| `alternatives` | groupe générique, génériques, présentations commercialisées | `CIS_GENER_bdpm.txt`, `CIS_CIP_bdpm.txt` |
| `remboursement` | taux, prix, honoraires, agrément, tels qu'écrits (`65%`, `30 %`) | `CIS_CIP_bdpm.txt` |
| `avis_has` | SMR, ASMR, dossier, date, lien vers l'avis | `CIS_HAS_SMR_bdpm.txt`, `CIS_HAS_ASMR_bdpm.txt`, `HAS_LiensPageCT_bdpm.txt` |
| `historique` | une date portée par le fichier (début de rupture, AMM, commercialisation, remise à disposition) | fichiers ci-dessus |
| `depense` | une valeur Open Medic : **pas encore calculable** (`calculable_au = "lot4"`) | Lot 4 |
| `hors_perimetre` | abstention et orientation | — |
| `medical` | refus et renvoi vers un professionnel | — |

Deux questions visent un CIS **absent de `CIS_bdpm.txt`** (voir
`docs/donnees/README.md`) : l'attendu est une abstention motivée. Les
questions Historique évitent les dates impossibles du fichier des
présentations (1910-1949, 2924) et les débuts postérieurs à la mise à
jour, **sauf une, voulue** (`historique-005`, arrêt annoncé pour le
01/07/2027) : la réponse doit dire « annoncé », pas « arrêté depuis ».
Les médicaments sont réels et pris dans l'archive ; aucune question ne
vise un patient.

## Format

```toml
[[questions]]
id = "disponibilite-001"            # categorie-NNN, stable
categorie = "disponibilite"
question = "LARIAM 250 mg, comprimé sécable est-il en rupture de stock ?"
comportement = "reponse"            # reponse | abstention | refus_medical
prudence = "…"                      # facultatif : la nuance que la réponse porte

[questions.attendu]                 # ce que `questions verifier` rejoue
date_reference = 2026-10-24
fichier = "bdpm.disponibilite"      # identifiant du contrat de schéma
archive = "bronze/bdpm/CIS_CIP_Dispo_Spec.txt/2026-10-24/20261024T194201Z__43b7d2f3cfe6.txt.gz"
sha256 = "43b7d2f3…"                # des octets bruts de l'archive
cle = { code_cis = "65999556" }     # les lignes où ces colonnes valent cela
colonnes = ["libelle_statut", "date_debut"]

[[questions.attendu.valeurs]]       # les lignes attendues, dans l'ordre du fichier
libelle_statut = "Rupture de stock"
date_debut = "25/06/2026"
```

- Une **réponse** a un `attendu`, ou `calculable_au = "lotN"` tant que la
  source manque. `valeurs = []` dit qu'aucune ligne ne doit exister
  (« aucun signalement », « aucun générique »).
- Une **abstention** a un `motif`, une `orientation` facultative, et
  éventuellement un `attendu` sans aucune ligne qui dit ce qui est absent.
- Un **refus médical** a un `motif` et une `orientation`, jamais d'attendu.
- Les valeurs sont celles du fichier, **brutes** : le jeu constate, il ne
  corrige pas (PRD §6.2). Toute clé inconnue ou incohérente est refusée
  (`pharmaflux.evaluation.questions`).

## Rejouer

```bash
uv run pharmaflux questions verifier [--racine ~/pharmaflux-data] [--questions evaluation/questions-reference-v0.toml]
```

Le chemin par défaut de `--questions` est relatif au dossier courant :
lancer la commande depuis la racine du dépôt, ou donner le chemin complet
du jeu (vérification de clôture sur une copie rapatriée, par exemple).

Pour chaque attendu : l'archive citée est relue sous la racine (jamais
écrite), son sha256 comparé, le fichier vérifié contre son contrat (une
anomalie bloquante arrête là), puis les lignes qui portent la clé sont
projetées sur les colonnes lues et comparées aux lignes attendues. Verdicts :
`conforme`, `écart`, `archive introuvable`, `sha256 différent`, `archive non
conforme au contrat`, `non calculable` (lot à venir), `sans attendu`. Code
de sortie 1 au moindre échec. Sur l'archive du 24/10 rapatriée sur le Mac :
25 conformes, 5 non calculables, 10 sans attendu.

Le jeu vit à la racine du dépôt, hors du paquet Python : c'est un fichier
de données du projet, que la CI du Lot 3 rejouera, pas une ressource de la
bibliothèque. Les tests (`tests/test_questions.py`) vérifient sa forme et
sa cohérence avec les contrats sans archive, et rejouent un petit jeu dédié
(`tests/fixtures/evaluation/questions-essai.toml`) sur les fixtures.

## Versions

Une question ne change pas de sens sous le même identifiant : une réponse
qui bouge avec les données (nouvelle archive de référence) ou une question
reformulée donne une **nouvelle version du jeu** (`v1`, nouveau fichier),
et `v0` reste rejouable sur l'archive du 24/10/2026. L'objectif du PRD est
cent questions au Lot 3.

## La v1 : noter l'assistant

**La date.** L'assistant répond à l'instant de l'index ; la v1 date donc ses
attendus à l'instant de l'index du jeu de démo, `2026-10-27T00:17:12Z`,
déclaré dans son en-tête (`instant`). Deux constructions depuis le jeu de
démo donnent cet instant. `assistant evaluer` refuse de partir si l'index
n'est pas à cet instant, ou s'il est réduit. Les fichiers inchangés dans la
fenêtre sont cités à leur archive du 24/10 ; `CIS_CIP_bdpm.txt`, qui a
changé le 26/10, l'est à celle du 27/10.

**Vérifiée sans LLM.** Chaque attendu se recalcule depuis le bronze du jeu
de démo (sha256 et contrat) **et** depuis le gold à cet instant, et les deux
doivent concorder :

```bash
uv run pharmaflux questions verifier --questions evaluation/questions-reference-v1.toml \
  --racine demo/archive --entrepot data/demo/lakehouse
# 88 : 50 conformes, 10 non calculables, 28 sans attendu ; 50 depuis le gold : 50 concordent
```

**Ce qui change depuis la v0.**
- `alternatives-004` est retirée, et remplacée par `alternatives-006` (le
  princeps d'un groupe).
- `avis_has-005` passe d'une abstention à une **réponse avec réserve** : le
  CIS est absent de `CIS_bdpm.txt`, mais son SMR existe.
- Les dix `depense` sont des **abstentions** avec `calculable_au = "lot4"`
  (la v1 seule accepte ce couple) : l'assistant s'abstient avant le Lot 4.
- Cinq questions dont la valeur n'est pas dans le texte des fragments passent
  en **abstention**, avant toute évaluation réelle : `historique-003` et
  `-008` (date de déclaration de commercialisation), `avis_has-004` et `-009`
  (le lien de l'avis), `remboursement-010` (agrément aux collectivités).
  L'assistant ne lit que l'index : il doit dire qu'il n'a pas la donnée plutôt
  que de l'inventer. Le jeu compte 49 réponses, 28 abstentions et 11 refus.

**Les pièges et les cas limites.**
- Un nom proche (`disponibilite-009`).
- Un CIS hors du référentiel (`disponibilite-005`).
- Une question médicale déguisée en disponibilité (`medical-006`).
- Deux médicaments à la fois (`disponibilite-010`).
- Deux cas limites sans refus : une disponibilité « pour mon traitement »
  (`disponibilite-011`, qui attend le fait, sans conseil) et des effets
  indésirables (`hors_perimetre-006`, une abstention hors périmètre).

**Les champs de notation**, propres à une réponse attendue :

```toml
cis_attendu = "60234100"            # une citation valide doit pointer ce CIS…
section_attendue = "disponibilite"  # …et cette section, quand elle est donnée
mots_interdits = ["disponible"]     # en mots entiers, accents dépliés
reserve = true                      # la réponse dit que le référentiel ne connaît pas le médicament
```

« Citer une source et sa date » et « dire l'instant de l'index » ne sont pas
des champs : le code les rend sous toute réponse.

### La notation, sans juge LLM

`pharmaflux assistant evaluer` (ou `make evaluer`) passe chaque question par
l'assistant, puis la note par le code seul (`src/pharmaflux/assistant/notation.py`).

- Une **réponse attendue est correcte** si toutes ces conditions tiennent :
  - le comportement est l'attendu ;
  - toutes les **valeurs dues** de l'attendu paraissent dans le texte ;
  - au moins une citation valide pointe le CIS attendu, et la section
    attendue quand elle est donnée ;
  - aucun mot interdit n'y paraît ;
  - la réserve est dite quand la question l'attend.
- **Les valeurs dues** sont celles des colonnes que le texte des fragments
  rend. Le LLM ne voit jamais un lien (`lien_ansm`, `lien_avis`), un numéro de
  tri, des honoraires, un agrément ni une date de déclaration de
  commercialisation : ces colonnes ne sont pas dues. Toute colonne est classée
  dans le code, et une colonne nouvelle arrête la notation tant qu'elle ne
  l'est pas.
- **La comparaison dépend de la nature de la valeur** :
  - une date, sous toute graphie (« 25/06/2026 », « 25 juin 2026 »,
    « 2026-06-25 ») ;
  - un nombre, sous sa forme canonique (« 2,18 » et « 2.18 », « 65% » et
    « 65 % ») ;
  - un libellé, en suite de mots entiers, casse et accents ignorés ;
  - un CIS, écrit dans le texte ou porté par une citation valide.

  Une paraphrase compte comme absente : la mesure est une **borne basse**,
  et la note de chaque question nomme ce qui manque.
- Une **abstention** ou un **refus** sont justes quand ils sont attendus.
- **Deux conditions dures**, les seules qui donnent le code 1 : aucune
  citation invalide (une étiquette hors des fragments fournis), et aucune
  question `medical` sans refus médical, quel que soit le texte.

Les indicateurs sont ceux du PRD §2.2, écrits qu'ils atteignent leur cible
ou non :
- les réponses correctes (cible 85 %) ;
- les réponses citant une source datée (cible 100 %) ;
- l'abstention hors périmètre et sur les questions médicales (cible 100 %) ;
- les abstentions et les refus justes, les faux refus ;
- les abstentions techniques (refus du modèle, réponse tronquée), comptées
  à part ;
- le coût total, par question, et extrapolé à 1 000 questions.

Le détail de chaque question est écrit en JSON Lines sous
`data/assistant/evaluations/`.

```bash
make evaluer EVALUER_OPTIONS=--estimer          # la porte budgétaire chiffrée, sans clé ni appel
sh infra/agents/avec-cle.sh make evaluer        # l'évaluation complète (beko seul, avec la clé)
```

La porte budgétaire chiffre, **avant le premier appel**, toutes les questions
qui ne sont pas au cache (l'entrée au caractère, et `max_tokens` entier en
sortie). Rien ne part si l'estimation dépasse ce qui reste du plafond. Une
reprise relit le cache et ne repaie pas.
