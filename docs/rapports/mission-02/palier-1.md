# Mission 02 — palier 1 : snapshot normalisé, contrat v1, ADR 0005 (décisions 1, 2)

**Fait**

- **Décision 2, normalisation** : `src/pharmaflux/contrats/normalisation.py`,
  `normaliser_valeur(type, valeur) -> Normalisee(valeur, regle)`. Forme
  canonique par type (tableau de l'ADR 0005), partage règle par règle :
  lisibilité → brute avec sa règle ; forme ou vraisemblance
  (`espace_parasite`, `longueur_depassee`, `date_hors_plage`,
  `hote_inconnu`) → canonique, règle consignée ; vide reste `""` ; liste
  élément par élément ; une valeur inchangée est le même objet chaîne. Les
  dates ISO se font par découpage du format déjà vérifié (test d'égalité
  avec `strptime`).
- **Contrat v1** (`presentations.toml`, raisons dans le fichier) :
  `milliers = ","` sur les trois prix, `canonique` des taux (`65 %` → `65%`,
  `100 %`, `30 %`, `15 %`). Chargeur : versions admises `v0` et `v1`
  (`VERSIONS_CONTRAT`), paramètres de la v1 **refusés dans un contrat v0**,
  `milliers` un seul caractère ni chiffre ni `-` ni `.`, `canonique` dont
  chaque graphie est dans `valeurs`, sans auto-référence ni chaîne, non
  vide. `tomlstrict.cles_restantes()` pour ce contrôle. Les dix autres
  contrats restent v0, intacts.
- **Vérification** : le type `decimal` admet `\d{1,3}(,\d{3})+,\d{2}` quand
  `milliers` est déclaré (`forme_decimale`, partagée avec la normalisation
  et les bornes du profil) ; anomalie **`fichier_vide`** non bloquante
  (`0 octet(s), aucune ligne non vide`, ligne 0) ; `_decoder` compte les
  lignes touchées par la substitution (`octets e9 illisibles en utf-8
  (2 lignes touchées)`).
- **Décision 1, snapshot** : `src/pharmaflux/evenements/snapshot.py`.
  `Ligne` figée (numéro, brutes = tuple de la `Lecture`, normalisées,
  anomalies (colonne, règle)), `Snapshot` (archive relative, sha256,
  horodatage, contrat, `identite` `cle` | `ligne`, `par_cle`, `par_ligne`
  empreinte → (ligne, occurrences), `bilan`, `ecarte`, `motif_ecart`),
  `BilanSnapshot` (lignes, bien formées, entités, occurrences en doublon,
  anomalies par règle, graphies par colonne à `canonique`, motif d'écart),
  `empreinte_ligne` (sha256 des valeurs normalisées jointes par `\x1f`).
  `lire(contrat, archive, racine)` passe par `bronze`, `construire` et
  `depuis_lecture` ne relisent jamais le fichier. Une bloquante → écarté
  avec motif (`4 anomalie(s) bloquante(s) : cle_non_unique (2), …`).
- **ADR 0005** écrit ; ADR 0002 : une ligne d'en-tête « complété par
  l'ADR 0005 ». `docs/donnees/bdpm.presentations.md` régénéré sur
  l'archive de référence du 24/10 (`a6da566e8036`, même commande qu'en
  mission 01, `--archive`) : seules différences, « v1 », « Produit le »,
  la ligne `decimal_illisible` disparue et les maxima des prix (`999,20`
  → `66,596,25`, `993,51` → `66,597,27`). `docs/donnees/README.md` : deux
  phrases sur la v1 (tableau et constat 2).
- **Tests** : 237 → **337** (+100) : 23 conversions, 13 illisibles restées
  brutes, 9 anomalies de forme, classement complet des règles, liste
  élément par élément, vide, objets partagés ; 2 refus en v0, 13 contrats
  v1 mal formés, chargement v1 ; 16 cas `decimal` avec `milliers`,
  `fichier_vide`, compte des lignes touchées ; snapshot de chaque fixture
  réelle retenu (identité, entités + doublons = bien formées, clés =
  valeurs normalisées, empreintes, chaînes partagées), tuples de la
  `Lecture` non copiés, prix/taux/dates des présentations, occurrences de
  `Dispo_Spec` (ligne 46 × 2), fixture fabriquée écartée, fichier vide non
  écarté, lecture par `bronze`.

**Non-régression du profil (contrat v1), comptes avant / après**
(archive de référence `20261024T231712Z__a6da566e8036`, 20 896 lignes) :
`decimal_illisible` **995 → 0** ; `date_hors_plage` 52 → 52 ;
`espace_parasite` 3 → 3 ; aucune autre différence. Les trois archives de
`CIS_CIP_bdpm.txt` ont chacune **995 prix** normalisés grâce à `milliers`
(bilan du snapshot). `uv run pharmaflux profil --racine ~/pharmaflux-data` :
11 fichiers, 0 bloquante, code 0. `questions verifier` : **25 / 5 / 10**.
Mesure : les onze snapshots des dernières archives (164 088 entités) en
**2,7 s**, pic **38 Mo** (sous `tracemalloc`). Archive du Mac lue seulement,
aucune requête réseau.

**Vérifications locales** (arbre committé comme fils de `a28969f`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 103 files already formatted |
| `uv run mypy src` | Success: no issues found in 25 source files |
| `uv run pytest -q` | 337 passed |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 17 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` | **non lancé** : refusé par le classificateur du mode auto (ci-dessous) ; aucun `.sh` n'est touché par ce palier |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` ; `questions verifier` | 11 fichiers, 0 bloquante ; 25 / 5 / 10 |

**Refus signalé, sans variante.** Le classificateur du mode auto (« Code
from External ») a refusé une commande composée qui enchaînait le script de
mesure, les deux tests des crochets et `uvx --from shellcheck-py==0.11.0.1
shellcheck infra/planification/*.sh ; echo "shellcheck code $?"`. J'ai
relancé séparément les trois parties qui ne téléchargent rien (mesure,
crochets, garde-fou) ; je n'ai pas relancé `shellcheck`, qui est la partie
visée. Les scripts de `infra/planification/` sont inchangés depuis la
mission 01 (vérifiés alors, et par la CI).

**Écarts à l'ordre**

1. Les règles par type vivent dans `contrats/normalisation.py`, pas dans
   `evenements/snapshot.py` comme je l'avais proposé au §0 K.5 : le profil
   (bornes min/max) lit les prix par la même conversion, et la couche
   `contrats` ne dépend pas de `evenements`. Le snapshot l'importe.
2. `docs/CONTEXTE.md` et `README.md` ne sont pas touchés : l'ordre les met
   au palier 3 (décision 10) ; la ligne « version `v0` » de CONTEXTE §
   contrats sera mise à jour là.

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** (PRD, consignes) : pour le Lot 5, sans code
ici : la réponse vide du 26/10 à 14:17 n'avait pas de `Content-Disposition`
(constat 2 du §0) ; un motif de signalement dans le manifeste (« réponse
sans `Content-Disposition` ») serait un signal gratuit.
