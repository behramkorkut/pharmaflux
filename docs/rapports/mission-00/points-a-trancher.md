# Mission 00 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Fable 5.1) · **À :** IeC, beko · **Date :** 24/10/2026
**Branche :** `mission-00-socle-et-archivage` · **Ordre lu sur `main`** (commit
`5faedbc`), addendum 1 compris.

Budget HTTP du §0 respecté : **une requête GET par URL**, 13 URL en tout
(la page de téléchargement, les onze fichiers BDPM, l'API data.gouv), en
série avec 2 s de pause, agent `pharmaflux-s0/0.0 (+…)`. Un écart à
déclarer : le premier appel à data.gouv a échoué **avant toute réponse
HTTP** (`curl: (35) Recv failure: Connection reset by peer`, sur l'adresse
IPv6 NAT64 `64:ff9b::…`) ; je l'ai relancé une fois, avec succès. Aucune
seconde requête sur une URL ayant répondu. Les fichiers téléchargés sont
dans le bac à sable de la session, hors dépôt ; ils serviront aux fixtures
du palier 2.

Lecture rapide : les **trois constats qui changent l'ordre** sont dans C
(aucune requête conditionnelle possible), E/F (deux sources dont l'octet
brut change sans que le fond change) et H.1 (trois faux positifs du
garde-fou).

---

## A. Racine de l'archive

**Constat.**
- `~/pharmaflux-data/` et `~/pharmaflux-collecte/` n'existent pas encore.
  Disque du Mac : 33 Gio libres sur 228 Gio.
- Volume d'un **passage complet** des onze fichiers BDPM, mesuré sur les
  octets reçus (24/10/2026, 13:20 UTC) :

| fichier | octets bruts | gzip (niveau 6) | ratio |
|---|---:|---:|---:|
| CIS_bdpm.txt | 3 175 357 | 399 313 | 0,13 |
| CIS_CIP_bdpm.txt | 4 148 805 | 711 196 | 0,17 |
| CIS_COMPO_bdpm.txt | 2 735 840 | 540 526 | 0,20 |
| CIS_GENER_bdpm.txt | 1 219 514 | 135 357 | 0,11 |
| CIS_CPD_bdpm.txt | 1 336 246 | 143 976 | 0,11 |
| CIS_HAS_SMR_bdpm.txt | 4 630 126 | 628 643 | 0,14 |
| CIS_HAS_ASMR_bdpm.txt | 4 605 173 | 710 565 | 0,15 |
| HAS_LiensPageCT_bdpm.txt | 517 390 | 65 658 | 0,13 |
| CIS_CIP_Dispo_Spec.txt | 153 497 | 15 344 | 0,10 |
| CIS_MITM.txt | 1 618 769 | 176 995 | 0,11 |
| CIS_InfoImportantes.txt | 4 510 790 | 134 888 | 0,03 |
| **total** | **28 651 507** (28,7 Mo) | **3 662 461** (3,7 Mo) | 0,13 |

  (gzip niveau 9 : 3,6 Mo, gain de 2 % pour un temps double ; niveau 6 suffit.)
- Projections annuelles : **si tout changeait chaque jour**, 10,5 Go bruts
  soit **1,3 Go/an compressés** ; si tout changeait à chaque passage horaire
  (irréaliste), 32 Go/an compressés. Rythme réaliste d'après les dates de la
  page (huit fichiers datés du 29/09, les autres du 13/10, 21/10, 23/10) :
  de l'ordre de un à trois fichiers par semaine, soit **moins de 200 Mo/an**.
  Le seul poste qui pourrait gonfler est `CIS_InfoImportantes.txt` si son
  empreinte changeait à chaque heure (135 Ko × 24 × 365 ≈ 1,2 Go/an) ;
  voir E.
- Métadonnées Open Medic (F) : 146 Ko de JSON, 17 Ko compressés, une fois
  par jour : 6 Mo/an.

**Avis.** D'accord avec `~/pharmaflux-data/` par défaut, surchargeable par
`PHARMAFLUX_DATA`, rien dans le dépôt. Le volume est négligeable pour le
disque du Mac ; l'enjeu est la **sauvegarde**, pas la place.

**Question pour beko (relayée).** Une copie hebdomadaire hors du Mac
est-elle possible ? Un `rsync` vers un disque externe ou un dossier
synchronisé (iCloud Drive, Drive…) suffit : moins de 1 Go/an. Je peux
fournir le script et la procédure dans `infra/planification/` (palier 3) ;
beko l'exécute. Sans sauvegarde, l'archive est un point de défaillance
unique : c'est écrit tel quel dans `docs/CONTEXTE.md`.

## B. Où tourne la collecte

**Constat.** Rien à mesurer ; j'ai vérifié les contraintes `launchd` de
tête :
- un agent `launchd` tourne avec un `PATH` minimal : le `.plist` doit poser
  `PATH` (pour `/opt/homebrew/bin/uv`) ou appeler `uv` par chemin absolu ;
- `StartCalendarInterval` : un passage manqué pendant une **veille** est
  rejoué une fois au réveil (les passages manqués sont fusionnés) ; un
  passage manqué **Mac éteint** est perdu ;
- au réveil, le réseau peut mettre quelques secondes à revenir : les trois
  essais avec attente exponentielle (décision 6) couvrent ce cas ; sinon le
  passage est consigné en `erreur`, ce qui est le comportement voulu.
- Le Mac a Python 3.14 (Homebrew) ; le projet est en 3.12 : `uv` télécharge
  et gère son propre interpréteur dans le projet, **sans installation
  système**. `.python-version` = `3.12`.

**Avis.** D'accord : `launchd`, toutes les heures, depuis un clone dédié
`~/pharmaflux-collecte/` sur `main`, `uv sync --frozen` à l'installation
et après chaque fusion, journaux sous `<racine>/journaux/`. Les trous
seront visibles dans le manifeste et dans `pharmaflux etat` (passages des
dernières 24 h). Je garde pour l'ADR ultérieur l'option GitHub Actions
planifié + stockage objet, avec déjà deux arguments mesurés en sa faveur si
les trous sont fréquents : 3,7 Mo par passage, 264 requêtes par jour (D).

**Question pour beko.** Le Mac dort-il la nuit ? Si oui, c'est 6 à 8 h de
trou quotidien dès le départ. Deux issues : « Empêcher la mise en veille
automatique lorsque l'écran est éteint » (réglage de beko), ou accepter
les trous jusqu'à l'ADR de collecte hébergée.

## C. URL de téléchargement et en-têtes HTTP

**Constat.** Page `https://base-donnees-publique.medicaments.gouv.fr/telechargement`
(HTTP 200, 48 Ko, `text/html; charset=UTF-8`, `Cache-Control: no-cache,
private`, un `nonce` CSP différent à chaque réponse). Les liens sont des
chemins relatifs :

| fichier | URL | date affichée | taille affichée |
|---|---|---|---|
| CIS_bdpm.txt | `/download/file/CIS_bdpm.txt` | 29/09/2026 | 3101 Ko |
| CIS_CIP_bdpm.txt | `/download/file/CIS_CIP_bdpm.txt` | 23/10/2026 | 4052 Ko |
| CIS_COMPO_bdpm.txt | `/download/file/CIS_COMPO_bdpm.txt` | 29/09/2026 | 2672 Ko |
| CIS_HAS_SMR_bdpm.txt | `/download/file/CIS_HAS_SMR_bdpm.txt` | 29/09/2026 | 4522 Ko |
| CIS_HAS_ASMR_bdpm.txt | `/download/file/CIS_HAS_ASMR_bdpm.txt` | 29/09/2026 | 4497 Ko |
| HAS_LiensPageCT_bdpm.txt | `/download/file/HAS_LiensPageCT_bdpm.txt` | 29/09/2026 | 505 Ko |
| CIS_GENER_bdpm.txt | `/download/file/CIS_GENER_bdpm.txt` | 29/09/2026 | 1191 Ko |
| CIS_CPD_bdpm.txt | `/download/file/CIS_CPD_bdpm.txt` | 29/09/2026 | 1305 Ko |
| CIS_CIP_Dispo_Spec.txt | `/download/file/CIS_CIP_Dispo_Spec.txt` | 21/10/2026 | 150 Ko |
| CIS_MITM.txt | `/download/file/CIS_MITM.txt` | 13/10/2026 | 1581 Ko |
| CIS_InfoImportantes.txt | `/download/CIS_InfoImportantes.txt` (**autre route**) | aucune (« génération en direct ») | aucune |

- **Stabilité des URL** : ce sont des routes applicatives (site Symfony :
  en-têtes `nelmio/csp`), pas des fichiers statiques ; l'ancien schéma
  `telechargement.php?fichier=` cité par la documentation a disparu. Je les
  tiens pour stables à l'échelle de quelques mois, pas garanties : le
  catalogue doit porter l'URL complète, et le collecteur **relire la page**
  pour détecter un changement de lien (voir D).
- **En-têtes des onze téléchargements** (tous HTTP 200, aucune
  redirection) : **ni `Last-Modified`, ni `ETag`, ni `Content-Length`**
  (`Transfer-Encoding: chunked`). `Content-Type:
  application/octet-stream` sans charset (dix fichiers) et
  `application/force-download` pour InfoImportantes. `Cache-Control:
  private, must-revalidate`, `Pragma: no-cache`, `Expires: 0`.
  `Content-Disposition: attachment; filename="<nom>"`, sauf InfoImportantes
  : `filename=CIS_InfoImportantes_20261024132108_bdpm.txt` (horodatage de
  génération à la seconde, sans guillemets).
- **Requête conditionnelle / 304** : **impossible**. Sans validateur
  (`ETag`, `Last-Modified`), il n'y a rien à mettre dans `If-None-Match`
  ou `If-Modified-Since` ; je n'ai pas dépensé de requête à le vérifier,
  la question est tranchée par les en-têtes. Le statut `non_modifie_304`
  du manifeste restera vide pour la BDPM ; je propose de le garder (coût
  nul, et data.gouv ou une source future peut le fournir).
- **Date de mise à jour par fichier** : oui, affichée pour dix fichiers
  sur onze, dans le texte du lien lui-même, motif fixe
  `(Date de mise à jour : JJ/MM/AAAA, N Ko)`, à l'intérieur du `<a
  href="/download/file/…">` de chaque `<li>`. L'association lien ↔ date se
  fait **dans le même élément**, sans dépendre de l'ordre de la page :
  lisible de façon fiable avec un analyseur HTML, pas d'expression
  régulière sur la page entière. La taille affichée est `octets / 1024`
  arrondi (3 175 357 / 1024 = 3100,9 → 3101 Ko) : elle confirme le fichier
  reçu. Granularité **jour**, date locale (Paris). Elle convient comme
  « date de la source » du PRD §6.3 (`date_source_affichee`), avec deux
  réserves : elle est absente pour InfoImportantes, et elle ne dit rien
  d'une seconde mise à jour le même jour (le 21/10 affiché pour
  Dispo_Spec est bien postérieur à la date la plus récente dans le fichier,
  le 20/10, ce qui est cohérent avec une date de publication).
- Un en-tête global `Dernière mise à jour le 29/09/2026` figure aussi sur
  la page : c'est la date de la base, pas celle des fichiers (Dispo_Spec et
  CIP sont plus récents). À ne pas utiliser.

**Avis.** Le collecteur doit (1) télécharger les onze fichiers sans
condition, (2) lire la page à chaque passage pour remplir
`date_source_affichee` et `taille_affichee_ko`, et signaler un lien
disparu ou nouveau (statut `erreur`, motif `lien_absent`), (3) archiver
la page elle-même uniquement quand ses dates ou tailles changent (le
`nonce` CSP rend son empreinte brute inutile ; voir le mécanisme commun
proposé en E).

## D. Intervalle de collecte

**Constat.** L'hypothèse « coût quasi nul d'un passage inchangé » tombe
avec C : chaque passage complet transfère 28,7 Mo en onze requêtes. Durée
mesurée du passage : 18,4 s de transfert (0,25 à 5 s par fichier, débit
de 1 à 3 Mo/s), soit ~45 s avec les pauses de 2 s. Toutes les heures : 264
requêtes et ~690 Mo par jour, depuis une seule adresse identifiée.

**Avis.** Je recommande quand même **toutes les heures, à `:17`, en
série, pause de 2 s**, pour la mission 00, et je note le point pour un
ADR après quelques semaines de manifeste :
- c'est la seule façon de **garantir** la détection sans validateur ;
- la charge reste modeste pour un service national de données ouvertes
  (le serveur a servi 28 Mo en 18 s sans ralentir) et nous sommes
  identifiés (`User-Agent` avec l'URL du dépôt) ;
- le manifeste enregistrera, à chaque passage, la date affichée **et**
  l'empreinte reçue : au bout de quelques semaines on saura si la date
  de la page suffit à prédire un changement. Si oui, l'ADR pourra passer à
  « page toutes les heures, fichiers seulement quand leur date ou taille
  change, plus un passage complet par jour » (≈ 1,2 Mo/jour au lieu de
  690). Je ne propose pas cette variante tout de suite : elle rate une
  seconde mise à jour du même jour à taille arrondie égale, et le PRD §2.2
  vise un p95 < 30 min.
- Point de cohérence PRD à trancher (voir H.3) : avec un passage par
  heure, le seul délai de collecte a un p95 d'environ 57 min, au-dessus de
  la cible de 30 min du §2.2.

**Question pour l'IeC.** Horaire : `:17` ; ou toutes les 30 min (`:17` et
`:47`, 1,4 Go/jour) pour tenir le §2.2 ? Mon avis : l'heure, et réviser
l'indicateur plutôt que doubler la charge d'une source qui change une à
trois fois par semaine.

## E. `CIS_InfoImportantes.txt`

**Constat** (une seule requête, donc pas de comparaison entre deux
téléchargements) :
- la partie « générée » visible est le **nom de fichier** dans
  `Content-Disposition` (`CIS_InfoImportantes_<AAAAMMJJhhmmss>_bdpm.txt`,
  et `download='CIS_InfoImportantes_*_bdpm.txt'` sur la page). Le corps
  (4,5 Mo, 10 905 lignes, 4 colonnes tabulées : CIS, date de début, date de
  fin, lien HTML vers l'ANSM) **ne contient aucun horodatage de
  génération** : zéro occurrence de la date ou de l'heure du
  téléchargement ; dates de début de 2018-03-01 à 2026-09-25, aucune
  ligne postérieure au 1er octobre ;
- les lignes **ne sont pas triées** (ni par CIS, ni par date ; 5 128 CIS
  distincts, aucune ligne en double) : l'ordre est celui d'une requête en
  base sans tri explicite. C'est le vrai risque : un **ordre différent à
  chaque génération** donnerait une empreinte différente à contenu égal,
  donc 24 archives par jour (1,2 Go/an) et un faux « changement » toutes
  les heures dans le flux du Lot 1.

**Avis / règle proposée.** Un mécanisme unique, déclaré dans le catalogue
par entrée, qui sert aussi à C (page) et F (data.gouv) :
- `sha256` du manifeste et contenu archivé : **toujours les octets bruts**
  (licence BDPM, rejeu) ;
- `empreinte_comparaison` : par défaut le même sha256 ; pour
  InfoImportantes, le sha256 de **l'ensemble des lignes triées** ; pour la
  page, le sha256 des couples (fichier, date, taille) ; pour data.gouv, le
  sha256 d'une projection stable (F). La décision « nouvelle copie ou
  `inchange` » se prend sur `empreinte_comparaison` ; les deux empreintes
  sont écrites dans le manifeste.
- Justification contre « un archivage par jour » : un réordonnancement
  n'est pas un changement, alors qu'une vraie information importante
  publiée à 10 h doit être vue au passage de 10 h 17, pas le lendemain.
  Et contre « empreinte sans la partie générée » : il n'y a pas de partie
  générée dans le corps, seulement un ordre.
- Nom d'archive : celui du catalogue (`CIS_InfoImportantes.txt`), jamais le
  nom généré ; le nom reçu va dans le manifeste (`content_disposition_nom`).

**Question pour l'IeC.** Pour trancher E avant d'écrire les fixtures du
palier 2, autorises-tu **une seule requête supplémentaire** sur cette URL
(le seul dépassement du budget du §0 que je demande) ? Sinon, la règle
ci-dessus est écrite d'emblée et les 24 premières heures de passages
planifiés la confirmeront ou l'infirmeront.

## F. Open Medic dans cette mission

**Constat.** URL de l'API :
`https://www.data.gouv.fr/api/1/datasets/open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes/`
(HTTP/2 200, `application/json`, `Content-Length: 146025`, 17 Ko
compressés, `Cache-Control: public`, pas de `ETag` ni `Last-Modified`
non plus). Identifiant stable du jeu : `566e964188ee3875beaf0bf5`,
licence `fr-lo`, fréquence `annual`, 85 ressources (`id` stables, `title`,
`url`, `format`, `created_at`, `last_modified`, `description`, `extras`).
Trois surprises :
1. `filesize` et `checksum` sont **nuls** pour les 85 ressources ;
2. `last_modified` par ressource est **un artefact du robot de
   data.gouv** : 84 ressources sur 85 ont
   `analysis:last-modified-detection = computed-checksum` sur un contenu
   de type `text/html` de 1 574 ou 3 121 octets (le serveur
   `open-data-assurance-maladie.ameli.fr` renvoie une page HTML au robot,
   pas le CSV). Ces dates valent toutes « hier ou aujourd'hui » et bougent
   à chaque vérification du robot ; `last_update` du jeu (24/10/2026
   11:29) en est le maximum. **Inutilisables** comme date de publication ;
3. ce qui est fiable : `last_modified` **du jeu** (2026-07-11T20:34, qui
   correspond au correctif « région du bénéficiaire 2025 » du PRD),
   `created_at` de chaque ressource (les sept ressources 2025 : 11/07/2026)
   et la liste même des ressources. Les URL des bases 2014 à 2021 sont en
   **`http://`**, les autres en `https://` (à noter pour le Lot 4).
   Le JSON contient aussi des compteurs (`metrics.views`…) qui changent
   tous les jours : son empreinte brute ne sera jamais stable.

**Avis.** Oui aux métadonnées seulement, **une fois par jour** (attribut de
cadence dans le catalogue : `quotidienne`, les autres entrées étant
`chaque_passage`), archivage du JSON brut, et `empreinte_comparaison`
calculée sur la projection (`id`, `title`, `url`, `format`, `created_at`,
`description` de chaque ressource ; `last_modified` et nombre de
ressources du jeu). Ainsi une nouvelle base annuelle ou un correctif
produit `nouveau`, et le bruit du robot produit `inchange`. Correction à
proposer au PRD §6.1 : « la page data.gouv.fr indique les dates de mise à
jour par fichier » est vrai à l'écran mais ces dates sont celles du robot ;
la date utile est `created_at` de la ressource (et `last_modified` du jeu).

## G. Dépôt public

Tranché par beko : public. Rien à ajouter.

## H. Autres remarques

**H.1 Trois faux positifs du garde-fou Claude Code** (signalés, non
contournés ; les lectures ont été refaites avec des commandes `cat` ou
`sed -n` simples). Commandes exactes refusées :

1. ```
   git status --short && git log --oneline -5 && echo "--- main vs branche ---" && git log --oneline main -3 && echo "--- arbo ---" && find . -path ./.git -prune -o -path ./data -prune -o -type f -print | grep -v '/\.git/' | sort | head -80 && echo "--- dossiers ---" && ls -la
   ```
   Refus : « opération git « prune » interdite ». Cause : le filet
   `GIT_ECRIT_BRUT` cherche `\bgit\b … prune` dans les arguments de
   `find`, et `./.git` contient le mot `git`. Piste : exclure le mot
   précédé de `.` ou `/` (`(?<![./])\bgit\b`).
2. ```
   grep -n -i -E "prune|curl|wget|httpx|reseau|réseau|MOTIFS|interdit|def |re\.compile|\bgit\b" .claude/hooks/garde_fou.py | head -80
   ```
   Refus : « `\bgit\b"` sur un chemin réservé : en lecture seulement ».
3. ```
   grep -n -i -E 'trailer|Commis|Co-Authored|reserv|RESERV|refus|main|HEAD' infra/git-hooks/pre-commit | head -30
   ```
   Refus : « `HEAD'` sur un chemin réservé : en lecture seulement ».
   Cause commune à 2 et 3 : `segments()` découpe sur `|` **y compris
   entre guillemets**, si bien que chaque branche d'une alternance `grep
   -E 'a|b'` devient une « commande » dont la tête n'est pas dans
   `LECTURE`. Piste : découper avec `shlex` d'abord (les opérateurs `|`,
   `&&`, `;` hors guillemets sont alors des mots isolés), puis segmenter
   sur ces mots. Conséquence pratique : **toute recherche `grep -E` avec
   alternance sur un chemin réservé est refusée**, ce qui gênera le
   relecteur aussi. Je ne touche pas au crochet (chemin réservé) ; je
   propose d'ajouter ces trois cas à `infra/agents/test_garde_fou.py`.

**H.2 Encodages hétérogènes, déjà visibles.** Neuf fichiers sont en
Windows-1252 (octets 0x80–0x9F présents : œ, apostrophes typographiques)
avec fins de ligne CRLF ; `HAS_LiensPageCT_bdpm.txt` est en ASCII pur
CRLF ; **`CIS_CIP_bdpm.txt` et `CIS_InfoImportantes.txt` sont en UTF-8 avec
LF**. `CIS_CIP_bdpm.txt` est précisément le fichier mis à jour le 23/10 :
soit il a toujours été à part, soit une chaîne de production a changé.
Sans incidence sur la mission 00 (archive à l'octet près), mais le
contrat de schéma de la mission 01 devra porter **l'encodage et la fin de
ligne par fichier**, et le profilage devra comparer avec une archive
antérieure si elle existe. Les en-têtes HTTP n'annoncent aucun charset :
le PRD §6.2 (« encodage source détecté ») est confirmé.

**H.3 Cohérence PRD §2.2 / intervalle.** La cible « p95 < 30 min entre la
mise à jour d'un fichier et sa disponibilité dans l'assistant, dont
l'intervalle de collecte » est intenable avec un passage par heure
(voir D). Le PRD prévoit « à affiner au Lot 0 » : je propose de l'affiner
en « < 90 min avec collecte horaire », ou de découpler l'indicateur
(délai de collecte d'une part, délai de traitement de l'autre, ce dernier
étant déjà le second indicateur du tableau).

**H.4 Champs du manifeste.** Je propose d'ajouter à la décision 5 :
`empreinte_comparaison` (E), `taille_affichee_ko` et
`content_disposition_nom` (C), `version_collecteur` (version du paquet et
commit, pour le rejeu), `essais` (nombre de tentatives HTTP). Les champs
`etag` et `last_modified` restent, à `null` pour la BDPM.

**H.5 Catalogue.** Douze entrées BDPM (onze fichiers plus
`bdpm.page_telechargement`) et une entrée `openmedic.metadonnees` ; par
entrée : identifiant, URL, nom de fichier d'archive, extension
(`.txt.gz`, `.html.gz`, `.json.gz`), cadence, mode d'empreinte de
comparaison. Entrée page : pas une « source » de données, mais la
preuve datée de ce que le site affichait.

**H.6 Relance.** L'échec TCP sur data.gouv (IPv6) plaide pour distinguer,
dans la décision 6, l'erreur de connexion (relance immédiate, puis
exponentielle) de la réponse 5xx (attente exponentielle d'emblée), et
pour consigner `essais` dans le manifeste.

**H.7 `.DS_Store`** est suivi par git à la racine (commit `5faedbc`). Je
l'ajoute au `.gitignore` du palier 1, mais le retirer de l'index demande
`git rm --cached`, que mon rôle ne permet pas : à faire par beko sur
`main`, ou à m'autoriser explicitement.

**H.8 URL du dépôt** pour le `User-Agent` (décision 6) : j'ai utilisé
`https://github.com/behramko/pharmaflux` au §0 par supposition. Merci de
me donner l'URL publique exacte avant le palier 2.

**H.9 `uv` et Python 3.12.** Rien à installer : `uv` gère l'interpréteur
dans le projet. Si beko préfère un Python 3.12 système, c'est son geste.

---

## Récapitulatif des décisions attendues

| point | ce que je demande |
|---|---|
| A | sauvegarde hebdomadaire hors du Mac : oui / non, et où (beko) |
| B | le Mac dort-il la nuit ? réglage ou trous acceptés (beko) |
| C | validation : téléchargements sans condition, page lue à chaque passage, archivée sur changement de ses dates ou tailles |
| D | toutes les heures à `:17` (mon avis) ou toutes les 30 min |
| E | mécanisme `empreinte_comparaison` ; autorisation d'une requête supplémentaire sur InfoImportantes |
| F | métadonnées une fois par jour, projection stable ; correction PRD §6.1 |
| H.1 | garde-fou : trois faux positifs à corriger côté IeC |
| H.3 | affinage de l'indicateur §2.2 |
| H.4–H.5 | champs du manifeste et entrées du catalogue ajoutés |
| H.7–H.8 | `.DS_Store` ; URL publique du dépôt |
