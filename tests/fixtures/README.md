# Fixtures

Extraits des vrais fichiers sources, tels que reçus (octets conservés :
encodages et fins de ligne d'origine), avec les en-têtes HTTP relevés dans
le fichier `.headers` voisin. Les tests n'appellent jamais le réseau : le
serveur est simulé (`httpx.MockTransport`, voir `tests/conftest.py`).

**Date des extraits : 24/10/2026, entre 13:19 et 13:21 UTC** (requêtes du §0
de la mission 00, une par URL ; `CIS_InfoImportantes.txt` a fait l'objet
d'une seconde requête à 14:37 UTC, identique à l'octet près à la première).

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

Les fichiers BDPM sont des extraits de données publiques sous la licence de
la BDPM (citation de la source, aucune altération : les lignes sont
copiées telles quelles).

## `openmedic/` — <https://www.data.gouv.fr>

| Fichier | URL | Extrait |
|---|---|---|
| `dataset.json` | `/api/1/datasets/open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes/` | le JSON du jeu, réduit aux 6 premières ressources sur 85 et à une description abrégée ; toutes les clés sont conservées |

Métadonnées publiques (Licence Ouverte). Aucune donnée personnelle dans
ces fichiers (`owner` nul, `contact_points` vide).

## Les renouveler

Un téléchargement réel par fichier, puis `head -n 40` (jamais de
conversion). Mettre à jour la date ci-dessus et vérifier que
`tests/test_empreintes.py` reflète toujours les dates et tailles affichées
par la page.
