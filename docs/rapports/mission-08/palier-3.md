# Mission 08 — palier 3 : notation, évaluation, `Makefile`, docs (décisions 4, 5, 7)

**Codeur** : Claude Opus 5.5, en session neuve depuis `4f827cb` (addendum 2). J'ai lu, dans
l'ordre de la consigne, l'ordre et ses addenda 1 et 2 sur `main`, `points-a-trancher.md`, les
rapports des paliers 1 et 2, puis les contrôles des paliers 1 et 2. **Aucun appel réel n'est
parti de ma session.** Ma session n'a pas de clé : seule `ANTHROPIC_BASE_URL`, la variable du
harnais, y est posée, et `cle_presente()` reste faux. Tout passe par le double, ou par
`--estimer`, qui n'appelle rien. Le garde-fou a refusé une seule commande, `awk` sur le PRD
(chemin réservé) : je l'ai relu par `grep` et `sed -n`, qu'il autorise. J'ai posé trois
questions à l'IeC par message (la notation, les cinq questions sans réponse possible, les
dates). Il les a acceptées avec des conditions, et en a posé d'autres sur le correctif « deux
médicaments » (point 6). **Deux commits** : `c4ddec8` porte le palier ; le commit de ce
rapport porte les conditions de l'IeC, reçues après (dates, raisons des colonnes, comptes par
catégorie, tests aléatoires et bornes). Je ne réécris pas l'historique.

## Fait

1. **La notation déterministe** (`assistant/notation.py`, sans juge LLM). Une réponse attendue
   est **correcte** si cinq conditions tiennent :
   - le comportement est l'attendu ;
   - toutes les **valeurs dues** de l'attendu paraissent dans le texte ;
   - une citation valide pointe le CIS attendu, et la section attendue quand elle est donnée ;
   - aucun mot interdit n'y paraît, en mots entiers, accents dépliés ;
   - la réserve est dite quand la question l'attend.

   Une citation est **valide** si son étiquette est parmi les fragments fournis, avec le même CIS
   et la même section. Il y a deux **conditions dures** : aucune citation invalide, et aucune
   question `medical` sans refus. Elles seules donnent le code 1.

   Les valeurs dues sont celles des colonnes que **le texte des fragments rend**. Deux tables du
   code classent chaque colonne et disent en une ligne pourquoi : où le texte la rend, ou pourquoi
   il ne la rend pas. La seule raison admise pour « non due » est l'absence du texte des
   fragments ; une valeur mal rendue par le LLM n'en est jamais une, et aucune colonne ne change
   de classe après une mesure (décision de l'IeC, Q1). Une colonne non classée arrête la notation,
   et un test exige que toutes les colonnes des attendus v1 soient classées.

   **Les valeurs dues de la v1, par catégorie** : 114 sur les 49 réponses attendues.

   | catégorie | réponses attendues | valeurs dues |
   |---|---|---|
   | disponibilite | 10 | 24 |
   | alternatives | 10 | 20 |
   | remboursement | 11 | 17 |
   | avis_has | 9 | 34 |
   | historique | 9 | 19 |

   Le nombre de valeurs **retrouvées** dépend des réponses du LLM. `assistant evaluer`
   l'écrit, par catégorie, à la ligne « valeurs dues retrouvées » : il viendra de l'évaluation
   de beko.

   La comparaison dépend de la nature de la valeur :
   - une date, sous toute graphie, par le normaliseur du contrôle ;
   - un nombre, sous sa forme canonique ;
   - un libellé, en suite de mots entiers ;
   - un CIS, écrit dans le texte ou porté par une citation valide.

   Une paraphrase compte comme absente : c'est une borne basse, et chaque note nomme ce qui
   manque. Les indicateurs sont ceux du PRD §2.2 :
   - les réponses correctes ;
   - les questions traitées justement ;
   - les réponses qui citent une source et sa date. C'est l'indicateur officiel de l'addendum.
     Un second chiffre l'éclaire : les réponses qui citent au moins une source, l'instant de
     l'index étant toujours rendu. **Dit en clair** : le fragment « aucun signalement » de
     `disponibilite-004` n'a qu'une source **non datée** (`CIS_CIP_Dispo_Spec.txt`, par
     construction de l'index : une absence de ligne n'a pas de date de fichier). Même juste,
     cette réponse manque donc l'indicateur officiel, qui ne peut pas atteindre 100 % sur la v1 ;
   - l'abstention hors périmètre et sur les questions médicales ;
   - les abstentions et refus justes, et les faux refus ;
   - les abstentions techniques, comptées à part ;
   - le coût total, par question, et pour 1 000 questions.
2. **`assistant evaluer` et sa porte budgétaire** (`assistant/evaluation.py`).
   - **Les préconditions (E1)** : le jeu est une v1, l'index est à l'instant qu'elle déclare et il
     n'est pas réduit. Sinon, code 2.
   - **La préparation** : toutes les questions passent par `chemin.preparer`, sans LLM ni dépense.
     Le dictionnaire du repérage n'est chargé qu'une fois.
   - **La porte (G2)** : la somme des estimations des appels qui ne sont pas au cache (l'entrée au
     caractère, et `max_tokens` entier en sortie) est calculée **avant le premier appel**. Rien ne
     part si elle dépasse le reste.
   - **Les appels et la notation** : chaque question est ensuite appelée, contrôlée et notée. La
     commande écrit une ligne par question au fil de l'eau, puis les indicateurs. Le détail va en
     JSON Lines sous `data/assistant/evaluations/`.
   - **Sans clé** : `--estimer` s'arrête après la porte, sans clé ni appel, et sans
     `count_tokens`. Un test le garantit : aucune variable `ANTHROPIC_*`, toute connexion réseau
     refusée, le client réel interdit de construction, et aucune ligne au journal. Une évaluation
     toute en cache ne demande pas la clé : on peut donc **re-noter sans dépense** après le
     passage de beko.

   Le chemin est découpé en `preparer` puis `conclure` (`demander` enchaîne les deux), et une
   `Citation` porte désormais `source_datee`.
3. **L'ADR 0012**. Elle couvre :
   - la recherche hybride : tokenizer, BM25 aux constantes figées, IDF par Qdrant, format 2, et
     **RRF côté client** avec ses raisons ;
   - le chemin, le LLM, le contrôle, le budget et le cache ;
   - la notation ;
   - ce que l'assistant ne fait pas ;
   - les options écartées.
4. **`make evaluer`, et `make rebatir` qui épargne `data/assistant`.**
   - `make evaluer` n'est enchaînée par aucune cible et ne va pas dans la CI ;
     `EVALUER_OPTIONS=--estimer` la chiffre sans clé.
   - `tests/test_makefile.py` développe les variables du `Makefile` et vérifie qu'aucune ligne
     `rm` n'efface `data/assistant`, `data` ni un de ses parents. Il vérifie aussi `make -n
     rebatir`, et qu'aucune cible n'enchaîne `evaluer`. L'aide de `make` le dit.
5. **Les remarques du contrôle du palier 2.**
   - **Le cache du prompt** : la remarque est déjà réglée au palier 2. Il est effectif, 923 jetons
     écrits puis relus.
   - **Une abstention ou un refus rendus par le LLM** passent le même contrôle des nombres et des
     dates qu'une réponse. En cas d'échec, le code remplace le texte, le motif et l'orientation
     par les siens. Un refus prend toujours la forme du code : son texte, l'orientation vers un
     médecin ou un pharmacien, aucune citation.
   - **Une erreur de l'API** (`anthropic.APIError` : surcharge, délai, réseau) devient
     `ErreurAPI`, que `demander` et `evaluer` rendent en code 2 avec une ligne lisible. Rien
     n'est journalisé, puisque rien n'est payé.
   - **`pyproject.toml`** : l'override mypy d'`anthropic` est **retiré** plutôt que raccourci. Le
     SDK porte ses types (`py.typed`), et `mypy src` reste vert sans lui.
6. **Un défaut du palier 2, trouvé par `--estimer` sur le vrai index et corrigé** (écart
   déclaré, voir plus bas). La règle « deux médicaments » s'abstenait à tort sur **18 des 54
   réponses attendues**. Le correctif (`repere.py`) :
   - **Les mots de forme ne nomment pas un médicament.** Ils sont tirés des dénominations
     elles-mêmes : ce qui suit la dernière « , », sans les parenthèses.
   - **Un médicament est nommé** quand tous les mots significatifs de son nom sont dans la
     question. Un nom contenu dans un autre nom nommé ne compte pas à part.
   - **L'exception « groupe »** ne vaut que si les noms nommés tiennent dans le libellé d'un
     même groupe générique de l'index. Les libellés sont lus dans le texte des fragments
     `identite`. La borne est testée : sans « groupe », « groupe » avec deux spécialités sans
     lien, deux groupes génériques distincts, ou deux groupes et leurs princeps donnent bien deux
     médicaments ou plus.
   - **Un CIS explicite** qui désigne un médicament déjà nommé ne compte plus deux fois.

   Les tests qu'a demandés l'IeC sont faits :
   - **200 médicaments tirés au hasard** (graine fixe, `demo/archive`, sans réseau) parmi les
     15 816 dénominations du jeu de démo qui ont un mot significatif. Pour chacun :
     - seul (« <dénomination> est-il en rupture de stock ? ») : **0 déclenchement sur 200**
       (0 %), et les 200 sont repérés ;
     - avec son voisin dans le tirage (« <A> ou <B> : lequel est remboursé ? ») :
       **200 déclenchements sur 200** (100 %).

     La règle à deux mots du palier 2 se déclenchait à tort sur 31 des 200 posés seuls.
   - **La v1** ne déclenche la règle que sur le piège `disponibilite-010`, et **la v0** jamais.
     Le vrai index donne la même chose.
7. **Le contrôle des dates** (décision de l'IeC, Q3) :
   - il lit les dates de 1900 à 2099, puisque les AMM remontent à 1978 ;
   - l'année d'une date d'appui devient un nombre appuyé, et un mois sans jour (« juin 2026 »)
     se vérifie contre les couples (année, mois) des dates d'appui. Un mois faux échoue, et une
     date d'AMM fausse aussi ;
   - **le jour et le mois sans année ne sont jamais appuyés** (« le 25 », « le 25 juin ») ;
   - **la forme compacte « AAAAMMJJ » ne se lit plus que dans une valeur attendue** (la
     notation, `compacte=True`). Dans un texte, elle se confond avec un montant à huit chiffres
     (« 20101010 » se lirait 10/10/2010). Le texte des fragments rend ses dates en ISO : le vrai
     fragment du CIS 67026956 dit « 2026-09-09 : Important », jamais « 20260909 », qui n'est que
     la forme brute de la v1. Le test du palier 2 qui posait un fragment « 20260909 » est aligné
     sur le vrai texte. La remarque du palier 1 (relier « 9 septembre 2026 » à la forme du
     fragment cité) reste tenue, et testée ;
   - un test vérifie qu'un CIS en 6…, un CIP13 et un montant à huit chiffres ne sont jamais lus
     comme une date par le contrôle.

   Chaque règle est testée dans les deux sens : appuyé, donc accepté ; non appuyé, donc
   abstention.
8. **Le jeu v1** (décision de l'IeC, Q2). Cinq questions dont la valeur n'est pas dans le texte
   des fragments passent en **abstention**, sous le même identifiant et avant toute évaluation
   réelle, avec leur motif et leur orientation :
   - `historique-003` et `-008` (la date de déclaration de commercialisation) ;
   - `avis_has-004` et `-009` (le lien de l'avis) ;
   - `remboursement-010` (l'agrément aux collectivités).

   Le jeu compte désormais 49 réponses, 28 abstentions et 11 refus. Un commentaire garde chaque
   ancienne valeur et son archive. La `description` du fichier disait « quatre-vingt-neuf »
   pour 88 questions : c'est corrigé.
9. **Les deux tests de l'addendum D2 sur la v1 entière manquaient.** La docstring de
   `regles.py` les annonçait, mais aucun test ne lisait la v1. Ils sont écrits : chaque `medical`
   est refusée par les règles, aucune autre question ne l'est. Le test « clé absente » retire
   maintenant **toutes** les variables `ANTHROPIC_*`.
10. **Le prompt système** demande deux choses de plus, des consignes générales et non tirées
    d'une question :
    - écrire « aucun signalement à cette date », sans jamais employer « disponible » (ADR 0003) ;
    - reprendre les statuts, les libellés et les valeurs tels que les fragments les donnent.

    Les trois réponses de la démonstration, en cache, ne servent donc plus. Leur clé change, et
    il en coûte trois appels, environ 0,04 $.
11. **Les docs** :
    - le README : l'état, l'exemple hybride de l'index, la section « L'assistant » avec deux
      sorties réelles de la démonstration (une réponse citée et datée, un refus médical) et les
      commandes ;
    - `evaluation/README.md` : la v1 et sa notation ;
    - `docs/CONTEXTE.md` : la section de l'assistant ;
    - `docs/journal.md`.

## L'évaluation complète, pour beko

Chiffrée sur le vrai index, **sans clé et sans appel** :

```
évaluation v1 : 88 questions, index au 2026-10-27T00:17:12Z, modèle claude-opus-5-5, effort low
porte budgétaire : 88 questions, 26 décidées hors LLM, 0 en cache, 62 appel(s) à faire
  estimation prudente 5.3985 $ (max_tokens entier en sortie) ; probable 0.8919 $ (au coût moyen constaté de 0.0144 $ par appel)
  déjà dépensé 0.0432 $, reste 19.9568 $ sur 20.00 $ : accordée
```

**Le coût** : 62 appels, **5,40 $ au pire** et environ **0,89 $ au coût moyen constaté** sur la
démonstration. Après l'évaluation, la mission aura dépensé moins de 1 $ en probable, et moins de
5,50 $ au pire, sur 20 $. Les 26 questions décidées hors LLM sont les 11 refus, les
14 abstentions des règles et le piège « deux médicaments ».

**La mémoire et le temps** (I) :
- `--estimer` tient en 439 Mo, puis 462 Mo sur une seconde mesure, et 11 s
  (`/usr/bin/time -l`). L'écart entre deux mesures est de l'ordre de celui de l'ADR 0011 ;
- le chemin complet, SDK importé, plafonne à 419 Mo, mesuré avec un faux client sans réseau ;
- un seul processus suffit.

**La séquence de clôture**, dans `pharmaflux-codeur/`, depuis Terminal.app :

```bash
make rebatir && make demo && make silver && make gold && make index
uv run pharmaflux assistant evaluer --estimer      # doit redonner 62 appels, rien n'est appelé
sh ../pharmaflux/infra/agents/avec-cle.sh make evaluer
uv run pharmaflux assistant depenses
```

`make rebatir` garde `data/assistant` (le journal) et `data/index` (le cache des vecteurs).
`make index` reconstruit donc au format 2 en reprenant les vecteurs, au même instant. **Ce qu'il
me faut** : la sortie entière de `make evaluer`, et celle de `depenses`. Le détail, sous
`data/assistant/evaluations/`, je le lis dans mon dossier. Si un indicateur appelle une
explication, une nouvelle notation se rejoue sur le cache, sans dépense.

## `make -n` des cibles nouvelles ou modifiées

```
$ make -n evaluer
uv run pharmaflux assistant evaluer --questions evaluation/questions-reference-v1.toml \
		--modele e5-small-int8
$ make -n evaluer EVALUER_OPTIONS=--estimer
uv run pharmaflux assistant evaluer --questions evaluation/questions-reference-v1.toml \
		--modele e5-small-int8 --estimer
$ make -n rebatir                     # recette inchangée, commentaire et aide ajoutés
docker compose -p pharmaflux down -v
rm -rf data/demo
make up
sh infra/demo/prerequis.sh
docker compose -p pharmaflux up -d --wait --pull never
```

`make help` gagne trois lignes pour `evaluer`, et une pour ce que `rebatir` garde.

## Vérifications locales (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / tous les fichiers formatés |
| `uv run mypy src` | Success: no issues found in 78 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` (Qdrant, Redpanda et modèle présents) | **705 passed** en 6 min 37 (657 au départ du palier, 703 sur `c4ddec8`), intégration et modèle compris, aucun saut ; session verte, **0 réessai du registre** |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK (21 tests) |
| `questions verifier` v1, `--racine demo/archive --entrepot data/demo/lakehouse` | 88 : 50 conformes, 10 non calculables, 28 sans attendu ; 50 depuis le gold : 50 concordent |
| `questions verifier` v0, `--racine demo/archive --entrepot data/demo/lakehouse` | 40 : 25 conformes, 5 non calculables, 10 sans attendu ; 25 depuis le gold : 25 concordent |
| `demo verifier` / `gold qualite` sur le jeu | conforme / 14 contrôles à 2026-10-27T00:17:12Z, aucun bloquant ne tombe |
| `assistant evaluer --estimer` (vrai index, sans clé), avant et après les conditions de l'IeC | 62 appels, 0 en cache, 5,3985 $ prudent, 0,8919 $ probable ; 439 puis 462 Mo, 11 s |
| `pharmaflux assistant depenses` | mission 8 : 3 appel(s), 0,0432 $ ; reste 19,9568 $ |

L'index, le gold, le silver, les événements et le bus n'ont pas changé depuis le palier 1 (ni
leur code, ni leurs données). La construction et `index verifier` restent ceux du palier 1, et
ne sont pas rejoués ici.

## Écarts à l'ordre

- **Le correctif « deux médicaments »** (point 6) corrige le palier 2, accepté. C'est un
  **correctif trouvé en passant la v1 sans LLM** (`--estimer`) : une mesure de développement. Le
  « 0 faux positif sur la v1 » ne prouve donc rien seul. La preuve est hors du jeu, sur
  200 médicaments tirés au hasard : 0 % de déclenchements seuls, 100 % deux par deux. La règle
  du palier 2 s'y trompait 31 fois. L'exception « groupe », la seule tirée d'un mot des
  questions, est bornée par les libellés de groupe de l'index, et testée. La v0 est vérifiée en
  non-régression.
- **Cinq questions de la v1 passent en abstention** (point 8), sur décision de l'IeC. Le
  changement est **tiré de la structure des fragments** (ce que leur texte rend ou ne rend pas),
  **avant toute évaluation réelle** : aucun résultat du LLM n'a guidé ce choix. `questions
  verifier` v1 et v0 restent verts.
- **La forme compacte des dates** ne se lit plus que dans une valeur attendue (point 7). Le test
  du palier 2 qui posait un fragment « 20260909 » est aligné sur le vrai texte des fragments.
- **Le prompt système change** (point 10) : deux consignes générales, et trois réponses en cache
  à repayer.
- **L'override mypy d'`anthropic` est retiré** au lieu d'être raccourci (point 5).

## Questions pour l'IeC

Aucune : les trois questions du palier sont tranchées par message (Q1 à Q3).

## Propositions d'évolution (PRD, consignes)

- **La mission 10** pourrait faire rendre par le code, sous la réponse, les liens des fragments
  cités (la fiche ANSM, la page de l'avis), comme il rend déjà leurs sources. `avis_has-004` et
  `-009` redeviendraient alors des réponses.
- **Le modèle de rapport** (« quinze lignes au plus ») n'est plus tenu depuis plusieurs
  missions. Le relever ou le relâcher dans `docs/agents/processus.md` serait plus honnête.
