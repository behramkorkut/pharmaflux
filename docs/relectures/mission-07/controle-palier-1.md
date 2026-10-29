# Mission 07 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `3a2d84d` (fils de `f7e4d1b`, le §0). Il est contrôlé
contre l'ordre et l'addendum 1 (`241bff0`). **Verdict : conforme, passe au
palier 2**, une fois que beko t'a transmis les téléchargements. Deux
corrections de commentaire sont à faire dans le commit du palier 2.

## Revérifié par l'IeC

Dans ton dossier, arbre propre sur `3a2d84d`, le courtier du projet en
marche :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 61 fichiers |
| `GITHUB_ACTIONS=true uv run pytest -q -rE` | **568 passed** en 2 min 45 s ; reproduction : **0 réessai sur 30 cycles** à ce passage (1 sur 30 au tien) |

Relu dans le code :

- **Le réessai** (`Registre._envoyer`) est celui de l'addendum :
  - trois essais, seulement sur les quatre erreurs sans réponse ;
  - une réponse, même 5xx, remonte telle quelle, et un `ReadTimeout` aussi ;
  - la ligne est horodatée à la milliseconde, comptée par client et par
    processus.

  Rejouer un `POST …/versions` après une coupure est sûr, même si le
  registre avait écrit avant de couper : il rend le même identifiant.
  `supprimer` tente maintenant la suppression définitive dans tous les cas.
- **Le nettoyage en fin de session** (`a_nettoyer`) supprime les sujets avant
  les topics. Plus aucun test n'écrit dans le registre pendant qu'un topic
  s'efface.
  - `pytest_sessionfinish` fait échouer la session si un réessai a servi.
  - Les réessais simulés des tests unitaires sont isolés
    (`reessais_isoles`), donc ils ne comptent pas.
- **CI** :
  - les loggers passent en `debug` avant les tests ;
  - les tests tournent avec `-rE` ;
  - en cas d'échec, le journal complet, la santé de la grappe et les stats
    du conteneur partent en artefact.

  **Compose** : le healthcheck attend aussi le registre.
- **Les fragments**, lus sur trois CIS réels du jeu :
  - 60002283 : « aucun signalement… cela ne veut pas dire “disponible” » ;
  - 66890524 : « arrêt annoncé à partir du 2027-07-01, pas encore commencé
    au jour de l'état », ligne sans CIP13 nommée comme telle ;
  - 60000229 : fiche partielle dite telle.

  La prudence du gold passe dans le texte. Il n'y a ni instant ni lien dans
  le texte, et l'identifiant ne dépend pas du texte.

  Le test du mot « disponible » est juste. Les 95 occurrences restantes
  sont des valeurs de la source citées mot pour mot (titres
  d'informations, un libellé), jamais notre texte.

## Écarts du rapport

1. **Les fragments sortent dans l'ordre CIS, section, partie**, et non triés
   par identifiant : accepté. L'ordre est déterministe, et le tri coûterait
   la mémoire qui manque au processus du gold.
2. **Un fragment découpé porte les liens de toute sa section** : accepté. Les
   liens sont des métadonnées, pas du texte encodé. Un lien de trop dans une
   partie ne fait rien dire de faux.
3. **Les avis gardent la forme de la fiche texte**, sans le libellé long :
   accepté. Le corpus HAS de la mission 08 apportera le texte des avis.
4. **« Aucun signalement » cite le fichier sans date** : accepté. Aucune
   date n'est propre à une absence. La date juste serait celle du dernier
   fichier de disponibilité retenu, que le silver ne garde pas : c'est la
   proposition déjà portée pour une mission ultérieure. D'ici là, la
   réponse se rapporte à l'**instant de l'index**, que `chercher` rend avec
   chaque résultat (addendum, D2). L'ADR 0011 l'écrit.

## Tes questions

1. **L'épinglage des actions par empreinte** : l'addendum se trompait en
   écrivant « comme les autres ». Aucune action ne l'est aujourd'hui. Les
   trois (`checkout`, `setup-uv`, `upload-artifact`) sont épinglées par
   empreinte de commit **dans cette mission, au palier 2**. Une étiquette
   comme `v4` se déplace, et une empreinte ne bouge pas. beko relève les
   empreintes avec l'image Qdrant (voir plus bas). Chaque ligne garde la
   version en commentaire (`uses: actions/checkout@<sha> # v4.x.y`).
2. **Le conteneur recréé au prochain `make up`** : noté. Le volume est
   gardé, et beko est prévenu.

## Corrections, dans le commit du palier 2

1. Le docstring de `a_nettoyer` (`tests/conftest.py`) et le commentaire de
   l'étape « Diagnostic du courtier » (`ci.yml`) attribuent la coupure
   observée en CI à la « PR #7 ». C'était le run de `main` après la fusion
   (`98505d3`), comme le dit ton journal. Écris-le ainsi aux deux endroits.
2. `infra/index/README.md`, étape 2 de l'image : `docker buildx imagetools
   inspect` suppose le greffon `buildx`, que le Docker du colima n'a pas
   forcément. Donne une seconde voie : après le `docker pull` par
   étiquette, `docker image inspect --format '{{index .RepoDigests 0}}'
   qdrant/qdrant:vX.Y.Z`, qui rend l'empreinte de l'index
   multi-architecture.

## Pour le palier 2

- Recopie tels quels :
  - les deux TOML que beko te transmet ;
  - l'image Qdrant (version, date, empreinte) dans le compose ;
  - les trois empreintes d'actions dans `ci.yml`.
- **Commence par les mesures des deux modèles** (addendum, C1) : la mémoire
  de l'encodage et de `chercher`, le temps sur tout le jeu, et le rappel à 5
  sur les questions v0 qui nomment un médicament. Le choix se fait suivant
  la règle de l'addendum. **Plus d'une heure d'encodage : tu t'arrêtes.**
  Le rapport du palier 2 donne les mesures des deux modèles.
- La borne de découpe se recale sur le décompte réel du tokenizer **avant**
  que le format 1 soit figé (addendum, D1). Si elle change, les nombres du
  palier 1 sont remesurés.
- Deux processus, chacun mesuré sous 512 Mo (addendum, J).
