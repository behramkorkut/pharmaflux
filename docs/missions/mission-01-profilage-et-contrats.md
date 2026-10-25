# Mission 01 — Profilage des sources, contrats de schéma et décisions du Lot 0

**À :** Claude Fable (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.1 §4 (Lot 0), §6.2, §6.3, §7.1, §9, §10.2, annexes A et
B · mission 00 (ordre, `pr.md`, rubrique « Reporté à la mission 01 ») ·
`CLAUDE.md` · `docs/agents/processus.md`
**Statut :** ordre rédigé le 26/10/2026 — **§0 à traiter avant de coder**
**Branche :** `mission-01-profilage-et-contrats`, dans `pharmaflux-codeur/`
(préparé par beko avec `preparer-mission.sh`). Quatre paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Lis d'abord `CLAUDE.md`, puis `docs/agents/processus.md`, puis le PRD v0.1,
puis cet ordre. Le circuit est celui de la mission 00, sans changement.

## Constat

La mission 00 a mis l'archive en service : depuis le 24/10/2026, le VPS-1
collecte chaque heure les onze fichiers de la BDPM, la page de
téléchargement, la documentation des formats et les métadonnées Open Medic.
Une copie est rapatriée sur le Mac de beko (`~/pharmaflux-data`). Le premier
changement réel (`CIS_CIP_bdpm.txt`, 24/10 à 23:17Z) a été capté une fois.

Le Lot 0 n'est pas fini : on archive des fichiers que l'on **ne sait pas
encore lire**. Le Lot 1 (normalisation, détection des changements,
événements) a besoin de trois choses que cette mission produit :

1. **des contrats de schéma** : pour chaque fichier, l'encodage, la fin de
   ligne, les colonnes, leur type, la clé. Les fichiers n'ont pas d'en-tête,
   et ton constat H.2 de la mission 00 montre que l'encodage varie déjà d'un
   fichier à l'autre ;
2. **un profil mesuré** de chaque fichier : volumes, valeurs, clés,
   anomalies, dans `docs/donnees/` ;
3. **les décisions du PRD §10.2** qui dépendent des données, écrites en
   ADR. Le point le plus lourd de conséquences : le sens d'une ligne qui
   disparaît du fichier de disponibilité (PRD §6.3, risque du §9).

Elle solde aussi les **reliquats de la mission 00**, acceptés et reportés.

**Objectif** : à la fusion, chaque fichier archivé a un contrat versionné et
vérifié par la CI, `pharmaflux profil` mesure n'importe quelle archive
contre son contrat, les ADR du Lot 0 sont écrits, et un jeu de questions de
référence v0 existe, avec des réponses attendues **recalculables** depuis
l'archive.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **Lieu et rythme de la collecte** (PRD §10.2, points 2 et 4) : VPS-1,
  toutes les heures à `:17`, sans requête conditionnelle (mission 00,
  addendum 2). Cette mission les **consigne** dans un ADR, elle ne les
  rouvre pas.
- **Nom du projet** (point 1) : Pharmaflux, retenu par beko. Le PRD v0.2
  l'acte ; pas d'ADR.
- **Points 5, 6 et 8** (Qdrant ou pgvector, stockage des traces, démo
  hébergée) : reportés aux lots qui les utilisent (3, 5, 6). Le PRD v0.2
  l'acte ; pas d'ADR dans cette mission.
- **Le VPS-1 est partagé** avec une pré-production d'Alamel (non
  confidentielle) jusqu'à mi-novembre 2026. Rien de ce que tu écris ne doit
  la voir ni la gêner. Le PRD v0.2 et l'ADR de collecte le disent.

Le PRD v0.2 est en cours de rédaction par l'IeC pendant ton §0. En cas de
divergence entre le PRD v0.1 et cet ordre, **l'ordre fait foi**.

## Sources de données pour cette mission

- **L'archive, en lecture seule.** Racine : `$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data` (la copie rapatriée par beko). Tu n'y écris **jamais**
  rien, ni fichier, ni dossier. beko la rafraîchit avec `rapatrier.sh` quand
  tu le lui demandes.
- **Aucune requête vers la BDPM ni vers data.gouv** dans toute la mission :
  tout ce qu'il faut est archivé, y compris la documentation PDF des
  formats.
- **HAS** (point 7 du §10.2, corpus) : **cinq requêtes au plus** pour toute
  la mission, à justifier une par une dans ton rapport.
- Les tests ne touchent ni le réseau ni l'archive : fixtures seulement
  (extraits réels, datés et sourcés dans `tests/fixtures/README.md`).

## §0 — Points à trancher avant de coder

Réponds point par point dans `docs/rapports/mission-01/points-a-trancher.md`
(commité, puis tu t'arrêtes) : constat (ce que tu as vérifié et comment),
avis, question éventuelle. Pour le §0, tu lis l'archive et le code ; **pas
de requête HAS** à ce stade.

- **A. Noms et sens des colonnes.** La référence est la documentation
  officielle archivée
  (`bronze/bdpm/Contenu_et_format_des_fichiers_telechargeables_dans_la_BDM_v5.pdf/`).
  Comment la lis-tu sans rien installer sur le système ni ajouter de
  dépendance au projet ? (Piste : un outil lancé par `uvx`, comme
  shellcheck à la mission 00.) Relève les écarts entre la documentation et
  les fichiers réels : nombre de colonnes, colonnes en trop ou vides.
- **B. Format des contrats.** Proposition : un fichier **TOML** par fichier
  source, lu par `tomllib` (bibliothèque standard, aucune dépendance),
  versionné (`v0`), dans le paquet (`src/pharmaflux/contrats/`). Contenu
  minimal : encodage attendu, fin de ligne, séparateur, liste ordonnée des
  colonnes (nom en `snake_case` français, type, obligatoire ou non, format
  pour les dates et les décimaux), clé métier, et la référence à la page de
  la documentation. Avis, et ce qu'il manque.
- **C. Types.** Propose un jeu de types **fermé et court** (texte, entier,
  décimal à virgule, date `JJ/MM/AAAA`, booléen `Oui`/`Non`, énumération…).
  Pour chaque type : la règle de validation, et ce qui compte comme
  anomalie. Rappel PRD §6.2 : on **constate** les anomalies, on ne corrige
  jamais en silence. Cette mission **ne produit pas de données
  normalisées** : la conversion et la couche silver sont au Lot 1.
- **D. Clés.** Pour chaque fichier, la clé métier que tu proposes (CIS,
  CIP13, CIS + substance…), et si elle est unique **dans l'archive du
  24/10** (mesuré). Une clé qui ne l'est pas est un constat majeur pour le
  Lot 1 : dis-le en tête.
- **E. Disponibilité et MITM** (PRD §10.2 point 3). Colonnes, valeurs des
  statuts de `CIS_CIP_Dispo_Spec.txt` (rupture, tension, arrêt, remise à
  disposition ?), présence de dates de début et de fin. Ce que les données
  permettent déjà de dire du **sens d'une ligne qui disparaît**, et ce qu'il
  faudra observer dans les prochaines archives pour conclure.
- **F. Emplacement du jeu de questions.** Proposition :
  `evaluation/questions-reference-v0.toml` à la racine du dépôt (il servira
  à la CI du Lot 3). Avis.
- **G. Reliquats de la mission 00.** Relis la liste de `pr.md` (rubrique
  « Reporté à la mission 01 ») et celle des décisions 9 à 12 ci-dessous.
  Confirme-la ou complète-la ; signale ce qui te paraît inutile.
- **H. Toute autre chose** que ta lecture de l'archive, du PRD ou du code te
  fait remarquer.

## Décisions (sous réserve du §0)

1. **Lecture du bronze** (`src/pharmaflux/bronze.py` ou équivalent) : une
   seule fonction qui liste les archives d'un fichier source, dans l'ordre
   chronologique, et qui en rend les **octets bruts** décompressés. Elle
   ignore les fichiers temporaires (`.*.partiel-*`) et les dossiers
   `.rsync-partiel/` (reliquat de la mission 00). C'est elle que le profil,
   les contrats et `etat` utilisent : aucune autre lecture directe de
   `bronze/`.

2. **Contrats de schéma v0** (`src/pharmaflux/contrats/`) : un contrat par
   fichier TSV de la BDPM (onze), au format retenu au §0 B. Un chargeur
   typé (`mypy --strict`), qui refuse un contrat mal formé avec un message
   clair. La page HTML, le PDF et le JSON de data.gouv n'ont pas de contrat
   dans cette mission : leur lecture est déjà définie par le collecteur.

3. **Vérification d'une archive contre son contrat** : décodage strict dans
   l'encodage déclaré, fin de ligne, nombre de colonnes par ligne, type de
   chaque valeur, valeurs obligatoires présentes, unicité de la clé. Le
   résultat est une liste d'**anomalies** (fichier, ligne, colonne, règle,
   valeur brute tronquée), jamais une correction. Une anomalie ne fait pas
   échouer la lecture du reste du fichier.

4. **`uv run pharmaflux profil [--fichier …] [--racine …] [--archive …]`**.
   Par défaut, la dernière archive de chaque fichier. Pour chacun :
   - la conformité au contrat (nombre d'anomalies par règle, cinq exemples
     au plus par règle) ;
   - le nombre de lignes, l'unicité de la clé ;
   - par colonne : taux de valeurs vides, nombre de valeurs distinctes, et
     pour les énumérations et les colonnes à moins de trente valeurs, la
     répartition complète ; minimum et maximum pour les dates et les
     nombres.

   Sortie lisible dans le terminal, et `--markdown <dossier>` pour écrire
   un fichier par source. Le code de sortie est non nul si une anomalie
   **bloquante** est trouvée (encodage, nombre de colonnes, clé non unique),
   pour que le Lot 5 puisse en faire une alerte de changement de format
   (risque n° 1 du PRD §9).

5. **`docs/donnees/`** : un profil par fichier, produit par
   `pharmaflux profil --markdown` sur l'archive du 24/10 (référence
   d'archive et sha256 en tête de chaque fichier), **plus** un
   `docs/donnees/README.md` écrit par toi : vue d'ensemble, constats
   majeurs, liens CIS ↔ CIP13 entre fichiers (taux de correspondance
   mesuré), encodages. Les extraits de données cités portent la source et
   la date (licence BDPM, PRD §6.2).

6. **ADR** (`docs/adr/`, gabarit `0000-modele.md`) :
   - `0001` — lieu et rythme de la collecte : décision **déjà prise**,
     consignée avec ses raisons et ses limites (VPS partagé, une copie sur
     le Mac, pas de requête conditionnelle, mesure honnête de la
     fraîcheur) ;
   - `0002` — format des contrats de schéma et jeu de types (§0 B et C) ;
   - `0003` — disponibilité : sens d'une ligne qui disparaît et des
     statuts (§0 E). Statut « proposé » si l'archive ne permet pas encore
     de conclure, avec la méthode d'observation et la date à laquelle on
     la revoit ;
   - `0004` — corpus HAS : pages web, PDF ou les deux ; volume estimé
     depuis `HAS_LiensPageCT_bdpm.txt` (nombre de liens, domaines) ;
     licence. C'est ici que servent les cinq requêtes HAS.

7. **Jeu de questions de référence v0** (emplacement du §0 F) :
   **quarante questions**, cinq par catégorie de l'annexe B du PRD. Pour
   chacune : identifiant stable, catégorie, question en français,
   comportement attendu (`reponse`, `abstention`, `refus_medical`), et pour
   une réponse : la date de référence, l'**archive** utilisée (chemin
   relatif et sha256), le fichier, la clé, les colonnes, et la valeur
   attendue.
   - Les questions **Dépense** n'ont pas encore de valeur (Open Medic au
     Lot 4) : `attendu` vide, `calculable_au = "lot4"`.
   - Les questions **Historique** s'appuient sur les dates présentes dans
     les fichiers eux-mêmes (date de début d'une rupture, par exemple),
     pas sur l'historique de l'archive, encore trop court.
   - Les médicaments cités sont réels et pris dans l'archive ; aucune
     question ne vise un patient réel.

8. **`uv run pharmaflux questions verifier [--racine …]`** : relit chaque
   archive citée, vérifie son sha256, recalcule la valeur attendue à partir
   du contrat, et signale tout écart. C'est ce qui rend le jeu
   **rejouable** (PRD annexe B). Testé sur fixtures avec un petit jeu de
   questions dédié.

9. **Reliquats du collecteur** (mission 00, `pr.md`) :
   - `passage.py` : l'ajout des lignes `lien_nouveau` passe sous le filet
     par entrée ; une exception autre qu'`AnalyseImpossible` levée par
     l'empreinte de comparaison **n'empêche plus d'archiver** (l'archive
     est irremplaçable ; la ligne du manifeste porte l'erreur) ;
   - URL de la documentation PDF : prise dans la page, plus figée en `v5`
     (un changement de version devient un `lien_nouveau`, pas une erreur
     404 silencieuse) ;
   - journal `logging` en UTC.

10. **Reliquats de `etat`** : lecture du manifeste en flux (comme le
    passage), affichage de l'identifiant du catalogue, signalement des
    fichiers `.partiel-*` orphelins, lecture du bronze par la décision 1.

11. **Unité systemd : score d'exposition sous 3.** Ajoute ce qui manque
    (`SystemCallFilter=@system-service`, `CapabilityBoundingSet=`,
    `RestrictNamespaces=`, `ProtectKernelLogs=`, `ProtectClock=`,
    `LockPersonality=`, `MemoryDenyWriteExecute=` si Python le supporte…),
    chacun justifié en une ligne dans l'unité. Le README de planification
    donne la commande de mesure et la procédure de mise à jour. **Tu ne
    l'exécutes pas** : beko la valide sur le VPS (voir paliers).
    `OnFailure=` n'est **pas** dans cette mission : une alerte sans canal
    de notification ne sert à rien ; les alertes sont au Lot 5.

12. **Docs** : `docs/CONTEXTE.md` (les contrats, la lecture du bronze, la
    règle « on constate, on ne corrige pas »), `docs/journal.md` (entrée de
    la mission, en fin de fichier), `README.md` (état du projet, commande
    `profil`).

**Outillage** : aucune nouvelle dépendance au projet. La bibliothèque
standard suffit (`tomllib`, `csv`, `gzip`, `hashlib`). Une exception se
justifie au §0.

## Paliers

1. **Reliquats** : décisions 1, 9, 10, 11.
   - Tests d'abord pour chaque reliquat du collecteur (exception de
     l'empreinte, `lien_nouveau` sous le filet, lien du PDF qui change,
     orphelins `.partiel-*`, dossiers `.rsync-partiel/` ignorés).
   - Rapport, commit.
   - **Après ton commit**, beko déploie la branche sur le VPS entre deux
     passages (procédure de mise à jour du README, sur la branche), lance
     un passage manuel et mesure le score. Le résultat entre dans le
     contrôle du palier. Le VPS revient sur `main` à la fusion.
2. **Contrats et vérification** : décisions 2 et 3.
   - Onze contrats ; fixtures étendues si besoin (une anomalie de chaque
     type, sur des lignes fabriquées **à partir de** lignes réelles,
     signalées comme telles dans `tests/fixtures/README.md`).
   - Un test vérifie que **chaque fixture réelle** passe son contrat sans
     anomalie bloquante.
   - Rapport, commit.
3. **Profil, données et ADR** : décisions 4, 5, 6.
   - `pharmaflux profil --markdown docs/donnees` sur l'archive du 24/10,
     sur ton Mac, en lecture seule.
   - ADR 0001 à 0004. Les requêtes HAS (cinq au plus) ont lieu ici.
   - Rapport, commit.
4. **Questions de référence** : décisions 7, 8, 12.
   - `pharmaflux questions verifier` passe sur l'archive du Mac ;
     résultat consigné dans le rapport.
   - Rapport, commit.

Après le contrôle du palier 4 : relecture (`/relire-mission 01`) jusqu'à
« CONFORME », `pr.md`, revue finale, publication et fusion par beko, puis
mise à jour du VPS sur `main`. **La mission est close** quand le VPS tourne
sur `main` avec l'unité durcie (score sous 3 mesuré, un passage planifié
sans erreur) et que `pharmaflux profil` et `pharmaflux questions verifier`
passent sur une copie rapatriée après la fusion.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests | `uv run pytest -q` |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck (même version que la CI) | `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` |
| unité systemd (syntaxe) | `systemd-analyze verify` n'existe pas sur le Mac : relecture, et mesure par beko sur le VPS |

## Hors périmètre

- Normalisation, conversion des types, couche silver, comparaison de
  snapshots, événements, Redpanda : **Lot 1**.
- Téléchargement des CSV Open Medic et questions Dépense chiffrées :
  **Lot 4**.
- Alertes (`OnFailure=`, notification) et tableaux de bord : **Lot 5**.
- Toute requête vers la BDPM ou data.gouv ; plus de cinq requêtes HAS.
- Toute écriture dans l'archive, sur le Mac comme sur le VPS.
- Toute utilisation de l'API Claude : Lot 3.
- **Pas d'usage des VPS d'Alamel**, et rien sur le VPS-1 qui touche à la
  pré-production qu'il héberge.
