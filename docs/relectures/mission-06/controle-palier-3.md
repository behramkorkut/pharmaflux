# Mission 06 — contrôle du palier 3 (IeC)

**Commit contrôlé** : `c3c36de` (fils de `e2d8e79`, qui porte le contrôle du
palier 2 tel quel). Il est contrôlé contre l'ordre et l'addendum 1
(`36d815e`). **Verdict : conforme, la clôture de l'ordre est atteinte.
Deux corrections de documentation sont à faire par un nouveau commit,
avant la relecture.**

## Revérifié par l'IeC

Dans le dossier du codeur, arbre propre sur `c3c36de` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 58 fichiers |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true`, courtier présent | 535 passed en 2 min 26 s, dont les tests d'intégration |

Relu :

- **`Makefile`** : `gold` enchaîne `gold qualite` puis `questions verifier
  --entrepot`. Make s'arrête au premier code non nul, donc un bloquant
  arrête la cible avant les questions. `fiche` ne passe `--a` que si `A` est
  donné sur la ligne de commande (`$(origin A)`), ce qui fonctionne avec
  GNU Make 3.81. Le `make -n` est dans le rapport.
- **CI** : l'étape `make gold` vient juste après `make silver`, dans le job
  `integration`. Le job `verifier` ne change pas.
- **`conftest.py`** : le commentaire demandé est là. La règle du premier
  instant observé est dans le message de refus, et elle est testée.
- **ADR 0010** : il couvre la forme, les instants, le typage, les vues, les
  contrôles, les questions et `fin_validite` hors du gold. Il a aussi une
  section « Limites » pour le constat 2 du palier 1.
- **Aucun chemin du poste, aucune IP, aucun hôte** dans le diff de la
  mission (`74c52e4..c3c36de`).
- **La clôture de l'ordre est atteinte.** beko, sur le Mac, a enchaîné
  `make rebatir`, `make demo`, `make silver` (22/22) puis `make gold`. Le
  résultat : aucun bloquant, et 25 questions sur 25 concordantes depuis le
  gold.

## Corrections avant la relecture (un commit)

1. **La section « État » du README** en est restée à la mission 02 :
   « Mission 02 en cours », un tableau où le Lot 1 est « à venir » et le
   Lot 2 aussi. C'est la première chose qu'un lecteur du dépôt voit, et
   elle contredit le reste de la page. Tu la proposais hors mission ; elle
   entre dans la décision 7 (le README), et elle se corrige maintenant :
   - un paragraphe court par mission fusionnée (00 à 05), puis la
     mission 06 ;
   - le tableau des lots :
     - Lot 0 : fait ;
     - Lot 1 : fait sur le Mac, le VPS reste ;
     - Lot 2 : fait à la fusion de cette mission ;
     - les autres : à venir.

   Reste sobre : les détails sont plus bas dans la page et dans les ADR.
2. **L'aide de `make fiche`** dit « sans A_FICHE », alors que la variable
   s'appelle `A`. Corrige en « sans A ».

## Propositions pour `pr.md`

Les deux autres propositions sont retenues pour `pr.md` :
- la détection qui compare aussi les anomalies ;
- la date du dernier fichier retenu, portée par le silver.

L'IeC les portera au PRD.

## Suite

Après le commit de ces deux corrections, beko avance le relecteur sur son
sommet, et la relecture (`/relire-mission 06`) commence.
