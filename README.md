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
[`01_Specifications/`](01_Specifications/PRD_Plateforme_Medicaments_v0.6.md)
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

### Démo : la chaîne entière en quatre minutes, sur une donnée réelle

Le dépôt porte un **jeu de démo figé**, [`demo/archive`](demo/README.md) :
trois jours de collecte réelle de la BDPM (du 24 au 27 octobre 2026, 71
passages, 22 archives, 6,7 Mo), repris à l'octet, et la seule donnée admise
dans git. `make demo` le rejoue sur le bus **en accéléré** : une heure
observée dure 3,6 s, un jour 86 s.

Prérequis : Docker avec Compose (sur le Mac, colima), [`uv`](https://docs.astral.sh/uv/),
`make`, et les images du bus déjà téléchargées, une fois :

```bash
docker compose -p pharmaflux --profile console pull   # une fois ; make ne télécharge jamais
```

Deux commandes :

```bash
make up      # vérifie les prérequis (sans rien télécharger) et démarre Redpanda
make demo    # enregistre les schémas, rejoue demo/archive sur le bus, puis verifier-bus
```

Ce qu'on voit, à l'heure observée : l'**état initial** du 24/10 à 19 h 41
(onze fichiers, 164 096 événements `creee`, une trentaine de secondes de
publication), puis l'horloge qui avance passage par passage, et les
changements réels tels qu'ils sont arrivés : dix présentations supprimées,
en trois fois (2 le 24 à 23 h 17, 1 le 26 à 0 h 17, 7 le 27 à 0 h 17), le fichier
des informations importantes servi **vide** quatre fois et écarté par le
garde-fou de volume, puis retenu identique au dernier retenu. La démo finit
par `verifier-bus --racine demo/archive` : le bus relu, dédoublonné, appliqué
et comparé au dernier snapshot recalculé depuis l'archive, « conforme » sur
les onze topics. Ce que la copie ne contient pas ne se voit pas : aucune
`modifiee`, aucun snapshot en attente, une file des échecs vide. Dans un
second terminal, `make suivre` (à lancer **avant** `make demo`) affiche
chaque événement publié en une ligne : heure observée, entité, type, clé.

Sur une machine qui a **déjà** un volume `pharmaflux` (le bus d'une mission
précédente, ou une démo déjà jouée), `make demo` refuse avec le code 2 et le
message qui renvoie à `make rebatir` : un événement publié ne se réécrit pas ;
`make rebatir` (efface le seul projet `pharmaflux` et `data/demo`) puis
`make demo` rejouent tout. Un rejeu interrompu se reprend avec
`uv run pharmaflux demo rejouer --reprendre` (ou `publier --reprendre
--sortie data/demo`, sans l'horloge). `make help` liste les cibles ; la même
démo tourne en CI sans pause (`make demo DEMO_OPTIONS=--sans-pause`). Le
détail des choix est dans l'[ADR 0008](docs/adr/0008-rejeu-accelere-et-jeu-de-demo.md).

### Le silver : l'histoire interrogeable, et vérifiée contre l'archive

Après `make demo`, une troisième commande construit le **silver** (mission 05,
[ADR 0009](docs/adr/0009-silver-iceberg-scd2-et-etat-a-une-date.md)) : une
table Iceberg par entité sous `data/demo/lakehouse`, où chaque ligne est une
**version** datée d'une ligne de la source, valable de la date d'observation
qui l'ouvre à celle qui la ferme (SCD2 sur le temps de la connaissance, borne
de fin exclue). Le consommateur lit le bus, garde sa position dans le commit
Iceberg lui-même, et reconnaît les doublons ; puis la vérification recalcule
le snapshot de chaque archive retenue depuis le bronze et le compare,
empreinte par empreinte, à l'état du silver au moment de son observation.

```bash
make silver  # consommer le bus → data/demo/lakehouse, puis silver verifier : 22/22 conforme
```

Deux questions sur le jeu, « que savait-on à cet instant ? », avec le temps
de la connaissance à la seconde : l'horodatage d'une archive est celui de
son téléchargement (`20261024T231712Z`), pas celui du passage de collecte.

```bash
# Une présentation déclarée en arrêt de commercialisation disparaît le 24/10 à 23:17:12 :
# encore là une seconde avant (une version ouverte), plus là à l'instant de l'archive.
make etat ENTITE=bdpm.presentations A=2026-10-24T23:17:11Z \
  ETAT_OPTIONS="--ou code_cip13=3400938844948 --format tableau --colonne code_cis --colonne etat_commercialisation --colonne fin_validite"
make etat ENTITE=bdpm.presentations A=2026-10-24T23:17:12Z ETAT_OPTIONS="--ou code_cip13=3400938844948"

# Le 26/10 juste après 14:17:39, le fichier des informations importantes a été servi vide
# et écarté par le garde-fou : l'état n'a pas bougé, 10 905 versions, toutes ouvertes.
make etat ENTITE=bdpm.infos_importantes A=2026-10-26T14:17:39Z ETAT_OPTIONS="--format csv --colonne code_cis --colonne fin_validite"
```

La première commande rend une version (`fin_validite` à `2026-10-24T23:17:12Z`),
la deuxième aucune, la troisième 10 905 lignes sans fin de validité. Et du
SQL libre, en lecture seule (DuckDB sans aucun accès fichier, seul un
`SELECT` passe) :

```bash
uv run pharmaflux silver sql --entrepot data/demo/lakehouse \
  "SELECT count(*) AS versions, count(fin_validite) AS fermees FROM presentations"
```

Le même silver se construit depuis les fichiers d'événements
(`uv run pharmaflux silver construire --sortie data/demo --entrepot <dossier>`),
et `silver comparer` montre qu'il est identique à celui du bus : le silver ne
dépend pas du chemin. `make rebatir` efface aussi `data/demo/lakehouse`.

### Les commandes

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
uv run pharmaflux schemas enregistrer # les schémas du dépôt dans le registre de Redpanda
uv run pharmaflux publier            # les fichiers d'événements sur le bus, ou --reprendre
uv run pharmaflux verifier-bus       # relit le bus et le compare à la référence (--racine : l'archive)
uv run pharmaflux suivre             # les événements publiés au fil de l'eau, une ligne par message
uv run pharmaflux demo verifier      # le jeu de démo demo/archive : manifeste, sha256, rien d'autre
uv run pharmaflux demo rejouer       # le jeu rejoué sur le bus, dans l'ordre observé, en accéléré
uv run pharmaflux silver consommer   # le bus → le silver Iceberg (une table par entité), position dans le commit
uv run pharmaflux silver construire  # le même silver, depuis les fichiers d'événements
uv run pharmaflux silver etat        # les versions valides à un instant (--entite, --a, --ou, --format)
uv run pharmaflux silver sql         # du SQL DuckDB sur le silver, en lecture seule
uv run pharmaflux silver comparer    # deux entrepôts : mêmes versions, mêmes validités
uv run pharmaflux silver verifier    # l'état à chaque observation contre le snapshot recalculé
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

**Le bus d'événements** (mission 03) tourne en local, dans Docker, à
partir du fichier [`docker-compose.yml`](docker-compose.yml) : un Redpanda
mono-nœud, projet `pharmaflux`, tous les ports sur `127.0.0.1` (Kafka
`19092`, registre de schémas `18081`, HTTP proxy `18082`, administration
`19644`), les données dans le volume `pharmaflux-redpanda`. Les versions des
images sont épinglées dans ce fichier.

```bash
docker compose -p pharmaflux --profile console pull  # une fois : télécharge les images (beko)
docker compose -p pharmaflux up -d --wait         # démarre, attend que le courtier réponde
docker compose -p pharmaflux down                 # arrête, garde les données
docker compose -p pharmaflux down -v              # rebâtit le bus : efface le volume (aussi après un changement des propriétés de grappe)
docker compose -p pharmaflux --profile console up -d   # en plus : la console sur http://127.0.0.1:18080
```

`schemas enregistrer` pose la règle de compatibilité `BACKWARD_TRANSITIVE`
et enregistre les schémas JSON du dépôt (`src/pharmaflux/bus/schemas/`),
un sujet par topic. `publier` envoie les fichiers d'événements, dans
l'ordre, sur un topic par entité (`pharmaflux.<entite>.v1`, trois
partitions, clé = la clé de l'événement, rétention sans limite) ; la valeur
du message est la ligne du fichier à l'octet près. `publication.json`
garde ce qui est publié ; `--reprendre` ne publie que les nouveaux
fichiers. Une ligne illisible ou un message trop gros vont dans la file
`pharmaflux.echecs.v1`, et le code de sortie le dit. `verifier-bus` relit
chaque topic depuis le début, sans commit d'offset, dédoublonne par `id`,
applique les événements et compare l'état obtenu aux fichiers d'événements
de la sortie ou, avec `--racine`, au dernier snapshot retenu recalculé
depuis l'archive ; il vérifie aussi la rétention sans limite, la politique
`delete`, le type d'horodatage et les partitions de chaque topic. Toute
différence donne le code 2, comme une référence introuvable, refusée avant de
lire le bus ; les doublons d'une reprise sont rapportés, avec le fichier dont
ils viennent. Les tests qui ont besoin du courtier sont
marqués `integration` et sautés sans lui :

```bash
uv run pytest -q -m integration
```

Vérifications locales, identiques à la CI :

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
```

La CI a deux jobs : `verifier`, ces commandes plus les tests des garde-fous
du circuit, et `integration`, qui démarre le Redpanda du même fichier
compose et lance les tests marqués avec la variable
`PHARMAFLUX_INTEGRATION_EXIGEE` posée : là, un saut est un échec, un job
vert a lancé les neuf tests, puis la démo sans pause (`make demo
DEMO_OPTIONS=--sans-pause`), vérifiée par `verifier-bus`.

## Méthode

Une mission = une branche = une PR, par paliers verts, avec relecture à
contexte neuf avant publication. Le circuit, les ordres de mission, les
rapports et les relectures sont dans [`docs/`](docs/) : ils font partie de
ce que ce dépôt montre.

## Licences des données

BDPM : citation de la source et de sa date, aucune altération (l'archive
conserve les octets reçus, tels quels). Open Medic : Licence Ouverte
Etalab.
