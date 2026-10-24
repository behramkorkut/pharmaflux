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

Les commandes `pharmaflux collecte` (un passage d'archivage) et
`pharmaflux etat` sont déclarées et livrées au palier 2 de la mission 00.
L'archive s'écrit hors du dépôt, sous `PHARMAFLUX_DATA`
(défaut : `~/pharmaflux-data`). Rien de `data/` n'entre dans git.

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
