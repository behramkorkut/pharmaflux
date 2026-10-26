# Mission 01 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Fable 5.1) · **À :** IeC, beko · **Date :** 26/10/2026
**Branche :** `mission-01-profilage-et-contrats` · **Ordre lu sur `main`**
(commit `5d444b3`).

**Ce que j'ai lu, et comment.** La copie rapatriée `~/pharmaflux-data`
(`PHARMAFLUX_DATA` non posée), en lecture seule : 16 archives, toutes du
24/10/2026 (14 du premier passage à 19:41Z, la page et `CIS_CIP_bdpm.txt` à
23:17Z), et le manifeste, 352 lignes du 24/10 19:41 au 25/10 22:17 UTC,
0 erreur, aucun autre changement en 27 h. Le PDF de documentation,
décompressé dans le dossier temporaire de session et lu avec
`uvx --from pdfminer.six==20250506 pdf2txt.py` (voir A). Les mesures : des
scripts Python de la bibliothèque standard (`gzip`, `collections`, `re`),
exécutés avec `python3 -I -` sur l'entrée standard, sans écrire de fichier
(voir H.9 : le garde-fou refuse l'écriture d'un script hors du dépôt).
**Aucune requête réseau**, ni BDPM, ni data.gouv, ni HAS. Sauf mention,
les chiffres portent sur l'archive de 19:41Z ; pour `CIS_CIP_bdpm.txt`, sur
celle de 23:17Z (20 896 lignes), la seule différence avec 19:41Z étant deux
lignes de moins.

**Lecture rapide, les constats qui pèsent sur l'ordre :**

1. **Trois fichiers n'ont pas de clé unique** (D) : `CIS_CIP_Dispo_Spec.txt`
   (aucune combinaison de colonnes n'est unique, et **cinq lignes entières
   sont en doublon**), `CIS_HAS_SMR_bdpm.txt` et `CIS_HAS_ASMR_bdpm.txt`
   (le couple CIS + dossier HAS porte plusieurs avis, un par indication :
   2 488 et 307 couples en doublon). La décision 4 fait d'une clé non
   unique une anomalie bloquante : il faut que le contrat puisse déclarer
   une clé **non unique** (question 1).
2. **Des valeurs que les types fermés de C refuseront chaque jour** (A, C) :
   497 prix écrits `1,003,48` (virgule des milliers), 2 545 taux écrits
   avec une espace (`65 %`) contre 11 079 sans, le titulaire de `CIS_bdpm.txt` précédé d'une espace
   sur **100 %** des lignes, 51 dates de déclaration entre 1910 et 1949 et
   une en **2924**. On constate, on ne corrige pas : il faut décider comment
   un contrat déclare une anomalie *connue et systématique* pour qu'elle ne
   noie pas le profil (question 2).
3. **La documentation diverge des fichiers** sur quatre points (A) : les
   dates de `CIS_InfoImportantes.txt` sont en ISO `AAAA-MM-JJ` et non
   `JJ/MM/AAAA` ; la nature du composant vaut `FT`, pas `ST` ; l'agrément
   `inconnu` n'existe pas ; le schéma de la page 9 contredit le texte
   (CIP7 au lieu de CIP13 dans Dispo_Spec, 11 colonnes au lieu de 13 pour
   `CIS_CIP_bdpm.txt`).
4. **Disponibilité** (E) : la « remise à disposition » est un **statut
   explicite** (code 4, 119 lignes, toujours daté). Une ligne qui disparaît
   n'est donc pas « remise à disposition probable » comme le dit le PRD
   §6.3 : c'est plus probablement le retrait de la fiche par l'ANSM. Une
   seule archive distincte à ce jour : l'ADR 0003 sera « proposé », avec la
   méthode d'observation.

---

## A. Noms et sens des colonnes

**Lecture du PDF, sans rien installer.** `bronze/bdpm/Contenu_et_format_…_v5.pdf/2026-10-24/20261024T194208Z__db10d5a62bc6.pdf.gz`
décompressé (`gunzip -c`) dans le dossier temporaire de session, puis :

```bash
uvx --from pdfminer.six==20250506 pdf2txt.py -o doc_v5.txt doc_v5.pdf
```

PDF 1.7, 9 pages, « Date de mise à jour : 13/10/2026 », 486 lignes de
texte, toutes les listes de colonnes lisibles (puces `- ` et `o `). `uvx`
met en cache `pdfminer.six` et sa dépendance `cryptography` dans le dossier
d'`uv`, hors dépôt, hors système ; rien dans `pyproject.toml`. Avis :
retenir cette commande, version figée, documentée dans
`docs/donnees/README.md` comme outil de lecture, pas comme dépendance.
`pypdf` ferait aussi l'affaire ; `pdfminer.six` a l'avantage d'un script
en ligne de commande prêt.

**Ce que dit la documentation, et ce que les fichiers font.** Les onze
fichiers ont **exactement le nombre de colonnes documenté**, sur toutes
leurs lignes (une exception : trois lignes vides dans `CIS_CPD_bdpm.txt`).
Généralités confirmées : tabulation, pas de délimiteur, pas d'en-tête.
Écarts et constats, fichier par fichier :

| fichier | colonnes doc = réelles | lignes | écarts et constats |
|---|---|---|---|
| `CIS_bdpm.txt` | 12 = 12 | 15 883 | **Titulaire précédé d'une espace sur 15 883 lignes** ; forme pharmaceutique avec espace de tête ou de fin sur 1 133 ; voies multiples `;` sur 2 201 (jamais pour les titulaires) ; StatutBdm vide 13 652, `Warning disponibilité` 2 214, `Alerte` 17 ; n° d'autorisation européenne vide 13 510 ; dates d'AMM toutes `JJ/MM/AAAA`, de 1974 à 2026 ; statut AMM 5 valeurs, procédure 8, commercialisation 2, surveillance renforcée `Oui`/`Non`. |
| `CIS_CIP_bdpm.txt` | 13 = 13 | 20 896 | **Prix et prix public ≥ 1 000 € écrits `1,003,48`** (497 et 498 lignes ; honoraires toujours conformes, 1,02 à 2,76) ; **taux en dix graphies** (`65%` 9 084, `65 %` 1 769, `100%`, `100 %`, `30%`, `30 %`, `15%`, `15 %`, `35%` 4 ; vide 7 272) ; agrément `oui`/`non` seulement (la doc annonce aussi `inconnu`) ; dates de déclaration toutes au format, mais **51 entre 1910 et 1949** (presque toutes un 19 janvier) et **une au 29/11/2924** ; texte des indications vide sur 20 098 lignes ; prix, taux et honoraires vides ensemble ou renseignés ensemble (0 écart) ; CIP13 = `34009` + CIP7 + 1 chiffre sur 100 % des lignes. Le schéma de la page 9 n'a que 11 colonnes (sans prix public ni honoraires) : le texte du §3.2 fait foi. |
| `CIS_COMPO_bdpm.txt` | 8 = 8 | 32 439 | Nature du composant **`SA`/`FT`**, la doc écrit « ST » (son propre schéma dit « SA/FT ») ; dosage et référence vides sur 2 844 lignes (2 828 `SA`, 16 `FT`) ; 17 couples (CIS, élément, substance, nature) répétés avec des dosages différents (dilutions homéopathiques), distingués par le numéro de liaison. |
| `CIS_HAS_SMR_bdpm.txt` | 6 = 6 | 15 547 | Date **`AAAAMMJJ`** (seul format de ce type avec ASMR), 2002-12-18 à 2026-09-16 ; valeur en 9 libellés (`Important` 9 634, `Insuffisant` 2 838, `Modéré` 1 677, `Faible` 1 170, `Commentaires` 99, `Non précisé` 88, trois `… conditionnel`) ; 2 488 couples (CIS, dossier) avec plusieurs lignes, **valeur différente dans 2 471 cas** (un avis par indication) ; aucune ligne entière en doublon. |
| `CIS_HAS_ASMR_bdpm.txt` | 6 = 6 | 10 117 | Même structure ; valeur en 7 libellés (`V` 7 767, `IV` 1 277, `III` 607, `II` 208, `I` 85, `Commentaires sans chiffrage de l'ASMR` 160, `V dans l'attente de données` 13) ; 307 couples (CIS, dossier) répétés. |
| `HAS_LiensPageCT_bdpm.txt` | 2 = 2 | 10 480 | Codes `CT-N` tous conformes ; 12 dossiers avec plusieurs liens, 18 liens partagés par plusieurs dossiers, couple (dossier, lien) unique ; **un seul hôte**, `www.has-sante.fr`, deux formes d'URL (`/jcms/c_N` 7 996, `/jcms/p_N` 2 484). |
| `CIS_GENER_bdpm.txt` | 5 = 5 | 10 737 | Types `0`/`1`/`2`/`4` comme documenté (1 808 / 8 832 / 36 / 61) ; 1 686 groupes ; 63 CIS dans plusieurs groupes ; 11 groupes sans princeps ; **2 483 lignes dont le CIS n'est pas dans `CIS_bdpm.txt`** (2 470 CIS). |
| `CIS_CPD_bdpm.txt` | 2 = 2 | 28 532 (+3 vides) | **Trois lignes vides `\r\r\n`** au milieu du fichier (après une condition longue, à 97 % du fichier) ; 164 conditions distinctes ; couple (CIS, condition) unique hors lignes vides. |
| `CIS_InfoImportantes.txt` | 4 = 4 | 10 905 | **Dates `AAAA-MM-JJ`**, la doc dit `JJ/MM/AAAA` ; nom réel sans horodatage (la doc : `CIS_InfoImportantes_AAAAMMJJhhmiss_bdpm.txt`) ; toutes les dates de fin sont futures (2026-10-31 à 2028-10-27) : le fichier ne garde que l'actif ; texte = balise `<a …>` complète vers `ansm.sante.fr` (10 543) ou `www.ansm.sante.fr` (362) ; 1 138 CIS absents de `CIS_bdpm.txt`. |
| `CIS_CIP_Dispo_Spec.txt` | 8 = 8 | 703 | Voir E. Codes statut 1 à 4 et libellés conformes ; CIP13 renseigné sur 36 lignes ; date de remise renseignée sur 119 lignes, exactement celles du statut 4 ; **47 lignes dont la date de début est postérieure à la mise à jour**, une au 01/07/2027 ; 5 lignes entières en doublon ; le schéma de la page 9 dit « CIP7 », le texte et les données disent CIP13. |
| `CIS_MITM.txt` | 7 = 7 | 7 855 | **Pas de retour à la ligne final** (seul fichier dans ce cas) ; ATC à 7 caractères (7 769) ou **5** (86, classes pharmacologiques comme `A02AH`) ; date de publication en **3 valeurs** seulement (18/12/2024 : 7 459, 13/03/2026 : 51, 05/10/2026 : 345) : c'est la date de la liste, pas de la spécialité ; lien = fiche BDPM du CIS, 100 % ; exploitant vide 20 ; les 7 855 CIS sont dans `CIS_bdpm.txt`. |

La table des matières du PDF s'arrête au §3.10 alors qu'un §3.11 (MITM)
existe ; sans conséquence. Les noms de colonnes `snake_case` des contrats
reprendront les libellés du PDF (`code_cis`, `denomination`,
`forme_pharmaceutique`, `voies_administration`, `statut_amm`,
`type_procedure_amm`, `etat_commercialisation`, `date_amm`, `statut_bdm`,
`numero_autorisation_europeenne`, `titulaires`, `surveillance_renforcee`…),
avec la section du PDF en référence.

## B. Format des contrats

**Avis : d'accord**, TOML + `tomllib`, un fichier par source, versionné,
dans le paquet. Proposition de chemin : `src/pharmaflux/contrats/bdpm/`
avec `cis_bdpm.toml`… et `version = "v0"` **dans** le fichier plutôt que
dans le nom, pour qu'un chargeur trouve le contrat par identifiant du
catalogue (`bdpm.specialites` → `specialites.toml`, mêmes identifiants que
le collecteur). À vérifier au palier 2 : que `uv_build` embarque les
`.toml` dans la roue (l'installation du VPS est éditable, elle les lit de
toute façon dans `src/`).

**Ce qui manque à la liste de l'ordre**, d'après A :

- `source` : identifiant du catalogue, nom du fichier, section du PDF et
  **sha256 du PDF** lu (`db10d5a62bc6…`), date de vérification et
  **archive de référence** (chemin relatif + sha256) sur laquelle le
  contrat a été vérifié.
- Fin de fichier : `retour_final = "obligatoire" | "tolere"` (MITM) ;
  `lignes_vides = "anomalie"` (CPD : signalées, non bloquantes, et ignorées
  pour le compte de colonnes).
- Par colonne, en plus de nom, type, obligatoire, format : `valeurs` pour
  les énumérations (liste fermée), `separateur = ";"` pour les colonnes à
  valeurs multiples (voies, taux), `motif` pour les codes (voir C), et une
  déclaration d'**anomalie connue** (question 2).
- `cle` : liste de colonnes **et** `unique = true | false`, avec `raison`
  obligatoire quand `false` (SMR, ASMR, Dispo_Spec). `lignes_identiques`
  signalées comme anomalie dans tous les cas.
- `liens` : les colonnes qui référencent un autre fichier (CIS →
  `CIS_bdpm.txt`, dossier → `HAS_LiensPageCT_bdpm.txt`, CIP13 →
  `CIS_CIP_bdpm.txt`), pour la **mesure** des taux de correspondance de la
  décision 5, jamais pour une anomalie : 2 938 CIS de SMR, 2 470 de GENER,
  1 138 d'Info et 23 de Dispo_Spec sont absents de `CIS_bdpm.txt`, c'est la
  réalité des fichiers (avis anciens, médicaments sortis de la base).
- Le chargeur : dataclasses figées, refus de toute clé inconnue, d'un type
  hors du jeu de C, d'une colonne de clé absente, d'une énumération sans
  valeurs.

## C. Types

Jeu fermé proposé, **neuf types**, avec la règle et l'anomalie. Gravité :
**bloquante** pour ce qui empêche de lire le fichier comme on l'attend
(encodage, fin de ligne, nombre de colonnes, clé déclarée unique qui ne
l'est pas) ; **non bloquante** pour tout ce qui porte sur une valeur.

| type | paramètres | règle de validation | anomalie |
|---|---|---|---|
| `texte` | `longueur_max` facultatif | toujours valide ; espaces de tête ou de fin signalés | `espace_parasite` (non bloquante) |
| `entier` | — | `^-?\d+$` | `entier_illisible` |
| `decimal` | `decimales = 2` | `^\d+,\d{2}$` (virgule, pas de séparateur de milliers) | `decimal_illisible` (les 497 `1,003,48`) |
| `date` | `format` ∈ `JJ/MM/AAAA`, `AAAAMMJJ`, `AAAA-MM-JJ` ; `plage` facultative | motif du format **et** date calendaire réelle ; hors plage signalé | `date_illisible`, `date_hors_plage` (1910, 2924, 2027) |
| `booleen` | `vrai`, `faux` (ex. `Oui`/`Non`, `oui`/`non`) | valeur dans les deux graphies déclarées, casse exacte | `booleen_inconnu` |
| `enumeration` | `valeurs` | valeur dans la liste | `valeur_inconnue` (un nouveau statut, un nouveau SMR : c'est le signal de changement de format du PRD §9) |
| `code` | `motif` | expression régulière : CIS `^\d{8}$`, CIP7 `^\d{7}$`, CIP13 `^34009\d{8}$`, ATC `^[A-Z]\d{2}[A-Z]{2}(\d{2})?$`, dossier HAS `^CT-\d+$`, groupe générique `^\d+$` | `code_illisible` |
| `url` | `hotes` facultatif | `^https?://` et hôte dans la liste si donnée (`ansm.sante.fr`, `www.has-sante.fr`, `base-donnees-publique.medicaments.gouv.fr`) | `url_illisible`, `hote_inconnu` |
| `liste` | `de` (un type ci-dessus), `separateur = ";"` | chaque élément validé avec le type `de` | celle de l'élément |

Un seul type `date` paramétré plutôt que trois types : les trois formats
coexistent dans la base et le Lot 1 n'aura qu'une conversion à écrire.
Les taux de remboursement : `enumeration` avec les **dix graphies
observées** (`65%` et `65 %` sont deux valeurs), parce que le fichier les
contient ; la normalisation est au Lot 1. Pas de type `html` : le texte des
informations importantes est un `texte` avec `motif = "^<a "` déclaré en
`code` si l'on veut le vérifier. Rien n'est converti : la vérification lit
des chaînes et rend des anomalies.

## D. Clés

**En tête, le constat majeur** : trois fichiers n'ont pas de clé métier
unique, et pour deux d'entre eux ce n'est pas un défaut mais leur
structure (un avis HAS par indication). Le Lot 1 devra comparer ces
fichiers **ligne à ligne** (empreinte de la ligne) et non par clé.

| fichier | clé proposée | unique dans l'archive du 24/10 |
|---|---|---|
| `CIS_bdpm.txt` | CIS | **oui**, 15 883 / 15 883 |
| `CIS_CIP_bdpm.txt` | CIP13 | **oui**, 20 896 / 20 896 (CIP7 aussi ; CIS seul : 4 527 doublons) |
| `CIS_COMPO_bdpm.txt` | CIS + élément + code substance + nature + n° de liaison | **oui**, 32 439 / 32 439 (sans le n° de liaison : 17 doublons) |
| `CIS_HAS_SMR_bdpm.txt` | CIS + dossier HAS | **non** : 12 777 distincts / 15 547 lignes, 2 488 en doublon ; la ligne entière est unique |
| `CIS_HAS_ASMR_bdpm.txt` | CIS + dossier HAS | **non** : 9 805 / 10 117, 307 en doublon ; la ligne entière est unique |
| `HAS_LiensPageCT_bdpm.txt` | dossier HAS + lien | **oui**, 10 480 / 10 480 (dossier seul : 12 doublons) |
| `CIS_GENER_bdpm.txt` | groupe + CIS | **oui**, 10 737 / 10 737 (CIS seul : 63 doublons) |
| `CIS_CPD_bdpm.txt` | CIS + condition | **oui** hors les trois lignes vides, 28 532 / 28 532 |
| `CIS_InfoImportantes.txt` | CIS + date de début + date de fin + texte | **oui**, 10 905 / 10 905 (CIS + début : 142 doublons) |
| `CIS_MITM.txt` | CIS | **oui**, 7 855 / 7 855 |
| `CIS_CIP_Dispo_Spec.txt` | CIS + CIP13 + statut + date de début + lien ANSM | **non** : 698 / 703, **5 lignes entières en doublon** (même tension, même fiche) |

Pour Dispo_Spec, l'entité réelle est la **fiche ANSM** (290 URL distinctes
pour 703 lignes, jusqu'à 45 lignes par fiche) : une fiche couvre plusieurs
CIS, parfois plusieurs présentations. Proposition : clé déclarée (CIS,
CIP13, lien) avec `unique = false`, et le Lot 1 raisonne par fiche.

## E. Disponibilité et MITM

**Colonnes et valeurs de `CIS_CIP_Dispo_Spec.txt`** (703 lignes, 679 CIS,
mise à jour la plus récente 21/10/2026, cohérente avec la date affichée par
la page BDPM) :

- statut : `2` Tension d'approvisionnement **499**, `4` Remise à
  disposition **119**, `1` Rupture de stock **61**, `3` Arrêt de
  commercialisation **24** ; codes et libellés toujours cohérents ;
- CIP13 : renseigné sur **36 lignes** (35 connues de `CIS_CIP_bdpm.txt`),
  vide sur 667 : la fiche vise la spécialité entière ;
- date de début : toujours renseignée, de 17/11/2011 à **01/07/2027** (un
  arrêt de commercialisation annoncé) ; 58 lignes antérieures au 06/10/2023,
  pour lesquelles la doc prévient que c'est la date de mise à jour ;
  **47 lignes ont un début postérieur à la mise à jour** (42 tensions) ;
- date de mise à jour : toujours renseignée, 19/05/2021 à 21/10/2026 ;
- date de remise à disposition : renseignée sur **les 119 lignes de statut
  4 et sur elles seules**, toujours **égale à la date de début** ;
- lien : une URL `ansm.sante.fr/disponibilites-des-produits-de-sante/medicaments/<fiche>` par ligne, 290 fiches distinctes ;
- 20 CIS ont plusieurs lignes, 2 avec des statuts différents selon la
  présentation (une en remise, une en tension) ; 23 CIS absents de
  `CIS_bdpm.txt`, 34 lignes dont le CIS est « Non commercialisée » ;
- **569 des 679 CIS sont dans `CIS_MITM.txt`** (84 %).

**Ce que cela dit d'une ligne qui disparaît.** La fin d'une rupture ou
d'une tension est **représentée dans le fichier** : la ligne passe au statut
4 avec sa date de remise (115 des 119 remises ont commencé en 2026, 4 en
2025 ; aucune plus ancienne, alors que des tensions de 2023 sont encore
là). Une ligne qui disparaît n'est donc pas, en règle, une remise à
disposition : c'est la **fin de publication de la fiche** par l'ANSM, soit
après une remise (la ligne 4 reste quelques mois puis part), soit après un
arrêt de commercialisation, soit par retrait ou correction de la fiche. Le
PRD §6.3 (« remise à disposition probable ») n'est pas soutenu par les
données. À observer dans les prochaines archives, par fiche (CIS, CIP13,
lien) : (a) combien de lignes passent par le statut 4 avant de disparaître,
et combien disparaissent **directement** depuis 1 ou 2 ; (b) la durée de
vie d'une ligne 4 ; (c) si une ligne qui disparaît réapparaît ; (d) la
fréquence de changement du fichier (une seule version en 27 h ; la page
BDPM le date du 21/10). Avec une mise à jour hebdomadaire environ, six
semaines donnent quelques dizaines de transitions : ADR 0003 au statut
**proposé**, revue proposée début décembre 2026 (question 3).

**`CIS_MITM.txt`** : liste des médicaments d'intérêt thérapeutique majeur,
une ligne par CIS, sans statut ni date propre (la « date de publication »
est celle de la liste : trois valeurs). C'est un **drapeau** sur le CIS,
pas un historique ; le PRD annexe A (« pas de dates ») est confirmé. Son
intérêt est le croisement : 84 % des CIS en difficulté sont des MITM.

## F. Emplacement du jeu de questions

**Avis : d'accord** pour `evaluation/questions-reference-v0.toml` à la
racine, avec un `evaluation/README.md` (catégories, champs, comment
recalculer). Remarques : TOML n'a pas de valeur nulle, donc `attendu`
absent plutôt que vide pour les questions Dépense (`calculable_au =
"lot4"`) ; identifiants stables de la forme `disponibilite-001` ; la
commande `questions verifier` prend `--questions <chemin>` avec ce fichier
par défaut, résolu depuis la racine du dépôt (`git rev-parse` existe déjà
dans `passage.py`) ; les archives citées le sont par chemin relatif à la
racine de données et sha256, comme le manifeste.

## G. Reliquats de la mission 00

Liste de `pr.md` et décisions 9 à 12 : **confirmées, rien d'inutile**.
Compléments :

- Décision 11 : en plus des directives citées, `SystemCallArchitectures=native`,
  `ProtectProc=invisible`, `ProcSubset=pid`, `PrivateDevices=true`,
  `ProtectHostname=true`, `UMask=0077` ; `MemoryDenyWriteExecute=true`
  passe en général avec CPython (pas de JIT), à confirmer par beko sur le
  VPS. `IPAddressDeny` est exclu : le collecteur a besoin du réseau.
- Décision 10 : `etat` en flux implique de ne plus charger la liste ; la
  fonction `calculer_etat` prendra un itérable.
- Déjà fait pendant la clôture de la mission 00 : shellcheck figé en
  0.11.0 dans la CI (`4182a36`), repris dans le tableau de vérifications de
  l'ordre.
- À ajouter : la page BDPM publie **une date par fichier**
  (`date_source_affichee` : `2026-09-29` pour sept fichiers, `2026-10-21`
  pour Dispo_Spec, `2026-10-13` pour MITM, `2026-10-24` pour les
  présentations). L'ADR 0001 peut s'en servir pour mesurer la fraîcheur.

## H. Autres remarques

1. **`CIS_bdpm.txt` n'est pas le référentiel de tous les CIS.** 4 CIS de
   `CIS_CIP_bdpm.txt`, 2 938 de SMR, 1 662 d'ASMR, 2 470 de GENER, 1 138
   d'Info et 23 de Dispo_Spec en sont absents. Inversement, **1 261 CIS de
   `CIS_bdpm.txt` n'ont aucune présentation**, dont 1 244 « Commercialisée ».
   Les jointures du Lot 1 seront externes, et une question de référence
   sur un tel CIS attend une abstention motivée.
2. **Deux présentations ont disparu de `CIS_CIP_bdpm.txt` le 24/10** entre
   19:41Z et 23:17Z : toutes deux « Déclaration d'arrêt de
   commercialisation » du **25/10/2021**, retirées cinq ans après, à un
   jour près. Premier indice sur la règle de rétention des présentations (la
   doc parle de deux ans pour les spécialités).
3. **Fixtures** : 40 lignes par fichier ne contiennent ni prix ≥ 1 000, ni
   `65 %`, ni les statuts 3 et 4 de Dispo_Spec, ni les lignes vides de
   CPD, ni la fin sans retour de MITM. Au palier 2, les fixtures seront
   complétées par des **lignes réelles choisies** dans l'archive du 24/10
   (datées, sourcées), en plus des lignes fabriquées pour les anomalies.
4. **Statut administratif des présentations** : `Présentation abrogée`
   91, et quatre états de commercialisation dont « Déclaration de
   suspension de commercialisation » (3) et « Arrêt de commercialisation
   (le médicament n'a plus d'autorisation) » (161) : énumérations à figer
   dans le contrat.
5. **Corpus HAS** (sans requête, pour l'ADR 0004) : 10 480 liens vers un
   seul hôte, deux formes d'URL (`c_N`, `p_N`), 7 332 des 8 783 dossiers
   SMR ∪ ASMR ont un lien (83 %), 3 133 liens ne correspondent à aucun
   avis des deux fichiers ; 745 dossiers SMR depuis 2024. Proposition pour les
   cinq requêtes du palier 3 : `robots.txt`, une page `c_N`, une page
   `p_N`, un PDF d'avis lié depuis l'une d'elles, la page des mentions
   légales (licence).
6. `CIS_InfoImportantes.txt` est **généré à la demande** (mission 00, E) :
   collecté à chaque passage avec une empreinte sur les lignes triées, il
   n'a donné qu'une version en 27 h : le mécanisme tient. Rien à changer.
7. Le manifeste rapatrié est complet et cohérent avec les 16 archives (16
   lignes `nouveau`). Le rapatriement a eu lieu après le passage de 22:17Z
   le 25/10.
8. **Dates du Lot 1** : `CIS_CIP_bdpm.txt` porte des dates de déclaration
   manifestement fausses (1910 à 1949, 2924). Le contrat les signalera
   (`date_hors_plage`), jamais ne les corrigera ; la question « depuis
   quand » du jeu de référence évitera ces lignes.
9. **Garde-fou** (signalé, non contourné). L'outil `Write` vers le dossier
   temporaire de session a été refusé : « écriture hors du dossier du
   codeur », chemin
   `/private/tmp/claude-501/-Users-behramko-Postule-folder-Data-Engineer-apply-pharmaflux-codeur/6a06d2c6-7a8c-4511-aa78-b58327201bcd/scratchpad/m01/outils/profil_brut.py`.
   Les mêmes mesures ont été faites sans fichier (`python3 -I -` sur
   l'entrée standard). Le `gunzip -c > …/scratchpad/m01/pdf/doc_v5.pdf` par
   Bash, lui, n'a pas été refusé, et c'est aussi là qu'était le script de
   mesure mémoire de la mission 00 : les deux chemins (outil `Write`,
   redirection Bash) ne sont pas traités pareil. À trancher par l'IeC :
   permettre le dossier temporaire de session au codeur, ou interdire les
   deux. *(Ajout après la relecture 1 : ce script jetable n'existe plus ;
   depuis le palier 3, les chiffres de ce §0 sont refaits par
   `uv run pharmaflux profil`, comme l'addendum H.9 le demandait, et
   `docs/donnees/` en est la sortie.)*

## Questions pour l'IeC

1. **Clé non unique déclarée** : la décision 4 fait de la clé non unique
   une anomalie bloquante. Proposition : bloquante **seulement** quand le
   contrat déclare `unique = true` ; pour SMR, ASMR et Dispo_Spec,
   `unique = false` avec `raison`, et les lignes entières en doublon
   signalées comme anomalie non bloquante `ligne_dupliquee`. D'accord ?
2. **Anomalies connues et systématiques** : titulaire avec espace (100 %),
   prix `1,003,48` (497), taux avec espace (2 545), dates 1910–1949 (51).
   Trois options : (a) les signaler à chaque profil comme les autres (le
   profil groupe par règle, cinq exemples, le code de sortie n'en dépend
   pas) ; (b) permettre au contrat de les déclarer `anomalies_connues =
   [{regle, colonne, attendu = 497}]`, le profil signalant alors tout
   **écart au compte attendu** ; (c) déclarer dans le contrat des
   tolérances par colonne (`espaces_toleres = true`). Mon avis : (a) pour
   cette mission, simple et honnête ; (b) est utile mais c'est déjà de la
   détection de changement, Lot 1.
3. **ADR 0003** : statut « proposé », revue début décembre 2026, méthode
   d'observation en E ; ou préfères-tu une fenêtre plus courte ?
4. **Lecture du PDF** par `uvx --from pdfminer.six==20250506 pdf2txt.py`,
   version figée, documentée dans `docs/donnees/README.md` : d'accord ?
5. **Type `date` paramétré** par `format` (trois formats) plutôt que trois
   types ; **taux** en `enumeration` des dix graphies observées : d'accord ?
6. **Garde-fou** : H.9.

## Propositions d'évolution

- PRD v0.2, §6.3 : remplacer « une ligne qui disparaît du fichier de
  disponibilité = fin de la situation (remise à disposition probable) » par
  « la remise à disposition est un statut du fichier ; une ligne qui
  disparaît est une fin de publication, sens à observer (ADR 0003) ».
- PRD v0.2, annexe A : `CIS_MITM.txt` « pas de dates » → « liste sans
  historique, drapeau par CIS » ; `CIS_HAS_SMR/ASMR` « plusieurs avis par
  CIS et dossier (indications) » ; `CIS_CIP_bdpm.txt` « prix ≥ 1 000 € avec
  virgule des milliers, taux en plusieurs graphies ».
- `docs/agents/processus.md` ou garde-fou : le point H.9.
