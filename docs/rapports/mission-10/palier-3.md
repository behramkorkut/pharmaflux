# Mission 10 — palier 3 : les docs et le Mac au repos

## Synthèse

**Fait** : les docs, et la fin de la procédure. Rien n'est déposé sur le VPS.

**Les vérifications locales** (arbre propre avant le commit, sans service) sont vertes :
- ruff, `format --check` et mypy (101 fichiers) passent ;
- `uv run pytest -q` : 1040 tests passent, et 14 d'intégration sautent ;
- les crochets, le garde-fou et `make -n down` sont conformes.

**Pas encore fait** :
- **le Mac au repos.** beko le met au repos en suivant la procédure, et me donne la sortie. Je
  la cite alors, avec un commit à part ;
- **le commit de l'observation.** Ses conditions ne sont pas réunies : il y a 4 passages
  porteurs sur 5, et aucun lot du mardi, qu'on attend le 24/11. `observation.md` reste un
  brouillon hors de git ; il porte déjà les relevés reportés, les archives nommées et la relance
  d'Alamel.

**Écarts** : aucun. **Questions pour l'IeC** : une, la mise à jour après la clôture.
**Propositions** : deux, pour après la mission.

Avant ce palier, j'ai commité tel quel `docs/relectures/mission-10/releves-apres-redemarrage.md`
(`3f1c6f6`).

## Ce qui est livré

| fichier | ce qui change |
|---|---|
| `docs/adr/0014-mise-en-service-sur-le-vps-1.md` | la mise en service, voir plus bas |
| `docs/adr/0001-collecte-horaire-sur-le-vps-1.md` | la ligne « complété par : ADR 0014 » |
| `README.md` | l'état : la mission 09 fusionnée, la mission 10 en cours, les lots 1 et 3, un schéma de ce qui tourne où |
| `docs/CONTEXTE.md` | une section sur la chaîne en service, et `chaine/` et `infra/vps/` dans « Où sont les choses » |
| `docs/journal.md` | une entrée, en fin de fichier |
| `infra/vps/README.md` | trois sections, voir plus bas |

**L'ADR 0014** couvre :
- la topologie, l'enchaînement, le verrou, les refus et le durcissement ;
- ce que l'observation a montré : un délai médian de 63 s, un maximum de 115 s, et 432 Mio au
  plus pour le résident des fragments ;
- les risques : le disque partagé avec `storage_min_free_bytes` à 10 Mo, et l'absence de
  sauvegarde du dérivé ;
- l'écart du déclencheur ;
- les options écartées.

**Les trois sections de `infra/vps/README.md`** :
- **« Après la fusion : le VPS sur `main` »** : le dépôt du commit de la fusion par les
  commandes de l'étape 4a.
  - Avant : le `diff --stat` de `src/` depuis la version en service, et celui de `infra/vps` et
    `infra/planification`.
  - Après : une vérification et `chaine etat`.
  - Ensuite, le compte du codeur se ferme.
- **« Mettre à jour après la clôture »** (addendum 1, question 19) : voir la question plus bas.
- **« Le Mac au repos »** :
  - `make down`, qui retire les conteneurs et garde les volumes ;
  - quatre lectures qui doivent rester vides : `docker ps -a`, `launchctl list`,
    `~/Library/LaunchAgents` et `pgrep` ;
  - ce qu'on garde, ce qui peut s'effacer sur demande de beko, et comment relancer la démo.

  `make down` remplace `docker compose -p pharmaflux down` : le test de la procédure
  (`test_la_procedure_ne_nomme_docker_que_pour_le_projet`) n'admet un `compose` qu'avec les
  fichiers du VPS. La règle du test ne change pas.

## Les vérifications locales

| commande | résultat |
|---|---|
| `uv run ruff check .`, `ruff format --check .` | vertes |
| `uv run mypy src` | 101 fichiers, aucune erreur |
| `uv run pytest -q` | 1040 passés, 14 sautés (intégration, sans service), 6 min |
| `tests/conftest.py::reseau_coupe` | garde de session inchangée |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK |
| `make -n down` | `docker compose -p pharmaflux down` |
| `shellcheck`, YAML de la CI, `docker compose config` | sans objet : rien de touché |

## Question pour l'IeC

**La mise à jour après la clôture passe par le compte du codeur, rouvert le temps du dépôt.**
- Après la clôture, `/srv/pharmaflux/code` appartient à root (`infra/agents/vps/README.md`,
  « Clôture d'une mission »).
- Déposer en root ferait tourner `uv sync` en root : il construit le projet (`uv_build`) et
  télécharge des paquets.
- La section propose donc ceci : rouvrir le compte avec une clé neuve, les commandes de 4a,
  refermer. Le geste reste `git archive` par beko.
- Le dépôt qui suit la fusion se fait avant la fermeture du compte, par `pharmaflux-vps`, sans
  rien rouvrir.

**Est-ce acceptable ?** Sinon, il faudrait un compte de dépôt à part, ou `/srv/pharmaflux/code`
rendu à un compte sans droits.

## Propositions, après la mission

1. **Le déclencheur.**
   - Deux voies : ne plus lire `MONITOR_*`, ou une unité par résultat (`pharmaflux-chaine@`).
   - La seconde touche des fichiers que root lit.
   - À trancher après l'observation (`observation.md`, « Les écarts »).
2. **Une seule unité dans la ligne « résident maximal »** des commandes `index` (Mio, comme le
   journal).
   - Aujourd'hui, elle donne des Mo décimaux : 432 Mio s'y lisent 453 Mo, au-dessus d'un seuil
     de 450 qui n'a pas été franchi.
   - Pour la mission 11 : cela ne change aucun calcul, mais la commande change.

## Ce qui reste à la mission 10

1. Ton contrôle de ce palier.
2. **Le Mac au repos** : beko suit la procédure et me donne la sortie, que je cite dans un
   commit à part.
3. **L'observation** : le cinquième passage porteur et le lot du mardi (24/11), puis la
   vérification qui suit, les relevés de beko à la fin, et le commit de l'observation.
4. Puis le circuit : la relecture, `pr.md`, ta revue finale, la fusion, et le VPS sur `main`.
