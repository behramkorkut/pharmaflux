# Profil — `CIS_HAS_SMR_bdpm.txt` (bdpm.smr)

Avis de service médical rendu (SMR) de la HAS depuis 2002.

- **Archive** : `bronze/bdpm/CIS_HAS_SMR_bdpm.txt/2026-10-24/20261024T194150Z__c2215af6b207.txt.gz`, sha256 `c2215af6b20705bb8b8eb6f447ebb2a45000c40e5cd8d3f575149832c639ffdd` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/smr.toml` v0, documentation BDPM §3.4.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

15 547 lignes non vides, 15 547 bien formées (6 colonnes, cp1252, CRLF) ; **aucune anomalie bloquante**.

Aucune anomalie.

## Clé

`code_cis + code_dossier_has`, déclarée non unique (Un avis par indication : 2 488 couples (CIS, dossier) ont plusieurs lignes le 24/10, souvent avec des valeurs différentes. La ligne entière est unique ; le Lot 1 compare ligne à ligne.) : 12 777 valeurs distinctes pour 15 547 lignes, 2 770 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne          | type        | obligatoire | vides     | distinctes | minimum  | maximum  |
|---|------------------|-------------|-------------|-----------|------------|----------|----------|
| 1 | code_cis         | code        | oui         | 0 (0,0 %) | 9 144      | —        | —        |
| 2 | code_dossier_has | code        | oui         | 0 (0,0 %) | 7 574      | —        | —        |
| 3 | motif_evaluation | enumeration | oui         | 0 (0,0 %) | 12         | —        | —        |
| 4 | date_avis        | date        | oui         | 0 (0,0 %) | 592        | 20021218 | 20260916 |
| 5 | valeur_smr       | enumeration | oui         | 0 (0,0 %) | 9          | —        | —        |
| 6 | libelle_smr      | texte       | oui         | 0 (0,0 %) | 7 575      | —        | —        |

### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)

**motif_evaluation** (12 valeurs, 0 vides)

| valeur                                             | nombre | part des non vides |
|----------------------------------------------------|--------|--------------------|
| Inscription (CT)                                   | 6 778  | 43,6 %             |
| Renouvellement d'inscription (CT)                  | 4 879  | 31,4 %             |
| Extension d'indication                             | 1 627  | 10,5 %             |
| Réévaluation SMR                                   | 934    | 6,0 %              |
| Réévaluation SMR et ASMR                           | 595    | 3,8 %              |
| Réévaluation suite saisine Ministères (CT)         | 195    | 1,3 %              |
| Réévaluation suite à résultats étude post-inscript | 184    | 1,2 %              |
| Modification des conditions d'inscription (CT)     | 105    | 0,7 %              |
| Réévaluation ASMR                                  | 100    | 0,6 %              |
| Nouvel examen suite au dépôt de nouvelles données  | 69     | 0,4 %              |
| Extension d'indication non sollicitée              | 67     | 0,4 %              |
| Autre demande                                      | 14     | 0,1 %              |

**valeur_smr** (9 valeurs, 0 vides)

| valeur                 | nombre | part des non vides |
|------------------------|--------|--------------------|
| Important              | 9 634  | 62,0 %             |
| Insuffisant            | 2 838  | 18,3 %             |
| Modéré                 | 1 677  | 10,8 %             |
| Faible                 | 1 170  | 7,5 %              |
| Commentaires           | 99     | 0,6 %              |
| Non précisé            | 88     | 0,6 %              |
| Important conditionnel | 18     | 0,1 %              |
| Faible conditionnel    | 13     | 0,1 %              |
| Modéré conditionnel    | 10     | 0,1 %              |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne          | cible                          | archive cible                                                                           | lignes                   | valeurs distinctes     | absentes                                         |
|------------------|--------------------------------|-----------------------------------------------------------------------------------------|--------------------------|------------------------|--------------------------------------------------|
| code_cis         | bdpm.specialites.code_cis      | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz`             | 11 296 / 15 547 (72,7 %) | 6 206 / 9 144 (67,9 %) | 67026956, 69487051, 65691213, 67388752, 61587651 |
| code_dossier_has | bdpm.liens_ct.code_dossier_has | `bronze/bdpm/HAS_LiensPageCT_bdpm.txt/2026-10-24/20261024T194155Z__2f01ff1e13f8.txt.gz` | 13 933 / 15 547 (89,6 %) | 6 551 / 7 574 (86,5 %) | CT-21978, CT-21877, CT-21747, CT-21719, CT-21717 |
