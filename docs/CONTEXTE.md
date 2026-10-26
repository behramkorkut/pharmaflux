# Contexte technique — point d'entrée

Ce fichier dit ce qu'il faut savoir avant de toucher au code. Il est tenu
à jour à chaque mission ; les décisions durables sont dans `docs/adr/`, le
fil des travaux dans `docs/journal.md`.

## Ce que fait le projet

Transformer des publications d'état (fichiers BDPM, bases Open Medic) en
un flux d'événements daté et rejouable. Tout repose sur une **archive
brute immuable** (couche bronze) : chaque fichier reçu est conservé à
l'octet près, horodaté, avec son empreinte, et n'est jamais réécrit.

## Règles qui ne se discutent pas

- **L'archive est irremplaçable.** La BDPM n'a pas d'historique : un jour
  sans collecte est un jour perdu pour toujours. On ne supprime jamais une
  archive, on ne la réécrit jamais, on ne la « nettoie » jamais. Une copie
  hors du serveur de collecte est tenue à jour chaque semaine
  (`infra/planification/rapatrier.sh`, rsync sans `--delete`).
- **Octets bruts.** Le contenu archivé est exactement ce que le serveur a
  envoyé, compressé (gzip), jamais converti ni réencodé : la licence BDPM
  interdit l'altération, et le rejeu du Lot 1 en dépend.
- **Aucune donnée dans git.** `data/` et `*.gz` sont ignorés ; l'archive
  vit sous `PHARMAFLUX_DATA` (défaut `~/pharmaflux-data`). Aucune donnée
  personnelle, nulle part.
- **Les tests n'appellent jamais le réseau.** Les sources sont un service
  public, pas un banc d'essai : un téléchargement réel sert à constituer
  des fixtures (`tests/fixtures/`), puis on travaille dessus.
- **Temps en UTC**, ISO 8601, partout dans l'archive et le manifeste. Les
  dates affichées par les sites sources sont des dates locales (Paris), au
  jour près : elles sont conservées telles quelles, dans un champ à part.
- **Français** dans les docs, les commits, les commentaires et les
  identifiants de code (sans accents dans le code).

## Ce que l'on sait des sources (mesuré le 24/10/2026)

Détail et chiffres : `docs/rapports/mission-00/points-a-trancher.md`.

- **BDPM** : onze fichiers texte tabulés sans en-tête, 28,7 Mo bruts par
  passage complet (3,7 Mo gzip). Le serveur n'envoie **ni `Last-Modified`,
  ni `ETag`, ni `Content-Length`** : aucune requête conditionnelle n'est
  possible, chaque passage télécharge tout. La page de téléchargement
  affiche une date de mise à jour et une taille par fichier (sauf
  `CIS_InfoImportantes.txt`, généré à la demande et non trié).
- **Encodages hétérogènes** : la plupart des fichiers sont en
  Windows-1252 avec fins de ligne CRLF, mais `CIS_CIP_bdpm.txt` et
  `CIS_InfoImportantes.txt` sont en UTF-8 avec LF. Les en-têtes HTTP
  n'annoncent aucun charset. Les contrats de schéma (mission 01) portent
  l'encodage et la fin de ligne par fichier.
- **Open Medic (data.gouv.fr)** : les dates `last_modified` par ressource
  sont celles du robot de data.gouv, pas de la Cnam ; les dates utiles
  sont `created_at` de la ressource et `last_modified` du jeu.

## Contrats de schéma et lecture du bronze (mission 01)

- **Un contrat TOML par fichier** (`src/pharmaflux/contrats/bdpm/<nom>.toml`,
  version `v0`) : encodage, fin de ligne, colonnes typées (neuf types,
  ADR 0002), clé déclarée unique ou non avec sa raison, liens de mesure
  vers d'autres fichiers, documentation PDF et archive de référence avec
  leurs sha256. Le chargeur est strict : toute clé inconnue est refusée.
  À partir de la fusion de la mission 01, **tout changement de contenu
  d'un contrat, lien compris, passe par une nouvelle version**.
- **On constate, on ne corrige pas** (PRD §6.2). `pharmaflux profil`
  vérifie une archive contre son contrat et signale les anomalies : quatre
  règles bloquantes (encodage, fin de ligne, nombre de colonnes, clé
  déclarée unique non unique) et quinze non bloquantes (valeur inconnue,
  date hors plage, décimal illisible, espace parasite…). Rien n'est
  jamais réécrit : les prix à virgule des milliers, les dates de 1949 et
  les espaces de fin restent tels quels dans le bronze, et c'est au Lot 1
  de normaliser. Ce que l'on sait des fichiers est dans `docs/donnees/`.
- **Le bronze se lit par `pharmaflux.bronze`** (`lister`, `derniere`,
  `lire_archive`), jamais par le système de fichiers directement : les noms
  qui commencent par un point (temporaires, `.rsync-partiel/`) sont
  ignorés, les archives rendues sont les octets bruts décompressés.
- **Jeu de questions de référence** (`evaluation/`, PRD annexe B) :
  quarante questions dont la réponse attendue est lue dans une archive
  précise par la clé et les colonnes du contrat ; `pharmaflux questions
  verifier` la recalcule. Les lignes attendues sont brutes elles aussi.

## Pièges connus

- Deux sources changent d'octets sans changer de fond (ordre des lignes
  d'InfoImportantes, compteurs du JSON data.gouv, `nonce` de la page
  HTML) : la décision « nouveau / inchangé » se prend sur une **empreinte
  de comparaison** déclarée par entrée du catalogue, alors que l'archive
  et le `sha256` du manifeste restent ceux des octets bruts.
- La page de téléchargement porte aussi un lien vers la documentation PDF
  du format (v5 au 24/10/2026) : il entre dans l'empreinte de la page (un
  changement de version sera vu) mais pas dans le contrôle « lien nouveau »,
  réservé aux fichiers `.txt`.
- Un lien que la page n'affiche plus (`lien_absent`) est quand même
  téléchargé et archivé : la ligne de manifeste est en `erreur` pour alerter,
  mais l'archive ne perd rien.
- `CIS_InfoImportantes.txt` : deux téléchargements à 76 min d'écart le
  24/10/2026 étaient identiques à l'octet près (même ordre des lignes) ;
  seul le nom dans `Content-Disposition` change. L'empreinte sur lignes
  triées reste en place, par prudence et à coût nul.
- Le `User-Agent` identifie le projet :
  `pharmaflux/<version> (+https://github.com/behramkorkut/pharmaflux)`.
  Téléchargements en série, pause de 2 s, une fois par heure à `:17`.

## Où sont les choses

| Quoi | Où |
|---|---|
| Spécifications (PRD) | `01_Specifications/` |
| Code | `src/pharmaflux/` : `cli.py`, `bronze.py` (lecture de l'archive), `tomlstrict.py` ; `collecte/` : `catalogue.py` (14 entrées), `page.py` (lecture de la page BDPM), `empreintes.py`, `telechargement.py`, `archive.py`, `manifeste.py`, `passage.py` (orchestration), `etat.py` ; `contrats/` : `modele.py`, `chargeur.py`, `verification.py`, `profil.py`, `rendu.py`, `bdpm/*.toml` ; `evaluation/` : `questions.py`, `verification.py` |
| Tests et fixtures | `tests/`, `tests/fixtures/` |
| Planification de la collecte (systemd, rapatriement) | `infra/planification/` |
| Décisions d'architecture | `docs/adr/` (gabarit : `0000-modele.md`) |
| Journal | `docs/journal.md` (ajout en fin de fichier) |
| Profil des sources | `docs/donnees/` (mission 01) |
| Jeu de questions de référence | `evaluation/` (PRD annexe B) |
| Circuit de travail, ordres, rapports, relectures | `docs/agents/`, `docs/missions/`, `docs/rapports/`, `docs/relectures/` |

## Outillage

Python 3.12 géré par `uv` (`.python-version`), `httpx`, `typer` ; `ruff`
(lint et format), `mypy --strict` sur `src/`, `pytest`. La CI
(`.github/workflows/ci.yml`) rejoue les mêmes commandes plus les tests des
garde-fous du circuit, en un seul job, sans appel réseau vers les sources.
