# Profil — `CIS_MITM.txt` (bdpm.mitm)

Médicaments d'intérêt thérapeutique majeur (MITM) publiés par l'ANSM : un drapeau par CIS, sans historique.

- **Archive** : `bronze/bdpm/CIS_MITM.txt/2026-10-24/20261024T194203Z__300f24c39e84.txt.gz`, sha256 `300f24c39e84466c617eedce9edfd491870259fd5abd2092b3f8296a3b6245fa` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/mitm.toml` v0, documentation BDPM §3.11.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

7 855 lignes non vides, 7 855 bien formées (7 colonnes, cp1252, CRLF) ; **aucune anomalie bloquante**.

Aucune anomalie.

## Clé

`code_cis`, déclarée unique : 7 855 valeurs distinctes pour 7 855 lignes, 0 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne          | type  | obligatoire | vides      | distinctes | minimum    | maximum    |
|---|------------------|-------|-------------|------------|------------|------------|------------|
| 1 | code_cis         | code  | oui         | 0 (0,0 %)  | 7 855      | —          | —          |
| 2 | code_atc         | code  | oui         | 0 (0,0 %)  | 1 258      | —          | —          |
| 3 | denomination     | texte | oui         | 0 (0,0 %)  | 7 855      | —          | —          |
| 4 | titulaire        | texte | oui         | 0 (0,0 %)  | 385        | —          | —          |
| 5 | exploitant       | texte | non         | 20 (0,3 %) | 250        | —          | —          |
| 6 | date_publication | date  | oui         | 0 (0,0 %)  | 3          | 18/12/2024 | 05/10/2026 |
| 7 | lien_bdpm        | url   | oui         | 0 (0,0 %)  | 7 855      | —          | —          |

### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)

**date_publication** (3 valeurs, 0 vides)

| valeur     | nombre | part des non vides |
|------------|--------|--------------------|
| 18/12/2024 | 7 459  | 95,0 %             |
| 05/10/2026 | 345    | 4,4 %              |
| 13/03/2026 | 51     | 0,6 %              |

## Liens vers d'autres fichiers

Taux de correspondance, mesurés sur la dernière archive du fichier cible ; jamais une anomalie.

| colonne  | cible                     | archive cible                                                               | lignes                  | valeurs distinctes      | absentes |
|----------|---------------------------|-----------------------------------------------------------------------------|-------------------------|-------------------------|----------|
| code_cis | bdpm.specialites.code_cis | `bronze/bdpm/CIS_bdpm.txt/2026-10-24/20261024T194143Z__332b95926f76.txt.gz` | 7 855 / 7 855 (100,0 %) | 7 855 / 7 855 (100,0 %) | —        |
