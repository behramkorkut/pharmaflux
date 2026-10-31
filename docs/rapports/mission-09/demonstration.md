# Mission 09 — la démonstration de beko (décision 7, palier 2)

## Synthèse

beko a lancé les cinq questions du §6 de `palier-2.md` le 31/10/2026, après l'évaluation, sur
l'index du jeu au format 3. Trois appels, 0,0743 $. La mission en est à **108 appels, 2,1673 $
sur 10 $**.
- **Conformes : les questions 1, 3, 4 et 5.**
  - La page d'avis est rendue sous la réponse avec ses trois dates, et les deux horloges de
    l'index aussi.
  - Pour LARIAM, seul le lien de l'ANSM est rendu, et aucun lien de la HAS.
  - La question 5 est refusée par les règles (posologie), sans appel.
- **La question 2** (« Quel progrès MOUNJARO apporte-t-il selon l'avis… ») s'abstient hors LLM,
  à la porte structurelle. C'est un **défaut**, diagnostiqué ici sans appel. Six CIS de MOUNJARO
  sont absents du référentiel ; ils portent les fragments des deux pages d'avis de MOUNJARO,
  sans dénomination, et prennent les dix places. Je ne corrige rien : le rappel est gelé, et
  l'IeC tranche.
- **La constante 1,7** : les trois appels sont reconstitués à l'identique (clés retrouvées au
  cache), et aucun n'est sous-estimé. Sur les 108 appels de la mission, aucun ne l'est.
- **L'exemple du README** est la question 3, rendue mot pour mot depuis le cache.

## 1. La sortie

Recopiée du terminal de beko et transmise par l'IeC. Les rendus des questions 1 et 3 sont
rejoués à l'identique **depuis le cache des réponses**, sans appel : `chemin.preparer`, puis
`chemin.conclure` avec un client qui lève une erreur s'il est appelé, et un journal de rejeu
resté vide.

| # | question | décision | coût | ce qui est rendu |
|---|---|---|---|---|
| 1 | Que dit l'avis de la CT sur KALYDECO 13,4 mg, granulés en sachet ? | réponse (LLM) | 0,0343 $ | avis du 2024-12-18, CT-21030 : SMR important pour les nourrissons de 1 à 4 mois, insuffisant ailleurs, ASMR II, arguments et réserves ; citations [1], [2], [10] (`avis_has`), avec la page `p_3577036`, mise en ligne le 2025-01-10, consultée le 2026-10-31 |
| 2 | Quel progrès MOUNJARO apporte-t-il selon l'avis de la CT ? | **abstention, porte structurelle (hors LLM)** | 0 $ | « le référentiel ne répond pas à cette question : aucun fragment du médicament visé » (§2) |
| 3 | Quel SMR la CT a-t-elle rendu pour MOUNJARO dans le dossier CT-21681 ? | réponse (LLM) | 0,0234 $ | avis du 2026-05-06 : « SMR : Modéré », ASMR V face à TRULICITY ; citations [3] et [6] (`avis_has`, CIS 68186732), page `p_4072400`, mise en ligne le 2026-06-12 |
| 4 | Où en est l'approvisionnement de LARIAM 250 mg, comprimé sécable ? | réponse (LLM) | 0,0166 $ | MITM, rupture de stock depuis le 2026-06-25, mise à jour le 2026-10-08 ; le lien de l'ANSM sous `disponibilite`, aucun lien de la HAS |
| 5 | Quelle est la durée du traitement par KALYDECO selon l'avis ? | refus médical (règles) | 0 $ | motif « la question demande une posologie (« duree du traitement ») » |

`assistant depenses` : mission 9, 108 appels, 2,1673 $, reste 7,8327 $.

**Une remarque, sans correction** : sous la réponse 1, le même lien est rendu trois fois (`p_3577036`
pour [1], [2] et [10]). Un rendu qui regroupe les citations d'une même page serait plus lisible :
c'est une piste pour une prochaine mission, reprise dans `pr.md`.

## 2. La question 2, diagnostiquée sans appel

`chemin.preparer` est rejoué sur la question, étape par étape, sur le même index :

| étape | ce qu'elle donne |
|---|---|
| règles (refus, abstention) | rien |
| repérage | « mounjaro » vise **6 CIS**, les six MOUNJARO du référentiel (`60830260`, `63052569`, `64888866`, `65111938`, `65553835`, `68186732`) ; un seul médicament nommé |
| table des sections | « Commission de la transparence » demande `avis_has` puis `avis` |
| recherche hybride (50 candidats) | les fragments des CIS visés ne sont qu'aux rangs **47 et 49**. Les dix premiers sont des fragments `avis_has` de la page `p_3538381` (MOUNJARO, Obésité, CT-20761, 2024) |
| déduplication | les dix restants viennent tous de CIS **non visés** : les pages de MOUNJARO (`p_3538381`, `p_4072400`) et d'autres avis |
| rappel par section | ne joue pas. Sa cible est le CIS visé le mieux classé parmi les dix, et aucun n'y est |
| porte structurelle | un médicament est visé, aucun des dix fragments n'est à lui : **abstention hors LLM** |

**Pourquoi.** Les pages d'avis de MOUNJARO se rattachent, par les liens de la BDPM, à 12 CIS
(`p_4072400`) et à 6 CIS (`p_3538381`). **Six de ces CIS sont absents du référentiel des
spécialités** (`CIS_bdpm.txt`) : `60930150`, `61022011`, `63816465`, `63925443`, `64061756`,
`67657964`.
- Leurs fiches sont partielles, sans dénomination (« CIS … — (dénomination inconnue) »). Le
  repérage, qui tire ses noms des dénominations, ne les vise donc pas.
- Leurs fragments d'avis portent pourtant le titre de la page, « MOUNJARO (tirzépatide) - … »,
  et la question en reprend les mots : ils se classent devant ceux des CIS visés.
- La déduplication garde le CIS visé d'une (page, partie) quand il est parmi les 50 candidats.
  Ici, il n'y est que deux fois.

Le texte de l'avis est donc trouvé, mais sous des CIS que le chemin ne relie pas au nom.

**Pourquoi la question 3 répond.** Elle nomme le dossier « CT-21681 », un mot exact du texte. La
recherche ramène alors les parties de `p_4072400` du CIS `68186732`, visé.

**Ce que c'est** : un défaut introduit par cette mission. À la mission 08, sans section
`avis_has`, ces fiches partielles n'avaient que leur fragment `avis` de la BDPM, sans le titre
de la page. Il touche les médicaments dont une partie des CIS liés à un avis manque au
référentiel.

**Ce que je ne fais pas** : aucune correction, aucune question ajoutée à la v2 (consigne de
l'IeC). La question 2 de la démonstration le reproduit, sans appel :
`chemin.preparer(…, "Quel progrès MOUNJARO apporte-t-il selon l'avis de la Commission de la
transparence ?")` rend `decision = porte_structurelle`. Pistes pour une prochaine mission, à
mesurer sur des questions écrites avant :
- ne rattacher une page d'avis qu'aux fiches du référentiel ;
- ou faire viser un CIS de fiche partielle par le titre de la page qu'il porte ;
- ou faire préférer, à la déduplication, un CIS du référentiel.

## 3. La constante 1,7 sur les trois appels

| question | clé au cache | caractères envoyés | jetons réels (entrée) | caractères par jeton | estimés à 1,7 | sortie |
|---|---|---|---|---|---|---|
| 1, KALYDECO | oui | 12 050 | 5 996 | 2,010 | 7 088 | 745 |
| 3, MOUNJARO CT-21681 | oui | 11 560 | 5 473 | 2,112 | 6 800 | 307 |
| 4, LARIAM | oui | 6 978 | 3 796 | 1,838 | 4 104 | 301 |

Aucun appel n'est sous-estimé. Avec les 105 de l'évaluation (`evaluation.md`), cela fait **108
appels et 0 sous-estimé**. La prose des avis (questions 1 et 3) compte plus de caractères par
jeton que les fiches : 1,7 y est encore plus prudent.
