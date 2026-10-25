# PRD — Plateforme temps réel de connaissance du médicament pour l'assurance santé

**Projet :** Pharmaflux _(nom de travail, à valider — §10.2)_ — projet portfolio
**Client :** client fictif — **direction santé d'une mutuelle** de taille moyenne (personas §3). Aucune donnée client : uniquement des données publiques réelles.
**Version :** 0.1 _(première rédaction — base des points à trancher du Lot 0)_
**Date :** 23 octobre 2026
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
| Délai entre la mise à jour d'un fichier source et la disponibilité du changement dans l'assistant (p95) | < 30 min _(dont l'intervalle de collecte ; à affiner au Lot 0)_ |
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

- Tranche les points du §10.2 (ADR pour chacun).
- **Lance l'archivage quotidien des fichiers bruts dès le premier jour** : l'historique n'existe que si on commence à le collecter (§10.1).
- Profilage de chaque fichier : colonnes, encodage, formats de dates, clés, anomalies → `docs/donnees/`.
- Constitution d'une première version du jeu de questions de référence (annexe B).

### Lot 1 — Socle : collecte, détection des changements, flux d'événements

- Collecte planifiée des fichiers BDPM, archivage brut immuable (couche bronze), empreinte par fichier.
- Normalisation (encodage, typage, clés) et **détection des changements par comparaison de snapshots** : création, modification, suppression.
- Publication des événements dans Redpanda, contrats de schéma, file des messages en échec.
- Idempotence et rejeu complet depuis le bronze.
- `docker compose` local, CI (lint, types, tests unitaires et d'intégration).

### Lot 2 — Lakehouse, historique et voyage dans le temps

- Couches silver et gold en Iceberg, interrogées avec DuckDB.
- Historisation des référentiels (SCD2) : présentations, disponibilité, MITM, taux de remboursement, groupes génériques.
- Requête « état au JJ/MM/AAAA HH:MM » et vérification contre le fichier archivé du même jour.
- Contrôles de qualité automatiques (unicité des clés, référentiel CIS ↔ CIP13 cohérent, volumes attendus).

### Lot 3 — Assistant gouverné en temps réel

- Indexation incrémentale : fiches médicament construites à partir du gold + avis HAS ; **mise à jour et suppression** des fragments quand la source change.
- Retrieval hybride (repris de `governed-omop-rag`), réponses sourcées et datées, porte d'abstention, refus du conseil médical.
- API (FastAPI) et interface (Streamlit).
- Évaluation automatique sur le jeu de référence à chaque PR ; test de fraîcheur de bout en bout.

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

- Téléchargement planifié de chaque fichier de la BDPM, à un intervalle à fixer au Lot 0 (respect du service public : requêtes conditionnelles si le serveur les accepte, sinon intervalle raisonnable).
- Empreinte (SHA-256) par fichier : pas de traitement si rien n'a changé.
- Archivage brut **immuable** : un fichier n'est jamais réécrit. Il est la source de vérité du rejeu.
- Open Medic : collecte à la publication d'une nouvelle base annuelle ou d'un correctif (la page data.gouv.fr indique les dates de mise à jour par fichier).

### 6.2 Normalisation

- Encodage source détecté et converti en UTF-8 ; anomalies consignées, jamais corrigées en silence.
- En-têtes appliqués depuis un **contrat de schéma versionné** par fichier (les fichiers n'en ont pas).
- Dates converties au format ISO ; valeurs impossibles rejetées vers la file des messages en échec avec la ligne brute.
- **Licence BDPM** : les données ne doivent pas être altérées et la source et la date de mise à jour doivent être citées. La normalisation ne change que la forme (encodage, typage), jamais le sens ; chaque donnée exposée porte sa source et sa date.

### 6.3 Détection des changements et événements

- Comparaison du snapshot normalisé avec le précédent, par clé métier (CIS, CIP13, couple CIS + substance…).
- Trois types d'événements par entité : `creee`, `modifiee` (avec les champs modifiés), `supprimee`.
- Chaque événement porte : identifiant déterministe (rejeu sans doublon), entité, clé, état avant, état après, date de la source, date d'observation, empreinte du fichier d'origine, version du schéma.
- Une ligne qui disparaît du fichier de disponibilité = **fin de la situation** (remise à disposition probable) : sens exact à confirmer au Lot 0.

### 6.4 Bus d'événements

- Redpanda, un topic par entité, partitionnement par clé (ordre garanti par médicament).
- Registre de schémas ; une évolution incompatible est refusée par la CI.
- File des messages en échec, avec le motif et la ligne brute.
- Consommateurs idempotents : traiter deux fois le même événement ne change rien.

### 6.5 Lakehouse et historique

- Bronze (fichiers bruts), silver (données normalisées et historisées), gold (vues métier : fiche médicament, disponibilité courante, indicateurs).
- SCD2 sur les référentiels : dates de validité début / fin.
- Fonction « état à une date » sur toutes les vues gold.

### 6.6 Référentiels et correspondances

- Identifiants : CIS (spécialité), CIP13 (présentation), code ATC (classe), groupe générique.
- Correspondance BDPM ↔ Open Medic par ATC et CIP13 ; taux de correspondance mesuré et publié.
- _Extension :_ rattachement aux vocabulaires OHDSI, en réutilisant `governed-omop-rag`.

### 6.7 Indexation pour l'assistant

- Document = fiche médicament générée depuis le gold (texte déterministe, sans LLM) + extraits des avis HAS.
- Chaque fragment porte : CIS, source, date de la source, version.
- Changement de la source → remplacement des fragments du médicament ; suppression → retrait des fragments. **Aucun fragment orphelin** (contrôle automatique).

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

- Rejeu complet depuis le bronze à tout moment, avec un résultat identique.
- Aucun événement perdu, aucun doublon ; vérifié par un test automatique.
- Toute anomalie de source est visible (file des messages en échec, tableau de bord), jamais absorbée.

### 7.2 Fraîcheur

- Objectifs du §2.2 mesurés en continu, de bout en bout.
- La fraîcheur annoncée est la fraîcheur **mesurée** : pas de promesse en millisecondes sur des sources publiées une fois par jour.

### 7.3 Reproductibilité

- `make up` lance l'ensemble sur un MacBook (Apple Silicon) avec Docker.
- Un jeu de fichiers archivés est fourni pour lancer la démo sans dépendre du site source.
- **Mode rejeu accéléré** : les jours archivés sont rejoués en quelques minutes pour montrer le flux en direct.

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
| **Rythme réel de mise à jour inconnu ou faible** (peu d'événements à montrer) | Élevé | Moyenne | Archivage dès le Lot 0 ; mode rejeu accéléré ; mesure honnête publiée |
| **Sens d'une disparition de ligne ambigu** (remise à disposition ? arrêt ?) | Moyen | Élevée | Point à trancher au Lot 0, documenté dans un ADR ; libellés prudents dans l'assistant |
| Granularités incompatibles (dépense annuelle, disponibilité quotidienne) | Moyen | Certaine | Indicateur « dépense exposée » défini et documenté avec ses limites |
| Correspondance BDPM ↔ Open Medic incomplète | Moyen | Moyenne | Taux mesuré et affiché ; non-correspondances listées |
| **Information de santé erronée produite par l'assistant** | Élevé | Moyenne | Réponses sourcées, abstention, refus médical, évaluation dans la CI |
| Sur-ingénierie pour un projet portfolio | Moyen | Élevée | Lots fermés ; chaque brique justifiée par un ADR ; Lot 6 optionnel |
| Charge du site source | Faible | Faible | Intervalle raisonnable, requêtes conditionnelles, identification du client HTTP |
| Projet qui s'étire et retarde la recherche d'emploi | Élevé | Moyenne | Lot 1 publiable seul ; README et démo à jour à chaque lot ; candidatures en parallèle |

---

## 10. Décisions par défaut actées et points restant à trancher

### 10.1 Décisions par défaut actées (23/10/2026) — réversibles par ADR

1. **Données publiques réelles uniquement** ; aucune donnée synthétique de patient.
2. **Archivage quotidien des fichiers bruts lancé dès le Lot 0**, avant toute autre brique.
3. **Stack par défaut** : Python 3.12 et uv, Redpanda, consommateurs Python, Iceberg + DuckDB, Qdrant, FastAPI, Streamlit, Docker Compose, Claude pour la génération.
4. **Méthode Alamel** (annexe C) : une mission = une branche = une PR, paliers verts, relecture à contexte neuf.
5. **Pas de Flink ni de Kubernetes en v1** (§8).

### 10.2 Points restant à trancher (Lot 0)

1. **Nom du projet.**
2. **Intervalle de collecte** et requêtes conditionnelles acceptées par le site de la BDPM. `[À VÉRIFIER]`
3. **Colonnes et valeurs exactes de `CIS_CIP_Dispo_Spec.txt` et `CIS_MITM.txt`**, et sens d'une ligne qui disparaît. `[À VÉRIFIER]`
4. **Lieu de l'archivage quotidien** : Mac (tâche planifiée), action GitHub planifiée, petit VPS ou stockage objet.
5. **Qdrant ou pgvector** (pgvector simplifierait l'exploitation ; Qdrant est repris de `governed-omop-rag`).
6. **Stockage des traces** : ClickHouse, ou DuckDB pour rester léger.
7. **Corpus HAS** : pages web seulement ou aussi PDF ; volume et licence. `[À VÉRIFIER]`
8. **Démo publique hébergée** ou démo locale seulement.

---

## Annexe A — Inventaire des sources

| Source | Fichier / jeu | Format | Rythme constaté | Licence | Défauts connus | Statut |
|---|---|---|---|---|---|---|
| BDPM | `CIS_bdpm.txt` (spécialités) | TSV sans en-tête | variable par fichier | citation, sans altération | encodage, pas d'en-tête | vérifié 23/10/2026 |
| BDPM | `CIS_CIP_bdpm.txt` (présentations, prix, taux) | TSV sans en-tête | variable | idem | — | à profiler |
| BDPM | `CIS_COMPO_bdpm.txt` (compositions) | TSV sans en-tête | variable | idem | — | à profiler |
| BDPM | `CIS_GENER_bdpm.txt` (groupes génériques) | TSV sans en-tête | variable | idem | — | à profiler |
| BDPM | `CIS_CPD_bdpm.txt` (conditions de prescription) | TSV sans en-tête | variable | idem | — | à profiler |
| BDPM | `CIS_HAS_SMR_bdpm.txt`, `CIS_HAS_ASMR_bdpm.txt` | TSV sans en-tête | variable | idem | — | à profiler |
| BDPM | `HAS_LiensPageCT_bdpm.txt` | TSV sans en-tête | variable | idem | liens externes | à profiler |
| BDPM | `CIS_CIP_Dispo_Spec.txt` (disponibilité) | TSV sans en-tête | variable | idem | lignes qui disparaissent | à profiler |
| BDPM | `CIS_MITM.txt` | TSV sans en-tête | variable | idem | pas de dates | à profiler |
| BDPM | `CIS_InfoImportantes.txt` | TSV, généré au téléchargement | à chaque téléchargement | idem | empreinte change toujours ? | à profiler |
| Cnam | Open Medic | CSV annuels + doc xlsx | publications annuelles et correctifs | Licence Ouverte | annuel ; honoraires exclus ; correctif 2025 | vérifié 23/10/2026 |

## Annexe B — Jeu de questions de référence (amorce)

Version 0.1 : une vingtaine de questions par catégorie au Lot 0, objectif 100 au Lot 3. Chaque question a une réponse attendue **calculée depuis le gold à une date donnée**, ce qui rend l'évaluation rejouable.

| Catégorie | Exemple | Attendu |
|---|---|---|
| Disponibilité | « Le médicament X 500 mg est-il en rupture ? » | Statut + source + date |
| Alternatives | « Quelles présentations du même groupe générique sont disponibles ? » | Liste issue du gold |
| Remboursement | « Quel est le taux de remboursement de X ? » | Taux + source + date |
| Avis HAS | « Quel est le SMR de X ? » | Niveau + date de l'avis + lien |
| Historique | « Depuis quand X est-il en tension ? » | Date de début (SCD2) |
| Dépense | « Quelle dépense remboursée en 2025 pour la classe ATC J01 ? » | Valeur de la couche sémantique |
| Hors périmètre | « Combien coûte ma mutuelle ? » | Abstention + orientation |
| Médical | « Puis-je remplacer X par Y pour mon fils ? » | Refus + renvoi vers un professionnel |

## Annexe C — Méthode de travail (reprise d'Alamel)

| Rôle | Qui | Responsabilités |
|---|---|---|
| Chef de projet | beko | Crée les branches de mission, tranche avec l'ingénieur en chef, fusionne, lance les démos |
| Ingénieur en chef | Claude (session dédiée) | Rédige les ordres de mission et les addenda, revue finale |
| Codeur | Claude Code | Code palier par palier sur la branche de mission, un commit par palier |
| Relecteur | Claude, contexte neuf (`/relire-pr`) | Relit la PR contre l'ordre de mission, poste sa relecture |

- **Points à trancher avant de coder** → un ADR par décision dans `docs/adr/`.
- Une mission = une branche = une PR ; PR en brouillon pendant la relecture ; fusion par commit de fusion.
- Garde-fous repris d'Alamel : permissions `deny`, crochet `pre-push`, trailer `Commis-par: codeur`.
- Journal de développement tenu à chaque palier ; il alimente l'étude de cas publique.
