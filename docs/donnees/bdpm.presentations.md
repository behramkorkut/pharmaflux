# Profil — `CIS_CIP_bdpm.txt` (bdpm.presentations)

Présentations (boîtes), prix et taux de remboursement des spécialités.

- **Archive** : `bronze/bdpm/CIS_CIP_bdpm.txt/2026-10-24/20261024T231712Z__a6da566e8036.txt.gz`, sha256 `a6da566e803671a14e403c19a6983c79ce284ecadf947742dafd66a5d72bb0b2` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/presentations.toml` v0, documentation BDPM §3.2.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

20 896 lignes non vides, 20 896 bien formées (13 colonnes, utf-8, LF) ; **aucune anomalie bloquante**.

| règle             | bloquante | nombre | exemples (cinq au plus : ligne, colonne, valeur brute)                                                                                                                                                                                                                                                     |
|-------------------|-----------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| decimal_illisible | non       | 995    | l. 50, prix_medicament : `1,466,29` ; l. 50, prix_public : `1,469,05` ; l. 78, prix_medicament : `7,518,58` ; l. 78, prix_public : `7,519,60` ; l. 125, prix_medicament : `3,982,28`                                                                                                                       |
| date_hors_plage   | non       | 52     | l. 73, date_declaration_commercialisation : `19/01/1949` ; l. 167, date_declaration_commercialisation : `19/01/1927` ; l. 514, date_declaration_commercialisation : `19/01/1947` ; l. 1302, date_declaration_commercialisation : `19/01/1925` ; l. 1634, date_declaration_commercialisation : `19/01/1936` |
| espace_parasite   | non       | 3      | l. 5037, libelle_presentation : ` 7 plaquette(s) PVC-Aluminium de 16 comprimé(s)` ; l. 13773, libelle_presentation : ` plaquette(s) aluminium PVC-Aluminium de 28 comprimés` ; l. 17355, libelle_presentation : ` 1 dispositif en plastique contenant 60 récipients unidoses (Aluminium/OPA/PVC)`          |

## Clé

`code_cip13`, déclarée unique : 20 896 valeurs distinctes pour 20 896 lignes, 0 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| #  | colonne                            | type        | obligatoire | vides           | distinctes | minimum    | maximum    |
|----|------------------------------------|-------------|-------------|-----------------|------------|------------|------------|
| 1  | code_cis                           | code        | oui         | 0 (0,0 %)       | 14 624     | —          | —          |
| 2  | code_cip7                          | code        | oui         | 0 (0,0 %)       | 20 896     | —          | —          |
| 3  | libelle_presentation               | texte       | oui         | 0 (0,0 %)       | 7 593      | —          | —          |
| 4  | statut_administratif               | enumeration | oui         | 0 (0,0 %)       | 2          | —          | —          |
| 5  | etat_commercialisation             | enumeration | oui         | 0 (0,0 %)       | 4          | —          | —          |
| 6  | date_declaration_commercialisation | date        | oui         | 0 (0,0 %)       | 5 638      | 19/01/1910 | 29/11/2924 |
| 7  | code_cip13                         | code        | oui         | 0 (0,0 %)       | 20 896     | —          | —          |
| 8  | agrement_collectivites             | enumeration | oui         | 0 (0,0 %)       | 2          | —          | —          |
| 9  | taux_remboursement                 | liste       | non         | 7 272 (34,8 %)  | 9          | —          | —          |
| 10 | prix_medicament                    | decimal     | non         | 7 272 (34,8 %)  | 2 570      | 0,66       | 999,20     |
| 11 | prix_public                        | decimal     | non         | 7 272 (34,8 %)  | 2 589      | 1,68       | 993,51     |
| 12 | honoraires_dispensation            | decimal     | non         | 7 272 (34,8 %)  | 2          | 1,02       | 2,76       |
| 13 | indications_remboursement          | texte       | non         | 20 098 (96,2 %) | 245        | —          | —          |

### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)

**statut_administratif** (2 valeurs, 0 vides)

| valeur               | nombre | part des non vides |
|----------------------|--------|--------------------|
| Présentation active  | 20 805 | 99,6 %             |
| Présentation abrogée | 91     | 0,4 %              |

**etat_commercialisation** (4 valeurs, 0 vides)

| valeur                                                             | nombre | part des non vides |
|--------------------------------------------------------------------|--------|--------------------|
| Déclaration de commercialisation                                   | 17 276 | 82,7 %             |
| Déclaration d'arrêt de commercialisation                           | 3 456  | 16,5 %             |
| Arrêt de commercialisation (le médicament n'a plus d'autorisation) | 161    | 0,8 %              |
| Déclaration de suspension de commercialisation                     | 3      | 0,0 %              |

**agrement_collectivites** (2 valeurs, 0 vides)

| valeur | nombre | part des non vides |
|--------|--------|--------------------|
| oui    | 15 005 | 71,8 %             |
| non    | 5 891  | 28,2 %             |

**taux_remboursement** (9 valeurs, 7 272 vides)

| valeur | nombre | part des non vides |
|--------|--------|--------------------|
| 65%    | 9 084  | 66,7 %             |
| 65 %   | 1 769  | 13,0 %             |
| 100%   | 872    | 6,4 %              |
| 30%    | 860    | 6,3 %              |
| 100 %  | 380    | 2,8 %              |
| 30 %   | 286    | 2,1 %              |
| 15%    | 259    | 1,9 %              |
| 15 %   | 110    | 0,8 %              |
| 35%    | 4      | 0,0 %              |

**honoraires_dispensation** (2 valeurs, 7 272 vides)

| valeur | nombre | part des non vides |
|--------|--------|--------------------|
| 1,02   | 11 823 | 86,8 %             |
| 2,76   | 1 801  | 13,2 %             |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne  | cible                     | archive cible                                                               | lignes                    | valeurs distinctes        | absentes                               |
|----------|---------------------------|-----------------------------------------------------------------------------|---------------------------|---------------------------|----------------------------------------|
| code_cis | bdpm.specialites.code_cis | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz` | 20 892 / 20 896 (100,0 %) | 14 620 / 14 624 (100,0 %) | 63278664, 64917175, 65999410, 69912584 |
