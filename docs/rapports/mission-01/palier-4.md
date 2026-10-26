# Mission 01 — palier 4 : questions de référence (décisions 7, 8, 12)

**Fait**

- **Décision 7**, `evaluation/questions-reference-v0.toml` : quarante
  questions, cinq par catégorie de l'annexe B (identifiants `categorie-NNN`,
  stables). Chacune a son comportement attendu (`reponse`, `abstention`,
  `refus_medical`) ; une réponse porte la date de référence, le contrat,
  l'archive du 24/10 (chemin relatif et sha256), la clé, les colonnes lues
  et les lignes attendues, **brutes** (`65%`, `30 %`, `1,16`). Addendum F :
  deux questions visent un CIS absent de `CIS_bdpm.txt` (abstention
  motivée, vérifiée par un attendu sans ligne dans les spécialités) ; les
  questions Historique s'appuient sur les dates des fichiers, évitent les
  dates impossibles, et **une seule** porte un début postérieur à la mise à
  jour, voulue (`historique-005`, arrêt annoncé pour le 01/07/2027, champ
  `prudence`). Dépense : `calculable_au = "lot4"`, pas d'attendu.
  Médicaments réels de l'archive, aucun patient. `evaluation/README.md`
  décrit le format, le rejeu et la règle de version.
- **Décision 8**, `uv run pharmaflux questions verifier [--racine …]
  [--questions …]` (`evaluation/questions.py`, `evaluation/verification.py`,
  `cli.py`) : lecture stricte du jeu (toute clé inconnue ou incohérente est
  refusée, fichiers et colonnes contrôlés contre les contrats), puis, par
  attendu : archive relue sous la racine, sha256 comparé, fichier vérifié
  contre son contrat (une bloquante arrête là), lignes de la clé projetées
  sur les colonnes et comparées dans l'ordre du fichier. Sept verdicts, code
  de sortie 1 au moindre échec. **Sur la copie du Mac : 25 conformes, 5 non
  calculables, 10 sans attendu, code 0.** Testé sur fixtures avec le jeu
  dédié `tests/fixtures/evaluation/questions-essai.toml` (huit questions, un
  cas par verdict, plus les échecs provoqués : écart de valeur, de nombre
  de lignes, sha256 différent, archive introuvable, archive non conforme).
- **Décision 12** : `docs/CONTEXTE.md` (contrats, lecture du bronze, « on
  constate, on ne corrige pas », jeu de questions), `README.md` (état,
  commandes `profil` et `questions verifier`), `docs/journal.md`.
- **Contrôle du palier 3** : commentaire de `specialites.toml` précisé
  (1 263 contre l'archive CIS_CIP de 23:17 UTC, 1 261 contre celle de
  19:41 UTC), version inchangée.
- La table TOML stricte des contrats est sortie dans `tomlstrict.py`,
  partagée avec le jeu de questions (`chargeur.py` ne change pas de
  comportement).

**Vérifications locales** (commit testé : celui de ce palier, arbre propre)

| commande | résultat |
|---|---|
| `uv run ruff check .` et `ruff format --check .` | ok |
| `uv run mypy src` | ok, 22 fichiers |
| `uv run pytest -q` | **229 passed** (198 + 31 pour les questions) |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | 16 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` | rien à signaler |
| `uv run pharmaflux questions verifier --racine ~/pharmaflux-data` | 40 questions : 25 conformes, 5 non calculables, 10 sans attendu, code 0 |
| `uv run pharmaflux profil --racine ~/pharmaflux-data --markdown <jetable>` | 11 fichiers, 0 bloquante, code 0 (inchangé) |
| `uv build --wheel` | `evaluation/` du paquet et `tomlstrict.py` dans la roue ; le jeu TOML reste à la racine du dépôt, hors paquet (voulu) |

**Garde-fou** : aucun refus pendant ce palier. Archive du Mac lue seulement ;
aucune requête réseau.

**Écarts à l'ordre**

1. L'ordre cite « `attendu` vide » pour Dépense ; le jeu **omet** la table
   `attendu` et porte `calculable_au = "lot4"`, comme l'addendum F le dit
   (« `attendu` absent »). Le chargeur refuse une réponse qui aurait les
   deux ou aucun.
2. Un attendu peut valoir **« aucune ligne »** (`valeurs = []`) pour une
   réponse (« aucun signalement », « aucun générique ») comme pour une
   abstention (CIS absent du référentiel) : c'est ce qui rend ces réponses
   rejouables plutôt que déclaratives. Non prévu par l'ordre, proposé tel
   quel.
3. Champ `prudence` (texte libre, facultatif) sur une réponse : la nuance
   que l'assistant devra porter (arrêt annoncé, trois SMR par indication,
   remboursement conditionné). Il n'est pas vérifié par la machine ; il
   servira à la notation au Lot 3.

**Questions pour l'IeC**

1. Les questions Avis HAS lisent les fichiers BDPM (SMR, ASMR, liens), pas
   le corpus HAS de l'ADR 0004 : convenu pour `v0` ? Le Lot 3 ajoutera des
   questions sur le texte des avis.
2. `alternatives-004` (présentations commercialisées) compte comme
   Alternatives, au sens de l'exemple de l'annexe B ; si l'IeC la préfère en
   Remboursement ou Disponibilité, c'est une ligne à changer dans `v1`.

**Propositions d'évolution** : PRD annexe B, ajouter que chaque question a
un comportement attendu (réponse, abstention, refus) et que la réponse
attendue cite l'archive (chemin et sha256), pas seulement « le gold à une
date » ; c'est ce que `v0` fait et ce que la CI du Lot 3 rejouera.
