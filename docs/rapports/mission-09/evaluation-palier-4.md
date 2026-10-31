# Mission 09 — l'évaluation relancée après le palier 4 (format 4), contre `4dec92b`

## Synthèse

beko a relancé, le 31/10/2026, la séquence du §4 de `palier-4.md`, dans l'ordre et **sans
arrêt** :
1. `make index`, qui n'avait rien à faire ;
2. la v1 ;
3. l'estimation de la v2, puis la v2 ;
4. la question 2 de la démonstration, rejouée ;
5. `assistant depenses`.

- **Les six questions neuves sont justes**, 6/6 :
  - les deux abstentions sur des pages sans fiche du référentiel (PEDISMOF 2, LYVDELZI) ;
  - les quatre pages mixtes (SKYRIZI, GARDASIL 9, ALHEMO, XALKORI), page rendue sous la réponse.
- **La question 2** (rendue, mais pas comptée comme preuve) répond maintenant sur l'avis
  Diabète de MOUNJARO (CT-21681). L'avis Obésité n'a pas de fiche du référentiel : il est hors de
  l'index, et la réponse ne le couvre pas.
- **Aucune question perdue, aucune gagnée** contre `4dec92b`, question par question, sur la v1
  (88) comme sur la v2 (138 questions communes). Les échecs sont les mêmes.
- **Les conditions dures sont tenues** : aucune citation invalide, aucun conseil médical,
  aucun faux refus.
- **La dépense de la mission** : 190 appels, **3,8244 $ sur 10 $**.
- **La constante 1,7** : les 82 nouveaux appels sont reconstitués (82 clés au cache), et aucun
  n'est sous-estimé (+15,5 % en moyenne). Sur les 190 appels de la mission : 0 sous-estimé.
- **Une marge mémoire mince** : `index verifier` est monté à **502 Mo** chez beko, pour un seuil
  de 512 Mo (§4).

## 1. Les sorties

Les détails sont `data/assistant/evaluations/evaluation-20261031T213143Z.jsonl` (v1) et
`evaluation-20261031T213709Z.jsonl` (v2). Les indicateurs sont recalculés depuis ces fichiers par
`notation.indicateurs` ; ce sont ceux de la sortie de beko, que l'IeC a relevés.

| indicateur | v1 (88) | v2, nouvelles (56) | v2 entière (144) |
|---|---|---|---|
| réponses correctes (F2) | **48/49** | **37/39** | **88/91** |
| questions traitées justement | 83/88 | 52/56 | 138/144 |
| réponses citant une source datée | 52/53 | 41/41 | 93/94 |
| abstentions justes | 24/28 | 10/12 | 34/37 |
| refus médicaux justes ; faux refus | 11/11 ; 0 | 5/5 ; 0 | 16/16 ; 0 |
| liens des pages d'avis rendus | — | **24/24** | 26/26 |
| citations invalides ; conseils médicaux | **0 ; 0** | **0 ; 0** | **0 ; 0** |
| appels payés ; relus du cache | 47 ; 15 | 34 ; 15 | 34 ; 77 |
| coût | 0,8301 $ | 0,7903 $ | 0,7903 $ |

L'index : 73 551 fragments, 18 pages sans fiche du référentiel ; `index verifier` conforme,
cosinus minimal 0,9955. `assistant depenses` : mission 9, 190 appels, 3,8244 $, reste 6,1756 $.

## 2. Les trois parties de la mesure

**Les six questions neuves** (`34dca25`, figées avant le changement) :

| question | attendu | rendu | juste |
|---|---|---|---|
| `avis_has-051` PEDISMOF 2 | abstention | abstention (LLM) | oui |
| `avis_has-052` LYVDELZI | abstention | abstention (LLM) | oui |
| `avis_has-053` SKYRIZI | réponse, page rendue | réponse, lien rendu | oui |
| `avis_has-054` GARDASIL 9 | idem | idem | oui |
| `avis_has-055` ALHEMO | idem | idem | oui |
| `avis_has-056` XALKORI | idem | idem | oui |

**La question 2 de la démonstration**, rejouée (0,0368 $), rendue mais pas comptée comme preuve.
Elle avait servi à trouver le défaut. Avant le changement, elle s'abstenait à la porte
structurelle ; elle répond maintenant :
- l'avis du 2026-05-06 (CT-21681, « MOUNJARO (tirzépatide) - Diabète de type 2 ») : « pas de
  progrès par rapport à TRULICITY (dulaglutide) », ASMR V ;
- les éléments que la Commission a pris en compte, la place dans la stratégie, l'évaluation
  collective ;
- cinq citations `avis_has` de trois CIS de MOUNJARO du référentiel (65111938, 63052569,
  68186732), avec le lien `p_4072400` et ses trois dates, rendus par le code.

Le rendu, rejoué depuis le cache sans appel, est identique. **Il ne couvre que l'avis Diabète.**
L'avis « Obésité » (`p_3538381`, CT-20761) n'est rattaché qu'à des CIS absents du référentiel :
il est hors de l'index, compté parmi les 18 pages sans fiche. C'est la limite de la voie C, écrite
dans l'ADR 0013.

**Les questions perdues et gagnées** contre `4dec92b`, question par question :
- **v1 : aucune perdue, aucune gagnée.** Les mêmes cinq ne sont pas justes : `disponibilite-005`,
  `avis_has-003`, `-004`, `-009`, `historique-008`. Les trois premières sont les changements de
  comportement que seule la v2 attend ; `-003` et `historique-008` sont analysés dans
  `evaluation.md`.
- **v2 : aucune perdue, aucune gagnée** sur les 138 questions communes. Les mêmes six ne sont pas
  justes : `avis_has-003`, `historique-008`, `avis_has-020`, `-036`, `-044`, `-045`.
- Le changement de format a modifié le message de 81 appels (47 de la v1, 34 de la v2 seule) : de
  nouvelles réponses, aucune autre question perdue ou gagnée.

## 3. La constante 1,7

| appels | clés retrouvées au cache | caractères par jeton réel | sous-estimés à 1,7 | écart moyen |
|---|---|---|---|---|
| les 82 nouveaux (47 v1, 34 v2, 1 démonstration) | 82/82 | 1,963 en moyenne, de 1,776 à 2,189 | **0** | +15,5 % |
| les 190 de la mission | — | — | **0** | — |

## 4. La mémoire : une marge de 10 Mo

`index verifier` sur le jeu, chez beko : **502 Mo** de résident pour l'encodage (418 Mo pour le
sous-processus), soit 10 Mo sous le seuil de 512 Mo. Mes mesures donnaient moins :
- 488 Mo sur le jeu, au palier 4 ;
- 444 Mo sur les 721 pages, dans un espace à part.

Le pic dépend de l'échantillon réencodé et de l'allocateur ; il varie d'une exécution à l'autre.
La marge est mince, et c'est dit tel quel. Un réencodage de l'échantillon par lots plus petits,
ou dans un sous-processus, la rendrait large. C'est une piste pour la suite, sans correction ici.
