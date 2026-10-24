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
[`01_Specifications/`](01_Specifications/PRD_Plateforme_Medicaments_v0.1.md)
et le point d'entrée technique dans [`docs/CONTEXTE.md`](docs/CONTEXTE.md).

## État

**Mission 00 en cours** : socle du dépôt et archivage horaire des fichiers
BDPM. L'archive brute est la seule brique qui ne se rattrape pas : elle
démarre avant tout le reste.

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
uv run pharmaflux catalogue          # les treize entrées collectées
uv run pharmaflux collecte           # un passage : télécharge, compare, archive, consigne
uv run pharmaflux etat               # dernière archive, dernier changement, erreurs, 24 h
```

Un passage télécharge la page de téléchargement de la BDPM et ses onze
fichiers, plus les métadonnées Open Medic une fois par jour. Chaque
fichier reçu est conservé à l'octet près, compressé, sous
`bronze/<source>/<fichier>/<jour>/<horodatage UTC>__<sha256>.gz`, et
chaque passage laisse une ligne par fichier dans
`manifeste/collecte.jsonl`, même en erreur. L'archive s'écrit hors du
dépôt, sous `PHARMAFLUX_DATA` (défaut : `~/pharmaflux-data`). Rien de
`data/` n'entre dans git. La planification horaire arrive au palier 3.

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
