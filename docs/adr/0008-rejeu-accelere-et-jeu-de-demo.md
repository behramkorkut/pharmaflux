# ADR-0008 — Rejeu accéléré et jeu de démo : `demo/archive` figé dans le dépôt, `make demo`, ordre global des observations, cadence au facteur 1 000

**Statut :** accepté (mission 04) · **Date :** 2026-10-27 · **Mission :** 04 ·
s'appuie sur les ADR 0006 (événements) et 0007 (bus)
**Remplace / remplacé par :** —

## Contexte

La chaîne de la mission 03 (`evenements`, `publier`, `verifier-bus`) ne se
voit qu'avec la copie de l'archive du Mac, hors du dépôt. Un recruteur qui
clone le dépôt doit pouvoir la regarder tourner sur une donnée réelle, sans
collecte ni téléchargement, en moins de cinq minutes, et la voir vérifiée.
La collecte réelle produit un changement toutes les quelques heures : au
rythme réel, trois jours d'observation ne se regardent pas. Contraintes :
rien de `data/` dans git sauf une exception écrite dans `CLAUDE.md` ; aucun
changement fabriqué ; le schéma d'événement, les contrats, l'enveloppe et
les topics ne changent pas ; aucune dépendance nouvelle ; GNU Make 3.81 sur
le Mac. Mesures sur la copie au 27/10/2026 (71 passages de collecte du
24/10 19:41 au 27/10 15:17) : 22 archives distinctes pour onze fichiers,
6,2 Mo compressés, 59 Mo bruts, 164 106 événements ; rejeu 9,4 s ;
185 Mo résidents pour `evenements` seul, 145 Mo pour la démo entière.

## Décision

**Un jeu de démo figé dans le dépôt** : `demo/archive`, une archive
Pharmaflux comme une autre (`bronze/…`, `manifeste/collecte.jsonl`),
fabriquée par `pharmaflux demo fabriquer` depuis la copie du Mac, coupée au
passage `20261027T151708Z` inclus et réduite aux onze fichiers TSV de la
BDPM. Les archives sont copiées à l'octet, les lignes du manifeste reprises
telles quelles et dans l'ordre : toute commande qui prend `--racine` marche
dessus. 22 archives, 11 entités, 781 lignes de manifeste, 71 passages,
6,7 Mo ; `.gitignore` fait l'exception `!demo/archive/bronze/**/*.gz` sous
`*.gz`. `pharmaflux demo verifier` et `tests/test_demo.py` contrôlent le jeu
sur un clone neuf (manifeste ordonné, sha256 et taille de chaque archive,
rien d'autre dans le dossier, table du `README.md` du jeu égale au
manifeste). Un jeu ne se met pas à jour : on en fabrique un autre.

**Un rejeu accéléré** : `pharmaflux demo rejouer` (`demo/rejeu_accelere.py`)
lance `evenements` sur le jeu vers `data/demo`, puis publie les fichiers
d'événements par le code de `publier` (`publication.preparer` et
`publier_fichier`, le même `publication.json`) dans l'**ordre global des
observations** : une entrée par bilan, triée par (horodatage de l'archive,
entité), plus une entrée par passage du manifeste sans archive nouvelle.
L'ordre par topic est celui de `publier` (le nom d'un fichier commence par
l'horodatage de son archive) ; seul l'entrelacement entre topics change.
**Cadence** : pour une entrée observée à `t_obs`, l'instant réel visé est
`t_reel_depart + (t_obs − t_obs_premiere) / facteur`, jamais de pause
négative ; facteur 1 000 par défaut (une heure observée dure 3,6 s, un
jour 86 s, la démo 4 min), `--sans-pause` pour la CI, `--sans-passages` pour
taire les passages. Une ligne par entrée, à l'heure observée ; un résumé.
**L'état attendu du bus** est jugé avant tout, code 2 : bus vide et sans
`publication.json` → rejeu ; bus publié avec son état → refus sans
`--reprendre`, reprise avec ; bus non vide sans état, ou état sans bus →
refus, avec `make rebatir` pour voie de retour. Un rejeu interrompu se
reprend avec `demo rejouer --reprendre` (ou `publier --reprendre --sortie
data/demo`, sans l'horloge).

**`pharmaflux suivre`** (`bus/suivi.py`) : un consommateur minimal pour un
second terminal, une ligne lisible par événement (heure observée, entité,
type, clé, colonnes changées), onze topics depuis leur fin, un topic absent
attendu, `--nombre`, `--depuis-le-debut`, code 0 ; `verifier-bus` juge.

**`Makefile`** : `make up` (prérequis puis `up -d --wait --pull never`),
`make demo` (`up`, `schemas enregistrer`, `demo rejouer`, `verifier-bus
--sortie data/demo --racine demo/archive`), `make verifier`, `make suivre`,
`make console`, `make down`, `make rebatir` (`down -v` du seul projet
`pharmaflux`, `rm -rf data/demo`, `up`), `make verifications`.
`infra/demo/prerequis.sh` vérifie, sans rien télécharger : le démon Docker,
que Compose lit le fichier, que les images **des services que la cible
lance** sont présentes (`docker compose config --images`, la console
seulement sous son profil), et `uv`. La CI lance `make demo
DEMO_OPTIONS=--sans-pause` dans le job `integration`, après les tests et
avant `down -v`.

## Conséquences

- Un clone neuf enchaîne `make up` puis `make demo` ; la démo finit par un
  `verifier-bus` conforme sur la référence indépendante des fichiers. Une
  machine qui a déjà un volume `pharmaflux` voit `make demo` refuser, puis
  `make rebatir` et `make demo` : le refus fait partie de ce qu'on montre.
- Ce que la démo montre : l'état initial (onze fichiers, 164 096 `creee`
  en une trentaine de secondes), dix présentations supprimées en trois
  fois (2 le 24/10 à 23:17, 1 le 26/10 à 00:17, 7 le 27/10 à 00:17), le garde-fou de
  volume sur `CIS_InfoImportantes.txt` servi vide quatre fois (écarté sans
  appel, puis retenu identique au dernier retenu : un fichier vide, publié
  avec zéro message), et 59 passages horaires sans archive nouvelle. Ce
  qu'elle ne montre pas, parce que la copie ne le contient pas : de
  `modifiee` ni de `creee` après l'état initial, de snapshot en attente ou
  confirmé, de ligne de manifeste en erreur, de message dans la file des
  échecs (le cas reste testé sur les fixtures).
- Le dépôt porte 6,7 Mo de données publiques figées (BDPM, Licence
  Ouverte / Etalab) : c'est la seule exception à « rien de `data/` dans
  git », et elle est datée. Mesure de beko : 6,68 Mio d'objets en vrac,
  contre un pack de 836 Kio avant le jeu.
- Mesures de mémoire (Q5 de l'addendum, à reporter au PRD §9) :
  `evenements` sous `tracemalloc`, pic par entité de 0,7 Mo
  (disponibilité) à 35,8 Mo (présentations) ; `demo rejouer` entier sur le
  jeu, rejeu et publication, 145 Mo résidents au maximum (seuil de
  l'addendum : 256 Mo) ; `evenements` seul sur la copie complète du 27/10,
  185 Mo résidents (134 à la mission 03 sur la copie du 26/10, trois
  archives pleines de plus pour les informations importantes) : une mesure,
  pas une régression de code, à surveiller à la prochaine copie.
- À surveiller : la durée de `make demo` en CI (≈ 1 min 30 s estimée sur
  amd64, job de 15 min) ; la taille du dépôt si un second jeu était ajouté
  (on remplace, on n'empile pas) ; le facteur 1 000, à revoir si la copie
  rejouée s'allonge.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| un script qui télécharge la BDPM au premier `make demo` | la source est un service public, pas un banc d'essai ; la démo doit être figée, datée, rejouable hors ligne |
| un jeu réduit à deux ou trois fichiers | l'état initial à onze topics est ce qu'on montre ; 6,7 Mo tiennent dans le dépôt |
| des changements fabriqués pour animer la démo | hors périmètre de l'ordre : la donnée est réelle ou elle n'est pas |
| publier l'état initial d'un bloc avant l'horloge | une règle de plus ; les onze archives du 24/10 sont onze entrées espacées de 2 à 3 s observées, elles s'enchaînent d'elles-mêmes |
| un second chemin de publication pour la démo | `publier` et `demo rejouer` partagent `preparer` et `publier_fichier` : un seul code pour l'enveloppe, la file des échecs, l'état et les refus |
| une option pour forcer sur un bus non vide | un événement publié ne se réécrit pas (ADR 0007) ; `make rebatir` est explicite |
| `grep` des lignes `image:` du fichier compose pour les prérequis | lit l'image de la console, que `make up` ne lance pas ; `config --images` résout les profils |
| GNU Make 4.x (`.ONESHELL`, `!=`) | le Mac a 3.81 ; un fichier écrit pour 3.81 se lit en 4.3 sur le runner |
| `pharmaflux suivre` avec la file des échecs ou un groupe de consommateurs | version minimale retenue par l'addendum ; la file se regarde dans la console, un groupe laisserait une trace sur le courtier |

## Références

PRD v0.5 §6.4, §9 · ordre de mission 04 et addendum 1 ·
`docs/rapports/mission-04/points-a-trancher.md` · ADR 0006, 0007 ·
`demo/README.md` · `Makefile`, `infra/demo/prerequis.sh` ·
`src/pharmaflux/demo/`, `src/pharmaflux/bus/suivi.py` ·
`tests/test_demo.py`, `tests/test_demo_rejeu.py`, `tests/test_suivi.py`,
`tests/test_demo_integration.py` · `.github/workflows/ci.yml` (job
`integration`).
