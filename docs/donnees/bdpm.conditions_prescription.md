# Profil — `CIS_CPD_bdpm.txt` (bdpm.conditions_prescription)

Conditions de prescription et de délivrance associées à un médicament.

- **Archive** : `bronze/bdpm/CIS_CPD_bdpm.txt/2026-10-24/20261024T194159Z__e92ca48f83f5.txt.gz`, sha256 `e92ca48f83f54f6e2bca7248d3e8c24d7399402fd6b5b9058c41ad730529c237` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/conditions_prescription.toml` v0, documentation BDPM §3.8.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

28 532 lignes non vides, 28 532 bien formées (2 colonnes, cp1252, CRLF) ; **aucune anomalie bloquante**.

| règle           | bloquante | nombre | exemples (cinq au plus : ligne, colonne, valeur brute)                                                                                                                                                                                                                                                                         |
|-----------------|-----------|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| espace_parasite | non       | 3      | l. 28027, condition : `l'administration du 1 er cycle et de la 1 ère injection du 2 ème cycle doit êtr…` ; l. 28029, condition : `l'administration du 1 er cycle et de la 1 ère injection du 2 ème cycle doit êtr…` ; l. 28031, condition : `l'administration du 1 er cycle et de la 1 ère injection du 2 ème cycle doit êtr…` |
| ligne_vide      | non       | 3      | l. 28028 : `'\r'` ; l. 28030 : `'\r'` ; l. 28032 : `'\r'`                                                                                                                                                                                                                                                                      |

## Clé

`code_cis + condition`, déclarée unique : 28 532 valeurs distinctes pour 28 532 lignes, 0 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne   | type  | obligatoire | vides     | distinctes | minimum | maximum |
|---|-----------|-------|-------------|-----------|------------|---------|---------|
| 1 | code_cis  | code  | oui         | 0 (0,0 %) | 12 555     | —       | —       |
| 2 | condition | texte | oui         | 0 (0,0 %) | 164        | —       | —       |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne  | cible                     | archive cible                                                               | lignes                    | valeurs distinctes        | absentes |
|----------|---------------------------|-----------------------------------------------------------------------------|---------------------------|---------------------------|----------|
| code_cis | bdpm.specialites.code_cis | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz` | 28 532 / 28 532 (100,0 %) | 12 555 / 12 555 (100,0 %) | —        |
