# Mission 05 — Silver historisé et « état à une date » : consommateur du bus, tables Iceberg, vérification contre l'archive

**À :** Claude Fable (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.6 §2.1 (objectif 2), §2.2, §4 (Lot 2), §5, §6.3, §6.5,
§7.1, §9 · mission 04 (`pr.md`, `controle-iec-final.md`) · ADR 0006, 0007
et 0008 · `CLAUDE.md` · `docs/agents/processus.md`
**Statut :** ordre rédigé le 28/10/2026 — **§0 à rédiger**
**Branche :** `mission-05-silver-et-etat-a-une-date`, dans `pharmaflux-codeur/`
(préparée par beko avec `preparer-mission.sh`). Trois paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Lis d'abord `CLAUDE.md`, puis `docs/agents/processus.md`, puis le PRD v0.6
(§6.5 a été réécrit pour cette mission), puis cet ordre. Le circuit est
celui de la mission 04, messages directs compris.

## Constat

Le Lot 1 est fait sur le Mac. Chaque changement de la BDPM devient un
événement daté, publié une fois dans Redpanda, et `make demo` le montre sur
un clone neuf. Mais l'objectif 2 du PRD n'est pas tenu :

1. **On ne peut pas demander « que savait-on le 26/10 à 14 h ? ».**
   L'histoire existe, dans les fichiers d'événements et sur le bus, mais
   rien ne l'interroge. Pour retrouver un état passé, il faut rejouer les
   événements à la main.
2. **Aucun consommateur ne lit le bus.** Le parcours du PRD (§5, étape 4)
   suppose un consommateur qui historise chaque changement. Aujourd'hui,
   seuls `verifier-bus` et `suivre` lisent les topics, et ils n'écrivent
   rien.
3. **L'indicateur « reconstruction de l'état à une date passée »** (§2.2,
   cible : empreinte égale) n'a pas de mesure.

**Objectif** : à la fusion, trois choses sont vraies.
- Un **consommateur du bus** alimente le silver : une table Iceberg par
  entité, où chaque ligne est une version datée d'une ligne de la source
  (SCD2 sur la date d'observation, PRD §6.5). Il est idempotent, et une
  reprise après une coupure donne le même silver.
- Une commande répond à **« état à une date »** pour une entité, et une
  autre **vérifie** que l'état reconstruit au moment de chaque archive
  retenue est égal à son snapshot normalisé, recalculé depuis le bronze.
- Sur un clone neuf, après `make demo`, une cible du `Makefile` construit
  le silver du jeu de démo et finit par cette vérification, conforme sur
  les 18 archives retenues du jeu. La CI la lance.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Iceberg et DuckDB** (PRD §10.1). Le silver est une table Iceberg par
  entité, en Parquet, dans un **entrepôt local** : un dossier sous `data/`,
  hors de git (`data/lakehouse` par défaut, `data/demo/lakehouse` pour la
  démo). **Aucun service** : ni serveur de catalogue, ni stockage objet, ni
  nouvelle image Docker. Le catalogue est local, lui aussi (§0 A).
- **Pas de MinIO.** Le colima porte `alamel-dev-minio` (ports 9000-9001),
  qui appartient à Alamel : le projet ne s'en sert jamais, n'en lance pas un
  autre, et rien ne vise ces ports.
- **L'axe du temps est la date d'observation** (PRD §6.5). Une version vaut
  de la date d'observation de l'événement qui l'ouvre à celle de
  l'événement qui la ferme, borne de fin exclue. La date de la source est
  gardée dans chaque version, sans servir d'axe. **Les snapshots d'Iceberg
  ne servent pas à « l'état à une date »** : ils datent l'écriture, qui
  diffère de l'observation dès qu'on rejoue.
- **Les valeurs restent des chaînes**, telles que l'événement les porte :
  la forme canonique, ou la valeur brute quand le type ne sait pas la lire
  (PRD §6.2). Le silver ne type rien, sinon il devrait choisir quoi faire
  d'une valeur illisible. Typer les colonnes est le travail du gold
  (mission 06).
- **Le consommateur lit le bus et n'y écrit rien.** Le schéma d'événement
  v1, les contrats, la normalisation, l'enveloppe, les topics et la
  publication **ne changent pas**. La file des messages en échec n'est pas
  consommée par le silver.
- **Les fichiers d'événements restent la référence** (PRD §7.1). Le silver
  se construit aussi en appliquant les fichiers d'événements, avec la
  **même fonction** d'application : seule la source des événements change.
  Un test montre que les deux chemins donnent le même silver.
- **La vérification contre l'archive ne passe pas par les événements.**
  Sa référence est le snapshot normalisé de chaque archive retenue,
  recalculé depuis le bronze, comme `verifier-bus --racine`.
- **Les tests unitaires restent hors réseau et hors Docker.** Les tests qui
  ont besoin du courtier sont marqués `integration`. Aucune extension de
  DuckDB ne se télécharge, ni dans les tests, ni dans les commandes (§0 A).
- **Tout se fait sur le Mac.** La chaîne tourne sur l'hôte avec uv, comme à
  la mission 04. `make` reste à beko et à la CI : tu en relis la simulation
  (`make -n`) et lances toi-même les commandes qu'elle affiche.
- **Le colima est toujours partagé avec Alamel** (`alamel-dev-postgres` sur
  5432, `alamel-dev-minio` sur 9000-9001). Rien ne change par rapport aux
  missions 03 et 04 : projet `pharmaflux` partout, `--pull never`, aucune
  commande qui vise un autre conteneur, volume ou image. Toute commande
  qui efface un volume attend la réponse de beko.

## Sources de données pour cette mission

- **Le jeu de démo** `demo/archive` : c'est la source principale de la
  mission, de ses tests et de sa démonstration. 22 archives, dont 18
  retenues et 4 écartées par le garde-fou de volume.
- **L'archive du Mac, en lecture seule** (`$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data`), pour la non-régression et une mesure de mémoire sur
  plus long que le jeu. Tu n'y écris jamais rien.
- **Aucune requête réseau vers les sources** (BDPM, data.gouv, HAS). Le seul
  trafic réseau de la mission va vers le Redpanda local, plus
  l'installation des dépendances verrouillées par `uv`.

## §0 — Points à trancher avant de coder

Réponds point par point dans `docs/rapports/mission-05/points-a-trancher.md`,
commite, puis arrête-toi. Pour chaque point : un constat (ce que tu as
vérifié et comment), ton avis, et ta question s'il y en a une.

- **A. Les bibliothèques et le catalogue.**
  - Le choix attendu est PyIceberg (avec PyArrow) et DuckDB. Donne pour
    chacun la version proposée, sa date de publication, la taille des
    roues, et leur disponibilité pour macOS arm64 et Linux amd64 (la CI).
    Ces versions doivent avoir au moins deux semaines.
  - **Le catalogue** : le catalogue SQL de PyIceberg sur un fichier SQLite
    dans l'entrepôt est-il le bon choix ? Compare-le à ce que PyIceberg
    offre d'autre sans serveur.
  - **La lecture par DuckDB** : l'extension `iceberg` de DuckDB se
    télécharge à la première utilisation, ce qui est exclu. Vérifie
    comment lire le silver sans elle (un scan PyIceberg vers Arrow, puis
    DuckDB sur la table Arrow, par exemple), et dis ce que cela coûte en
    mémoire et en temps sur la plus grosse entité.
- **B. Le schéma d'une table du silver.** Propose les colonnes d'une
  version : l'identité de la ligne, les colonnes du contrat, la date de la
  source, le début et la fin de validité, l'identifiant de l'événement qui
  ouvre la version et de celui qui la ferme, l'archive, la version du
  contrat, les anomalies de la ligne. Dis aussi :
  - comment s'écrit l'identité d'un fichier sans clé unique (empreinte et
    rang, PRD §6.3) ;
  - ce qui arrive à une table quand la version du contrat de son entité
    change (nouvelle table, colonnes ajoutées, refus) ;
  - le partitionnement (aucun, pour ces volumes ?) et le nom des tables.
- **C. L'application d'un lot d'événements (SCD2).** Décris l'algorithme :
  - une `creee` ouvre une version, une `modifiee` ferme la version ouverte
    et en ouvre une autre, une `supprimee` ferme la version ouverte ;
  - ce qui est refusé : une `modifiee` ou une `supprimee` sans version
    ouverte, une `creee` sur une identité déjà ouverte. Dis le code de
    sortie et ce que le message montre ;
  - **l'ordre** : le bus garantit l'ordre par clé (une partition par clé,
    PRD §6.4), pas l'ordre global. Montre que l'ordre par clé suffit au
    SCD2, y compris pour un fichier sans clé unique, où une `supprimee` et
    la `creee` qui la remplace ont des identités différentes (ADR 0006) ;
  - **l'écriture dans Iceberg** : fermer une version, c'est réécrire une
    ligne existante. Compare ce que PyIceberg permet (écrasement filtré,
    `upsert`, réécriture de la table entière) et son coût sur l'état
    initial (environ 164 000 versions ouvertes d'un coup) et sur un
    changement de quelques lignes ;
  - les **doublons** : un événement déjà appliqué, reconnu à son
    identifiant, ne change rien ;
  - la taille d'un lot, et ce qui fait un commit Iceberg.
- **D. Le consommateur du bus.** Propose la commande (nom, options), puis :
  - **les positions lues** (offsets) : où sont-elles gardées ? La
    proposition de l'IeC est de les écrire dans le commit Iceberg qui
    applique le lot (propriétés du snapshot), et de repartir de là au
    redémarrage, sans groupe de consommateurs ni commit sur le courtier.
    Le silver et la position avancent alors ensemble, et une coupure entre
    les deux n'existe pas. Donne ton avis et l'alternative ;
  - la fin d'une exécution : jusqu'aux offsets de fin lus au départ, comme
    `verifier-bus`, ou en continu avec une option ;
  - ce que fait un message qui n'est pas un événement v1 lisible ;
  - les refus : un entrepôt construit depuis un autre bus, ou un bus
    rebâti après la construction du silver (§0 G).
- **E. La construction depuis les fichiers d'événements.** Option ou
  commande, et le test qui compare les deux chemins : mêmes versions, mêmes
  validités, mêmes identifiants. Ce qui ne peut pas être égal (les
  métadonnées des snapshots d'Iceberg, les noms des fichiers Parquet) est
  dit et exclu de la comparaison.
- **F. « État à une date ».** Propose la commande (nom, arguments,
  options : entité, filtre sur la clé, format de sortie) et son écriture
  des instants (UTC, ISO 8601, ce qu'on accepte et ce qu'on refuse). Que
  répond-elle pour un instant antérieur à la première observation ? Pour
  un instant postérieur à la dernière archive ? Dis si une commande
  d'interrogation SQL du silver (DuckDB) vaut son coût dans cette mission.
- **G. La vérification contre l'archive.** Propose la commande. Pour chaque
  archive retenue de chaque entité, l'état au moment de son observation est
  comparé à son snapshot normalisé, empreinte par empreinte (reprends ce
  que `verifier-bus` sait faire). Dis :
  - comment sont traités les snapshots écartés (aucune version ne doit
    bouger) et les snapshots en attente puis confirmés (leurs événements
    portent la date de leur archive, PRD §6.3) ;
  - ce que vaut un état « juste après » une observation, à la seconde
    près ;
  - la durée et la mémoire attendues sur le jeu de démo ;
  - comment les tests couvrent ce que le jeu ne contient pas (aucune
    `modifiee` ni `creee` après l'état initial, aucun snapshot en attente :
    `demo/README.md`), sur des fixtures ou des événements construits ;
  - comment le silver est aussi comparé au bus ou aux fichiers
    d'événements, si cela apporte quelque chose de plus.
- **H. La reprise et la reconstruction.** Une coupure à n'importe quel
  point (avant, pendant et après un commit Iceberg) donne-t-elle, après
  reprise, le même silver que sans coupure ? Comment le testes-tu sans
  vraie coupure de processus ? Comment rebâtit-on le silver de zéro (option,
  ou effacement du dossier par une cible `make`) ?
- **I. `Makefile` et CI.** Propose la ou les cibles (par exemple
  `make silver`, qui construit le silver du jeu de démo depuis le bus puis
  le vérifie), leurs commandes exactes, et leur place par rapport à
  `make demo` et `make rebatir`. Évalue la durée ajoutée au job
  `integration`. `make` reste compatible avec GNU Make 3.81.
- **J. La mémoire.** Mesure la mémoire résidente maximale du consommateur
  et de la vérification sur le jeu de démo, puis, si c'est faisable sans
  rien écrire dans l'archive, sur la copie du Mac. PyArrow pèse : dis
  combien, et ce qu'il faudrait pour tenir sous 256 Mo un jour sur le VPS
  (sans le faire dans cette mission).
- **K. Toute autre chose** que ta lecture du code, des ADR 0006 à 0008 ou
  du jeu de démo te fait remarquer.

## Décisions (sous réserve du §0)

1. **Dépendances** (§0 A) : PyIceberg, PyArrow et DuckDB, versions
   verrouillées dans `uv.lock`, justifiées dans l'ADR 0009. Aucune autre
   dépendance de production sans justification au §0.
2. **Le silver** (§0 B et C) : une table par entité, le schéma arrêté au
   §0, et une fonction d'application des événements, la même pour le bus
   et pour les fichiers.
3. **Le consommateur du bus** (§0 D et H) : idempotent, avec reprise ; les
   positions lues sont gardées comme arrêté au §0.
4. **« État à une date » et sa vérification** (§0 F et G) : deux commandes.
   La vérification est conforme sur toutes les archives retenues du jeu de
   démo, et une différence donne le code 2.
5. **`Makefile` et CI** (§0 I) : la cible du silver, puis son étape dans le
   job `integration`, après `make demo`. Le job `verifier` ne change pas.
6. **Démonstration sur le Mac** :
   - toi, au palier 2 : sur le bus de la démo, la construction du silver
     depuis le bus, sa comparaison avec le silver construit depuis les
     fichiers, la vérification contre l'archive, avec les temps et la
     mémoire ;
   - beko, au palier 3 : `make rebatir`, `make demo`, puis la cible du
     silver, dont il te transmet la sortie. Tu la cites dans le rapport.
7. **Docs** :
   - ADR 0009 : le silver (catalogue, schéma, SCD2 sur la date
     d'observation, application des événements, positions lues, reprise,
     vérification, ce que le silver ne fait pas) ;
   - `README.md` : une suite à la section « Démo », avec **deux exemples
     réels du jeu** : l'état d'une présentation avant et après l'une des
     suppressions de `CIS_CIP_bdpm.txt` (présente, puis absente), et l'état de
     `CIS_InfoImportantes.txt` le 26/10 juste après 14:17, quand le
     fichier servi vide a été écarté (l'état n'a pas bougé) ;
   - `docs/CONTEXTE.md` et `docs/journal.md`, en fin de fichier. La
     première entrée du journal donne la **correspondance des hashes**
     de `main` réécrits après la fusion de la mission 04 : `aceb5ba` →
     `38589dc` (addendum 1 de la mission 04), `714b673` → `5167314`
     (`git count-objects`), `9ad4b14` → `5c3fe5a` (`make --version`). Les
     documents de la mission 04 citent les anciens.

**Outillage** : les trois dépendances de la décision 1. Toute autre
dépendance, de production ou de test, se justifie au §0.

## Paliers

1. **Silver depuis les fichiers, état à une date, vérification** :
   décisions 1, 2 et 4.
   - Les dépendances, le schéma, la fonction d'application, la
     construction depuis les fichiers d'événements.
   - Les deux commandes, testées sur les fixtures et sur `demo/archive`
     (événements calculés dans un dossier jetable).
   - Python pur, aucune commande `docker`.
   - L'entrée du journal sur les hashes.
   - Rapport, commit.
2. **Consommateur du bus** : décision 3.
   - Tests unitaires sur le bus simulé de la mission 03 : positions lues,
     doublons, reprise après une coupure simulée à chaque étape, refus.
   - Tests d'intégration sur le vrai courtier.
   - Ta démonstration de la décision 6, et les mesures de mémoire (§0 J).
   - Rapport, commit.
3. **`Makefile`, CI, docs** : décisions 5, 6 (beko) et 7.
   - `make -n` de chaque cible nouvelle ou modifiée dans le rapport.
   - L'étape de CI.
   - L'ADR 0009 et les docs, avec la sortie de la cible du silver lancée
     par beko.
   - Rapport, commit.

Après le contrôle du palier 3, la suite est celle du circuit :
1. la relecture (`/relire-mission 05`), jusqu'à « CONFORME » ;
2. `pr.md` ;
3. la **revue finale écrite de l'IeC** (`controle-iec-final.md`) ;
4. la publication et la fusion par beko.

**La mission est close** quand beko, sur le Mac, enchaîne `make rebatir`,
`make demo` et la cible du silver, et que celle-ci finit par une
vérification conforme sur les 18 archives retenues du jeu.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests unitaires | `uv run pytest -q` (les tests d'intégration sautés sans courtier, et dit) |
| tests d'intégration (paliers 2 et 3) | courtier lancé par `docker compose -p pharmaflux up -d --wait --pull never`, puis `uv run pytest -q -m integration` |
| comme la CI | la suite complète avec `GITHUB_ACTIONS=true` (mission 04, écart 9) |
| simulation du `Makefile` (palier 3) | `make -n <cible>` pour chaque cible nouvelle ou modifiée |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck (même version que la CI) | `uvx --from shellcheck-py==0.11.0.1 shellcheck <fichiers .sh touchés>`, si un `.sh` est touché |
| non-régression | `uv run pharmaflux demo verifier` ; `uv run pharmaflux profil` et `uv run pharmaflux questions verifier` sur `~/pharmaflux-data` ; `pharmaflux evenements` sur la copie du Mac, comparé au `diff -r` à la sortie du code fusionné (`1af4ef9`) |

## Hors périmètre

- **Le gold** (fiche médicament, disponibilité courante), les colonnes
  typées et les **contrôles de qualité** : mission 06.
- Open Medic et les indicateurs assurance : **Lot 4**. L'indexation et
  l'assistant : **Lot 3**.
- **Toute exécution sur le VPS**, et toute modification de la collecte. Le
  VPS-1 reste partagé avec la pré-production d'Alamel jusqu'à mi-novembre.
- Tout serveur de catalogue, tout stockage objet (MinIO compris), toute
  nouvelle image Docker, tout téléchargement d'image ou d'extension de
  DuckDB.
- Tout changement du schéma d'événement v1, des contrats, des règles de
  normalisation, de l'enveloppe, des topics ou de la publication ; toute
  écriture sur le bus.
- Toute requête vers les sources ; toute écriture dans l'archive ; toute
  utilisation de l'API Claude.
- **Pas d'usage des VPS d'Alamel**, et rien qui touche aux conteneurs
  d'Alamel du colima (`alamel-dev-postgres`, `alamel-dev-minio`) ni à la
  pré-production du VPS-1.

## Addendum 1 — le §0 tranché (28/10/2026)

Réponse au §0 du codeur (`points-a-trancher.md`, commit `7103e8b`). Les
propositions sont retenues, **sauf les deux corrections ci-dessous**. La
première vient d'une lecture de PyPI et de `uv.lock` ; la seconde, d'une
lecture de ce que DuckDB permet. Ce qui n'est pas cité ici est retenu tel
que proposé.

### Corrections

1. **Les versions (A.1) : pas d'`exclude-newer` global.**
   - Le verrou actuel contient déjà quatre paquets publiés après le 14/10 :
     `ruff 0.17.2`, `pluggy 1.7.0`, `certifi 2026.10.23` et
     `ast-serialize 0.13.1`. Un `exclude-newer = "2026-10-14"` les ferait
     redescendre au prochain `uv lock`. Pour ruff, cela change la base du
     lint, ce qui sort de la mission.
   - SQLAlchemy 2.0.46 n'est pas la bonne cible. La dernière 2.0 qui a plus
     de deux semaines est **2.0.54** (15/09/2026). À l'inverse, un
     `exclude-newer` seul choisirait **2.1.4** (07/10/2026), dans une
     branche 2.1 sortie le 24/09.

   La règle retenue :
   - dans `dependencies`, des bornes basses, comme pour les paquets déjà
     là : `pyiceberg[sql-sqlite]>=0.12.0`, `pyarrow>=26.0.0` et
     `duckdb>=1.5.6`. `uv.lock` fixe les versions ;
   - dans `[tool.uv] constraint-dependencies` : `duckdb<2`,
     `sqlalchemy>=2.0.54,<2.1`, plus un plafond pour chaque autre paquet
     transitif **nouveau** publié après le 14/10 (`python-dateutil`,
     `cachetools`, `tzdata` dans ta liste, à revoir au moment du verrou).
     Chaque contrainte porte un commentaire d'une ligne qui donne la
     raison ;
   - au palier 1, le rapport donne la liste des paquets **ajoutés** à
     `uv.lock`, avec leur version et leur date de publication (lue dans
     `upload-time`). Toutes ces dates sont au 14/10/2026 ou avant. Le
     rapport montre aussi que les paquets **déjà** verrouillés n'ont pas
     changé de version : `git diff --stat` du verrou, puis un `awk` sur les
     couples nom et version, avant et après.

   L'ADR 0009 donne la règle : au moins deux semaines pour un paquet ajouté
   ou mis à jour, appliquée par contraintes, sans toucher au reste du verrou.

2. **`silver sql` (F.2) se fait au palier 1, à condition d'être en lecture
   seule.**
   - DuckDB sait écrire (`COPY … TO`, `ATTACH`, `EXPORT DATABASE`), lire
     n'importe quel fichier du poste (`read_csv('/…')`) et installer des
     extensions. Une commande qui exécute du SQL libre doit fermer tout
     cela.
   - Une fois les vues créées, la connexion pose, dans cet ordre :
     `autoinstall_known_extensions = false`,
     `autoload_known_extensions = false`, `allowed_directories` limité au
     dossier de l'entrepôt, `enable_external_access = false`, puis
     `lock_configuration = true`.
   - Les tests montrent un refus pour chacune de ces requêtes :
     - `COPY (SELECT 1) TO '<tmp>/x.csv'` ;
     - `read_csv` d'un fichier hors de l'entrepôt ;
     - `ATTACH` ;
     - `INSTALL iceberg` ;
     - un `SET` après le verrou.

     Ils montrent aussi qu'une vue se lit encore.
   - Si DuckDB 1.5.6 ne permet pas cette combinaison avec des vues
     lisibles, `silver sql` sort de la mission. Tu le dis dans le rapport
     du palier 1, et le README s'appuie sur `silver etat` seul.
   - Le refus quand `plan_files()` rend un fichier de suppression est
     retenu.

### Les questions

- **A.2** : `pyarrow-stubs` en dépendance de dev, version
  `20.0.0.20260819` (19/08/2026). Ces stubs décrivent PyArrow 20, et nous
  verrouillons la 26.
  - Les appels à Arrow restent dans le paquet `pharmaflux.silver`.
  - Si les stubs ne connaissent pas une API de la 26 : un
    `# type: ignore[code]` précis, avec un commentaire.
  - Au-delà de cinq `type: ignore`, tu retires les stubs et tu poses un
    bloc `[[tool.mypy.overrides]]` `module = "pyarrow.*"`, avec
    `ignore_missing_imports`.

  Le rapport du palier 1 dit lequel des deux est retenu et pourquoi.
- **B.1** : `identite` en clé JSON compacte à clés triées, égale à la clé
  du message. **B.2** : `anomalies` en `list<struct<colonne, regle>>`. Le
  refus en cas de changement de version du contrat est retenu, et la
  colonne `version_contrat` reste.
- **C.1** : `LOT = 10 000`, avec une option `--lot`. **C.2** : comme
  proposé. La règle « une seule version ouverte par identité » se vérifie
  au lot sur les identités du lot, et sur toute la table dans
  `silver verifier`.
- **D.1** : l'identifiant de grappe donne un **avertissement**, le contrôle
  des `id` à `offset − 1` donne le **refus**. Au palier 2, le rapport dit si
  un `down -v` change l'identifiant de grappe de Redpanda. **D.2** :
  `--continu` est hors mission. Tu le proposes dans `pr.md`.
- **E** : retenu, y compris `silver comparer A B` au palier 1. Cette
  commande sert à ta démonstration du palier 2.
- **F.1** : code 0 avec le message sur la sortie d'erreur, avant la
  première observation comme après la dernière. Les règles sur les instants
  sont retenues : UTC, à la seconde, refus d'un instant sans fuseau.
- **G** : retenu, y compris :
  - la vérification des archives écartées : l'état est égal à celui du
    dernier snapshot retenu ;
  - les invariants du SCD2 en DuckDB, avec le code 2 si l'un d'eux tombe.

  **Précision sur la décision 7** : le temps de la connaissance est
  l'horodatage de l'archive, à la seconde. Le second exemple du README
  dit donc « le 26/10 juste après 14:17:39 », pas « après 14:17 ». Les
  documents de la mission 04 ne changent pas.
- **H** : retenu. La cale sur `SqlCatalog.commit_table` dépend du code
  interne de PyIceberg. Le test cite en commentaire la version (0.12.0) et
  la fonction visée. S'il casse lors d'une montée de version, c'est voulu :
  il faudra revoir la reprise.
- **I** : retenu. `make silver` ne dépend pas de `demo` ; `make etat` prend
  ses variables ; l'étape de CI vient après `make demo`, avant `down -v`.
  `pr.md` donne la durée réelle de cette étape sur le runner.
- **J, la mémoire** :
  - les commandes `silver` posent l'allocateur système d'Arrow au
    démarrage (K.4) ;
  - la cible des 256 Mo ne vaut pas pour le silver en v1 : il tourne sur le
    Mac, là où est le bus, et le VPS continue de collecter. L'IeC le
    reporte au PRD §9 ;
  - **seuil d'alerte : 512 Mo résidents** pour chaque commande `silver` sur
    le jeu de démo. Si une commande le dépasse, tu t'arrêtes et tu le
    signales avant le commit. Mesures au palier 1 (`construire`,
    `verifier`, `etat`) et au palier 2 (`consommer`) ;
  - la mesure « plus longue que le jeu » est reportée au prochain
    rapatriement. C'est un écart accepté, à écrire dans `pr.md`.

### Précisions

- **Les imports paresseux (K.1) se testent.** Dans un sous-processus,
  après `import pharmaflux.cli`, ni `pyarrow`, ni `pyiceberg`, ni `duckdb`
  ne figurent dans `sys.modules`.
- **La maquette du §0** : le venv jetable, avec des paquets non verrouillés
  installés depuis PyPI, est accepté pour mesurer. Rien n'en entre dans le
  dépôt. Les mesures du palier 1 se refont avec le code de la mission et
  `uv.lock`.
- **Les chemins absolus de l'entrepôt (K.3)** : les tests écrivent sous
  `tmp_path`. Aucun rapport ne cite de chemin du poste.
- **Le découpage des paliers ne change pas.** `construire`, `etat`, `sql`,
  `comparer` et `verifier` vont au palier 1, `consommer` au palier 2.
