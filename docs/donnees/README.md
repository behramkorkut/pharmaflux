# Profil des sources — ce que les fichiers de la BDPM contiennent vraiment

Mesuré sur l'archive du **24/10/2026** (copie rapatriée sur le Mac, lecture
seule), avec `pharmaflux profil --markdown docs/donnees` (mission 01).
Chaque fichier `bdpm.<nom>.md` de ce dossier porte en tête l'archive
profilée et son sha256 ; tout chiffre cité ici en vient, sauf mention
d'une autre source. Les extraits de données sont des valeurs brutes de la
BDPM (base-donnees-publique.medicaments.gouv.fr, fichiers datés par la
page de téléchargement du 29/09/2026 au 24/10/2026 selon le fichier),
reproduites sans altération, comme la licence BDPM le demande.

## D'abord : `CIS_bdpm.txt` n'est pas le référentiel de tous les CIS

Le fichier des spécialités ne contient que les médicaments commercialisés
ou arrêtés depuis moins de deux ans. Les autres fichiers citent des CIS
qui n'y sont pas, et c'est normal (avis anciens, médicaments sortis de la
base) :

| fichier | CIS distincts | retrouvés dans `CIS_bdpm.txt` | absents |
|---|---|---|---|
| `CIS_HAS_SMR_bdpm.txt` | 9 144 | 6 206 (67,9 %) | **2 938** |
| `CIS_GENER_bdpm.txt` | 10 661 | 8 191 (76,8 %) | **2 470** |
| `CIS_HAS_ASMR_bdpm.txt` | 6 287 | 4 625 (73,6 %) | **1 662** |
| `CIS_InfoImportantes.txt` | 5 128 | 3 990 (77,8 %) | **1 138** |
| `CIS_CIP_Dispo_Spec.txt` | 679 | 656 (96,6 %) | 23 |
| `CIS_CIP_bdpm.txt` | 14 624 | 14 620 (100,0 %) | 4 |
| `CIS_COMPO_bdpm.txt`, `CIS_CPD_bdpm.txt`, `CIS_MITM.txt` | 15 881, 12 555, 7 855 | tous | 0 |

Dans l'autre sens, **1 263 des 15 883 spécialités n'ont aucune
présentation** dans `CIS_CIP_bdpm.txt` (archive de 23:17 UTC). Toute
jointure du Lot 1 est donc externe, et une question de référence posée sur
un CIS absent de `CIS_bdpm.txt` attend une abstention motivée, pas une
réponse (`evaluation/`, mission 01 palier 4).

## Vue d'ensemble

| fichier | lignes | clé | unique | encodage, fin de ligne | anomalies non bloquantes le 24/10 |
|---|---|---|---|---|---|
| `CIS_bdpm.txt` | 15 883 | CIS | oui | cp1252, CRLF | 17 016 `espace_parasite` (titulaire précédé d'une espace sur **toutes** les lignes, 1 133 formes), 1 `code_illisible` (`EU/1/17/1235/`) |
| `CIS_CIP_bdpm.txt` | 20 896 | CIP13 | oui | **UTF-8, LF** | 52 `date_hors_plage` (51 déclarations de 1910 à 1949, une au `29/11/2924`), 3 espaces ; les 995 prix ≥ 1 000 € écrits `1,466,29` étaient `decimal_illisible` avec le contrat v0, ils se lisent depuis la v1 (`milliers`, ADR 0005) |
| `CIS_COMPO_bdpm.txt` | 32 439 | CIS + élément + substance + nature + n° de liaison | oui | cp1252, CRLF | 1 309 `espace_parasite` (espace de fin après la substance) |
| `CIS_HAS_SMR_bdpm.txt` | 15 547 | CIS + dossier HAS | **non** | cp1252, CRLF | aucune |
| `CIS_HAS_ASMR_bdpm.txt` | 10 117 | CIS + dossier HAS | **non** | cp1252, CRLF | aucune |
| `HAS_LiensPageCT_bdpm.txt` | 10 480 | dossier HAS + lien | oui | ASCII, CRLF | aucune |
| `CIS_GENER_bdpm.txt` | 10 737 | groupe + CIS | oui | cp1252, CRLF | aucune |
| `CIS_CPD_bdpm.txt` | 28 532 | CIS + condition | oui | cp1252, CRLF | 3 `ligne_vide` (`\r\r\n`), 3 espaces (un `\r` de trop en fin de valeur) |
| `CIS_InfoImportantes.txt` | 10 905 | CIS + début + fin + texte | oui | **UTF-8, LF** | aucune |
| `CIS_CIP_Dispo_Spec.txt` | 703 | CIS + CIP13 + lien ANSM | **non** | cp1252, CRLF | 5 `ligne_dupliquee` |
| `CIS_MITM.txt` | 7 855 | CIS | oui | cp1252, CRLF, **sans retour final** | aucune |

**Aucune anomalie bloquante** sur les onze fichiers : encodages, fins de
ligne et nombres de colonnes sont ceux des contrats
(`src/pharmaflux/contrats/bdpm/`), et les clés déclarées uniques le sont.
Les anomalies ci-dessus sont des **constats**, signalés à chaque profil,
jamais corrigés ni masqués (PRD §6.2) : c'est au Lot 1 de normaliser
(virgule des milliers, espaces, graphies des taux), et l'ADR 0002 dit
pourquoi les contrats ne portent pas de tolérance.

## Constats majeurs pour le Lot 1

1. **Trois fichiers n'ont pas de clé unique, par construction.** SMR et
   ASMR portent un avis par indication : 2 488 et 307 couples (CIS,
   dossier) ont plusieurs lignes, presque toujours avec des valeurs
   différentes. `CIS_CIP_Dispo_Spec.txt` décrit des fiches ANSM (290 fiches
   pour 703 lignes, jusqu'à plusieurs CIS et présentations par fiche) :
   aucune combinaison de colonnes n'est unique, et cinq lignes entières
   sont en doublon. **Le Lot 1 comparera SMR, ASMR et Dispo_Spec ligne à
   ligne** (empreinte de la ligne), pas par clé.
2. **Les prix et les taux ne se lisent pas tels quels.** 497 prix et 498
   prix publics au-delà de 1 000 € s'écrivent `1,466,29` (virgule des
   milliers) ; les honoraires, jamais. Les taux de remboursement ont neuf
   graphies (`65%` 9 084 fois, `65 %` 1 769, `100%`, `100 %`, `30%`,
   `30 %`, `15%`, `15 %`, `35%`), énumérées telles quelles dans le contrat.
   Depuis la v1 du contrat (mission 02, ADR 0005), la virgule des milliers
   est déclarée (`milliers = ","`, lecture vérifiée par prix public = prix
   + honoraires) et les graphies avec espace ont une forme canonique
   (`canonique`) : la normalisation les lit, le profil ne les signale plus.
3. **Des dates fausses, à ne pas corriger.** 51 dates de déclaration de
   commercialisation entre 1910 et 1949 (presque toutes un 19 janvier) et
   une au `29/11/2924`. Le contrat les signale `date_hors_plage` ; le jeu de
   questions de référence évite ces lignes.
4. **Trois formats de date coexistent** : `JJ/MM/AAAA` (spécialités,
   présentations, disponibilité, MITM), `AAAAMMJJ` (avis SMR et ASMR),
   `AAAA-MM-JJ` (informations importantes, que la documentation annonce
   pourtant en `JJ/MM/AAAA`).
5. **La documentation (PDF v5 du 13/10/2026) diverge des fichiers** sur
   quatre points : dates des informations importantes en ISO, nature du
   composant `FT` et non `ST`, agrément `inconnu` jamais observé, schéma de
   la page 9 contredit par le texte (CIP7 au lieu de CIP13 dans Dispo_Spec,
   11 colonnes au lieu de 13 pour les présentations). Les contrats suivent
   les fichiers et notent l'écart dans la description de la colonne.
6. **Disponibilité.** Quatre statuts : tension 499, remise à disposition
   119, rupture 61, arrêt 24. La date de remise est renseignée sur les 119
   lignes de statut 4 et sur elles seules, toujours égale à la date de
   début. **47 lignes ont une date de début postérieure à leur date de mise
   à jour** (une au `01/07/2027`, un arrêt annoncé) : c'est une règle
   métier, mesurée ici (« Ordre des dates » du profil), pas une règle de
   schéma. Le sens d'une ligne qui disparaît est traité dans l'ADR 0003.
7. **MITM est un drapeau, pas un historique** : une ligne par CIS, trois
   dates de publication en tout (celles de la liste). Le croisement vaut le
   détour : **569 des 679 CIS en difficulté dans `CIS_CIP_Dispo_Spec.txt`
   sont des MITM (83,8 %)**, et les 7 855 MITM sont tous dans `CIS_bdpm.txt`.
8. **Les informations importantes ne gardent que l'actif** : les 10 905
   dates de fin sont postérieures au 24/10/2026 (jusqu'au 27/10/2028), et
   le texte est une balise `<a …>` complète vers `ansm.sante.fr`.

## Liens entre fichiers

Mesurés par le profil (section « Liens ») sur la dernière archive de
chaque fichier cible ; jamais une anomalie.

| de | vers | lignes retrouvées | valeurs distinctes retrouvées |
|---|---|---|---|
| présentations `code_cis` | spécialités | 20 892 / 20 896 (100,0 %) | 14 620 / 14 624 |
| spécialités `code_cis` | présentations | 14 620 / 15 883 (92,0 %) | 14 620 / 15 883 |
| disponibilité `code_cip13` | présentations `code_cip13` | 35 / 36 (97,2 %) | 35 / 36 (`3400957382070` absent) |
| disponibilité `code_cis` | MITM | 592 / 703 (84,2 %) | 569 / 679 (83,8 %) |
| SMR `code_dossier_has` | liens CT | 13 933 / 15 547 (89,6 %) | 6 551 / 7 574 (86,5 %) |
| ASMR `code_dossier_has` | liens CT | 8 075 / 10 117 (79,8 %) | 4 667 / 6 019 (77,5 %) |

Le fichier des liens CT (10 480 liens) ne vise qu'un hôte,
`www.has-sante.fr`, sous deux formes d'URL (`/jcms/c_N` et `/jcms/p_N`) ;
voir l'ADR 0004 pour le corpus HAS.

## Encodages et formes

Neuf fichiers en Windows-1252 avec CRLF, deux en UTF-8 avec LF
(`CIS_CIP_bdpm.txt`, `CIS_InfoImportantes.txt`), un en ASCII pur
(`HAS_LiensPageCT_bdpm.txt`). Aucun en-tête, tabulation comme séparateur,
pas de délimiteur de champ. `CIS_MITM.txt` finit sans retour à la ligne.
`CIS_CPD_bdpm.txt` contient trois lignes vides `\r\r\n` à 97 % du fichier.
Un fichier cp1252 qui arriverait un jour en UTF-8 serait signalé par le
contrat (le décodage seul ne le verrait pas : les deux octets d'un `é`
UTF-8 sont valides en cp1252).

## Outils

- `uv run pharmaflux profil [--fichier …] [--archive …] [--racine …]
  [--markdown <dossier>]` : par défaut la dernière archive des onze
  fichiers ; code de sortie 1 si une anomalie bloquante est trouvée. Les
  fichiers de ce dossier se régénèrent avec
  `uv run pharmaflux profil --markdown docs/donnees` (seule la ligne
  « Produit le … » change tant que l'archive ne change pas).
- La documentation officielle des formats est archivée
  (`bronze/bdpm/Contenu_et_format_des_fichiers_telechargeables_dans_la_BDM_v5.pdf/`,
  sha256 `db10d5a6…`, 9 pages, « Date de mise à jour : 13/10/2026 »). Elle
  se lit sans rien installer ni ajouter au projet :
  `gunzip -c <archive> > doc_v5.pdf` puis
  `uvx --from pdfminer.six==20250506 pdf2txt.py -o doc_v5.txt doc_v5.pdf`
  (version figée ; outil de lecture, pas une dépendance).
- Les contrats : `src/pharmaflux/contrats/bdpm/*.toml`, format et types
  dans l'ADR 0002.

## Les pages d'avis de la HAS (mission 09)

Le profil de la page d'avis de la Commission de la transparence (structure, tailles, sections,
dates, rejets, coquilles gardées telles quelles) est dans [`has.pages_avis.md`](has.pages_avis.md),
mesuré sur les 722 pages de la première étape du corpus.

