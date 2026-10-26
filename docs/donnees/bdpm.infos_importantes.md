# Profil — `CIS_InfoImportantes.txt` (bdpm.infos_importantes)

Informations importantes de sécurité en cours, générées à la demande.

- **Archive** : `bronze/bdpm/CIS_InfoImportantes.txt/2026-10-24/20261024T194206Z__a27b30e12c83.txt.gz`, sha256 `a27b30e12c837fd709906513fb0fe8e8c16bd008d3d0fab2fd0dea8de46a39ff` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/infos_importantes.toml` v0, documentation BDPM §3.9.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

10 905 lignes non vides, 10 905 bien formées (4 colonnes, utf-8, LF) ; **aucune anomalie bloquante**.

Aucune anomalie.

## Clé

`code_cis + date_debut + date_fin + texte_et_lien`, déclarée unique : 10 905 valeurs distinctes pour 10 905 lignes, 0 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne       | type | obligatoire | vides     | distinctes | minimum    | maximum    |
|---|---------------|------|-------------|-----------|------------|------------|------------|
| 1 | code_cis      | code | oui         | 0 (0,0 %) | 5 128      | —          | —          |
| 2 | date_debut    | date | oui         | 0 (0,0 %) | 346        | 2018-03-01 | 2026-09-25 |
| 3 | date_fin      | date | oui         | 0 (0,0 %) | 230        | 2026-10-31 | 2028-10-27 |
| 4 | texte_et_lien | code | oui         | 0 (0,0 %) | 403        | —          | —          |

## Ordre des dates

Lignes où les deux dates se lisent, et ordre observé.

| première   | seconde  | comparables | première après | égales | première avant |
|------------|----------|-------------|----------------|--------|----------------|
| date_debut | date_fin | 10 905      | 0              | 0      | 10 905         |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne  | cible                     | archive cible                                                               | lignes                  | valeurs distinctes     | absentes                                         |
|----------|---------------------------|-----------------------------------------------------------------------------|-------------------------|------------------------|--------------------------------------------------|
| code_cis | bdpm.specialites.code_cis | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz` | 8 626 / 10 905 (79,1 %) | 3 990 / 5 128 (77,8 %) | 63729455, 60076821, 60092341, 60113045, 60129665 |
