# Mission 02 — palier 2 : comparaison, événements, garde-fou de volume, bilan (décisions 3 à 6)

**Fait** (tout dans `src/pharmaflux/evenements/`, selon l'ordre et l'addendum 1)

- **Décision 4, `schema.py`** : `Evenement` figé, `version_schema = 1`, les
  champs du §0 D tels quels (`id`, `entite`, `fichier`, `version_contrat`,
  `type`, `etat_initial`, `identite`, `cle`, `empreinte_ligne`, `rang`,
  `avant`, `apres`, `champs_modifies`, `anomalies`, `date_source`,
  `date_observation`, `archive`, `archive_sha256`, `archive_precedente`,
  `archive_precedente_sha256`), valeurs de données toutes en chaînes.
  `identifiant` = sha256 de `entite \x1f archive \x1f archive_precedente
  \x1f type \x1f identite_de_ligne`, les deux archives par leur **chemin
  relatif** (`""` pour l'état initial) ; `identite_de_ligne` = clé
  normalisée jointe par `\x1f`, ou `empreinte \x1f rang`. `serialiser` : une
  ligne JSON, clés triées, séparateurs compacts, UTF-8 tel quel ;
  `deserialiser` relit la ligne et refuse une autre version
  (`EvenementInvalide`). Rien ne dépend de l'horloge.
- **Décision 3, `comparaison.py`** : `comparer(precedent | None, nouveau,
  date_source=)`. À clé : `creee`, `supprimee`, `modifiee` avec
  `champs_modifies` dans l'ordre du contrat, sur les valeurs normalisées
  (`65 %` → `65%` ne donne rien). Ligne à ligne : multiensemble, `supprimee`
  puis `creee`, rangs des occurrences, jamais de `modifiee` ; `cle` porte
  les colonnes de la clé déclarée non unique. Premier snapshot : une
  `creee` par entité, `etat_initial = true`, sans compression. Tri : clé,
  puis `supprimee` < `modifiee` < `creee`, puis empreinte, puis rang.
  `appliquer(etat, evenements)` rejoue les événements (inverse de la
  comparaison, refuse une incohérence) et `etat_du_snapshot` donne l'état à
  retrouver : la propriété « aucun changement perdu » de la décision 8 est
  testée dès ce palier sur les fixtures.
- **Décision 5, `volume.py`** : `SEUIL_PERTE = 0.01` ; `evaluer` → écarté
  (« bloquant : … », « vide : aucune ligne bien formée », **sans appel**),
  en attente (« 8 lignes au lieu de 17, perte de 52,9 %, en attente de
  confirmation »), retenu (« identique au dernier retenu (…) », « premier
  snapshot, N lignes ») ; `trancher` → confirmé par un passage `inchange`
  ou par l'archive suivante ni vide ni bloquante à ≤ 1,01 × ses lignes,
  écarté « jamais confirmée (archive suivante : N lignes) » sinon, en attente
  tant que rien ne la suit. `Suivi` déroule la règle sur une suite de
  snapshots (dernier retenu, en attente, résultats dans l'ordre des
  archives) : une archive en attente a **deux résultats**, en attente puis
  tranchée, pour que le palier 3 réécrive son bilan (addendum F.2) ;
  `clore(inchange_revu=)` à la fin du bronze. Les lignes comptées sont les
  lignes bien formées.
- **Décision 6, `bilan.py`** : `BilanArchive` = bilan du snapshot + verdict
  + `Ecart` avec le dernier retenu (lignes, entités, anomalies par règle en
  différence, événements par type) ; `en_dict` donne la forme JSON (le
  palier 3 l'écrit). Une mesure, pas une alerte : rien n'y touche au code
  de sortie.
- **Fixtures fabriquées** (`tests/fixtures/evenements/`, six fichiers
  décrits dans `tests/fixtures/README.md`, à partir de lignes réelles de
  `CIS_CIP_bdpm.txt` et `CIS_CIP_Dispo_Spec.txt`, octets conservés) :
  création, modification de deux champs, suppression, changement de
  graphie seul, doublon, fichier vide, perte partielle ; retour A → B → A,
  oscillation A → B → A → B et bloquant (`contrats/presentations_anomalies.txt`)
  joués par les tests sous des noms d'archive fixés.
- **Tests** : 347 → **368** (+21, `tests/test_evenements.py`) : état
  initial, à clé (trois types, aucun événement pour la graphie, ordre),
  retour et **oscillation A → B → A → B avec identifiants tous distincts**
  et sérialisation identique au rejeu, ligne à ligne (rangs 1 et 2 du
  doublon, `supprimee` puis `creee` d'une même clé), `appliquer` redonne
  chaque snapshot, identifiant recalculé à la main, JSON stable et relu,
  refus (deux fichiers, sans horodatage), **cas du 26/10** (retenu, écarté
  « vide », identique → 0 événement, écart −17 consigné), vide et bloquant
  jamais en attente, perte confirmée par l'archive suivante, perte jamais
  confirmée (la comparaison suivante porte le cumul depuis le dernier
  retenu), perte en attente à la fin du bronze puis confirmée par un
  `inchange` (à la clôture, et à l'arrivée de l'archive suivante), perte
  suivie d'un vide (écartée), seuil, bilan en dict, fixtures conformes.

**Aperçu réel** (copie du Mac, lecture seule, `CIS_CIP_bdpm.txt`, trois
archives, par `Suivi`) : 24/10 19:41 retenu, 20 898 `creee` initiales
(25 Mo de JSON Lines) ; 23:17 retenu, **2 `supprimee`** (CIP13
3400938844948 et 3400949939374, « Déclaration d'arrêt de commercialisation »,
`date_observation` 2026-10-24T23:17:12Z) ; 26/10 00:17 retenu, **1
`supprimee`** (3400930151181, même état). 13,4 s sous `tracemalloc`, pic
113 Mo (trois snapshots de 20 900 lignes et 20 898 événements en mémoire).
La démonstration complète, avec le vide du 26/10, est au palier 3.

**Vérifications locales** (arbre committé comme fils de `a9a117b`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 113 files already formatted |
| `uv run mypy src` | Success: no issues found in 29 source files |
| `uv run pytest -q` | 368 passed |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK |
| shellcheck | non lancé : aucun `.sh` touché (contrôle du palier 1) |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` ; `questions verifier` | 11 fichiers, 0 bloquante ; 25 / 5 / 10 |

**Écarts à l'ordre**

1. `appliquer` et `etat_du_snapshot` (décision 8, palier 3) sont écrits dès
   ce palier, dans `comparaison.py` : c'est le test naturel de la
   comparaison, et le palier 3 n'aura qu'à les appeler sur la sortie.
2. Le motif d'un snapshot bloquant répète le motif d'écart du snapshot
   (« bloquant : 2 anomalie(s) bloquante(s) : … ») ; la remarque du
   contrôle sur le double emploi `cle_non_unique` / clé normalisée est
   laissée telle quelle, comme permis.
3. Les fixtures ne permettent pas de jouer une suppression **retenue** à
   travers le garde-fou (une ligne sur 17 est déjà 5,9 %, donc en attente) ;
   la suppression retenue est testée par `comparer` directement, et par
   l'aperçu réel ci-dessus (−2 et −1 lignes sur 20 898 : retenues).

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** (PRD, consignes) : aucune.
