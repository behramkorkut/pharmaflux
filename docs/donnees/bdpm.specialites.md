# Profil — `CIS_bdpm.txt` (bdpm.specialites)

Spécialités : médicaments commercialisés ou en arrêt de commercialisation depuis moins de deux ans.

- **Archive** : `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz`, sha256 `332b95926f76f1a2ab3d70cdf64205397fc13e74b7cc9afad9b625fbb6961640` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/specialites.toml` v0, documentation BDPM §3.1.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

15 883 lignes non vides, 15 883 bien formées (12 colonnes, cp1252, CRLF) ; **aucune anomalie bloquante**.

| règle           | bloquante | nombre | exemples (cinq au plus : ligne, colonne, valeur brute)                                                                                                                                                                                                     |
|-----------------|-----------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| espace_parasite | non       | 17 016 | l. 1, titulaires : ` PHARMA DEVELOPPEMENT` ; l. 2, titulaires : ` PHARMA DEVELOPPEMENT` ; l. 3, forme_pharmaceutique : ` comprimé et solution(s) et granules et poudre et pommade` ; l. 3, titulaires : ` BOIRON` ; l. 4, titulaires : ` ARROW GENERIQUES` |
| code_illisible  | non       | 1      | l. 15682, numero_autorisation_europeenne : `EU/1/17/1235/`                                                                                                                                                                                                 |

## Clé

`code_cis`, déclarée unique : 15 883 valeurs distinctes pour 15 883 lignes, 0 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| #  | colonne                        | type        | obligatoire | vides           | distinctes | minimum    | maximum    |
|----|--------------------------------|-------------|-------------|-----------------|------------|------------|------------|
| 1  | code_cis                       | code        | oui         | 0 (0,0 %)       | 15 883     | —          | —          |
| 2  | denomination                   | texte       | oui         | 0 (0,0 %)       | 15 646     | —          | —          |
| 3  | forme_pharmaceutique           | texte       | oui         | 0 (0,0 %)       | 369        | —          | —          |
| 4  | voies_administration           | liste       | oui         | 0 (0,0 %)       | 156        | —          | —          |
| 5  | statut_amm                     | enumeration | oui         | 0 (0,0 %)       | 5          | —          | —          |
| 6  | type_procedure_amm             | enumeration | oui         | 0 (0,0 %)       | 8          | —          | —          |
| 7  | etat_commercialisation         | enumeration | oui         | 0 (0,0 %)       | 2          | —          | —          |
| 8  | date_amm                       | date        | oui         | 0 (0,0 %)       | 4 351      | 11/03/1974 | 28/07/2026 |
| 9  | statut_bdm                     | enumeration | non         | 13 652 (86,0 %) | 2          | —          | —          |
| 10 | numero_autorisation_europeenne | code        | non         | 13 510 (85,1 %) | 1 136      | —          | —          |
| 11 | titulaires                     | liste       | oui         | 0 (0,0 %)       | 666        | —          | —          |
| 12 | surveillance_renforcee         | booleen     | oui         | 0 (0,0 %)       | 2          | —          | —          |

### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)

**statut_amm** (5 valeurs, 0 vides)

| valeur                 | nombre | part des non vides |
|------------------------|--------|--------------------|
| Autorisation active    | 14 940 | 94,1 %             |
| Autorisation abrogée   | 724    | 4,6 %              |
| Autorisation archivée  | 205    | 1,3 %              |
| Autorisation retirée   | 10     | 0,1 %              |
| Autorisation suspendue | 4      | 0,0 %              |

**type_procedure_amm** (8 valeurs, 0 vides)

| valeur                               | nombre | part des non vides |
|--------------------------------------|--------|--------------------|
| Procédure nationale                  | 7 013  | 44,2 %             |
| Procédure décentralisée              | 3 377  | 21,3 %             |
| Procédure centralisée                | 2 373  | 14,9 %             |
| Procédure de reconnaissance mutuelle | 1 505  | 9,5 %              |
| Enreg homéo (Proc. Nat.)             | 1 316  | 8,3 %              |
| Autorisation d'importation parallèle | 239    | 1,5 %              |
| Enreg phyto (Proc. Nat.)             | 55     | 0,3 %              |
| Enreg phyto (Proc. Dec.)             | 5      | 0,0 %              |

**etat_commercialisation** (2 valeurs, 0 vides)

| valeur             | nombre | part des non vides |
|--------------------|--------|--------------------|
| Commercialisée     | 13 650 | 85,9 %             |
| Non commercialisée | 2 233  | 14,1 %             |

**statut_bdm** (2 valeurs, 13 652 vides)

| valeur                | nombre | part des non vides |
|-----------------------|--------|--------------------|
| Warning disponibilité | 2 214  | 99,2 %             |
| Alerte                | 17     | 0,8 %              |

**surveillance_renforcee** (2 valeurs, 0 vides)

| valeur | nombre | part des non vides |
|--------|--------|--------------------|
| Non    | 15 375 | 96,8 %             |
| Oui    | 508    | 3,2 %              |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne  | cible                       | archive cible                                                                   | lignes                   | valeurs distinctes       | absentes                                         |
|----------|-----------------------------|---------------------------------------------------------------------------------|--------------------------|--------------------------|--------------------------------------------------|
| code_cis | bdpm.presentations.code_cis | `bronze/bdpm/CIS_CIP_bdpm.txt/2026-10-24/20261024T231712Z__a6da566e8036.txt.gz` | 14 620 / 15 883 (92,0 %) | 14 620 / 15 883 (92,0 %) | 69103878, 60386663, 60538772, 65698396, 63075735 |
