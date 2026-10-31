# Mission 09 — contrôle du palier 2 par l'IeC

**Commits contrôlés** : `07ac561` (infrastructure), `bbb9809` (questions
neuves de la v2) et `ee2f0a6` (retouches et rapport), revus contre l'ordre,
l'addendum 1 et mes réponses par message (rejets, extracteur v2).
**Verdict : palier 2 accepté. beko peut lancer la démonstration** avec les
commandes du §6 du rapport. Je réponds aux deux questions plus bas : la
première est acceptée sous condition, la seconde est refusée.

## Revérifié par l'IeC

Dans ton dossier, arbre propre sur `ee2f0a6` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run mypy src` | verts |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **889 passed** |
| `index etat` (jeu de démo, Qdrant du Mac) | format 3 ; 1 543 fragments `avis_has` ; pages collectées jusqu'au 2026-10-31T13:07:40Z, manifeste lu jusqu'à la ligne 150, extracteur v2 ; 149 extraites, 1 rejetée, 5 contrôles de dossier impossibles, listés |
| `assistant evaluer --estimer` sur la v2 | 106 questions, 31 hors LLM, 75 appels, 7,42 $ au pire, 1,19 $ probables, accordée ; **466 Mo** |

**L'ordre des commits** est celui que demandait l'addendum (H) :
- `07ac561` écrit la table des sections et la liste des mots courants **sans
  les brancher**. Ce qu'il change au chemin ne concerne que le rendu des
  liens, les deux horloges et le masquage des adresses, ce qui n'est pas une
  retouche ;
- `bbb9809` fige les 18 questions neuves ;
- `ee2f0a6` branche les retouches **sans toucher au fichier des questions**.

**Lu dans le code et le rapport** :
- **le LLM ne voit aucune adresse**. Les trois fragments qui citent une URL
  dans le texte de l'avis la voient masquée à l'envoi, et gardée dans
  l'index. Une adresse écrite par le LLM rend sa réponse non vérifiable ;
- **le rendu des liens** donne la page, avec la date de l'avis, la mise en
  ligne (ou la mise à jour) et la consultation, puis les deux horloges.
  C'est ce que demande la licence ;
- **la partie BDPM du jeu** est identique à `beba0c8`, et un test le prouve ;
- **`avgdl` remesurée** (55,44) : aucun rappel à 10 ne recule. C'est la
  condition de l'addendum (F2), elle est tenue ;
- **les deux réglages de mémoire** ne changent aucun vecteur, et
  `index verifier` reste conforme (cosinus minimal 0,9964).

## Les deux questions

**Question 1 (SMR et ASMR vers `avis` seul) : acceptée, à une condition.**
Le défaut se voit sans aucun résultat du modèle. Le dernier SMR d'un
médicament est toujours dans le fragment `avis` de la BDPM, alors qu'une page
d'avis de la HAS peut être plus ancienne, ou absente (OZEMPIC). La table
avait donc tort de tenir « SMR » pour satisfait par `avis_has`.

La condition est celle de l'ordre : le changement se mesure sur des
questions qui n'ont pas servi à le trouver.
1. **D'abord**, un commit qui ajoute à la v2 des questions neuves tirées par
   une règle écrite et sans LLM, avant le changement :
   - les CIS dont le dernier SMR ou ASMR n'est que dans le fragment `avis`,
     alors qu'un fragment `avis_has` plus ancien du même CIS est dans les dix ;
   - au moins trois questions ;
   - leur empreinte fixée par un test, comme pour les dix-huit.
2. **Ensuite**, un commit qui change la table, et seulement elle.
3. `avis_has-003` et `-014` ont servi à trouver le défaut : ils sont rendus,
   mais ne comptent pas comme preuve.
4. **C'est la dernière retouche du rappel dans cette mission** : quel que soit
   le résultat, on ne touche plus à la table après la mesure.

**Question 2 (la cible du rappel quand plusieurs CIS sont visés) : refusée.**
Ce serait une heuristique de plus, que seul OZEMPIC motive, et qui se
réglerait sur la question même. La cible reste le CIS le mieux classé, et
l'ADR 0013 l'écrit comme limite.

## À faire au palier 3

1. **Les trois questions médicales neuves qui ont fait étendre la règle**
   (`medical-013`, `-014`, `-016`) ne mesurent plus cette règle : elles ont
   servi à la trouver. L'extension ne se juge que par l'absence de faux refus
   (v0, v1, v2, 200 questions factuelles). `pr.md` le dit en rendant le score
   des questions médicales neuves.
2. **La mémoire de l'index sur la première étape entière.** Le palier 2 a
   mesuré 149 pages : `index construire` 493 Mo, `index verifier` 496 Mo,
   pour un seuil de 512 Mo. La première étape en compte 721.
   - Mesure, avant la séquence de beko, `index construire` et
     `index verifier` avec `--archive-has ~/pharmaflux-data` (les 721 pages,
     environ 7 400 fragments d'avis), dans une collection à part, puis remets
     l'index du jeu.
   - Si l'une des deux commandes passe 512 Mo, dis-le et propose une
     séparation avant d'aller plus loin. N'ajuste rien sans réponse.
3. **Le jeu v2 complet**, tel que l'addendum le prévoit :
   - les questions sur le texte des avis (environ 24) ;
   - les pièges, dont PEDMARQSI, la page rejetée ;
   - les trois questions qui demandent le PDF ;
   - la comparaison (G3) ;
   - les questions de la question 1 ci-dessus.

   Ces questions s'ajoutent sous de nouveaux identifiants, sans toucher aux
   dix-huit questions figées.
4. **La démonstration de beko**, citée dans un commit à part, avec la
   vérification de la constante 1,7 sur ses appels (I1).
5. **L'ADR 0013**, et la ligne « complété par » de l'ADR 0004.

## Remarque, sans correction

- **Le garde-fou a refusé un `sed`** dont la commande nommait
  `infra/agents/avec-cle.sh`, alors que la cible était ton rapport. C'est un
  faux positif connu de la règle sur `avec-cle.sh`, et tu ne l'as pas
  contourné. Je le note pour beko, avec le refus de `shasum` du palier 1.
