# Mission 01 — palier 3 : profil, données et ADR (décisions 4, 5, 6)

**Fait**

- **Décision 4**, `pharmaflux profil [--fichier …] [--racine …] [--archive …]
  [--markdown <dossier>]` (`contrats/profil.py`, `contrats/rendu.py`,
  `cli.py`). Par défaut la dernière archive des onze fichiers ; `--fichier`
  accepte l'identifiant ou le nom du fichier ; `--archive` une archive
  précise (fichier déduit du chemin). Pour chacun : conformité au contrat
  (anomalies groupées par règle, nombre et cinq exemples, **`valeur_inconnue`
  en tête** puis les bloquantes), lignes et clé (valeurs distinctes,
  répétitions), colonnes (vides, distinctes, répartition complète pour les
  énumérations et les colonnes à trente valeurs au plus, minimum et maximum
  des dates et des nombres lisibles), **ordre des dates** entre colonnes de
  dates d'une même ligne, et **liens** (lignes et valeurs distinctes
  retrouvées dans la dernière archive du fichier cible, cinq exemples
  absents). Sortie Markdown aux colonnes alignées, lisible telle quelle
  dans le terminal ; `--markdown` écrit `<identifiant>.md` par source. Code
  de sortie 1 si une anomalie bloquante. 2 s pour les onze fichiers.
- **Décision 5**, `docs/donnees/` : les onze profils de l'archive du
  24/10 (archive et sha256 en tête ; archive de référence du contrat pour
  chacun), produits sur le Mac en lecture seule, **0 anomalie bloquante**.
  `README.md` : H.1 en tête (2 938 CIS de SMR, 2 470 de GENER, 1 662
  d'ASMR, 1 138 d'Info, 23 de Dispo_Spec absents de `CIS_bdpm.txt` ; 1 263
  spécialités sans présentation), vue d'ensemble, huit constats majeurs
  (dont « le Lot 1 comparera SMR, ASMR et Dispo_Spec ligne à ligne », les
  47 débuts postérieurs à la mise à jour, **569 des 679 CIS en difficulté
  sont des MITM, 83,8 %**), liens entre fichiers, encodages, outils
  (`profil`, lecture du PDF par `uvx --from pdfminer.six==20250506`).
- **Décision 6**, `docs/adr/` : 0001 collecte horaire sur le VPS-1
  (consignée, avec le score 1,3 et la mesure de fraîcheur par
  `date_source_affichee`) ; 0002 contrats TOML et neuf types, avec la ligne
  demandée au contrôle du palier 2 (bornes hautes 2030 et 2035 relevées par
  une nouvelle version du contrat) ; 0003 disponibilité, **proposé**, revue
  au plus tard le 07/12/2026, méthode (a) à (d) et critère de passage à
  « accepté » (trente disparitions, quatre sur cinq précédées d'un statut 4
  ou 3) ; 0004 corpus HAS.
- **Requêtes HAS** : cinq, dans l'ordre convenu, le 26/10 entre 13:31 et
  13:35 UTC, `User-Agent` du projet, réponses gardées dans le dossier
  temporaire de session (rien dans le dépôt) : `robots.txt` (deux chemins
  interdits, pas les avis) ; page `p_4461003` (CT-21902) ; page `c_2973834`
  (CT-17553) ; le document d'avis lié depuis la première (`p_4461002`) :
  **302 vers une redirection de mesure d'audience `doXiti.jsp`, non
  suivie** ; mentions légales (réutilisation libre avec source et date de
  mise à jour, sans altération). Le détail est dans l'ADR 0004.

**Vérifications locales** (commit testé : celui de ce palier, arbre propre)

| commande | résultat |
|---|---|
| `uv run ruff check .` et `ruff format --check .` | ok |
| `uv run mypy src` | ok, 18 fichiers |
| `uv run pytest -q` | **198 passed** (190 + 8 pour `profil`) |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | 16 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` | rien à signaler |
| `uv run pharmaflux profil --racine ~/pharmaflux-data --markdown docs/donnees` | 11 fichiers, 0 bloquante, code 0 |

**Garde-fou, refus signalé (non contourné)** : `awk '/^## 6|…/{p=1} … p'
01_Specifications/PRD_Plateforme_Medicaments_v0.2.md | head -150` a été
refusée (« awk » sur un chemin réservé à l'IeC, lecture permise par `cat`,
`head`, `grep`, `sed -n`). Le PRD a été lu avec `grep -n` et `sed -n`.

**Écarts à l'ordre**

1. **Le PDF d'avis n'a pas été téléchargé.** Le lien « document » des pages
   d'avis répond par une redirection de mesure d'audience (302) ; la suivre
   aurait été une sixième requête. L'ADR 0004 le dit et place les PDF en
   second, à mesurer au Lot 3.
2. **Deux liens de mesure ajoutés aux contrats du palier 2** (`v0`
   inchangé, aucun effet sur la vérification) : `specialites.code_cis →
   presentations` (spécialités sans présentation) et `disponibilite.code_cis
   → mitm` (croisement MITM), commentés comme mesures et non références.
   C'est ce qui permet au profil de produire les chiffres du README.
3. **« Ordre des dates »** : mesure ajoutée au profil, au-delà de la
   décision 4, pour les 47 débuts postérieurs à la mise à jour demandés au
   contrôle du palier 2 ; elle vaut pour tout couple de colonnes de dates.
4. **Nom des fichiers de `docs/donnees/`** : `<identifiant>.md`
   (`bdpm.specialites.md`), pour suivre le catalogue plutôt que le nom du
   fichier source.
5. **Décision 12** (README du projet, `CONTEXTE.md`) : au palier 4, comme
   prévu par l'ordre ; `CONTEXTE.md` dit déjà que les contrats portent
   l'encodage.

**Questions pour l'IeC** : l'ADR 0004 tranche « pages HTML d'abord, PDF en
second, par étapes depuis 2024 » ; si tu préfères les PDF dès la première
étape, l'ADR se réécrit au Lot 3 avec la mesure qui manque.

**Propositions d'évolution** : PRD v0.3, annexe A, colonne « Statut » des
onze fichiers : « profilé (mission 01, `docs/donnees/`) ».
