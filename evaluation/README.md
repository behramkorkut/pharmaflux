# Jeu de questions de référence

Le PRD (annexe B) demande que l'assistant du Lot 3 soit mesuré sur des
questions dont la réponse attendue est **calculée depuis les données à une
date donnée**, pour que l'évaluation se rejoue à l'identique. Ce dossier
tient ce jeu ; `questions-reference-v0.toml` en est la première version :
quarante questions, cinq par catégorie, sur l'archive BDPM du 24/10/2026.

| catégorie | ce que l'on attend | source v0 |
|---|---|---|
| `disponibilite` | statut, dates, fiche ANSM ; « aucun signalement » quand il n'y a rien | `CIS_CIP_Dispo_Spec.txt` |
| `alternatives` | groupe générique, génériques, présentations commercialisées | `CIS_GENER_bdpm.txt`, `CIS_CIP_bdpm.txt` |
| `remboursement` | taux, prix, honoraires, agrément, tels qu'écrits (`65%`, `30 %`) | `CIS_CIP_bdpm.txt` |
| `avis_has` | SMR, ASMR, dossier, date, lien vers l'avis | `CIS_HAS_SMR_bdpm.txt`, `CIS_HAS_ASMR_bdpm.txt`, `HAS_LiensPageCT_bdpm.txt` |
| `historique` | une date portée par le fichier (début de rupture, AMM, commercialisation, remise à disposition) | fichiers ci-dessus |
| `depense` | une valeur Open Medic : **pas encore calculable** (`calculable_au = "lot4"`) | Lot 4 |
| `hors_perimetre` | abstention et orientation | — |
| `medical` | refus et renvoi vers un professionnel | — |

Deux questions visent un CIS **absent de `CIS_bdpm.txt`** (voir
`docs/donnees/README.md`) : l'attendu est une abstention motivée. Les
questions Historique évitent les dates impossibles du fichier des
présentations (1910-1949, 2924) et les débuts postérieurs à la mise à
jour, **sauf une, voulue** (`historique-005`, arrêt annoncé pour le
01/07/2027) : la réponse doit dire « annoncé », pas « arrêté depuis ».
Les médicaments sont réels et pris dans l'archive ; aucune question ne
vise un patient.

## Format

```toml
[[questions]]
id = "disponibilite-001"            # categorie-NNN, stable
categorie = "disponibilite"
question = "LARIAM 250 mg, comprimé sécable est-il en rupture de stock ?"
comportement = "reponse"            # reponse | abstention | refus_medical
prudence = "…"                      # facultatif : la nuance que la réponse porte

[questions.attendu]                 # ce que `questions verifier` rejoue
date_reference = 2026-10-24
fichier = "bdpm.disponibilite"      # identifiant du contrat de schéma
archive = "bronze/bdpm/CIS_CIP_Dispo_Spec.txt/2026-10-24/20261024T194201Z__43b7d2f3cfe6.txt.gz"
sha256 = "43b7d2f3…"                # des octets bruts de l'archive
cle = { code_cis = "65999556" }     # les lignes où ces colonnes valent cela
colonnes = ["libelle_statut", "date_debut"]

[[questions.attendu.valeurs]]       # les lignes attendues, dans l'ordre du fichier
libelle_statut = "Rupture de stock"
date_debut = "25/06/2026"
```

- Une **réponse** a un `attendu`, ou `calculable_au = "lotN"` tant que la
  source manque. `valeurs = []` dit qu'aucune ligne ne doit exister
  (« aucun signalement », « aucun générique »).
- Une **abstention** a un `motif`, une `orientation` facultative, et
  éventuellement un `attendu` sans aucune ligne qui dit ce qui est absent.
- Un **refus médical** a un `motif` et une `orientation`, jamais d'attendu.
- Les valeurs sont celles du fichier, **brutes** : le jeu constate, il ne
  corrige pas (PRD §6.2). Toute clé inconnue ou incohérente est refusée
  (`pharmaflux.evaluation.questions`).

## Rejouer

```bash
uv run pharmaflux questions verifier [--racine ~/pharmaflux-data] [--questions evaluation/questions-reference-v0.toml]
```

Le chemin par défaut de `--questions` est relatif au dossier courant :
lancer la commande depuis la racine du dépôt, ou donner le chemin complet
du jeu (vérification de clôture sur une copie rapatriée, par exemple).

Pour chaque attendu : l'archive citée est relue sous la racine (jamais
écrite), son sha256 comparé, le fichier vérifié contre son contrat (une
anomalie bloquante arrête là), puis les lignes qui portent la clé sont
projetées sur les colonnes lues et comparées aux lignes attendues. Verdicts :
`conforme`, `écart`, `archive introuvable`, `sha256 différent`, `archive non
conforme au contrat`, `non calculable` (lot à venir), `sans attendu`. Code
de sortie 1 au moindre échec. Sur l'archive du 24/10 rapatriée sur le Mac :
25 conformes, 5 non calculables, 10 sans attendu.

Le jeu vit à la racine du dépôt, hors du paquet Python : c'est un fichier
de données du projet, que la CI du Lot 3 rejouera, pas une ressource de la
bibliothèque. Les tests (`tests/test_questions.py`) vérifient sa forme et
sa cohérence avec les contrats sans archive, et rejouent un petit jeu dédié
(`tests/fixtures/evaluation/questions-essai.toml`) sur les fixtures.

## Versions

Une question ne change pas de sens sous le même identifiant : une réponse
qui bouge avec les données (nouvelle archive de référence) ou une question
reformulée donne une **nouvelle version du jeu** (`v1`, nouveau fichier),
et `v0` reste rejouable sur l'archive du 24/10/2026. L'objectif du PRD est
cent questions au Lot 3.
