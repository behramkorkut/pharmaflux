# Mission 09 — le corpus des avis HAS : collecte des pages d'avis, extraction, indexation, citation, jeu de questions v2

Branche `mission-09-corpus-des-avis-has`, depuis `d05355e`. `main` porte en plus l'addendum 1
(`a7df8ef`, l'ordre et `CLAUDE.md`). Aucun conflit n'est attendu : la branche ne touche aucun
chemin réservé, hormis les contrôles et les décisions de l'IeC (`docs/relectures/mission-09/`),
committés tels quels.

- **Ordre de mission** : `docs/missions/mission-09-corpus-des-avis-has.md`, avec l'addendum 1,
  puis `decision-question-2.md` et sa suite, qui ont ouvert un palier 4.
- **Codeur** : Claude Opus 5.5, pour toute la mission. Chaque commit porte son trailer.
- **Les paliers** : le §0 en `5cb8f9d`, puis quatre paliers acceptés par l'IeC. Leurs contrôles
  sont dans `docs/relectures/mission-09/`.
- **Le commit de clôture du code**, sur lequel l'évaluation finale est notée : `aba5173`. beko
  l'a lancée depuis `a1ae12a`, qui n'ajoute que des docs.
- **À venir** : la relecture (Claude Fable 5.1), puis la revue finale de l'IeC.
- **Aucun appel à l'API n'est parti d'une session d'agent**, des tests ou de la CI. Les tests
  passent par un double du client, et une garde de session fait échouer tout test qui sortirait
  sur le réseau. La démonstration et les évaluations ont été lancées par beko, avec la clé de son
  trousseau (`infra/agents/avec-cle.sh`).
- **Les seules requêtes d'agent vers la HAS** sont les douze du §0. La collecte a été lancée par
  beko.

## Ce qui est livré

**La collecte polie** (palier 1, `pharmaflux has collecter`, ADR 0013).
- **L'ordre d'un passage** : `robots.txt`, puis les mentions légales, relues à chaque passage,
  puis les pages.
- **La politesse** :
  - une pause de 2 s au moins, tenue dans le client, et qu'allonge un `Crawl-delay` visant
    notre `User-Agent` ;
  - aucune redirection suivie ;
  - un plafond de requêtes obligatoire ;
  - l'arrêt au premier 429 ou à la seconde défaillance, et un seul réessai, après 10 s ;
  - des codes de sortie de 0 à 3.
- **L'archive** est faite à l'octet (gzip, immuable). Le manifeste est en ajout seul, avec
  l'empreinte du texte extrait. La collecte reprend après une coupure, et `--simuler` ne fait
  aucune requête.
- **Le périmètre** : les dossiers dont un avis SMR ou ASMR date de 2024 ou après, lus par leurs
  contrats. Ils sont rangés par date d'avis décroissante, puis par dossier et par URL.

**L'extraction** (`pharmaflux has extraire`, version 2).
- **Le texte de la page**, bloc par bloc : toutes les sections sont gardées, coquilles comprises.
- **Trois dates** : celle de l'avis, celle de la mise en ligne (ou de la mise à jour), et celle
  de la consultation.
- **Le JSON-LD** contrôle le nom, les dossiers et la date ; il ne donne jamais de texte. Douze
  motifs de rejet.
- **La preuve de non-altération** a trois volets, dont un second lecteur sans code commun.
- **La version 2**, écrite après la collecte, compare le nom après `unescape` et lit tous les
  dossiers d'un avis commun.

**Le jeu de démo** : 150 pages sous `demo/archive` (2,57 Mo compressés), choisies par une règle
écrite (`demo choisir-has`). La partie BDPM est inchangée **à l'octet** : un test le vérifie
contre `beba0c8`. Le README du jeu porte la mention de la HAS.

**L'index au format 4** (format 3 au palier 2, puis 4 au palier 4).
- **Les fragments** : un par (page, CIS, partie), dans la section `avis_has`. L'extraction est
  recalculée à chaque construction, et les vecteurs denses des fiches sont repris du cache.
- **L'avgdl** est remesurée une fois, à 55,44, puis figée. Aucun rappel à 10 des fiches n'est
  perdu ; les avis coûtent un rang à 1 sur la v0 et la v1.
- **Deux horloges** : l'instant de la BDPM, et la position dans le manifeste HAS (lignes, empreinte
  du préfixe, version de l'extracteur). Un préfixe changé ou un autre extracteur impose la
  reconstruction.
- **Le rattachement** (palier 4) : une page ne se rattache qu'aux fiches du référentiel. Les pages
  sans fiche sont comptées et listées par `index etat`, par le bilan et par `index verifier`.
- **La mémoire** : les textes sont encodés avant l'écriture, et le modèle est chargé à la demande
  puis libéré. `index verifier` réencode son échantillon d'abord.
- **Les volumes** : le jeu compte 73 551 fragments, dont 1 255 `avis_has` ; la première étape en
  compte 77 350, dont 5 054.

**L'assistant**.
- **Le LLM ne voit aucune adresse** : elles lui sont masquées, et le contrôle refuse une adresse
  écrite dans la réponse. Le code rend sous la réponse la page d'avis avec ses trois dates, et
  les deux horloges.
- **Le prompt** demande la date de chaque fait daté, avec le fait. Il dit qu'un avis est une
  évaluation collective, qui ne s'applique jamais à une personne.
- **Le rappel** :
  - les fragments d'une même (page, partie) sont dédupliqués ;
  - le rappel par section suit une table écrite ; depuis le palier 3, « SMR » et « ASMR » ne
    demandent que le fragment `avis` ;
  - un mot courant ne vise un médicament qu'avec le mot qui le suit.
- **Le refus par les règles** couvre la posologie (dose, durée, rythme, mode de prise) et la
  convenance pour une personne (G2). L'extension est éprouvée sans faux refus sur 200 questions
  factuelles.
- **Le budget** : mission 9, plafond de 10 $, `CARACTERES_PAR_JETON = 1,7`.

**Le jeu v2** (`evaluation/questions-reference-v2.toml`) compte **144 questions**.
- **Les 88 de la v1**, au même texte. Trois comportements changent (`disponibilite-005`,
  `avis_has-004`, `-009`) ; ils sont listés en tête du fichier, avec leur raison.
- **56 nouvelles** :
  - 18 pour les correctifs (dates, rappel, mots courants, questions médicales), figées avant
    toute retouche (`bbb9809`) ;
  - 5 pour la table des sections, figées avant son changement (`c80b795`) ;
  - 19 sur le texte des avis, 4 pièges, 3 qui demandent le PDF et 1 comparaison (`fa8a5be`) ;
  - 6 pour le rattachement, figées avant lui (`34dca25`).
- **Le tirage** : 10 des 18 questions des correctifs, les 5 de la table, les 19 sur le texte et
  les 6 du rattachement sont tirées par une règle écrite, sans LLM (scripts
  `evaluation/choisir_*.py`). Les trois groupes figés avant un changement (les 18, les 5 de la
  table, les 6 du rattachement) ont leur empreinte fixée par un test.
- **L'attendu `attendu_has`** se vérifie sans gold, depuis l'archive HAS et le bronze.
- **La notation** ajoute le lien rendu, la date de l'avis et l'extrait. Les indicateurs sont
  rendus en trois blocs : la v1, les questions nouvelles seules, et la v2 entière.

**`Makefile` et CI** : `make index` passe `--archive-has demo/archive`, et `make evaluer` prend
`JEU_QUESTIONS`. La CI construit l'index réduit avec les pages d'avis.

**Les docs** :
- l'ADR 0013, et la ligne « complété par » de l'ADR 0004 ;
- le profil de la page d'avis (`docs/donnees/has.pages_avis.md`) ;
- le README : un exemple réel, le SMR de MOUNJARO dans le dossier CT-21681, avec son lien, et
  l'état ;
- `evaluation/README.md`, `docs/CONTEXTE.md` et le journal.

## La collecte de la première étape (beko, le 31/10)

| mesure | valeur |
|---|---|
| périmètre | 746 dossiers avec un avis de 2024 ou après, 720 avec un lien, **722 pages** (CT-21716 d'OZEMPIC n'a pas de lien) |
| passage `20261031T124148Z` | **724 requêtes sur un plafond de 761** : `robots.txt`, les mentions légales et 722 pages |
| réponses | 724 en HTTP 200 au premier essai ; aucune redirection, aucun réessai |
| durée | **25 min 56 s**, avec une pause moyenne de 2,15 s ; 101,5 Mio de résident au plus |
| pages | 722 archivées, **0 en erreur**, 0 interdite par `robots.txt` |
| extraction v1 | 714 extraites, **8 rejetées** |
| extraction v2 (`104cebb`) | **721 extraites, 1 rejetée** (PEDMARQSI : son document d'avis porte un autre dossier, un vrai défaut de la page) ; 0 écart, 0 divergence ; 714 empreintes égales au manifeste, 7 changements de statut ; 10 pages sans contrôle de dossier possible |
| mentions légales | premier passage, sans référence ; conditions inchangées depuis le 26/10, l'ADR 0004 n'est pas rouvert |

Sept des huit rejets venaient d'un contrôle trop strict : deux entités `&lt;` dans le nom, et cinq
avis communs à plusieurs dossiers. La correction a été proposée, acceptée par l'IeC, puis
appliquée, sans changer aucun texte déjà accepté.

## L'évaluation complète (PRD §2.2)

**L'évaluation finale** est celle que beko a relancée le 31/10 (21:31 et 21:37 UTC), depuis
`a1ae12a`, sur l'index du jeu au format 4. Elle est citée en `cf04a7e`
(`evaluation-palier-4.md`).

| indicateur (PRD §2.2) | cible | v1 (88) | v2, nouvelles seules (56) | v2 entière (144) |
|---|---|---|---|---|
| réponses correctes (borne basse : une paraphrase compte comme absente) | ≥ 85 % | **48/49 (98,0 %)** | **37/39 (94,9 %)** | **88/91 (96,7 %)** |
| réponses citant une source et sa date | 100 % | 52/53 (98,1 %) | **41/41 (100 %)** | 93/94 (98,9 %) |
| abstention sur les questions hors périmètre ou médicales | 100 % | **22/22** | **8/8** | **30/30** |
| lien et date de l'avis sous chaque réponse qui cite une page (condition de clôture) | 100 % | — | **24/24** | **26/26** |
| questions traitées justement | — | 83/88 | 52/56 | 138/144 |
| abstentions justes ; refus justes ; faux refus | — | 24/28 ; 11/11 ; 0 | 10/12 ; 5/5 ; 0 | 34/37 ; 16/16 ; 0 |
| abstentions techniques | — | 0 | 0 | 0 |
| **citations invalides** (condition dure) | 0 | **0** | **0** | **0** |
| **conseils médicaux** (condition dure) | 0 | **0** | **0** | **0** |
| appels payés ; relus du cache | — | 47 ; 15 | 34 ; 15 | 34 ; 77 |
| coût | sous le plafond | 0,8301 $ | 0,7903 $ | 0,7903 $ |

**La première évaluation**, avant le palier 4, a été lancée le 31/10 (20:25 et 20:30 UTC) depuis
`c8bd9e2`, sur l'index au format 3. Elle est citée et analysée en `4dec92b` (`evaluation.md`).

| indicateur | v1 (88) | v2, nouvelles seules (50) | v2 entière (138) |
|---|---|---|---|
| réponses correctes | 48/49 | 33/35 | 84/87 |
| sources datées ; hors périmètre ou médicales | 52/53 ; 22/22 | 37/37 ; 8/8 | 89/90 ; 30/30 |
| liens rendus | — | 20/20 | 22/22 |
| questions justes ; citations invalides ; conseils médicaux | 83/88 ; 0 ; 0 | 46/50 ; 0 ; 0 | 132/138 ; 0 ; 0 |
| appels payés ; coût | 62 ; 1,1011 $ | 43 ; 0,9919 $ | 43 ; 0,9919 $ |

**Le passage d'une évaluation à l'autre** : aucune question perdue ni gagnée, sur la v1 (88) comme
sur les 138 questions communes de la v2. Le changement de format a modifié le message de 81
appels, et les réponses nouvelles ont toutes gardé leur verdict. **Les six questions du
rattachement sont justes**, 6/6 :
- deux abstentions sur des pages sans fiche du référentiel (PEDISMOF 2, LYVDELZI) ;
- quatre pages mixtes, rendues sous la réponse (SKYRIZI, GARDASIL 9, ALHEMO, XALKORI).

**La v1 contre la mission 08** (44/49, 82/88) :
- 4 questions gagnées, les dates omises (`disponibilite-012`, `avis_has-007`, `-011`,
  `historique-005`) ;
- 3 perdues : `avis_has-004` et `-009`, qui répondent désormais par le lien, comme la v2 l'attend,
  et `historique-008`.

**La cible des sources datées** ne peut pas atteindre 100 % sur la v1 : `disponibilite-004` cite
`CIS_CIP_Dispo_Spec.txt`, qui n'a pas de date de fichier. Le cas est connu depuis la mission 08.

**La démonstration** (palier 2, cinq questions, `92aa78d`) :
- trois réponses citent une page d'avis ou l'ANSM, avec leurs dates ;
- un refus médical est décidé par les règles ;
- la question 2, sur MOUNJARO, s'abstenait à tort : c'est elle qui a ouvert le palier 4.

Rejouée après le palier 4 (0,0368 $, rendue mais pas comptée comme preuve), elle répond sur l'avis
du 2026-05-06 (CT-21681) : « pas de progrès par rapport à TRULICITY », ASMR V, avec la page
`p_4072400` et ses trois dates. **Cette réponse ne couvre que l'avis « Diabète de type 2 ».**
L'avis « Obésité » (`p_3538381`) n'est rattaché qu'à des CIS absents du référentiel : la page est
dans l'archive, mais hors de l'index.

### Les échecs, un par un

Ils sont les mêmes dans les deux évaluations. Chacun est analysé depuis le texte de sa réponse,
sans rien retoucher (`evaluation.md`, §3).
- **`historique-008` est gardé tel quel et compté FAUX.** La réponse est presque mot pour mot celle
  de la mission 08 : elle dit que la date de commercialisation manque. Mais elle se déclare
  « réponse » au lieu d'« abstention ».
  - Le suspect est le prompt, et sa consigne sur les dates.
  - Une seule observation ne sépare pas cette cause de la variation du modèle, et aucune session
    d'agent ne peut appeler l'API pour le vérifier.
- **`avis_has-044` : les liens ne sont pas filtrés par dossier.** C'est une piste pour plus tard,
  qui n'est pas corrigée ici.
  - La question porte sur le dossier CT-21716 d'OZEMPIC, qui n'a pas de page. Le texte le dit.
  - Mais le code rend sous la réponse la page d'un autre dossier (CT-21501), et les quatre liens
    du fragment `avis` de la fiche.
  - C'est une limite écrite dans l'ADR 0013.
- **`avis_has-045` : un écart honnête entre l'attendu et le comportement.** DOLIPRANE 2015 est hors
  corpus. La réponse donne le SMR de la BDPM et dit que le texte de l'avis manque, alors que
  l'attendu est une abstention. L'attendu ne bouge pas.
- **`avis_has-036` : une paraphrase.** C'est la borne basse annoncée : la réponse ne reprend pas
  l'extrait mot pour mot.
- **`avis_has-020` (WEGOVY) et `-003` (OZEMPIC) : la limite de la cible du rappel.** Le CIS visé
  est le mieux classé, qui n'est pas toujours la dose de la question. Une heuristique de plus a été
  refusée au palier 2. Aucune des deux réponses n'invente.
- **`disponibilite-005`, `avis_has-004` et `-009`** sont fausses au regard de la v1 et justes au
  regard de la v2. Ce sont les trois changements de comportement annoncés.

### Les questions neuves

- **Les questions médicales neuves** (`medical-012` à `-016`) : **5/5**, toutes refusées par les
  règles.
  - `medical-013`, `-014` et `-016` ont servi à étendre la règle de refus : elles ne la mesurent
    pas.
  - `-012` et `-015` étaient refusées par les règles d'avant l'extension.
  - L'extension se juge par l'absence de faux refus : 0 sur la v0, la v1 et la v2, et 0 sur 200
    questions factuelles.
- **Les questions qui ont servi à trouver un défaut** sont rendues, mais ne comptent pas comme
  preuve : `avis_has-003` et `-014` pour la table, la question 2 de la démonstration pour le
  rattachement.
- **Les groupes de la v2** (évaluation finale) :

| groupe | score |
|---|---|
| dates | 6/6 |
| rappel | 4/4 |
| table | 4/5 |
| mots courants | 3/3 |
| médicales | 5/5 |
| texte des avis | 18/19, lien rendu 19/19 |
| pièges | 2/4 |
| PDF | 3/3 |
| comparaison | 1/1 |
| rattachement | 6/6 |

## Le coût

**La dépense de la mission** (`pharmaflux assistant depenses`) : **190 appels, 3,8244 $ sur
10 $**, tous partis le 31/10, avant le 16/11 (UTC). Il reste 6,1756 $. Le Lot 3 en est à
255 appels pour 4,8553 $ (missions 08 et 09).

| lancement | appels | coût |
|---|---|---|
| première évaluation, v1 puis v2 | 62 + 43 | 2,0930 $ |
| démonstration | 3 | 0,0743 $ |
| évaluation relancée après le palier 4, v1 puis v2 | 47 + 34 | 1,6204 $ |
| question 2 de la démonstration, rejouée | 1 | 0,0368 $ |

**Le coût pour 1 000 questions** se lit sur la première évaluation, faite sans cache :
- **12,51 $** pour la v1 (11,22 $ à la mission 08) ;
- **19,84 $** pour les questions nouvelles ;
- 7,19 $ pour la v2 entière, dont 62 appels relus du cache.

La relance donne moins (9,43 $, 14,11 $ et 5,49 $), parce qu'elle relit le cache. Le prix d'un appel
payé n'a pas bougé : 0,0177 $ pour la v1 et 0,0232 $ pour les nouvelles. Les nouvelles coûtent plus,
pour deux raisons :
- **la part qui va au LLM** : les règles décident moins de refus et d'abstentions sur les
  nouvelles (86 % d'appels, contre 70 % pour la v1) ;
- **les fragments d'avis sont plus longs** : +28 % en entrée et +24 % en sortie.

**La constante 1,7** (I1) : les 190 appels sont reconstitués sans API, et toutes leurs clés sont
retrouvées au cache. **Aucun n'est sous-estimé.**
- Sur les deux évaluations, le réel va de 1,776 à 2,189 caractères par jeton.
- L'estimation dépasse le réel de +15,0 % en moyenne sur les 105 appels de la première, et de
  +15,5 % sur les 82 de la relance (question 2 comprise).
- La prose des avis se découpe en plus de caractères par jeton que les fiches (2,006 contre
  1,880) : la constante y est encore plus prudente.

## La mémoire (ADR 0009, seuil de 512 Mo, `/usr/bin/time -l`)

| commande | mesure |
|---|---|
| `has collecter`, passage réel (722 pages) | 101,5 Mio |
| `index construire` sur le jeu (format 3, 1 543 textes à encoder) | 586 Mo, ramenés à **493 Mo** au palier 2 (encodage avant écriture, modèle libéré) |
| `index verifier` sur le jeu | 534 Mo, ramenés à **496 Mo** au palier 2 (échantillon réencodé d'abord) ; 488 Mo au palier 4 |
| `index verifier` sur le jeu, chez beko, le 31/10 (format 4) | **502 Mo** pour l'encodage, 418 Mo pour le sous-processus |
| la première étape, 721 pages, dans un espace Qdrant à part | construire 471 Mo et vérifier 483 Mo au format 3 ; 425 et 444 Mo au format 4 |
| `assistant evaluer --estimer` | de 400 à 469 Mo |

**La marge est de 10 Mo.** Chez beko, `index verifier` est monté à 502 Mo pour un seuil de 512 Mo.
C'est plus que les 444 Mo mesurés sur les 721 pages, dans un espace à part. Le pic dépend de
l'échantillon réencodé et de l'allocateur, et il varie d'une exécution à l'autre. Un réencodage
par lots plus petits, ou dans un sous-processus, élargirait la marge. C'est une proposition, sans
correction ici.

## Vérifications locales (commit testé : `cf04a7e`, le sommet avant ce rapport ; code identique à `aba5173`)

Redpanda, Qdrant et les fichiers du modèle sont présents sur le Mac.

| commande | résultat |
|---|---|
| `uv run ruff check .` ; `uv run ruff format --check .` | All checks passed ; 340 files already formatted |
| `uv run mypy src` | Success: no issues found in 89 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **913 passed** en 6 min 25, aucun saut, session verte, intégration et modèle compris. Une première passe, lancée pendant que d'autres commandes chargeaient la machine, a donné 913 passed et une session **rouge** : un réessai du registre a servi pendant l'intégration (`RemoteProtocolError` sur un `POST /subjects/…`, règle A2). Le code du bus n'a pas changé depuis `dff0a34`. La seconde passe, seule, n'a eu aucun réessai |
| aucune requête réseau dans les tests | la garde de session `tests/conftest.py::reseau_coupe` et `tests/test_reseau.py` |
| `sh infra/git-hooks/test-crochets.sh` ; `python3 infra/agents/test_garde_fou.py` | tout est conforme ; OK (24 tests) |
| simulation du `Makefile` | `make -n index`, `make -n demo` (palier 2) ; `make -n evaluer`, avec et sans `JEU_QUESTIONS` (palier 3) |
| YAML de la CI | `ci.yml` touché au palier 2 : relu par `yaml.safe_load` et par le crochet |
| `demo verifier` | conforme : la BDPM et 150 pages d'avis (2 574 863 octets compressés) |
| `profil --racine ~/pharmaflux-data` | 11 fichiers profilés, 0 anomalie bloquante |
| `questions verifier --racine ~/pharmaflux-data` (v0) | 40 : 25 conformes, 5 non calculables, 10 sans attendu |
| `questions verifier --racine demo/archive --entrepot data/demo/lakehouse` | v0 : 25 concordent ; v1 : 50 conformes, 50 concordent ; v2 : 144 questions, 91 conformes, 67 concordent |
| `silver verifier` sur le jeu | 22/22 archives conformes, invariants conformes |
| `gold qualite` sur le jeu | 14 contrôles, aucun bloquant ne tombe |
| `evenements` contre `beba0c8` | identique (`diff -r` vide, palier 1) ; le socle (`evenements`, `collecte`, `bus`, `contrats`, `silver`, `gold`) n'a pas changé depuis `dff0a34` |
| `index verifier` sur le jeu (format 4, séquence de beko) | conforme, cosinus minimal 0,9955 ; 73 551 fragments, 18 pages sans fiche |
| `assistant evaluer` (v1, v2), séquence de beko | conditions dures tenues ; aucune question perdue contre `4dec92b` |
| `pharmaflux assistant depenses` | mission 9 : 190 appels, 3,8244 $ ; reste 6,1756 $ sur 10 $ |

**La séquence de beko** a commencé à `make index`. La partie BDPM du jeu, le silver et le gold
n'ont pas changé : la partie BDPM est vérifiée par un test d'empreinte contre `beba0c8`, et il
n'y a aucun changement de code depuis `dff0a34`. `silver verifier` et `gold qualite` sont
rejoués ici, sur le jeu.

**Le nombre de tests** : 735 au départ de la mission, puis 810, 889, 909 et 913 aux paliers 1 à
4.

## Écarts acceptés

**Le §0** : un lien a été suivi jusqu'au PDF, au lieu de trois.

**Palier 1** : quatre précisions prises en codant.
- `robots.txt` illisible donne un refus, mais un 429 donne un arrêt.
- `robots.txt` et les mentions légales ne s'archivent que s'ils changent.
- Le texte des mentions est celui de `<main>`.
- `--simuler` conseille un plafond, sans l'exiger.

**La collecte** : l'extracteur v2 vient après le passage réel, sur sept rejets trop stricts. L'ADR
0013 a été reportée au palier 3.

**Palier 2** :
- la démonstration est citée à part ;
- deux réglages ramènent `index construire` et `index verifier` sous 512 Mo ;
- la règle de refus s'étend après l'échec de trois questions médicales neuves ;
- deux questions ont été posées à l'IeC. La première (la table des sections) est acceptée sous
  condition ; la seconde (la cible du rappel) est refusée.

**Palier 3** :
- la table des sections change, après cinq questions figées avant elle ;
- la v2 se lance après la v1, parce que la porte la refuse seule ;
- **il y a 19 questions sur le texte des avis, au lieu d'environ 24.** Le §0 en annonçait environ
  24, que l'addendum a retenu et que le contrôle du palier 2 a repris. La règle en tire 19 : cinq
  thèmes, quatre questions par thème, et trois pour le lien. **28 questions portent sur une page
  d'avis** : les 19, les 4 pièges, les 3 qui demandent le PDF, `avis_has-004` et `-009`. Avec les
  six du palier 4, dont deux sur des pages hors de l'index, elles sont 34.

**L'évaluation** :
- rien n'est retouché ;
- `historique-008` et `avis_has-045` comptent FAUX, tels quels ;
- `disponibilite-004` n'a pas de source datée.

**Palier 4**, ouvert par `decision-question-2.md` (voie C) :
- les 121 pages sans fiche du référentiel sont hors de l'index ;
- la v1 et la v2 se relancent, parce que leurs messages changent : 82 appels de plus avec la
  question 2, pour 1,6571 $.

## Limites et propositions

- **Les liens rendus ne sont pas filtrés par le dossier de la question** (`avis_has-044`).
  - **Proposition (mission 10)** : ne rendre que les liens du dossier nommé, mesuré sur des
    questions écrites avant.
- **Le lien rendu en double.** Sous la réponse KALYDECO de la démonstration, le même lien est rendu
  trois fois, une fois par citation de la page.
  - **Proposition** : regrouper les citations d'une même page sous un seul lien.
- **Les pages sans fiche du référentiel** : 121 sur 721 (**16,8 %**, 1 111 fragments). Ce sont
  surtout des médicaments récents : KISUNLA, LEQEMBI, SHINGRIX, l'avis « Obésité » de MOUNJARO.
  Elles restent dans l'archive, et reviennent dans l'index quand leur fiche entre au référentiel.
- **La cible du rappel** est le CIS visé le mieux classé (`avis_has-020`, `-003`). La table des
  sections fait l'union des lignes qui correspondent.
- **19 faux rattachements possibles par avis commun**, et 10 pages sans contrôle de dossier. Ces
  pages sont comptées et listées.
- **`historique-008`** : la consigne des dates est suspecte.
  - **Proposition** : la mesurer sur plusieurs tirages, dans une mission qui le prévoit.
- **La marge mémoire** de `index verifier`, 10 Mo.
  - **Proposition** : réencoder l'échantillon par lots plus petits, ou dans un sous-processus.
- **Les PDF d'avis** demandent une mission et une ADR à eux. Le chiffrage est dans l'ADR 0013 :
  722 requêtes, environ 0,45 Go, et un index qui double.
- **Une collecte périodique des avis** : proposée dans l'ADR 0013, et pas installée.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
