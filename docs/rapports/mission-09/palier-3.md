# Mission 09 — palier 3 : la table des sections, la mémoire, le jeu v2 complet, l'ADR 0013

## Synthèse

**Fait**, suivant le contrôle du palier 2 :
- **Question 1 de l'IeC.**
  - `c80b795` : cinq questions tirées par une règle écrite, sans LLM, et figées par un test
    (`avis_has-019` à `-023`) ;
  - `5bbf3a8` : le changement de la table, seul.

  Mesure sans LLM : **4 des 5 questions retrouvent leur fragment `avis`** ; `-020` (WEGOVY) ne
  le retrouve pas, c'est la limite de la question 2. Aucune autre question ne perd le sien.
- **La mémoire sur la première étape entière** (721 pages, 78 461 fragments, dans un espace
  Qdrant à part, puis effacé) : `index construire` 471 Mo, `index verifier` 483 Mo, conforme.
  **Sous 512 Mo**, rien n'est ajusté. L'index du jeu est intact.
- **Le jeu v2 complet** (`fa8a5be`) : 138 questions.
  - Les 88 de la v1, dont trois comportements changent.
  - 50 nouvelles : 18 et 5 figées, 19 sur le texte tirées par une règle, 4 pièges, 3 qui
    demandent le PDF, 1 comparaison.
  - L'attendu `attendu_has` se vérifie sans gold, et la notation ajoute le lien, la date de
    l'avis et l'extrait.
- **Docs** (ce commit) : l'ADR 0013, la ligne « complété par » de l'ADR 0004, le profil de la
  page d'avis, le README de l'évaluation, `CONTEXTE.md`, le journal, l'état du README.
  `make evaluer` prend `JEU_QUESTIONS`.

**Vérifications locales** (commit testé : `fa8a5be` pour le code, ce commit n'ajoute que des
docs et le Makefile) : vertes, **909 tests**.
**Reste à beko** :
- la démonstration du palier 2, que l'IeC lui a transmise ;
- l'évaluation de la v1 **puis** de la v2, avec les commandes du §4.

Je cite chacune dans un commit à part. L'exemple réel de réponse du README vient de la
démonstration.
**Écarts** : la v2 seule passe la porte budgétaire au pire (10,55 $ pour 10 $). Elle se lance
**après** la v1, dont elle relit 62 appels du cache (§4).
**Questions pour l'IeC** : aucune. **Propositions** : aucune.

## 1. La table des sections (question 1 du palier 2)

**La règle** (`evaluation/choisir_neuves_v2_table.py`, écrite et committée avec ses questions,
avant le changement) porte sur les CIS que la v2 ne vise pas encore. Elle retient ceux dont le
dernier SMR (3 questions) ou le dernier ASMR (2) n'est que dans le fragment `avis`, alors qu'un
fragment `avis_has` plus ancien du même CIS est dans les dix que le chemin fournit. 26 CIS
examinés, 5 retenus. Empreinte `33890d4817f17b46…`, fixée par `tests/test_questions_v2.py`.

**Le changement** (`5bbf3a8`, `sections.py` et ses tests seulement) :
- « SMR » et « ASMR » demandent `avis` seul ;
- « Commission de la transparence » et « HAS » demandent `avis_has` puis `avis` ;
- le mot « avis » ne demande plus rien. Avec l'union des lignes, le garder aurait fait demander
  encore `avis_has` à « dernier avis de SMR ».

**La mesure** (sans LLM : le fragment attendu est-il dans les dix ?) :

| question | avant | après | par |
|---|---|---|---|
| `avis_has-019` BENLYSTA 400 mg (SMR) | non | **oui** | le rappel |
| `avis_has-020` WEGOVY 0,5 mg (SMR) | non | non | la cible est WEGOVY 0,25 mg, le CIS visé le mieux classé (limite, question 2) |
| `avis_has-021` BENLYSTA 120 mg (SMR) | non | **oui** | le rappel |
| `avis_has-022` OZEMPIC 0,5 mg (ASMR) | non | **oui** | le rappel |
| `avis_has-023` RETSEVMO 40 mg (ASMR) | non | **oui** | le rappel |
| v1 et v2 (questions qui visent une section) | — | aucune perte | — |

`avis_has-003` et `-014` ne comptent pas (ils ont servi à trouver le défaut). `-014` est rendu ;
`-003` (OZEMPIC 1 mg) ne l'est pas, pour la même raison que `-020`. **C'est la dernière retouche
du rappel dans cette mission.**

## 2. La mémoire sur la première étape entière

`--archive-has ~/pharmaflux-data` (lu, jamais écrit), sur l'entrepôt du jeu, dans l'espace
Qdrant `pharmaflux-mesure-has`. Les commandes sont celles de la CLI, appelées par un script de
mesure qui ne fait que changer l'espace. L'espace est effacé ensuite, et `index etat` du jeu est
inchangé (format 3, 73 839 fragments).

| commande | résultat | résident (encodage ; sous-processus) | durée |
|---|---|---|---|
| `index construire` | 78 461 fragments, dont 6 165 d'avis ; 4 622 textes encodés, le reste du cache ; 721 pages extraites, 1 rejet, 10 contrôles impossibles | **471 Mo ; 421 Mo** | 348 s |
| `index verifier` | conforme, 0 écart, cosinus minimal 0,9960 | **483 Mo ; 411 Mo** | 55 s |

## 3. Le jeu v2 complet

| bloc | identifiants | comment |
|---|---|---|
| la v1 | 88 | au même texte. `disponibilite-005` devient une réponse avec réserve ; `avis_has-004` et `-009` se notent par le lien rendu (`c_2027377`, `p_3577036`) |
| correctifs de la mission 08 | `bbb9809`, 18 | intacts (empreinte) |
| la table | `avis_has-019` à `-023` | intacts (empreinte) |
| le texte des avis | `avis_has-024` à `-042` | `choisir_texte_v2.py` : pages du jeu par sha256 de « texte/<page> », hors pages imposées ; nature 4, date 4, « L'essentiel » 4, « Quel progrès ? » 4, lien 3 ; chacune attend le lien rendu et la date de l'avis |
| les pièges | `-043` à `-046` | ADEMPAS : la décision de 2025, plus récente que la date du dossier dans la BDPM ; OZEMPIC CT-21716 sans page ; DOLIPRANE 2015 hors corpus ; PEDMARQSI rejetée |
| le PDF | `-047` à `-049` | le vote, la population cible, les comparateurs ; absents des pages (vérifié), abstention motivée |
| la comparaison (G3) | `-050` | MOUNJARO contre TRULICITY : abstention |

`questions verifier` (jeu de démo) : 138 questions, **87 conformes** (dont les 20 pages d'avis,
vérifiées sans gold), 10 non calculables, 41 sans attendu ; **67 concordent avec le gold**.

**La notation** ajoute :
- `lien_rendu` : la page rendue sous la réponse par une citation valide, depuis ses liens ou la
  page d'un fragment `avis_has` ;
- la date de l'avis et l'extrait, dus.

Les indicateurs de la v2 se rendent en deux blocs : les questions nouvelles seules, puis la v2
entière. La v1 se note par son fichier.

`medical-013`, `-014` et `-016` ont servi à étendre la règle de refus : `pr.md` le dira en
rendant le score des questions médicales neuves.

## 4. L'évaluation de beko

Après la démonstration, depuis `pharmaflux-codeur/`, dans Terminal.app. L'index du jeu est à
jour : `make index` n'aurait rien à faire, et l'option est passée de toute façon.

```bash
make evaluer EVALUER_OPTIONS=--estimer
sh infra/agents/avec-cle.sh make evaluer
make evaluer JEU_QUESTIONS=evaluation/questions-reference-v2.toml EVALUER_OPTIONS=--estimer
sh infra/agents/avec-cle.sh make evaluer JEU_QUESTIONS=evaluation/questions-reference-v2.toml
uv run pharmaflux assistant depenses
```

| étape | appels | au pire | probable |
|---|---|---|---|
| v1 | 62 | 6,10 $ | environ 1,0 $ |
| v2, après la v1 | environ 43 nouveaux (62 relus du cache) | environ 4,3 $ | environ 0,7 $ |

La v2 lancée seule demande 105 appels, 10,55 $ au pire : la porte la refuse. **L'ordre compte.**
Les deux sorties, le détail JSON Lines et `assistant depenses` seront cités dans un commit à
part, avec la vérification de la constante 1,7 sur les appels réels (I1).

## 5. Vérifications locales

| vérification | résultat |
|---|---|
| `uv run ruff check .` ; `ruff format --check .` ; `uv run mypy src` | verts |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` (sur `fa8a5be`) | **909 passés**, 6 min 35 s |
| `questions verifier` v2 ; v1 | 87 conformes, 67 concordent ; 50 concordent |
| `assistant evaluer --estimer` v2 | 138 questions, 33 hors LLM, 105 appels, 10,55 $ au pire (seule), 400 Mo |
| `make -n evaluer`, avec et sans `JEU_QUESTIONS` | corrects |
| mémoire sur la première étape | 471 et 483 Mo (§2) |
| `index etat` du jeu après la mesure | inchangé |
