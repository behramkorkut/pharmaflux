# Mission 06 — Gold et qualité : colonnes typées, fiche médicament, disponibilité courante, contrôles, questions recalculées

**À :** Claude Opus 5.5 (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.7 §2.1, §2.2, §4 (Lot 2), §6.2, §6.3, §6.5, §7.1, §9,
annexe B · mission 05 (`pr.md`, `controle-iec-final.md`) · ADR 0002, 0003,
0005, 0006 et 0009 · `CLAUDE.md` · `docs/agents/processus.md`
**Statut :** ordre rédigé le 29/10/2026 — **§0 à rédiger**
**Branche :** `mission-06-gold-et-qualite`, dans `pharmaflux-codeur/`
(préparée par beko avec `preparer-mission.sh`). Trois paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Tu es un codeur nouveau sur ce projet : les missions 00 à 05 ont été codées
par une autre session. Lis d'abord `CLAUDE.md`, puis
`docs/agents/processus.md`, puis le PRD v0.7 (§6.5 et l'annexe B ont été
complétés pour cette mission), puis l'ADR 0009, puis cet ordre. Le circuit
est celui de la mission 05, messages directs compris. Tes commits portent
les trailers `Commis-par: codeur` et
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Constat

Le silver est fait sur le Mac : une table Iceberg par entité, historisée
sur la date d'observation, construite depuis le bus ou depuis les fichiers
à l'identique, vérifiée contre l'archive (22/22 sur le jeu de démo).
`make silver` le montre, et la CI le lance. Mais :

1. **Le silver ne parle pas métier.** Une question comme « cette
   présentation est-elle disponible, et quelles alternatives du même groupe
   générique le sont ? » demande de joindre cinq tables à la main, en SQL,
   sur des chaînes. La fiche médicament, que le Lot 3 doit indexer, n'existe
   pas.
2. **Rien n'est typé.** Le silver garde les valeurs en chaînes, comme
   tranché à la mission 05 (ADR 0009). Une date, un prix ou un taux ne se
   comparent pas encore comme tels.
3. **Aucun contrôle de qualité ne tourne sur l'état.** Les contrats
   contrôlent chaque fichier à la lecture, mais personne ne vérifie qu'à un
   instant donné les clés sont uniques, que les présentations renvoient à
   des spécialités connues, ni que les volumes sont plausibles.
4. **Le jeu de questions est encore calculé depuis le bronze seulement.**
   L'annexe B du PRD demande, à partir du Lot 2, le même calcul depuis le
   gold, et que les deux concordent.

**Objectif** : à la fusion, quatre choses sont vraies.
- Pour chaque entité, le gold donne l'**état typé** du silver à un instant
  donné.
- Deux **vues métier** existent, interrogeables à un instant : la **fiche
  médicament** et la **disponibilité courante**.
- Une commande lance les **contrôles de qualité** à un instant. Elle sort
  en erreur sur un contrôle bloquant, et affiche les autres.
- Les **25 questions** du jeu v0 qui attendent une réponse sont
  recalculées depuis le gold, chacune à l'instant de son archive, et
  **concordent** avec le calcul depuis le bronze. Sur un clone neuf, une
  cible du `Makefile` le montre après `make silver`, et la CI la lance.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Le gold se calcule depuis le silver, sur le Mac.** Il ne lit ni le bus,
  ni les fichiers d'événements, ni le bronze. La seule exception est la
  vérification des questions, dont la référence est le bronze, comme
  aujourd'hui. Aucun service, aucune image, aucune extension DuckDB
  téléchargée. DuckDB n'a aucun accès aux fichiers : les tables lui sont
  données par Arrow, connexion verrouillée, comme `silver sql` (ADR 0009).
- **« État à une date » vaut pour tout le gold.** Chaque vue gold se
  calcule à un instant, avec la règle de validité du silver (début inclus,
  fin exclue). Par défaut, c'est l'instant de la dernière observation du
  silver. Les instants s'écrivent comme pour `silver etat`.
- **Une valeur illisible n'est jamais devinée.** Le type d'une colonne vient
  de son contrat. Une valeur que ce type ne sait pas lire donne une colonne
  typée vide. La valeur brute reste lisible dans le silver, et le contrôle
  de qualité compte ces valeurs, colonne par colonne. La forme canonique du
  silver (PRD §6.2) est la seule entrée du typage : on ne relit pas les
  graphies de la source.
- **Les jointures sont externes** (PRD §6.3). Un CIS cité par un fichier et
  absent du référentiel des spécialités n'est pas une erreur : il se compte.
- **La disponibilité reste prudente** (ADR 0003, revue avant le 07/12). Une
  ligne sans CIP13 vise toutes les présentations de la spécialité, et le
  gold le dit (une colonne qui le marque), sans en tirer plus. L'absence de
  signalement n'est pas « disponible » : la vue distingue « aucun
  signalement » d'un statut déclaré.
- **Le silver, les événements, le bus et les contrats ne changent pas.** Le
  jeu de questions v0 non plus : il reste rejouable tel quel depuis le
  bronze.
- **Les tests restent hors réseau et hors Docker**, sauf ceux marqués
  `integration`. Les tests du gold partent d'un silver construit sur les
  fixtures par `silver construire`, et pour le jeu de démo, d'un silver
  construit dans un dossier jetable.
- **Le colima est toujours partagé avec Alamel** (`alamel-dev-postgres` sur
  5432, `alamel-dev-minio` sur 9000-9001). Rien ne change par rapport aux
  missions 03 à 05 : projet `pharmaflux` partout, `--pull never`, aucune
  commande qui vise un autre conteneur, volume ou image. Toute commande qui
  efface un volume attend la réponse de beko.
- **Dépendances** : aucune nouvelle dépendance de production n'est
  attendue (PyArrow, PyIceberg et DuckDB sont là). Toute autre dépendance se
  justifie au §0, avec la règle des deux semaines et des plafonds
  temporaires de l'ADR 0009.

## Sources de données pour cette mission

- **Le jeu de démo** `demo/archive` : la source principale de la mission,
  de ses tests et de sa démonstration. Les 25 archives citées par les
  questions v0 y sont toutes.
- **L'archive du Mac, en lecture seule** (`$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data`), pour la non-régression. Tu n'y écris jamais rien.
- **Aucune requête réseau vers les sources** (BDPM, data.gouv, HAS).

## §0 — Points à trancher avant de coder

Réponds dans `docs/rapports/mission-06/points-a-trancher.md` : pour chaque
point, ton **constat** (mesuré sur le jeu de démo quand c'est possible,
avec la commande), ton **avis**, et tes **questions**. Rien n'est codé
avant l'addendum de l'IeC. Tu peux construire un silver du jeu dans un
dossier jetable pour mesurer, et lancer `silver sql` dessus.

**A. Le typage.** Pour chacun des neuf types des contrats (ADR 0002) : le
type Arrow proposé et la règle de conversion depuis la forme canonique.
Points précis :
- les décimaux : un `decimal128` à précision fixe, ou un `float64` ? Un prix
  ne doit pas devenir `1.1600000000000001` ;
- les listes (`taux_remboursement`, `voies_administration`,
  `titulaires`) : quel séparateur dans la forme canonique, et une
  `list<string>` suffit-elle ?
- les énumérations : en `string`, ou en `dictionary` ?
- les dates : un `date32`.

Mesure le nombre de valeurs illisibles par colonne sur l'état du jeu à la
dernière observation : c'est ce que le contrôle de qualité affichera.

**B. La forme du gold.** L'IeC penche pour un gold **calculé à la
demande** depuis le silver à un instant, sans table gold stockée : le gold
n'a pas d'histoire propre, donc rien à garder cohérent. Donne ton avis,
mesures à l'appui : le temps de la fiche médicament pour le jeu entier, et
sa mémoire. Si tu proposes une matérialisation (une table Iceberg du gold
courant, par exemple), dis ce qu'elle apporte, ce qu'elle coûte, et
comment elle reste juste quand le silver avance.

**C. Les colonnes typées par entité.** Le nom des vues (le nom court du
silver, ou un préfixe ?), les colonnes de version gardées (`debut_validite`
et `date_source` au moins, pour qu'une réponse soit datée) et le traitement
des trois fichiers sans clé unique.

**D. La fiche médicament.** Le grain (une ligne par CIS ?), et la liste
des colonnes, pour chaque entité qui y entre :
- les présentations, avec leurs prix et leurs taux ;
- la composition (substances et dosages) ;
- le groupe générique ;
- les conditions de prescription ;
- les avis SMR et ASMR (tous, ou le plus récent par indication ?), avec les
  liens vers les avis de la commission de la transparence ;
- le statut MITM ;
- la disponibilité ;
- les informations importantes en cours à l'instant demandé.

Précise les structures imbriquées (`list<struct>`) ou les colonnes plates,
et ce qui sert au Lot 3 (une fiche qu'on peut transformer en texte, avec sa
source et sa date). Les CIS cités ailleurs mais absents de
`CIS_bdpm.txt` : fiche partielle, ou pas de fiche ? Compte-les sur le jeu.

**E. La disponibilité courante.** Le grain (la présentation, la fiche
ANSM ?), l'expansion d'une ligne sans CIP13 vers toutes les présentations
de la spécialité, une présentation visée par plusieurs fiches, les cinq
lignes en doublon (ADR 0006), et la distinction entre « aucun signalement »
et « remise à disposition ». Compte, sur le jeu, les présentations
couvertes par expansion.

**F. Les alternatives.** L'annexe B prévoit une liste issue du gold
(groupe générique × présentations × disponibilité). Est-ce une troisième
vue, ou une requête sur les deux autres ? Elle sert le Lot 3, et elle ne
recommande rien.

**G. Les contrôles de qualité.** La liste des contrôles, leur requête, et
pour chacun : **bloquant** ou **mesuré**, avec la règle qui le classe. Au
moins :
- l'unicité des clés déclarées uniques, à l'instant ;
- les présentations dont le CIS est absent des spécialités ;
- les CIS des autres fichiers absents des spécialités ;
- les volumes par entité, comparés à quoi (le dernier snapshot retenu, les
  bilans, une plage) ;
- les valeurs illisibles par colonne.

Donne les chiffres du jeu pour chacun. Un contrôle bloquant qui tomberait
sur le jeu de démo est un constat à remonter, pas une raison de
l'assouplir.

**H. Les questions depuis le gold.** Comment une question v0 (une entité,
une clé, des colonnes, des lignes **brutes** attendues) se recalcule depuis
le gold à l'instant de son archive, et comment les valeurs brutes attendues
se comparent aux valeurs du gold (normalisation par le contrat, puis
typage ?). Ce que devient une question dont le résultat diffère : un code
d'erreur, et les deux calculs affichés. Une option de `questions verifier`,
ou une commande à part ? Combien des 25 questions passent par une vue
métier, et combien par les colonnes typées seulement ?

**I. Les commandes.** Les noms, les options et les formats de sortie (le
groupe `pharmaflux gold`, comme `silver`), et la commande SQL : réutiliser
`silver sql` avec les vues gold en plus, ou une commande à part.

**J. `Makefile` et CI.** La cible (le nom : `make gold`, `make qualite` ?),
ce qu'elle enchaîne après `make silver`, son étape dans le job
`integration` et la durée ajoutée estimée.

**K. La mémoire.** La fiche médicament joint onze tables : mesure-la sur
le jeu, contre le seuil de 512 Mo de l'ADR 0009.

**L. Autre.** Tout ce que cet ordre n'a pas vu.

## Décisions (sous réserve du §0)

1. **Colonnes typées** (§0 A et C) : pour chaque entité, l'état typé à un
   instant, sans deviner une valeur.
2. **Vues métier** (§0 B, D, E et F) : la fiche médicament et la
   disponibilité courante, à un instant.
3. **Qualité** (§0 G) : une commande, code 2 sur un contrôle bloquant ;
   les contrôles mesurés sont affichés.
4. **Questions depuis le gold** (§0 H) : les 25 questions concordent sur
   le jeu de démo, et une discordance donne le code 2.
5. **`Makefile` et CI** (§0 J) : la cible, puis son étape dans le job
   `integration`, après `make silver`. Le job `verifier` ne change pas.
6. **Démonstration sur le Mac** :
   - toi, au palier 2 : sur le silver du jeu, la fiche médicament et la
     disponibilité courante à deux instants, les contrôles de qualité et
     les questions, avec les temps et la mémoire ;
   - beko, au palier 3 : `make rebatir`, `make demo`, `make silver`, puis
     la cible du gold. Il te transmet la sortie, et tu la cites dans le
     rapport.
7. **Docs** :
   - ADR 0010 : le gold (forme, typage, vues, contrôles, questions, ce que
     le gold ne fait pas) ;
   - `README.md` : une suite à la section « Le silver », avec **deux
     exemples réels du jeu**. Le premier : la fiche d'une spécialité, à un
     instant. Le second : la disponibilité courante d'une présentation
     couverte par une ligne sans CIP13 ;
   - `docs/CONTEXTE.md` et `docs/journal.md`, en fin de fichier. La
     **première entrée du journal** donne la durée de l'étape `make silver`
     dans la CI, que `pr.md` de la mission 05 laissait à reporter :
     **37 s** sur la PR #6, **38 s** sur `main` après la fusion (`make demo`
     dure 1 min 50 s dans le même job).

**Outillage** : aucune dépendance nouvelle attendue (§0 L sinon).

## Paliers

1. **Colonnes typées et contrôles de qualité** : décisions 1 et 3.
   - Le typage de chaque entité, à un instant.
   - Les contrôles, et leur commande.
   - Les tests sur les fixtures, puis sur `demo/archive`, avec un silver
     construit dans un dossier jetable.
   - Python pur, aucune commande `docker`.
   - L'entrée du journal sur la durée de la CI.
   - Rapport, commit.
2. **Vues métier et questions** : décisions 2 et 4.
   - La fiche médicament, la disponibilité courante, et les alternatives
     si le §0 les retient.
   - Les questions recalculées depuis le gold, et la concordance des 25.
   - Ta démonstration de la décision 6, et les mesures de mémoire.
   - Rapport, commit.
3. **`Makefile`, CI, docs** : décisions 5, 6 (beko) et 7.
   - `make -n` de chaque cible nouvelle ou modifiée dans le rapport.
   - L'étape de CI.
   - L'ADR 0010 et les docs, avec la sortie de la cible lancée par beko.
   - Rapport, commit.

Après le contrôle du palier 3, la suite est celle du circuit :
1. la relecture (`/relire-mission 06`), jusqu'à « CONFORME » ;
2. `pr.md` ;
3. la **revue finale écrite de l'IeC** (`controle-iec-final.md`) ;
4. la publication et la fusion par beko.

**La mission est close** quand beko, sur le Mac, enchaîne `make rebatir`,
`make demo`, `make silver` et la cible du gold, et que celle-ci finit avec
des contrôles de qualité sans bloquant et les 25 questions concordantes.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests unitaires | `uv run pytest -q` (les tests d'intégration sautés sans courtier, et dit) |
| tests d'intégration (paliers 2 et 3) | courtier lancé par `docker compose -p pharmaflux up -d --wait --pull never`, puis `uv run pytest -q -m integration` |
| comme la CI | la suite complète avec `GITHUB_ACTIONS=true` |
| simulation du `Makefile` (palier 3) | `make -n <cible>` pour chaque cible nouvelle ou modifiée |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck (même version que la CI) | `uvx --from shellcheck-py==0.11.0.1 shellcheck <fichiers .sh touchés>`, si un `.sh` est touché |
| non-régression | `uv run pharmaflux demo verifier` ; `uv run pharmaflux profil` et `uv run pharmaflux questions verifier` sur `~/pharmaflux-data` ; `pharmaflux evenements` sur la copie du Mac, comparé au `diff -r` à la sortie du code fusionné (`53f261b`) ; `silver verifier` sur le jeu, 22/22 |

## Hors périmètre

- **Les indicateurs assurance** et Open Medic : **Lot 4**. L'indexation,
  l'API, l'interface et l'assistant : **Lot 3**. Le gold de cette mission
  est ce qu'ils liront.
- Tout changement du silver, du schéma d'événement v1, des contrats, de la
  normalisation, de l'enveloppe, des topics ou de la publication ; toute
  écriture sur le bus.
- Toute nouvelle version du jeu de questions : la v1 est prévue au Lot 3
  (PRD, annexe B).
- **Toute exécution sur le VPS**, et toute modification de la collecte. Le
  VPS-1 reste partagé avec la pré-production d'Alamel jusqu'à mi-novembre.
- Tout serveur, tout stockage objet (MinIO compris), toute nouvelle image
  Docker, tout téléchargement d'image ou d'extension de DuckDB.
- Toute requête vers les sources ; toute écriture dans l'archive ; toute
  utilisation de l'API Claude.
- **Pas d'usage des VPS d'Alamel**, et rien qui touche aux conteneurs
  d'Alamel du colima (`alamel-dev-postgres`, `alamel-dev-minio`) ni à la
  pré-production du VPS-1.
