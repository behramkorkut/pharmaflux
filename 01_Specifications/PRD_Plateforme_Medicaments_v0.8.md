# PRD — Plateforme temps réel de connaissance du médicament pour l'assurance santé

**Projet :** Pharmaflux — projet portfolio
**Client :** client fictif — **direction santé d'une mutuelle** de taille moyenne (personas §3). Aucune donnée client : uniquement des données publiques réelles.
**Version :** 0.8 _(après la mission 06 : le Lot 2 est fait ; Lot 3 découpé, fragments et index précisés pour la mission 07)_
**Date :** 29 octobre 2026 _(v0.1 : 23 octobre 2026 ; v0.2 à v0.4 : 26 octobre 2026 ; v0.5 : 27 octobre 2026 ; v0.6 : 28 octobre 2026 ; v0.7 : 29 octobre 2026)_
**Auteur :** Behram Korkut

**Sources de données (publiques, réelles) :**

- **Base de données publique des médicaments (BDPM)** — ANSM / HAS / Assurance Maladie, page de téléchargement : <https://base-donnees-publique.medicaments.gouv.fr/telechargement> — spécialités, présentations, compositions, génériques, conditions de prescription, avis SMR/ASMR de la HAS, **disponibilité (`CIS_CIP_Dispo_Spec.txt`)**, **médicaments d'intérêt thérapeutique majeur (`CIS_MITM.txt`)**, informations importantes
- **Open Medic** — Cnam, data.gouv.fr : <https://www.data.gouv.fr/datasets/open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes> — dépenses de médicaments remboursées, bases annuelles 2014 → 2025
- **Avis de la Commission de la transparence (HAS)** — liens fournis par la BDPM (`HAS_LiensPageCT_bdpm.txt`) — corpus textuel du RAG
- _Extensions possibles (Lot 6)_ : Open PHMEV, Open DAMIR, extraction de l'Annuaire Santé (agrégée uniquement)

**Projets antérieurs réutilisés :**

- `governed-omop-rag` — retrieval hybride BM25 + dense, porte d'abstention, évaluation sur gold set, taxonomie des échecs
- `governed-analytics-agent` — couche sémantique, agent qui ne calcule jamais lui-même, lane quasi temps réel, contrôle de fraîcheur
- ECP / Cloclo — connaissance métier de la mutuelle santé, garde-fous d'un agent en production
- Alamel — circuit de travail (ordres de mission, paliers, relecture par PR, garde-fous git) : annexe C

---

## Journal des évolutions

| # | Évolution | Origine |
|---|---|---|
| 1 | Création du PRD v0.1 | Cadrage du 23/10/2026 : domaine santé × assurance, données publiques réelles, méthode Alamel |
| 2 | PRD v0.2 : nom Pharmaflux retenu ; collecte **horaire** sur le VPS-1 de beko, partagé avec une pré-production jusqu'à mi-novembre 2026 ; pas de requête conditionnelle ; indicateur de fraîcheur découplé (§2.2) ; dates utiles de data.gouv (§6.1) ; constats sur les encodages et les formats (annexe A, avec le §0 de la mission 01) ; sens d'une ligne qui disparaît de la disponibilité (§6.3) ; points 5, 6 et 8 du §10.2 reportés à leur lot ; circuit local (annexe C) | Mission 00 (24-25/10/2026) : réponse au §0, addendum 2, 24 h de passages sur le VPS |
| 3 | PRD v0.3 : Lot 0 soldé (§4) ; contrats de schéma v0 et règle de version (§6.2) ; **fichier servi vide** et garde-fou de volume (§6.1, §6.3, §9) ; points 2, 3, 4 et 7 du §10.2 tranchés par les ADR 0001 à 0004 ; annexe A avec colonne « Statut » ; annexe B : comportement attendu, archive citée, réponse avec réserve ; messages directs entre sessions pour la routine (annexe C) | Mission 01 (26/10/2026) : PR #2, contrôles des paliers 3 et 4, relecture 1, passages du 26/10 sur le VPS |
| 4 | PRD v0.4 : avancement du Lot 1 (§4) ; forme canonique par type et forme déclarée vérifiée par une mesure (§6.2) ; valeur illisible gardée brute, et non rejetée (§6.2) ; schéma d'événement v1, identité d'une ligne sans clé unique, ordre des colonnes et des rangs, garde-fou de volume chiffré, premier snapshot (§6.3) ; reprise égale au rejeu complet (§7.1) ; mémoire de pointe au-dessus du plafond du VPS (§9) | Mission 02 (26/10/2026) : PR #3, ADR 0005 et 0006, contrôles des paliers 1 à 3, relectures 1 et 2 |
| 5 | PRD v0.5 : avancement du Lot 1 (§4) ; bus précisé : topics, clé, valeur, compatibilité des schémas, rétention, file des messages en échec, vérification (§6.4) ; publication sans perte ni doublon d'identifiant, reprise (§7.1) ; jeu de démo figé dans le dépôt, rejeu accéléré dans l'ordre des observations, `make up` (§7.3) ; risque mémoire levé, rythme réel mesuré (§9) | Mission 03 (27/10/2026) : PR #4, ADR 0007, contrôles des paliers 1 à 3, relecture 1, contrôle final ; ordre de la mission 04 |
| 6 | PRD v0.6 : Lot 1 fait sur le Mac, seul le VPS reste (§4) ; Lot 2 découpé en deux missions (§4) ; silver précisé : tables Iceberg par entité, historisation sur la date d'observation, « état à une date », vérification contre l'archive, consommateur du bus idempotent (§6.5) ; silver reconstruit identique depuis le bus ou depuis les fichiers d'événements (§7.1) ; mémoire de la démo mesurée (§9) | Mission 04 (27/10/2026) : PR #5, ADR 0008, contrôles des paliers 1 à 3, relecture 1, contrôle final, premier passage de la CI ; ordre de la mission 05 |
| 7 | PRD v0.7 : Lot 2, mission 05 faite (§4) ; gold précisé : colonnes typées par entité, vues métier, valeur illisible jamais devinée, gold calculé depuis le silver à un instant donné, contrôles de qualité (§6.5) ; jeu de questions recalculé depuis le gold (annexe B) ; mémoire du silver mesurée, le silver tourne sur le Mac en v1, seuil d'alerte de 512 Mo (§9) | Mission 05 (28-29/10/2026) : PR #6, ADR 0009, contrôles des paliers 1 à 3, relectures 1 et 2, contrôle final ; ordre de la mission 06 |
| 8 | PRD v0.8 : **Lot 2 fait** (§4) ; Lot 3 découpé en trois missions (§4) ; limite de la détection : une valeur brute illisible égale à la forme canonique de la précédente ne produit aucun événement (§6.3, §9) ; fragments et index précisés : texte déterministe depuis le gold, état courant seulement, mise à jour incrémentale, index égal à sa reconstruction complète (§6.7) ; mémoire du gold mesurée (§9) ; point 5 du §10.2 confié à la mission 07 | Mission 06 (29/10/2026) : PR #7, ADR 0010, contrôles des paliers 1 à 3, relecture 1, contrôle final ; ordre de la mission 07 |

---

## 1. Contexte

### 1.1 Le domaine

En France, un médicament remboursé fait intervenir trois mondes : l'**ANSM** (autorisation, sécurité, disponibilité), la **HAS** (service médical rendu, amélioration du service médical rendu) et l'**assurance** — l'Assurance Maladie obligatoire (AMO), qui fixe le taux de remboursement, puis la **complémentaire santé** (mutuelle, assureur), qui prend en charge tout ou partie du reste.

Une mutuelle a donc besoin de savoir, en continu, ce qui change sur les médicaments : une rupture de stock pousse vers un autre médicament (souvent plus cher), un changement de taux de remboursement déplace la dépense vers la complémentaire, un nouveau générique la fait baisser.

### 1.2 Le client fictif

Une mutuelle santé régionale d'environ 300 000 adhérents. Une équipe data de quatre personnes, une cellule « études santé », un pharmacien conseil, un centre de relation adhérents. Les personas du §3 sont construits sur ce profil.

### 1.3 L'existant — les sources publiques et leurs limites

| Source | Forme | Limite |
|---|---|---|
| BDPM — fichiers de référence | Fichiers texte tabulés, **sans en-tête**, un fichier par thème | Pas d'historique, pas de journal des modifications : chaque téléchargement écrase le précédent |
| BDPM — disponibilité | `CIS_CIP_Dispo_Spec.txt` | Fichier mis à jour à son propre rythme (dates différentes d'un fichier à l'autre, constatées le 23/10/2026) ; une situation qui se normalise **disparaît** du fichier |
| BDPM — MITM | `CIS_MITM.txt` | Liste à plat, sans date d'entrée ni de sortie |
| Open Medic | CSV annuels, documentation xlsx | Granularité **annuelle** ; base complète au niveau ATC, CIP13 seulement dans les bases complémentaires ; honoraires de dispensation exclus ; anomalies corrigées a posteriori (région du bénéficiaire 2025, corrigée le 10/07/2026) |
| Avis HAS | Pages web et PDF | Texte non structuré, longueur variable |

Le point le plus révélateur : **aucune de ces sources ne publie d'événement**. Elles publient un état. Savoir *ce qui a changé*, *quand*, et *ce que l'on savait à une date donnée* est un travail d'ingénierie à construire.

### 1.4 Le problème

| Problème | Conséquence pour la mutuelle |
|---|---|
| Les changements (ruptures, remises à disposition, nouveaux génériques, avis HAS) ne sont connus que par veille manuelle | Réaction tardive ; conseillers qui répondent avec une information périmée |
| Les sources ne gardent pas d'historique | Impossible de reconstituer ce que l'on savait au moment d'une décision (audit, réclamation) |
| Les données de dépense (annuelles) et de disponibilité (quasi quotidiennes) ne se croisent pas | Aucune estimation de la dépense exposée à une rupture |
| Les assistants IA du marché répondent sans source ni date | Risque d'information de santé erronée, inacceptable pour un organisme de santé |

### 1.5 L'axe structurant du projet

**Transformer des publications d'état en un flux d'événements gouverné, rejouable et daté.** Tout le reste — historique, indicateurs, assistant — se branche sur ce flux. La qualité du projet se juge d'abord là : aucun changement perdu, aucun doublon, tout rejouable depuis les fichiers bruts archivés.

### 1.6 Le second axe — l'IA gouvernée

L'assistant ne répond **qu'à partir du flux et du corpus**, **cite chaque source avec sa date**, **s'abstient** quand il ne sait pas, et **ne donne jamais de conseil médical**. Même parti pris que `governed-omop-rag` : l'IA seulement là où elle apporte, mesurée sur un jeu de questions de référence.

---

## 2. Objectifs et indicateurs

### 2.1 Objectifs

1. **Détecter chaque changement des sources** et le publier comme événement daté, une seule fois.
2. **Conserver l'histoire complète** et pouvoir répondre « que savait-on le JJ/MM à HH:MM ? ».
3. **Répondre aux questions métier** (disponibilité, remboursement, alternatives) avec une information fraîche, sourcée et datée.
4. **Croiser disponibilité et dépense** pour estimer la dépense exposée aux ruptures.
5. **Exploiter le système comme en production** : objectifs de service mesurés, alertes, runbook, incidents documentés.
6. **Rendre le projet reproductible** : une commande pour tout lancer sur un portable, une CI qui le prouve.

### 2.2 Indicateurs

| Indicateur | Cible v1 |
|---|---|
| Délai de collecte : entre la mise à jour d'un fichier source et son archivage | ≤ 60 min **par construction** (un passage par heure, §6.1) ; mesuré depuis le manifeste |
| Délai de traitement d'un événement, de sa détection à l'index vectoriel (p95) | < 60 s |
| Événements perdus ou en double lors d'un rejeu complet depuis les fichiers bruts | 0 |
| Reconstruction de l'état à une date passée, comparée au fichier archivé du même jour | identique (empreinte égale) |
| Réponses correctes sur le jeu de questions de référence (annexe B) | ≥ 85 % |
| Réponses citant une source et sa date | 100 % |
| Abstention sur les questions hors périmètre ou médicales | 100 % |
| Réponses périmées lors du test de fraîcheur (changement injecté puis question posée) | 0 |
| Coût LLM pour 1 000 questions | à mesurer, plafond fixé au Lot 0 |
| Lancement complet sur un MacBook (`make up`) | < 10 min, une seule commande |

---

## 3. Personas

### P1 — Claire, chargée d'études santé (persona principal)
Suit la dépense médicaments de la mutuelle et prépare les notes pour la direction.
**Besoin :** savoir chaque matin ce qui a changé, et combien cela pèse dans la dépense ; pouvoir remonter dans le temps.
**Contrainte :** ne fait confiance qu'à un chiffre dont elle connaît la source et la date.

### P2 — Dr Martin, pharmacien conseil
Valide les positions de la mutuelle sur les médicaments et répond aux cas complexes.
**Besoin :** les alternatives disponibles à un médicament en rupture (même groupe générique, même substance), avec les avis HAS correspondants.
**Contrainte :** refuse toute réponse sans référence vérifiable.

### P3 — Yanis, conseiller relation adhérents
Répond au téléphone et par chat à des adhérents inquiets (« mon médicament est introuvable, je serai remboursé pareil ? »).
**Besoin :** une réponse en quelques secondes, en langage simple, sur la disponibilité et le remboursement.
**Contrainte :** ne doit jamais donner de conseil médical ; l'assistant doit l'en empêcher.

### P4 — Inès, data engineer d'astreinte
Exploite la plateforme.
**Besoin :** savoir immédiatement si une source a changé de format, si le flux prend du retard, et rejouer sans risque.
**Contrainte :** documentation d'exploitation à jour, alertes qui ont un sens.

### P0 — Le lecteur du portfolio (recruteur, tech lead)
Persona du projet lui-même : il ouvre le dépôt dix minutes.
**Besoin :** comprendre le problème, voir l'architecture, les décisions et les chiffres mesurés, lancer la démo.
**Contrainte :** le README doit tenir sa promesse en un écran ; chaque affirmation renvoie à une mesure ou à un test.

---

## 4. Périmètre — découpage par lots

Chaque lot est livrable et démontrable seul, dans l'ordre indiqué.

### Lot 0 — Cadrage et exploration des données

- Tranche les points du §10.2 qui en relèvent (ADR pour chacun).
- **Lance l'archivage des fichiers bruts dès le premier jour** : l'historique n'existe que si on commence à le collecter (§10.1). _Fait par la mission 00 : collecte horaire en service depuis le 24/10/2026._
- Contrats de schéma v0 de chaque fichier (encodage, colonnes, types, clé), vérifiés par la CI.
- Profilage de chaque fichier : colonnes, encodage, formats de dates, clés, anomalies → `docs/donnees/`.
- Constitution d'une première version du jeu de questions de référence (annexe B).
- _Soldé par la mission 01 (fusionnée le 26/10/2026) : onze contrats TOML dans le paquet, chargés et testés par la CI sur des fixtures réelles ; `pharmaflux profil` mesure n'importe quelle archive contre son contrat ; ADR 0001 à 0004 ; quarante questions de référence rejouables (`pharmaflux questions verifier`)._

### Lot 1 — Socle : collecte, détection des changements, flux d'événements

- Collecte planifiée des fichiers BDPM, archivage brut immuable (couche bronze), empreinte par fichier.
- Normalisation (encodage, typage, clés) **pilotée par les contrats de schéma** et **détection des changements par comparaison de snapshots** : création, modification, suppression ; un snapshot vide ou anormalement réduit n'est jamais lu comme une suppression en masse (§6.3).
- Publication des événements dans Redpanda, contrats de schéma, file des messages en échec.
- Idempotence et rejeu complet depuis le bronze.
- `docker compose` local, CI (lint, types, tests unitaires et d'intégration).
- _Avancement : la collecte est en service depuis la mission 00. La mission 02 (fusionnée le 26/10/2026) va du bronze aux événements : `pharmaflux evenements` normalise chaque archive, la compare au dernier snapshot retenu, et écrit les événements et un bilan par archive, avec rejeu complet et reprise. Elle ne tourne que sur le Mac. La mission 03 (fusionnée le 27/10/2026) écrit les événements en flux (474 Mo → 118 à 149 Mo résidents au rejeu complet), les publie dans un Redpanda local (`docker compose`, projet `pharmaflux`), avec un registre de schémas et une file des messages en échec, et vérifie le bus contre le dernier snapshot retenu ; la CI a un job d'intégration. La mission 04 (fusionnée le 27/10/2026) fournit un jeu de démo figé dans le dépôt (`demo/archive`, 67 h de collecte réelle) et le rejeu accéléré : sur un clone neuf, `make up` puis `make demo` publient ce jeu dans l'ordre des observations en 4 min, et finissent par un `verifier-bus` conforme ; la CI lance la démo à chaque PR. **Le Lot 1 est fait sur le Mac.** Reste l'exécution sur le VPS, après le départ de la pré-production voisine (mi-novembre 2026)._

### Lot 2 — Lakehouse, historique et voyage dans le temps

- Couches silver et gold en Iceberg, interrogées avec DuckDB.
- Historisation des référentiels (SCD2) : présentations, disponibilité, MITM, taux de remboursement, groupes génériques.
- Requête « état au JJ/MM/AAAA HH:MM » et vérification contre le fichier archivé du même jour.
- Contrôles de qualité automatiques (unicité des clés, référentiel CIS ↔ CIP13 cohérent, volumes attendus).
- _Découpage (28/10/2026) : le Lot 2 commence sur le Mac, sans attendre le VPS. La **mission 05** construit le silver (un consommateur du bus, une table historisée par entité), la requête « état à une date » et sa vérification contre l'archive. La **mission 06** construira le gold (fiche médicament, disponibilité courante) et les contrôles de qualité._
- _Avancement : la mission 05 (fusionnée le 29/10/2026) a livré le silver. Une table Iceberg par entité est alimentée par un consommateur du bus idempotent, qui garde sa position dans le commit Iceberg. Le silver se construit à l'identique depuis les fichiers d'événements. `pharmaflux silver etat` répond « état à une date », et `silver verifier` est conforme sur les 22 archives du jeu de démo (18 retenues, 4 écartées). `make silver` enchaîne les deux après `make demo`, et la CI le lance (38 s) (ADR 0009). La mission 06 (fusionnée le 29/10/2026) a livré le gold, calculé à la demande depuis le silver à un instant, sans table stockée : colonnes typées par entité (une valeur illisible n'est jamais devinée), fiche médicament (21 445 CIS sur le jeu, dont 5 562 fiches partielles), disponibilité courante, alternatives, quatorze contrôles de qualité (quatre bloquants). Les 25 questions du jeu v0 qui attendent une réponse concordent depuis le gold et depuis le bronze. `make gold` les lance après `make silver`, et la CI aussi (17 s) (ADR 0010). **Le Lot 2 est fait sur le Mac.**_

### Lot 3 — Assistant gouverné en temps réel

- Indexation incrémentale : fiches médicament construites à partir du gold + avis HAS ; **mise à jour et suppression** des fragments quand la source change.
- Retrieval hybride (repris de `governed-omop-rag`), réponses sourcées et datées, porte d'abstention, refus du conseil médical.
- API (FastAPI) et interface (Streamlit).
- Évaluation automatique sur le jeu de référence à chaque PR ; test de fraîcheur de bout en bout.
- _Découpage (29/10/2026), sur le Mac comme le Lot 2 :_
  - _**mission 07** : les fragments de la fiche médicament, l'index vectoriel et sa mise à jour incrémentale depuis le bus, sans LLM (§6.7). Elle commence par fiabiliser l'intégration continue ;_
  - _**mission 08** : le corpus des avis HAS (ADR 0004), le retrieval hybride, les réponses sourcées et datées, l'abstention, le refus médical, le jeu de questions v1 ;_
  - _**mission 09** : l'API, l'interface, l'évaluation dans la CI et le test de fraîcheur de bout en bout._

  _Le découpage des missions 08 et 09 se revoit à la fin de la mission 07._

### Lot 4 — Volet assurance : dépense et exposition

- Ingestion d'Open Medic (bases annuelles), rattachement aux médicaments par ATC et CIP13.
- Indicateurs : dépense remboursée par classe ATC, **dépense de l'année précédente exposée aux ruptures en cours**, part des génériques.
- Couche sémantique : chaque indicateur défini une seule fois, utilisé par le tableau de bord et par l'assistant (repris de `governed-analytics-agent`).

### Lot 5 — Observabilité et exploitation

- Traces OpenTelemetry de la collecte au LLM ; tableaux de bord : fraîcheur par source, retard du flux, coût et latence LLM, qualité des réponses.
- Objectifs de service (§2.2) mesurés et alertes.
- Runbook ; **incidents provoqués** (changement de format d'un fichier, consumer arrêté, topic rejoué) et leurs post-mortems.
- Réindexation complète sans interruption lors d'un changement de modèle d'embedding (bascule blue/green).

### Lot 6 — Extensions (optionnel)

- Serveur MCP exposant la plateforme à des agents, avec garde-fous.
- Sources supplémentaires : Open PHMEV, Open DAMIR, Annuaire Santé agrégé.
- Démo publique hébergée.

---

## 5. Parcours cible — un changement de bout en bout

> **Contexte.** Le fichier de disponibilité de la BDPM est mis à jour : une présentation d'amoxicilline passe en tension d'approvisionnement.

1. **Collecte.** Au passage planifié suivant, le collecteur constate que l'empreinte du fichier a changé. Il archive le fichier brut, horodaté, dans le bronze.
2. **Détection.** La comparaison avec le snapshot précédent produit un événement `disponibilite.modifiee` (clé : CIS + CIP13 ; état avant, état après ; date de la source ; date d'observation ; version du schéma).
3. **Flux.** L'événement est publié dans Redpanda. Trois consommateurs le lisent indépendamment.
4. **Historique.** Le consommateur lakehouse ferme la ligne SCD2 précédente et ouvre la nouvelle.
5. **Index.** Le consommateur d'indexation reconstruit la fiche du médicament et remplace ses fragments dans la base vectorielle.
6. **Indicateurs.** Le consommateur assurance recalcule la dépense exposée aux ruptures.
7. **Réponse.** Yanis demande : « L'amoxicilline 500 mg est-elle disponible ? » L'assistant répond qu'une tension est déclarée, cite la BDPM et sa date, et indique les présentations du même groupe générique disponibles — sans recommandation médicale.
8. **Mesure.** Le délai de chaque étape est tracé ; le tableau de bord de fraîcheur l'affiche.

---

## 6. Spécifications fonctionnelles

### 6.1 Collecte

- Téléchargement de chaque fichier de la BDPM **toutes les heures, à `:17`**, en série, avec une pause de 2 s entre deux fichiers. Le serveur n'envoie ni `Last-Modified` ni `ETag` : pas de requête conditionnelle possible, d'où un intervalle d'une heure plutôt que plus court (mission 00, §0 C et D).
- La page de téléchargement est lue à chaque passage : elle donne le lien et la date de chaque fichier. Un lien absent ou nouveau est une erreur visible, pas un silence.
- Empreinte (SHA-256) par fichier, sur les octets bruts ; la décision « changé ou non » se prend sur une **empreinte de comparaison** propre à chaque fichier (lignes triées pour le fichier généré à la demande, couples lien-date pour la page).
- Archivage brut **immuable** : un fichier n'est jamais réécrit. Il est la source de vérité du rejeu.
- Un manifeste en ajout seul consigne chaque tentative, y compris en erreur : c'est la base des mesures de fraîcheur.
- La collecte **constate et archive** tout ce que la source envoie, même un contenu anormal : le 26/10/2026 à 14:17 UTC, `CIS_InfoImportantes.txt` (généré à la demande) a été servi **vide** (sha256 `e3b0c442…`, celui d'un contenu vide), puis normal au passage suivant. L'archive garde cette preuve ; c'est la détection (§6.3) qui ne doit pas en tirer de conclusion.
- Open Medic : métadonnées du jeu collectées chaque jour ; les CSV au Lot 4, à la publication d'une nouvelle base annuelle ou d'un correctif. Les dates du robot de data.gouv ne sont pas utilisables : la date utile est le `created_at` de chaque ressource et le `last_modified` du jeu.

### 6.2 Normalisation

- Encodage source détecté et converti en UTF-8 ; anomalies consignées, jamais corrigées en silence.
- En-têtes appliqués depuis un **contrat de schéma versionné** par fichier (les fichiers n'en ont pas) : un TOML par fichier dans `src/pharmaflux/contrats/`, neuf types, clé avec `unique` et sa raison quand elle ne l'est pas (ADR 0002). Depuis la fusion de la mission 01, **tout changement de contenu d'un contrat, lien compris, passe par une nouvelle version** ; une borne haute de date se relève de la même façon.
- **Une forme que la source ne documente pas** peut être déclarée dans un contrat, par une nouvelle version, à une condition : une contrainte interne **mesurée** sur les données la vérifie, et le contrat porte la mesure. C'est le cas des prix de `CIS_CIP_bdpm.txt` écrits avec des milliers (`1,466,29`) : prix public = prix + honoraires sur 13 620 lignes sur 13 623, dont 495 des 498 à séparateur. Les 3 écarts, de 2 centimes, sont dans la source (ADR 0005, contrat `presentations` v1). Sans mesure, une forme reste illisible : on ne devine pas.
- Quatre anomalies sont **bloquantes** (encodage, fin de ligne, nombre de colonnes, clé déclarée unique qui ne l'est pas) ; les autres portent sur une valeur et sont comptées (ADR 0002, `docs/donnees/`).
- **Forme canonique par type**, toujours en chaîne : texte sans espaces de tête ni de fin, entier sans zéro de tête, décimal à point sans séparateur de milliers, date ISO, booléen `true` / `false`, graphie canonique d'une énumération déclarée dans le contrat (`65 %` → `65%`). Une valeur que le type **ne sait pas lire** reste **brute**, avec sa règle. Une valeur qui se lit mais dont la **forme ou la vraisemblance** est en cause (espace parasite, date hors plage) prend la forme canonique et garde sa règle (ADR 0005).
- Une valeur illisible n'est **pas rejetée** : elle voyage brute, avec sa règle, dans l'événement (`anomalies`) et dans le bilan de l'archive. Une ligne n'est jamais écartée seule : c'est le snapshot entier qui l'est, avec son motif, quand il a une anomalie bloquante. La file des messages en échec (§6.4) reçoit ce que la chaîne ne peut pas publier.
- **Licence BDPM** : les données ne doivent pas être altérées et la source et la date de mise à jour doivent être citées. La normalisation ne change que la forme (encodage, typage), jamais le sens ; chaque donnée exposée porte sa source et sa date.

### 6.3 Détection des changements et événements

- Comparaison du snapshot normalisé avec le **dernier snapshot retenu**, sur les valeurs normalisées, par clé métier (CIS, CIP13, couple CIS + substance…). Une graphie, une espace ou un format de date ne produisent aucun événement : le bilan les mesure.
- **Limite connue** (mission 06, ADR 0010) : la comparaison porte sur les valeurs, pas sur leurs anomalies. Si la source écrit brute une valeur que le type ne sait pas lire, et que cette brute est égale à la forme canonique de la valeur précédente (`24.34` après `24,34`, par exemple), aucun événement n'est produit. Le silver garde alors la version sans anomalie, et le gold type une valeur que la source a cessé d'écrire lisiblement. Comparer aussi les règles d'anomalie d'une ligne demandera une mission sur la détection, peut-être avec une nouvelle version du schéma d'événement.
- Trois types d'événements par entité : `creee`, `modifiee` (avec les champs modifiés), `supprimee`.
- Chaque événement (schéma v1, ADR 0006) porte : identifiant déterministe, entité, version du contrat, clé, état avant, état après, champs modifiés, anomalies de la ligne, date de la source, date d'observation, chemins et empreintes des deux archives comparées, version du schéma. Toutes les valeurs sont des chaînes. L'identifiant est un sha256 de l'entité, des **chemins relatifs** des deux archives, du type et de l'identité de la ligne. Il est donc le même à chaque rejeu, et différent pour deux comparaisons de même contenu (un aller-retour A → B → A → B).
- **Premier snapshot** d'un fichier : une `creee` par entité, marquée état initial. Appliquer tous les événements au vide redonne le dernier snapshot retenu.
- Fichier de disponibilité : la **remise à disposition est un statut explicite** (code 4, daté). Une ligne qui disparaît est une **fin de publication** de la fiche par l'ANSM (après une remise, un arrêt, ou un retrait), pas une remise probable. ADR 0003 « proposé », revu au plus tard le 07/12/2026 avec un critère de passage chiffré.
- Trois fichiers n'ont pas de clé métier unique (disponibilité ; avis SMR et ASMR, un avis par indication) : leur comparaison se fait ligne à ligne, pas par clé. L'**identité d'une ligne** y est l'empreinte de la ligne normalisée plus son **rang**, qui distingue les occurrences d'une ligne répétée. Une ligne qui change donne une `supprimee` puis une `creee`, jamais une `modifiee`. L'événement porte quand même les colonnes de la clé déclarée non unique, pour que le Lot 2 rapproche les deux sans que l'événement l'affirme.
- **Ordre, sans dépendre d'un objet JSON** : dans l'identifiant comme dans le tri, les colonnes de la clé sont prises par **ordre alphabétique de leurs noms**, l'ordre que le JSON écrit. Les événements d'une comparaison sont triés par clé, puis `supprimee` < `modifiee` < `creee`, puis empreinte, puis rang. Le rang est **décroissant pour les `supprimee`** et croissant pour les `creee`. Un consommateur qui suit le flux dans l'ordre voit ainsi un compte d'occurrences toujours juste, même quand une ligne en perd plusieurs d'un coup.
- **Garde-fou de volume** : un snapshot qui n'a pas d'anomalie bloquante mais qui est vide, ou qui perd une part anormale de ses lignes d'un passage à l'autre, ne produit **aucun** événement `supprimee`. Il est mis de côté avec un motif visible, et la comparaison reprend au snapshot suivant (cas réel du §6.1). Règle de la mission 02 (ADR 0006) :
  - un snapshot vide ou bloquant est **écarté sans appel** ;
  - un snapshot qui perd plus de **1 %** des lignes du dernier retenu est **en attente**. Il est confirmé si la source maintient la baisse : un passage inchangé avant l'archive suivante, ou une archive suivante d'au plus 101 % de ses lignes. Sinon, il est écarté.

  Un vrai rétrécissement coûte une heure de retard, et ses événements gardent la date d'observation de leur archive.
- `CIS_bdpm.txt` ne contient pas tous les CIS cités par les autres fichiers (avis anciens, médicaments sortis de la base : `docs/donnees/README.md`) : les jointures sont externes, et un CIS absent du référentiel n'est pas une erreur.

### 6.4 Bus d'événements

- Redpanda, un topic par entité (`pharmaflux.<entite>.v1`, 3 partitions), partitionnement par clé (ordre garanti par médicament). La clé du message est l'objet `cle` de l'événement ; pour un fichier sans clé unique, ce sont les colonnes de la clé déclarée, pour qu'une `supprimee` et la `creee` qui la remplace restent dans la même partition.
- La valeur du message est la ligne de l'événement v1 à l'octet : le bus ne transforme pas l'événement. L'horodatage du message est la date d'observation. Rétention sans limite, posée par le projet à la création du topic, jamais de compactage.
- Registre de schémas, compatibilité `BACKWARD_TRANSITIVE` ; une évolution incompatible est une nouvelle version de schéma, donc un nouveau topic, et la CI refuse l'autre cas.
- File des messages en échec (`pharmaflux.echecs.v1`) : ce que la chaîne ne peut pas publier (ligne illisible, message trop gros), avec le motif et la ligne brute. Une valeur de source illisible n'y va pas : elle est gardée brute dans l'événement (§6.2).
- Consommateurs idempotents : traiter deux fois le même événement ne change rien. Ils dédoublonnent par identifiant d'événement.
- Vérification du bus : relu depuis le début et appliqué, il redonne le dernier snapshot retenu de chaque fichier (ADR 0007).

### 6.5 Lakehouse et historique

- Bronze (fichiers bruts), silver (données normalisées et historisées), gold (vues métier : fiche médicament, disponibilité courante, indicateurs).
- **Silver** : une table Iceberg par entité, au format Parquet, dans un entrepôt local hors de git, interrogée avec DuckDB. Une ligne du silver est une **version** d'une ligne de la source : son identité (la clé métier, ou l'empreinte et le rang pour un fichier sans clé unique, §6.3), ses valeurs normalisées, et sa validité.
- **SCD2 sur la date d'observation** : une version est valide de la date d'observation de l'événement qui l'ouvre (`creee`, `modifiee`) à celle de l'événement qui la ferme (`modifiee`, `supprimee`), borne de fin exclue. C'est le temps de la connaissance, celui de la question « que savait-on le JJ/MM à HH:MM ? » (§2.1). La date de la source voyage dans chaque version, sans servir d'axe. Un snapshot écarté par le garde-fou de volume ne produit aucun événement : l'état ne bouge pas, ce qui est juste.
- **Les snapshots d'Iceberg ne sont pas l'axe du temps** : ils datent l'écriture, qui diffère de l'observation dès qu'on rejoue. Ils servent à l'audit et à la reprise, pas à « l'état à une date ».
- **Fonction « état à une date »** : les versions valides à l'instant demandé. Elle sert sur le silver dès la mission 05, puis sur toutes les vues gold.
- **Vérification contre l'archive** : pour chaque archive retenue, l'état au moment de son observation est égal, empreinte par empreinte, à son snapshot normalisé recalculé depuis le bronze. C'est l'indicateur « reconstruction de l'état à une date passée » du §2.2.
- **Le consommateur du silver lit le bus** (§5, étape 4). Il est idempotent : il dédoublonne par identifiant d'événement, et une reprise après une coupure, à n'importe quel point, redonne le même silver.
- **Gold, colonnes typées** : pour chaque entité, l'état du silver à un instant, avec les colonnes typées selon le type du contrat (date, entier, décimal, booléen, liste). Une valeur que le type ne sait pas lire n'est **jamais devinée** : sa colonne typée est vide, la valeur brute reste dans le silver avec sa règle, et le contrôle de qualité la compte.
- **Gold, vues métier** : la fiche médicament (une ligne par spécialité : présentations, composition, groupe générique, conditions de prescription, avis SMR et ASMR, statut MITM, disponibilité, informations importantes en cours) et la disponibilité courante par présentation. Une ligne de disponibilité sans CIP13 vise toutes les présentations de la spécialité : le gold le rend explicite, sans en dire plus que l'ANSM (ADR 0003). Les jointures sont externes : un CIS absent du référentiel n'est pas une erreur (§6.3).
- **Le gold est une fonction du silver et d'un instant** : « état à une date » vaut pour chaque vue gold, et le gold n'a pas d'histoire propre à garder cohérente avec celle du silver.
- **Contrôles de qualité** à un instant donné : unicité des clés déclarées uniques, cohérence du référentiel CIS ↔ CIP13, volumes attendus, valeurs illisibles comptées par colonne. Chaque contrôle est soit **bloquant** (code d'erreur), soit **mesuré** (affiché, jamais absorbé), et la règle qui le classe est écrite.

### 6.6 Référentiels et correspondances

- Identifiants : CIS (spécialité), CIP13 (présentation), code ATC (classe), groupe générique.
- Correspondance BDPM ↔ Open Medic par ATC et CIP13 ; taux de correspondance mesuré et publié.
- _Extension :_ rattachement aux vocabulaires OHDSI, en réutilisant `governed-omop-rag`.

### 6.7 Indexation pour l'assistant

- Document = fiche médicament générée depuis le gold (texte déterministe, sans LLM) + extraits des avis HAS.
- Chaque fragment porte : CIS, source, date de la source, version.
- Changement de la source → remplacement des fragments du médicament ; suppression → retrait des fragments. **Aucun fragment orphelin** (contrôle automatique).
- _Précisé pour la mission 07 :_
  - **Le texte d'un fragment est une fonction de la fiche** : les mêmes fiches donnent les mêmes fragments, à l'octet, et leur identifiant est déterministe. Chaque fragment dit sa source (le fichier), la date de la source, depuis quand la valeur est observée, et l'instant de l'état dont il vient. La prudence du gold passe dans le texte : « aucun signalement » n'y devient jamais « disponible » (ADR 0003).
  - **L'index porte l'état courant**, pas l'histoire : « que savait-on le JJ/MM ? » reste une question pour le gold. L'instant de l'index est celui de la dernière observation qu'il a appliquée, et il le dit.
  - **Mise à jour incrémentale** : seuls les médicaments touchés par les changements depuis l'instant de l'index sont recalculés, depuis le gold, et leurs fragments remplacés ou retirés. L'index n'est jamais en avance sur le silver qu'il lit. Il est idempotent et reprend après une coupure, comme le consommateur du silver. La mission 07 tranche d'où viennent les changements : les événements du bus (§5, étape 5), ou les versions du silver ouvertes ou fermées depuis l'instant de l'index.
  - **Vérification** : l'index mis à jour pas à pas est égal à l'index reconstruit en entier à partir du gold au même instant. Aucun fragment orphelin, aucun manquant, aucun texte différent.
  - **Embeddings calculés localement**, par un modèle épinglé, sans API payante. Un fragment dont le texte ne change pas n'est pas recalculé (§7.5).

### 6.8 Assistant gouverné

- Questions couvertes : disponibilité, alternatives du même groupe générique, taux de remboursement, avis SMR/ASMR, conditions de prescription, statut MITM, historique (« depuis quand ? »).
- Chaque réponse cite ses sources avec leur date.
- Abstention si l'information n'est pas dans le corpus ou est trop ancienne par rapport à la fraîcheur attendue.
- **Refus systématique du conseil médical** (posologie, substitution pour un patient, interactions) avec renvoi vers un professionnel de santé.
- Les chiffres viennent de la couche sémantique, jamais du LLM.

### 6.9 Indicateurs assurance

- Dépense remboursée par classe ATC et par année.
- Dépense de l'année N-1 rattachée aux présentations actuellement en rupture ou en tension (« dépense exposée »).
- Part des génériques par groupe.
- Chaque indicateur est défini une seule fois (couche sémantique) et documenté avec ses limites (granularité annuelle, honoraires exclus).

### 6.10 Interfaces

- API REST : questions, fiche médicament, état à une date, indicateurs.
- Interface Streamlit : assistant, journal des changements du jour, tableau de bord de fraîcheur.

---

## 7. Exigences non fonctionnelles

### 7.1 Exactitude et rejeu — exigence centrale

- Rejeu complet depuis le bronze à tout moment, avec un résultat identique **à l'octet**.
- **Reprise égale au rejeu complet** : après une coupure à n'importe quel point, même pendant un rejeu complet, la reprise produit la même sortie que le rejeu complet. Pour cela, chaque fichier de sortie est écrit entier puis renommé, dans l'ordre événements, bilan, état, et l'état ne garde que des chemins d'archives : les snapshots se recalculent. Une reprise est refusée quand une version de contrat a changé.
- Aucun événement perdu, aucun doublon ; vérifié par un test automatique. Côté bus : la publication reprend au premier fichier non accusé, donc un fichier peut être republié après une coupure ; ses messages en double portent le même identifiant, et les consommateurs les dédoublonnent. Un fichier déjà publié qui a changé fait refuser la publication.
- **Le silver ne dépend pas du chemin** : construit en lisant le bus, ou en appliquant les fichiers d'événements, il a le même contenu, versions et validités comprises. Les fichiers d'événements restent la référence ; le bus et le silver se vérifient contre eux et contre l'archive.
- Toute anomalie de source est visible (file des messages en échec, tableau de bord), jamais absorbée.

### 7.2 Fraîcheur

- Objectifs du §2.2 mesurés en continu, de bout en bout.
- La fraîcheur annoncée est la fraîcheur **mesurée** : pas de promesse en millisecondes sur des sources publiées une fois par jour.

### 7.3 Reproductibilité

- `make up` lance l'ensemble sur un MacBook (Apple Silicon) avec Docker ; la chaîne tourne sur l'hôte, avec uv. `make up` ne télécharge rien qui ne soit épinglé.
- Un jeu de fichiers archivés est fourni **dans le dépôt** (`demo/`) pour lancer la démo sans dépendre du site source ni du réseau. Les fichiers sont repris à l'octet, avec leur manifeste, leur source et leur date (licence de la BDPM : sans altération) ; le jeu est figé.
- **Mode rejeu accéléré** : les jours archivés sont rejoués en quelques minutes pour montrer le flux en direct, dans l'ordre où les archives ont été observées, toutes entités confondues. Il publie les mêmes messages que la publication normale ; seul le moment de leur envoi change, et la vérification du bus est conforme à la fin.
- La démo montre le rythme réel, sans changement fabriqué : l'état initial, puis les rares changements et incidents observés (§9).

### 7.4 Santé, conformité et IA

- Aucune donnée personnelle dans le périmètre v1. Annuaire Santé : uniquement agrégé (Lot 6).
- Licences respectées et citées : BDPM (citation de la source et de la date, sans altération), Licence Ouverte Etalab pour Open Medic.
- L'assistant n'est pas un dispositif médical et le dit ; garde-fous testés.
- Note de positionnement vis-à-vis de l'AI Act (reprise de `governed-omop-rag/docs/ia_act.md`).

### 7.5 Coût

- Budget LLM plafonné et mesuré ; cache des réponses pour les questions répétées.
- Embeddings recalculés seulement pour les fragments modifiés.

### 7.6 Qualité du code

- Python typé (mypy strict), ruff, couverture mesurée, tests d'intégration avec de vrais services (testcontainers).
- CI à chaque PR ; évaluation de l'assistant dans la CI.

### 7.7 Langue

- Documentation en français ; README bilingue (français et anglais) pour le portfolio.

---

## 8. Hors périmètre

- Données individuelles de patients ou d'adhérents, réelles ou simulées.
- Tarification, devis, gestion de contrats ou de sinistres.
- Conseil médical, aide à la prescription, interactions médicamenteuses.
- Temps réel en millisecondes : les sources ne le permettent pas.
- Flink et Kubernetes en v1 (consommateurs Python ; à réexaminer si la volumétrie l'exige).
- Haute disponibilité multi-zone.

---

## 9. Risques

| Risque | Impact | Probabilité | Mitigation |
|---|---|---|---|
| **Format d'un fichier source modifié sans préavis** | Élevé | Moyenne | Contrats de schéma ; collecte qui s'arrête proprement et alerte ; incident documenté |
| **Fichier servi vide ou tronqué par la source**, sans erreur HTTP (observé le 26/10/2026) | Élevé | Faible | Archivé tel quel ; garde-fou de volume avant toute comparaison (§6.3) ; jamais d'événement `supprimee` en masse |
| **Mémoire de pointe au-dessus du plafond du VPS** : 474 Mo au rejeu complet, contre 256 Mo pour l'unité systemd (mission 02) | Élevé | **Levé pour la chaîne** par la mission 03 : 118 à 149 Mo en flux ; `verifier-bus` monte à 190-230 Mo, sans cible. Mission 04 : `demo rejouer` (rejeu et publication du jeu de démo) 145 Mo résidents ; `evenements` de 0,7 à 35,8 Mo par entité sous `tracemalloc` | Plafond de l'unité gardé, au service de la pré-production voisine ; mesure à refaire sur le VPS, avec le bus, avant d'y lancer autre chose que la collecte. Le silver (mission 05) apporte PyArrow, PyIceberg et DuckDB. Leurs imports pèsent déjà 102 Mo résidents. Les commandes du silver mesurent de 123 à 424 Mo sur le jeu de démo : `consommer` 357, `construire` 272, `verifier` 310, `comparer` 424. **En v1, le silver et le gold tournent sur le Mac**, là où est le bus, avec un seuil d'alerte de 512 Mo par commande ; le VPS ne fait que collecter. Le gold (mission 06) monte de 312 à 470 Mo selon la commande ; la plus lourde, `questions verifier --entrepot`, laisse une quarantaine de mégaoctets de marge. L'index du Lot 3 ajoute un modèle d'embeddings : sa mémoire se mesure avant tout choix |
| **Changement de lisibilité invisible à la détection** : une brute illisible égale à la forme canonique de la valeur précédente ne produit aucun événement (§6.3) | Moyen | Faible (aucun cas observé) | Limite écrite dans l'ADR 0010 ; mission sur la détection, qui compare aussi les anomalies d'une ligne |
| **Intégration continue intermittente** : le registre de schémas a coupé ses connexions pendant les tests d'intégration, dans la CI de `main` après la fusion de la mission 06, puis sur le Mac (1 passage sur 15), juste après la suppression des topics du test précédent ; la relance est passée | Faible | Moyenne | Correction au premier palier de la mission 07 : nettoyage des tests en fin de session, réessai borné quand le registre ne répond pas, diagnostic complet en CI ; une relance n'est pas une correction |
| **Rythme réel de mise à jour faible** (peu d'événements à montrer) : en 45 heures (24-26/10/2026), en dehors de l'état initial, un seul fichier a changé, deux fois, plus un fichier servi vide | Élevé | **Avérée** | Archivage dès le Lot 0 ; mode rejeu accéléré (mission 04 : 67 h 35 min observées rejouées en 4 min 03 s) ; la démo montre ce rythme et l'incident tels quels ; mesure honnête publiée ; l'historique s'allonge chaque heure |
| **Sens d'une disparition de ligne ambigu** (remise à disposition ? arrêt ?) | Moyen | Élevée | ADR 0003 « proposé » (fin de publication, pas remise), revu au plus tard le 07/12/2026 sur les disparitions observées ; libellés prudents dans l'assistant |
| Granularités incompatibles (dépense annuelle, disponibilité quotidienne) | Moyen | Certaine | Indicateur « dépense exposée » défini et documenté avec ses limites |
| Correspondance BDPM ↔ Open Medic incomplète | Moyen | Moyenne | Taux mesuré et affiché ; non-correspondances listées |
| **Information de santé erronée produite par l'assistant** | Élevé | Moyenne | Réponses sourcées, abstention, refus médical, évaluation dans la CI |
| Sur-ingénierie pour un projet portfolio | Moyen | Élevée | Lots fermés ; chaque brique justifiée par un ADR ; Lot 6 optionnel |
| Charge du site source | Faible | Faible | Un passage par heure, téléchargements en série avec pause, identification du client HTTP (`User-Agent` avec l'URL du dépôt) |
| Gêne d'un autre service sur le VPS-1 partagé | Moyen | Faible | Compte dédié sans droits, unité systemd durcie (`ProtectHome=tmpfs`, plafonds mémoire et CPU, entrées-sorties en priorité basse) |
| Projet qui s'étire et retarde la recherche d'emploi | Élevé | Moyenne | Lot 1 publiable seul ; README et démo à jour à chaque lot ; candidatures en parallèle |

---

## 10. Décisions par défaut actées et points restant à trancher

### 10.1 Décisions par défaut actées (23/10/2026) — réversibles par ADR

1. **Données publiques réelles uniquement** ; aucune donnée synthétique de patient.
2. **Archivage horaire des fichiers bruts lancé dès le Lot 0**, avant toute autre brique _(v0.1 : quotidien ; passé à horaire par la mission 00)_.
3. **Stack par défaut** : Python 3.12 et uv, Redpanda, consommateurs Python, Iceberg + DuckDB, Qdrant, FastAPI, Streamlit, Docker Compose, Claude pour la génération.
4. **Méthode Alamel** (annexe C) : une mission = une branche = une PR, paliers verts, relecture à contexte neuf.
5. **Pas de Flink ni de Kubernetes en v1** (§8).
6. **Collecte sur le VPS-1 de beko** _(26/10/2026)_. Le VPS-1 héberge aussi, jusqu'à mi-novembre 2026, une pré-production d'Alamel (non confidentielle) : la collecte tourne sous un compte dédié, dans une unité systemd qui ne voit pas le reste du système et ne peut pas le gêner. Les VPS d'Alamel, qui appartiennent au client, ne sont jamais utilisés. Une copie de l'archive est rapatriée chaque semaine sur le Mac de beko.

### 10.2 Points du Lot 0 — état au 26/10/2026 (après la mission 01)

| # | Point | État |
|---|---|---|
| 1 | Nom du projet | **Tranché** : Pharmaflux |
| 2 | Intervalle de collecte, requêtes conditionnelles | **Tranché** : toutes les heures à `:17` ; pas de requête conditionnelle, le serveur ne les permet pas (§6.1). **ADR 0001** |
| 3 | Colonnes et valeurs de `CIS_CIP_Dispo_Spec.txt` et `CIS_MITM.txt`, sens d'une ligne qui disparaît | Colonnes et statuts **profilés** (`docs/donnees/`) ; MITM est un drapeau par CIS. Sens d'une disparition : **ADR 0003, proposé**, revue au plus tard le 07/12/2026 |
| 4 | Lieu de l'archivage | **Tranché** : VPS-1, §10.1 point 6. **ADR 0001** |
| 5 | Qdrant ou pgvector | **Reporté au Lot 3**, qui l'utilise ; tranché par la mission 07 (§0), avec un ADR |
| 6 | Stockage des traces : ClickHouse ou DuckDB | **Reporté au Lot 5**, qui l'utilise |
| 7 | Corpus HAS : pages web ou PDF, volume, licence | **Tranché** : pages d'avis HTML d'abord, PDF en second, par étapes depuis 2024 ; réutilisation libre avec source et date. **ADR 0004** ; mesure du besoin en PDF au Lot 3 |
| 8 | Démo publique hébergée ou locale | **Reporté au Lot 6** |

---

## Annexe A — Inventaire des sources

Toutes les sources ci-dessous sont **archivées chaque heure depuis le 24/10/2026** (quotidiennement pour la documentation PDF et Open Medic). Date affichée par la page de téléchargement au 24/10/2026 ; encodages relevés par la mission 00 (§0 H.2) et vérifiés par les contrats. Profil détaillé, archive du 24/10 : `docs/donnees/` (mission 01), un fichier par identifiant du catalogue.

| Source | Fichier / jeu | Format | Date affichée au 24/10 | Licence | Défauts connus | Statut |
|---|---|---|---|---|---|---|
| BDPM | page de téléchargement | HTML | — | citation, sans altération | la date globale affichée (« Dernière mise à jour ») est celle de la base, pas des fichiers : seule la date dans chaque lien est utilisable | archivée quand ses couples lien-date changent ; preuve datée de ce que le site affichait ; pas de contrat (lue par le collecteur) |
| BDPM | `CIS_bdpm.txt` (spécialités) | TSV sans en-tête, Windows-1252, CRLF | 29/09/2026 | idem | pas d'en-tête ; ne contient pas tous les CIS cités ailleurs (§6.3) ; espace en tête du titulaire sur toutes les lignes | profilé (`bdpm.specialites.md`, 15 883 lignes, clé CIS unique) ; contrat v0 |
| BDPM | `CIS_CIP_bdpm.txt` (présentations, prix, taux) | TSV sans en-tête, **UTF-8, LF** | 24/10/2026 | idem | encodage différent des autres fichiers ; prix ≥ 1 000 € écrits avec une virgule des milliers (`1,003,48`) ; taux en plusieurs graphies (`65%`, `65 %`) ; dates de déclaration impossibles (1910-1949, 2924) ; 1 263 spécialités sans présentation | profilé (`bdpm.presentations.md`, clé CIP13 unique) ; contrat v0 ; premier changement capté le 24/10, deuxième le 26/10 |
| BDPM | `CIS_COMPO_bdpm.txt` (compositions) | TSV sans en-tête, Windows-1252, CRLF | 29/09/2026 | idem | espaces parasites en fin de substance | profilé (`bdpm.compositions.md`, 32 439 lignes, clé à cinq colonnes unique) ; contrat v0 |
| BDPM | `CIS_GENER_bdpm.txt` (groupes génériques) | TSV sans en-tête, Windows-1252, CRLF | 29/09/2026 | idem | 2 470 CIS absents de `CIS_bdpm.txt` | profilé (`bdpm.generiques.md`, 1 686 groupes) ; contrat v0 |
| BDPM | `CIS_CPD_bdpm.txt` (conditions de prescription) | TSV sans en-tête, Windows-1252, CRLF | 29/09/2026 | idem | trois lignes vides (`\r` seul), tolérées par le contrat | profilé (`bdpm.conditions_prescription.md`) ; contrat v0 |
| BDPM | `CIS_HAS_SMR_bdpm.txt`, `CIS_HAS_ASMR_bdpm.txt` | TSV sans en-tête, Windows-1252, CRLF | 29/09/2026 | idem | plusieurs avis par couple CIS + dossier (un par indication) : pas de clé unique ; dates `AAAAMMJJ` | profilés (`bdpm.smr.md`, `bdpm.asmr.md`) ; contrats v0, clé non unique déclarée ; comparaison ligne à ligne |
| BDPM | `HAS_LiensPageCT_bdpm.txt` | TSV sans en-tête, ASCII, CRLF | 29/09/2026 | idem | liens externes ; des dossiers cités par SMR et ASMR n'y sont pas | profilé (`bdpm.liens_ct.md`) ; contrat v0 ; base du corpus HAS (ADR 0004) |
| BDPM | `CIS_CIP_Dispo_Spec.txt` (disponibilité) | TSV sans en-tête, Windows-1252, CRLF | 21/10/2026 | idem | remise à disposition = statut 4 daté ; lignes qui disparaissent ; pas de clé unique, cinq lignes en doublon ; 667 lignes sur 703 sans CIP13 ; 47 débuts postérieurs à la mise à jour (arrêts annoncés) | profilé (`bdpm.disponibilite.md`, 290 fiches ANSM) ; contrat v0, clé non unique déclarée ; sens d'une disparition : ADR 0003 (proposé) |
| BDPM | `CIS_MITM.txt` | TSV sans en-tête, Windows-1252, CRLF | 13/10/2026 | idem | liste sans historique : un drapeau par CIS, date de publication de la liste seulement | profilé (`bdpm.mitm.md`, 7 855 CIS) ; contrat v0 ; 83,8 % des CIS en difficulté sont MITM |
| BDPM | `CIS_InfoImportantes.txt` | TSV, **généré à chaque téléchargement**, UTF-8, LF | — | idem | seul le nom envoyé (`Content-Disposition`) porte l'heure de génération ; comparaison sur les lignes triées ; **servi vide le 26/10/2026 à 14:17 UTC**, normal à 15:17 (§6.1) | profilé (`bdpm.infos_importantes.md`) ; contrat v0 |
| BDPM | documentation des formats (PDF, `v5`) | PDF | — | idem | nom de fichier versionné ; l'URL est lue dans la page (mission 01) | archivée ; référence des contrats (section et sha256 cités dans chacun) |
| Cnam | Open Medic | CSV annuels + doc xlsx ; métadonnées JSON de data.gouv | publications annuelles et correctifs | Licence Ouverte | annuel ; honoraires exclus ; correctif 2025 ; dates du robot data.gouv inutilisables | métadonnées archivées chaque jour ; CSV et contrats au Lot 4 |
| HAS | avis de la Commission de la transparence | pages HTML (puis PDF) | — | réutilisation libre avec source et date de mise à jour, sans altération | le lien « document » passe par une redirection de mesure d'audience | non collecté ; corpus au Lot 3 (ADR 0004) |

## Annexe B — Jeu de questions de référence

**Version 0** (mission 01) : `evaluation/questions-reference-v0.toml`, quarante questions, cinq par catégorie ; objectif cent au Lot 3. Format et règles de version : `evaluation/README.md`.

Chaque question porte :

- un **identifiant stable** `categorie-NNN` : une question ne change jamais de sens sous le même identifiant ; une question retirée n'est pas réutilisée ;
- un **comportement attendu** : `reponse`, `abstention` (motivée, avec une orientation concrète) ou `refus_medical` (avec renvoi vers un professionnel) ;
- pour une réponse, un **attendu rejouable** : la date de référence, l'**archive citée** (chemin dans le bronze et sha256), le contrat, la clé, les colonnes et les **lignes attendues, brutes**, telles que le fichier les écrit. `valeurs = []` signifie « aucune ligne » : « aucun générique » ou « aucun signalement à cette date » devient un fait vérifié, pas une affirmation ;
- un champ `prudence` : la nuance que la réponse doit respecter (« aucun signalement » n'est pas « disponible partout » ; un arrêt annoncé n'est pas encore un arrêt). Il n'est pas vérifié par la machine ; il sert à la notation du Lot 3.

`pharmaflux questions verifier` relit chaque archive citée, contrôle son sha256 et son contrat, recalcule les lignes et sort en erreur au moindre écart. En v0, les attendus sont calculés **depuis le bronze** ; à partir du Lot 2 (mission 06), aussi depuis le gold à l'instant de l'archive citée, et les deux calculs doivent concorder. Une question dont l'archive est hors de la fenêtre du silver est dite « non calculable depuis le gold », jamais comptée conforme.

| Catégorie | Exemple | Attendu |
|---|---|---|
| Disponibilité | « Le médicament X 500 mg est-il en rupture ? » | Statut + source + date |
| Alternatives | « Quelles présentations du même groupe générique sont disponibles ? » | Liste issue du gold (jointure groupe générique × présentations) |
| Remboursement | « Quel est le taux de remboursement de X ? » | Taux + source + date |
| Avis HAS | « Quel est le SMR de X ? » | Niveau + date de l'avis + lien |
| Historique | « Depuis quand X est-il en tension ? » | Date de début (dans le fichier en v0 ; SCD2 au Lot 2) |
| Dépense | « Quelle dépense remboursée en 2025 pour la classe ATC J01 ? » | Valeur de la couche sémantique (`calculable_au = "lot4"` en v0) |
| Hors périmètre | « Combien coûte ma mutuelle ? » | Abstention + orientation |
| Médical | « Puis-je remplacer X par Y pour mon fils ? » | Refus + renvoi vers un professionnel |

**Réponse avec réserve.** Un CIS absent de `CIS_bdpm.txt` n'appelle pas toujours une abstention : si l'information demandée existe dans un autre fichier (un avis SMR, par exemple), la réponse la donne, avec sa source et sa date, **et** dit que le référentiel des spécialités ne connaît pas ce médicament. L'abstention reste la règle quand rien ne répond à la question.

**Prévu pour la v1** (nouveau fichier, la v0 reste rejouable) : `alternatives-004` retirée et remplacée par une question sur le groupe générique, sous un nouvel identifiant ; `avis_has-005` devient une réponse avec réserve ; questions sur le texte des avis HAS avec le corpus du Lot 3.

## Annexe C — Méthode de travail (reprise d'Alamel, adaptée)

Le circuit détaillé est dans `docs/agents/processus.md`.

| Rôle | Qui | Responsabilités |
|---|---|---|
| Chef de projet | beko | Prépare les missions, tranche avec l'ingénieur en chef, **seul à pousser**, ouvre la PR, fusionne, installe sur le système |
| Ingénieur en chef | Claude (session dédiée, `pharmaflux/`) | Rédige les ordres de mission et les addenda, contrôle chaque palier, revue finale |
| Codeur | Claude Code (`pharmaflux-codeur/`) | Répond au §0, code palier par palier sur la branche de mission, un commit local par palier |
| Relecteur | Claude, contexte neuf (`pharmaflux-relecteur/`, `/relire-mission`) | Relit le sommet de la branche contre l'ordre de mission, écrit sa relecture dans le dépôt |

- **Points à trancher avant de coder** (§0) ; une décision d'architecture → un ADR dans `docs/adr/`.
- Une mission = une branche = une PR. **Tout se vérifie en local** : contrôles et relectures se font avant le push ; la PR n'est ouverte qu'à la fin, avec une seule CI ; fusion par commit de fusion.
- Ce qui fait foi passe par des fichiers du dépôt (ordres, rapports, contrôles, relectures), qui restent dans l'historique. Les messages de routine (palier prêt, contrôle remis) passent directement entre les sessions de l'IeC et du codeur ; beko reste dans la boucle pour tout ce qui sort du local.
- Garde-fous : crochet Claude Code par rôle, crochets git (pas de push par un agent, pas de chemin réservé, trailer `Commis-par: codeur`), permissions `deny`.
- Journal de développement tenu à chaque palier ; il alimente l'étude de cas publique.
