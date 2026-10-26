# Mission 01 — profilage des sources, contrats de schéma et questions de référence

Branche `mission-01-profilage-et-contrats`, 18 commits depuis `main` (dont
une fusion de `main`), du §0 (`2b66971`) à cette description. Ordre de
mission : `docs/missions/mission-01-profilage-et-contrats.md` (addendum 1).
Relecture 1 : **CONFORME**, 0 bloquant
(`docs/relectures/mission-01/relecture-1.md`), quatre points non bloquants
corrigés (`docs/rapports/mission-01/reponse-relecture-1.md`).

## Ce qui est livré

**Reliquats de la mission 00** (palier 1, `51a55e5`, correctif C1
`ee50cdc`) : `bronze.py`, seule lecture de `bronze/` (ordre chronologique,
octets bruts, noms commençant par un point ignorés) ; le collecteur archive
même si l'empreinte de comparaison lève une exception imprévue, consigne
les liens nouveaux sous le filet et prend l'URL de la documentation PDF
dans la page (un `_v6.pdf` est archivé sous son nom et signalé
`lien_change`) ; journal en UTC ; `etat` lit le manifeste en flux et montre
les fichiers partiels orphelins ; une entrée quotidienne archivée sous
signalement n'est plus retéléchargée à chaque passage ; unité systemd
durcie (capacités vides, filtre d'appels système, `UMask=0027`), **score
d'exposition 1,3** mesuré par beko sur le VPS, contre 6,3.

**Contrats de schéma v0** (palier 2, `787e035`),
`src/pharmaflux/contrats/bdpm/`, un TOML par fichier BDPM, onze fichiers :
encodage, fin de ligne, séparateur, retour final, lignes vides ; colonnes
typées parmi neuf types (`texte`, `entier`, `decimal`, `date` paramétré
par son format, `booleen`, `enumeration`, `code`, `url`, `liste`) ; clé
avec `unique` et une `raison` obligatoire sinon ; liens vers d'autres
fichiers ; source (section du PDF et son sha256, archive de référence et
son sha256). Chargeur strict (`tomllib`, toute clé inconnue refusée,
`tomlstrict.py` partagé). La vérification d'une archive rend des
**anomalies, jamais une correction** (PRD §6.2) ; quatre règles sont
bloquantes : encodage, fin de ligne, nombre de colonnes, clé déclarée
unique qui ne l'est pas. Les onze archives du 24/10/2026 passent sans
anomalie bloquante ; les constats du §0 ressortent tels quels (17 016
espaces parasites dans `CIS_bdpm.txt`, 995 prix à virgule des milliers,
52 dates hors plage, 5 lignes en doublon dans `CIS_CIP_Dispo_Spec.txt`).

**Profil des archives** (palier 3, `c98a750`), `uv run pharmaflux profil`
: n'importe quelle archive contre son contrat (anomalies groupées par
règle, `valeur_inconnue` en tête ; clé ; colonnes avec vides, distinctes,
répartition, bornes ; ordre des dates ; liens mesurés), Markdown par
source avec `--markdown`, code 1 à la moindre anomalie bloquante : c'est
l'alerte de changement de format du Lot 5. `docs/donnees/` : les onze
profils de l'archive du 24/10 (0 bloquante) et un README qui ouvre sur le
constat que `CIS_bdpm.txt` n'est pas le référentiel de tous les CIS.
**ADR** 0001 (collecte horaire sur le VPS-1, consignée), 0002 (contrats
TOML, neuf types, bornes relevées par nouvelle version), 0003
(disponibilité : sens d'une ligne qui disparaît, « proposé », revue au plus
tard le 07/12/2026 avec critère de passage), 0004 (corpus HAS : pages
d'avis d'abord, PDF en second). Les cinq requêtes HAS permises ont été
faites : `robots.txt` n'interdit pas les pages d'avis, le document d'avis
est servi derrière une redirection de mesure d'audience (non suivie), les
mentions légales autorisent la réutilisation avec source et date.

**Jeu de questions de référence v0** (palier 4, `87b1ab9`),
`evaluation/questions-reference-v0.toml`, à la racine du dépôt, hors du
paquet : quarante questions, cinq par catégorie de l'annexe B du PRD
(disponibilité, alternatives, remboursement, avis HAS, historique, dépense,
hors périmètre, médical), chacune avec son comportement attendu (réponse,
abstention motivée, refus médical) et, pour une réponse, l'archive du 24/10
(chemin et sha256), le contrat, la clé, les colonnes et les lignes
attendues, brutes. `uv run pharmaflux questions verifier` relit chaque
archive citée, vérifie son sha256 et son contrat, recalcule les lignes et
sort en code 1 au moindre écart : **25 conformes, 5 non calculables
(Dépense, Open Medic au Lot 4), 10 sans attendu** (abstentions hors
périmètre, refus médicaux). `evaluation/README.md` : format, rejeu,
versions (une question ne change pas de sens sous le même identifiant ; v1
= nouveau fichier, cent questions visées au Lot 3).

**Correctifs de la relecture 1** (`f527e9c`, `7b826d5`, `60be1d2`,
`f09741e`) : les bornes numériques du profil ne prennent que des valeurs
conformes au type (`NaN`, `1e9` sont des anomalies comptées) ; décimales en
chiffres ASCII ; l'archive citée par une question doit être dans le
dossier bronze du contrat nommé, en cinq segments exacts ; test des règles
bloquantes lisible ; aide de `--questions`, ADR 0002 et §0 précisés.

**Tests** : 237 (66 à la fin de la mission 00), sur fixtures (`tests/fixtures/`,
lignes réelles choisies du 24/10/2026 et anomalies fabriquées à part dans
`tests/fixtures/contrats/`, jeu d'essai dans `tests/fixtures/evaluation/`),
serveur simulé par `httpx.MockTransport`, aucun appel réseau, aucune
lecture de l'archive. Aucune dépendance ajoutée.

**Documents** : `README.md` et `docs/CONTEXTE.md` à jour (contrats, lecture
du bronze, « on constate, on ne corrige pas »), `docs/rapports/mission-01/`
(points à trancher, quatre rapports de palier, réponse à la relecture),
`docs/relectures/mission-01/` (quatre contrôles de l'IeC, une relecture,
commis tels quels), journal à jour.

## Vérifications locales (commit testé : `f09741e`, le dernier qui touche au code ; `0bf13b1` n'ajoute que des documents)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 94 files already formatted |
| `uv run mypy src` | Success: no issues found in 22 source files |
| `uv run pytest -q 2>&1 \| tail -25` | 237 passed in 5.8s |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 16 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` | rien, code 0 |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` | 11 fichiers profilés, 0 anomalie bloquante, code 0 |
| `… profil --markdown <jetable>` puis `diff -r` avec `docs/donnees/` | identiques, à la ligne « Produit » près |
| `uv run pharmaflux questions verifier --racine ~/pharmaflux-data` | 40 questions : 25 conformes, 5 non calculables, 10 sans attendu, code 0 |
| `uv build --wheel` (dossier jetable) | onze contrats TOML, `evaluation/` du paquet et `tomlstrict.py` présents |

Le compte de `ruff format` inclut les blocs Python des fichiers Markdown.
L'archive `~/pharmaflux-data` du Mac n'a été que lue pendant toute la
mission ; aucune requête BDPM ni data.gouv ; HAS : cinq requêtes, toutes
consommées au palier 3.

## Sur le VPS

Le VPS-1 tourne sur cette branche depuis le 26/10 (unité durcie, score
1,3, passage manuel sans erreur, `MemoryDenyWriteExecute` conservé),
installée par beko au contrôle du palier 1. Après la fusion : retour sur
`main` (étape 7 du README de `infra/planification/`). Rien de cette
mission ne touche la pré-production partagée.

## Écarts à l'ordre et interprétations

Tous consignés dans les rapports de palier et acceptés par les contrôles
de l'IeC :

1. `UMask=0027` et non `0077`, pour que le compte qui rapatrie la copie
   lise encore l'archive ; `PrivateUsers=true` non posé, score atteint sans.
2. Un changement de version du PDF est une ligne en erreur `lien_change`
   de l'entrée elle-même, archivée tout de suite sous son nouveau nom.
3. Lignes vides : une seule règle `ligne_vide`, non bloquante, là où le
   contrat les tolère (`CIS_CPD_bdpm.txt`) ; ailleurs, nombre de colonnes
   faux, bloquant. Une ligne faite seulement de blancs est une ligne vide
   (ADR 0002).
4. Encodage, un contrôle de plus : un fichier déclaré cp1252 qui se décode
   entièrement en UTF-8 est signalé `encodage`, bloquant.
5. Énumérations au-delà de la documentation (`motif_evaluation`, douze
   libellés observés) ; `taux_remboursement` est une liste d'énumération.
6. Plages de dates par colonne, non bloquantes (1950–2030, 2002–2030,
   2000–2035) ; la règle « début postérieur à la mise à jour » est une
   mesure du profil (« ordre des dates »), pas une anomalie.
7. Le PDF d'avis HAS n'a pas été téléchargé (une sixième requête) ; l'ADR
   0004 place les PDF en second.
8. Deux liens de mesure ajoutés aux contrats (`v0` inchangé) :
   spécialités sans présentation, croisement MITM.
9. `docs/donnees/<identifiant>.md`, pour suivre le catalogue.
10. Dépense : table `attendu` omise et `calculable_au = "lot4"` ; un attendu
    peut valoir « aucune ligne » (`valeurs = []`), ce qui rend ces réponses
    rejouables ; champ `prudence` libre, non vérifié par la machine.
11. Avis HAS lus dans les fichiers BDPM (SMR, ASMR, liens CT) en v0 ; le
    corpus HTML est au Lot 3.

À partir de la fusion, tout changement de contenu d'un contrat, lien
compris, passe par une nouvelle version (décision de l'IeC au contrôle du
palier 3).

## Reporté (accepté par l'IeC ou le relecteur)

- Jeu v1 : `alternatives-004` retirée et remplacée par une question sur le
  groupe générique (jointure GENER × CIP), sans réutiliser l'identifiant ;
  `avis_has-005` devient une réponse avec réserve ; cent questions au Lot 3.
- Lot 1 : détection d'écart au compte attendu d'anomalies connues
  (proposition du palier 3) ; `_decoder` : nombre de lignes touchées par
  un octet illisible.
- Lot 4 : `profiler_racine` lit chaque archive une fois, cibles comprises.
- PRD v0.3 : annexe A, colonne « Statut » (palier 3) ; annexe B, chaque
  question porte son archive, son sha256 et ses lignes attendues
  (palier 4) ; retenu par l'IeC.
- Garde-fou (pour l'IeC) : une boucle `for` de lecture sur
  `docs/relectures/` est refusée au relecteur, qui lit à chaque tour ; un
  seul `cat` passe.

Hors périmètre, inchangé : CSV Open Medic, Redpanda, Iceberg, Docker, API
Claude (lots suivants).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
