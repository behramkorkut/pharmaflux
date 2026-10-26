# Profil — `HAS_LiensPageCT_bdpm.txt` (bdpm.liens_ct)

Liens vers les avis complets de la Commission de la transparence de la HAS.

- **Archive** : `bronze/bdpm/HAS_LiensPageCT_bdpm.txt/2026-10-24/20261024T194155Z__2f01ff1e13f8.txt.gz`, sha256 `2f01ff1e13f8431434d545d1c567368276223b7a5d9c5612fc423f4353c54a2b` (archive de référence du contrat).
- **Contrat** : `src/pharmaflux/contrats/bdpm/liens_ct.toml` v0, documentation BDPM §3.6.
- **Produit** par `pharmaflux profil --markdown` le 2026-10-26 13:32Z.
- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.

## Conformité au contrat

10 480 lignes non vides, 10 480 bien formées (2 colonnes, ascii, CRLF) ; **aucune anomalie bloquante**.

Aucune anomalie.

## Clé

`code_dossier_has + lien_avis`, déclarée unique : 10 480 valeurs distinctes pour 10 480 lignes, 0 ligne(s) au-delà de la première pour une même clé.

## Colonnes

| # | colonne          | type | obligatoire | vides     | distinctes | minimum | maximum |
|---|------------------|------|-------------|-----------|------------|---------|---------|
| 1 | code_dossier_has | code | oui         | 0 (0,0 %) | 10 465     | —       | —       |
| 2 | lien_avis        | url  | oui         | 0 (0,0 %) | 10 460     | —       | —       |
