# Mission 00 — Socle du dépôt et archivage quotidien des sources

**À :** Claude Fable (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.1 §4 (Lot 0), §6.1, §7.1, §7.3, §10 · `CLAUDE.md`
**Statut :** ordre rédigé le 24/10/2026, **addendum 1** (circuit local)
le même jour — **§0 à traiter avant de coder**
**Branche :** `mission-00-socle-et-archivage`, dans le dossier
`pharmaflux-codeur/` préparé par beko. Trois paliers, chacun committé en
local et contrôlé par l'IeC ; **aucun push** de ta part.

Tu es le codeur de ce projet. Lis d'abord `CLAUDE.md` (ses règles
s'imposent), puis `docs/agents/processus.md` (le circuit), puis le PRD
v0.1 (`01_Specifications/`), puis cet ordre **et son addendum 1 en fin de
fichier**.

## Constat

Le Lot 0 du PRD a deux buts : **démarrer l'archivage des sources tout de
suite**, et **connaître les données** avant de construire le flux. Les deux
n'ont pas la même urgence.

- L'archivage est **la seule brique qui ne se rattrape pas** : la BDPM
  écrase ses fichiers à chaque mise à jour, sans historique. Chaque jour
  sans collecte est un jour d'histoire perdu, et donc un jour de moins pour
  le voyage dans le temps (Lot 2) et la démo en rejeu accéléré (§7.3).
- Le profilage, les contrats de schéma, les ADR et le jeu de questions
  peuvent attendre quelques jours sans rien perdre.

Le Lot 0 est donc découpé en **deux missions** :

- **Mission 00 (celle-ci)** : le dépôt, ses garde-fous, et un collecteur
  qui archive les fichiers bruts chaque heure, **en service sur le Mac de
  beko à la fin de la mission**.
- **Mission 01** (rédigée ensuite) : profilage des fichiers, contrats de
  schéma v0, ADR des points du PRD §10.2, jeu de questions de référence
  v0.

**Objectif** : à la fusion de cette mission, l'archive brute de la BDPM se
remplit toute seule, sans jamais perdre ni réécrire un fichier, et chaque
passage est consigné dans un manifeste qui servira plus tard à mesurer la
fraîcheur.

## Préalables (beko, avant le début de la mission)

Faits par beko (voir addendum 1) : dépôt créé et publié en public,
garde-fous committés sur `main`, puis
`sh infra/agents/preparer-mission.sh 00-socle-et-archivage`, qui crée la
branche et les dossiers `pharmaflux-codeur/` et `pharmaflux-relecteur/`.
Le codeur est lancé dans `pharmaflux-codeur/`.

## §0 — Points à trancher avant de coder

Réponds point par point dans `docs/rapports/mission-00/points-a-trancher.md`
(commité, puis tu t'arrêtes) : constat (ce que tu as
vérifié et comment), avis, question éventuelle. **Tu as droit, pour tout le
§0, à une requête HTTP par URL** (en-têtes et un téléchargement), pas plus.

- **A. Racine de l'archive.**
  - Proposition : hors du dépôt, `~/pharmaflux-data/` par défaut,
    surchargeable par la variable `PHARMAFLUX_DATA`. Le dépôt ne contient
    jamais de données.
  - À mesurer : le volume d'un passage complet (brut et compressé gzip),
    pour estimer le volume annuel si tout changeait chaque jour.
  - Question pour beko : une copie de sauvegarde hebdomadaire hors du Mac
    (disque externe, dossier synchronisé) est-elle possible ? Un disque
    seul, c'est une archive irremplaçable sans sauvegarde.
- **B. Où tourne la collecte.**
  - Proposition : `launchd` sur le Mac, toutes les heures, depuis un
    **clone dédié** à jour de `main` (`~/pharmaflux-collecte/`), jamais
    depuis le dossier de travail (un `git switch` changerait le code qui
    tourne).
  - Limite assumée : Mac éteint = passages manqués. Ils seront visibles
    dans le manifeste ; si les trous sont trop fréquents, une collecte
    hébergée (GitHub Actions planifié + stockage objet) fera l'objet d'un
    ADR plus tard.
- **C. URL de téléchargement et en-têtes HTTP.** Pour chaque fichier de la
  page <https://base-donnees-publique.medicaments.gouv.fr/telechargement> :
  - l'URL directe, et si elle est stable ;
  - les en-têtes `Last-Modified`, `ETag`, `Content-Length`,
    `Content-Type` (charset annoncé ?) ;
  - si le serveur répond `304` à une requête conditionnelle ;
  - si la page affiche une date de mise à jour **par fichier** et si elle
    est lisible de façon fiable (elle deviendrait la « date de la source »
    du PRD §6.3).
- **D. Intervalle de collecte.** Proposition : toutes les heures, à une
  minute fixe non ronde (par exemple `:17`), téléchargements en série avec
  une pause de 2 s. À confirmer selon C : avec des requêtes
  conditionnelles, le coût d'un passage inchangé est quasi nul.
- **E. `CIS_InfoImportantes.txt`** est généré au moment du téléchargement
  (PRD annexe A). Son empreinte change-t-elle à chaque requête même sans
  changement de fond ? Si oui, propose une règle (par exemple : empreinte
  calculée sans la partie générée, ou un seul archivage par jour) et
  justifie-la.
- **F. Open Medic dans cette mission ?**
  - Proposition : **oui pour les métadonnées seulement** — chaque jour,
    la liste des ressources du jeu sur l'API data.gouv.fr (nom, URL,
    taille, date de modification), archivée comme un fichier ; **pas de
    téléchargement des CSV** dans cette mission.
  - À vérifier : l'URL de l'API du jeu et la forme de la réponse.
- **G. Dépôt public dès maintenant ?** Avis de l'IeC : oui. L'historique
  des missions, des relectures et des corrections fait partie de ce que le
  portfolio montre. Décision de beko, à prendre avant le `gh repo create`.
  - **Tranché par beko le 24/10/2026 : public.** Rien à répondre sur ce
    point.
- **H. Toute autre chose** que ta lecture du PRD ou des sources te fait
  remarquer (risque, contradiction, simplification).

## Décisions (sous réserve du §0)

1. **Arborescence du dépôt.**

   ```
   pharmaflux/
     01_Specifications/            (lecture seule)
     CLAUDE.md  .claude/           (IeC, déjà là)
     pyproject.toml  uv.lock  .python-version  .gitignore  README.md
     src/pharmaflux/
       __init__.py
       cli.py
       collecte/
         catalogue.py              (sources déclarées)
         telechargement.py         (HTTP)
         archive.py                (écriture immuable du bronze)
         manifeste.py              (journal des passages)
     tests/
       fixtures/
     infra/
       git-hooks/  agents/         (IeC, déjà là)
       planification/              (modèle launchd + procédure)
     docs/
       CONTEXTE.md  journal.md
       adr/  donnees/  rapports/
       missions/  agents/  relectures/   (IeC, déjà là)
     .github/workflows/ci.yml
   ```

2. **Outillage.** Python 3.12, `uv`, `httpx`, `typer` (ou `argparse` si
   tu le justifies), `pytest`, `ruff`, `mypy --strict` sur `src/`. Aucune
   autre dépendance sans la justifier dans ton rapport.

3. **Catalogue des sources** (`catalogue.py`), déclaratif : pour chaque
   fichier, un identifiant stable (`bdpm.specialites`,
   `bdpm.disponibilite`…), l'URL, le nom de fichier, et un éventuel
   traitement particulier (§0 E). Les onze fichiers BDPM du PRD annexe A,
   plus les métadonnées Open Medic selon §0 F.

4. **Archive bronze — immuable.**
   - Chemin : `<racine>/bronze/<source>/<fichier>/<AAAA-MM-JJ>/<horodatage UTC>__<sha256 sur 12 car.>.<ext>.gz`.
   - Écriture dans un fichier temporaire puis renommage atomique ; **refus
     d'écrire si le chemin existe** (jamais de réécriture).
   - Pas de nouvelle copie si l'empreinte est égale à celle de la dernière
     archive du même fichier.
   - Le contenu archivé est **l'octet près ce que le serveur a envoyé**
     (compressé, jamais converti) : la licence BDPM interdit l'altération,
     et le rejeu du Lot 1 en dépend.

5. **Manifeste** : `<racine>/manifeste/collecte.jsonl`, en ajout seul, une
   ligne par fichier et par passage : `passage_id`, `source`, `fichier`,
   `url`, `debut`, `fin` (UTC, ISO 8601), `statut` (`nouveau`,
   `inchange`, `non_modifie_304`, `erreur`), `http_statut`, `sha256`,
   `taille_octets`, `last_modified`, `etag`, `date_source_affichee` (si
   §0 C la rend possible), `chemin_archive`, `erreur`. C'est la base des
   mesures de fraîcheur du Lot 5 : **aucun passage ne doit manquer**, même
   en erreur.

6. **HTTP.** Délai d'attente 60 s ; trois essais avec attente
   exponentielle ; `User-Agent: pharmaflux/<version> (+<URL du dépôt>)` ;
   requêtes conditionnelles si §0 C le permet ; téléchargements en série.
   Une erreur sur un fichier n'arrête pas les autres ; le code de sortie
   est non nul si au moins un fichier est en erreur.

7. **Ligne de commande.**
   - `uv run pharmaflux collecte [--source …] [--racine …]` : un passage.
   - `uv run pharmaflux etat` : pour chaque fichier, dernière archive,
     dernier changement, dernière erreur, passages des dernières 24 h.

8. **Planification** (`infra/planification/`) : un modèle de fichier
   `launchd` (`.plist`) et un `README.md` qui donne à beko la procédure
   complète — créer le clone dédié, installer, vérifier, lire les
   journaux, mettre à jour après une fusion, désinstaller. **Tu
   n'exécutes aucune de ces commandes** (`CLAUDE.md`, « Système »).

9. **Garde-fous** — *remplacée par l'addendum 1* : livrés par l'IeC
   (`infra/git-hooks/`, `.claude/hooks/`, `infra/agents/`). Tu ne les
   écris pas ; tu les fais tourner en CI (décision 11).

10. **Circuit de relecture** — *remplacée par l'addendum 1* : livré par
    l'IeC (`docs/agents/processus.md`, `docs/agents/relecteur.md`,
    `.claude/commands/relire-mission.md`). Pas de modèle de PR : la
    description est `docs/rapports/mission-00/pr.md`.

11. **CI** (`.github/workflows/ci.yml`) : sur PR et sur `main` — ruff
    (lint et format), mypy, pytest, `sh infra/git-hooks/test-crochets.sh`,
    `python3 infra/agents/test_garde_fou.py`. Aucun appel réseau vers les
    sources. Sobre : un seul job, cache uv.

12. **Docs** : `README.md` (court : ce qu'est le projet, état, comment
    lancer la collecte — il sera réécrit au fil des lots), `docs/CONTEXTE.md`
    (règles et pièges, dont « l'archive est irremplaçable »),
    `docs/adr/0000-modele.md` (gabarit d'ADR), `docs/journal.md` (entrée
    de la mission, en fin de fichier).

## Paliers

1. **Socle** : décisions 1, 2, 11, 12 (sans le collecteur), `.gitignore`
   (au moins `data/`, `.venv/`, caches, `.claude/settings.local.json`).
   `uv run pharmaflux --help` répond. Tests des garde-fous verts.
   Rapport, commit.
2. **Collecteur** : décisions 3 à 7.
   - Tests d'abord, sur fixtures : premier passage, passage inchangé,
     réponse `304`, erreur réseau puis succès, erreur définitive, archive
     déjà existante (refus de réécrire), écriture interrompue (aucun
     fichier partiel visible), manifeste complet dans tous les cas.
   - Fixtures : un extrait des vrais fichiers (en-têtes HTTP relevés au
     §0 C, quelques dizaines de lignes de contenu), avec la source et la
     date de l'extrait dans `tests/fixtures/README.md`. Le serveur est
     simulé (`httpx.MockTransport` ou équivalent).
   - Rapport, commit.
3. **Planification et premier passage réel** : décision 8.
   - Un passage réel, **un seul**, lancé à la main
     (`uv run pharmaflux collecte`) vers une racine temporaire : durée,
     volume, statuts. Consigne les chiffres dans le journal.
   - Rapport, commit.

Après le contrôle du palier 3 par l'IeC : relecture (`/relire-mission
00`) jusqu'à « CONFORME », `pr.md`, revue finale, publication et fusion
par beko, **puis installation de la planification par beko** selon
`infra/planification/README.md`. La mission est close quand `pharmaflux
etat` montre au moins 24 h de passages planifiés.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests | `uv run pytest -q` |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck (non installé sur le Mac : en CI seulement) | `shellcheck infra/planification/*.sh` s'il y en a |

## Hors périmètre

- Profilage des fichiers, contrats de schéma, ADR du PRD §10.2, jeu de
  questions : **mission 01**.
- Normalisation, décodage, comparaison de snapshots, Redpanda : Lot 1.
- Téléchargement des CSV Open Medic (§0 F).
- Docker : rien ne tourne en conteneur dans cette mission.
- Collecte hébergée (GitHub Actions, VPS, stockage objet) : ADR ultérieur
  si §0 B le justifie. **Pas d'usage des VPS d'Alamel** : ils appartiennent
  au client.

## Addendum 1 — circuit local (IeC, 24/10/2026, validé par beko)

**Contexte.** beko est seul à pousser ; chaque push déclenche la CI. Le
circuit est revu pour que **tout se vérifie en local** et qu'il n'y ait
**qu'un push par mission**. Détails : `docs/agents/processus.md`.

**Ce qui change pour toi :**

1. **Tu travailles dans `pharmaflux-codeur/`**, un worktree git sur ta
   branche. Tu ne pousses jamais, tu n'ouvres pas de PR, tu n'utilises pas
   `gh`. Tu committes en local, un commit par palier.
2. **Échanges par fichiers** : ta réponse au §0 dans
   `docs/rapports/mission-00/points-a-trancher.md` ; un rapport par
   palier `palier-K.md` ; les contrôles de l'IeC et les relectures
   arrivent dans `docs/relectures/mission-00/`, tu les commites sans les
   modifier ; à la fin, `pr.md`.
3. **Décisions 9 et 10 retirées de ton périmètre** : les garde-fous et le
   circuit sont livrés par l'IeC, sur `main`. Tu ne les écris pas ; tu
   lances leurs tests à chaque palier et en CI. Si un garde-fou te
   bloque à tort, tu le signales dans ton rapport avec la commande exacte.
4. **Relecture avant publication** : après le palier 3, le relecteur relit
   le sommet de ta branche dans son propre dossier ; tu corriges par
   nouveaux commits jusqu'à « CONFORME ». La PR n'est ouverte qu'à la
   fin, par beko, avec ta `pr.md` pour description.
5. **CI** : le dépôt est public, les minutes GitHub Actions ne sont pas
   comptées. On garde une CI sobre quand même (un job, cache uv).
