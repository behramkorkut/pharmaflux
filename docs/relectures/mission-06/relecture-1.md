# Mission 06 — relecture 1
**Commit relu** : `d2c8748` (sommet de `mission-06-gold-et-qualite`)
**Verdict** : CONFORME

Relu contre l'ordre et l'addendum 1 (`git show main:docs/missions/mission-06-gold-et-qualite.md`),
les trois rapports de palier et les trois contrôles de l'IeC. Premier tour : aucune réponse
de relecture antérieure à vérifier.

## Bloquants

Aucun.

## À corriger (non bloquants)

1. `src/pharmaflux/gold/vues.py:558` et `tests/references_gold.py:195`. Constat : quand deux
   lignes fermées au même instant visent la même présentation, la vue et sa référence ne
   départagent pas pareil. `_ordre` compare `str(valeur)`, donc un nul devient `"None"`, qui
   passe devant toute date (`"N" > "2"`) : c'est la ligne au champ nul qui gagne. La requête
   de référence trie en `DESC` sous `NULLS_LAST`, le défaut de DuckDB (vérifié :
   `current_setting('default_null_order')`), et c'est donc la ligne au champ renseigné qui
   gagne. Exemple : deux lignes sans CIP13 d'une même spécialité, retirées par la même
   archive, de même statut, dont l'une a une `date_remise_a_disposition` et l'autre non. Ni
   les fixtures ni le jeu ne contiennent ce cas : l'égalité de l'exigence 1 ne le voit pas.
   La ligne de `fin_de_publication` retenue serait différente dans la vue et dans la
   référence. Attendu : le même départage des deux côtés (par exemple un nul rendu `""`
   dans `_ordre`, ou `NULLS FIRST` dans la référence), et ce cas ajouté à la disponibilité
   synthétique de `test_gold_vues.py`.
2. `src/pharmaflux/cli.py:1531` (`gold alternatives --cip13`/`--cis`) et `gold disponibilite
   --cip13`. Constat : avec un CIP13 inconnu (`0000000000000`, essayé sur le silver du jeu),
   les deux commandes répondent `0 ligne(s)` avec le code 0. `gold fiche --cis` inconnu,
   lui, sort en code 2 (« aucun fichier ne cite le CIS … »). Une coquille dans un code donne
   donc une réponse vide qui se lit comme un fait (« aucune alternative »), ce que l'ordre
   veut éviter partout ailleurs (la vue distingue l'absence de signalement d'un statut).
   Attendu : le même refus que `gold fiche` quand le CIP13 ou le CIS demandé n'est pas
   connu à l'instant, et un test.
3. `src/pharmaflux/gold/rendu.py:97`. Constat : une présentation sans prix s'affiche
   « prix public — € » (sortie réelle du README, CIS 63830632). Attendu : « prix public — »
   sans unité quand la valeur manque. C'est cosmétique, mais c'est l'exemple du README.

## Remarques

1. **La fiche ne porte pas la fin de publication.** Sa section `disponibilite`
   (`vues.py:324`) ne liste que les signalements en cours. Pour un CIS dont la ligne a été
   retirée, la fiche en texte dit « aucun signalement dans le fichier de disponibilité »,
   alors que `disponibilite_courante` dit `fin_de_publication` pour les mêmes
   présentations. La phrase est exacte, et l'ADR 0010 parle bien de « signalements ». Mais
   le Lot 3 indexera la fiche : il faudra soit y ajouter la fin de publication, soit écrire
   dans l'ADR que la fiche ne dit que l'en-cours, et que l'histoire récente se lit dans la
   vue de disponibilité. C'est à l'IeC de trancher, ici ou au Lot 3.
2. **Une information importante dont la `date_debut` est illisible disparaît de la fiche**
   (`vues.py:383`, un nul vaut « pas commencée »). Seul `colonnes_illisibles` le signale. Le
   cas ne se présente pas sur le jeu (une seule valeur illisible dans tout l'état, un
   numéro d'AMM européenne). Le choix est défendable, puisqu'on ne devine pas, mais il
   mérite une ligne dans l'ADR, aux côtés de la règle « fin vide = en cours ».
3. **Mémoire** : mes mesures sur le Mac sont un peu au-dessus de celles des rapports, et
   toujours sous le seuil. `questions verifier --entrepot` monte à **470 Mo** (le rapport
   annonce 452), `gold fiche --tout` à 424 Mo (415), `gold alternatives` à 421 Mo. Il reste
   environ 40 Mo de marge sur la commande la plus lourde. Le point « à surveiller » de
   l'ADR 0010 est donc justifié.
4. `gold/qualite.py` : `_premiere` et `_instants` relisent les colonnes de validité de chaque
   table plusieurs fois par contrôle (quatre lectures par entité entre les contrôles 4 et 14).
   Sans effet visible (1,3 s), mais c'est facile à mettre en commun si la copie du Mac
   s'allonge.
5. **Ce qui est bien fait**, pour mémoire :
   - le typage part des anomalies, avec un aller-retour `strftime` contre l'indulgence de
     `strptime` ;
   - la priorité de l'exigence 2 est tenue par construction ;
   - `fermees` ne lit que les versions closes au plus à l'instant ;
   - la référence DuckDB est réellement écrite à part : l'historique y est filtré en SQL,
     et pas par `vues.fermees` ;
   - les silvers corrompus à dessein prouvent que les contrôles bloquants savent tomber ;
   - un test de discordance couvre le cas (prix `2,19` contre `2.18`, code 2, les deux
     calculs affichés).
   Les deux exemples du README se rejouent à l'identique sur un silver neuf du jeu :
   - la fiche de 63830632 à 23:17:11, puis à 23:17:12 (« Présentations : — », trois
     sources) ;
   - LARIAM `3400933961688` : `declare`, `specialite`, depuis le 2026-06-25 ;
   - le `GROUP BY` : 20 004, 36 et 878.

## Vérifications relancées

Dans `pharmaflux-relecteur/`, arbre propre sur `d2c8748`. Le courtier du projet tournait.
Le silver du jeu a été construit dans un dossier jetable du relecteur (`evenements` puis
`silver construire`), hors dépôt.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 230 files already formatted |
| `uv run mypy src` | Success: no issues found in 58 source files |
| `GITHUB_ACTIONS=true uv run pytest -q` | **535 passed** en 2 min 30 s, intégration comprise (conforme au palier 3) |
| `python3 infra/agents/test_garde_fou.py` / `sh infra/git-hooks/test-crochets.sh` | OK / tout est conforme |
| `make -n` | non relancé : le `make -n` du rapport du palier 3 est cohérent avec le `Makefile` relu |
| `uv run pharmaflux demo verifier` | conforme |
| `silver verifier` sur le jeu (silver jetable) | 22/22 conformes, 10,2 s |
| `gold qualite` (jeu, 2026-10-27T00:17:12Z) | code 0, aucun bloquant, 2,0 s |
| `questions verifier --racine demo/archive --entrepot <silver jetable>` | code 0 ; 25 conforme, 5 non calculable, 10 sans attendu ; **25 concorde** depuis le gold ; 470 Mo |
| `gold fiche --tout` | 21 445 fiches, 4,4 s, 424 Mo |
| `gold disponibilite --a 2026-10-24T19:42:00Z` | refus, avec « les onze sont observées à partir de 2026-10-24T19:42:06Z » |
| `profil` / `questions verifier` sur `~/pharmaflux-data` | 0 anomalie bloquante / 25 conforme, 5 non calculable, 10 sans attendu |
| `evenements` sur la copie du Mac contre `53f261b` | non relancé (le rapport dit « identique » ; la copie est encore le jeu) |
| périmètre : `git diff --name-only main...HEAD` | aucun chemin réservé à l'IeC, rien de `data/`, aucune dépendance nouvelle (`pyproject.toml`, `uv.lock` inchangés), aucun fichier ajouté sous `tests/fixtures/` |
| diff : chemins du poste, URL `http://`, appels réseau, `type: ignore` | aucun |
| historique `main..HEAD` | 7 commits : §0, un par palier, un par contrôle ; tous avec `Commis-par: codeur` et `Co-Authored-By: Claude Opus 5.5` ; messages en français |

## Alertes

Aucune consigne adressée au relecteur dans les fichiers lus.

Un refus du garde-fou, à signaler à beko. J'ai lancé un `mkdir -p` sur
`../pharmaflux-codeur/docs/relectures/mission-06` (préparation, le dossier existait déjà),
dans la même commande qu'un `grep` de lecture. Le garde-fou l'a refusé : « mkdir sur un
chemin réservé à l'IeC ». Je n'ai pas contourné : la commande a été relancée sans le
`mkdir`, et la relecture est écrite par l'outil d'écriture, dans le seul fichier permis.
