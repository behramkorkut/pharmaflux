# Profil — `CIS_HAS_ASMR_bdpm.txt` (bdpm.asmr)

Avis d'amélioration du service médical rendu (ASMR) de la HAS depuis 2002.

- **Archive** : `bronze/bdpm/CIS_HAS_ASMR_bdpm.txt/2026-10-24/20261024T194153Z__f849554030c7.txt.gz`, sha256 `f849554030c7dafdaf9ccf604dcdb8393590302f7a28f869a71a3fd798ae0a69` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/asmr.toml` v0, documentation BDPM §3.5.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

10 117 lignes non vides, 10 117 bien formées (6 colonnes, cp1252, CRLF) ; **aucune anomalie bloquante**.

Aucune anomalie.

## Clé

`code_cis + code_dossier_has`, déclarée non unique (Un avis par indication : 307 couples (CIS, dossier) ont plusieurs lignes le 24/10, souvent avec des valeurs différentes. La ligne entière est unique ; le Lot 1 compare ligne à ligne.) : 9 805 valeurs distinctes pour 10 117 lignes, 312 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne          | type        | obligatoire | vides     | distinctes | minimum  | maximum  |
|---|------------------|-------------|-------------|-----------|------------|----------|----------|
| 1 | code_cis         | code        | oui         | 0 (0,0 %) | 6 287      | —        | —        |
| 2 | code_dossier_has | code        | oui         | 0 (0,0 %) | 6 019      | —        | —        |
| 3 | motif_evaluation | enumeration | oui         | 0 (0,0 %) | 11         | —        | —        |
| 4 | date_avis        | date        | oui         | 0 (0,0 %) | 592        | 20021218 | 20260916 |
| 5 | valeur_asmr      | enumeration | oui         | 0 (0,0 %) | 7          | —        | —        |
| 6 | libelle_asmr     | texte       | oui         | 0 (0,0 %) | 4 695      | —        | —        |

### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)

**motif_evaluation** (11 valeurs, 0 vides)

| valeur                                             | nombre | part des non vides |
|----------------------------------------------------|--------|--------------------|
| Inscription (CT)                                   | 6 804  | 67,3 %             |
| Extension d'indication                             | 2 045  | 20,2 %             |
| Réévaluation SMR et ASMR                           | 471    | 4,7 %              |
| Renouvellement d'inscription (CT)                  | 208    | 2,1 %              |
| Réévaluation SMR                                   | 135    | 1,3 %              |
| Réévaluation ASMR                                  | 133    | 1,3 %              |
| Réévaluation suite à résultats étude post-inscript | 120    | 1,2 %              |
| Modification des conditions d'inscription (CT)     | 101    | 1,0 %              |
| Nouvel examen suite au dépôt de nouvelles données  | 53     | 0,5 %              |
| Réévaluation suite saisine Ministères (CT)         | 40     | 0,4 %              |
| Autre demande                                      | 7      | 0,1 %              |

**valeur_asmr** (7 valeurs, 0 vides)

| valeur                                | nombre | part des non vides |
|---------------------------------------|--------|--------------------|
| V                                     | 7 767  | 76,8 %             |
| IV                                    | 1 277  | 12,6 %             |
| III                                   | 607    | 6,0 %              |
| II                                    | 208    | 2,1 %              |
| Commentaires sans chiffrage de l'ASMR | 160    | 1,6 %              |
| I                                     | 85     | 0,8 %              |
| V dans l'attente de données           | 13     | 0,1 %              |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne          | cible                          | archive cible                                                                           | lignes                  | valeurs distinctes     | absentes                                         |
|------------------|--------------------------------|-----------------------------------------------------------------------------------------|-------------------------|------------------------|--------------------------------------------------|
| code_cis         | bdpm.specialites.code_cis      | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz`             | 7 945 / 10 117 (78,5 %) | 4 625 / 6 287 (73,6 %) | 67026956, 69487051, 65691213, 67388752, 69625011 |
| code_dossier_has | bdpm.liens_ct.code_dossier_has | `bronze/bdpm/HAS_LiensPageCT_bdpm.txt/2026-10-24/20261024T194155Z__2f01ff1e13f8.txt.gz` | 8 075 / 10 117 (79,8 %) | 4 667 / 6 019 (77,5 %) | CT-21978, CT-21877, CT-21747, CT-21719, CT-21716 |
