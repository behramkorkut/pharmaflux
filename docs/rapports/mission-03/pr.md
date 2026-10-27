# Mission 03 — bus d'événements : écriture en flux, Redpanda, schémas, publication, file des échecs, vérification

Branche `mission-03-bus-d-evenements`, 13 commits depuis `main` dont trois
fusions de `main` par beko (§0 en `8c2017e`, cette description en dernier).
Ordre de mission : `docs/missions/mission-03-bus-d-evenements.md`
(addendum 1). Trois paliers acceptés par l'IeC, chacun avec un correctif
léger (`docs/relectures/mission-03/`, six contrôles commis tels quels).
Relecture 1 : **CONFORME**, 0 bloquant
(`docs/relectures/mission-03/relecture-1.md`), trois points non bloquants
corrigés en `57b9be6` (`docs/rapports/mission-03/reponse-relecture-1.md`).

## Ce qui est livré

**Écriture des événements en flux** (palier 1, `eb79940`, rapport
`6ea3405`) : `comparaison.comparer` rend un itérateur sur des squelettes
triés, chaque événement est fabriqué, sérialisé et écrit à son tour, aucun
n'existe avant d'être écrit ni ne survit après ; `volume.Resultat` ne porte
plus ses événements, `Suivi.resultats` est retiré ; les valeurs brutes et
normalisées répétées d'une ligne à l'autre sont partagées. Sortie identique à
l'octet à celle du code fusionné (`diff -r`), 413 tests inchangés, un test de
mémoire sous `tracemalloc`. Mémoire résidente du rejeu complet sur la copie
du Mac : **474 Mo → 118 à 149 Mo** selon l'exécution, cible de 160 tenue.
ADR 0006 mis à jour.

**Bus local, schémas, publication, file des échecs** (palier 2, `ab015b2`,
correctifs `a805da5`) : `docker-compose.yml`, un Redpanda mono-nœud
`v26.2.6` épinglé (console `v3.13.1` sous profil), ports sur `127.0.0.1`
hors des ports par défaut, volume nommé, mode `dev-container` à 768 Mo,
création automatique des topics coupée par `.bootstrap.yaml` (bloc
`configs: content:`) ; paquet `pharmaflux.bus` : enveloppe (la valeur est
la ligne JSONL à l'octet, la clé l'objet `cle` trié, l'horodatage
`date_observation`, en-têtes dont `schema_id` et `fichier`), client
`confluent-kafka` (producteur idempotent, zstd, `murmur2_random`, 1 Mo
refusé au `produce`, topics `pharmaflux.<entite>.v1` à 3 partitions créés
avec rétention infinie), registre (`BACKWARD_TRANSITIVE`, un sujet par
topic, deux schémas draft-07 épinglés par sha256, historique vide),
publication (`publication.json` écrit après l'accusé de réception de chaque
fichier, sha256 des octets publiés, `--reprendre`, refus sans forçage d'un
fichier modifié ou disparu, codes 1/2/3) et file `pharmaflux.echecs.v1`
(`illisible`, `trop_gros` tronqué à 64 Ko, 1 partition, `LogAppendTime`).
Commandes `pharmaflux schemas enregistrer` et `pharmaflux publier`.

**Vérification, coupure et reprise, CI** (palier 3, `be0ec60`, correctif
`24a9242`) : `pharmaflux verifier-bus` relit chaque topic depuis le début,
toutes les partitions assignées à la fois jusqu'aux offsets de fin lus au
départ, sans groupe ni commit ; dédoublonne par `id`, applique par lots,
réduit l'état à une empreinte sha256 par ligne avant de calculer la
référence (un seul état complet en mémoire) ; deux références, les fichiers
d'événements de la sortie ou, avec `--racine`, le dernier snapshot retenu
recalculé depuis l'archive ; rétention, politique, type d'horodatage et
partitions vérifiés ; une référence introuvable est refusée avant de lire
le bus ; code 2 sur toute différence, doublons rapportés avec leur fichier.
Tests de coupure pendant chacun des trois fichiers puis `--reprendre`, sur
un bus simulé et sur le vrai courtier : aucune différence, les doublons
viennent du seul fichier republié et sont des copies exactes. Job CI
`integration` par le compose du dépôt (amorçage vérifié, schémas sur
registre neuf, journal du courtier en cas d'échec, `down -v` toujours). ADR
0007 accepté, `CONTEXTE.md`, README, journal.

**Correctifs de la relecture 1** (`57b9be6`) : en CI, un saut des tests
d'intégration est un échec (`PHARMAFLUX_INTEGRATION_EXIGEE`) ; `publier`
interroge le courtier au départ, donc `--reprendre` sort code 1 sans
courtier même sans rien à publier ; ADR 0006 corrigé sur les squelettes.

**Démonstration sur la copie du Mac** (archive en lecture seule, sortie
jetable) : rejeu complet 8,3 s, `diff -r` identique ; `publier` 164 099
messages sur onze topics en 29,8 s et 59 Mo ; `verifier-bus` conforme,
0 doublon, 11 s et 189 Mo (219 avec `--racine`). Le relecteur a reproduit
ces chiffres avec un rejeu indépendant (149 Mo, 12 topics conformes sur 12).

**Tests** : **446** (413 à la fin de la mission 02), dont 6 d'intégration
marqués `integration`, sautés avec le motif sans courtier sur le Mac ; les
autres tournent sans réseau ni conteneur, sur un bus et un registre
simulés. Dépendance de production ajoutée : `confluent-kafka` (`jsonschema`
en test).

**Documents** : `docs/rapports/mission-03/` (points à trancher, trois
rapports de palier, trois réponses aux contrôles, réponse à la relecture),
`docs/relectures/mission-03/` (six contrôles, une relecture, commis tels
quels), ADR 0006 et 0007, journal.

## Vérifications locales (commit testé : `57b9be6` ; `pr.md` et le journal seuls ont changé depuis)

Courtier du projet démarré sur le Mac (`pharmaflux-redpanda`, sain).

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 154 files already formatted |
| `uv run mypy src` | Success: no issues found in 36 source files |
| `uv run pytest -q` | 446 passed in 28 s |
| `uv run pytest -q -m integration` | 6 passed in 14 s ; topics et sujets de test supprimés |
| `PHARMAFLUX_COURTIER=127.0.0.1:1 uv run pytest -q -m integration` | 6 skipped, motif affiché ; avec `PHARMAFLUX_INTEGRATION_EXIGEE=1` : 6 erreurs, code 1 |
| `python3 infra/agents/test_garde_fou.py` | OK |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| shellcheck | non lancé : aucun `.sh` dans `git diff --name-only main...HEAD` |
| `rpk cluster config get auto_create_topics_enabled` | `false` |
| critère de clôture sur la copie du Mac : `evenements --reprendre`, `publier --reprendre`, `verifier-bus` | 0 archive ; 0 fichier en 0,1 s ; 12 topics conformes sur 12, 0 doublon, 12,1 s, 195 Mo |

Le compte de `ruff format` inclut les blocs Python des fichiers Markdown.
L'archive `~/pharmaflux-data` n'a été que lue ; aucune requête réseau vers
les sources ; les conteneurs d'Alamel n'ont pas été touchés. La CI
`integration` n'a pas encore tourné : sa première exécution a lieu au push,
et c'est là que les deux écarts nommés dans le rapport du palier 3 se
vérifient (architecture amd64 du runner, version de Compose pour le bloc
`configs: content:`).

## Sur le VPS

Rien. Le bus tourne sur le Mac dans cette mission ; la collecte horaire
n'est pas touchée. Le passage sur le VPS est un ordre à part.

## Écarts à l'ordre et interprétations

Tous consignés dans les rapports de palier et acceptés par les contrôles
de l'IeC :

1. Partage des valeurs répétées dans la lecture et la normalisation, hors de
   la liste du §0, pour tenir la cible de 160 Mo (le flux seul donnait
   171 Mo).
2. Test de mémoire à 4 000 lignes au lieu de 20 000 (même ratio, 3,4 s au
   lieu de 15).
3. Le registre déduplique par contenu : les onze sujets d'événements
   partagent le `schema_id` 1, la file le 2 (dit dans l'ADR 0007).
4. `message.timestamp.type` vérifié par `verifier-bus` en plus de la
   rétention et des partitions.
5. Pas de cible de mémoire pour `verifier-bus` : 190 à 230 Mo mesurés, cause
   nommée dans l'ADR 0007 (tampons du consommateur, fragmentation).
6. `ConfigResource` importé d'un module privé de `confluent-kafka`, le
   commentaire dit pourquoi (remarque de l'IeC, sans correctif).

Quatre propositions restent à trancher par l'IeC, listées dans la réponse à
la relecture 1 : tri numérique de l'historique des schémas, sort de
`Registre.compatible`, refus explicite d'un fichier hors d'ordre, test d'une
coupure sur un préfixe livré.
