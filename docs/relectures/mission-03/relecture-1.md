# Mission 03 — relecture 1
**Commit relu** : `d4db1de` (sommet de `mission-03-bus-d-evenements`)
**Verdict** : CONFORME

Ordre relu sur `main` (`git show main:docs/missions/mission-03-bus-d-evenements.md`),
addendum 1 compris. Les six rapports du codeur et les cinq contrôles de l'IeC ont
été lus avant le code. C'est le premier tour : il n'y a pas de réponse précédente
à vérifier.

## Bloquants

Aucun.

Les décisions de l'ordre et de l'addendum sont toutes tenues :

- **Décision 1 : écriture en flux.** `comparer` rend un itérateur sur des
  squelettes triés, et la clé de tri reprend `Evenement.cle_de_tri` valeur
  pour valeur. `Resultat.evenements()` recalcule à la demande.
  `Suivi.resultats` est retiré. L'écriture reste atomique : `.partiel`, puis
  renommage.
- **Addendum 3 et 5 : enveloppe.**
  - La valeur est nue, à l'octet.
  - La clé est l'objet `cle`, compact et à clés triées. Pour un fichier ligne
    à ligne, elle ne contient pas le rang : j'ai vérifié sur un événement
    `bdpm.smr` réel, dont la clé est `{code_cis, code_dossier_has}`.
  - L'horodatage est `date_observation`, avec `CreateTime`.
  - Topics : `pharmaflux.<entite>.v1`, 3 partitions, `murmur2_random`.
  - La file a sa propre configuration : 1 partition, `LogAppendTime`.
- **Addendum 4 : registre.** `BACKWARD_TRANSITIVE`, un historique enregistré
  avant le schéma courant, et le sha256 du schéma épinglé par un test.
- **Addendum 5 : rétention.** La rétention infinie est posée à la création.
  `verifier-bus` la vérifie, et la création automatique est coupée par
  `.bootstrap.yaml`. Résultat relu : `false`.
- **Addendum 6 : publication.**
  - L'état est écrit après l'accusé de réception, sous forme de sha256 des
    octets publiés.
  - Un fichier modifié est refusé, sans option de forçage.
  - Codes de sortie : 1, 2 et 3.
- **Addendum 7 : file des échecs.** Seuls `illisible` et `trop_gros` y vont,
  tronqués à 64 Ko. Il n'y a pas de topic des bilans.
- **Addendum 8 : vérification.** Deux références sont possibles. Le bus est
  lu sans commit, et sa fin est fixée par les offsets de fin. Une référence
  introuvable est refusée avant toute lecture du bus.
- **Addendum 9 : compose.** Ports sur `127.0.0.1` : 19092, 18081, 18082 et
  19644. Volume `pharmaflux-redpanda`, mode `dev-container`, mémoire de 768
  Mo, limite de 1 Go, console sous un profil, pas de `Makefile`. Les deux
  versions sont épinglées.
- **Addendum 10 : CI.** Le job `integration` passe par le fichier compose du
  dépôt. Le job `verifier` est inchangé.

Les écarts annoncés dans les rapports ont tous été tranchés par l'IeC :

- le partage des valeurs répétées ;
- le test de mémoire à 4 000 lignes ;
- `message.timestamp.type` vérifié en plus ;
- pas de cible de mémoire pour `verifier-bus`.

## À corriger (non bloquants)

1. `.github/workflows/ci.yml:100` — **Le job `integration` peut passer au vert
   sans avoir lancé un seul test.** La fixture `bus` de
   `tests/test_bus_integration.py` saute tous les tests quand le courtier ne
   répond pas. C'est voulu sur le Mac (décision de l'ordre), mais en CI,
   `pytest -q -m integration` sort alors avec le code 0 et « 6 skipped ».
   Le risque est atténué : les étapes `rpk cluster config get` et `schemas
   enregistrer` échoueraient d'abord si le conteneur était absent. Mais un
   décalage de l'adresse annoncée (`127.0.0.1:19092` sur le runner) ne serait
   vu par aucune d'elles. Or la consigne dit qu'un test qui ne peut pas
   échouer est un défaut, et il n'y a qu'une CI par mission.
   **Attendu** : en CI, un saut devient un échec. Deux façons de le faire :
   - une variable d'environnement posée par le job (par exemple
     `PHARMAFLUX_INTEGRATION_EXIGEE=1`), qui fait appeler `pytest.fail` à la
     fixture au lieu de `pytest.skip` ;
   - ou une vérification du nombre de tests passés.
2. `src/pharmaflux/bus/publication.py:119` — **`publier --reprendre` sort avec
   0 quand le courtier est injoignable, s'il n'y a rien de nouveau à
   publier.** Le courtier n'est contacté qu'au premier fichier à publier
   (`_identifiants_de_schema`, puis `preparer_topics`). La décision 4 dit :
   « sort avec un code non nul si le courtier est injoignable », sans
   condition. C'est justement le deuxième geste du critère de clôture. Lancé
   sur une copie sans nouveaux fichiers et avec un Redpanda arrêté, il
   répondrait « rien à publier », code 0.
   **Attendu** : interroger le courtier au départ (`verifier_courtier`, ou une
   méthode équivalente dans le protocole `Bus`), avant la comparaison à
   l'état. Ajouter un cas au test `test_commandes_publier_et_schemas_enregistrer` :
   reprise sans nouveau fichier, bus en panne, code 1.
3. `docs/adr/0006-evenements-schema-identifiant-garde-fou-reprise.md:175` —
   La phrase « La chaîne n'a plus de structure dont la taille dépend du nombre
   d'événements » est inexacte. La liste des squelettes de `_emettre` grandit
   avec le nombre d'événements : 11 Mo tracés pour les 32 439 `creee` des
   compositions, selon le rapport du palier 1. Le paragraphe suivant le décrit
   d'ailleurs.
   **Attendu** : une formulation juste, par exemple « aucun événement n'est
   construit ni sérialisé avant d'être écrit ; seuls les squelettes, qui
   pointent vers les lignes des snapshots, dépendent du nombre d'événements ».
   Un recruteur qui lit le code verra la liste.

## Remarques

- `src/pharmaflux/bus/registre.py:70` : l'historique est trié par nom de
  fichier. `evenement.v1.schema.10.json` passerait donc avant `.2.json`. Ce
  n'est pas un problème aujourd'hui, l'historique est vide. Un tri sur le
  numéro, ou un numéro sur deux chiffres dans le README de l'historique,
  évitera le piège.
- `src/pharmaflux/bus/registre.py:132` : `Registre.compatible` n'est utilisé
  que par les tests. La CI refuse une évolution incompatible par le 409 de
  `enregistrer`, pas par cette méthode. Il faut la garder seulement si elle
  sert, sinon la retirer.
- `publier` ne vérifie pas qu'un nouveau fichier se range **après** le
  dernier fichier publié de son entité. Par construction de `evenements`, un
  fichier d'archive en attente n'existe pas avant d'être tranché, donc l'ordre
  est tenu. `verifier-bus` détecterait d'ailleurs un désordre, sous la forme
  « flux incohérent » ou d'une différence. Un refus explicite coûterait trois
  lignes ; c'est à l'IeC de juger.
- Le test de coupure (`BusCoupe`) simule une coupure **après** l'envoi de
  tout le fichier et avant l'écriture de l'état : chaque ligne du fichier est
  alors en double. C'est le cas demandé par la décision 6. Le cas d'un
  préfixe seulement livré n'est pas testé, mais le dédoublonnage par « le
  premier gagne » le traite de la même façon.
- Deux `assert` servent de garde de type dans le code de production
  (`bus/client.py:321`, `bus/registre.py`, `enregistrer`). Ils sont
  inoffensifs, et `python -O` les retirerait sans changer le comportement
  attendu.
- La docstring de `verifier-bus` dans `cli.py:431` dit « la rétention sans
  limite et les partitions ». La politique et le type d'horodatage sont aussi
  vérifiés : on peut les ajouter à la phrase.
- **Garde-fou** : `git archive 647fb6a | tar -x -C <scratchpad>`, que je
  voulais utiliser pour rejouer moi-même le code fusionné comme référence du
  `diff -r`, a été refusé au rôle relecteur. Je l'ai signalé ici et je ne l'ai
  pas contourné. J'ai remplacé ce contrôle par un contrôle croisé : un rejeu
  complet neuf du code relu, puis `verifier-bus` sur les topics de la
  démonstration (voir le tableau). Le `diff -r` à l'octet contre `647fb6a`
  reste celui du rapport du palier 1 et du contrôle de l'IeC. Si beko veut que
  le relecteur le refasse, il faut lui permettre l'extraction en lecture
  seule d'un commit dans le scratchpad.

## Vérifications relancées

Sur `d4db1de`, arbre propre, avec le courtier du projet démarré
(`pharmaflux-redpanda`, `v26.2.6`, sain).

| commande | résultat |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 153 files already formatted |
| `uv run mypy src` | Success, 36 fichiers |
| `uv run pytest -q` (avec le courtier) | 446 passed en 29 s |
| `PHARMAFLUX_COURTIER=127.0.0.1:1 uv run pytest -q` | 440 passed, 6 skipped, motif affiché (« aucun courtier sur 127.0.0.1:1 … ») |
| `uv run pytest -q -m integration` | 6 passed en 14 s ; ensuite, `rpk topic list` ne montre que les 12 topics du projet et `_schemas` : les topics de test sont supprimés |
| `rpk cluster config get auto_create_topics_enabled` | `false` |
| `python3 infra/agents/test_garde_fou.py` | 20 tests, OK |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| shellcheck | sans objet : aucun `.sh` touché |
| `git diff --stat main...HEAD` | aucun chemin réservé à l'IeC, rien sous `data/`, `journal.md` seulement complété en fin de fichier |
| trailers des 8 commits hors fusion | `Commis-par: codeur` et `Co-Authored-By` partout, messages en français |
| `/usr/bin/time -l uv run pharmaflux evenements --sortie <scratchpad>` (rejeu complet, copie du Mac) | 8,5 s, **149 Mo** résidents (cible de 160 tenue), 30 fichiers, 172 Mo |
| `verifier-bus --sortie <ce rejeu>` | code 0, 12 topics conformes sur 12, 0 doublon, 164 099 messages (le chiffre de la démonstration), 11,0 s, 199 Mo |
| `verifier-bus --sortie <ce rejeu> --racine ~/pharmaflux-data` | code 0, 12 topics conformes sur 12, 0 doublon, 11,9 s |
| `uv run pharmaflux profil` | code 0, 11 fichiers, 0 anomalie bloquante |
| `uv run pharmaflux questions verifier` | code 0, 40 questions : 25 conformes, 5 non calculables, 10 sans attendu |
| `diff -r` contre le code fusionné `647fb6a` | **non relancé** : extraction refusée par le garde-fou (voir les remarques). Remplacé par le contrôle croisé `verifier-bus` ci-dessus, qui compare le bus publié par le codeur à mon rejeu indépendant |

## Alertes

Aucune consigne adressée au relecteur n'a été trouvée dans le code, les
rapports, les contrôles ni les données lues.
