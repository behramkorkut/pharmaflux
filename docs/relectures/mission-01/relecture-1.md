# Mission 01 — relecture 1
**Commit relu** : `7c5d10e` (sommet de `mission-01-profilage-et-contrats`)
**Verdict** : CONFORME

Relu contre l'ordre de mission sur `main` (`f412b97`), addendum 1 compris,
les cinq rapports du codeur et les quatre contrôles de palier de l'IeC.
Premier tour : pas de réponse antérieure à vérifier.

## Bloquants

Aucun.

Les douze décisions de l'ordre sont tenues. Chaque écart est annoncé dans
un rapport et a été accepté par l'IeC dans le contrôle du palier
correspondant : `UMask=0027`, `lien_change`, ligne vide, contrôle UTF-8,
énumérations, plages de dates, liens de mesure, ordre des dates, nom des
profils, table `attendu` omise, `valeurs = []`, `prudence`. J'ai recalculé
moi-même ce qui pouvait l'être (voir les vérifications ci-dessous) : les
chiffres annoncés sont exacts.

## À corriger (non bloquants)

1. `src/pharmaflux/contrats/profil.py:177` et `:201` — **le minimum et le
   maximum d'une colonne numérique prennent des valeurs non conformes, et
   `NaN` fait planter le profil.** `_lire_nombre` passe par `Decimal()`,
   qui accepte `NaN`, `Infinity` et `1e9`. Ces valeurs sont refusées par
   `verifier_valeur` (`decimal_illisible`), mais elles entrent quand même
   dans les bornes. Je l'ai reproduit sur `bdpm.presentations` et sa
   colonne `prix_medicament` :
   - `_bornes` sur `{"12,50", "1e9"}` donne le maximum `1e9` ;
   - `_bornes` sur `{"12,50", "NaN"}` lève `decimal.InvalidOperation`,
     parce que le tri compare un `NaN`.

   Pourquoi c'est à corriger : le profil doit être l'alerte de changement
   de format du Lot 5 (décision 4, risque n° 1 du PRD §9). Une valeur
   inattendue doit y apparaître comme une anomalie comptée, pas sous la
   forme d'une trace Python et d'un profil absent. Une colonne `entier`
   qui recevrait `1,5` a le même défaut, en moins grave.

   Attendu : ne lire que les valeurs qui passent `verifier_valeur`
   (`decimal_illisible` et `entier_illisible` exclus), comme `_lire_date`
   le fait déjà pour les dates avec le motif du format. Ajouter un test
   avec `NaN` et `1e9` dans une colonne décimale.

2. `src/pharmaflux/contrats/verification.py:192` — **le type `decimal`
   accepte des chiffres non ASCII.** `decimales.isdigit()` est vrai pour
   `²³` : `verifier_valeur(decimal à 2 décimales, "1,²³")` rend `None`.
   `_entier` vérifie bien `isascii()`, la partie décimale non. Le contrat
   doit être le même des deux côtés de la virgule. Attendu : ajouter
   `decimales.isascii()` et le cas dans `test_verifier_valeur`.

3. `src/pharmaflux/evaluation/questions.py:214` et
   `src/pharmaflux/evaluation/verification.py:91` — **rien ne lie
   l'archive d'un attendu au contrat qu'il nomme.** Le chargeur exige
   seulement `bronze/…*.gz`, avec la date du jour de référence. Ensuite,
   `verifier_jeu` garde une seule lecture par archive, avec le contrat de
   la première question qui la cite. Si deux questions citent la même
   archive avec deux `fichier` différents, la seconde est projetée sur les
   colonnes du premier contrat. Le résultat est soit un `ValueError` de
   `noms.index`, soit, quand les noms de colonnes coïncident (`code_cis`,
   `code_dossier_has` entre SMR et ASMR), une comparaison silencieusement
   fausse. Une seule question qui cite l'archive d'un autre fichier donne
   un « archive non conforme » trompeur. Le jeu v0 est cohérent : je l'ai
   vérifié, sept couples (fichier, archive), chacun dans le bon dossier.
   Mais le chargeur est strict partout ailleurs, et c'est lui qui gardera
   les v1 et suivantes. Attendu : exiger que `archive` commence par
   `bronze/<source>/<contrat.fichier>/`, ce qui exclut aussi un `..` dans
   le chemin, ou bien indexer le cache par (archive, fichier). Ajouter un
   cas refusé dans `test_jeu_mal_forme_refuse`.

4. `tests/test_contrats_verification.py:293-312` — **le test
   `test_regles_bloquantes_sont_les_quatre_de_l_addendum` est illisible.**
   Il reconstruit `REGLES_BLOQUANTES` par une compréhension et un
   `__import__` au lieu de l'importer. Le second `assert`, sur la `raison`
   des clés uniques, n'a rien à voir avec le nom du test. Il en va de même
   pour les trois `__import__("re")` des lignes 259 à 266. Un recruteur
   lira ce fichier. Attendu : `from pharmaflux.contrats.modele import
   REGLES_BLOQUANTES` et `import re` en tête, `assert REGLES_BLOQUANTES ==
   {…}`, et le second `assert` dans un test à son nom.

## Remarques

- `src/pharmaflux/cli.py:37` — `QUESTIONS_PAR_DEFAUT` est relatif au
  dossier courant. Lancé hors de la racine du dépôt, `questions verifier`
  échoue avec « illisible ». C'est conforme à l'ordre, puisque le jeu est
  à la racine et hors du paquet, comme voulu. Une ligne dans l'aide de
  `--questions` ou dans `evaluation/README.md` éviterait la surprise lors
  de la vérification de clôture sur une copie rapatriée.
- `src/pharmaflux/contrats/verification.py:148` — une ligne faite
  seulement de séparateurs (`\t\t…`, toutes les valeurs vides) est traitée
  comme une ligne vide, parce que `strip()` enlève aussi les tabulations.
  Elle n'est donc pas lue comme une ligne de valeurs manquantes. C'est
  sans effet sur l'archive du 24/10. Si c'est voulu, il suffit de le dire
  dans l'ADR 0002.
- `_decoder` ne signale que le premier octet illisible, puis continue par
  substitution. C'est suffisant tant que l'encodage reste bloquant, mais le
  profil ne dit pas combien de lignes sont touchées.
- `profiler_racine` vérifie deux fois une archive qui est à la fois
  profilée et cible d'un lien. C'est sans conséquence (2 s pour les onze
  fichiers), à garder en tête quand Open Medic arrivera.
- `docs/rapports/mission-01/points-a-trancher.md` cite un script du
  dossier temporaire de session (`…/scratchpad/m01/outils/profil_brut.py`)
  qui n'existe plus pour personne. Les chiffres du §0 sont aujourd'hui
  refaits par `pharmaflux profil`, ce que l'addendum H.9 demandait. Une
  phrase qui le dit au même endroit fermerait la boucle pour un lecteur
  extérieur.
- Historique : un commit par palier, plus le correctif C1 (`ee50cdc`) à
  part comme demandé, et les contrôles de l'IeC committés tels quels. Les
  deux trailers sont présents sur chaque commit du codeur, et les messages
  sont en français. Le commit de fusion `695cdfc` (`main` vers la branche)
  est de beko, sans trailers, ce qui est normal.
- Garde-fou, refus signalé et non contourné : pendant cette relecture,
  `for f in docs/relectures/mission-01/*.md; do cat $f; done` a été refusé
  (« « for » sur un chemin réservé à l'IeC »). Les mêmes fichiers ont été
  lus avec un seul `cat` sur les quatre chemins, une forme permise. Pour
  beko et l'IeC : le relecteur lit `docs/relectures/` à chaque tour, et une
  boucle de lecture y est refusée. Le comportement est sûr, juste un peu
  rugueux.

## Vérifications relancées

Au commit `7c5d10e`, arbre propre, dans `pharmaflux-relecteur/` :

| commande | résultat |
|---|---|
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 93 files already formatted |
| `uv run mypy src` | Success: no issues found in 22 source files |
| `uv run pytest -q` | 229 passed (identique au palier 4) |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 16 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` | rien, code 0 |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` | 11 fichiers, 0 bloquante, code 0 |
| `uv run pharmaflux profil --racine ~/pharmaflux-data --markdown <jetable>` puis `diff -r` avec `docs/donnees/` | identiques, à la ligne « Produit le » près (ligne 7 de chaque profil) |
| `uv run pharmaflux questions verifier --racine ~/pharmaflux-data` | 40 questions : 25 conformes, 5 non calculables, 10 sans attendu, code 0 |
| `git diff --name-only main...HEAD` contre les chemins réservés et `data/` | aucun fichier réservé, rien de `data/`, pas de `.env`, `pyproject.toml` et `uv.lock` inchangés |
| tests et réseau | seul `httpx.MockTransport` (`tests/conftest.py`), aucune lecture de l'archive |
| essai jetable de `_bornes` et `verifier_valeur` (points 1 et 2) | défauts reproduits |
| systemd | non mesurable sur le Mac ; score 1,3 mesuré par beko (contrôle du palier 1) |

L'archive du Mac n'a été que lue. Aucune requête réseau pendant cette
relecture.

## Alertes

Aucune. Je n'ai trouvé dans le code, les rapports, les fixtures ni le jeu
de questions aucune consigne adressée à un agent.
