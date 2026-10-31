# Mission 09 — décision de l'IeC sur la question 2 de la démonstration

**Objet** : « Quel progrès MOUNJARO apporte-t-il selon l'avis de la
Commission de la transparence ? ». L'assistant s'abstient, hors LLM, alors que
le texte de l'avis est dans l'index (diagnostic de `92aa78d`).
**Décision : on corrige dans cette mission, au palier 4.** Ce n'est pas
retenu comme une simple limite.

## Pourquoi corriger

- **C'est une régression de cette mission.** À la mission 08, les fiches
  absentes du référentiel n'avaient que leur fragment `avis`, sans titre.
  Le rattachement des pages leur donne maintenant le titre de la page, et ces
  fragments passent devant ceux des fiches que la question vise.
- **La question est la plus naturelle du corpus** : demander ce que dit l'avis
  sur un médicament nommé, sans numéro de dossier. Une page d'avis qui ne sert
  qu'à condition de connaître le numéro manque le but de l'ADR 0004.
- **La correction est une règle de périmètre, pas un réglage.** Une page ne se
  rattache qu'aux fiches que le référentiel nomme. Un fragment rattaché à une
  fiche sans nom ne peut être ni visé ni cité utilement : il ne fait que du
  bruit. On ne touche ni au rappel, ni à la table, ni au classement. Ce gel
  tient toujours.

Des trois pistes du codeur, je retiens la première. La deuxième (viser une
fiche partielle par le titre de sa page) et la troisième (préférer un CIS du
référentiel à la déduplication) sont deux heuristiques de plus.

## Le palier 4, dans cet ordre

1. **Mesurer l'ampleur, sans rien changer.** Sur les 721 pages et sur les
   150 du jeu, combien de pages et de fragments `avis_has` sont rattachés à un
   CIS absent du référentiel. Combien de pages n'ont **que** de tels CIS, et
   n'auraient donc plus aucun rattachement. Pour ces dernières, dis ce que tu
   proposes. Ne tranche pas seul.
2. **Figer d'abord des questions neuves**, tirées par une règle écrite et sans
   LLM : des médicaments dont une page est rattachée à la fois à des CIS du
   référentiel et à des CIS absents. La question prend la forme de la
   question 2 : « Quel progrès X apporte-t-il selon l'avis de la Commission
   de la transparence ? », sans numéro de dossier. Il en faut au moins trois,
   sans MOUNJARO, qui a servi à trouver le défaut. Leur empreinte est fixée
   par un test, dans un commit séparé.
3. **Ensuite**, un commit qui ne change que le rattachement et ses tests.
   `VERSION` de l'index ou de l'extracteur si le format le demande.
   `index verifier` doit rester conforme.
4. **Le jeu de démo** : reconstruire l'index, puis `index etat`. Mesurer la
   mémoire de `index construire` et de `index verifier` sur les 721 pages,
   comme au palier 3.
5. **`--estimer`** sur la v2. Puis les commandes pour beko : l'évaluation de la
   v2, puis la question 2 de la démonstration, rejouée. La v1 ne se relance
   que si l'estimation montre que ses messages changent.
6. **La mesure** se rend en trois parties :
   - les questions neuves du point 2 ;
   - la question 2 de la démonstration, rendue mais pas comptée comme preuve ;
   - aucune perte sur la v2, question par question, contre `4dec92b`.

## Ce qui ne change pas

- `4dec92b` et `92aa78d` restent la trace de l'état avant la correction.
  `pr.md` cite les deux évaluations, avant et après.
- Le budget reste 10 $ (2,17 $ dépensés). Les appels doivent partir avant le
  16/11.
- Si la correction fait perdre une question de la v2, ne retouche rien :
  dis-le à beko et à l'IeC.
