# Mission 02 — contrôle du palier 3 (IeC)

**Commit contrôlé** : `5e102ec`. **Verdict** : palier 3 accepté **sous
réserve d'un correctif** et d'une correction de formulation, à faire dans
un nouveau commit. La mission passera ensuite en relecture.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `5e102ec` :

- ruff check et format, mypy (30 fichiers) : vert ;
- pytest : 399 tests, tous passent ;
- crochets git et garde-fou : OK ;
- `profil` : 11 fichiers, 0 bloquante ;
- `questions verifier` : 25 / 5 / 10 ;
- shellcheck : non rejoué, aucun `.sh` n'est touché.

J'ai rejoué la démonstration sur la copie du Mac, en lecture seule, avec la
sortie dans mon dossier temporaire :

- **rejeu complet** : 7,8 s, 474 Mo résidents, code 0. J'obtiens les mêmes
  comptes que ton rapport : 164 096 `creee`, 3 `supprimee` sur les
  présentations, et 1 archive écartée sur les infos importantes ;
- **deux rejeux complets** dans deux dossiers : `diff -r` ne trouve
  **aucune différence** ;
- **`--reprendre`** sur le premier : 0 archive, 2,9 s, et toujours aucune
  différence avec le second ;
- **l'archive** est intacte : 21 fichiers avant et après, et même empreinte
  md5 du manifeste.

## Sur le fond

- **La sortie par archive et l'ordre d'écriture** (événements, bilan, état,
  chacun écrit entier puis renommé) sont faits comme décidé. Les snapshots
  ne sont jamais sérialisés.
- **L'archive en attente**, ses deux résultats et son bilan réécrit sont
  testés aux treize points d'arrêt, dont l'attente tranchée dans les deux
  sens. C'est exactement ce que demandait F.2.
- **La fenêtre de confirmation par `inchange`**, entre l'archivage et
  l'archive suivante (écart 2) : acceptée. C'est la seule lecture juste,
  puisqu'au-delà de l'archive suivante, un `inchange` compare à cette
  dernière.
- **Les refus de `--reprendre`** sont bien couverts : contrat changé, état
  illisible, archive disparue du bronze. Le code 2 les distingue du code 1
  (archive illisible).
- **La sortie sous la racine de l'archive est refusée** : c'est le bon
  verrou.
- **L'ADR 0006** dit l'ordre alphabétique pour l'identifiant comme pour le
  tri, comme demandé.

## Correctif

**Un rejeu complet interrompu, suivi de `--reprendre`, perd des événements
sans rien dire.** Au rejeu complet, `_traiter_entite` efface
`evenements/<entite>/` et `bilans/<entite>/`. Mais `etat.json` garde
l'**ancienne** entrée de l'entité jusqu'au premier `_ecrire_etat`. Si
l'exécution s'arrête entre les deux, la sortie est vidée alors que l'état
dit encore « traité jusqu'à X ». C'est le cas d'une archive illisible dès la
première (`break` avant toute écriture d'état), d'un Ctrl-C ou d'une
coupure. `--reprendre` repart alors de X et ne réécrit rien.

Je l'ai reproduit sur la copie du Mac. J'ai pris la sortie d'un rejeu
complet, j'ai effacé les deux dossiers de `bdpm.presentations` comme le
fait le rejeu, sans toucher à l'état, puis j'ai lancé
`--reprendre --fichier bdpm.presentations`. Résultat : 0 archive lue,
code 0, et les **20 901 événements** des présentations absents. C'est
exactement ce que la décision 8 interdit : la reprise ne donne plus la
sortie du rejeu complet.

Correctif attendu : au rejeu complet, **retirer l'entité de `etat.json`
d'abord** (réécriture atomique), **puis** effacer ses dossiers. Une reprise
après n'importe quelle coupure voit alors une entité sans état, et la
rejoue en entier. Ajoute un test : un rejeu complet par-dessus une sortie
existante, interrompu après l'effacement (par une archive illisible en
tête, par exemple), puis `--reprendre` doit donner, une fois l'archive
rendue lisible, les octets du rejeu complet. Une phrase dans l'ADR 0006,
section reprise.

## Formulation

ADR 0006, ligne 146 : « loin des 256 Mo de l'unité du VPS » se lit comme
« bien en dessous ». C'est l'inverse : 474 Mo, c'est **près de deux fois
au-dessus**. Écris-le ainsi. Garde la conclusion : écriture en flux avant
toute exécution sur le VPS (mission 03).

## Écarts

1. **474 Mo au pic** : accepté **pour cette mission**, qui ne tourne que sur
   le Mac. C'est une condition de la mission 03 : aucune exécution de la
   chaîne sur le VPS avant l'écriture en flux. Je l'inscrirai dans l'ordre
   de la mission 03.
2. **Fenêtre de l'`inchange`** : accepté (voir plus haut).
3. **Le rejeu complet efface la sortie de l'entité** : accepté sur le
   principe, avec le correctif ci-dessus sur l'ordre des opérations.

## Proposition d'évolution

PRD §6.3 : l'identité d'une ligne sans clé unique (empreinte + rang) et
l'ordre alphabétique des colonnes y entreront à la prochaine version. Je
les note.

## Suite

Commite ce fichier tel quel. Fais le correctif et la formulation dans un
nouveau commit, réponds dans `docs/rapports/mission-02/reponse-controle-3.md`,
rejoue les vérifications, puis arrête-toi et annonce le commit. Après mon
accord vient la relecture (`/relire-mission 02`), que beko lance dans
`pharmaflux-relecteur/`. N'écris pas encore `pr.md`.
