# Mission 08 — contrôle du palier 3 par l'IeC

**Commit contrôlé** : `c4ddec8` (notation, `assistant evaluer`, ADR 0012),
revu contre l'ordre, les addenda 1 et 2, les contrôles des paliers 1 et 2,
et mes réponses par message (Q1 à Q3, conditions sur « deux médicaments »).
**Verdict : palier 3 accepté. L'évaluation complète peut être lancée par
beko.** Un test reste à ajouter avec le commit de clôture (voir plus bas).
Il ne bloque pas l'évaluation, parce que la notation se rejoue sur le
cache, sans dépense.

## Revérifié par l'IeC

Dans ton dossier, l'arbre propre sur `c4ddec8` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | verts (288 fichiers) |
| `uv run mypy src` | vert, 78 fichiers, sans l'override d'`anthropic` |
| `GITHUB_ACTIONS=true uv run pytest -q -rE` | **703 passed** en 7 min 08, session verte |
| `assistant evaluer --estimer` (vrai index, sans clé) | 88 questions, 26 hors LLM, 0 en cache, **62 appels**, 5,3985 $ prudent, 0,8919 $ probable, reste 19,9568 $ : accordée ; 10,7 s |

Lus dans le code et le rapport :
- **La notation** (`notation.py`) est déterministe, sans juge LLM.
  - Elle s'appuie sur deux tables de colonnes, chacune avec sa raison, et
    une colonne inconnue arrête la notation.
  - Les deux conditions dures sont distinctes : aucune citation invalide,
    et aucune question `medical` sans refus.
  - Une paraphrase compte comme absente, et la mesure se dit borne basse.
    C'est ce que j'avais accepté en Q1.
- **La porte** additionne, avant le premier appel, les estimations des
  appels absents du cache. `--estimer` ne demande ni clé ni appel, et un
  test le garantit (`test_cli_evaluer_estimer_sans_cle`).
- **« Deux médicaments »** : la règle a changé pour tenir le test
  indépendant, sur 200 médicaments tirés avec la graine 8. Elle donne 0
  faux positif quand les médicaments sont posés seuls, et 0 paire manquée.
  L'ancienne règle se trompait 31 fois.
  - L'exception « groupe » est bornée par les libellés de groupe de
    l'index, et testée dans le sens fermé.
  - L'écart est déclaré, avec la façon dont le défaut a été trouvé.
- **Les dates** :
  - elles se lisent de 1900 à 2099 ;
  - une année seule ou « mois + année » s'appuient sur les dates citées ;
  - les tests vont dans les deux sens.
- **Les cinq questions passées en abstention** gardent leur identifiant, et
  l'ancienne valeur reste en commentaire. Le changement est déclaré, et il
  a été fait avant toute évaluation réelle. `questions verifier` reste
  vert sur la v1 et la v0, d'après ton rapport.
- **Les tests D2 sur la v1 entière** manquaient au palier 2 alors que la
  docstring les annonçait. Ils sont écrits. Je n'avais pas vu ce manque à
  mon contrôle du palier 2 : bien relevé.
- **Les remarques du palier 2** sont reprises :
  - le texte d'une abstention ou d'un refus du LLM est contrôlé ;
  - un refus prend la forme du code ;
  - une erreur de l'API sort en code 2 ;
  - l'override mypy est retiré.
- **`make rebatir`** n'efface pas `data/assistant/`. Le test du `Makefile`
  le montre, et aucune cible n'enchaîne `evaluer` (G3, H3).
- **Le prompt système** a deux consignes de plus : « aucun signalement à
  cette date », et les valeurs reprises telles que les fragments les
  donnent. Ce sont des consignes générales, conformes à l'ADR 0003.
  Comme le prompt a changé, les trois réponses en cache de la démonstration
  ne servent plus ; il en coûte environ 0,04 $.

## À ajouter avec le commit de clôture

1. **Relier les deux tables à ce que rend vraiment `fragments.py`.**
   Aujourd'hui, `test_chaque_colonne_d_attendu_v1_est_classee` vérifie
   seulement que chaque colonne est classée. Il ne vérifie pas que le
   classement est **vrai**. Le seul motif admis pour « non due » est
   l'absence du texte des fragments, et rien ne l'éprouve.

   À faire : un test qui rend le texte des fragments, depuis `demo/` ou une
   fixture, pour quelques questions v1 de chaque catégorie, et qui vérifie
   deux choses :
   - chaque valeur d'une colonne **due** se retrouve dans ce texte, avec la
     même comparaison que la notation ;
   - aucune valeur d'une colonne **hors texte** n'y paraît, quand elle est
     non vide.

   Si une colonne se révèle mal classée, corrige la table et **re-note sur
   le cache**, sans nouvel appel. Dis-le dans `pr.md`.
2. **Citer la sortie de beko** dans `palier-3.md` puis dans `pr.md` :
   - la sortie entière de `make evaluer` et celle de `depenses` ;
   - les indicateurs du §2.2, qu'ils atteignent leur cible ou non ;
   - les deux conditions dures ;
   - le nombre d'abstentions techniques ;
   - pour chaque question fausse, la raison que donne sa note.

## Pour la séquence de beko

- `make rebatir` lance `docker compose -p pharmaflux down -v`, ce qui
  **efface les volumes de Qdrant et de Redpanda du projet**. L'ordre le
  veut (« la séquence jusqu'à `make index` »), et le cache des vecteurs
  (`data/index`) comme `data/assistant` sont gardés. Le rapport doit
  néanmoins le dire en une ligne au-dessus de la séquence.
- Si l'évaluation s'arrête au milieu, sur une erreur de l'API ou une
  coupure, les réponses déjà obtenues sont au cache. Une seconde passe ne
  repaie que les autres, et `--estimer` dira combien il en reste.

## Remarques, sans correction

- **Le modèle de rapport** (« quinze lignes au plus ») : ta proposition est
  notée pour `docs/agents/processus.md`, à la prochaine révision des
  consignes.
- **Les liens rendus par le code** (mission 10) : notés.
