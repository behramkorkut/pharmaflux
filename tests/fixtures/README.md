# Fixtures

Extraits des vrais fichiers sources, tels que reçus (octets conservés :
encodages et fins de ligne d'origine), avec les en-têtes HTTP relevés dans
le fichier `.headers` voisin. Les tests n'appellent jamais le réseau : le
serveur est simulé (`httpx.MockTransport`, voir `tests/conftest.py`).

**Date des extraits : 24/10/2026, entre 13:19 et 13:21 UTC** (requêtes du §0
de la mission 00, une par URL ; `CIS_InfoImportantes.txt` a fait l'objet
d'une seconde requête à 14:37 UTC, identique à l'octet près à la première).

**Complément du 26/10/2026 (mission 01, palier 2)** : les fichiers TSV ont
reçu, après leurs 40 premières lignes, des **lignes réelles choisies** dans
l'archive du 24/10 (copie rapatriée, lecture seule, aucune nouvelle
requête), pour que chaque valeur d'énumération et chaque anomalie connue
soit représentée. Les octets sont ceux de l'archive ; les numéros de ligne
sont ceux du fichier décompressé (`gunzip -c <archive> | sed -n '<N>p'`).
Voir « Lignes réelles ajoutées » ci-dessous. Les anomalies **fabriquées**
sont dans `contrats/`, jamais dans `bdpm/`.

## `bdpm/` — <https://base-donnees-publique.medicaments.gouv.fr>

| Fichier | URL | Extrait |
|---|---|---|
| `telechargement.html` | `/telechargement` | page entière (48 Ko) : les liens, dates et tailles affichées, le `nonce` CSP, la documentation PDF ; une page tronquée ne testerait pas l'analyseur |
| `CIS_bdpm.txt` | `/download/file/CIS_bdpm.txt` | 40 premières lignes (Windows-1252, CRLF) |
| `CIS_CIP_bdpm.txt` | `/download/file/CIS_CIP_bdpm.txt` | 40 premières lignes (UTF-8, LF) |
| `CIS_COMPO_bdpm.txt` | `/download/file/CIS_COMPO_bdpm.txt` | 40 premières lignes |
| `CIS_HAS_SMR_bdpm.txt` | `/download/file/CIS_HAS_SMR_bdpm.txt` | 40 premières lignes |
| `CIS_HAS_ASMR_bdpm.txt` | `/download/file/CIS_HAS_ASMR_bdpm.txt` | 40 premières lignes |
| `HAS_LiensPageCT_bdpm.txt` | `/download/file/HAS_LiensPageCT_bdpm.txt` | 40 premières lignes (ASCII, CRLF) |
| `CIS_GENER_bdpm.txt` | `/download/file/CIS_GENER_bdpm.txt` | 40 premières lignes |
| `CIS_CPD_bdpm.txt` | `/download/file/CIS_CPD_bdpm.txt` | 40 premières lignes |
| `CIS_CIP_Dispo_Spec.txt` | `/download/file/CIS_CIP_Dispo_Spec.txt` | 40 premières lignes |
| `CIS_MITM.txt` | `/download/file/CIS_MITM.txt` | 40 premières lignes |
| `CIS_InfoImportantes.txt` | `/download/CIS_InfoImportantes.txt` | 40 premières lignes (UTF-8, LF ; généré à la demande) |
| `Contenu_et_format_des_fichiers_telechargeables_dans_la_BDM_v5.pdf` | `/download/file/Contenu_et_format_…_v5.pdf` | 4 096 premiers octets du PDF (295 557 octets, `%PDF-1.7`), téléchargé le 24/10/2026 à 18:18 UTC (une requête, pour la 14e entrée du catalogue) |

Les fichiers BDPM sont des extraits de données publiques sous la licence de
la BDPM (citation de la source, aucune altération : les lignes sont
copiées telles quelles).

### Lignes réelles ajoutées (archive du 24/10/2026, 19:41 UTC sauf mention)

| Fichier | Archive (`bronze/bdpm/<fichier>/2026-10-24/`) | Lignes ajoutées | Ce qu'elles apportent |
|---|---|---|---|
| `CIS_bdpm.txt` | `20261024T194143Z__332b95926f76` | 300, 324, 1044, 1104, 4815 | procédures phyto (nat., déc.) et importation parallèle, autorisation retirée avec `Alerte`, autorisation suspendue |
| `CIS_CIP_bdpm.txt` | `20261024T231712Z__a6da566e8036` (23:17 UTC) | 50, 73, 78, 132, 160, 452, 1111, 13292, 14055 | prix ≥ 1 000 € écrits `1,466,29` (deux lignes), `100 %`, `35%`, présentation abrogée, arrêt sans AMM, suspension, indications remboursables, dates `19/01/1949` et `29/11/2924` |
| `CIS_HAS_SMR_bdpm.txt` | `20261024T194150Z__c2215af6b207` | 68, 69, 300, 307, 319, 677, 1822 | un couple (CIS, dossier) à deux avis, les trois valeurs « conditionnel », `Non précisé`, `Commentaires` |
| `CIS_HAS_ASMR_bdpm.txt` | `20261024T194153Z__f849554030c7` | 41, 118, 177, 223, 224, 514, 594, 738 | valeurs `IV`, `III`, `II`, `I`, les deux libellés longs, un couple à deux avis |
| `HAS_LiensPageCT_bdpm.txt` | `20261024T194155Z__2f01ff1e13f8` | 2485 | une URL de la forme `/jcms/c_N` |
| `CIS_GENER_bdpm.txt` | `20261024T194157Z__04ea92fb3d2e` | 2383 | type de générique `4` |
| `CIS_CPD_bdpm.txt` | `20261024T194159Z__e92ca48f83f5` | 28026 à 28034 | les trois lignes vides `\r\r\n` du fichier et leurs voisines (dont le `\r` de trop en fin de valeur) |
| `CIS_CIP_Dispo_Spec.txt` | `20261024T194201Z__43b7d2f3cfe6` | 44, 49, 111, 235, 304, 305, 312 | statuts 1 et 3, un CIP13 renseigné, début au `01/07/2027`, début en 2013, deux lignes entières identiques (305 et 312) |
| `CIS_MITM.txt` | `20261024T194203Z__300f24c39e84` | 123, 540, 7855 | date `13/03/2026`, exploitant vide, et la **dernière ligne du fichier, sans retour à la ligne** (la fixture finit comme l'archive) |
| `CIS_InfoImportantes.txt` | `20261024T194206Z__a27b30e12c83` | 2923 | date de fin en 2028 |

`CIS_COMPO_bdpm.txt` n'a rien reçu : ses 40 premières lignes contiennent déjà
`SA` et `FT`, un dosage vide et un numéro de liaison supérieur à 1.

## `contrats/` — anomalies fabriquées

Fichiers construits **à partir des premières lignes réelles** des fixtures
`bdpm/` ci-dessus, puis altérés à la main pour qu'une règle de
`pharmaflux.contrats.verification` se déclenche. Ce ne sont pas des extraits
de la BDPM : rien de ce qu'ils contiennent ne doit être cité comme une
donnée réelle.

| Fichier | Base réelle | Altérations (ligne : changement → règle attendue) |
|---|---|---|
| `specialites_anomalies.txt` | `CIS_bdpm.txt`, lignes 1 à 5 | 2 : fin de ligne `LF` seule → `fin_de_ligne` ; 3 : dernière colonne retirée → `nombre_colonnes` ; 4 : CIS de la ligne 1, statut `Autorisation nouvelle`, date `31/02/2020`, surveillance `oui` → `cle_non_unique`, `valeur_inconnue`, `date_illisible`, `booleen_inconnu` ; 5 : copie exacte de la ligne 1 → `ligne_dupliquee`, `cle_non_unique` ; 6 : CIS à 7 chiffres, dénomination vide, pas de retour final → `code_illisible`, `valeur_manquante`, `retour_final` |
| `specialites_utf8.txt` | `CIS_bdpm.txt`, lignes 1 à 3 | fichier entier transcodé de cp1252 en UTF-8 → `encodage` (ligne 0) |
| `presentations_anomalies.txt` | `CIS_CIP_bdpm.txt`, lignes 1 à 3 | 2 : premier `é` remplacé par l'octet cp1252 `0xE9` → `encodage` ; 3 : fin de ligne `CRLF`, taux `65%;45%`, prix `12.50`, date `19/01/1910` → `fin_de_ligne`, `valeur_inconnue`, `decimal_illisible`, `date_hors_plage` |
| `compositions_anomalies.txt` | `CIS_COMPO_bdpm.txt`, lignes 1 à 3 | 2 : nature `ST`, liaison `1a` → `valeur_inconnue`, `entier_illisible` ; 3 : ligne vide insérée → `nombre_colonnes` (lignes vides interdites) |
| `mitm_anomalies.txt` | `CIS_MITM.txt`, lignes 1 à 3 | 2 : lien vers `exemple.invalid` → `hote_inconnu` ; 3 : lien `fiche BDPM`, ATC `A02` → `url_illisible`, `code_illisible` ; pas de retour final (toléré) |
| `liens_ct_bom.txt` | `HAS_LiensPageCT_bdpm.txt`, lignes 1 à 3 | marque d'ordre des octets UTF-8 en tête → `encodage` |

## `openmedic/` — <https://www.data.gouv.fr>

| Fichier | URL | Extrait |
|---|---|---|
| `dataset.json` | `/api/1/datasets/open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes/` | le JSON du jeu, réduit aux 6 premières ressources sur 85 et à une description abrégée ; toutes les clés sont conservées |

Métadonnées publiques (Licence Ouverte). Aucune donnée personnelle dans
ces fichiers (`owner` nul, `contact_points` vide).

## Les renouveler

Un téléchargement réel par fichier, puis `head -n 40` (`head -c 4096` pour
le PDF ; jamais de conversion), puis les lignes choisies du tableau
ci-dessus (à rechoisir si leurs numéros ont bougé). Mettre à jour la date
ci-dessus et vérifier que `tests/test_empreintes.py` reflète toujours les
dates et tailles affichées par la page, et que
`tests/test_contrats_verification.py` compte toujours les mêmes anomalies
connues.
