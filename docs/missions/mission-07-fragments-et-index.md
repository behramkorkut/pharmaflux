# Mission 07 — Fragments et index : la fiche médicament en fragments datés, l'index vectoriel et sa mise à jour incrémentale ; une CI fiable

**À :** Claude Opus 5.5 (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.8 §2.2, §4 (Lot 3), §5, §6.7, §7.1, §7.3, §7.5, §9,
§10.2 (point 5) · mission 06 (`pr.md`, `controle-iec-final.md`) ·
ADR 0003, 0004, 0007, 0009 et 0010 · `CLAUDE.md` ·
`docs/agents/processus.md`
**Statut :** ordre rédigé le 29/10/2026 — **§0 à rédiger**
**Branche :** `mission-07-fragments-et-index`, dans `pharmaflux-codeur/`
(préparée par beko avec `preparer-mission.sh`). Trois paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Tu as codé la mission 06 : le circuit est le même, messages directs
compris. Lis le PRD v0.8 (§4, Lot 3 : le découpage ; §6.7 : précisé pour
cette mission ; §9), puis cet ordre. Tes commits portent les trailers
`Commis-par: codeur` et
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Constat

Le Lot 2 est fait sur le Mac : le gold donne, à un instant, la fiche
médicament, la disponibilité courante et les alternatives, et les 25
questions concordent depuis le gold. Le Lot 3 commence, et il manque trois
choses :

1. **Rien ne transforme la fiche en texte indexable.** `gold fiche
   --format texte` est lisible, mais l'ADR 0010 dit qu'il n'engage pas le
   format des fragments. Un fragment doit dire sa source, sa date, et
   garder la prudence du gold (« aucun signalement » n'est pas
   « disponible »).
2. **Il n'y a pas d'index.** Le point 5 du §10.2 (Qdrant ou pgvector) est
   resté ouvert jusqu'au Lot 3, qui l'utilise. Le modèle d'embeddings n'est
   pas choisi.
3. **Rien ne tient un index à jour quand la source change.** Le PRD
   demande de remplacer les fragments d'un médicament qui change, de
   retirer ceux d'un médicament qui disparaît, et de n'avoir aucun fragment
   orphelin.

S'y ajoute une dette : **la CI de la PR #7 est tombée une fois** sur trois
tests d'intégration. Le registre de schémas a coupé la connexion sur
`POST /subjects/…/versions`, sans réponse, dans la fixture `registre`
(`tests/conftest.py`), dans trois tests de suite. Les huit tests
précédents étaient passés, et l'étape « Schémas » avant eux aussi. La
relance est passée. beko observe le même phénomène depuis plusieurs
missions. Une relance n'est pas une correction.

**Objectif** : à la fusion, cinq choses sont vraies.
- La CI ne dépend plus de la chance : la cause des coupures du registre
  est établie, ou, à défaut, la chaîne y résiste d'une façon écrite et
  testée.
- Les **fragments** de chaque fiche se calculent depuis le gold à un
  instant, à l'identique d'un calcul à l'autre, et chacun porte sa source,
  la date de sa source et l'instant de l'état.
- Un **index vectoriel** local contient les fragments du jeu de démo, avec
  leurs embeddings, calculés par un modèle local épinglé.
- L'index se **met à jour par incréments** et reste égal à sa
  reconstruction complète, sans fragment orphelin ni manquant.
- Une commande de recherche rend les fragments les plus proches d'une
  question, avec leur source et leur date. **Aucun LLM** dans cette
  mission.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Les fragments viennent du gold, et seulement du gold.** Pas de lecture
  du bronze, du silver brut ou des événements pour écrire un texte. Le
  texte est **déterministe** : sans LLM, sans date du jour, sans ordre
  dépendant d'un dictionnaire. Les mêmes fiches donnent les mêmes
  fragments, à l'octet, et le même identifiant.
- **La prudence du gold passe dans le texte.** `aucun_signalement` ne
  s'écrit jamais « disponible » (ADR 0003). Une ligne sans CIP13 dit
  qu'elle vise la spécialité. Un début à venir dit qu'il est annoncé. Une
  fiche partielle dit que le référentiel des spécialités ne connaît pas ce
  CIS. Une colonne illisible ne s'écrit pas avec une valeur devinée.
- **Citation** : chaque fragment dit le fichier BDPM, la date de la
  source et depuis quand la valeur est observée, comme la fiche texte de la
  mission 06 (« observée depuis …, source du … »). La date du dernier
  fichier retenu par entité reste une proposition hors mission : le silver
  ne change pas.
- **L'index porte l'état courant**, pas l'histoire. Son instant est celui
  de la dernière observation du silver qu'il a appliquée, et il le dit.
  « Que savait-on le JJ/MM ? » reste une question pour le gold.
- **L'index n'est jamais en avance sur le silver**, et il se vérifie
  contre une reconstruction complète depuis le gold au même instant :
  mêmes identifiants, mêmes textes, mêmes métadonnées.
- **Embeddings locaux**, par un modèle épinglé (nom, révision, empreinte
  des fichiers), sans API payante. Les crédits de l'API Claude restent
  pour la génération (mission 08). Un fragment dont le texte n'a pas changé
  n'est pas recalculé (PRD §7.5).
- **Le corpus des avis HAS n'est pas dans cette mission** : sa collecte
  vers `has-sante.fr` (ADR 0004) est à la mission 08. Les avis SMR et ASMR
  de la BDPM, eux, sont dans la fiche, donc dans les fragments.
- **Le silver, le gold, les événements, le bus et les contrats ne changent
  pas**, sauf ce que demande la fiabilisation du palier 1 (côté client du
  registre, fixtures de test, CI). Le jeu de questions v0 non plus.
- **Les tests restent hors réseau et hors Docker**, sauf ceux marqués
  `integration`. Les tests unitaires n'utilisent pas le vrai modèle : un
  encodeur de test déterministe, derrière la même interface, suffit pour
  tout ce qui n'est pas la qualité de la recherche.
- **Le colima est toujours partagé avec Alamel** (`alamel-dev-postgres`
  sur 5432, `alamel-dev-minio` sur 9000-9001). Projet `pharmaflux`
  partout, `--pull never`, ports liés à `127.0.0.1` et différents de ceux
  d'Alamel. Aucune commande ne vise un autre conteneur, volume ou image.
  Toute commande qui efface un volume attend la réponse de beko.
- **Téléchargements** : seul beko télécharge une image Docker ou les
  fichiers d'un modèle. Tu écris la procédure, épinglée (version et
  empreinte), et beko la lance. Les fichiers du modèle sont hors de git.
- **Dépendances** : toute dépendance nouvelle se justifie au §0, avec la
  règle des deux semaines et les plafonds temporaires de l'ADR 0009.

## Sources de données pour cette mission

- **Le jeu de démo** `demo/archive` et le silver qu'en tire `make silver` :
  la source principale de la mission, de ses tests et de sa
  démonstration.
- **L'archive du Mac, en lecture seule** (`$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data`), pour la non-régression. Tu n'y écris jamais rien.
- **Le journal du run de CI en échec** (PR #7) : beko te le transmet, avec
  le journal du courtier s'il existe.
- **Aucune requête réseau vers les sources** (BDPM, data.gouv, HAS). Les
  seuls téléchargements de la mission (image de la base vectorielle,
  fichiers du modèle) sont faits par beko, selon ta procédure.

## §0 — Points à trancher avant de coder

Réponds dans `docs/rapports/mission-07/points-a-trancher.md` : pour chaque
point, ton **constat** (mesuré quand c'est possible, avec la commande), ton
**avis**, et tes **questions**. Rien n'est codé avant l'addendum de l'IeC.

**A. Les coupures du registre.** Lis le journal que beko te transmet, puis
le client (`bus/registre.py`), la fixture `registre`, le compose
(`--memory=768M`, `--smp=1`, `mem_limit: 1g`, le healthcheck ne regarde que
Kafka) et l'étape de CI. Dis ce que tu sais de la cause, et ce qui reste
une hypothèse. Propose :
- la correction côté client : un réessai borné sur une coupure de
  connexion, pour quels appels (un `POST …/versions` du même schéma est
  idempotent, une suppression aussi ?), combien de fois, avec quelle
  attente, et ce qui est écrit quand il sert ;
- ce que la CI ou le compose doivent attendre avant les tests (un
  registre qui accepte une écriture, pas seulement un Kafka qui répond) ;
- comment on saura, à la prochaine coupure, ce qui s'est passé : le
  journal du courtier au bon moment, et le détail des erreurs de pytest
  (`-rE`).

Un réessai qui cacherait une vraie panne n'est pas une correction : dis
où passe la limite.

**B. La base vectorielle** (point 5 du §10.2). Qdrant (défaut du PRD) ou
pgvector, et tout autre choix que tu juges meilleur, argumenté. Critères :
- tourne dans le compose du projet, ou dans le processus, sans toucher au
  Postgres d'Alamel ;
- image épinglée, mémoire au repos et en charge sur le jeu ;
- recherche **hybride** possible à la mission 08 (dense et lexicale) ;
- remplacement et suppression des fragments d'un médicament ;
- où garder l'instant et la position de l'index.

L'IeC penche pour Qdrant, dans le compose, sur un port non standard lié à
`127.0.0.1`, avec un volume du projet `pharmaflux`. L'ADR 0011 enregistre
le choix.

**C. Le modèle d'embeddings.** Un modèle multilingue qui comprend le
français médical, assez petit pour le seuil de 512 Mo par commande. Pour
deux ou trois candidats : taille, mémoire, temps pour encoder tous les
fragments du jeu, licence, et une première mesure de qualité sur quelques
questions du jeu v0 (le fragment attendu est-il dans les cinq premiers ?).
La bibliothèque (ONNX ou PyTorch : PyTorch est lourd), l'épinglage
(révision, sha256 des fichiers), où vivent les fichiers (hors de git),
comment `make up` vérifie leur présence sans les télécharger, et comment
la CI les obtient (téléchargement épinglé avec cache, ou autre).

**D. Les fragments.** Le grain : une fiche entière, une section par
fragment (présentations, composition, groupe générique, conditions,
avis, MITM, disponibilité, informations importantes), ou autre. Pour
chaque grain : le texte d'un exemple réel du jeu, la taille en jetons du
modèle retenu, et ce qui dépasse sa fenêtre. Puis :
- l'identifiant déterministe d'un fragment ;
- les métadonnées (CIS, section, fichier, date de la source, observée
  depuis, instant de l'état, version du format) ;
- une version du format des fragments, et ce qui la fait changer ;
- comment la prudence du gold s'écrit (exemples réels : une ligne sans
  CIP13, un début à venir, une fiche partielle, `aucun_signalement`) ;
- les nombres sur le jeu : fiches, fragments, taille totale.

**E. La mise à jour incrémentale.** D'où viennent les changements :
- les **événements du bus** (PRD §5, étape 5), avec une position par
  topic, à borner par celle du silver ;
- ou les **versions du silver** ouvertes ou fermées depuis l'instant de
  l'index.

L'IeC penche pour le silver : l'index lit le gold, donc il doit suivre le
silver, et il n'aurait pas de position de bus à garder cohérente avec
celle du silver. Donne ton avis. Puis :
- de chaque changement, comment déduire les CIS touchés : une
  présentation par son CIS, une ligne de disponibilité sans CIP13, un
  groupe générique (tous ses CIS ?), un lien vers un avis de la CT (les
  CIS de ses avis), une information importante ;
- le remplacement (les fragments qui disparaissent d'une fiche aussi), la
  suppression d'une fiche ;
- l'idempotence et la reprise après une coupure à n'importe quel point,
  sans transaction entre l'index et autre chose ;
- le cas où rien n'a changé.

**F. La vérification.** `index verifier` : l'index courant est-il égal à
la reconstruction complète depuis le gold au même instant ? Ce qu'il
compare (identifiants, textes, métadonnées, présence des vecteurs, ou les
vecteurs eux-mêmes), son code de sortie, et le contrôle « aucun fragment
orphelin ». Le test qui prouve l'incrément : le jeu publié en plusieurs
tranches, silver et index mis à jour après chacune, et à chaque étape
l'index égal à la reconstruction complète.

**G. La recherche.** `index chercher "…"` : les k fragments les plus
proches, avec leur score, leur source et leur date. Un filtre par CIS ou
par section ? Ce n'est pas encore l'assistant : pas de seuil d'abstention,
pas de réponse rédigée. Dis ce que tu mesures pour donner à la mission 08
une première idée de la qualité.

**H. Les commandes.** Le groupe `pharmaflux index` : les noms, les
options, les formats de sortie, et les codes de sortie. Au moins
`construire` (en entier), `mettre-a-jour` (par incréments), `verifier`,
`chercher`, `etat` (instant, nombre de fragments, modèle, format).

**I. `Makefile`, compose et CI.** La cible (`make index` ?), ce qu'elle
enchaîne après `make gold` ; la place de la base vectorielle dans `make
up`, `make down` et `make rebatir` ; le contrôle de `infra/demo/prerequis.sh`
(image et modèle présents) ; l'étape du job `integration` et sa durée
estimée, modèle compris.

**J. La mémoire et le temps.** Pour chaque commande, sur le jeu : le
résident maximal, contre le seuil de 512 Mo par commande (ADR 0009), et la
durée. Le calcul des fiches (411 à 421 Mo à la mission 06) et le modèle
dans le même processus dépasseraient-ils le seuil ? Si oui, comment les
séparer.

**K. Autre.** Tout ce que cet ordre n'a pas vu.

## Décisions (sous réserve du §0)

1. **Fiabilisation de la CI** (§0 A) : la correction retenue, son test, et
   une CI qui collecte ce qu'il faut pour diagnostiquer la prochaine
   coupure.
2. **Fragments** (§0 D) : une fonction du gold à un instant, déterministe,
   datée, prudente, versionnée.
3. **Index** (§0 B, C, H) : la base vectorielle dans le compose, le modèle
   épinglé, `index construire`, `index chercher`, `index etat`.
4. **Incrément et vérification** (§0 E, F) : `index mettre-a-jour` et
   `index verifier`, égalité avec la reconstruction complète à chaque
   tranche.
5. **`Makefile`, compose, CI** (§0 I) : la cible après `make gold`, l'étape
   dans le job `integration`. Le job `verifier` ne change pas.
6. **Démonstration sur le Mac** :
   - toi, au palier 2 : l'index du jeu construit, trois recherches réelles
     avec leurs résultats, la mémoire et les temps ;
   - beko, au palier 3 : `make rebatir`, `make demo`, `make silver`,
     `make gold`, puis la cible de l'index. Il te transmet la sortie, et tu
     la cites dans le rapport.
7. **Docs** :
   - ADR 0011 : les fragments, la base vectorielle, le modèle, l'incrément
     et la vérification, et ce que l'index ne fait pas ;
   - `README.md` : une section « L'index », avec un exemple réel (une
     recherche sur le jeu et ses fragments, avec source et date). La
     section « État » passe la mission 06 en « fusionnée » et ajoute la
     mission 07 ; le Lot 2 y est « fait » ;
   - `docs/CONTEXTE.md`, et `docs/journal.md` en fin de fichier. La
     **première entrée du journal** donne la durée de l'étape `make gold`
     dans la CI, que `pr.md` de la mission 06 laissait à compléter :
     **17 s** sur `main` après la fusion (run du 29/10, `make silver` 40 s
     dans le même job), et la panne du registre de la PR #7.

**Outillage** : un client de la base vectorielle et une bibliothèque
d'embeddings sont attendus (§0 B et C) ; rien d'autre sans justification.

## Paliers

1. **CI fiable et fragments** : décisions 1 et 2.
   - La correction du registre, ses tests, et l'étape de CI qui collecte
     le diagnostic.
   - Les fragments, depuis le gold, et leurs tests : sur les fixtures,
     puis sur le jeu de démo, avec un silver construit dans un dossier
     jetable. Chaque règle de prudence a son test.
   - Une commande qui écrit les fragments en JSON Lines, sans index (pour
     les relire et les compter).
   - Python pur, aucune commande `docker`, aucun modèle.
   - L'entrée du journal sur la durée de la CI.
   - Rapport, commit.
2. **Index et recherche** : décision 3.
   - La base vectorielle dans le compose (beko télécharge l'image selon
     ta procédure), le modèle épinglé (beko télécharge ses fichiers).
   - `index construire`, `index chercher`, `index etat`, et les tests
     d'intégration.
   - Ta démonstration de la décision 6, avec la mémoire et les temps.
   - Rapport, commit.
3. **Incrément, vérification, `Makefile`, CI, docs** : décisions 4, 5,
   6 (beko) et 7.
   - `index mettre-a-jour` et `index verifier`, et le test par tranches.
   - `make -n` de chaque cible nouvelle ou modifiée dans le rapport.
   - L'étape de CI.
   - L'ADR 0011 et les docs, avec la sortie de la cible lancée par beko.
   - Rapport, commit.

Après le contrôle du palier 3, la suite est celle du circuit :
1. la relecture (`/relire-mission 07`), jusqu'à « CONFORME » ;
2. `pr.md` ;
3. la **revue finale écrite de l'IeC** (`controle-iec-final.md`) ;
4. la publication et la fusion par beko.

**La mission est close** quand beko, sur le Mac, enchaîne `make rebatir`,
`make demo`, `make silver`, `make gold` et la cible de l'index, et que
celle-ci finit avec un index égal à sa reconstruction complète, et quand la
CI de la PR passe **du premier coup**.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests unitaires | `uv run pytest -q` (les tests d'intégration sautés sans services, et dit) |
| tests d'intégration (paliers 2 et 3 ; palier 1 pour le registre) | services lancés par `docker compose -p pharmaflux up -d --wait --pull never`, puis `uv run pytest -q -rE -m integration` |
| comme la CI | la suite complète avec `GITHUB_ACTIONS=true`, et `-rE` |
| simulation du `Makefile` (palier 3) | `make -n <cible>` pour chaque cible nouvelle ou modifiée |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck (même version que la CI) | `uvx --from shellcheck-py==0.11.0.1 shellcheck <fichiers .sh touchés>`, si un `.sh` est touché |
| YAML de la CI | lu sans erreur, si `ci.yml` est touché |
| non-régression | `uv run pharmaflux demo verifier` ; `uv run pharmaflux profil` et `uv run pharmaflux questions verifier` sur `~/pharmaflux-data` ; `pharmaflux evenements` sur la copie du Mac, comparé au `diff -r` à la sortie du code fusionné (`98505d3`) ; `silver verifier` sur le jeu, 22/22 ; les deux commandes de `make gold` sur le jeu, aucun bloquant et 25 concordantes |

## Hors périmètre

- **Le corpus HAS**, le retrieval hybride, les réponses rédigées, la porte
  d'abstention, le refus médical, le jeu de questions v1 : **mission 08**.
  L'API, l'interface, l'évaluation dans la CI et le test de fraîcheur de
  bout en bout : **mission 09**. L'index de cette mission est ce qu'elles
  liront.
- Un consommateur qui tourne en continu : l'index se met à jour par une
  commande, comme le silver. Le délai « de la détection à l'index » du
  §2.2 se mesurera de bout en bout à la mission 09.
- La limite de la détection (une brute illisible égale à la forme
  canonique précédente, PRD §6.3) et la date du dernier fichier retenu :
  propositions pour une mission ultérieure.
- Tout changement du silver, du gold, du schéma d'événement v1, des
  contrats, de la normalisation, de l'enveloppe, des topics ou de la
  publication ; toute écriture sur le bus.
- **Toute exécution sur le VPS**, et toute modification de la collecte. Le
  VPS-1 reste partagé avec la pré-production d'Alamel jusqu'à mi-novembre.
- Toute requête vers les sources ; toute écriture dans l'archive ; toute
  utilisation de l'API Claude ; tout service d'embeddings distant.
- Tout stockage objet (MinIO compris) ; toute image ou tout fichier de
  modèle téléchargé par toi.
- **Pas d'usage des VPS d'Alamel**, et rien qui touche aux conteneurs
  d'Alamel du colima (`alamel-dev-postgres`, `alamel-dev-minio`) ni à la
  pré-production du VPS-1.
