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
médicaments » (point 6). **Les commits du palier**, sans réécriture de l'historique :
- `c4ddec8` : le palier ;
- `f6b1d67` : les conditions de l'IeC, reçues après (les dates, les raisons des colonnes, les
  comptes par catégorie, les tests aléatoires et les bornes) ;
- `37375dd` : le premier point du contrôle (le classement éprouvé contre `fragments.py`) ;
- `2891e98` : **le commit de clôture**, le correctif des étiquettes trouvé par l'évaluation
  réelle ;
- le commit de ce rapport, qui ne porte que les docs.

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

**La séquence de clôture**, dans `pharmaflux-codeur/`, depuis Terminal.app. `make rebatir`
lance `docker compose -p pharmaflux down -v` : il **efface les volumes Qdrant et Redpanda du
projet `pharmaflux`** (rien d'Alamel), comme l'ordre le veut, et garde `data/index` et
`data/assistant`.

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

## Le contrôle du palier 3 (accepté) : ce qui est fait avant la clôture

1. **Le classement des colonnes est éprouvé contre le texte que rend vraiment
   `fragments.py`** (`test_le_classement_des_colonnes_est_vrai`). Les fiches du gold du jeu de
   démo, à l'instant de la v1, passent par `index.fragments`. Les **114 valeurs dues** des
   **49 réponses attendues** se retrouvent toutes, par la comparaison de la notation, dans le
   texte des fragments de leur CIS et de leur section. Aucune valeur hors texte des fiches
   elles-mêmes n'y paraît : prix hors honoraires, honoraires, date de déclaration, agrément, rang
   de tri, liens d'avis, liens ANSM. Le test compte ce qu'il examine, pour ne jamais passer à
   vide. **Le classement est vrai** : aucune colonne ne change de table, et aucune nouvelle
   notation n'est nécessaire.
2. **La sortie de beko** sera citée ici, puis dans `pr.md`, une fois l'évaluation lancée : la
   sortie entière de `make evaluer` et de `depenses`, les indicateurs du §2.2, les deux conditions
   dures, les abstentions techniques, et la raison de chaque question fausse.

Le fichier du contrôle est committé tel quel.

## L'évaluation complète, lancée par beko (30/10/2026, 23:05 UTC)

**La séquence**, sur le Mac, depuis `pharmaflux-codeur/` au sommet `37375dd`, jusqu'à `make
index`. Tout est vert :
- `make rebatir` : volumes Qdrant et Redpanda du projet effacés puis recréés ;
- `make demo` : 22 archives rejouées, 18 publiées, 4 écartées ; `verifier-bus` conforme ;
- `make silver` : 164 106 messages ; `silver verifier` 22/22 conformes ;
- `make gold` : 14 contrôles, aucun bloquant ne tombe ; 25 questions v0 concordent depuis le gold ;
- `make index` : 72 296 fragments, 0 encodé, 72 296 repris du cache, en 39 s (412 et 421 Mo).
  `index verifier` est conforme : 0 manquant, 0 orphelin, 0 écart de texte, de vecteur ou de
  vecteur creux, cosinus minimal 0,9964.

**La sortie entière de `make evaluer` et de `depenses`** (seule la ligne de commande de
l'invite est abrégée) :

```
$ uv run pharmaflux assistant evaluer --estimer
évaluation v1 : 88 questions, index au 2026-10-27T00:17:12Z, modèle claude-opus-5-5, effort low
porte budgétaire : 88 questions, 26 décidées hors LLM, 0 en cache, 62 appel(s) à faire
  estimation prudente 5.3985 $ (max_tokens entier en sortie) ; probable 0.8919 $ (au coût moyen constaté de 0.0144 $ par appel)
  déjà dépensé 0.0432 $, reste 19.9568 $ sur 20.00 $ : accordée
$ sh ../pharmaflux/infra/agents/avec-cle.sh make evaluer
uv run pharmaflux assistant evaluer --questions evaluation/questions-reference-v1.toml \
		--modele e5-small-int8 
évaluation v1 : 88 questions, index au 2026-10-27T00:17:12Z, modèle claude-opus-5-5, effort low
porte budgétaire : 88 questions, 26 décidées hors LLM, 0 en cache, 62 appel(s) à faire
  estimation prudente 5.3985 $ (max_tokens entier en sortie) ; probable 0.8919 $ (au coût moyen constaté de 0.0144 $ par appel)
  déjà dépensé 0.0432 $, reste 19.9568 $ sur 20.00 $ : accordée
disponibilite-001    reponse → reponse (llm) : correcte [0.0192 $]
disponibilite-002    reponse → reponse (llm) : correcte [0.0139 $]
disponibilite-003    reponse → reponse (llm) : correcte [0.0195 $]
disponibilite-004    reponse → reponse (llm) : correcte [0.0111 $]
disponibilite-005    abstention → abstention (controle) : juste [0.0172 $]
disponibilite-006    reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque libelle_statut = Tension d'approvisionnement ; manque date_debut = 20/10/2026 [0.0194 $]
disponibilite-007    reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque libelle_statut = Tension d'approvisionnement ; manque date_debut = 01/10/2026 ; manque date_mise_a_jour = 14/10/2026 [0.0193 $]
disponibilite-008    reponse → reponse (llm) : correcte [0.0149 $]
disponibilite-009    reponse → reponse (llm) : correcte [0.0197 $]
disponibilite-010    abstention → abstention (deux_medicaments) : juste [hors LLM]
disponibilite-011    reponse → reponse (llm) : correcte [0.0153 $]
disponibilite-012    reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque libelle_statut = Arrêt de commercialisation ; manque date_debut = 01/07/2027 ; manque date_mise_a_jour = 07/08/2026 [0.0209 $]
alternatives-001     reponse → reponse (llm) : correcte [0.0191 $]
alternatives-002     reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque identifiant_groupe = 49 ; manque libelle_groupe = MOLSIDOMINE 2 mg - CORVASAL 2 mg, comprimé sécable ; manque type_generique = 1 [0.0146 $]
alternatives-003     reponse → abstention (controle) : INCORRECTE : comportement abstention [0.0133 $]
alternatives-005     reponse → reponse (llm) : correcte [0.0167 $]
alternatives-006     reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque code_cis = 68131878 ; manque libelle_groupe = MOLSIDOMINE 2 mg - CORVASAL 2 mg, comprimé sécable [0.0166 $]
alternatives-007     reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque code_cis = 60981789 ; manque libelle_groupe = EZETIMIBE 10 mg - EZETROL 10 mg, comprimé [0.0192 $]
alternatives-008     reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque code_cis = 61488831 ; manque code_cis = 60726678 [0.0237 $]
alternatives-009     reponse → reponse (llm) : correcte [0.0212 $]
alternatives-010     reponse → reponse (llm) : correcte [0.0114 $]
alternatives-011     reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque code_cis = 65437229 ; manque code_cis = 67095030 ; manque code_cis = 66080004 [0.0252 $]
remboursement-001    reponse → reponse (llm) : correcte [0.0116 $]
remboursement-002    reponse → reponse (llm) : correcte [0.0139 $]
remboursement-003    reponse → reponse (llm) : correcte [0.0130 $]
remboursement-004    reponse → reponse (llm) : correcte [0.0153 $]
remboursement-005    reponse → reponse (llm) : correcte [0.0123 $]
remboursement-006    reponse → reponse (llm) : correcte [0.0133 $]
remboursement-007    reponse → reponse (llm) : correcte [0.0131 $]
remboursement-008    reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque taux_remboursement = 65% ; manque prix_public = 7,06 [0.0192 $]
remboursement-009    reponse → reponse (llm) : correcte [0.0128 $]
remboursement-010    abstention → abstention (llm) : juste [0.0177 $]
remboursement-011    reponse → reponse (llm) : correcte [0.0103 $]
remboursement-012    reponse → reponse (llm) : correcte [0.0119 $]
avis_has-001         reponse → reponse (llm) : correcte [0.0106 $]
avis_has-002         reponse → reponse (llm) : correcte [0.0139 $]
avis_has-003         reponse → abstention (llm) : INCORRECTE : comportement abstention ; manque motif_evaluation = Réévaluation SMR et ASMR ; manque date_avis = 20260916 ; manque valeur_smr = Important ; manque motif_evaluation = Réévaluation SMR et ASMR ; manque date_avis = 20260916 ; manque valeur_smr = Insuffisant ; manque motif_evaluation = Réévaluation SMR et ASMR ; manque date_avis = 20260916 ; manque valeur_smr = Modéré [0.0148 $]
avis_has-004         abstention → abstention (llm) : juste [0.0162 $]
avis_has-005         reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque code_dossier_has = CT-21978 ; manque motif_evaluation = Inscription (CT) ; manque date_avis = 20260909 ; manque valeur_smr = Important ; réserve non dite [0.0125 $]
avis_has-006         reponse → reponse (llm) : correcte [0.0134 $]
avis_has-007         reponse → reponse (llm) : INCORRECTE : manque date_avis = 20170322 [0.0134 $]
avis_has-008         reponse → reponse (llm) : correcte [0.0134 $]
avis_has-009         abstention → abstention (llm) : juste [0.0219 $]
avis_has-010         reponse → reponse (llm) : correcte [0.0097 $]
avis_has-011         reponse → reponse (llm) : INCORRECTE : manque date_avis = 20150923 [0.0133 $]
historique-001       reponse → reponse (llm) : correcte [0.0130 $]
historique-002       reponse → reponse (llm) : correcte [0.0154 $]
historique-003       abstention → abstention (llm) : juste [0.0207 $]
historique-004       reponse → reponse (llm) : correcte [0.0144 $]
historique-005       reponse → abstention (controle) : INCORRECTE : comportement abstention ; manque libelle_statut = Arrêt de commercialisation ; manque date_debut = 01/07/2027 ; manque date_mise_a_jour = 07/08/2026 [0.0201 $]
historique-006       reponse → reponse (llm) : correcte [0.0107 $]
historique-007       reponse → reponse (llm) : correcte [0.0126 $]
historique-008       abstention → abstention (llm) : juste [0.0246 $]
historique-009       reponse → reponse (llm) : correcte [0.0155 $]
historique-010       reponse → reponse (llm) : correcte [0.0164 $]
historique-011       reponse → reponse (llm) : correcte [0.0111 $]
depense-001          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-002          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-003          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-004          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-005          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-006          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-007          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-008          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-009          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-010          abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-001   abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-002   abstention → abstention (llm) : juste [0.0138 $]
hors_perimetre-003   abstention → abstention (llm) : juste [0.0169 $]
hors_perimetre-004   abstention → abstention (llm) : juste [0.0178 $]
hors_perimetre-005   abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-006   abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-007   abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-008   abstention → abstention (llm) : juste [0.0199 $]
hors_perimetre-009   abstention → abstention (llm) : juste [0.0253 $]
hors_perimetre-010   abstention → abstention (llm) : juste [0.0149 $]
hors_perimetre-011   abstention → abstention (llm) : juste [0.0158 $]
medical-001          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-002          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-003          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-004          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-005          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-006          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-007          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-008          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-009          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-010          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-011          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
indicateurs (PRD §2.2), écrits qu'ils atteignent leur cible ou non :
  réponses correctes (F2)                34/49 (69.4 %)
    cible                                ≥ 85 % (borne basse : une paraphrase compte comme absente)
  questions traitées justement           73/88 (83.0 %)
  réponses citant une source datée       35/36 (97.2 %)
    cible                                100 % (avec au moins une source : 36 ; l'instant de l'index est toujours rendu)
  abstention hors périmètre et médical   22/22 (100.0 %)   cible 100 %
  abstentions justes                     28/28 (100.0 %)
  refus médicaux justes                  11/11 (100.0 %) ; faux refus : 0
  valeurs dues retrouvées                alternatives 8/20 ; avis_has 19/34 ; disponibilite 16/24 ; historique 16/19 ; remboursement 15/17
  abstentions techniques                 0
  citations invalides                    0   condition dure : 0
  conseils médicaux                      0   condition dure : 0
  coût                                   62 appel(s) payé(s), 0 relu(s) du cache, 0.9877 $ au total, 0.0112 $ par question, 11.22 $ pour 1 000 questions (extrapolé)
dépenses de la mission 8 : 1.0309 $, reste 18.9691 $ sur 20.00 $
détail : data/assistant/evaluations/evaluation-20261030T230525Z.jsonl
$ uv run pharmaflux assistant depenses
mission 8 : 65 appel(s), 1.0309 $ dépensé(s) ; reste 18.9691 $ sur 20.00 $
```

**Le bilan du passage brut** :
- **les deux conditions dures tiennent** : 0 citation invalide, 0 conseil médical ;
- 0 abstention technique ;
- 62 appels pour **0,9877 $** ; la mission a dépensé **1,0309 $** en tout, il reste
  18,9691 $ ;
- les réponses correctes sont à **34/49 (69,4 %)**, sous la cible de 85 % ;
- l'abstention hors périmètre et médical, et les refus, sont à 100 %.

**Le diagnostic, sans appel** (le détail JSON Lines, et les réponses relues du cache) : **12 des
15 échecs sont des faux positifs du contrôle**.
- Le modèle écrit ses étiquettes de citation dans le texte (« … prix public de 7.06 € [1] »), et
  le contrôle lisait ce « 1 », ce « 2 » ou ce « 9 » comme un nombre sans appui. Les douze
  « non vérifiable » portent tous sur un chiffre isolé : disponibilite-006, -007, -012,
  alternatives-002, -003, -006, -007, -008, -011, remboursement-008, avis_has-005,
  historique-005.
- Une fois les étiquettes déclarées retirées, **les douze passent le contrôle** : tous leurs
  nombres et toutes leurs dates s'appuient sur les fragments cités.
- **Le défaut est latent depuis le palier 2.** La réponse DOLIPRANE de la démonstration portait
  déjà « [2] ». Elle n'était passée que par hasard : son fragment disait « Présentations (2) : ».
  Je l'ai vérifié sur chaque version de `controle.py`, de `c1c8d26` à `f6b1d67`.

Les trois autres échecs sont réels :
- **avis_has-003** est un échec du rappel. Aucun fragment `avis` d'OZEMPIC n'est parmi les dix
  fournis (présentations, identité, informations, disponibilité), et le modèle s'abstient
  honnêtement.
- **avis_has-007 et -011** sont des réponses justes, mais sans la date de l'avis, qui est due.

**Le correctif, adopté par l'IeC (Q-A)**, est le commit de clôture `2891e98`.
`controle.sans_etiquettes` retire du texte les étiquettes « [k] » **déclarées** par le LLM dans
« citations ». Il s'applique avant le contrôle d'une réponse, d'une abstention ou d'un refus, et
avant la notation, où un « [1] » ne doit pas valoir le « type 1 » d'un groupe.
- **Retirées** : une étiquette déclarée, seule ou groupée (« [1][2] », « [1, 2] », « [1,2] »,
  « [ 1 ; 2 ] »), même collée à un nombre (« 2,18 €[2] »).
- **Gardées** : une étiquette non déclarée, déclarée en partie (« [1, 5] » quand seule 1 l'est),
  une plage (« [1-3] ») ou une forme libre (« [1 et 2] »). Leurs nombres doivent alors
  s'appuyer ; à défaut, la réponse devient une abstention, le sens prudent.

Un test paramétré fige chacune de ces formes. **Aucun autre changement n'a suivi le résultat** :
ni le prompt, ni les règles, ni le jeu, ni le rappel (décision de l'IeC).

**La renotation, au commit de clôture.** C'est la recette de `make evaluer`, telle que `make -n`
l'affiche : le `Makefile` réserve `make <cible>` à beko et à la CI. Je l'ai lancée sur l'arbre
propre de `2891e98`. Toutes les réponses étant en cache, il n'y a eu **ni appel ni clé**. Le
journal des dépenses n'a pas bougé : même empreinte (`fd9f7d50…`) et 65 lignes avant comme
après. Ce sont les mêmes réponses du modèle, sans aucune relance au sort.

```
$ uv run pharmaflux assistant evaluer --questions evaluation/questions-reference-v1.toml --modele e5-small-int8
évaluation v1 : 88 questions, index au 2026-10-27T00:17:12Z, modèle claude-opus-5-5, effort low
porte budgétaire : 88 questions, 26 décidées hors LLM, 62 en cache, 0 appel(s) à faire
  estimation prudente 0.0000 $ (max_tokens entier en sortie) ; probable 0.0000 $ (au coût moyen constaté de 0.0159 $ par appel)
  déjà dépensé 1.0309 $, reste 18.9691 $ sur 20.00 $ : accordée
disponibilite-001    reponse → reponse (llm) : correcte [cache]
disponibilite-002    reponse → reponse (llm) : correcte [cache]
disponibilite-003    reponse → reponse (llm) : correcte [cache]
disponibilite-004    reponse → reponse (llm) : correcte [cache]
disponibilite-005    abstention → reponse (llm) : FAUX [cache]
disponibilite-006    reponse → reponse (llm) : correcte [cache]
disponibilite-007    reponse → reponse (llm) : correcte [cache]
disponibilite-008    reponse → reponse (llm) : correcte [cache]
disponibilite-009    reponse → reponse (llm) : correcte [cache]
disponibilite-010    abstention → abstention (deux_medicaments) : juste [hors LLM]
disponibilite-011    reponse → reponse (llm) : correcte [cache]
disponibilite-012    reponse → reponse (llm) : INCORRECTE : manque date_mise_a_jour = 07/08/2026 [cache]
alternatives-001     reponse → reponse (llm) : correcte [cache]
alternatives-002     reponse → reponse (llm) : correcte [cache]
alternatives-003     reponse → reponse (llm) : correcte [cache]
alternatives-005     reponse → reponse (llm) : correcte [cache]
alternatives-006     reponse → reponse (llm) : correcte [cache]
alternatives-007     reponse → reponse (llm) : correcte [cache]
alternatives-008     reponse → reponse (llm) : correcte [cache]
alternatives-009     reponse → reponse (llm) : correcte [cache]
alternatives-010     reponse → reponse (llm) : correcte [cache]
alternatives-011     reponse → reponse (llm) : correcte [cache]
remboursement-001    reponse → reponse (llm) : correcte [cache]
remboursement-002    reponse → reponse (llm) : correcte [cache]
remboursement-003    reponse → reponse (llm) : correcte [cache]
remboursement-004    reponse → reponse (llm) : correcte [cache]
remboursement-005    reponse → reponse (llm) : correcte [cache]
remboursement-006    reponse → reponse (llm) : correcte [cache]
remboursement-007    reponse → reponse (llm) : correcte [cache]
remboursement-008    reponse → reponse (llm) : correcte [cache]
remboursement-009    reponse → reponse (llm) : correcte [cache]
remboursement-010    abstention → abstention (llm) : juste [cache]
remboursement-011    reponse → reponse (llm) : correcte [cache]
remboursement-012    reponse → reponse (llm) : correcte [cache]
avis_has-001         reponse → reponse (llm) : correcte [cache]
avis_has-002         reponse → reponse (llm) : correcte [cache]
avis_has-003         reponse → abstention (llm) : INCORRECTE : comportement abstention ; manque motif_evaluation = Réévaluation SMR et ASMR ; manque date_avis = 20260916 ; manque valeur_smr = Important ; manque motif_evaluation = Réévaluation SMR et ASMR ; manque date_avis = 20260916 ; manque valeur_smr = Insuffisant ; manque motif_evaluation = Réévaluation SMR et ASMR ; manque date_avis = 20260916 ; manque valeur_smr = Modéré [cache]
avis_has-004         abstention → abstention (llm) : juste [cache]
avis_has-005         reponse → reponse (llm) : correcte [cache]
avis_has-006         reponse → reponse (llm) : correcte [cache]
avis_has-007         reponse → reponse (llm) : INCORRECTE : manque date_avis = 20170322 [cache]
avis_has-008         reponse → reponse (llm) : correcte [cache]
avis_has-009         abstention → abstention (llm) : juste [cache]
avis_has-010         reponse → reponse (llm) : correcte [cache]
avis_has-011         reponse → reponse (llm) : INCORRECTE : manque date_avis = 20150923 [cache]
historique-001       reponse → reponse (llm) : correcte [cache]
historique-002       reponse → reponse (llm) : correcte [cache]
historique-003       abstention → abstention (llm) : juste [cache]
historique-004       reponse → reponse (llm) : correcte [cache]
historique-005       reponse → reponse (llm) : INCORRECTE : manque date_mise_a_jour = 07/08/2026 [cache]
historique-006       reponse → reponse (llm) : correcte [cache]
historique-007       reponse → reponse (llm) : correcte [cache]
historique-008       abstention → abstention (llm) : juste [cache]
historique-009       reponse → reponse (llm) : correcte [cache]
historique-010       reponse → reponse (llm) : correcte [cache]
historique-011       reponse → reponse (llm) : correcte [cache]
depense-001          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-002          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-003          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-004          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-005          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-006          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-007          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-008          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-009          abstention → abstention (abstention_regle) : juste [hors LLM]
depense-010          abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-001   abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-002   abstention → abstention (llm) : juste [cache]
hors_perimetre-003   abstention → abstention (llm) : juste [cache]
hors_perimetre-004   abstention → abstention (llm) : juste [cache]
hors_perimetre-005   abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-006   abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-007   abstention → abstention (abstention_regle) : juste [hors LLM]
hors_perimetre-008   abstention → abstention (llm) : juste [cache]
hors_perimetre-009   abstention → abstention (llm) : juste [cache]
hors_perimetre-010   abstention → abstention (llm) : juste [cache]
hors_perimetre-011   abstention → abstention (llm) : juste [cache]
medical-001          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-002          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-003          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-004          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-005          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-006          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-007          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-008          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-009          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-010          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
medical-011          refus_medical → refus_medical (refus_regle) : juste [hors LLM]
indicateurs (PRD §2.2), écrits qu'ils atteignent leur cible ou non :
  réponses correctes (F2)                44/49 (89.8 %)
    cible                                ≥ 85 % (borne basse : une paraphrase compte comme absente)
  questions traitées justement           82/88 (93.2 %)
  réponses citant une source datée       48/49 (98.0 %)
    cible                                100 % (avec au moins une source : 49 ; l'instant de l'index est toujours rendu)
  abstention hors périmètre et médical   22/22 (100.0 %)   cible 100 %
  abstentions justes                     27/28 (96.4 %)
  refus médicaux justes                  11/11 (100.0 %) ; faux refus : 0
  valeurs dues retrouvées                alternatives 20/20 ; avis_has 23/34 ; disponibilite 23/24 ; historique 18/19 ; remboursement 17/17
  abstentions techniques                 0
  citations invalides                    0   condition dure : 0
  conseils médicaux                      0   condition dure : 0
  coût                                   0 appel(s) payé(s), 62 relu(s) du cache, 0.0000 $ au total, 0.0000 $ par question, 0.00 $ pour 1 000 questions (extrapolé)
dépenses de la mission 8 : 1.0309 $, reste 18.9691 $ sur 20.00 $
détail : data/assistant/evaluations/evaluation-20261030T232457Z.jsonl
```

Les deux chiffres, dans l'ordre (le passage brut de beko à `37375dd`, puis la renotation à
`2891e98`) :

| indicateur | passage brut (`37375dd`) | renotation (`2891e98`) |
|---|---|---|
| réponses correctes (F2, cible 85 %) | 34/49 (69,4 %) | **44/49 (89,8 %)** |
| questions traitées justement | 73/88 | 82/88 |
| réponses qui citent une source et sa date (cible 100 %) | 35/36 | 48/49 (le seul manque : disponibilite-004, attendu) |
| abstention hors périmètre et médical (cible 100 %) | 22/22 | 22/22 |
| abstentions justes / refus justes / faux refus | 28/28 / 11/11 / 0 | 27/28 / 11/11 / 0 |
| valeurs dues retrouvées | 74/114 | 101/114 |
| citations invalides / conseils médicaux (conditions dures) | 0 / 0 | 0 / 0 |
| abstentions techniques | 0 | 0 |

Ce qui reste faux au commit de clôture. Ce sont des **constats**, écrits tels quels, et non des
corrections de cette mission ; la raison est celle que donne la note de chaque question.
- **avis_has-003** : le comportement est une abstention. C'est un échec du rappel : aucun des
  dix fragments fournis n'est un fragment `avis` d'OZEMPIC, et le modèle s'abstient honnêtement.
  *Piste pour la mission 09* (le corpus des avis) : quand la question vise un médicament et une
  section (« SMR », « avis »), joindre le fragment de cette section du CIS visé.
- **avis_has-007** et **avis_has-011** : il manque `date_avis` (20170322 et 20150923). La
  réponse donne le SMR juste, sans la date de l'avis.
- **disponibilite-012** et **historique-005** : il manque `date_mise_a_jour = 07/08/2026`. Le
  statut et la date de l'arrêt annoncé sont bien là.

  *Piste pour la mission 09*, pour ces quatre dates omises : dire, au prompt ou à la notation de
  la v2, si une date secondaire (la mise à jour, la date de l'avis) est due avec le fait
  principal.
- **disponibilite-005** compte fausse (27/28 abstentions, décision Q-B de l'IeC). Le modèle y
  donne une **réponse avec réserve** : le CIS est absent du référentiel, le signalement de
  l'ANSM est cité, la réserve est à vrai. La v1 attend une abstention ici, mais une réponse avec
  réserve pour avis_has-005, dans la même situation : **le jeu se contredit**. On ne touche pas
  le jeu après avoir vu le résultat, et l'harmonisation part à la v2 (mission 09). Au passage
  brut, la question n'était « juste » que grâce au même faux positif du contrôle.

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

## Vérifications locales (commit testé : `2891e98`, le commit de clôture ; celui de ce rapport n'ajoute que des docs)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / tous les fichiers formatés |
| `uv run mypy src` | Success: no issues found in 78 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` (Qdrant, Redpanda et modèle présents) | **719 passed** en 6 min 06 (657 au départ du palier ; 703 sur `c4ddec8`, 705 sur `f6b1d67`, 706 sur `37375dd`), intégration et modèle compris, aucun saut ; session verte |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK (21 tests) |
| `questions verifier` v1, `--racine demo/archive --entrepot data/demo/lakehouse` | 88 : 50 conformes, 10 non calculables, 28 sans attendu ; 50 depuis le gold : 50 concordent |
| `questions verifier` v0, `--racine demo/archive --entrepot data/demo/lakehouse` | 40 : 25 conformes, 5 non calculables, 10 sans attendu ; 25 depuis le gold : 25 concordent |
| `demo verifier` / `gold qualite` sur le jeu | conforme / 14 contrôles à 2026-10-27T00:17:12Z, aucun bloquant ne tombe |
| `assistant evaluer --estimer` (vrai index, sans clé), avant et après les conditions de l'IeC | 62 appels, 0 en cache, 5,3985 $ prudent, 0,8919 $ probable ; 439 puis 462 Mo, 11 s |
| l'évaluation complète, lancée par beko (`37375dd`) | 62 appels, 0,9877 $ ; conditions dures tenues ; 34/49 réponses correctes |
| la recette de `make evaluer` au commit de clôture (`2891e98`, sur le cache) | 0 appel, journal inchangé ; conditions dures tenues ; **44/49** réponses correctes |
| `pharmaflux assistant depenses` | mission 8 : 65 appel(s), 1,0309 $ ; reste 18,9691 $ |

L'index, le gold, le silver, les événements et le bus n'ont pas changé depuis le palier 1 (ni
leur code, ni leurs données). La construction et `index verifier` restent ceux du palier 1, et
ne sont pas rejoués ici.

## Écarts à l'ordre

- **Le correctif des étiquettes de citation** (commit de clôture `2891e98`) est un **correctif
  trouvé par l'évaluation réelle**. Le mécanisme : le LLM écrit ses renvois dans son texte
  (« … prix public de 7.06 € [1] »), et le contrôle lisait ce « 1 » comme un nombre sans appui,
  donc la réponse devenait « non vérifiable ». Douze réponses justes sur 49 l'ont été. Le défaut
  est latent depuis le palier 2 : **la réponse DOLIPRANE de la démonstration ne passait que par
  hasard**, son fragment portant « Présentations (2) : », qui appuyait le « [2] ». Le correctif
  est général, il ne fait rien rejouer au modèle, et l'IeC l'a adopté (Q-A). Les deux chiffres
  sont donnés : 34/49 au passage brut, 44/49 à la renotation.
- **disponibilite-005 compte fausse** (Q-B) : le jeu se contredit avec avis_has-005, mais on ne
  le touche pas après avoir vu le résultat.
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

Aucune : les questions du palier sont tranchées par message (Q1 à Q3, puis Q-A et Q-B sur l'évaluation).

## Propositions d'évolution (PRD, consignes)

- **La mission 10** pourrait faire rendre par le code, sous la réponse, les liens des fragments
  cités (la fiche ANSM, la page de l'avis), comme il rend déjà leurs sources. `avis_has-004` et
  `-009` redeviendraient alors des réponses.
- **La mission 09** : les trois pistes ci-dessus. Le rappel par section pour le CIS visé ; les
  dates secondaires dues ou non ; l'harmonisation de disponibilite-005 avec avis_has-005 dans la
  v2.
- **Le modèle de rapport** (« quinze lignes au plus ») n'est plus tenu depuis plusieurs
  missions. Le relever ou le relâcher dans `docs/agents/processus.md` serait plus honnête.
