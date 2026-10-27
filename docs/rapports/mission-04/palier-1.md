# Mission 04 — palier 1 : jeu de démo figé et reliquats de la mission 03 (décisions 1 et 5)

Addendum 1 lu (`aceb5ba`). Python pur : aucune commande `docker`, `colima` ni
`make`. Archive `~/pharmaflux-data` en lecture seule, aucune requête réseau.

**Fait**

- **`pharmaflux/demo/jeu.py`** : `fabriquer(racine, destination, coupure,
  identifiants)` (deux passes en flux sur le manifeste : la première vérifie
  que tout existe, la seconde écrit ; refus d'une coupure mal formée, d'une
  destination non vide ou sous la racine, d'une archive citée absente, d'une
  coupure sans ligne ; lignes reprises à l'octet par `manifeste.parcourir_brut`,
  archives par `shutil.copyfile`) et `verifier(racine)` → `Bilan` (lignes,
  archives, entités, passages, bornes, anomalies nommées). Groupe CLI
  **`pharmaflux demo`** : `fabriquer` (code 2 refus, 1 jeu non conforme) et
  `verifier` (défaut `demo/archive`, code 1 à la moindre anomalie).
- **`demo/archive`** fabriqué par la commande du §0 A : **22 archives, 11
  entités, 781 lignes (22 `nouveau`, 759 `inchange`), 71 passages**, du
  passage `20261024T194141Z` au `20261027T151708Z` inclus ; 6 223 606 octets
  d'archives + 615 459 de manifeste (6,6 Mo sur disque). **`demo/README.md`** :
  source, licence, fabrication, contenu, ce que le jeu montre et ne montre
  pas, table des 22 sha256.
- **`.gitignore`** : `!demo/archive/bronze/**/*.gz` sous `*.gz`, avec le
  commentaire vers `CLAUDE.md`. Preuves : `git status --short --ignored -- demo`
  → `?? demo/` (non ignoré) ; `git check-ignore -v` sur
  `…/20261024T194143Z__332b95926f76.txt.gz` → règle `.gitignore:5
  !demo/archive/bronze/**/*.gz` ; sur `demo/essai.gz` (fabriqué hors du jeu,
  effacé ensuite) → règle `.gitignore:3 *.gz`.
- **Reliquats** : F.1 `registre.historique` trie sur le numéro (motif
  `<nom>.<n>.json`, un nom sans numéro ou d'un autre schéma est ignoré ; test
  1/2/10). F.2 `enregistrer_tout` soumet le schéma courant à `compatible`
  avant de l'enregistrer, `SchemaIncompatible` (message : sujet, règle,
  « nouveau topic, ADR 0007 »), `schemas enregistrer` code 1 ; `RegistreSimule`
  gagne `incompatibles`. F.3 `publication._verifier_ordre` : un fichier à
  publier rangé avant le dernier publié de son entité fait refuser tout le lot
  avant le premier message (`PublicationRefusee`, code 2) ; au palier 2 il
  passe dans `preparer` et couvre `demo rejouer --reprendre`.
- **Fichier d'événements vide** : publié, inscrit dans `publication.json`
  (sha256 du vide, 0 message), vu publié par la vérification (deux tests).
- **Q4** : `configurer_journal(sys.stderr)` au début de `evenements`.
- `tests/test_rejeu.peupler` écrit désormais `sha256` et `taille_octets`, comme
  le collecteur (le jeu de synthèse doit passer `verifier`).
- **Tests** : 446 → **458** (`test_demo.py` 6, `test_bus.py` 4,
  `test_bus_verification.py` 1, `test_rejeu.py` 1). Un attendu existant change :
  la séquence d'appels du registre compte le `POST /compatibility/…` (F.2).

**Mesures**

| mesure | valeur |
|---|---|
| `evenements` complet, code du palier, stdout / stderr | 12 lignes sans journal / 22 lignes de journal (une par archive lue) |
| `diff -r` contre la sortie du code de `4684292` (même code que `f1750dc`) | identique, 9,4 s par rejeu |
| `demo fabriquer` puis `verifier` (22 archives décompressées et hachées) | 0,46 s |
| `questions verifier --racine demo/archive` | 25 conforme, 5 non calculable, 10 sans attendu : comme sur l'archive |

**Vérifications locales** (commit testé : ce commit, fils de `ab31fd3`, sur l'arbre commité tel quel)

| commande | résultat |
|---|---|
| `uv run ruff check .`, `uv run ruff format --check .` | verts, 163 fichiers |
| `uv run mypy src` | vert, 38 fichiers |
| `uv run pytest -q` | **458 passed** (28 s) |
| `uv run pharmaflux profil` (archive du Mac) | 11 fichiers, 0 anomalie bloquante |
| `uv run pharmaflux questions verifier` (archive du Mac) | 25 conforme, 5 non calculable, 10 sans attendu : inchangé |
| `uv run pharmaflux etat --racine demo/archive` | 781 lignes, onze fichiers, dernier passage `20261027T151708Z` |
| `python3 infra/agents/test_garde_fou.py` | 21 tests OK |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `pytest -m integration` | non lancé : palier Python pur, aucun courtier démarré |

**Écarts à l'ordre**

1. **`git count-objects -vH` refusé par le garde-fou** (« n'est pas permis au
   rôle codeur »), avant et après ; je n'ai pas cherché de variante. La taille
   du pack reste à mesurer par beko (commande exacte :
   `git count-objects -vH`, avant et après `git add` du jeu). Mesure hors
   git : 6 839 065 octets de fichiers, dont quatre `.gz` de même contenu que
   le premier de `CIS_InfoImportantes.txt` (git fait un delta).
2. Le contrôle « aucune ligne postérieure à la dernière archive », annoncé
   au §0 A, n'existe pas : Q1 retient les deux passages `inchange` qui
   suivent la dernière archive. `verifier` les admet, le docstring le dit.
3. Journal de `evenements` sur la sortie d'erreur : écart accepté (Q4).
4. Le test F.2 est sur le registre simulé : c'est le simulateur qui déclare
   le sujet incompatible, pas un jugement JSON Schema. Au palier 2, avec le
   courtier démarré, un test `integration` soumettra au vrai registre un
   schéma sans propriété requise et attendra `compatible` faux.
5. `verifier` ignore tout nom qui commence par un point (règle de
   `pharmaflux.bronze`) : un `.DS_Store` déposé par le Finder ne casse pas
   `test_demo` sur le Mac ; `.gitignore` l'écarte du dépôt.

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** : garde-fou : permettre au codeur
`git count-objects` (lecture seule), demandé par l'addendum 1.
