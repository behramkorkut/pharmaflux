# Mission 06 — palier 2 : vues métier et questions (décisions 2 et 4)

Contrôle du palier 1 lu et committé tel quel (`8823759`). Python pur : aucune
commande `docker`, `colima` ni `make` ; `~/pharmaflux-data` en lecture
seule ; aucune requête vers les sources ; aucun refus du garde-fou. Le
courtier tournait : les 11 tests d'intégration ont tourné.

**Fait**

- **`gold/vues.py`** : la fiche médicament (une ligne par CIS connu,
  `dans_referentiel`, sections en `list<struct>` triées, avis SMR et ASMR
  tous gardés avec `occurrences` et `liens_avis`, informations en cours au
  jour UTC, bornes incluses, fin vide = en cours, `provenance` par fichier,
  `colonnes_illisibles`, `instant`) ; la disponibilité courante, avec la
  **priorité écrite** de l'exigence 2 (`declare`, puis `fin_de_publication`
  lue dans les seules versions fermées au plus à l'instant, puis
  `aucun_signalement`), `portee`, `occurrences`, `presentation_connue`,
  `debut_a_venir`, `fin_publication` ; les alternatives (groupe × présentation
  × disponibilité, triées par `numero_tri`, sans classement).
- **`gold/questions.py`** et `questions verifier --entrepot` (H.1, H.2) :
  instant lu dans le nom de l'archive, attendus normalisés par le contrat
  puis typés, comparaison en multiensemble ; route par la fiche (CIS ou
  CIP13), les alternatives (groupe) ou les colonnes typées ; une discordance
  affiche les deux calculs ; une discordance ou une question hors de la
  fenêtre du silver donne le code 2.
- **Commandes** : `gold fiche` (`--cis`, `--tout`, `--format jsonl|texte`),
  `gold disponibilite` (`--cis`, `--cip13`), `gold alternatives` (`--cip13`,
  `--cis` qui s'excluent du résultat, `--groupe`) ; `gold sql` voit aussi
  `fiche_medicament`, `disponibilite_courante`, `alternatives`.
  `gold/rendu.py` : JSON à toute profondeur (décimal en chaîne, date ISO,
  instant en `…Z`), écrit par lots de 500 lignes, et le texte de la fiche,
  qui dit « observée depuis …, source du … ».
- **Exigence 1** : `tests/references_gold.py`, une requête DuckDB par vue,
  écrite à part (la fermeture y est lue dans toutes les versions du silver,
  filtrées en SQL). Égalité en multiensemble, listes comprises, sur les
  fixtures à trois instants (14:17, 14:30, 16:17), et sur le jeu pour un
  échantillon fixe de **28 CIS** : ceux des 25 questions (et des groupes 49
  et 40), le premier CIS dans plusieurs groupes, celui à 37 présentations,
  celui à 44 avis SMR, BEFIZAL L.P. 62119207, une fiche partielle, un CIS
  signalé sans présentation.
- **Exigence 2** : `tests/test_gold_vues.py`, un fichier de disponibilité
  **synthétique construit en mémoire** sur des CIS des extraits réels, un
  test par branche (déclaré sur chaque présentation visée ; fin de
  publication avec sa date et son dernier statut ; rien d'appris après
  l'instant ; une ligne directe en cours l'emporte sur une fermeture ;
  aucun signalement), plus les doublons, l'arrêt annoncé et la présentation
  inconnue.
- `demo_silver` reste en lecture seule pour tous les tests.

**Vérifications locales** (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | verts (225 fichiers) |
| `uv run mypy src` | vert, 58 fichiers, 0 `type: ignore` |
| `GITHUB_ACTIONS=true uv run pytest -q` | **535 passed** en 144 s (518 avant ; les 11 `integration` ont tourné) |
| crochets git / garde-fou | conformes / OK |
| `demo verifier` ; `profil`, `questions verifier` sur `~/pharmaflux-data` | conforme ; 0 bloquante ; 25 / 5 / 10 |
| `evenements` sur la copie du Mac, `diff -r` contre `53f261b` | identique |
| `silver verifier` sur le jeu | 22/22 conformes |
| test de l'exigence 1 sur le jeu, seul (`pytest …::test_les_vues_du_jeu_egalent_leur_reference_sur_l_echantillon`) | 20 s, **524 Mo** pour le processus entier (rejeu, silver, gold, référence) ; sur un silver déjà bâti : vues 411 Mo, référence 436 Mo |

**Démonstration (décision 6)** sur le silver du jeu (`$S`, dossier jetable) :

| commande | résultat | temps | mémoire |
|---|---|---|---|
| `gold fiche --cis 63830632 --format texte --a 2026-10-24T20:00:00Z` | 1 présentation, 3400938844948 | 1,4 s | 421 Mo |
| idem `--a 2026-10-27T00:17:12Z` | « Présentations : — » (retirée le 24/10 à 23:17:12) | 1,4 s | 412 Mo |
| `gold disponibilite --cip13 3400933961688` (LARIAM) aux deux instants | `declare`, Rupture de stock, `portee = specialite`, depuis le 2026-06-25 (une seule archive de disponibilité dans le jeu : identique) | 1,4 s | 411-415 Mo |
| `gold disponibilite --a 2026-10-24T19:42:00Z` | refus, code 2 : disponibilité, infos importantes et MITM pas encore observées | 0,7 s | 147 Mo |
| `gold fiche --tout` | 21 445 fiches | 3,7 s | **415 Mo** |
| `gold alternatives --cis 62011103` / `gold sql` (sur `disponibilite_courante`) | 7 lignes / `aucun_signalement` 20 004, `declare` 36 + 878 | 1,4 s | 420 / 417 Mo |
| `gold qualite` | code 0, aucun bloquant | 1,3 s | 312 Mo |
| `questions verifier --racine demo/archive --entrepot $S` | **25 concordantes** (sept instants) | 9,0 s | **452 Mo** |

Toutes les commandes `gold` restent sous 512 Mo.

**Écarts à l'ordre et précisions**

1. **Les alternatives gardent une ligne pour une spécialité du groupe sans
   présentation** (`code_cip13` vide), au lieu de la laisser à la fiche
   seule (§0 F). Sans elle, `alternatives-001` (les CIS d'un groupe) ne se
   recalculait pas fidèlement par la vue.
2. **Un instant où l'une des onze entités n'est pas encore observée est
   refusé** par les vues et par `gold qualite` (code 2) : à 19:42:00 le
   24/10, la vue aurait dit « aucun signalement » de toutes les
   présentations avant d'avoir lu le fichier de disponibilité. Le recalcul
   des questions, lui, n'en a pas besoin : une question ne lit que la
   section de son entité, dans la fenêtre de celle-ci.
3. **La sortie JSON par lots** : `gold fiche --tout` montait à 552 Mo, tout
   converti d'un coup en objets Python ; 415 Mo par lots de 500.
4. **`conftest.py` importe `pharmaflux.silver` en premier**, pour que
   l'allocateur système d'Arrow soit posé avant que les modules de test
   n'importent PyArrow : sans cela, le test de l'exigence 1 mesurait 945 Mo
   (jemalloc), 524 avec.
5. **La connexion de référence des tests a un seul fil** (la même barrière
   que `silver sql`) : avec huit fils, la requête de la fiche prenait 190 Mo
   de plus, même sur 28 CIS. Le code de production ne change pas.

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** : celle du palier 1 (détection qui compare
aussi les anomalies), à porter dans l'ADR 0010 (« Limites ») et `pr.md`.
