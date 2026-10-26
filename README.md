# Pharmaflux

Plateforme temps réel de connaissance du médicament pour l'assurance
santé, construite sur des **données publiques réelles** : la Base de
données publique des médicaments (BDPM), Open Medic (Cnam) et les avis de
la Commission de la transparence (HAS).

Ces sources publient un **état**, jamais d'événement, et n'en gardent pas
l'historique : chaque mise à jour écrase la précédente. Pharmaflux les
archive, détecte ce qui change, publie des événements datés et rejouables,
et les met à la disposition d'un assistant qui cite ses sources et
s'abstient quand il ne sait pas.

Projet portfolio de Behram Korkut. Le cadrage complet est dans
[`01_Specifications/`](01_Specifications/PRD_Plateforme_Medicaments_v0.3.md)
et le point d'entrée technique dans [`docs/CONTEXTE.md`](docs/CONTEXTE.md).

## État

**Mission 00 fusionnée** : socle du dépôt et archivage horaire des fichiers
BDPM, en production sur un VPS depuis le 24/10/2026. L'archive brute est
la seule brique qui ne se rattrape pas : elle a démarré avant tout le reste.

**Mission 01 fusionnée** : contrats de schéma des onze fichiers BDPM,
profil des archives (`docs/donnees/`), décisions d'architecture
(`docs/adr/`) et jeu de questions de référence (`evaluation/`).

**Mission 02 en cours** : du bronze aux événements. Chaque archive est
normalisée selon son contrat (ADR 0005), comparée à la dernière retenue, et
chaque changement devient un événement JSON rejouable à l'identique
(`creee`, `modifiee`, `supprimee`, ADR 0006), avec un garde-fou qui écarte
une réponse vide ou tronquée au lieu d'en faire des milliers de
suppressions.

| Lot | Contenu | État |
|---|---|---|
| 0 | archivage des sources, profilage, décisions d'architecture | en cours |
| 1 | collecte, détection des changements, flux d'événements (Redpanda) | à venir |
| 2 | lakehouse Iceberg + DuckDB, historique, voyage dans le temps | à venir |
| 3 | assistant gouverné (sources citées, abstention) | à venir |
| 4 | volet assurance : dépense exposée aux ruptures (Open Medic) | à venir |
| 5 | observabilité, objectifs de service, incidents provoqués | à venir |

## Lancer

Prérequis : [`uv`](https://docs.astral.sh/uv/). Python 3.12 est installé
par `uv` dans le projet.

```bash
uv sync
uv run pharmaflux --help
```

```bash
uv run pharmaflux catalogue          # les quatorze entrées collectées
uv run pharmaflux collecte           # un passage : télécharge, compare, archive, consigne
uv run pharmaflux etat               # dernière archive, dernier changement, erreurs, 24 h
uv run pharmaflux profil             # chaque archive contre son contrat : anomalies, clé, colonnes, liens
uv run pharmaflux questions verifier # le jeu de questions de référence rejoué sur l'archive
uv run pharmaflux evenements         # du bronze aux événements : rejeu complet, ou --reprendre
```

Un passage télécharge la page de téléchargement de la BDPM et ses onze
fichiers ; une fois par jour, la documentation PDF de leur format et les
métadonnées Open Medic. Chaque
fichier reçu est conservé à l'octet près, compressé, sous
`bronze/<source>/<fichier>/<jour>/<horodatage UTC>__<sha256, 12 car.>.<ext>.gz`, et
chaque passage laisse une ligne par fichier dans
`manifeste/collecte.jsonl`, même en erreur. L'archive s'écrit hors du
dépôt, sous `PHARMAFLUX_DATA` (défaut : `~/pharmaflux-data`). Rien de
`data/` n'entre dans git. En production, la collecte tourne toutes les
heures à `:17` sur un VPS (minuteur systemd) et une copie est rapatriée
chaque semaine : procédure dans
[`infra/planification/README.md`](infra/planification/README.md).

`profil` vérifie une archive contre son **contrat de schéma**
(`src/pharmaflux/contrats/bdpm/`, un TOML par fichier) et mesure ce
qu'elle contient : les anomalies sont signalées, jamais corrigées. Le
résultat sur l'archive du 24/10/2026 est dans
[`docs/donnees/`](docs/donnees/README.md). `questions verifier` rejoue le
[jeu de questions de référence](evaluation/README.md) : quarante questions
dont la réponse attendue est lue dans une archive précise.

`evenements` lit chaque archive du bronze avec son contrat, la normalise,
la compare à la dernière archive retenue du même fichier et écrit, par
archive, un fichier d'événements JSON Lines, un bilan et un état de
reprise (`data/evenements/` par défaut, hors git). Deux rejeux donnent les
mêmes octets ; `--reprendre` ne traite que les archives arrivées depuis.
Sur la copie de l'archive au 26/10/2026 : 164 096 événements d'état
initial, puis 3 présentations supprimées, et le fichier vide du 26/10
écarté sans un seul événement.

Vérifications locales, identiques à la CI :

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
```

## Méthode

Une mission = une branche = une PR, par paliers verts, avec relecture à
contexte neuf avant publication. Le circuit, les ordres de mission, les
rapports et les relectures sont dans [`docs/`](docs/) : ils font partie de
ce que ce dépôt montre.

## Licences des données

BDPM : citation de la source et de sa date, aucune altération (l'archive
conserve les octets reçus, tels quels). Open Medic : Licence Ouverte
Etalab.
