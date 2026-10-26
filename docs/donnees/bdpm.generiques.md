# Profil — `CIS_GENER_bdpm.txt` (bdpm.generiques)

Groupes génériques et les médicaments qui en font partie.

- **Archive** : `bronze/bdpm/CIS_GENER_bdpm.txt/2026-10-24/20261024T194157Z__04ea92fb3d2e.txt.gz`, sha256 `04ea92fb3d2e7682ed0720daea48ecf65f3459b4b0b61fe9160bb7cce82f152c` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/generiques.toml` v0, documentation BDPM §3.7.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

10 737 lignes non vides, 10 737 bien formées (5 colonnes, cp1252, CRLF) ; **aucune anomalie bloquante**.

Aucune anomalie.

## Clé

`identifiant_groupe + code_cis`, déclarée unique : 10 737 valeurs distinctes pour 10 737 lignes, 0 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne            | type        | obligatoire | vides     | distinctes | minimum | maximum |
|---|--------------------|-------------|-------------|-----------|------------|---------|---------|
| 1 | identifiant_groupe | code        | oui         | 0 (0,0 %) | 1 686      | —       | —       |
| 2 | libelle_groupe     | texte       | oui         | 0 (0,0 %) | 1 686      | —       | —       |
| 3 | code_cis           | code        | oui         | 0 (0,0 %) | 10 661     | —       | —       |
| 4 | type_generique     | enumeration | oui         | 0 (0,0 %) | 4          | —       | —       |
| 5 | numero_tri         | entier      | oui         | 0 (0,0 %) | 36         | 1       | 36      |

### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)

**type_generique** (4 valeurs, 0 vides)

| valeur | nombre | part des non vides |
|--------|--------|--------------------|
| 1      | 8 832  | 82,3 %             |
| 0      | 1 808  | 16,8 %             |
| 4      | 61     | 0,6 %              |
| 2      | 36     | 0,3 %              |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne  | cible                     | archive cible                                                               | lignes                  | valeurs distinctes      | absentes                                         |
|----------|---------------------------|-----------------------------------------------------------------------------|-------------------------|-------------------------|--------------------------------------------------|
| code_cis | bdpm.specialites.code_cis | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz` | 8 254 / 10 737 (76,9 %) | 8 191 / 10 661 (76,8 %) | 65383183, 67535309, 65025026, 69472373, 60089516 |
