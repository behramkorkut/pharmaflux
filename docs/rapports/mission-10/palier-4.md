# Mission 10 — palier 4 : des lots bornés dans `index mettre-a-jour`

## Synthèse

**Fait** (addendum 3) : `index mettre-a-jour` encode d'abord, rend le modèle, puis écrit par
requêtes bornées. Sa mémoire ne dépend plus de la taille d'un lot de la BDPM.
- Chaque lot laisse une ligne d'avancée sur la sortie d'erreur.
- Le calcul ne change pas.
- Aucune unité ni aucun fichier que root lit ne change.

**Vérifications locales** (arbre propre sur les fichiers du commit, sans service) : vertes.
- ruff, `format --check` et mypy (101 fichiers) passent.
- `uv run pytest -q` : 1047 tests passent et 14 d'intégration sautent. Les 8 tests neufs passent
  à part, dont celui du vrai modèle.

**Pas encore vérifié** :
- **La CI de la PR**, au commit poussé. Je citerai son verdict, en particulier l'étape « Le vrai
  modèle », qui lance le test neuf marqué `modele`.
- **Le VPS.** Un résident mesuré sur le Mac ne valide aucun plafond (addendum 1). La preuve est le
  prochain lot d'au moins 1 000 CIS, sur le VPS.

**Écarts** : un, sur le jeu de démo avec le vrai modèle (plus bas).

**Dans le même commit**, les deux corrections de l'IeC à `incident-index-20-11.md` :
- l'heure de ma lecture, 13:27 UTC, prise sur l'horodatage des fichiers lus ;
- la synthèse, alignée sur la section 2 : la mort survient dans la boucle d'un lot, entre
  l'encodage et l'écriture, sans qu'on sache à quel moment.

## Ce qui change

**`src/pharmaflux/index/construction.py`, `mettre_a_jour`**

1. **`vise` d'abord**, comme avant.
2. **L'encodage d'abord** (`_encoder_d_abord`).
   - Les fragments des CIS touchés sont lus en flux. Les textes absents du cache sont encodés par
     `LOT_TEXTES` (256) et gardés au cache après chaque lot. C'est ce que fait `remplir_cache`
     pour `construire`.
   - Un fragment inchangé a déjà son vecteur au cache, puisque `index verifier` l'exige : seuls les
     textes ajoutés ou changés s'encodent.
3. **`encodeur.liberer()`** : la session du modèle est rendue avant toute écriture.
4. **L'écriture**, par lots de `LOT_CIS` (256) CIS lus. Les points existants de ces CIS sont lus,
   puis comparés en JSON canonique, comme avant.
   - Les points à écrire partent par requêtes de `LOT_POINTS` (256) points au plus.
   - Les points à retirer partent de même, **après** les écritures du lot : un CIS n'est jamais
     vide.
   - Les vecteurs ne viennent que du cache (`_du_cache`). Un texte absent est un refus, code 2,
     et non un encodage : le modèle ne se recharge jamais pendant l'écriture.
5. **L'instant à la fin**, comme avant.
6. **Une ligne par lot** sur la sortie d'erreur, à l'encodage comme à l'écriture :
   `mise à jour, encodage : CIS 1840/5200 ; 512 encodé(s), 0 écrit(s), 0 retiré(s) ; résident
   371 Mio`.
   - Le résident est le résident **courant** : `/proc/self/statm` sous Linux ; ailleurs, le
     maximum.
   - La chaîne garde les 12 dernières lignes de l'étape : la dernière ligne d'une tentative tuée
     dit où elle est morte.

Ce qui reste en mémoire :
- un lot de 256 textes à l'encodage ;
- les fragments et les charges existantes de 256 CIS à l'écriture ;
- une requête de 256 points au plus ;
- les seuls codes des CIS touchés ou vus.

**Une tentative tuée perd au plus un lot d'encodage** : 256 textes, soit environ 47 s à
5,4 fragments/s.

**`src/pharmaflux/cli.py`** : `index mettre-a-jour` passe ces lignes à la sortie d'erreur. Le
résumé final (sortie standard) et la ligne « résident maximal » ne changent pas.

**Ce qui ne change pas** :
- les fragments et le sous-processus qui les calcule ;
- les identifiants, les charges et le format de l'index ;
- le témoin des formats, `construire`, `verifier` et les unités.

## Les tests

`tests/test_index_maj_bornes.py`, neuf.
- Les bornes sont réduites par le test (2 CIS, 4 textes, 3 points), sous le lot de test : 5 CIS
  touchés, des dizaines de fragments.
- Qdrant est simulé, sans réseau.

| ce que demande l'addendum 3 | test |
|---|---|
| aucun appel à l'encodeur après la première écriture ; le modèle rendu avant | `test_l_encodeur_n_est_plus_appele_apres_la_premiere_ecriture` |
| des appels et des requêtes bornés (encodage, écriture, retrait), sur un lot plus grand que les bornes | `test_les_appels_et_les_requetes_sont_bornes` |
| la reprise après une coupure avant **chaque** requête d'écriture, puis de retrait, jusqu'à l'index de la reconstruction | `test_une_coupure_a_chaque_lot_puis_la_reprise_egale_la_reconstruction` (2 cas, chacun boucle sur toutes les requêtes) |
| une mort pendant l'encodage ne perd qu'un lot : ce qui était encodé est au cache | `test_une_mort_pendant_l_encodage_ne_perd_qu_un_lot` (2 cas) |
| une ligne d'avancée par lot, la dernière avec tous les CIS | `test_une_ligne_d_avancee_par_lot` |
| le vrai modèle en lots bornés : conforme, cosinus compris | `test_le_vrai_modele_en_lots_bornes_est_conforme_cosinus_compris` (`modele`) |

Le test du vrai modèle procède en quatre temps :
- il construit l'index d'avant avec e5, puis le met à jour en lots bornés ;
- `index verifier` le dit conforme : vecteurs égaux au cache, échantillon réencodé au cosinus de
  0,99 au moins ;
- il le compare à une reconstruction complète : mêmes identifiants et mêmes charges, chaque
  vecteur au cosinus de 0,99 au moins ;
- il est sauté sans les fichiers du modèle, et `PHARMAFLUX_MODELE_EXIGE` en fait un échec dans
  la CI.

**Le jeu de démo** (`tests/test_index_tranches.py`, inchangé sur le fond) :
- le jeu est publié en quatre tranches : `construire`, puis trois `mettre-a-jour` ;
- `index verifier` est conforme à chaque tranche ;
- l'index final est égal à sa reconstruction complète : 72 296 points, mêmes charges et mêmes
  vecteurs (encodeur de test).

Un seul changement dans ce test : `invoquer` rend la sortie standard seule. Les lignes d'avancée
vont sur la sortie d'erreur, et la règle « la première ligne dit le résultat » reste vraie.

## L'écart : le vrai modèle sur tout le jeu de démo

L'addendum 3 demande, sur le jeu de démo, « le même index final qu'avant le palier, et
`index verifier` conforme, cosinus de l'échantillon compris ». Je le couvre en deux tests :
- **le jeu entier, avec l'encodeur de test** : même index final que la reconstruction complète,
  qui était aussi celui d'avant le palier. `index verifier` est conforme ;
- **le vrai modèle, sur les fiches du test de mise à jour** : conforme, cosinus compris.

Le vrai modèle n'est pas lancé en `mettre-a-jour` sur les 72 296 fragments du jeu.
- Il faudrait encoder tout le jeu dans la CI : la construction avait pris 24 minutes.
- L'étape de la CI construit un index réduit, et une mise à jour refuse un index réduit.

**Si tu le veux sur le jeu entier**, une étape de CI : `construire` sur le jeu à une tranche
antérieure, `mettre-a-jour` à la dernière, puis `verifier`, avec le vrai modèle. Cela fait
environ 25 minutes de CI de plus. Je ne l'ai pas ajoutée sans ta décision.

## Les vérifications locales

| commande | résultat |
|---|---|
| `uv run ruff check .`, `ruff format --check .` | vertes |
| `uv run mypy src` | 101 fichiers, aucune erreur |
| `uv run pytest -q` | 1047 passés, 14 sautés (intégration, sans service), 6 min |
| `uv run pytest tests/test_index_maj_bornes.py -q` | 8 passés, dont le test `modele` : les fichiers du modèle sont sur le Mac, et le test a chargé e5 quelques secondes |
| `tests/conftest.py::reseau_coupe` | garde de session inchangée |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK |
| `make -n index` | inchangé : `mettre-a-jour` ou `construire`, puis `verifier` |
| `shellcheck`, YAML de la CI, `docker compose config` | sans objet : rien de touché |

Aucun résident mesuré ici ne vaut pour le VPS. Les 907 Mio d'un test sur le Mac sont ceux du
processus de `pytest` entier.

## Le dépôt, après ton contrôle, le push de beko et la CI verte

1. **Le code** (étape 4a de `infra/vps/README.md`), par `pharmaflux-vps`, hors de la minute
   `:17` :
   - `git archive --prefix=versions/<commit>/ <commit> | ssh pharmaflux-vps 'tar -x -C /srv/pharmaflux/code'` ;
   - `uv sync --directory /srv/pharmaflux/code/versions/<commit> --frozen --no-dev --no-editable --compile-bytecode`,
     avec `UV_PYTHON_INSTALL_DIR=/srv/pharmaflux/code/python` et `UV_LINK_MODE=copy` ;
   - la bascule sous le verrou : `ln -sfn` vers `courante.neuf`, puis
     `flock -n …/chaine/verrou mv -T`. Si le verrou est tenu, `flock` sort en 1 sans rien
     basculer, et je relance plus tard ;
   - les droits : les deux `find`, rien attendu. La version : `pharmaflux --version`, `VERSION`,
     `readlink -f` du Python.
2. **La condition du témoin des formats** : `git diff --stat f35d797 <commit> -- src` ne doit
   toucher que `index/construction.py` et `cli.py`, sans rien du format.
3. **La vérification d'après le dépôt**, lancée par beko, puisque la liste polkit reste vide :
   `sudo systemctl start pharmaflux-verification.service`. Puis
   `systemctl show pharmaflux-verification.service -p Result -p ExecMainStatus`, à coller à
   l'IeC. La seconde observation part de là.
4. **`f35d797` reste sur le disque** : revenir en arrière, c'est rebasculer le lien, sur
   décision de l'IeC. `eecc9f3` se retire par son chemin exact, pour garder deux versions.

## Ce qui reste

1. Ton contrôle de ce palier.
2. Le push de beko, la CI verte, et le verdict de l'étape du vrai modèle, que je cite.
3. Le dépôt, puis la vérification par beko.
4. **La seconde observation** :
   - 48 heures sans intervention ;
   - un lot d'au moins 1 000 CIS passé en un seul passage, sans étape tuée, avec un résident
     de l'étape `index` sous 450 Mio, et ses lignes d'avancée dans le journal ;
   - trois passages porteurs sur la nouvelle version ;
   - sans lot de cette taille dans les 14 jours, tu décides sur pièces.
5. Les relevés de beko du 25/11 : si la ligne « Killed process » contredit l'analyse, je
   reprends ce palier.
6. Le commit de l'observation : les retouches 1 à 5 du palier 3, l'incident, les chiffres des
   deux observations, et les contrôles des paliers 3 et 4 tels quels.
