# Mission 09 — Le corpus des avis HAS : collecte des pages d'avis, extraction, indexation, citation, jeu de questions v2

**À :** Claude Opus 5.5 (codeur, session neuve) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v1.0 §2.2, §4 (Lot 3), §6.1, §6.7, §6.8, §7.4, §7.5, §9,
annexes A et B · mission 08 (`pr.md`, `controle-iec-final.md`) · ADR 0003,
0004, 0011 et 0012 · `evaluation/README.md` · `CLAUDE.md` ·
`docs/agents/processus.md`
**Statut :** ordre rédigé le 31/10/2026 — §0 rendu (`5cb8f9d`), tranché
par l'**addendum 1** (en fin de fichier) — **palier 1 ouvert**
**Branche :** `mission-09-corpus-des-avis-has`, dans `pharmaflux-codeur/`
(préparée par beko avec `preparer-mission.sh`). Trois paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Tu n'as pas codé les missions précédentes dans cette session. Lis, dans
l'ordre :
1. `CLAUDE.md` et `docs/agents/processus.md` (le circuit, et le modèle de
   rapport revu le 31/10) ;
2. le PRD v1.0 : §4 (Lot 3), §6.7 et §6.8 (ce que les missions 07 et 08
   ont fait, et ce qui est précisé pour celle-ci), §7.5, annexe B ;
3. l'ADR 0004 (le corpus HAS), l'ADR 0011 (l'index) et l'ADR 0012
   (l'assistant) ;
4. `docs/rapports/mission-08/pr.md` et
   `docs/relectures/mission-08/controle-iec-final.md` : ce que la mission 08
   a mesuré, et ce qu'elle te laisse ;
5. cet ordre.

Tes commits portent les trailers `Commis-par: codeur` et
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Le relecteur
sera Claude Fable 5.1, un autre modèle que toi.

## Constat

L'assistant répond : 44 bonnes réponses sur 49, aucune citation invalide,
aucun conseil médical, 1,03 $ pour l'évaluation complète. Mais il ne sait
de la HAS que ce que la BDPM en recopie :

1. **Un avis n'est qu'une ligne.** Les fichiers SMR et ASMR donnent le
   niveau, la date et le libellé de l'indication. Le motif de l'avis, sa
   synthèse, ce que la Commission a regardé, sont sur la page de l'avis,
   que personne ne lit. L'annexe B prévoit des questions sur ce texte.
2. **Le lien n'est pas rendu.** La licence de la HAS demande de citer la
   source et la date de dernière mise à jour (ADR 0004). L'assistant rend
   le fichier et la date de la BDPM, pas la page de l'avis. Cinq questions
   de la v1 sont passées en abstention parce que la réponse attendue était
   un lien.
3. **La mission 08 laisse des constats** que l'on n'a pas encore le droit
   de corriger : quatre dates omises (`avis_has-007`, `-011`,
   `disponibilite-012`, `historique-005`), un rappel manqué
   (`avis_has-003`, OZEMPIC), une estimation des jetons d'entrée minorée
   d'un facteur 2, et `disponibilite-005` à harmoniser avec
   `avis_has-005`. Ils ont été trouvés sur la v1 : la v1 ne peut pas, seule,
   prouver qu'on les a corrigés.

**Objectif** : à la fusion, quatre choses sont vraies.
- Une **collecte des pages d'avis** existe, polie envers le site, archivée
  comme le bronze de la BDPM, et elle a constitué la **première étape** du
  corpus de l'ADR 0004 (les dossiers avec un avis depuis 2024), lancée par
  beko.
- Le texte de ces pages est **extrait sans altération** et **indexé** à
  côté des fragments de la fiche, avec sa mise à jour par incréments et sa
  vérification, sur le jeu de démo comme sur le Mac.
- L'assistant **cite une page d'avis** avec son URL, la date de l'avis et
  la date de la collecte, rendues par le code.
- Le **jeu de questions v2** dépasse la centaine, avec des questions sur
  le texte des avis et des questions neuves qui mesurent les correctifs de
  la mission 08. L'évaluation complète de la v1 et de la v2 a tourné sous
  le plafond.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Le corpus est celui de l'ADR 0004** : les pages HTML d'avis
  (`/jcms/p_N`, `/jcms/c_N`) que donne `HAS_LiensPageCT_bdpm.txt`, et
  d'abord les dossiers avec un avis SMR ou ASMR **daté de 2024 ou après**.
  Le reste du corpus (environ 10 000 pages) n'est pas dans cette mission.
- **Les PDF d'avis ne sont pas collectés** dans cette mission. Le §0 en
  mesure le besoin (point J) ; une collecte de PDF serait une mission à
  elle.
- **La politesse envers le site** (ADR 0004, `CLAUDE.md`) :
  - `robots.txt` est lu au début de chaque passage, et un chemin interdit
    n'est jamais demandé ;
  - les requêtes partent **en série**, avec une pause d'au moins **deux
    secondes**, et le `User-Agent` du projet (celui de la collecte de la
    BDPM) ;
  - les redirections ne sont pas suivies pour les pages d'avis ; une page
    qui redirige, disparaît ou change de forme est une **erreur visible**,
    pas un silence ;
  - **une page déjà archivée n'est pas redemandée** dans cette mission ;
  - une commande de collecte a un **plafond de requêtes** explicite, et
    s'arrête net à la première réponse 429 ou 5xx répétée.
- **L'archive est immuable**, comme le bronze de la BDPM : une page est
  écrite à l'octet, avec son empreinte, l'URL demandée, l'heure de la
  collecte et la réponse HTTP, dans un manifeste en ajout seul. Les pages
  vivent sous `$PHARMAFLUX_DATA` (sinon `~/pharmaflux-data`), hors de git.
- **Qui fait quelle requête** :
  - **toi, au §0 seulement** : **douze requêtes au plus** vers
    `www.has-sante.fr`, et aucun autre hôte. D'abord `robots.txt`, puis des
    pages d'avis variées (les deux formes d'URL, des années différentes, un
    dossier à plusieurs spécialités), et au plus **trois** liens de document
    suivis une fois jusqu'à leur réponse finale, en `HEAD` quand le
    serveur le permet, pour mesurer les PDF. En série, deux secondes de
    pause, avec le `User-Agent` du projet. Chaque requête est consignée
    dans le §0 : heure UTC, URL, statut, taille, sha256. Les réponses
    deviennent des **fixtures** (`tests/fixtures/has/`), avec leur source et
    leur date ;
  - **beko, ensuite** : la collecte de la première étape, sur le Mac,
    par une commande que tu as écrite et testée (palier 1). Elle écrit dans
    `$PHARMAFLUX_DATA`, où tu ne fais que lire ;
  - **aucune autre requête** vers la HAS, la BDPM ou data.gouv ne part de
    ta session, ni des tests, ni de la CI, ni de `make up`.
- **Le texte n'est pas altéré** (licence de la HAS) : ce qui est extrait
  d'une page est repris tel quel, sans résumé ni reformulation par un LLM.
  Les espaces et les entités HTML se normalisent ; le sens, jamais. Chaque
  extrait garde l'URL, la date de l'avis et la date de la collecte.
- **L'extraction est déterministe** et testée sur des pages réelles : les
  mêmes octets donnent le même texte. Une page dont la structure attendue
  manque est **rejetée avec son motif**, comptée et rendue, jamais devinée.
- **L'assistant reste gouverné comme à la mission 08** : il ne lit que des
  fragments de l'index ; les faits viennent des fragments, jamais du LLM ;
  les citations sont vérifiées par le code ; les sources, leurs dates et
  l'instant de l'index sont rendus par le code ; le refus médical et les
  abstentions dures se décident d'abord hors du LLM. Le texte d'un avis
  parle souvent de malades, d'indications et de traitements : **il ne fait
  pas d'une question médicale une question permise**.
- **Le code rend le lien de chaque fragment cité.** Pour un fragment d'avis
  HAS : l'URL de la page, la date de l'avis et la date de la collecte (la
  licence l'exige). Pour un fragment de la fiche qui porte un lien (la
  fiche ANSM, la page de l'avis dans `avis`) : ce lien. La mission 08
  l'avait proposé pour la mission 10 ; la licence le demande dès que l'on
  cite la HAS, il vient donc ici.
- **Une correction se mesure sur des questions qui n'ont pas servi à la
  trouver.** Toute retouche du prompt, de la recherche ou du contrôle qui
  répond à un constat de la mission 08 est mesurée sur des questions
  neuves de la v2, écrites et figées **avant** la retouche. La v1 reste
  rejouable telle quelle et ses chiffres sont rendus à côté, jamais à la
  place.
- **Budget : 10 $ au plus** pour toute la mission (PRD §7.5), dans le même
  journal des dépenses que la mission 08, sur les crédits qui **expirent le
  16/11/2026 (UTC)** : les appels de la mission partent avant cette date.
  La porte budgétaire, le cache des réponses et la clé (trousseau de beko,
  `avec-cle.sh` lancé par beko seul) ne changent pas. **Aucun appel réel ne
  part d'une session d'agent.**
- **Les tests et la CI n'appellent ni l'API, ni le réseau.** La CI construit
  l'index du jeu de démo avec le sous-ensemble d'avis du dépôt (point E).
- **Le gold, le silver, les événements, le bus, les contrats et la
  normalisation ne changent pas.** L'index change de format pour accueillir
  les avis (ADR 0011 : un format qui change est une collection de plus).
- **Le jeu v0 et le jeu v1 restent rejouables tels quels.** La v2 est un
  nouveau fichier.
- **Le colima est toujours partagé avec Alamel** (`alamel-dev-postgres`
  sur 5432, `alamel-dev-minio` sur 9000-9001). Projet `pharmaflux` partout,
  `--pull never`. Toute commande qui efface un volume attend la réponse de
  beko. `make` ne tourne chez toi qu'en `make -n`.
- **Dépendances** : un analyseur HTML, s'il en faut un, se justifie au §0
  avec la règle des deux semaines et les plafonds de l'ADR 0009. La
  bibliothèque standard (`html.parser`) est la première option à mesurer.
- **La coupure du registre** : la règle de la mission 07 tient (réessai
  borné, diagnostic). La CI de la PR doit passer du premier coup.

## Sources de données pour cette mission

- **`www.has-sante.fr`**, dans les seules limites ci-dessus : douze requêtes
  au §0 par toi, puis la collecte de la première étape par beko.
- **L'archive du Mac, en lecture seule** (`$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data`) : la dernière archive de `HAS_LiensPageCT_bdpm.txt`,
  de `CIS_HAS_SMR_bdpm.txt` et de `CIS_HAS_ASMR_bdpm.txt` pour choisir les
  dossiers ; les pages collectées par beko ; la non-régression.
- **Le jeu de démo** et ce qu'en tirent `make silver`, `make gold` et
  `make index`, plus le sous-ensemble d'avis que tu y ajoutes (point E).
- **L'API Claude**, sous le plafond, par les seules commandes de
  l'assistant, lancées par beko.

## §0 — Points à trancher avant de coder

Réponds dans `docs/rapports/mission-09/points-a-trancher.md` : pour chaque
point, ton **constat** (mesuré quand c'est possible, avec la commande), ton
**avis**, et tes **questions**. Rien n'est codé avant l'addendum de l'IeC,
hors le petit script de tes douze requêtes, que tu gardes et cites.
**Aucun appel à l'API au §0.**

**A. La page d'avis.** Sur tes pages réelles :
- les champs utiles et où ils sont (titre, date de publication, date de
  mise à jour, motif, synthèse, indication, niveau de SMR et d'ASMR s'il y
  figure, liens vers les documents), en données structurées
  (`application/ld+json`, `meta`) ou dans le corps ;
- ce qui varie entre `c_N` et `p_N`, et entre les années ;
- la taille brute et la taille du texte utile ;
- la « date de dernière mise à jour » que la licence demande de citer :
  laquelle des dates de la page la porte ?

**B. Le périmètre de la première étape.** Depuis la dernière archive du
Mac, sans réseau :
- le nombre de dossiers avec un avis SMR ou ASMR daté de 2024 ou après,
  avec un lien ; le nombre sans lien ; le nombre de spécialités (CIS)
  concernées ;
- le même décompte sur le jeu de démo, à l'instant de son index ;
- la durée de la collecte, à deux secondes de pause et plus ;
- l'ordre de collecte, et ce qu'on fait d'un dossier à plusieurs liens ou
  d'un lien partagé par plusieurs dossiers.

**C. La collecte.**
- La commande (un groupe `pharmaflux has` ?), ses options (le plafond de
  requêtes, une liste de dossiers, une simulation qui dit ce qu'elle
  demanderait sans rien demander), ses codes de sortie.
- Le client HTTP : celui de la collecte de la BDPM, ou à côté ; délais,
  essais, arrêt sur 429 et 5xx.
- L'archive : l'arborescence, le nom des fichiers, le manifeste, ce que
  garde une réponse en erreur, une redirection, une page vide.
- La **reprise** après une coupure : la commande relancée ne redemande que
  ce qui manque.
- Où elle tournera plus tard (le VPS, après mi-novembre), et ce qui la
  rendra périodique : à proposer, pas à faire.

**D. L'extraction.**
- L'analyseur, et le texte gardé : quels blocs, dans quel ordre, avec
  quelles étiquettes ; ce qui est écarté (menus, pied de page).
- Ce qui fait **rejeter** une page, et comment ce rejet se voit.
- Comment on prouve que le texte n'est pas altéré : un test qui retrouve
  chaque phrase extraite dans la page brute, une fois les balises et les
  entités ôtées ?
- L'extraction est-elle stockée (une couche de plus, dérivée et
  reconstructible) ou recalculée à chaque construction de l'index ?

**E. Le jeu de démo.**
- Le sous-ensemble de pages repris dans `demo/` (à l'octet, avec leur
  manifeste, leur source et leur date, comme le reste du jeu) : le choix
  des dossiers (au moins ceux des questions v2 sur le texte des avis), le
  nombre, la taille sur disque et ce qu'il ajoute au paquet git.
  **Plafond : 10 Mo sur disque pour les pages ajoutées.**
- Comment `make index` et la CI le lisent sans réseau, et comment le
  sous-ensemble se reconstitue depuis l'archive de beko par une commande.

**F. L'index.**
- Le fragment d'avis : un par page, ou un par couple (page, CIS) ? Son
  identifiant, sa section, son texte (les métadonnées et l'extrait), sa
  longueur contre les 512 jetons de multilingual-e5-small, et le
  découpage s'il le faut.
- Le format et la collection neuve ; la recherche lexicale sur ces textes
  plus longs.
- **La mise à jour par incréments** : les fragments d'avis suivent les
  liens et les avis du silver (comme la section `avis` aujourd'hui) **et**
  les pages présentes dans l'archive. Que veut dire « l'instant de
  l'index » quand une page est collectée après la dernière observation du
  silver ? L'index ne doit pas mentir sur ce qu'il sait.
- `index verifier` : l'index mis à jour pas à pas égal à l'index
  reconstruit, avis compris.

**G. L'assistant.**
- Le rendu des liens par le code (fragments d'avis et fragments qui
  portent un lien), et ce que le LLM en sait.
- Ce qui change au prompt système, au contrôle des nombres et des dates
  (le texte d'un avis est plein de dates et de pourcentages), et à la
  sélection des dix fragments.
- **Les constats de la mission 08**, chacun avec ta proposition et la façon
  de la mesurer sur des questions neuves :
  - le rappel par section pour le CIS visé (`avis_has-003`) ;
  - les dates secondaires : dues ou non avec le fait principal ;
  - les tentatives de citation hors des fragments fournis, comptées à part ;
  - les mots courants qui « visent » un CIS (« eau », « fer »…).
- Le refus médical devant une question qui reprend les mots d'un avis
  (« l'avis dit-il que je peux le prendre pendant ma grossesse ? »).

**H. Le jeu de questions v2.**
- Ce qu'elle reprend de la v1, et sous quels identifiants ;
  `disponibilite-005` harmonisée avec `avis_has-005` (réponse avec
  réserve dans les deux cas) ; les cinq questions passées en abstention
  faute de lien.
- Les **questions sur le texte des avis** : combien, sur quoi (le motif, la
  date, ce que dit la synthèse, le lien), et les pièges (un avis plus
  ancien que celui demandé, un dossier sans page, une page rejetée).
- Les **questions neuves qui mesurent les correctifs** de la mission 08 :
  combien, écrites et figées avant toute retouche, et ce qui garantit
  qu'elles n'ont pas servi à la mettre au point.
- Comment leurs attendus se vérifient sans LLM : depuis les pages
  archivées et leur extraction, comme `questions verifier` le fait depuis le
  bronze et le gold.
- Ce que la notation déterministe ajoute : le lien rendu, la date de
  l'avis, une phrase de l'avis retrouvée.

**I. Le coût.**
- **La constante d'estimation des jetons d'entrée**, minorée d'un facteur
  2 à la mission 08 : recalée sur les 65 lignes du journal, avec la
  méthode et l'écart restant.
- Le coût d'une question qui porte des fragments d'avis, et d'une
  évaluation complète de la v1 et de la v2 (l'index change, donc le cache de
  la mission 08 ne sert plus).
- Le plan de dépense, palier par palier, dans 10 $ et avant le 16/11.

**J. Les PDF.** Sur tes trois liens de document : la redirection, le type
et la taille de la réponse finale. Sur les questions v2 sur le texte des
avis : combien la page seule ne permet pas de répondre. Ta recommandation
pour une mission future, chiffrée.

**K. La mémoire et le temps.** Pour chaque commande nouvelle ou modifiée,
sur le jeu et sur la première étape : le résident maximal contre le seuil
de 512 Mo (ADR 0009) et la durée.

**L. Autre.** Tout ce que cet ordre n'a pas vu, en particulier ce que les
pages t'apprennent sur les conditions de réutilisation (un changement des
mentions légales ou de `robots.txt` rouvre l'ADR 0004).

## Décisions (sous réserve du §0)

1. **Collecte des pages d'avis** (§0 B, C) : la commande, l'archive, le
   manifeste, la reprise, ses tests sur les fixtures.
2. **Extraction** (§0 A, D) : le texte, ses rejets, la preuve de non-
   altération.
3. **Index** (§0 E, F) : les fragments d'avis, le format, l'incrément, la
   vérification, le sous-ensemble du jeu de démo.
4. **Assistant** (§0 G) : le rendu des liens, les retouches qui répondent
   aux constats de la mission 08, mesurées sur des questions neuves.
5. **Jeu v2 et évaluation** (§0 H, I) : le fichier, ses attendus vérifiés
   sans LLM, la notation, une évaluation complète de la v1 et de la v2.
6. **`Makefile` et CI** : les cibles, et l'index du jeu de démo avec les
   avis dans la CI.
7. **Lancements par beko sur le Mac** :
   - à la fin du palier 1 : la collecte de la première étape. Tu prépares
     la commande et sa simulation ; beko la lance et te donne la sortie, que
     tu cites (nombre de pages, rejets, erreurs, durée) ;
   - au palier 2 : la démonstration de cinq questions, dont deux sur le
     texte d'un avis et un refus médical ;
   - au palier 3 : la séquence jusqu'à `make index`, puis l'évaluation
     complète de la v1 et de la v2.
8. **Docs** :
   - ADR 0013 : la collecte des avis, l'extraction, les fragments d'avis,
     le rendu des liens, la décision sur les PDF ; et la ligne « remplacé
     par » ou « complété par » de l'ADR 0004 ;
   - `docs/donnees/` : le profil de la page d'avis ;
   - `README.md` : un exemple réel de réponse qui cite un avis HAS, avec
     son lien, et la section « État » ;
   - `evaluation/README.md` pour la v2 ;
   - `docs/CONTEXTE.md`, et `docs/journal.md` en fin de fichier.

## Paliers

1. **Collecte et extraction** : décisions 1 et 2.
   - La commande de collecte, sa simulation, l'archive, la reprise.
   - L'extraction, ses rejets, le test de non-altération.
   - Les tests, tous sur les fixtures du §0, sans réseau.
   - La simulation de la première étape sur la dernière archive du Mac :
     les URL qu'elle demanderait, leur nombre, la durée.
   - Rapport, commit. **Puis beko lance la collecte** (décision 7) ; tu
     cites sa sortie dans un commit à part, avant le palier 2.
2. **Index et assistant** : décisions 3, 4 et 6.
   - Le sous-ensemble d'avis du jeu de démo, tiré de l'archive de beko.
   - Les fragments d'avis, le format, la collection, l'incrément,
     `index verifier`.
   - Le rendu des liens. Les retouches de l'assistant ne viennent
     qu'**après** que les questions neuves du point H sont écrites et
     committées : elles peuvent donc entrer dans ce palier, dans un commit
     qui les précède.
   - Les tests, avec le double du client Claude et l'encodeur de test.
   - La démonstration de beko (décision 7), citée avec ses coûts et ce qui
     reste du plafond.
   - Rapport, commit.
3. **Jeu v2, évaluation, docs** : décisions 5, 6 (le `Makefile`), 7
   (l'évaluation de beko) et 8.
   - Le jeu v2 complet, ses attendus vérifiés sans LLM, la notation.
   - `make -n` de chaque cible nouvelle ou modifiée.
   - L'évaluation complète de la v1 et de la v2, lancée par beko, citée.
   - L'ADR 0013 et les docs.
   - Rapport, commit.

Après le contrôle du palier 3, la suite est celle du circuit :
1. la relecture (`/relire-mission 09`, Claude Fable 5.1), jusqu'à
   « CONFORME » ;
2. `pr.md` ;
3. la **revue finale écrite de l'IeC** (`controle-iec-final.md`) ;
4. la publication et la fusion par beko.

**La mission est close** quand :
- la première étape du corpus est collectée par beko, et ses chiffres
  (pages, rejets, erreurs, durée, requêtes) sont dans `pr.md` ;
- beko, sur le Mac, a enchaîné la séquence jusqu'à `make index`, puis
  l'évaluation complète de la v1 et de la v2, qui finit :
  - **sans aucune citation invalide** ;
  - **sans aucun conseil médical** sur les questions `medical` ;
  - avec **le lien et la date de l'avis** rendus sous chaque réponse qui
    cite une page d'avis ;
  - avec les indicateurs du §2.2 mesurés et écrits dans `pr.md`, pour la v1
    et pour la v2 séparément, qu'ils atteignent leur cible ou non ;
- la dépense de la mission est **sous 10 $**, lue dans le journal, et
  faite avant le 16/11/2026.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests | `GITHUB_ACTIONS=true uv run pytest -q -rE -rs`, services et modèle présents |
| tests d'intégration et du modèle | `uv run pytest -q -rE -m "integration or modele"` |
| aucune requête réseau dans les tests | ce qui le garantit (un test qui échoue si un client HTTP sort), cité |
| simulation du `Makefile` | `make -n <cible>` pour chaque cible nouvelle ou modifiée |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck | si un `.sh` est touché |
| YAML de la CI | si `ci.yml` est touché |
| dépenses | `pharmaflux assistant depenses` : le total de la mission 09, celui du Lot 3, ce qui reste |
| non-régression | `demo verifier` ; `profil` et `questions verifier` sur `~/pharmaflux-data` ; `evenements` contre `beba0c8` ; `silver verifier` 22/22 ; `make gold` sans bloquant et 25 concordantes ; `index verifier` conforme ; la v1 renotée |

## Hors périmètre

- Les PDF d'avis ; le corpus au-delà de la première étape ; une collecte
  périodique des avis (proposée, pas installée) ; l'API, l'interface,
  l'évaluation dans la CI et le test de fraîcheur de bout en bout
  (mission 10) ; les indicateurs de dépense (Lot 4).
- Toute requête vers la HAS au-delà de tes douze requêtes du §0 ; toute
  requête vers la BDPM ou data.gouv ; tout téléchargement en boucle.
- Toute écriture dans l'archive du Mac par toi.
- Tout appel à l'API Claude depuis une session d'agent, les tests ou la
  CI ; tout dépassement du plafond ; toute lecture, tout affichage ou toute
  écriture de la clé.
- Tout résumé ou toute reformulation d'un avis par un LLM avant
  l'indexation.
- Tout changement du gold, du silver, du schéma d'événement v1, des
  contrats, de la normalisation, des topics ou de la publication.
- **Toute exécution sur le VPS**. Le VPS-1 reste partagé avec la
  pré-production d'Alamel jusqu'à mi-novembre.
- **Pas d'usage des VPS d'Alamel**, et rien qui touche aux conteneurs
  d'Alamel du colima (`alamel-dev-postgres`, `alamel-dev-minio`) ni à la
  pré-production du VPS-1.

## Addendum 1 — le §0 tranché (31/10/2026)

Réponse au §0 du codeur (`points-a-trancher.md`, commit `5cb8f9d`). Les
avis sont **retenus**, avec les précisions ci-dessous et **un écart** (G2 :
la durée de traitement selon l'avis est un refus). Ce qui n'est pas cité
ici est retenu tel que proposé.

**Revérifié par l'IeC** :
- le journal `tests/fixtures/has/journal-s0.jsonl` compte **douze
  requêtes**, toutes vers `https://www.has-sante.fr`, en série, avec le
  `User-Agent` du projet. Aucune redirection n'a été suivie par le client :
  chaque saut est une requête comptée. La valeur de `JSESSIONID` est retirée
  des en-têtes ;
- sur les trois archives du 24/10 (`2f01ff1e…`, `c2215af6…`, `f8495540…`),
  un recalcul indépendant donne **746 dossiers** avec un avis SMR ou ASMR de
  2024 ou après, **720** avec un lien, **722** URL. CT-21716 (OZEMPIC) est
  dans les 746, et n'a pas de lien.

**L'écart sur les documents** (un lien suivi jusqu'au PDF au lieu de trois)
est accepté : il va dans le sens de la prudence, et le JSON-LD donne l'URL
directe du PDF, ce qui rend la chaîne de redirection inutile pour une
mission future.

### Ce que l'addendum change dans l'ordre

- **La durée, la dose ou le rythme d'un traitement restent un refus
  médical**, même « selon l'avis » (G2, ci-dessous).
- **`CLAUDE.md`** (ligne « Données ») admet désormais le sous-ensemble de
  pages HAS du jeu de démo et les pages HAS entières des fixtures, avec la
  mention de la HAS. L'IeC l'a écrit sur `main` avec cet addendum.
- **Les indicateurs de l'évaluation** sont rendus en trois blocs : la v1
  telle quelle (88 questions), les questions **nouvelles** de la v2 seules,
  et la v2 entière.

### A. La page d'avis

- **A1 : oui.** Le code rend trois dates : la date de l'avis
  (`datePublished`), la date de mise en ligne comme « date de dernière mise
  à jour » de la licence (« Mis à jour le » à sa place si une page
  l'affiche), et la date de consultation (la collecte).
- Le JSON-LD sert de **contrôle**, jamais de texte : retenu.

### B et C. Le périmètre et la collecte

- **L'ordre de collecte** (date d'avis décroissante, puis dossier, puis URL),
  une requête par URL distincte, la date d'un fragment prise sur **sa
  page** : retenus.
- **C1 : oui** pour les codes de sortie 0 à 3, et pour la politique de
  réessai (un seul réessai, après 10 s, puis l'arrêt au second 5xx). Un
  premier 429 arrête tout.
- **C2 : les mentions légales sont relues à chaque passage réel**, juste
  après `robots.txt` : une requête de plus, comptée dans le plafond. La page
  est archivée comme une autre, et l'empreinte de son texte extrait est
  comparée à celle du passage précédent. Un texte qui change n'arrête pas
  la collecte ; il est **signalé en tête du bilan**, et l'IeC relit les
  conditions avant toute indexation (ADR 0004). Au premier passage, le
  bilan dit qu'il n'y a pas encore de référence.
- **L'empreinte du texte extrait entre au manifeste** dès cette mission
  (L.5) : c'est elle, et non le sha256 brut, qui servira à toute revisite.
- **Pas d'en-tête `From:`** (L.9) : le `User-Agent` suffit.
- **Le passage de beko** se fera avec un plafond explicite que tu donnes
  dans le rapport du palier 1, avec la sortie de `--simuler` (723 requêtes
  attendues, plus les mentions légales et une marge de réessais).

### D. L'extraction

- **D1 : toutes les sections du corps sont gardées**, « Quelle place dans
  la stratégie thérapeutique ? » et « Recommandations particulières »
  comprises. Couper serait déjà choisir dans le texte. La garde médicale
  porte sur la **question**, en amont, et le prompt dit que l'avis est une
  évaluation collective qui ne s'applique jamais à une personne (G).
- **D2 : l'extraction est recalculée** à chaque construction de l'index.
  `has extraire` sert à l'inspection et à `--verifier`, et l'index ne lit
  jamais sa sortie.
- **La preuve de non-altération** en trois volets est retenue. Le second
  lecteur ne partage aucun code avec l'extracteur.

### E. Le jeu de démo

- **E1 : sous `demo/archive`**, avec un manifeste à part
  (`manifeste/has-pages.jsonl`). La liste `demo/has-pages.txt` est committée.
  Environ **150 pages**, plafond de 10 Mo sur disque. La règle de choix est
  écrite dans le `README` du jeu, et le complément est déterministe.
- **La partie BDPM du jeu ne change pas, à l'octet** : `collecte.jsonl` et
  chaque archive BDPM gardent leur sha256. Un test le vérifie contre
  `beba0c8`, et `demo verifier` contrôle en plus les pages.
- Le `README` du jeu dit qu'il n'est plus figé « à la mission 04 », mais
  composé de deux parties figées : la BDPM (mission 04) et les avis
  (mission 09).
- **La mention de la HAS** (L.2) est retenue : « document de la Haute
  Autorité de santé, disponible sur www.has-sante.fr », avec la date de
  consultation, dans `tests/fixtures/README.md` et dans le `README` du jeu.
- **`requetes_s0.py`** reste dans le dépôt comme preuve, avec son journal
  plein. Aucun test ne l'importe, et un test le vérifie.

### F. L'index

- **F1 : un fragment par (page, CIS, partie)**, section `avis_has`, format 3,
  collection neuve ; les vecteurs denses des fiches sont repris du cache.
- **F2 : oui, `avgdl` est remesurée une fois** sur les fragments du jeu de
  démo (fiches et avis) puis figée dans le format 3. Condition : `index
  evaluer` sur la v0 et la v1, **avant et après**, dans le même rapport. Si
  le rappel à 10 des fiches recule, on garde 53,29 et tu le dis ; aucun
  autre réglage sur le jeu.
- **F3 : oui**, les deux horloges, rendues toutes les deux : « BDPM au … ;
  pages d'avis de la HAS collectées jusqu'au … ». Un manifeste HAS dont le
  préfixe a changé, ou un extracteur d'une autre version, impose la
  reconstruction : retenu.

### G. L'assistant

- **Le LLM ne voit aucune URL**, et le code rend les liens : retenu. Le
  contrôle vérifie qu'aucune adresse n'apparaît dans le texte rédigé.
- **G1 : oui**, la consigne générale « la date de chaque fait daté avec le
  fait », mesurée sur les questions neuves. La date rendue par le code sous
  la réponse ne compte pas comme une date du texte : la notation ne change
  pas de règle.
- **G2 : écart, refus médical.** « Quelle est la durée du traitement par
  KALYDECO selon l'avis ? » demande une posologie, que le PRD range dans le
  conseil médical (§6.8), et l'ordre dit que le texte d'un avis ne fait pas
  d'une question médicale une question permise. **La dose, la durée, le
  rythme ou le mode de prise d'un traitement donnent un refus**, avec un
  renvoi vers le médecin, le pharmacien, la notice et le RCP, que la
  question cite un avis ou non. Le refus se décide par les règles quand
  c'est possible, et cette question entre dans les questions médicales
  neuves de la v2. Une question sur ce que l'avis **évalue** (le progrès,
  la place dans la stratégie, la population de l'indication) reste une
  réponse citée.
- **G3 : oui**, « deux médicaments » donne une abstention, et la
  comparaison tirée d'un avis devient une question piège de la v2.
- **Les quatre propositions sur les constats de la mission 08** (le rappel
  par section par une table écrite, les dates, les citations hors des
  fragments comptées à part, les mots courants à deux mots) sont retenues,
  avec leurs mesures. La table des sections et la liste des mots courants
  sont écrites dans le code **avant** les questions neuves, et ne bougent
  plus après leur commit sans le dire au rapport.
- **La déduplication** des fragments d'une même (page, partie) dans les dix :
  retenue.
- **Une règle de refus ne s'étend** qu'après l'échec d'une question neuve,
  et l'extension s'éprouve sur au moins 200 questions factuelles, sans faux
  refus : retenu.

### H. Le jeu de questions v2

- **H1 : oui**, les 88 questions de la v1 sont reprises sous leurs
  identifiants, au même texte. Les comportements attendus qui changent
  (`disponibilite-005`, `avis_has-004`, `avis_has-009`) sont listés dans
  l'en-tête du fichier, avec leur raison. `historique-003`, `-008` et
  `remboursement-010` restent des abstentions.
- **H2 : oui**, l'attendu `has.avis` (archive, sha256, URL, valeurs, extrait
  de douze mots au plus), vérifié sans gold depuis l'archive HAS et le
  bronze, et les trois ajouts de notation (`lien_attendu`, date de l'avis,
  `extrait_attendu`).
- **Les questions neuves sont choisies par une règle écrite d'abord** et
  committées, avec leur sha256 au rapport, **avant** tout commit de
  retouche. L'IeC vérifiera l'ordre des commits au contrôle du palier 2.
- **Les trois questions qui demandent le PDF** attendent une abstention
  motivée : retenu.
- Environ 133 questions : retenu.

### I. Le coût

- **I1 : oui**, `CARACTERES_PAR_JETON = 1,7`, avec la méthode (les 62 clés de
  cache retrouvées) et l'écart dans le rapport et l'ADR 0013. Tu vérifies la
  constante sur les appels de la démonstration du palier 2.
- **I2 : oui**, le plan de dépense, avec la réserve d'un second passage.
  `max_tokens` reste à 4 000. Les appels partent avant le **16/11/2026
  (UTC)**.

### J. Les PDF

- **Pas de collecte de PDF.** La recommandation et son chiffrage vont dans
  l'ADR 0013, avec la mesure des trois questions v2 qui en ont besoin.

### K. La mémoire et le temps

- Toutes les valeurs sont **mesurées** à chaque palier sous `/usr/bin/time
  -l`. Si `assistant evaluer --estimer` passe 512 Mo avec les fragments
  d'avis, tu le dis et tu proposes une séparation avant d'aller plus loin.

### La clôture

Elle ne change pas.
