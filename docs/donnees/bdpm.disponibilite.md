# Profil — `CIS_CIP_Dispo_Spec.txt` (bdpm.disponibilite)

Fiches ANSM de disponibilité des spécialités : ruptures, tensions, arrêts, remises à disposition.

- **Archive** : `bronze/bdpm/CIS_CIP_Dispo_Spec.txt/2026-10-24/20261024T194201Z__43b7d2f3cfe6.txt.gz`, sha256 `43b7d2f3cfe699fffded55893472d9fa17fd77964c5e3a31d4017160b8d35ed6` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/disponibilite.toml` v0, documentation BDPM §3.10.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

703 lignes non vides, 703 bien formées (8 colonnes, cp1252, CRLF) ; **aucune anomalie bloquante**.

| règle           | bloquante | nombre | exemples (cinq au plus : ligne, colonne, valeur brute)                                                                                                                                                                                                                                                                                                                                                                                                                              |
|-----------------|-----------|--------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ligne_dupliquee | non       | 5      | l. 308 : `identique à la ligne 306 : 63003440⇥⇥2⇥Tension d'approvisionnement⇥27/11/2025⇥1…` ; l. 309 : `identique à la ligne 307 : 67954061⇥⇥2⇥Tension d'approvisionnement⇥27/11/2025⇥1…` ; l. 311 : `identique à la ligne 310 : 66415335⇥⇥2⇥Tension d'approvisionnement⇥27/11/2025⇥1…` ; l. 312 : `identique à la ligne 305 : 67122698⇥⇥2⇥Tension d'approvisionnement⇥27/11/2025⇥1…` ; l. 314 : `identique à la ligne 313 : 65135519⇥⇥2⇥Tension d'approvisionnement⇥27/11/2025⇥1…` |

## Clé

`code_cis + code_cip13 + lien_ansm`, déclarée non unique (L'entité réelle est la fiche ANSM, qui couvre plusieurs CIS et parfois plusieurs présentations ; aucune combinaison de colonnes n'est unique et 5 lignes entières sont en doublon le 24/10 (ligne_dupliquee). Le Lot 1 raisonne par fiche et compare ligne à ligne.) : 697 valeurs distinctes pour 703 lignes, 6 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne                   | type        | obligatoire | vides        | distinctes | minimum    | maximum    |
|---|---------------------------|-------------|-------------|--------------|------------|------------|------------|
| 1 | code_cis                  | code        | oui         | 0 (0,0 %)    | 679        | —          | —          |
| 2 | code_cip13                | code        | non         | 667 (94,9 %) | 36         | —          | —          |
| 3 | code_statut               | enumeration | oui         | 0 (0,0 %)    | 4          | —          | —          |
| 4 | libelle_statut            | enumeration | oui         | 0 (0,0 %)    | 4          | —          | —          |
| 5 | date_debut                | date        | oui         | 0 (0,0 %)    | 220        | 17/11/2011 | 01/07/2027 |
| 6 | date_mise_a_jour          | date        | oui         | 0 (0,0 %)    | 164        | 19/05/2021 | 21/10/2026 |
| 7 | date_remise_a_disposition | date        | non         | 584 (83,1 %) | 64         | 06/10/2025 | 15/10/2026 |
| 8 | lien_ansm                 | url         | oui         | 0 (0,0 %)    | 290        | —          | —          |

### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)

**code_statut** (4 valeurs, 0 vides)

| valeur | nombre | part des non vides |
|--------|--------|--------------------|
| 2      | 499    | 71,0 %             |
| 4      | 119    | 16,9 %             |
| 1      | 61     | 8,7 %              |
| 3      | 24     | 3,4 %              |

**libelle_statut** (4 valeurs, 0 vides)

| valeur                      | nombre | part des non vides |
|-----------------------------|--------|--------------------|
| Tension d'approvisionnement | 499    | 71,0 %             |
| Remise à disposition        | 119    | 16,9 %             |
| Rupture de stock            | 61     | 8,7 %              |
| Arrêt de commercialisation  | 24     | 3,4 %              |

## Ordre des dates

Lignes où les deux dates se lisent, et ordre observé.

| première         | seconde                   | comparables | première après | égales | première avant |
|------------------|---------------------------|-------------|----------------|--------|----------------|
| date_debut       | date_mise_a_jour          | 703         | 47             | 69     | 587            |
| date_debut       | date_remise_a_disposition | 119         | 0              | 119    | 0              |
| date_mise_a_jour | date_remise_a_disposition | 119         | 54             | 64     | 1              |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne    | cible                         | archive cible                                                                   | lignes             | valeurs distinctes | absentes                                         |
|------------|-------------------------------|---------------------------------------------------------------------------------|--------------------|--------------------|--------------------------------------------------|
| code_cis   | bdpm.specialites.code_cis     | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz`     | 680 / 703 (96,7 %) | 656 / 679 (96,6 %) | 68705771, 60245890, 60120488, 60354021, 64799798 |
| code_cip13 | bdpm.presentations.code_cip13 | `bronze/bdpm/CIS_CIP_bdpm.txt/2026-10-24/20261024T231712Z__a6da566e8036.txt.gz` | 35 / 36 (97,2 %)   | 35 / 36 (97,2 %)   | 3400957382070                                    |
| code_cis   | bdpm.mitm.code_cis            | `bronze/bdpm/CIS_MITM.txt/2026-10-24/20261024T194203Z__300f24c39e84.txt.gz`     | 592 / 703 (84,2 %) | 569 / 679 (83,8 %) | 61717034, 61402622, 61615894, 66018611, 68705771 |
