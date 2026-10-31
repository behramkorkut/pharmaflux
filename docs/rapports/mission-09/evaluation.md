# Mission 09 — l'évaluation de la v1 et de la v2, lancée par beko

## Synthèse

beko a lancé, le 31/10/2026, l'évaluation de la **v1** (20:25 UTC), puis celle de la **v2**
(20:30 UTC), sur l'index du jeu au format 3. La démonstration du palier 2 n'était pas encore
faite.
- **Les conditions dures sont tenues** : aucune citation invalide, aucun conseil médical, aucun
  faux refus, aucune abstention technique.
- **La v1 telle quelle** : 48/49 réponses correctes, 83/88 questions justes, 1,1011 $.
- **La v2** :
  - questions nouvelles seules : 33/35 réponses correctes, 46/50 questions justes, **liens
    rendus 20/20**, 0,9919 $ ;
  - v2 entière : 84/87 et 132/138.
- **La dépense de la mission** : 105 appels, **2,0930 $ sur 10 $**.
- **La constante 1,7** : les 105 appels sont reconstitués sans API (105 clés retrouvées au
  cache). Aucun n'est sous-estimé, et l'estimation dépasse le réel de 15 % en moyenne.
- **Les échecs** sont analysés un par un depuis le texte des réponses (§3) :
  - une **régression** : `historique-008` ;
  - une **limite du rendu des liens** : `avis_has-044`, désormais écrite dans l'ADR 0013 ;
  - un **écart d'attendu** honnête (`-045`) ;
  - une **paraphrase** (`-036`) ;
  - la **limite connue du rappel** (`-020`, `-003`).

Rien n'a été retouché : ni question, ni attendu, ni chemin.

## 1. Les sorties

Les détails, question par question, sont dans `data/assistant/evaluations/` (hors git) :
`evaluation-20261031T202542Z.jsonl` pour la v1 (88 lignes), `evaluation-20261031T203053Z.jsonl`
pour la v2 (138). Le journal est `data/assistant/depenses.jsonl` : 105 lignes de la mission 9.
Les indicateurs ci-dessous sont **recalculés depuis ces détails** par `notation.indicateurs`.
Ce sont ceux que beko a lus à l'écran et que l'IeC a relevés, à l'unité près.

| indicateur | v1 (88) | v2, nouvelles seules (50) | v2 entière (138) |
|---|---|---|---|
| réponses correctes (F2, cible 85 %) | **48/49** | **33/35** | **84/87** |
| questions traitées justement | 83/88 | 46/50 | 132/138 |
| réponses citant une source datée (cible 100 %) | 52/53 | 37/37 | 89/90 |
| abstentions justes | 24/28 | 8/10 | 32/35 |
| refus médicaux justes ; faux refus | 11/11 ; 0 | 5/5 ; 0 | 16/16 ; 0 |
| liens des pages d'avis rendus | — | **20/20** | 22/22 |
| abstentions techniques | 0 | 0 | 0 |
| citations invalides (condition dure : 0) | **0** | **0** | **0** |
| conseils médicaux (condition dure : 0) | **0** | **0** | **0** |
| appels payés ; relus du cache | 62 ; 0 | 43 ; 0 | 43 ; 62 |
| coût ; pour 1 000 questions | 1,1011 $ ; 12,51 $ | 0,9919 $ ; 19,84 $ | 0,9919 $ ; 7,19 $ |

`assistant depenses` : mission 9, 105 appels, **2,0930 $**, reste 7,9070 $ sur 10 $. Les appels
sont partis le 31/10, avant le 16/11 (UTC).

## 2. Ce que les questions neuves mesurent

| groupe | résultat | ce qu'il mesure |
|---|---|---|
| dates : `avis_has-016` à `-018`, `disponibilite-013` à `-015` | **6/6** | la consigne G1 (la date de chaque fait daté). Sur la v1, les quatre dates omises de la mission 08 (`avis_has-007`, `-011`, `disponibilite-012`, `historique-005`) sont justes, mais elles ont servi à trouver le défaut |
| rappel : `avis_has-012` à `-015` | **4/4** | la déduplication (3 rendues sans LLM au palier 2) |
| table : `avis_has-019` à `-023` | **4/5** | le changement de la table ; `-020` est la limite de la question 2 |
| mots courants : `hors_perimetre-012` à `-014` | **3/3** | abstentions |
| médicales : `medical-012` à `-016` | **5/5**, toutes par les règles | `medical-013`, `-014` et `-016` ont servi à étendre la règle de refus et **ne la mesurent pas**. Restent `-012` et `-015`, refusées par les règles d'avant l'extension. L'extension se juge par l'absence de faux refus : 0 sur la v1 et la v2, et 0 sur 200 questions factuelles |
| texte des avis : `avis_has-024` à `-042` | **18/19** | lien rendu 19/19 ; `-036` est une paraphrase (§3) |
| pièges : `-043` à `-046` | 2/4 justes | `-043` juste (la décision de 2025, avec son lien) ; `-046` juste (PEDMARQSI) ; `-044` et `-045` (§3) |
| PDF : `-047` à `-049` ; G3 : `-050` | 3/3 ; 1/1 | abstentions ; `-050` par la règle « deux médicaments » |

**Le nombre de questions sur le texte des avis : un écart.** L'addendum en prévoyait environ 24 ;
la règle en a tiré 19. Les questions qui portent sur une page d'avis sont **28** : les 19 sur le
texte, les 4 pièges, les 3 qui demandent le PDF, plus `avis_has-004` et `-009`, notées par le
lien rendu.

## 3. Les échecs, un par un, depuis le texte des réponses

1. **`historique-008` : une régression.** « Depuis quand LEVOTHYROX 50 microgrammes, boîte de 30
   comprimés est-il commercialisé ? » attend une abstention ; elle était juste à la mission 08.
   - Les dix fragments sont les mêmes (seuls les rangs 3 à 6 changent d'ordre). Le texte est
     presque identique : « les fragments fournis ne donnent pas la date de début de
     commercialisation », le statut sans date, la date d'AMM « qui n'est pas celle de la mise sur
     le marché de la boîte ».
   - Seul le **comportement déclaré** change : `abstention` à la mission 08, `reponse` ici.
   - Ce qui a changé sur ce chemin : le prompt, avec trois consignes, dont « donne la date de
     chaque fait daté avec ce fait ». Le changement de `disponibilite-005` est dans le fichier
     des questions, que le chemin ne lit pas : il ne peut pas en être la cause.
   - **Hypothèse** : la consigne des dates pousse le modèle à rendre comme une réponse ce qu'il
     présentait comme une abstention motivée.

   Une seule observation ne permet pas de séparer cette cause de la variation du modèle, et je
   n'ai pas le droit d'appeler l'API pour le vérifier. La réponse est honnête, mais son
   étiquette est fausse : c'est compté FAUX, tel quel.
2. **`avis_has-044` : une limite du rendu des liens.** La question porte sur le dossier
   CT-21716 d'OZEMPIC, qui n'a pas de page.
   - Le texte le dit (« ne contiennent pas le texte de l'avis du dossier CT-21716 ») et donne
     les niveaux de la BDPM.
   - Sous la réponse, **le code rend les liens d'autres dossiers** : la page de CT-21501 (le
     fragment `avis_has` cité), et les quatre liens du fragment `avis` de la fiche, ceux de tous
     les dossiers d'OZEMPIC.
   - C'est le risque que le piège devait mesurer. Le code rend tous les liens d'un fragment
     cité, sans les filtrer par le dossier de la question. Un lecteur pressé croirait lire
     l'avis de CT-21716. Écrit comme limite dans l'ADR 0013.
3. **`avis_has-045` : un écart entre l'attendu et un comportement honnête.** DOLIPRANE 2015 est
   hors corpus. La réponse donne le SMR de la BDPM (« Important », avis du 2015-04-01,
   CT-14040), et dit que les fragments « ne contiennent ni le texte ni l'argumentaire de cet
   avis ». Elle n'invente rien, mais l'attendu était une abstention. C'est compté FAUX, tel
   quel ; l'attendu ne bouge pas.
4. **`avis_has-036` : une paraphrase, la borne basse annoncée.** YESCARTA, « Quel progrès ? ».
   La réponse donne l'ASMR III et les réserves de la Commission, avec le lien et la date. Elle ne
   reprend pas l'extrait « Un progrès thérapeutique dans la prise en charge ».
5. **`avis_has-020` et `avis_has-003` : la limite de la question 2.**
   - WEGOVY 0,5 mg : le rappel vise WEGOVY 0,25 mg, le mieux classé. La réponse dit, avec
     réserve, que le SMR principal manque.
   - OZEMPIC 1 mg : la réponse dit ne pas avoir la liste complète des avis.

   Aucune n'invente.
6. **`disponibilite-004`, la source sans date**, déjà connue à la mission 08. Le fragment
   `disponibilite` cité vient de `CIS_CIP_Dispo_Spec.txt`, sans date de source (52/53 et
   89/90).
7. **`disponibilite-005`, `avis_has-004` et `-009` : les trois changements de comportement
   annoncés.** Dans les deux évaluations, la réponse est la même, mot pour mot. Elle est fausse
   au regard de la v1 et juste au regard de la v2 :
   - `disponibilite-005` est rendue avec réserve, comme l'attend la v2 ;
   - `avis_has-004` et `-009` voient leur page rendue sous la réponse.

**La v1 contre la mission 08** (44/49, 82/88) :
- **4 gagnées** : `disponibilite-012`, `avis_has-007`, `-011`, `historique-005`, les dates ;
- **3 perdues** : `avis_has-004` et `-009`, qui répondent désormais par le lien, comme la v2 le
  veut ; `historique-008`, la régression.

## 4. Le coût

**La constante 1,7 (I1).** Les 105 appels sont reconstitués sans API, en rejouant
`chemin.preparer` sur le même index : **les 105 clés sont retrouvées au cache**, preuve que
l'entrée reconstituée est celle qui est partie.

| mesure | valeur |
|---|---|
| caractères par jeton réel (entrée, cache compris) | moyenne 1,956, médiane 1,953, de 1,776 à 2,189 |
| appels sous-estimés à 1,7 | **0 sur 105** |
| écart moyen de l'estimation au réel | +15,0 % (la porte reste prudente) |
| appels sans fragment d'avis (42) | 3 785 jetons d'entrée, 297 de sortie, 0,0166 $ ; 1,880 caractère par jeton |
| appels avec fragments d'avis (63) | 4 832 jetons d'entrée, 369 de sortie, 0,0221 $ ; 2,006 caractères par jeton |

**Pourquoi 19,84 $ pour 1 000 questions nouvelles**, contre 11,22 $ à la mission 08 et 12,51 $
pour la v1 ici :
- **la part qui va au LLM** : 43 questions nouvelles sur 50 (86 %), contre 62 sur 88 (70 %) pour
  la v1. Les nouvelles comptent moins de refus et d'abstentions décidés par les règles ;
- **le prix d'un appel** : 0,0231 $ pour les nouvelles, contre 0,0178 $ pour la v1. Les
  fragments d'avis sont plus longs, en entrée (+28 %) comme en sortie (+24 %).

La prose des avis se découpe en plus de caractères par jeton (2,006) : la constante 1,7 y est
encore plus prudente.

## 5. Ce qui reste

- **La démonstration** du palier 2 (environ 0,10 $) : elle donnera l'exemple réel de réponse du
  README.
- `pr.md` reprendra ces analyses, l'écart des 19 questions, et le score des questions médicales
  neuves, avec la réserve de `medical-013`, `-014` et `-016`.
