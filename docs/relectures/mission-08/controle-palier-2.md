# Mission 08 — contrôle du palier 2 par l'IeC

**Commit contrôlé** : `c1c8d26` (l'assistant gouverné), revu contre l'ordre,
l'addendum 1 (`385490b`), l'addendum 2 (`27b0440`) et le contrôle du
palier 1. **Verdict : palier 2 accepté, sous réserve d'un commit correctif
court (point 1 ci-dessous), à faire avant la démonstration.** La
démonstration des cinq questions se fait ensuite, sur ce commit correctif.

## Revérifié par l'IeC

Dans ton dossier, l'arbre propre sur `c1c8d26` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | verts (281 fichiers) |
| `uv run mypy src` | vert, 76 fichiers |
| `uv run pytest tests/test_assistant.py tests/test_questions.py -q` | 64 passed |
| `GITHUB_ACTIONS=true uv run pytest -q -rE` | **649 passed** en 5 min 51, session verte, **aucun réessai du registre** cette fois |
| `uv.lock`, de `1d2c20d` à `c1c8d26` | **aucune ligne retirée** ; seuls `anthropic`, `docstring-parser`, `jiter`, `opentelemetry-api` et `sniffio` sont ajoutés |

Lus dans le code :
- **Le chemin** (`chemin.py`) suit l'ordre de l'addendum B :
  1. le refus médical ;
  2. les abstentions dures ;
  3. les deux médicaments ;
  4. la recherche hybride ;
  5. la porte structurelle ;
  6. la porte budgétaire, puis le LLM et le cache ;
  7. le contrôle.

  Aucune décision des étapes 1 à 5 n'appelle le LLM.
- **L'appel** est conforme à l'API d'Opus 5.5 :
  - `output_config` porte l'effort et le format JSON ;
  - aucun `thinking` n'est passé, ce qui revient à la pensée adaptative, qui
    ne se désactive pas sur ce modèle ;
  - ni `temperature` ni modèle de repli ;
  - un `stop_reason` égal à `refusal` ou `max_tokens` donne une abstention
    technique.
- **Les étiquettes** : la citation hors des fragments fournis et la réponse
  sans citation sont deux abstentions distinctes, chacune avec son motif.
- **Le contrôle des nombres et des dates** relie bien `20260909` à
  « 9 septembre 2026 » et à « 09/09/2026 » (remarque du palier 1). Le
  contrôle retire les dates du texte avant d'y chercher les nombres. Un CIS
  à 8 chiffres n'y est jamais lu comme une date, puisque l'année doit
  tomber entre 2000 et 2099.
- **La porte budgétaire** ajoute l'entrée estimée au caractère et
  `max_tokens` entier en sortie. Elle n'appelle jamais `count_tokens`.
  Le coût réel est lu dans `usage`, et la grille porte la lecture du cache
  à 0,20 $.
- **`disponibilite-011`** passe sans refus : « mon traitement » sans geste
  de soin ne déclenche pas la règle.

## Les trois points du palier 1

1. **`depense` en v1** : fait. La v0 est intacte, et deux tests le figent.
2. **Le RRF côté client** : déclaré. Il reste à l'écrire dans l'ADR 0012 au
   palier 3.
3. **La piste keep-alive** : **d'accord pour ne pas corriger le client.**
   - Tu as fait ce qui était demandé : lire le délai des deux côtés, puis
     t'arrêter faute de preuve.
   - La règle de la mission 07 reste en place : la session échoue s'il reste
     un réessai.
   - Si la coupure revient en CI, on aura un deuxième cas daté, à comparer
     avec le mien. C'est à ce moment-là qu'un `keepalive_expiry` plus bas se
     discutera, pas avant.

## À corriger avant la démonstration (commit correctif)

1. **Un appel payé doit toujours entrer au journal.** Dans
   `ClientClaude.repondre`, la sortie est lue par `next(... "text")` puis
   `json.loads` et les clés `donnees[...]`. Si l'une de ces lectures échoue,
   l'exception sort **avant** que `chemin.demander` ait journalisé l'appel :
   - l'appel est payé ;
   - mais `depenses.jsonl` ne le compte pas ;
   - et la porte du plafond sous-estime la suite.

   La sortie structurée rend ce cas rare, mais la règle du budget est une
   règle dure (addendum G).

   **À faire** : toute sortie illisible, c'est-à-dire un bloc texte absent,
   un JSON invalide ou une clé manquante, devient une **abstention
   technique** avec son `usage`, et sa cause est journalisée comme pour
   `max_tokens`. Ajoute un test avec le double, sur un faux objet de réponse
   ou par une fonction de lecture extraite, qui montre que la ligne est
   écrite.
2. **Une abstention technique ne va pas au cache.** Aujourd'hui, elle y est
   écrite. Une réponse tronquée à l'effort `low` reviendrait donc à chaque
   reprise de l'évaluation sans nouvel essai, et elle fausserait la mesure
   du palier 3. Ne mets au cache que ce que le modèle a effectivement rendu.
   Le coût de l'appel reste journalisé. Ajoute un test.

## La démonstration des cinq questions

Le choix des cinq questions me convient :
- trois appels réels, qui couvrent un statut daté, un taux et la réserve
  d'un CIS hors référentiel (avec la date `20260909`) ;
- un refus et une abstention hors du LLM, à 0 $.

Une précision pour le rapport : `avec-cle.sh` **existe**, sur `main`, au
commit `27b0440`. Ta branche part d'avant, d'où ton constat. Comme le code
de l'assistant n'est que sur ta branche, beko lance la démonstration
**depuis ton dossier**, avec le script de `main` :

```
sh ../pharmaflux/infra/agents/avec-cle.sh uv run pharmaflux assistant demander "…"
```

Corrige la phrase « n'existe pas encore » dans ton rapport. Une fois la
sortie de beko reçue, cite-la avec le coût réel de chaque appel et le reste
que donne `pharmaflux assistant depenses`.

## Remarques, sans correction ici (palier 3)

- **Le cache du prompt** : le prompt système fait quelques centaines de
  jetons, sous le minimum que l'API met en cache. Le `cache_control` y est
  donc sans effet : ce n'est pas faux, mais c'est inutile. Les jetons
  `cache_*` de la démonstration le montreront. Si c'est nul, dis-le dans le
  rapport, sans changer le code.
- **Le texte d'une abstention ou d'un refus rendu par le LLM** n'est pas
  contrôlé : `_apres_llm` le rend tel quel. Au palier 3, soit tu le
  contrôles comme une réponse, soit tu le remplaces par le motif seul. Sinon,
  un fait non appuyé peut passer par ce chemin.
- **Une erreur de l'API**, par exemple une surcharge ou un délai dépassé,
  sort en trace Python. Rien n'est payé dans ce cas, mais `demander` devrait
  la rendre en code 2, avec une ligne lisible, comme les autres refus.
- **`pyproject.toml`** : le commentaire de l'override mypy (« peut manquer
  tant que beko n'a pas verrouillé le uv.lock ») ne tient plus, puisque le
  verrou est fait. Raccourcis-le.
