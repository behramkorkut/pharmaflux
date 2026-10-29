# Mission 05 — contrôle du palier 3 (IeC)

**Commit contrôlé** : `63118d6` (fils de `b90c492`, qui porte le contrôle du
palier 2 tel quel). Il est contrôlé contre l'ordre et l'addendum 1
(`b5b9420`). **Verdict : conforme. La mission passe à la relecture.**

## Revérifié par l'IeC

Dans le dossier du codeur, arbre propre sur `63118d6` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 51 fichiers |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true`, courtier présent | 498 passed en 2 min 00 s, dont les tests d'intégration |

Relu :

- **`Makefile`** : `silver` enchaîne `consommer` puis `verifier`. Make
  s'arrête au premier code non nul, donc la vérification a bien le dernier
  mot. `etat` passe ses trois variables. `rebatir` ne change pas : son
  `rm -rf data/demo` emporte l'entrepôt, et `make help` le dit maintenant.
  Rien de GNU Make 3.82 ou 4.x.
- **CI** : l'étape `make silver` est dans le job `integration`, après
  `make demo` et avant le journal d'échec et le `down -v`. Le job
  `verifier` ne change pas. La décision 5 est tenue.
- **ADR 0009** : il contient tout ce que demande la décision 7. Il y
  ajoute :
  - la règle des plafonds temporaires (contrôle du palier 1) ;
  - la raison de l'absence d'`allowed_directories`, en options écartées ;
  - les mesures de mémoire et le seuil de 512 Mo ;
  - la cible des 256 Mo, qui ne vaut pas pour le silver en v1.
- **README** : les deux exemples sont réels, et ils tournent sur le silver
  rebâti par beko (1, 0 et 10 905 lignes). Le second dit bien « juste
  après 14:17:39 ». La règle sur le temps de la connaissance (horodatage de
  l'archive, pas du passage) est écrite pour le lecteur.
- **Aucun chemin du poste, aucune IP, aucun hôte** dans le diff de la
  mission (`7103e8b..63118d6`).
- **La clôture de l'ordre est atteinte** : beko, sur le Mac, a enchaîné
  `make rebatir`, `make demo` puis `make silver`. Le résultat : 164 106
  messages, puis 22/22 archives conformes (18 retenues, 4 écartées).

## D.1

Il est réglé, et c'est la meilleure issue possible :
- la grappe change à chaque `down -v` ;
- l'avertissement sort ;
- le contrôle des `id` reconnaît un bus rebâti à l'identique, parce que
  l'`id` est le sha256 du contenu de l'événement, et répond « rien de
  nouveau ».

L'avertissement sans refus, retenu à l'addendum, était donc le bon choix.

## Écarts du rapport

1. **`profil` et `questions verifier` non rejoués** : accepté. Aucun
   fichier de `src/` n'a changé depuis le palier 2. Pour `pr.md`, rejoue
   quand même toute la non-régression de l'ordre sur le commit testé, en
   une passe : ce sont les vérifications de la mission entière.
2. **La durée de l'étape CI** : elle va dans `pr.md` après la publication,
   comme l'addendum le prévoit.

## Pour la suite

- **beko** efface le témoin `data/lakehouse-temoin-d1` dans
  `pharmaflux-codeur/`.
- **La relecture** (`/relire-mission 05`) se fait dans une session neuve,
  dans `pharmaflux-relecteur/`, qu'on aura avancé sur le sommet du codeur.
- **Dans `pr.md`** :
  - les écarts acceptés des trois paliers ;
  - la mesure « plus longue que le jeu », reportée au prochain
    rapatriement ;
  - la mémoire ;
  - `--continu`, en proposition.
