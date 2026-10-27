# Mission 04 — rejeu accéléré et jeu de démo : `demo/archive` figé dans le dépôt, `demo rejouer`, `suivre`, `make demo`, CI

Branche `mission-04-rejeu-accelere-et-demo`, 9 commits depuis `main`
(`f1750dc`), §0 en `ab31fd3`, cette description en dernier. Ordre de
mission : `docs/missions/mission-04-rejeu-accelere-et-demo.md` (addendum 1,
`aceb5ba` sur `main`). Trois paliers acceptés par l'IeC, le troisième avec un
correctif (`7c9e6a8`) ; trois contrôles commis tels quels dans
`docs/relectures/mission-04/`. Relecture 1 : **CONFORME**, 0 bloquant
(`relecture-1.md`), un point non bloquant et trois remarques corrigés en
`cd7810e` (`docs/rapports/mission-04/reponse-relecture-1.md`).

## Ce qui est livré

**Un jeu de démo figé dans le dépôt** (palier 1, `642998b`) : `demo/archive`,
trois jours de collecte réelle de la BDPM (du 24/10 19:41 au 27/10 15:17,
71 passages, 22 archives pour onze fichiers, 781 lignes de manifeste, 6,7 Mo),
repris à l'octet depuis la copie du Mac par `pharmaflux demo fabriquer`, avec
`demo/README.md` (source, licence, contenu, table des sha256) et
`pharmaflux demo verifier` qui le contrôle sur un clone neuf (`test_demo.py`
relit aussi le README). Seule exception à « rien de `data/` dans git »,
écrite dans `CLAUDE.md` par l'IeC et dans `.gitignore`. Mesure de beko dans
git : **6,68 Mio d'objets en vrac, contre un pack de 836 Kio avant le jeu**.
Reliquats de la mission 03 soldés et testés : historique des schémas trié sur
le numéro (F.1), schéma courant soumis à la compatibilité du registre avant
enregistrement (F.2, testé aussi contre le vrai registre : un schéma sans
`date_source` est refusé, une seule version), refus d'un fichier hors d'ordre
avant le premier message (F.3). Un fichier d'événements vide est publié avec
zéro message.

**Le rejeu accéléré** (palier 2, `aa079da`) : `pharmaflux demo rejouer`
lance `evenements` sur le jeu vers `data/demo`, puis publie les fichiers
d'événements par le code de `publier` (`publication.preparer` et
`publier_fichier`, le même `publication.json`) dans l'ordre global des
observations, une entrée par archive et une par passage sans archive, à la
cadence `t_reel_depart + (t_obs − t_obs_premiere) / facteur`, facteur 1 000
par défaut (une heure observée dure 3,6 s), `--sans-pause` pour la CI,
`--sans-passages`, `--reprendre`. Une ligne par entrée à l'heure observée,
un résumé. L'état du bus est jugé avant tout, code 2 : bus vide sans état →
rejeu ; bus publié avec son état → refus sans `--reprendre` ; bus non vide
sans état ou état sans bus → refus vers `make rebatir`. Seuls comptent les
topics exacts de la démo (correctif du contrôle 3). `pharmaflux suivre`
affiche chaque événement publié en une ligne, attend un topic absent,
`--nombre`, `--depuis-le-debut`.

**`Makefile`, prérequis, CI, docs** (palier 3, `59421c7`) : `make up`
(prérequis puis `up -d --wait --pull never`), `make demo` (schémas, rejeu,
`verifier-bus --racine demo/archive` qui a le dernier mot), `make suivre`,
`make verifier`, `make console`, `make down`, `make rebatir` (`down -v` du
seul projet `pharmaflux`, `rm -rf data/demo`, `up`), `make verifications`,
`make help` ; écrit pour GNU Make 3.81. `infra/demo/prerequis.sh` vérifie
sans rien télécharger : démon Docker, Compose lit le fichier, images des
seuls services que la cible lance (`config --images` résout les profils),
`uv` ; chaque manque affiche le geste, puis « prérequis : NON », code 1. La
CI lance `make demo DEMO_OPTIONS=--sans-pause` dans le job `integration`,
après les tests d'intégration et avant `down -v`. ADR 0008, section « Démo »
en tête de « Lancer » dans le README, `CONTEXTE.md`, journal.

**Démonstration de beko sur le Mac** (décision 7, sur `7c9e6a8`, dans
`pharmaflux-codeur/`) : `make demo` sur le bus qui portait la démo du
palier 2 a **refusé** (code 2, « le bus a déjà reçu une publication …
(make rebatir) »), puis `make rebatir` et `make demo` : rejeu des 22 archives
en 9,0 s ; 22 archives déroulées, 18 fichiers publiés, 4 écartés, 0 en
attente, 59 passages sans archive ; **164 106 messages** sur onze topics,
dont 20 908 pour les présentations (20 898 à l'état initial, puis 2, 1 et 7
suppressions) ; observé du 24/10 19:41:43 au 27/10 15:17:08 (67 h 35 min),
réel **4 min 03 s** au facteur 1 000 ; `verifier-bus` **12/12 conforme**,
file des échecs vide, 12,3 s, code 0 ; registre neuf (schéma d'événement
id 1, échecs id 2). L'IeC a relancé `verifier-bus` ensuite : identique.
Mémoire (Q5) : `demo rejouer` entier 145 Mo résidents (seuil 256),
`evenements` sous `tracemalloc` de 0,7 à 35,8 Mo par entité.

**Tests** : **470** (446 à la fin de la mission 03), dont 9 d'intégration
marqués `integration`, lancés sur le courtier du Mac et sautés sans lui ; les
autres tournent sans réseau ni conteneur. Aucune dépendance nouvelle.

**Documents** : `docs/rapports/mission-04/` (points à trancher, trois
rapports de palier, réponse à la relecture), `docs/relectures/mission-04/`
(trois contrôles, une relecture, commis tels quels), ADR 0008, `demo/README.md`.

## Vérifications locales (commit testé : `cd7810e` ; `pr.md` et le journal seuls ont changé depuis)

Courtier du projet démarré sur le Mac (`pharmaflux-redpanda`, le bus de la
démo de beko).

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 176 files already formatted |
| `uv run mypy src` | Success: no issues found in 40 source files |
| `uv run pytest -q` | 470 passed in 35,8 s, dont 9 `integration` |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/demo/prerequis.sh` | rien à signaler |
| `sh infra/demo/prerequis.sh` ; avec `PHARMAFLUX_IMAGES=exemple/absente:1` | OK, code 0 ; NON, code 1 |
| `make -n` des dix cibles (palier 3, relecteur) | codes 0 ; `rebatir` ne nomme que le projet `pharmaflux` |
| `python3 infra/agents/test_garde_fou.py` | 21 tests OK |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `uv run pharmaflux demo verifier` | conforme (22 archives, 781 lignes, 71 passages) |
| `profil`, `questions verifier`, `evenements` puis `diff -r` contre `4684292` (relecteur) | 0 bloquante ; 25/5/10 ; identique |
| `make up` puis `make demo` (beko, `7c9e6a8`) | ci-dessus : 12/12 conforme, code 0 |

L'archive `~/pharmaflux-data` n'a été que lue ; aucune requête réseau vers
les sources. **La CI n'a pas encore tourné** : sa première exécution a lieu au
push. Limites de l'étape `make demo` en CI, à vérifier là : le runner est en
amd64 (arm64 sur le Mac, images multi-architecture), GNU Make 4.3 lit un
fichier écrit pour 3.81, Compose est celui du runner (le bloc
`configs: content:` demande la 2.23.1 au moins, déjà passé à la mission 03),
et la démo sans pause est estimée à **≈ 1 min 30 s** (rejeu 9 s, publication
d'environ 30 s, `verifier-bus` 12 s, plus les démarrages) dans un job de
15 minutes. Le temps mesuré au premier passage est à reporter ici par beko.

## Sur le VPS

Rien. La collecte horaire n'est pas touchée ; le jeu de démo est une copie
figée, pas un flux.

## Écarts à l'ordre et interprétations

Tous consignés dans les rapports de palier et acceptés par les contrôles de
l'IeC :

1. 59 passages sans archive, pas 49 : le §0 comptait mal, 12 des 71
   passages portent une archive.
2. La troisième entité du test d'ordre global (spécialités) vient de
   `fixtures/bdpm/CIS_bdpm.txt`, les fixtures dédiées étant écartées comme
   « bloquant » par le garde-fou de volume.
3. Le journal de `evenements` va sur la sortie d'erreur (Q4).
4. `CONTEXTE.md` : la section « La démo » est ajoutée à la suite, mais « Où
   sont les choses » et l'outillage sont modifiés en place, là où la
   décision 8 dit « en fin de fichier » (document de référence, accepté au
   contrôle 3, relevé par la relecture).
5. Le refus d'une image absente renvoie toujours à `--profile console
   pull`, le geste unique du README, même pour `make up`.
6. Le contrôle « aucune ligne postérieure à la dernière archive » annoncé au
   §0 n'existe pas : le jeu garde les deux passages `inchange` qui suivent la
   dernière archive, et `demo verifier` les admet.
7. Au palier 2, `down -v` a été lancé après avoir prévenu beko sans attendre
   sa réponse ; depuis le contrôle 2, toute commande qui efface un volume
   attend sa réponse, et `make rebatir` a été lancé par lui.
8. Trois refus du garde-fou, signalés et jamais contournés : `git
   count-objects -vH` (beko a mesuré le pack), `make --version` (version
   3.81 prise du §0), `chmod +x` sur une cale de test (le cas « `config
   --images` échoue » de `prerequis.sh` n'a pas été exercé, le chemin est relu
   et shellcheck ne dit rien).

Propositions pour les consignes, à trancher par l'IeC dans
`controle-iec-final.md` : permettre au codeur `git count-objects` et
`make --version`, deux lectures.
