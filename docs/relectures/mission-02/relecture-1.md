# Mission 02 — relecture 1
**Commit relu** : `54a36e3` (sommet de `mission-02-normalisation-et-evenements`)
**Verdict** : NON CONFORME

Relu contre l'ordre de mission et son addendum 1 (`git show main:docs/missions/mission-02-normalisation-et-evenements.md`),
les rapports du codeur (`palier-1..3`, `reponse-controle-1..3`) et les six
contrôles de l'IeC. Premier tour : pas de relecture antérieure à vérifier.

## Bloquants

1. `src/pharmaflux/evenements/rejeu.py:181-182` — **la dernière archive
   traitée reste en arrière quand une archive en attente est tranchée par
   une archive qui passe elle-même en attente** ; `--reprendre` rejoue alors
   une archive déjà traitée et **efface des événements écrits**.

   `derniere_traitee` n'est mis à jour que si le **dernier** résultat de
   `suivi.traiter` n'est pas en attente. Or `traiter` rend deux résultats
   quand une archive P est en attente : P tranchée (confirmée ou écartée),
   puis la nouvelle archive N. Si N passe en attente, P est tranchée mais
   `derniere_archive_traitee` reste avant P. À la reprise, la boucle repart
   de P (qui n'est pas l'archive en attente de l'état, donc pas sautée),
   la relit et appelle `traiter(P)` avec N en attente : N est « tranchée »
   par une archive **antérieure**, et P est recomparée à elle-même.

   Reproduit sur un bronze de synthèse (sonde du relecteur, fixtures du
   dépôt) : `presentations_a.txt` (17 lignes), puis `presentations_perte.txt`
   (8 lignes, en attente), puis ses 4 premières lignes (confirme la perte,
   puis passe en attente face à elle). Après le rejeu complet, l'état dit
   `derniere_archive_traitee` = A, `dernier_retenu` = la perte,
   `en_attente` = la troisième archive. Puis :
   - **`--reprendre` sans aucune archive nouvelle** change la sortie : le
     fichier d'événements de la perte confirmée passe de **9 lignes à 0**
     (les 9 événements de la confirmation disparaissent), son bilan est
     réécrit, `etat.json` change ;
   - un arrêt après la deuxième archive, puis deux `--reprendre` après
     l'arrivée de la troisième, ne redonnent pas le rejeu complet.

   Pourquoi c'est bloquant : c'est exactement la décision 8 (« une reprise
   après chaque point d'arrêt possible donne la sortie du rejeu complet »)
   et la propriété « aucun changement perdu ». Le cas est réaliste : une
   source qui se vide par paliers (deux pertes successives de plus de 1 %)
   suffit. La suite `SUITE` de `tests/test_rejeu.py` n'a jamais deux pertes
   en attente qui se suivent, d'où les treize points d'arrêt verts.

   Attendu :
   - `derniere_traitee` suit **chaque** résultat dont la décision n'est pas
     `en_attente` (comme le fait déjà la boucle de `clore`, l. 188-191), et
     non le seul dernier résultat ;
   - dans `SUITE` (ou une seconde suite), une perte en attente tranchée par
     une archive elle-même en attente, **dans les deux sens** (confirmée,
     puis écartée), pour que `test_reprise_apres_chaque_point_d_arret` et
     `test_reprise_sans_rien_de_nouveau_et_sans_etat` la couvrent ;
   - une phrase dans l'ADR 0006, section reprise : « la dernière archive
     traitée est la dernière dont le verdict est définitif ».

2. `src/pharmaflux/evenements/comparaison.py:131-134` et `:158-163` —
   **`appliquer` refuse un flux valide dès qu'une ligne perd deux
   occurrences ou plus** ; la propriété « aucun changement perdu » de la
   décision 8 est donc fausse sur un cas que l'ordre met dans le périmètre
   (comparaison ligne à ligne, doublons).

   `_par_ligne` émet les `supprimee` de rangs `apres_n+1 … avant_n` dans
   l'ordre croissant, et le tri (`cle_de_tri`, rang croissant) le garde.
   `appliquer` exige pour une `supprimee` que `rang` soit égal au compte
   présent. Une ligne en triple qui revient à une occurrence donne
   `supprimee` rang 2, puis rang 3. Au rang 2, le compte présent est 3, et
   `appliquer` lève une erreur. Sonde du relecteur sur `dispo_a.txt`, avec la
   ligne en doublon passée à trois occurrences puis ramenée à une :
   `[('supprimee', 2), ('supprimee', 3)]`, puis `ValueError : suppression
   d'une ligne absente ou de mauvais rang`.

   Les événements écrits sont justes, c'est le vérificateur qui se trompe.
   Mais l'ADR 0006 présente `appliquer` comme l'inverse de la comparaison,
   et un consommateur du Lot 2 qui suivra le flux dans son ordre tombera sur
   la même contradiction. Les tests ne la voient pas parce qu'aucune fixture
   ne perd plus d'une occurrence d'une même ligne. Or `smr`, `asmr` et
   `disponibilite` sont ligne à ligne, et l'archive réelle a déjà des
   doublons.

   Attendu : une convention unique, écrite dans l'ADR 0006. Soit les
   `supprimee` d'une même empreinte sortent par rang **décroissant** (la
   suppression du rang r ramène le compte à r − 1), soit `appliquer` admet
   un rang ≤ au compte présent. Il faut aussi un test : une ligne en triple
   ramenée à une, puis remontée à trois, avec `appliquer` sur la sortie
   **relue du disque**.

## À corriger (non bloquants)

1. `src/pharmaflux/evenements/schema.py:171` — `champs_modifies` n'est pas
   vérifié comme une liste : une chaîne `"abc"` est acceptée et lue
   `("a", "b", "c")`. C'est le même genre d'écart que le correctif 2 du
   contrôle du palier 2. Exiger une liste, comme `_chaines` exige un objet ;
   même remarque pour `anomalies`.
2. `src/pharmaflux/evenements/rejeu.py:19` et l'ADR 0006 (l. 113-114) :
   « l'état garde la dernière archive avant lui » est à reformuler avec le
   bloquant 1 (dernière archive au verdict définitif).

## Remarques

- **La lecture de l'ordre est fidèle.** Toutes les décisions de l'addendum
  sont tenues : contrat `presentations` v1 avec `canonique` et `milliers`,
  et leurs raisons ; partage lisibilité / forme règle par règle, dans le
  code comme dans l'ADR 0005 ; identifiant sur les **chemins relatifs** ;
  ordre alphabétique des colonnes dit dans l'ADR 0006 ; vide et bloquant
  écartés sans appel ; X = 1 % ; sortie par archive, écrite dans l'ordre
  événements, bilan, état ; refus de `--reprendre` sur un changement de
  version ; état illisible jamais traité comme vide.
- Les écarts annoncés sont tous dans les rapports et acceptés par l'IeC :
  règles dans `contrats/normalisation.py`, `appliquer` dès le palier 2,
  fenêtre de l'`inchange`, effacement de la sortie au rejeu complet, et
  474 Mo au pic (sur le Mac seulement, une condition de la mission 03).
- Les tests portent sur le **comportement** : octets de la sortie,
  décisions des bilans, état intermédiaire après coupure. Aucun ne m'a paru
  incapable d'échouer. Les deux trous ci-dessus sont des cas absents, pas
  des tests creux.
- Le code est lisible pour un recruteur. Les noms et les docstrings sont en
  français, il n'y a ni code mort ni `TODO`, les modules sont courts et les
  responsabilités nettes (`snapshot`, `comparaison`, `volume`, `bilan`,
  `rejeu`).

## Vérifications relancées

Au commit `54a36e3`, arbre propre, dans `pharmaflux-relecteur/`.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 124 files already formatted |
| `uv run mypy src` | Success: no issues found in 30 source files |
| `uv run pytest -q` | 401 passed (comme annoncé) |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 17 tests, OK |
| shellcheck | non relancé : aucun `.sh` dans `git diff --stat main...HEAD` |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` | 11 fichiers, 0 bloquante, code 0 |
| `uv run pharmaflux questions verifier --racine ~/pharmaflux-data` | 25 conforme, 5 non calculable, 10 sans attendu |
| `pharmaflux evenements` (rejeu complet, sortie dans mon dossier temporaire) | 7,97 s, 474 Mo résidents, code 0 ; 164 096 `creee`, 3 `supprimee` (présentations), infos importantes 3 lues, 2 retenues, 1 écartée : identique au rapport du palier 3 |
| second rejeu complet, `diff -r` | aucune différence |
| `--reprendre` sur le premier, `diff -r` | 0 archive lue, aucune différence |
| archive du Mac | 21 fichiers avant et après, md5 du manifeste inchangé |
| sonde : pertes en attente successives (bloquant 1) | `--reprendre` sans archive nouvelle : 9 événements perdus |
| sonde : triple ramené à un (bloquant 2) | `appliquer` lève `ValueError` |

Périmètre : `git diff --stat main...HEAD` ne touche **aucun chemin réservé à
l'IeC**. Les fichiers de `docs/relectures/` sont des contrôles de l'IeC
committés par le codeur, comme le prévoit le circuit. Rien de `data/`, aucun
secret, aucun appel réseau dans le code ni dans les tests de la mission.
`docs/journal.md` est seulement complété en fin de fichier.

Historique : un commit par palier (`370d087`, `5e00abf`, `5e102ec`), les
correctifs en nouveaux commits, aucune réécriture. Les 14 commits portent
les deux trailers. Les messages sont en français.

## Alertes

Aucune.
