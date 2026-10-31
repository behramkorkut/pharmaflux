# Mission 08 — relecture 1
**Commit relu** : `98cdb69` (sommet de `mission-08-assistant-gouverne`)
**Verdict** : CONFORME

Relecture à contexte neuf (Claude Fable 5.1), le 31/10/2026, contre l'ordre
de mission et ses addenda 1 et 2 lus sur `main`, les rapports du codeur
(`points-a-trancher.md`, `palier-1.md` à `palier-3.md`, `pr.md`) et les trois
contrôles de l'IeC. Tout le code livré a été lu (`index/lexical.py`, le diff
de `index/`, les neuf modules de `assistant/`, le diff de `cli.py`, de
`evaluation/questions.py`, du `Makefile` et de `pyproject.toml`), ainsi que les
tests nouveaux (`test_assistant.py`, `test_notation.py`, `test_lexical.py`,
`test_makefile.py`, les diffs de `test_index*.py`, `test_questions.py`,
`qdrant_simule.py`), l'ADR 0012, le jeu v1, le README, `evaluation/README.md`,
`docs/CONTEXTE.md` et le journal.

**Ce qui est tenu, point par point.** Chaque décision de l'ordre et des addenda
se retrouve dans le code et dans un test : le tokenizer figé sur dix cas, les
constantes BM25 et la longueur moyenne figées, l'indice `blake2b` sur 31 bits,
l'IDF à Qdrant, le format 2 en collection neuve, `verifier` qui compare le
vecteur creux en `float32`, `index evaluer` en trois modes ; le chemin dans
l'ordre de l'addendum B (refus, abstentions dures, deux médicaments, recherche,
porte structurelle, LLM, contrôle), le repérage par CIS, CIP13 et premier mot ;
le schéma de sortie avec `reserve`, dix fragments, `max_tokens` 4 000, pas de
repli, `refusal` et `max_tokens` en abstention technique journalisée et hors
cache, les sources et l'instant rendus par le code ; la grille datée, le plafond
constante, la porte par estimation locale avant le premier appel de toute
l'évaluation, le journal et le cache sous `data/assistant` épargnés par
`make rebatir` ; la notation déterministe aux cinq conditions, les deux
conditions dures seules à donner le code 1 ; les deux tests D2 sur la v1
entière ; la v1 datée à l'instant de l'index, vérifiée depuis le bronze et le
gold ; la clé jamais lue par le code hors `ANTHROPIC_API_KEY` ; l'évaluation
complète lancée par beko, citée en entier, sous 20 $. Les écarts (RRF côté
client, 88 questions, `depense` en abstention, cinq questions passées en
abstention, correctif « deux médicaments », étiquettes de citation,
`disponibilite-005`) sont tous déclarés dans un rapport et tranchés par
l'IeC. Les quatre points « à faire » des contrôles sont faits.

## Bloquants

Aucun.

## À corriger (non bloquants)

1. `tests/test_assistant.py:464` — le test « clé absente » (addendum 1 J)
   retire les variables `ANTHROPIC_*` mais **ne bloque pas le réseau** et ne
   pose pas de dossier de profil vide, comme l'addendum le demande ; cet écart
   n'est déclaré nulle part. Le comportement est bien garanti par le code
   (`cle_presente` ne lit que l'environnement et répond avant tout import),
   et le test voisin `test_cli_evaluer_estimer_sans_cle`
   (`tests/test_notation.py:465`) bloque, lui, `socket.socket.connect`.
   Attendu : la même ligne de blocage dans le test de `demander`, et une
   phrase dans le rapport disant que le profil n'est pas lu par le code.
2. `src/pharmaflux/assistant/regles.py:23` — le cadre d'une demande de
   décision ne connaît que « puis-je », « dois-je », « faut-il ». Vérifié
   ici : « Peut-on associer DOLIPRANE 1000 mg et EFFERALGAN 1000 mg ? »,
   « Est-ce que je peux prendre DOLIPRANE 1000 mg avec de l'alcool ? »,
   « Je peux remplacer LARIAM par un autre antipaludique ? » et **« Mon fils
   de 6 ans peut-il prendre le générique de DOLIPRANE ? »**, l'exemple même
   du §0 D de l'ordre, passent les règles et vont au LLM. Le filet existe (le
   LLM est consigné de refuser, un refus du LLM prend la forme du code, et la
   condition dure compte toute `medical` sans refus), mais l'ordre veut la
   décision « d'abord hors du LLM … quand c'est possible », et c'est possible
   ici : ces formes ont la structure de « puis-je ». Attendu : élargir le
   cadre (« peut on », « peut il », « peut elle », « je peux », « on peut »,
   « est il possible de »), des tests dans les deux sens, et les deux tests
   D2 sur la v1 toujours verts (aucun faux refus).
3. `src/pharmaflux/assistant/controle.py:59` — **« 1er juillet 2027 » n'est
   pas lu comme une date** : « 1er » n'entre pas dans `_EN_LETTRES`,
   « juillet 2027 » devient un mois seul, et le « 1 » restant est un nombre
   sans appui. Vérifié : `controler("Arrêt annoncé à partir du 1er juillet
   2027.", ["… 2027-07-01 …"], "q")` rend « le nombre « 1 » du texte n'est
   dans aucun fragment cité ». Une réponse juste deviendrait donc une
   abstention « non vérifiable ». Aucune des 124 réponses réelles des deux
   détails JSON Lines n'a écrit « 1er », mais la forme est la plus courante en
   français pour le premier du mois (les attendus `01/07/2027` de
   `disponibilite-012` et `historique-005` s'y prêtent). Attendu : accepter
   l'ordinal (« 1er ») dans `_EN_LETTRES`, avec un test dans les deux sens.
4. `tests/test_index.py:157` — `assert fusion[0]["payload"] == {"t": "X"} or
   fusion[0]["id"] == "y"` **ne peut pas échouer** : la ligne précédente a
   déjà établi `fusion[0]["id"] == "y"`. Un test qui ne peut pas échouer est
   un défaut (consigne). Attendu : vérifier ce que `fusion_rrf` garde
   vraiment comme charge (celle de `x`, `{"t": "X"}`, en `fusion[1]` ; pour
   `y`, celle de la dernière voie), ou retirer l'assertion.
5. `src/pharmaflux/assistant/budget.py:38` — le commentaire dit que
   l'estimation d'entrée « majore plutôt qu'elle ne minore ». Le journal réel
   dit le contraire. Sur les 62 appels de l'évaluation : 223 934 jetons
   d'entrée réels (entrée, cache lu et cache écrit), soit 3 612 par appel,
   contre 1 768 estimés (0,4385 $ d'entrée dans les 5,3985 $, à 4 $ par
   million). **L'entrée est sous-estimée d'un facteur 2** sur ce contenu, fait
   de codes, de dates et de nombres. La porte reste prudente par
   `max_tokens` entier (0,0871 $ estimé contre 0,0159 $ réel par appel) :
   l'addendum G2 est tenu. Attendu : corriger le commentaire, et le dire dans
   l'ADR 0012 (« l'entrée est minorée, la sortie la couvre »), ou abaisser
   `CARACTERES_PAR_JETON` vers 1,9 pour ce contenu.
6. `tests/test_assistant.py:503` — l'addendum D2 est tenu pour le refus
   (aucun faux refus sur la v1), mais rien d'équivalent n'existe pour les
   abstentions dures : aucun test ne vérifie qu'**aucune réponse attendue de
   la v1 n'est abstenue par `regles.abstention`**. Vérifié ici : 0 faux
   positif, et 14 abstentions décidées (`depense-001` à `-010`,
   `hors_perimetre-001`, `-005`, `-006`, `-007`), ce que la sortie de
   l'évaluation confirme. Attendu : le test miroir, deux lignes.

## Remarques

- `src/pharmaflux/assistant/notation.py:162` et `chemin.py:395` : la
  condition dure « aucune citation invalide » est tenue **par
  construction**. Une étiquette hors des fournis devient une abstention dans
  le chemin avant la notation, et chaque `Citation` est bâtie depuis les
  résultats fournis. L'indicateur mesure donc un invariant du code, pas ce
  que le modèle a tenté. Ce dernier serait mieux rendu par un compte à part
  des abstentions « une citation sort des fragments fournis » (décision
  `controle`), aujourd'hui confondues avec les « non vérifiable ». À noter
  dans l'ADR, ou à compter à la mission 09.
- `src/pharmaflux/assistant/repere.py:198` : tout jeton de la question qui
  est le premier mot d'une dénomination « vise » ses CIS. Sur le dictionnaire
  réel du jeu de démo, « eau », « huile », « vitamine », « calcium »,
  « alcool », « glucose », « fer », « zinc », « magnesium » et « oxygene » en
  sont. « Quel est le prix public de DOLIPRANE 1000 mg avec un verre
  d'eau ? » vise 31 CIS (noms « doliprane » et « eau »). La porte
  structurelle passe dès qu'un fragment d'un CIS visé est rendu, et « deux
  médicaments » exige tous les mots du nom : la v1, la v0 et les 200 tirages
  ne montrent aucun faux positif. Mais une question qui ne cite que de
  l'« eau » incidemment s'abstiendrait au motif « aucun fragment du
  médicament visé ». À surveiller (mission 09).
- `src/pharmaflux/cli.py:2035` : l'aide de `index evaluer` dit encore « Une
  première mesure de la recherche sur le jeu v0, pour la mission 08 », alors
  que la commande prend `--questions` et rend dense, creux et hybride. À
  rafraîchir.
- `src/pharmaflux/cli.py:2519` : `notation.ColonneNonClassee` (une colonne
  nouvelle dans un attendu) sort en trace Python, pas en code 2 avec une
  ligne lisible (addendum H2, « erreur de configuration »). Sans effet
  aujourd'hui : un test garantit que toute colonne de la v1 est classée.
- `src/pharmaflux/cli.py:2259` et `:2333` : `_rendre_reponse`,
  `_reponse_json`, `_ligne_note`, `_rendre_estimation` et
  `_rendre_indicateurs` sont typées `Any` dans un projet `mypy --strict`.
  `chemin.Reponse`, `notation.Note`, `evaluation.Estimation` et
  `notation.Indicateurs` s'importent sous `TYPE_CHECKING` sans alourdir le
  démarrage de la ligne de commande.
- `src/pharmaflux/assistant/cache.py:39` : `assistant evaluer --estimer`
  crée `cache-reponses.sqlite` dans le dossier des données, alors qu'il
  n'écrit rien d'autre ; le test ne vérifie que l'absence du journal. Sans
  conséquence.
- `src/pharmaflux/assistant/chemin.py:110` : la docstring de
  `Reponse.decision` cite « cache » parmi les provenances, mais le cache est
  porté par `depuis_cache` et `decision` reste « llm » ou « controle ».
- Historique : plus d'un commit par palier (quatre au palier 2, cinq au
  palier 3), mais chacun est relié à un contrôle, à la démonstration ou à une
  condition de l'IeC, et tous sont expliqués dans les rapports ; aucune
  réécriture. Les sujets de commit sont écrits sans accents (« cloture »,
  « eprouve », « deterministe »), celui du §0 avec (« réponses ») : une
  graphie à fixer dans les consignes.
- Rapports : les chiffres annoncés se retrouvent tous (tests, `--estimer`,
  dépenses, attendus v1 et v0, `make -n`). Les 6 min 06 du `pytest` de
  `pr.md` sont 6 min 30 ici, pour le même compte.
- Lisibilité pour un recruteur : noms, commentaires et docs en français,
  identifiants sans accents, docstrings qui disent le pourquoi et renvoient à
  l'addendum ; pas de code mort trouvé. Les modules `controle.py`, `repere.py`
  et `notation.py` se lisent seuls. L'ADR 0012 et la section « L'assistant »
  du README, avec les deux sorties réelles et les deux chiffres (34/49 puis
  44/49) dits en clair, sont la meilleure vitrine de la mission.

## Vérifications relancées

Dans `pharmaflux-relecteur/`, arbre propre sur `98cdb69`, Qdrant et Redpanda
du projet `pharmaflux` présents, modèle e5-small-int8 en place. Aucun appel à
l'API : ma session n'a pas de clé, et aucune commande lancée n'en demande.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 290 files already formatted |
| `uv run mypy src` | Success: no issues found in 78 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **719 passed** en 6 min 30, aucun saut, session verte ; « 0 réessai(s) du registre sur 30 cycles » ; intégration et modèle compris (non relancés à part) |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK (21 tests) |
| `make -n evaluer` ; `make -n evaluer EVALUER_OPTIONS=--estimer` ; `make -n rebatir` | identiques au rapport du palier 3 ; `rebatir` n'efface que `data/demo` |
| `questions verifier` v1, `--racine demo/archive --entrepot ../pharmaflux-codeur/data/demo/lakehouse` | 88 : 50 conformes, 10 non calculables, 28 sans attendu ; 50 depuis le gold : 50 concordent |
| `questions verifier` v0, mêmes options | 40 : 25 conformes, 5 non calculables, 10 sans attendu ; 25 depuis le gold : 25 concordent |
| `questions verifier` v0 `--racine ~/pharmaflux-data` ; `profil --racine ~/pharmaflux-data` | 25 conformes, 5 non calculables, 10 sans attendu ; 11 fichiers profilés, 0 anomalie bloquante |
| `demo verifier` | conforme |
| `assistant depenses --donnees ../pharmaflux-codeur/data/assistant` | mission 8 : 65 appel(s), 1,0309 $ ; reste 18,9691 $ sur 20 $ (journal lu : 65 lignes, toutes mission 8, `claude-opus-5-5`, effort `low`, sortie maximale 661 jetons) |
| `assistant evaluer --estimer` sur le vrai index, journal et cache vides, sans clé | 88 questions, 26 hors LLM, 0 en cache, **62 appels, 5,3985 $** prudent, accordée ; 9,3 s, 457 Mo ; aucun journal écrit |
| `index verifier --entrepot ../pharmaflux-codeur/data/demo/lakehouse`, depuis ce dossier | 72 296 points pour 72 296 attendus ; 0 manquant, 0 orphelin, 0 texte, 0 vecteur, **0 vecteur creux différent** ; cosinus minimal 0,9964 ; 413 et 421 Mo, 44 s. **NON CONFORME** sur le seul poste « vecteurs absents du cache : 72 296 », parce que ce dossier n'a pas de `data/index/cache-vecteurs.sqlite` : le cache est chez le codeur et je n'ai pas pris son verrou. Artefact de mon environnement, pas de l'index ; la séquence de beko l'a donné conforme sur le même sommet. La commande a créé `data/index/` ici (hors git), à effacer. |
| `index modele verifier e5-small-int8` | 4 fichier(s) en place, sha256 vérifiés |
| `git diff --stat main...HEAD` sur `01_Specifications/`, `CLAUDE.md`, `.claude/`, `docs/agents/`, `docs/missions/`, `infra/git-hooks/`, `infra/agents/`, `.github/`, `*.sh` | vide ; `git ls-files data/` vide ; `uv.lock` : 149 lignes ajoutées, 0 retirée |
| `git log --format=%(trailers)` main..HEAD | 12 commits, tous `Commis-par: codeur` ; `Co-Authored-By` Claude Opus 5.5 pour le §0, le palier 1 et de `c4ddec8` à la fin, Claude Opus 4.8 de `1d2c20d` à `4f827cb`, comme l'addendum 2 ; messages en français |
| non relancés : `evenements` contre `85ec0ab`, `silver verifier`, `make gold`, `index construire` | le code du bronze, des événements, du silver et du gold n'est pas touché par la branche ; `make <cible>` est à beko ; les contrôles de l'IeC et la séquence de beko du 30/10 les donnent verts |

## Alertes

Aucune. Rapports, code, tests, ADR, jeu v1 et README relus ; aucune consigne
adressée au relecteur n'y figure (recherche de « relecteur », « déclare
conforme », « ignore la règle »).
