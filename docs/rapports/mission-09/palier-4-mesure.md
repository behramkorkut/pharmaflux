# Mission 09 — palier 4, point 1 : l'ampleur du rattachement aux fiches absentes du référentiel

## Synthèse

**Mesuré sans rien changer** (`decision-question-2.md`, point 1), sur la première étape entière
(721 pages extraites) et sur le jeu de démo (149 pages extraites) :
- 151 pages sur 721 portent au moins un CIS absent du référentiel (`CIS_bdpm.txt`) ;
- 1 111 fragments `avis_has` sur 6 165 sont rattachés à un tel CIS (18 %) ;
- **121 pages sur 721 (16,8 %) n'ont que des CIS absents**. Pour le jeu, c'est **18 pages sur
  149** (288 fragments sur 1 543).

Avec la règle « une page ne se rattache qu'aux fiches que le référentiel nomme », ces pages ne
seraient plus rattachées à rien : **la condition d'arrêt de la décision est atteinte.** Je
m'arrête après ce point, sans rien changer, et je propose trois voies sans trancher (§3).

## 1. La mesure

`index fragments` (lecture seule de l'archive), sur l'entrepôt du jeu à son instant :

| | première étape (721 pages) | jeu de démo (149 pages) |
|---|---|---|
| fragments `avis_has` | 6 165 | 1 543 |
| dont rattachés à un CIS absent du référentiel | **1 111** | **288** |
| CIS absents distincts | 211 | 45 |
| pages avec au moins un CIS absent | 151 | 29 |
| dont pages **mixtes** (CIS du référentiel et CIS absents) | 30 | 11 |
| dont pages qui n'ont **que** des CIS absents | **121** | **18** |

**Les 121 pages** sont surtout des médicaments récents ou pas encore commercialisés. Le
référentiel ne les nomme pas, mais le SMR et l'ASMR de la BDPM les lient à leur page. Exemples :
- KISUNLA, LEQEMBI (maladie d'Alzheimer) ;
- SHINGRIX, FLUENZ, FLUARIX (vaccins) ;
- RYBREVANT ;
- **MOUNJARO « Obésité »** (`p_3538381`, CT-20761) et **MOUNJARO « Diabète de type 2 »**
  (`p_3538387`), toutes deux rattachées aux six CIS absents de MOUNJARO.

La liste entière se retrouve par la commande ci-dessus.

**Ce qu'en fait la v2** (évaluation de `4dec92b`) :
- une seule réponse cite le fragment d'avis d'une fiche partielle : `avis_has-047`, une
  abstention juste ;
- aucune question de la v2 ne porte sur l'une des 18 pages du jeu qui perdraient tout
  rattachement.

## 2. La question 2, simulée sans rien changer

La simulation repose sur un filtre de recherche sur l'index actuel : les fragments que chaque
règle retirerait sont exclus par Qdrant. Elle est approchée, car l'IDF du lexical reste celle de
l'index entier.

| règle | fragments des CIS visés (MOUNJARO du référentiel) dans les dix | porte structurelle |
|---|---|---|
| actuelle | 0 | abstention |
| **A** : une page ne se rattache qu'aux fiches du référentiel | **4**, dont le premier (`p_4072400`) | passe |
| **B** : la règle A sur les seules pages mixtes, les pages sans fiche nommée gardent leurs fiches partielles | 1, au rang 3 | passe de justesse ; les fragments de `p_3538381` (Obésité) restent dans les dix |

## 3. Trois voies, sans trancher

**A. La règle stricte, telle que décidée.**
- Ce qu'elle apporte : la question 2 passe nettement. Aucun fragment n'est plus rattaché à une
  fiche sans nom, qui ne peut être ni visée ni citée utilement, et la règle est simple.
- Ce qu'elle coûte : le texte de **121 pages (16,8 %) quitte l'index**, soit 18 pages du jeu.
  Parmi elles, l'avis « Obésité » de MOUNJARO.
- Aujourd'hui, une question qui nomme l'un de ces médicaments n'en vise aucun (le repérage ne
  connaît pas son nom). Elle peut pourtant trouver ce texte par la recherche, et le LLM peut le
  citer (comme `avis_has-005` pour le SMR d'un CIS absent, « avec réserve »). Avec A, elle ne le
  trouverait plus.

**B. La règle sur les seules pages mixtes.**
- Ce qu'elle apporte : aucune page ne perd son rattachement.
- Ce qu'elle coûte : le défaut de la question 2 n'est corrigé qu'à moitié. Une page sans fiche
  nommée (MOUNJARO Obésité) qui partage le nom d'un médicament du référentiel continue de
  l'encombrer.

**C. A, en rendant la perte visible.** La règle A, et l'état de l'index qui compte et liste les
pages sans fiche nommée (« pages sans fiche du référentiel : 121 »), comme les contrôles de
dossier impossibles. L'ADR 0013 l'écrit comme limite du corpus.

**Mon avis, pour éclairer ta décision** : C. Ton argument tient : un fragment sur une fiche
sans nom ne fait que du bruit. B laisse le même défaut par une autre page. Le texte perdu
est rendu visible, et le rattacher par le titre de la page serait la piste 2, que tu as écartée.
Mais c'est 17 % du corpus : la décision t'appartient.

Rien n'est changé dans le code. Le palier 4 reprend au point 2 après ta réponse.
