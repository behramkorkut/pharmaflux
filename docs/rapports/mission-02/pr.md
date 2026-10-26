# Mission 02 — normalisation, snapshots et événements de changement du bronze

Branche `mission-02-normalisation-et-evenements`, 21 commits depuis `main`,
du §0 (`a28969f`) à cette description. Ordre de mission :
`docs/missions/mission-02-normalisation-et-evenements.md` (addendum 1).
Relecture 1 : NON CONFORME, deux bloquants corrigés en `bf005cb`
(`docs/relectures/mission-02/relecture-1.md`,
`docs/rapports/mission-02/reponse-relecture-1.md`). Relecture 2 :
**CONFORME**, 0 bloquant (`docs/relectures/mission-02/relecture-2.md`), un
point non bloquant corrigé (`reponse-relecture-2.md`).

## Ce qui est livré

**Normalisation et snapshot** (palier 1, `370d087`, correctifs `95958dc`) :
`contrats/normalisation.py`, forme canonique par type, en chaînes (les
règles de lisibilité laissent la valeur brute, celles de forme ou de
vraisemblance la forme canonique) ; `presentations.toml` passe en **v1**
(`milliers = ","` sur les prix, vérifié par prix public = prix + honoraires
sur 13 620 lignes sur 13 623 ; `canonique` des taux) avec un chargeur
v0/v1 ; `fichier_vide` non bloquante ; `evenements/snapshot.py`, lignes
figées à clé ou en multiensemble, bilan, snapshot écarté avec motif ; ADR
0005. Seule différence de non-régression : `decimal_illisible` passe de
995 à 0 sur `CIS_CIP_bdpm.txt`.

**Comparaison, événements, garde-fou de volume** (palier 2, `5e00abf`,
correctifs `155941f`) : `evenements/schema.py`, événement v1 tout en
chaînes (`creee`, `modifiee`, `supprimee`), identifiant sha256 sur les
chemins relatifs des deux archives, JSON stable relu strictement ;
`comparaison.py`, à clé ou ligne à ligne avec rangs (empreinte de la ligne
normalisée + rang), tri déterministe, `appliquer` comme vérificateur ;
`volume.py`, seuil de perte 1 %, vide et bloquant écartés sans appel, perte
en attente confirmée par un passage inchangé ou l'archive suivante ;
`bilan.py` ; six archives fabriquées à partir de lignes réelles.

**Chaîne, rejeu et reprise** (palier 3, `5e102ec`, correctifs `81635d5`,
`54a36e3`) : `evenements/rejeu.py` et la commande `uv run pharmaflux
evenements [--fichier] [--racine] [--sortie] [--reprendre]` ; sortie par
archive écrite atomiquement, dans l'ordre événements, bilan, état
(`evenements/<entite>/<horodatage>__<sha12>.jsonl`, `bilans/`,
`etat.json`) ; reprise depuis les archives, snapshots jamais sérialisés ;
bilan d'une archive en attente réécrit quand elle est tranchée ;
`--reprendre` refusé après un changement de version de contrat, un état
illisible dit quoi faire ; au rejeu complet, l'entité quitte l'état avant
l'effacement de sa sortie. ADR 0006, `docs/CONTEXTE.md`, `README.md`.

**Démonstration sur la copie du Mac** (lecture seule, sortie jetable) :
164 096 `creee` initiales (172 Mo), **3 `supprimee` réelles** de
`CIS_CIP_bdpm.txt` (arrêts de commercialisation), le fichier vide du
26/10 à 14:17 écarté et le 15:17 identique au 24/10 (zéro événement),
995 prix lus grâce à `milliers` ; 7,9 s, 474 Mo de mémoire résidente ;
`--reprendre` ensuite : 0 archive, 2,9 s. Deux rejeux complets sont
identiques à l'octet, la reprise ne change rien, l'archive n'a pas bougé.

**Correctifs de la relecture 1** (`bf005cb`) : la dernière archive traitée
de l'état est la dernière dont le verdict est définitif, et non le seul
dernier résultat, ce qui faisait relire une archive déjà traitée et effacer
ses événements à `--reprendre` quand une attente était tranchée par une
attente ; les `supprimee` d'une même ligne sortent du rang le plus haut au
plus bas, pour qu'un consommateur qui suit le flux voie un compte toujours
juste ; `deserialiser` exige de vraies listes. Relecture 2 : les trois
fixtures du tour signalées dans `tests/fixtures/README.md` (`da507c1`).

**Tests** : **413** (237 à la fin de la mission 01), sur un bronze de
synthèse fabriqué dans `tmp_path` à partir de `tests/fixtures/evenements/`
(lignes réelles altérées, signalées comme telles) : deux rejeux identiques
à l'octet, reprise après chacun des points d'arrêt d'une suite de
vingt-deux archives (attente tranchée dans les deux sens, deux pertes en
attente qui se suivent, ligne en triple ramenée à une puis remontée à
trois, passages inchangés), `etat.json` supprimé, aucun identifiant en
double, `appliquer` sur la sortie relue du disque. Aucun appel réseau,
aucune lecture de l'archive, aucune dépendance ajoutée.

**Documents** : `docs/rapports/mission-02/` (points à trancher, trois
rapports de palier, trois réponses aux contrôles, deux réponses aux
relectures), `docs/relectures/mission-02/` (six contrôles de l'IeC, deux
relectures, commis tels quels), journal à jour.

## Vérifications locales (commit testé : `da507c1` ; le code n'a pas changé depuis `bf005cb`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 127 files already formatted |
| `uv run mypy src` | Success: no issues found in 30 source files |
| `uv run pytest -q 2>&1 \| tail -25` | 413 passed in 11.2 s |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 17 tests, OK |
| shellcheck | non lancé : aucun `.sh` dans `git diff --name-only main...HEAD` |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` | 11 fichiers profilés, 0 anomalie bloquante, code 0 |
| `uv run pharmaflux questions verifier --racine ~/pharmaflux-data` | 40 questions : 25 conformes, 5 non calculables, 10 sans attendu, code 0 |
| `uv run pharmaflux evenements --racine ~/pharmaflux-data --sortie <jetable>` (à `bf005cb`) | identique au `diff -r` à la sortie du palier 3 ; `--reprendre` : 11 entités à 0 archive, aucune différence ; archive intacte (21 fichiers) |

Le compte de `ruff format` inclut les blocs Python des fichiers Markdown.
L'archive `~/pharmaflux-data` du Mac n'a été que lue pendant toute la
mission ; aucune requête réseau (BDPM, data.gouv ou HAS). Le relecteur a
rejoué le rejeu complet, le second rejeu et la reprise sur `811edcd`, avec
les mêmes résultats.

## Sur le VPS

Rien. La chaîne ne tourne que sur le Mac dans cette mission : la mémoire de
pointe de 474 Mo dépasse les 256 Mo de l'unité du VPS, et l'écriture en
flux est une condition de la mission 03 (ADR 0006). La collecte horaire
n'est pas touchée.

## Écarts à l'ordre et interprétations

Tous consignés dans les rapports de palier et acceptés par les contrôles
de l'IeC :

1. Les règles de normalisation par type vivent dans
   `contrats/normalisation.py`, pas dans `evenements/snapshot.py` : le
   profil lit les prix par la même conversion, et `contrats` ne dépend pas
   de `evenements`.
2. `appliquer` et `etat_du_snapshot` sont écrits dès le palier 2, comme
   test naturel de la comparaison.
3. Les fixtures ne jouent pas une suppression retenue à travers le
   garde-fou (une ligne sur 17 fait déjà 5,9 %) ; elle est testée par
   `comparer` directement et par les 3 `supprimee` réelles de l'archive.
4. Un `inchange` ne confirme une archive en attente que dans la fenêtre
   entre son archivage et l'archive suivante (précision de la règle F.3).
5. Le rejeu complet efface d'abord la sortie de l'entité, après l'avoir
   retirée de l'état, pour que deux rejeux restent identiques à l'octet.
6. Mémoire de pointe de 474 Mo au rejeu complet, acceptée pour cette
   mission, qui ne tourne que sur le Mac (voir ci-dessus).
7. Convention de schéma (relecture 1) : `supprimee` d'une même empreinte
   par rang décroissant, `creee` par rang croissant, `appliquer` strict ;
   retenue par l'IeC, à inscrire aux reliquats du PRD §6.3 avec l'identité
   d'une ligne sans clé unique et l'ordre alphabétique des colonnes.
