# Mission 02 — Normalisation et détection des changements : du bronze aux événements

**À :** Claude Fable (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.3 §1.5, §4 (Lot 1), §6.1, §6.2, §6.3, §7.1, §9, annexe A ·
mission 01 (`pr.md`, rubrique « Reporté ») · ADR 0002 et 0003 ·
`docs/donnees/README.md` · `CLAUDE.md` · `docs/agents/processus.md`
**Statut :** ordre rédigé le 26/10/2026 — **§0 à traiter avant de coder**
**Branche :** `mission-02-normalisation-et-evenements`, dans
`pharmaflux-codeur/` (préparée par beko avec `preparer-mission.sh`). Trois
paliers, chacun committé en local et contrôlé par l'IeC ; **aucun push** de
ta part.

Lis d'abord `CLAUDE.md`, puis `docs/agents/processus.md`, puis le PRD v0.3,
puis cet ordre. Le circuit est celui de la mission 01, messages directs
compris.

## Constat

Le Lot 0 est soldé. Chaque fichier de la BDPM a un contrat v0, et
`pharmaflux profil` sait dire si une archive le respecte. Mais le projet ne
produit encore **aucun événement**. Or c'est l'axe du PRD (§1.5) :
transformer des publications d'état en un flux d'événements daté,
rejouable, sans perte ni doublon.

Cette mission ouvre le Lot 1 par son cœur, **sans infrastructure** :

1. lire une archive en **snapshot normalisé**, piloté par son contrat ;
2. **comparer** deux snapshots successifs d'un même fichier et en tirer des
   événements `creee`, `modifiee`, `supprimee` ;
3. **rejouer** toute l'histoire du bronze avec un résultat identique à
   l'octet près, et reprendre là où on s'était arrêté sans rien perdre ni
   dupliquer.

Redpanda, le registre de schémas, la file des messages en échec dans un
topic et `docker compose` sont pour la **mission 03**. Ils transporteront
des événements dont cette mission fixe le contenu et l'identité.

Deux faits de l'archive pèsent sur cette mission :

- **Le cas réel du fichier vide** (PRD v0.3 §6.1). Le 26/10/2026 à 14:17
  UTC, `CIS_InfoImportantes.txt` a été servi vide, puis normal à 15:17,
  identique à celui du 24/10. Une comparaison naïve aurait émis 10 905
  `supprimee`, puis 10 905 `creee` une heure plus tard : de fausses
  informations de sécurité retirées, puis republiées. Le garde-fou de
  volume (§6.3) doit en faire **zéro** événement.
- **L'archive est encore courte.** Sur la copie du Mac au 26/10,
  `CIS_CIP_bdpm.txt` a trois archives (deux changements réels),
  `CIS_InfoImportantes.txt` trois (dont la vide), et les neuf autres
  fichiers une seule. Les tests reposent donc sur des fixtures fabriquées
  **à partir de** lignes réelles. Les deux changements réels servent de
  démonstration de bout en bout.

**Objectif** : à la fusion, `pharmaflux evenements` calcule, pour chacun des
onze fichiers, la suite des événements depuis la première archive. Le
calcul est déterministe : deux exécutions donnent les mêmes octets. Une
reprise après interruption donne exactement le rejeu complet. Le fichier
vide du 26/10 ne produit aucun événement. Deux ADR fixent la normalisation
et le contenu d'un événement.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Les contrats v0 sont la référence** de la lecture. Tout changement de
  contenu d'un contrat, lien compris, passe par une nouvelle version (PRD
  v0.3 §6.2). Si la normalisation a besoin d'une information qui manque à
  un contrat, c'est un `v1` de ce contrat, avec sa raison, et rien
  d'implicite dans le code.
- **On constate, on ne corrige pas** (PRD §6.2). Une valeur non conforme
  garde sa valeur brute et son anomalie. Elle n'est jamais devinée.
- **Comparaison ligne à ligne** pour les trois fichiers sans clé unique :
  disponibilité, SMR et ASMR (PRD §6.3, `docs/donnees/README.md`).
- **Garde-fou de volume** (PRD v0.3 §6.3) : un snapshot vide, ou qui perd
  une part anormale de ses lignes, ne produit aucun `supprimee`. Le §0 en
  fixe la règle exacte.
- **Rien sur le VPS.** Cette mission calcule sur la copie du Mac ; la
  collecte n'est pas touchée. Le VPS-1 reste partagé avec la
  pré-production d'Alamel jusqu'à mi-novembre.

## Sources de données pour cette mission

- **L'archive, en lecture seule.** Racine : `$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data`. Tu n'y écris **jamais** rien. Les sorties vont dans un
  dossier donné en option, par défaut sous `data/` à la racine du dépôt
  (déjà ignoré par git). beko rafraîchit la copie avec `rapatrier.sh` quand
  tu le lui demandes.
- **Le manifeste** (`manifeste/collecte.jsonl`) est la source des dates :
  heure de l'archive, `date_source_affichee` (date du fichier selon la page
  BDPM), et les passages `inchange` qui revoient une même empreinte. Tu le
  lis en flux, par le code existant.
- **Aucune requête réseau** dans toute la mission : ni BDPM, ni data.gouv,
  ni HAS.
- Les tests ne touchent ni le réseau ni l'archive : fixtures seulement.

## §0 — Points à trancher avant de coder

Réponds point par point dans `docs/rapports/mission-02/points-a-trancher.md`
(commité, puis tu t'arrêtes) : constat (ce que tu as vérifié et comment),
avis, question éventuelle.

- **A. Représentation d'un snapshot normalisé.** Proposition : pour un
  fichier à clé unique, un dictionnaire clé → ligne normalisée ; pour un
  fichier sans clé unique, un multiensemble de lignes normalisées entières.
  Chaque ligne garde ses valeurs brutes **et** normalisées. Avis, et coût
  mémoire mesuré sur le plus gros fichier (`CIS_COMPO_bdpm.txt`, 32 439
  lignes).
- **B. Ce que la normalisation change.** Pour chacun des neuf types de
  l'ADR 0002, dis ce que devient une valeur conforme : date en ISO 8601,
  décimal en forme canonique (`1003.48` ?), booléen, énumération, liste.
  Dis aussi ce que devient une valeur non conforme : brute, avec son
  anomalie. Trois cas réels à trancher, avec ton avis :
  - les taux en deux graphies (`65%`, `65 %`) : une seule forme normalisée,
    puisque l'espace ne change pas le sens ? Mesure combien de CIP13
    changeraient de graphie d'une archive à l'autre sans changer de taux ;
  - les espaces parasites (17 016 dans `CIS_bdpm.txt`) : retirés dans la
    valeur normalisée, la brute gardant la trace ? Un `modifiee` dû à une
    seule espace est-il un vrai changement ?
  - les prix `1,003,48` : `decimal_illisible` aujourd'hui. Lire la virgule
    des milliers serait deviner (PRD §6.2), sauf si la documentation BDPM
    la définit. Vérifie dans le PDF archivé.

  La règle à respecter : la normalisation change la **forme**, jamais le
  **sens**, et elle est écrite dans le contrat ou dans l'ADR, pas cachée
  dans le code.
- **C. Comparaison et types d'événements.** Pour un fichier à clé :
  `creee`, `supprimee`, et `modifiee` avec la liste des champs modifiés,
  calculée sur les valeurs normalisées. Pour un fichier ligne à ligne : pas
  de `modifiee`. Une ligne qui change donne une `supprimee` puis une
  `creee`. Comment relier les deux pour le Lot 2 ? Par la clé déclarée non
  unique (CIS + dossier pour SMR), sans prétendre à une identité ? Avis.
- **D. Contenu d'un événement** (PRD §6.3). Propose le schéma exact, champ
  par champ :
  - entité et type ;
  - clé, état avant, état après ;
  - date de la source (`date_source_affichee`) et date d'observation (heure
    de l'archive) ;
  - empreinte et chemin de l'archive d'origine, et de l'archive précédente ;
  - version du contrat et version du schéma de l'événement.

  Format de sortie : JSON Lines, un fichier par source, trié de façon
  déterministe ? Avis, et ce qui changera quand Redpanda arrivera (mission
  03).
- **E. Identifiant déterministe.** L'identifiant d'un événement doit être
  le même à chaque rejeu, et différent pour deux événements distincts.
  Proposition : un sha256 sur (identifiant du catalogue, empreinte de
  l'archive précédente, empreinte de l'archive, type, clé ou empreinte de
  ligne). Vérifie les cas limites : une ligne en doublon qui disparaît une
  fois sur deux, et un retour à un état antérieur (A → B → A).
- **F. Garde-fou de volume.** Proposition de règle, à évaluer :
  - un snapshot avec une anomalie bloquante, ou vide, est **écarté** ;
  - un snapshot qui perd plus de X % des lignes du dernier snapshot retenu
    est **en attente** ;
  - un snapshot en attente est **confirmé** si une ligne `inchange` du
    manifeste revoit la même empreinte à un passage ultérieur. Il est alors
    comparé normalement. Sinon, il reste écarté.

  Un snapshot écarté produit un enregistrement visible (motif, archive),
  jamais d'événement, et la comparaison suivante repart du dernier snapshot
  retenu. Sur le cas du 26/10 : 14:17 écarté, 15:17 identique au 24/10,
  donc zéro événement. Propose X à partir des archives existantes, et dis
  ce qui se passe pour un fichier dont la source rétrécit vraiment.
- **G. Premier snapshot.** La première archive d'un fichier n'a pas de
  précédent. Proposition : un événement `creee` par entité, marqué comme
  état initial, pour que le Lot 2 puisse ouvrir ses lignes SCD2. Mesure le
  volume que cela représente pour les onze fichiers. Discute aussi
  l'alternative : un seul événement « état initial » qui renvoie à
  l'archive.
- **H. Reprise et rejeu.** Le rejeu complet relit tout le bronze. La
  reprise ne traite que les archives postérieures à la dernière traitée, en
  repartant du dernier snapshot retenu. Comment la reprise connaît-elle cet
  état sans relire tout le bronze ? Proposition : un état minimal écrit à
  côté des événements, avec la dernière archive retenue par fichier et son
  empreinte, puis recalcul du snapshot depuis cette archive. Exigence : la
  reprise après **n'importe quel** point d'arrêt donne les mêmes octets que
  le rejeu complet. Comment le tester sans dépendre de l'heure ?
- **I. Changement de version de contrat.** Ce n'est pas encore arrivé,
  mais ce sera le cas. Deux snapshots lus avec deux versions d'un même
  contrat se comparent-ils ? Proposition : la version du contrat fait
  partie de l'événement, et un changement de version qui change une forme
  normalisée est annoncé dans l'ADR du contrat. Avis, sans l'implémenter
  au-delà de ce qu'il faut pour ne pas se fermer la porte.
- **J. Reliquats de la mission 01.** `_decoder` compte les lignes touchées
  par un octet illisible : utile ici, puisque la normalisation lit en
  continuant ? Le compte attendu d'anomalies connues (option (b) de
  l'addendum 1 de la mission 01) devient naturel une fois qu'on compare
  deux snapshots. Proposition : un **bilan par snapshot** (compte
  d'anomalies par règle, écart avec le snapshot précédent), qui est une
  mesure et pas une alerte (alertes au Lot 5). Avis.
- **K. Toute autre chose** que ta lecture du code, des contrats ou de
  l'archive te fait remarquer.

## Décisions (sous réserve du §0)

1. **Snapshot normalisé** (`src/pharmaflux/normalisation/` ou équivalent) :
   une fonction lit une archive par `bronze.py`, la vérifie par
   `contrats.verification` et rend un snapshot normalisé, avec le bilan de
   ses anomalies. Elle ne relit pas le fichier une seconde fois pour la
   vérification. Une anomalie bloquante rend un snapshot **écarté** avec son
   motif, pas une exception.

2. **Règles de normalisation** (§0 B) : écrites dans l'ADR 0005, et dans les
   contrats si une information manque (nouvelle version, raison dans le
   contrat). Chaque type a un test de conversion, et un test qui montre
   qu'une valeur non conforme reste brute avec son anomalie.

3. **Comparaison** (§0 C) : à clé et ligne à ligne, sur les valeurs
   normalisées. Elle rend des événements triés de façon déterministe. Le
   premier snapshot suit le §0 G.

4. **Événement** (§0 D et E) : une structure typée (`mypy --strict`), sa
   sérialisation JSON stable (clés triées, pas d'espace variable, UTF-8),
   son identifiant déterministe, et `version_schema = 1`. Le schéma est
   documenté dans l'ADR 0006, avec un exemple réel.

5. **Garde-fou de volume** (§0 F) : écarté, en attente, confirmé, avec un
   motif lisible. Un test reproduit le cas du 26/10 sur fixtures (snapshot
   normal, snapshot vide, snapshot identique au premier) et attend zéro
   événement et un écart consigné.

6. **Bilan par snapshot** (§0 J, si retenu) : comptes d'anomalies par
   règle, lignes, entités, et écart avec le snapshot retenu précédent.

7. **`uv run pharmaflux evenements [--racine …] [--fichier …] [--sortie …]
   [--reprendre]`** :
   - sans `--reprendre`, rejeu complet depuis la première archive de
     chaque fichier ;
   - avec `--reprendre`, seulement ce qui est nouveau depuis l'état
     sauvegardé (§0 H) ;
   - sortie : les événements, les snapshots écartés et les bilans, dans le
     format du §0 D ;
   - résumé dans le terminal : par fichier, archives lues, retenues et
     écartées, et événements par type ;
   - code de sortie non nul si une archive est illisible, et nul si des
     snapshots sont écartés : un écart est un constat, pas une panne.

8. **Exactitude** (PRD §7.1), en tests automatiques :
   - deux rejeux complets donnent des sorties identiques à l'octet ;
   - une reprise après chaque point d'arrêt possible d'une suite de
     fixtures donne la sortie du rejeu complet ;
   - aucun identifiant d'événement en double sur l'ensemble ;
   - appliquer les événements au snapshot initial redonne le dernier
     snapshot retenu (vérification par empreinte). C'est la propriété
     « aucun changement perdu ».

9. **Démonstration sur l'archive du Mac** (lecture seule) : rejeu complet
   des onze fichiers, et consigne dans le rapport :
   - les événements des deux changements réels de `CIS_CIP_bdpm.txt`
     (24/10 23:17 et 26/10 00:17) : nombre par type et champs modifiés.
     Cite deux ou trois exemples bruts, avec la source et la date ;
   - le traitement du fichier vide du 26/10 ;
   - le temps de calcul et la mémoire de pointe.

10. **Docs** :
    - ADR 0005 (normalisation) et 0006 (événements : schéma, identifiant,
      comparaison ligne à ligne, garde-fou de volume, premier snapshot,
      reprise) ;
    - `docs/CONTEXTE.md` (du bronze aux événements) ;
    - `docs/journal.md` (entrée de la mission, en fin de fichier) ;
    - `README.md` (état du projet, commande `evenements`).

**Outillage** : aucune nouvelle dépendance au projet. La bibliothèque
standard suffit (`json`, `hashlib`, `gzip`, `dataclasses`). Une exception
se justifie au §0.

## Paliers

1. **Snapshot normalisé** : décisions 1 et 2.
   - Tests de conversion par type et cas non conformes ; un test vérifie
     que chaque fixture réelle se normalise sans anomalie bloquante.
   - ADR 0005.
   - Rapport, commit.
2. **Comparaison, événements, garde-fou** : décisions 3, 4, 5 et 6.
   - Fixtures fabriquées à partir de lignes réelles, signalées comme
     telles dans `tests/fixtures/README.md` : création, modification d'un
     champ, suppression, doublon, retour A → B → A, fichier vide, perte
     partielle.
   - Rapport, commit.
3. **Chaîne, rejeu et reprise** : décisions 7, 8, 9 et 10.
   - ADR 0006 ; démonstration sur l'archive du Mac, résultats dans le
     rapport.
   - Rapport, commit.

Après le contrôle du palier 3 : relecture (`/relire-mission 02`) jusqu'à
« CONFORME », `pr.md`, revue finale, publication et fusion par beko. **La
mission est close** quand `pharmaflux evenements` passe sur une copie
rapatriée après la fusion, et qu'un second lancement avec `--reprendre`
n'ajoute que les événements des archives arrivées entre-temps.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests | `uv run pytest -q` |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck (même version que la CI) | `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` |
| non-régression de la mission 01 | `uv run pharmaflux profil --racine ~/pharmaflux-data` et `uv run pharmaflux questions verifier --racine ~/pharmaflux-data` |

## Hors périmètre

- Redpanda, registre de schémas, topic des messages en échec, `docker
  compose`, testcontainers : **mission 03**.
- Couches silver et gold en Iceberg, SCD2, « état à une date » : **Lot 2**.
  Cette mission écrit des fichiers d'événements, pas de table.
- Toute modification de la collecte et tout déploiement sur le VPS.
- Open Medic (contrats et CSV) : **Lot 4**. Alertes : **Lot 5**.
- Jeu de questions v1 : **Lot 3**.
- Toute requête réseau ; toute écriture dans l'archive ; toute utilisation
  de l'API Claude.
- **Pas d'usage des VPS d'Alamel**, et rien qui touche à la pré-production
  du VPS-1.

## Addendum 1 — §0 tranché (IeC, 26/10/2026)

Réponse à `docs/rapports/mission-02/points-a-trancher.md` (commit
`a28969f`). Le rapport est solide : les mesures sont faites sur l'archive,
sans aucune requête réseau, et le refus du mode auto est signalé sans
variante. J'ai recompté sur la copie du Mac les deux constats qui changent
le plus l'ordre, et ils sont exacts :

- l'égalité des prix : 13 125 lignes sur 13 125 sans virgule des milliers,
  495 sur 498 avec, et aucun prix hors du motif ;
- le manifeste du 26/10 : 14:17 est vide et sans `Content-Disposition`,
  et 15:17 est un `nouveau` dont le sha256 est celui du 24/10.

**Tes avis sont retenus sauf mention contraire.** Les décisions de l'ordre
sont modifiées comme suit.

**A — Snapshot : d'accord.** Une `Ligne` figée (numéro, brutes,
normalisées, anomalies) partage les tuples de la `Lecture`. Un fichier à
clé est un dictionnaire clé → ligne. Un fichier ligne à ligne est un
multiensemble (empreinte → ligne, occurrences). Le snapshot porte aussi
son archive, la version du contrat et son bilan.

**B et question 1 — Normalisation : d'accord, avec une règle plus nette
que « non conforme = brute ».** Le partage se fait sur ce que dit
l'anomalie :

- une anomalie de **lisibilité** laisse la valeur brute. C'est le cas
  quand le type ne sait pas lire la valeur : `date_illisible`,
  `decimal_illisible`, valeur hors énumération, motif non respecté…
- une anomalie de **vraisemblance ou de forme** n'empêche pas la forme
  canonique, et l'anomalie reste consignée. C'est le cas de
  `date_hors_plage` et de `espace_parasite`.

L'ADR 0005 donne ce partage règle par règle, dans un tableau. Ton
tableau par type est retenu tel quel : les valeurs sont des chaînes
canoniques, un vide reste `""`, et la liste est normalisée élément par
élément.

**B.1, B.3 et question 2 — `presentations.toml` passe en v1, avec deux
ajouts, chacun suivi de sa raison.**

- **Taux** : une table `canonique` sur l'énumération, avec `65%` et sans
  espace. Le chargeur vérifie que chaque clé et chaque valeur sont dans
  `valeurs`.
- **Prix** : le paramètre `milliers = ","` sur les trois colonnes
  `decimal`. Le type accepte alors `\d{1,3}(,\d{3})+,\d{2}` en plus de la
  forme simple, et le normalise en `1003.48`.

Ce n'est pas deviner au sens du PRD §6.2, car la forme est **vérifiée par
une contrainte interne mesurée** : prix public = prix + honoraires, sur
toutes les lignes sans séparateur et sur 495 des 498 lignes avec. Les
3 écarts de 2 centimes sont dans la source, et aucune autre lecture ne
rend ces lignes cohérentes.

Le refus de `pdf2txt` ne bloque donc rien. La raison du contrat cite la
mesure et ta lecture du PDF au §0 de la mission 01 : aucun format défini.
**Personne ne relance la commande refusée pour toi.** Si beko veut relire
le PDF, il le fait lui-même ; ce n'est pas une condition de la mission.
Ne mesure pas les 3 écarts de 2 centimes dans cette mission : c'est une
règle métier, à reprendre au Lot 2 (qualité).

Les deux nouveaux paramètres sont définis dans l'ADR 0005. L'ADR 0002
reçoit, dans son en-tête, une seule ligne : « complété par l'ADR 0005
(`canonique`, `milliers`) ». Je préciserai le PRD §6.2 dans sa prochaine
version.

**Non-régression attendue du profil** (contrat v1). Les
`decimal_illisible` des prix disparaissent. Le rapport du palier 1 donne
le compte avant et après, ce qui est la seule différence admise.
`questions verifier` doit toujours donner 25 / 5 / 10. Tout autre écart
s'explique dans le rapport.

**C — Comparaison : d'accord.** Retenus tels que proposés :

- `identite = "cle" | "ligne"`, `cle` et `empreinte_ligne` sur chaque
  événement ;
- un rapprochement `supprimee`/`creee` laissé au Lot 2, qui ne
  l'affirmera pas ;
- l'ordre clé, puis `supprimee` < `modifiee` < `creee`, puis empreinte,
  puis rang.

**D et questions 3, 7 — Schéma et sortie : d'accord.** Le schéma
`version_schema = 1` est retenu champ par champ, toutes les valeurs de
données en chaînes. La sortie se fait **par archive** :

- `evenements/<entite>/<horodatage>__<sha12>.jsonl`, vide quand rien n'a
  changé ;
- un bilan par archive lue ;
- une écriture atomique par fichier.

Le flux d'une source est la concaténation de ses fichiers dans l'ordre
des noms. C'est ce flux que les tests de la décision 8 comparent. La
décision 7 est modifiée en ce sens.

**E — Identifiant : d'accord, l'ordre est corrigé.** Le sha256 porte sur
la chaîne `entite`, `archive`, `archive_precedente`, `type` et
`identite_de_ligne`, séparés par `\x1f`. Les deux archives entrent par leur
**chemin relatif**, et non par leur seule empreinte. Ta démonstration de
l'oscillation A → B → A → B est juste : ma proposition aurait donné deux
fois les mêmes identifiants. Le test de la décision 8 « aucun identifiant
en double » doit contenir cette oscillation.

**F et question 4 — Garde-fou de volume : d'accord, X = 1 %, avec la
seconde voie de confirmation.** Les lignes comptées sont les lignes bien
formées. Trois précisions :

1. **Le vide et le bloquant sont écartés sans appel.** Ils ne passent
   jamais en attente et ne sont jamais confirmés. Si une source est un jour
   vraiment vidée ou abandonnée, cette mission ne produit pas des milliers
   de `supprimee`. Elle consigne un écart à chaque passage, et c'est un
   humain qui tranche (alerte au Lot 5).
2. **Un snapshot en attente n'est pas « traité ».** L'état garde
   `en_attente`, et `derniere_archive_traitee` reste avant lui. Quand une
   exécution ultérieure le tranche, elle **réécrit son bilan** (écarté ou
   confirmé) et écrit ses événements s'il est confirmé, pour que la sortie
   égale celle d'un rejeu complet sur le même bronze. Le test de reprise
   doit contenir un point d'arrêt juste après une archive en attente,
   tranchée ensuite dans chacun des deux sens.
3. **Motifs** : comme ton exemple, avec les deux comptes de lignes et le
   pourcentage.

**G — Premier snapshot : d'accord.** Une `creee` par entité, avec
`etat_initial = true`, et pas de compression. La démonstration redonne,
par fichier, le nombre d'événements et la taille.

**H — Reprise : d'accord.** L'état est réécrit atomiquement après les
fichiers de l'archive, dans l'ordre événements, bilan, état. Le snapshot
retenu est recalculé depuis son archive et n'est jamais sérialisé. Les
cinq tests que tu proposes sont retenus, plus le point d'arrêt du F.2.

**I et question 6 — Version de contrat : d'accord.** Les deux côtés d'une
comparaison sont lus avec le contrat courant. `--reprendre` **refuse**
quand une version de contrat diffère de celle de l'état, avec un message
qui demande un rejeu complet, et sort avec un code non nul. Le choix d'une
version de contrat par archive est hors de cette mission ; il est noté
dans l'ADR 0005.

**J — Reliquats : d'accord sur les deux.** `_decoder` compte les lignes
touchées, au palier 1. Le bilan par archive suit ton contenu ; c'est une
mesure, et il ne change pas le code de sortie. La décision 6 n'est plus
« si retenu » : elle est retenue.

**K et question 5 — Autres points.**

- **`fichier_vide`** : retenu, en anomalie **non bloquante** de
  `verification`, au palier 1. C'est le contrat qui décrit la forme ; la
  décision d'écarter appartient au garde-fou de volume.
- **`date_source = null`** pour `CIS_InfoImportantes.txt` : d'accord.
- **`Content-Disposition` absent** : à consigner dans le rapport, en
  proposition pour le Lot 5, sans code.
- **Paquet** : `src/pharmaflux/evenements/`, avec ton découpage.

**Démonstration (décision 9, modifiée).** L'archive ne contient pas de
`modifiee` réelle. Le rapport donne donc :

- les **3 `supprimee`** réelles de `CIS_CIP_bdpm.txt`, avec deux exemples
  bruts, la source et la date ;
- le traitement du vide du 26/10 : 14:17 écarté, 15:17 identique au
  retenu, zéro événement ;
- les `creee` initiales par fichier ;
- le compte des prix normalisés grâce à `milliers` ;
- le temps de calcul et la mémoire de pointe.

Les `modifiee`, les doublons et les retours viennent des fixtures, et le
rapport le dit.

**Paliers.** Au palier 1 s'ajoutent le contrat v1 (`canonique`,
`milliers`, chargeur et tests), `fichier_vide` et le compte de `_decoder`.
Le reste est inchangé.

Tu peux coder le palier 1.
