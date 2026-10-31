# Mission 09 — palier 2 : l'index au format 3 avec les avis, le jeu de démo, l'assistant

## Synthèse

**Fait** (décisions 3, 4 et 6), en trois commits dans l'ordre que demande l'addendum 1 (H) :
1. `07ac561`, l'infrastructure, sans retouche de l'assistant :
   - le `Crawl-delay`, le sous-ensemble de démo (150 pages) et l'index au format 3 avec la
     section `avis_has` et sa seconde horloge ;
   - les liens et les dates rendus par le code ;
   - la table des sections et la liste des mots courants, écrites mais non branchées.
2. `bbb9809`, le jeu v2 : les 88 questions de la v1, plus **18 questions neuves figées**, dont
   10 tirées par une règle sans LLM.
3. ce commit, les retouches : le prompt, la déduplication, le rappel par section, les mots
   courants et le refus de la posologie (G2).

**Mesuré sans LLM** :
- index : 1 543 fragments d'avis (149 pages, 259 CIS), aucun rappel à 10 perdu, l'avgdl est
  remesurée à 55,44 ;
- déduplication : elle rend leur section à 3 des 4 questions neuves de rappel ;
- rappel par section : il ne se déclenche ni pour OZEMPIC ni pour BIMZELX (question 1) ;
- règles : les 5 questions médicales neuves sont refusées, sans faux refus sur 200 questions
  factuelles.

**Démonstration de beko** : commandes plus bas ; sa sortie sera citée dans un commit à part.
**Vérifications locales** (commit testé : celui-ci) : vertes, 889 tests ; aucun appel à l'API.
**Écarts** : la démonstration est citée à part, comme la collecte au palier 1. L'ADR 0013 est
au palier 3. Deux réglages de mémoire ramènent `index construire` et `index verifier` sous
512 Mo.
**Questions pour l'IeC** : 1. la table des sections (SMR → `avis` seul ?) ; 2. la cible du
rappel quand plusieurs CIS sont visés. **Propositions** : aucune autre.
Plus de 200 lignes : le palier porte trois commits et quatre mesures (rappel, mémoire,
retouches, coût).

## 1. Le jeu de démo (addendum 1 E)

| mesure | valeur |
|---|---|
| pages | 150 : 22 imposées (5 fixtures du §0, 17 cas de la collecte), 3 des CIS de la v1, 125 de complément (plus petit sha256 de l'URL) |
| taille | 2 574 863 octets compressés (2,8 Mo sur disque), sous les 10 Mo |
| partie BDPM | identique à `beba0c8` : sha256 de « chemin sha256 » de ses 23 fichiers, `84924ced…`, ici comme à `beba0c8` (test) |
| commandes | `demo choisir-has` (la règle, sans réseau, sur la BDPM du jeu) ; `demo fabriquer-has --racine ~/pharmaflux-data` (0,45 s, 56 Mo) ; `demo verifier` contrôle les deux parties |

La liste `demo/has-pages.txt` porte la raison de chaque page. Un test la recalcule par la règle.
Le README du jeu dit ses deux parties figées et porte la mention de la HAS.

## 2. L'index au format 3 (addendum 1 F)

**Les fragments** : un par (page, CIS, partie) dans la section `avis_has`, avec un identifiant
`f3/<cis>/avis_has/<page>/<partie>`.
- **Le texte** : la ligne d'identité, puis une ligne d'en-tête à nous (titre, dossier, date de
  l'avis, mise en ligne), répétées à chaque partie, puis les lignes de la page mot pour mot.
  Aucune URL dans le texte : elle va en métadonnée (`page`, `liens`).
- **La découpe** : 27 lignes de plus de 700 caractères ; la plus longue fait 1 781 caractères
  (`p_3700800`). Une ligne qui ne tiendrait pas se coupe donc entre deux phrases, mot pour mot :
  rejointe par une espace, elle redonne la ligne. Résultat : 1 198 caractères au plus et
  **381 jetons e5 au plus** (test du vrai modèle sur les 1 543 fragments).
- **Le contrôle de dossier** se fait fiche par fiche : chaque dossier de la fiche doit être nommé
  par le document d'avis. Il ne dépend pas des autres fiches, si bien qu'une mise à jour égale la
  reconstruction.

**Le rappel de la recherche** (`index evaluer`, hybride ; bon CIS, puis bon CIS et bonne section
à 1, 5 et 10 ; rang réciproque moyen) :

| index du jeu | v0 (22) CIS | v0 CIS+section | RRM | v1 (44) CIS | v1 CIS+section | RRM |
|---|---|---|---|---|---|---|
| sans avis, avgdl 53,29 (le format 2) | 21/22/22 | 12/20/21 | 0,675 | 42/44/44 | 28/40/43 | 0,753 |
| avec avis, avgdl 53,29 | 20/22/22 | 11/19/21 | 0,642 | 41/44/44 | 27/40/43 | 0,739 |
| **avec avis, avgdl 55,44 (retenu)** | 20/22/22 | **11/21/21** | 0,648 | 41/44/44 | **27/41/43** | 0,740 |

L'avgdl remesurée sur fiches et avis vaut 55,44 : 53,29 sur les fiches, 155,88 sur les avis.
Elle ne fait reculer aucun rappel à 10 et gagne au rappel à 5 (v0 19 → 21, v1 40 → 41) : je la
garde (F2). Ajouter les avis coûte un rang à 1 en v0 et en v1 : une partie d'avis passe devant
la fiche.

**La seconde horloge.** L'état porte `has` : la position du manifeste (150 lignes, empreinte du
préfixe), la dernière collecte (2026-10-31T13:07:40Z), l'extracteur v2, 149 pages extraites,
1 rejet (`dossier_incoherent`) et 5 contrôles impossibles. Elle se voit dans `index etat`. Les
refus sont tenus :
- la mise à jour refuse un préfixe changé, un autre extracteur, ou un index et des fragments
  qui ne lisent pas tous deux les pages ;
- la vérification exige la même position.

`make index` passe `--archive-has demo/archive`. `index etat --complet` rend le code 2 pour un
index d'un autre format, sans les pages d'avis ou d'un autre extracteur : `make index`
reconstruit alors l'index au lieu de le mettre à jour.

**Mémoire et durée** (`/usr/bin/time -l`) :

| commande | avant le réglage | après |
|---|---|---|
| `index fragments` du jeu (sous-processus) | 426 Mo sans avis | 428 Mo avec, 5,5 s |
| `index construire`, 1 543 textes à encoder | **586 Mo** | **493 Mo**, 133 s |
| `index construire`, tout en cache | 418 Mo | 261 à 281 Mo, 43 s |
| `index verifier` | **534 Mo** | **496 Mo**, 46 s, conforme (cosinus minimal 0,9964) |

Les deux réglages ne changent aucun vecteur :
- **la construction** encode les textes absents du cache **avant** d'écrire dans Qdrant, puis
  rend le modèle. Celui-ci se charge au premier besoin (`liberer`) ;
- **la vérification** réencode son échantillon **avant** de lire les points.

## 3. L'assistant (addendum 1 G)

**Ce qui n'est pas une retouche** (`07ac561`) :
- **Les liens**. Le code rend sous chaque citation la page d'avis avec ses trois dates (avis,
  mise en ligne ou mise à jour, consultation), ou les liens d'une fiche, et les deux horloges
  de l'index.
- **Aucune adresse au LLM**. Le texte de trois fragments d'avis cite `http://lecrat.fr/` : ce que
  reçoit le LLM la masque, l'index la garde.
- **Le contrôle** : une adresse écrite par le LLM rend son texte non vérifiable.

**Les retouches** (ce commit, après `bbb9809`) :
- **le prompt** : la date de chaque fait daté avec ce fait (G1) ; l'avis comme évaluation
  collective, jamais pour une personne ; aucune adresse ;
- **la déduplication** : une même (page, partie) pour plusieurs CIS n'occupe qu'une place. On
  garde le CIS visé, sinon le mieux classé, sur les 50 candidats de la fusion ;
- **le rappel par section** : la table, inchangée depuis `07ac561`, est branchée. Si aucun des
  dix fragments n'est d'une section demandée pour le CIS visé le mieux classé, sa première
  partie remplace le dernier fragment d'un autre CIS ;
- **les mots courants** : la liste, inchangée, est branchée. Un tel mot ne vise qu'avec le mot
  significatif qui le suit (« eau oxygénée », « chlorure (de sodium) Lavoisier ») ;
- **le refus de la posologie (G2)**. Trois questions médicales neuves échappaient aux règles
  (`medical-013`, `-014`, `-016`). La règle s'étend donc :
  - la dose, la durée, le rythme ou le mode de prise donnent un refus sans cadre de décision ;
  - la convenance pour une personne (« convient-il à ma mère ? ») aussi.

  L'extension est éprouvée sur la v0, la v1, la v2 et 200 questions factuelles : aucun faux
  refus. Un test de notation qui comptait sur une posologie échappant aux règles prend une autre
  question médicale.

**Mesure sans LLM** : pour chaque question qui vise une section, le fragment attendu (CIS,
section) figure-t-il dans les dix, avant et après les retouches ?

| jeu | trouvé avant et après | gagné | perdu | manqué avant et après |
|---|---|---|---|---|
| v1 (49 questions) | 48 | 0 | 0 | 1 (`avis_has-003`) |
| v2 (59 questions) | 54 | **3** (`avis_has-012`, `-013`, `-015`, par la déduplication) | 0 | 2 (`avis_has-003`, `-014`) |

Les 3 pièges des mots courants ne visent plus aucun médicament, et les 5 médicales sont refusées
par les règles. La date (G1) ne se mesure qu'avec le LLM, à l'évaluation du palier 3.

**Pourquoi le rappel ne se déclenche pas** pour `avis_has-003` (OZEMPIC) et `-014` (BIMZELX) :
la table, écrite avant les questions, envoie « SMR » vers `avis` **ou** `avis_has`. Un fragment
`avis_has` du bon CIS est déjà dans les dix (rang 5 pour OZEMPIC 1 mg, rangs 1, 2 et 8 pour
BIMZELX), donc la section demandée est tenue. Mais c'est la page d'un avis plus ancien : le
dernier SMR (CT-21716 pour OZEMPIC) n'est que dans le fragment `avis` de la BDPM. Je ne touche
pas à la table après coup (G : elle ne bouge pas sans le dire, et ces questions la mesurent).
**Question 1** : faut-il séparer les lignes de la table, « SMR », « ASMR » vers `avis` seul et
« avis », « HAS », « Commission » vers `avis_has` puis `avis` ? Ce changement se mesurerait sur
des questions neuves écrites avant lui, au palier 3.
**Question 2** : quand plusieurs CIS sont visés (les trois OZEMPIC), la cible est aujourd'hui
le mieux classé. Faut-il préférer celui dont la dénomination recouvre le plus la question
(« 1 mg ») ? Même condition de mesure.

## 4. Les questions neuves de la v2 (addendum 1 H)

`evaluation/questions-reference-v2.toml` (`bbb9809`, sha256 `c4d47c2a2c1c92f5faf473fdfbb75416252100f2bccbbe414320056a342962b2`) :
- les 88 questions de la v1 à l'identique (test) ;
- 18 questions neuves, dont l'empreinte `c11886b22076f341…` est fixée par
  `tests/test_questions_v2.py` :
  - **dix tirées par une règle sans LLM** (`evaluation/choisir_neuves_v2.py`) : rappel
    `avis_has-012` à `-015` (675 CIS examinés par la recherche seule, 4 sans leur fragment
    `avis` dans les dix) ; dates d'avis `avis_has-016` à `-018` ; dates de mise à jour
    `disponibilite-013` à `-015` ;
  - **trois pièges** de mots courants : `hors_perimetre-012` à `-014` ;
  - **cinq médicales**, avec les mots d'un avis : `medical-012` à `-016`, dont G2.

`questions verifier` sur la v2 : 106 questions, 60 conformes, 60 concordent avec le gold.

## 5. Le coût (addendum 1 I)

`budget` passe à la mission 9, au plafond de 10 $ et à 1,7 caractère par jeton.
`assistant evaluer --estimer`, sans clé ni appel :

| jeu | appels à faire | estimation prudente | probable (coût moyen constaté) | résident |
|---|---|---|---|---|
| v1 | 62 (26 décidées hors LLM) | 6,10 $ | 0,98 $ | 463 Mo |
| v2 | 75 (31 hors LLM) | 7,42 $ | 1,19 $ | 469 Mo |

Lancée après la v1, la v2 relit du cache les 62 appels communs et n'en ajoute que 13. La
constante se vérifie sur les appels de la démonstration (I1).

## 6. La démonstration de beko (décision 7)

L'index du jeu est déjà au format 3 dans le Qdrant du Mac : je l'ai construit pour les mesures,
et `index verifier` le dit conforme. Depuis `pharmaflux-codeur/`, dans Terminal.app :

```bash
uv run pharmaflux index etat
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "Que dit l'avis de la Commission de la transparence sur KALYDECO 13,4 mg, granulés en sachet ?"
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "Quel progrès MOUNJARO apporte-t-il selon l'avis de la Commission de la transparence ?"
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "Quel SMR la Commission de la transparence a-t-elle rendu pour MOUNJARO dans le dossier CT-21681 ?"
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "Où en est l'approvisionnement de LARIAM 250 mg, comprimé sécable ?"
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "Quelle est la durée du traitement par KALYDECO selon l'avis ?"
uv run pharmaflux assistant depenses
```

Ce que chaque question vise :
- deux portent sur le texte d'un avis : lien et dates rendus, déduplication des douze CIS de
  MOUNJARO ;
- une sur une date due avec un SMR, une sur un statut de disponibilité daté ;
- un refus médical par les règles, sans appel.

Aucune n'appartient aux jeux v1 ou v2. Coût attendu : 4 appels, environ 0,10 $ probables, sous
0,45 $ à l'estimation. Si l'index n'était plus au format 3, il faudrait `make index` d'abord.

## 7. Vérifications locales

Commit testé : celui-ci, arbre propre hors de `data/`.

| vérification | résultat |
|---|---|
| `uv run ruff check .` ; `ruff format --check .` | verts ; 322 fichiers formatés |
| `uv run mypy src` | 89 fichiers, aucune erreur |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **889 passés**, 6 min 31 s |
| `pytest -m "integration or modele"` | 18 passés (vrai Qdrant, vrai modèle, dont les 1 543 fragments d'avis sous 512 jetons) |
| aucune requête réseau dans les tests | la garde de session (`tests/conftest.py`, `reseau_coupe`) ; aucune requête vers la HAS depuis le palier 1 |
| `make -n index`, `make -n demo` | corrects ; `index` passe `--archive-has demo/archive` |
| crochets git ; garde-fou | conformes ; OK |
| YAML de la CI | `ci.yml` touché (index réduit avec les pages d'avis) : lu par `yaml.safe_load`, et relu par le crochet au commit |
| `demo verifier` | conforme, deux parties, 150 pages |
| `questions verifier` v1 ; v2 (jeu de démo) | 50 concordent ; 60 concordent |
| `profil --racine ~/pharmaflux-data` | 11 fichiers, 0 anomalie bloquante |
| `index verifier` (jeu de démo, vrai modèle) | conforme, 73 839 points, cosinus minimal 0,9964 |
| `evenements`, `silver`, `gold`, bus, contrats, collecte | aucun changement de code depuis `dff0a34` (`git diff --stat` vide) |
| `assistant depenses` | mission 9 : 0 appel, 0 $ ; reste 10 $ |
