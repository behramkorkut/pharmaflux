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

## `evenements/` — archives fabriquées pour la détection des changements (mission 02)

Suites d'archives construites **à partir de lignes réelles** des fixtures
`bdpm/` ci-dessus (octets conservés : UTF-8 LF pour les présentations,
cp1252 CRLF pour la disponibilité), puis altérées à la main pour qu'une
comparaison donne chaque type d'événement et que le garde-fou de volume
rencontre chaque cas. Ce ne sont pas des extraits de la BDPM : rien de ce
qu'ils contiennent ne doit être cité comme une donnée réelle. Les tests les
archivent sous des noms d'archive fixés (24 au 26/10/2026) pour jouer le
retour A → B → A, l'oscillation A → B → A → B, la perte confirmée ou non.
Le cas bloquant réutilise `contrats/presentations_anomalies.txt`.

| Fichier | Base réelle | Altérations | Ce que la comparaison doit donner |
|---|---|---|---|
| `presentations_a.txt` | `CIS_CIP_bdpm.txt`, lignes 1 à 8 et 41 à 49 (17 lignes) | aucune | 17 `creee` initiales (une avec `date_hors_plage`, deux prix `1,466,29` lus `1466.29`) |
| `presentations_b.txt` | `presentations_a.txt` | ligne 3 (CIP13 `3400936963504`) retirée ; ligne 2 (`3400949497706`) : prix `68,68` → `69,00`, prix public `71,44` → `73,76` ; ligne 7 (`3400930116791`) : taux `15 %` → `15%` ; ligne 9 de `CIS_CIP_bdpm.txt` (`3400949444137`) ajoutée en fin | de A vers B : 1 `supprimee`, 1 `modifiee` (`prix_medicament`, `prix_public`), 1 `creee`, et **rien** pour la graphie du taux |
| `presentations_vide.txt` | — | 0 octet | écarté « vide », aucun événement (cas du 26/10 à 14:17) |
| `presentations_perte.txt` | `presentations_a.txt`, lignes 1 à 8 | 9 lignes retirées (perte de 52,9 %) | en attente, puis confirmé ou écarté selon la suite |
| `dispo_a.txt` | `CIS_CIP_Dispo_Spec.txt`, lignes 41 à 47 (46 et 47 identiques) | aucune | 7 `creee` initiales, la ligne en doublon aux rangs 1 et 2 |
| `dispo_b.txt` | `dispo_a.txt` | ligne 47 (le doublon) retirée ; ligne 44 (CIS `66890524`) : date de début `01/07/2027` → `01/09/2027` | de A vers B : `supprimee` de rang 2 du doublon, `supprimee` puis `creee` de la ligne changée, pas de `modifiee` |
| `dispo_triple.txt` | `dispo_a.txt` | ligne 47 (le doublon, CIS `67122698`) répétée une fois de plus : trois occurrences (8 lignes) | depuis `dispo_simple.txt` : `creee` de rangs 2 puis 3 de la même ligne (rang croissant) ; vers `dispo_b.txt` : `supprimee` de rangs 3 puis 2, plus le changement de date de B |
| `dispo_simple.txt` | `dispo_a.txt` | ligne 47 (le doublon) retirée : une seule occurrence (6 lignes) | depuis `dispo_triple.txt` : `supprimee` de rangs 3 puis 2 (rang décroissant), un passage `inchange` la confirme ensuite |
| `presentations_perte_forte.txt` | `presentations_perte.txt`, lignes 1 à 4 | 4 lignes retirées sur 8 | après `presentations_a.txt` : perte de 76,5 %, en attente, écartée dès que `presentations_perte.txt` revient ; après `presentations_perte.txt` : perte de 50 %, en attente, et confirme la perte précédente (deux attentes qui se suivent, dans les deux sens) |

## `evaluation/` — jeu de questions d'essai

`questions-essai.toml` : huit questions, un cas par verdict de
`pharmaflux questions verifier`, qui citent les fixtures `bdpm/` comme
archives (le test les écrit sous les noms cités, horodatage figé
`2026-10-24T14:17:00Z`, sha256 des octets de la fixture). Si une fixture
`bdpm/` change, le sha256 cité change aussi : c'est le vérificateur qui le
dit (`sha256 différent`).

## `has/` — <https://www.has-sante.fr> (mission 09, §0)

**Date : 31/10/2026, entre 10:41:23 et 10:43:24 UTC.** Les douze requêtes du
§0 de la mission 09, les seules permises à l'agent : en série, deux secondes
au moins entre deux, le `User-Agent` de la collecte de la BDPM
(`pharmaflux/0.1.0 (+https://github.com/behramkorkut/pharmaflux)`), aucune
redirection suivie. Elles sont faites par `requetes_s0.py` (ce dossier), qui
tient le journal en ajout seul `journal-s0.jsonl` (heure, méthode, URL,
statut, taille, sha256, en-têtes utiles) et refuse la treizième. Le détail et
ce que chaque réponse apprend : `docs/rapports/mission-09/points-a-trancher.md`.

| Fichier | URL | Ce que c'est |
|---|---|---|
| `robots.txt` | `/robots.txt` | 109 octets, deux chemins interdits (`/jcms/fc_2875171/`, un export de Scope Santé) : ni les pages d'avis, ni `/upload/` |
| `p_4072400.html` | `/jcms/p_4072400` | CT-21681, MOUNJARO, avis du 06/05/2026 : 12 spécialités, deux SMR et deux ASMR |
| `p_3590639.html` | `/jcms/p_3590639` | CT-21088, IMFINZI - LYNPARZA, avis du 15/01/2025 : un dossier, deux marques |
| `p_3577036.html` | `/jcms/p_3577036` | CT-21030, KALYDECO, avis du 18/12/2024 (questions `avis_has-002`, `-008`, `-009` de la v1) |
| `p_3500927.html` | `/jcms/p_3500927` | CT-20568, ADEMPAS, avis du 28/02/2024, premier des deux liens du dossier |
| `p_3741668.html` | `/jcms/p_3741668` | CT-20568, second lien : une autre décision, du 10/11/2025, sans SMR ni document |
| `c_2027377.html` | `/jcms/c_2027377` | CT-14040, DOLIPRANE, avis du 01/04/2015 : la forme `c_N`, 20 spécialités |
| `doc1-saut1.headers` … `doc1-saut4-pdf.headers` | le document d'avis de MOUNJARO, saut par saut | 302 vers `doXiti.jsp`, page de mesure d'audience (`doc1-saut3-doXiti.html`, rafraîchissement vers le PDF), puis le PDF en `HEAD` (631 564 octets) |
| `doc2-saut1.headers` | le document d'avis de DOLIPRANE (2015) | 302 vers `doXiti.jsp`, comme en 2026 |

`p_4072400.extrait.json` et `c_2027377.extrait.json` (palier 1) ne sont pas des
réponses : ce sont les **extractions de référence** de deux pages, relues à la
main contre la page, que `tests/test_has_extraction.py` exige à l'identique
(blocs, ordre, empreinte) tant que la version de l'extracteur ne change pas.

Les corps sont gardés **à l'octet**, tels que reçus (décompressés par
`httpx`), et leur sha256 est au journal. Une page porte un jeton CSRF et un
horodatage propres à chaque réponse : deux requêtes de la même page ne
donnent pas les mêmes octets. **Seule retouche** : la valeur du cookie de
session `JSESSIONID` est remplacée par `<retiré>` dans les `.headers` ; les
corps ne contiennent aucun cookie.

Contenus de la Haute Autorité de santé, réutilisés selon ses mentions légales
(article du 01/10/2015, lu le 26/10/2026, ADR 0004) : sans altération, avec
la source et la date. Document de la Haute Autorité de santé, disponible sur
<https://www.has-sante.fr>, pages consultées le 31/10/2026 ; la date de mise
en ligne de chaque avis est dans la page (« Mis en ligne le … »).

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
