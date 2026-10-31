# Mission 09 — contrôle du palier 3 par l'IeC

**Commits contrôlés** : `c80b795` (questions neuves de la table), `5bbf3a8`
(la table seule), `fa8a5be` (le jeu v2 complet) et `c8bd9e2` (ADR 0013, docs,
rapport). Ils sont revus contre l'ordre, l'addendum 1 et le contrôle du
palier 2.
**Verdict : palier 3 accepté. beko peut lancer la démonstration, puis
l'évaluation** de la v1 et ensuite de la v2, avec les commandes du §4 du
rapport. Je ne demande aucune correction de code. Deux points seront à écrire
dans `pr.md`.

## Revérifié par l'IeC

Dans ton dossier, arbre propre sur `c8bd9e2` :

| commande | résultat |
|---|---|
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **909 passed** |
| `questions verifier --questions evaluation/questions-reference-v2.toml` | 138 questions : 87 conformes, 10 non calculables, 41 sans attendu |
| `assistant evaluer --estimer` (v1) | 62 appels, 6,10 $ au pire, 0,98 $ probables, accordée |
| `assistant evaluer --estimer` (v2 seule) | 105 appels, 10,55 $ au pire, 1,67 $ probables, **refusée** |
| `make -n evaluer` avec `JEU_QUESTIONS` | la bonne commande |

**L'ordre des commits** est celui que demandait le contrôle du palier 2 :
- `c80b795` fige les cinq questions et leur règle écrite, avant le changement ;
- `5bbf3a8` ne touche que `sections.py` et ses tests ;
- `fa8a5be` ne modifie de la v1 que les trois comportements annoncés dans
  l'en-tête (`disponibilite-005`, `avis_has-004`, `-009`). Les 18 questions et
  les 5 questions figées restent fixées par leurs empreintes.

**La porte budgétaire** ajoute ce qui a déjà été dépensé à l'estimation
(`budget.exiger_budget`). La clé du cache ne dépend que du message envoyé,
pas de l'identifiant de la question. La v2 lancée après la v1 relit donc les
appels déjà payés. Si l'estimation était fausse, la porte refuserait : elle ne
peut pas laisser dépasser le plafond. La dépense probable des deux
évaluations est d'environ 2,7 $, soit 0,98 $ pour la v1 et environ 1,7 $ pour
la v2 entière, sur 10 $.

**La mémoire** de la première étape entière (721 pages, 78 461 fragments)
reste sous 512 Mo : 471 Mo pour `index construire` et 483 Mo pour
`index verifier`. Elle a été mesurée dans un espace Qdrant à part, effacé
ensuite. L'index du jeu est intact.

**La table** : quatre des cinq questions neuves retrouvent leur fragment
`avis`. La cinquième (WEGOVY) bute sur la limite de la question 2, écrite dans
l'ADR 0013. Comme convenu, on ne touche plus au rappel.

## À écrire dans `pr.md`

1. **19 questions sur le texte des avis, et non environ 24.** Le contrôle du
   palier 2 en annonçait environ 24. Ta règle en tire 19 : cinq thèmes, et
   quatre questions par thème, sauf trois pour le lien. Dis-le comme un écart,
   avec le nombre total de questions qui portent sur une page d'avis.
2. **Le score des questions médicales neuves**, en rappelant que `medical-013`,
   `-014` et `-016` ont servi à étendre la règle (contrôle du palier 2, point 1).

## Pour la suite

- **La démonstration d'abord**, puis la v1, puis la v2, dans cet ordre.
- Cite chaque sortie de beko dans un commit à part. Ajoute-y la vérification
  de la constante 1,7 sur les appels réels.
- Si une évaluation s'arrête sur la porte ou sur une erreur, ne relance rien :
  dis-le à beko et à l'IeC.
- Ensuite viennent `pr.md` et la relecture par une session neuve.
