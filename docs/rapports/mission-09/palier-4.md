# Mission 09 — palier 4 : le rattachement des pages d'avis aux seules fiches du référentiel

## Synthèse

**Fait**, suivant `decision-question-2.md` et sa suite (voie C), dans l'ordre demandé :
1. `9694be7` : la mesure, sans rien changer. 121 pages sur 721 n'ont que des CIS absents du
   référentiel ; arrêt, puis décision de l'IeC.
2. `34dca25` : six questions neuves tirées par une règle écrite et figées par un test.
   - 4 portent sur des pages mixtes (SKYRIZI, GARDASIL 9, ALHEMO, XALKORI) ;
   - 2 portent sur des pages sans fiche du référentiel (PEDISMOF 2, LYVDELZI).
3. `aba5173` : le rattachement seul, l'état et leurs tests.
   - Une page d'avis ne se rattache plus qu'aux fiches du référentiel, au format 4.
   - Le rattachement se recalcule à chaque construction et mise à jour.
   - Les pages sans fiche du référentiel sont comptées et listées par `index etat`, le bilan
     de construction et `index verifier`.
4. Ce commit : l'ADR 0013, le profil de la page d'avis, `CONTEXTE.md` et ce rapport.

**Mesuré sans LLM** :
- la question 2 de la démonstration passe la porte, avec 5 fragments de MOUNJARO dans les dix ;
- les 4 pages mixtes sont dans les dix, sous des fiches du référentiel ;
- jeu : 73 551 fragments, 18 pages sans fiche du référentiel ; `index verifier` conforme ;
- première étape : 121 pages sans fiche ; `construire` 425 Mo, `verifier` 444 Mo.

**Vérifications locales** (commit testé : `aba5173`) : vertes, **913 tests**.
**Reste à beko** : la v1, puis la v2, puis la question 2 rejouée (§4). Changer le format modifie
les messages de 47 appels de la v1 : **la v1 se relance**, et la v2 seule ne passerait pas la
porte.
**Écarts** : aucun. **Questions pour l'IeC** : aucune.

## 1. La mesure et la décision

Voir `palier-4-mesure.md` (`9694be7`) :
- 1 111 fragments sur 6 165 étaient rattachés à un CIS absent du référentiel ;
- 151 pages en portaient, dont 30 mixtes ;
- **121 pages (16,8 %)** n'avaient que de tels CIS : 18 sur 149 dans le jeu.

L'IeC a choisi la **voie C** (`decision-question-2-suite.md`) : la règle stricte, et la perte
rendue visible. L'identité d'un médicament vient du référentiel, et la v1 attend déjà une
abstention pour un CIS absent.

## 2. Les questions neuves (`34dca25`)

**La règle** est dans `evaluation/choisir_neuves_v2_rattachement.py`, écrite et committée avec
les questions, avant le changement. Elle retient les pages du jeu à un seul dossier, hors
MOUNJARO et hors des pages déjà citées par la v2, rangées par sha256 de « rattachement/<page> ».
La question est celle de la démonstration : « Quel progrès <nom> apporte-t-il selon l'avis de la
Commission de la transparence ? ».

| question | page | type | attendu |
|---|---|---|---|
| `avis_has-051` | PEDISMOF 2 (`p_4336375`) | sans fiche du référentiel | abstention, orientée vers la HAS |
| `avis_has-052` | LYVDELZI (`p_3636962`) | sans fiche du référentiel | abstention, orientée vers la HAS |
| `avis_has-053` | SKYRIZI (`p_3826273`) | mixte | la page rendue, la date de l'avis, l'extrait de « Quel progrès ? » |
| `avis_has-054` | GARDASIL 9 (`p_3634549`) | mixte | idem |
| `avis_has-055` | ALHEMO (`p_3658189`) | mixte | idem |
| `avis_has-056` | XALKORI (`p_3892357`) | mixte | idem |

Empreinte `bdfcaff782040057…`, fixée par `tests/test_questions_v2.py`. La règle se lit contre la
v2 d'avant ces questions : rejouée ainsi, elle les redonne à l'identique.
`questions verifier` : 144 questions, 91 conformes, 67 concordent avec le gold.

## 3. Les mesures sans LLM (index du jeu au format 4)

**La question 2 de la démonstration** (rendue, mais pas comptée comme preuve) : elle allait à la
porte structurelle. Elle passe maintenant au LLM, avec 5 fragments des CIS de MOUNJARO visés
parmi les dix (page `p_4072400`).

**Les questions neuves** (`chemin.preparer`, sans appel) :

| question | décision avant le LLM | dans les dix |
|---|---|---|
| `-053` SKYRIZI | au LLM, 5 CIS visés | 7 fragments visés, la page attendue est là |
| `-054` GARDASIL 9 | au LLM, 1 CIS visé | 10 fragments visés, la page attendue est là |
| `-055` ALHEMO | au LLM, 2 CIS visés | 4 fragments visés, la page attendue est là |
| `-056` XALKORI | au LLM, 2 CIS visés | 4 fragments visés, la page attendue est là |
| `-051` PEDISMOF 2 | au LLM, aucun CIS visé (nom inconnu du référentiel) | d'autres pages ; l'abstention se jugera à l'évaluation |
| `-052` LYVDELZI | idem | idem |

La mesure décisive est l'évaluation de beko (§4). Elle seule dira si une question de la v2 est
perdue contre `4dec92b`, question par question.

**L'index** :

| | jeu (150 pages) | première étape (721 pages) |
|---|---|---|
| fragments | 73 551 (−288) | 77 350 (−1 111) |
| `avis_has` | 1 255 | 5 054 |
| pages sans fiche du référentiel | 18 | 121 |
| `index construire` | 37 s, tout du cache ; 238 et 418 Mo | 46 s ; 212 et 425 Mo (espace à part, effacé ensuite) |
| `index verifier` | conforme, cosinus minimal 0,9955 ; 488 et 421 Mo | conforme, 0,9962 ; 444 et 412 Mo |

L'avgdl reste à 55,44 : le gel du classement tient.

## 4. Le coût et les commandes pour beko

`assistant evaluer --estimer` sur l'index au format 4. Retirer 288 fragments change l'IDF du
lexical que tient Qdrant, donc l'ordre des fragments, donc les messages :

| jeu | en cache | appels à faire | au pire | probable |
|---|---|---|---|---|
| v1 | 15 | **47** | 4,64 $ | environ 0,87 $ |
| v2 seule | 30 | 81 | 8,15 $, **refusée** (7,83 $ restants) | environ 1,50 $ |
| v2 après la v1 | environ 77 | environ 34 | environ 3,4 $ | environ 0,6 $ |

**La v1 se relance**, puisque ses messages changent. La v2 se lance après elle, puis la question
2 de la démonstration est rejouée. Tout part avant le 16/11. Depuis `pharmaflux-codeur/`, dans
Terminal.app :

```bash
make index
uv run pharmaflux index etat
make evaluer EVALUER_OPTIONS=--estimer
sh infra/agents/avec-cle.sh make evaluer
sh infra/agents/avec-cle.sh make evaluer JEU_QUESTIONS=evaluation/questions-reference-v2.toml
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "Quel progrès MOUNJARO apporte-t-il selon l'avis de la Commission de la transparence ?"
uv run pharmaflux assistant depenses
```

L'index du jeu est déjà au format 4 dans le Qdrant du Mac, donc `make index` n'aura rien à
faire. Si une évaluation s'arrête sur la porte ou sur une erreur, ne relance rien et préviens
l'IeC et moi. Je citerai les sorties dans un commit à part, avec la comparaison question par
question contre `4dec92b`.

## 5. Vérifications locales

| vérification | résultat |
|---|---|
| ruff, format, mypy | verts |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` (sur `aba5173`) | **913 passés**, 7 min 6 s |
| `questions verifier` v2 | 144 questions, 91 conformes, 67 concordent |
| `index verifier` (jeu, format 4) | conforme |
| mémoire sur la première étape | 425 et 444 Mo, sous 512 Mo |
