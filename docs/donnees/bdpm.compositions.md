# Profil — `CIS_COMPO_bdpm.txt` (bdpm.compositions)

Composition qualitative et quantitative en substances actives et fractions thérapeutiques.

- **Archive** : `bronze/bdpm/CIS_COMPO_bdpm.txt/2026-10-24/20261024T194148Z__90a6e8ee286b.txt.gz`, sha256 `90a6e8ee286b6245c3938dd417ac75d1135a61b15ba50cfad70ee6b3bd181b7a` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/compositions.toml` v0, documentation BDPM §3.3.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

32 439 lignes non vides, 32 439 bien formées (8 colonnes, cp1252, CRLF) ; **aucune anomalie bloquante**.

| règle           | bloquante | nombre | exemples (cinq au plus : ligne, colonne, valeur brute)                                                                                                                                                                                                    |
|-----------------|-----------|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| espace_parasite | non       | 1 309  | l. 89, denomination_substance : `GOLIMUMAB ` ; l. 102, denomination_substance : `ALBUMINE HUMAINE ` ; l. 130, denomination_substance : `DARATUMUMAB ` ; l. 141, denomination_substance : `TOCILIZUMAB ` ; l. 143, denomination_substance : `SOMAPACITAN ` |

## Clé

`code_cis + designation_element + code_substance + nature_composant + numero_liaison`, déclarée unique : 32 439 valeurs distinctes pour 32 439 lignes, 0 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne                | type        | obligatoire | vides         | distinctes | minimum | maximum |
|---|------------------------|-------------|-------------|---------------|------------|---------|---------|
| 1 | code_cis               | code        | oui         | 0 (0,0 %)     | 15 881     | —       | —       |
| 2 | designation_element    | texte       | oui         | 0 (0,0 %)     | 264        | —       | —       |
| 3 | code_substance         | code        | oui         | 0 (0,0 %)     | 3 907      | —       | —       |
| 4 | denomination_substance | texte       | oui         | 0 (0,0 %)     | 4 490      | —       | —       |
| 5 | dosage                 | texte       | non         | 2 844 (8,8 %) | 3 942      | —       | —       |
| 6 | reference_dosage       | texte       | non         | 2 844 (8,8 %) | 900        | —       | —       |
| 7 | nature_composant       | enumeration | oui         | 0 (0,0 %)     | 2          | —       | —       |
| 8 | numero_liaison         | entier      | oui         | 0 (0,0 %)     | 88         | 1       | 205     |

### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)

**nature_composant** (2 valeurs, 0 vides)

| valeur | nombre | part des non vides |
|--------|--------|--------------------|
| SA     | 26 915 | 83,0 %             |
| FT     | 5 524  | 17,0 %             |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne  | cible                     | archive cible                                                               | lignes                    | valeurs distinctes        | absentes |
|----------|---------------------------|-----------------------------------------------------------------------------|---------------------------|---------------------------|----------|
| code_cis | bdpm.specialites.code_cis | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz` | 32 439 / 32 439 (100,0 %) | 15 881 / 15 881 (100,0 %) | —        |
