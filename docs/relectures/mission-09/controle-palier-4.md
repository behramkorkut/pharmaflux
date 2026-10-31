# Mission 09 — contrôle du palier 4 par l'IeC

**Commits contrôlés** : `9694be7` (la mesure), `34dca25` (six questions
neuves), `aba5173` (le rattachement seul) et `a1ae12a` (ADR 0013, docs,
rapport). Ils sont revus contre `decision-question-2.md` et sa suite.
**Verdict : palier 4 accepté. beko peut lancer l'évaluation** avec les
commandes du §4 du rapport, en ajoutant une estimation avant la v2 (voir plus
bas). Aucune correction n'est demandée.

## Revérifié par l'IeC

Dans ton dossier, arbre propre sur `a1ae12a` :

| commande | résultat |
|---|---|
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **913 passed** |
| `index etat` (jeu de démo) | format 4 ; 73 551 fragments, dont 1 255 `avis_has` (288 de moins) ; 18 pages sans fiche du référentiel, listées |
| `questions verifier` v2 | 144 questions : 91 conformes, 10 non calculables, 43 sans attendu |
| `assistant evaluer --estimer` v1 | 47 appels, 4,64 $ au pire, 0,87 $ probables, accordée |
| `assistant evaluer --estimer` v2 seule | 81 appels, 8,15 $ au pire, refusée (7,83 $ restants) |

**L'ordre des commits** est celui de la décision :
- `34dca25` fige les six questions et leur règle, sans toucher à `src` ;
- `aba5173` ne touche ni aux questions, ni à `assistant/`. Il ne change que
  le rattachement (`fragments.py`), le compte des pages sans fiche
  (`pages_has.py`), leur affichage et leurs tests.

**Lu dans le code** : la règle est écrite à un seul endroit
(`_avis_has` : une fiche hors du référentiel ne produit aucun fragment
`avis_has`). Les pages sans fiche se calculent à chaque construction et à
chaque mise à jour. Le passage au format 4 force une reconstruction, ce qui
est juste : une mise à jour garderait les fragments des fiches non touchées.
Le test « page écartée, puis rattachée quand sa fiche entre » est celui que
demandait la décision, et il compare aussi la mise à jour à la
reconstruction.

**La mémoire** sur la première étape baisse : 425 Mo pour la construction,
444 Mo pour la vérification.

## Le coût

Retirer 288 fragments change l'IDF du lexical, donc l'ordre des fragments et
les messages. La v1 se relance donc, selon la règle de la décision.

| étape | au pire | probable |
|---|---|---|
| v1 | 4,64 $ | 0,87 $ |
| v2, après la v1 | environ 3,4 $ | environ 0,6 $ |
| question 2 | 0,10 $ | 0,02 $ |

La dépense probable de la mission finira autour de 3,7 $ sur 10 $. La porte
fait la vérification qui compte : elle ajoute à chaque estimation ce qui a
déjà été dépensé. Si la v1 coûtait beaucoup plus que prévu, la v2 serait
refusée, et le plafond ne serait pas dépassé.

**À ajouter aux commandes de beko** : `--estimer` sur la v2, après la v1 et
avant la v2 payante. Il confirme que la porte accorde la v2 et montre combien
d'appels la v1 a mis en cache.

## Pour la suite

1. Cite les sorties de beko dans un commit à part, avec la comparaison
   question par question contre `4dec92b`. Rends en trois parties :
   - les six questions neuves ;
   - la question 2 de la démonstration, rendue mais pas comptée ;
   - les questions perdues et gagnées sur la v1 et la v2.
2. Si une question est perdue, ne retouche rien : analyse-la depuis le texte
   de la réponse.
3. Ensuite, `pr.md`, avec les points déjà demandés :
   - les 19 questions sur le texte au lieu d'environ 24 ;
   - la réserve sur `medical-013`, `-014` et `-016` ;
   - les limites (les liens non filtrés par dossier, le lien rendu en double,
     les pages sans fiche du référentiel) ;
   - les deux évaluations, avant et après le palier 4.
