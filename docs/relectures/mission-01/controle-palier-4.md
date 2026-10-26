# Mission 01 — contrôle du palier 4 (IeC)

**Commit contrôlé** : `87b1ab9`. **Verdict** : palier 4 accepté **sans
correctif**. La précision demandée au contrôle du palier 3 (1 263 contre
1 261 dans `specialites.toml`) est faite. Les quatre paliers sont acceptés :
la mission passe en relecture.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `87b1ab9` :

- ruff check et format (92 fichiers) : vert ;
- mypy strict (22 fichiers) : vert ;
- pytest : 229 tests, tous passent ;
- garde-fou : 16 tests, tous passent ;
- crochets git et shellcheck 0.11.0 : vert.

Sur la copie rapatriée du Mac, en lecture seule :

- `pharmaflux questions verifier --racine ~/pharmaflux-data` donne
  40 questions : 25 conformes, 5 non calculables, 10 sans attendu, code 0,
  comme dans le rapport ;
- **contre-épreuve** : sur une copie jetable du jeu où j'ai remplacé
  `65%` par `65 %` dans `remboursement-001`, la commande signale
  « attendu « 65 % », lu « 65% » » et sort avec le code 1. Le jeu est donc
  bien recalculé depuis l'archive, à l'octet près, et pas seulement relu.

## Sur le fond

- **Le jeu v0** respecte l'ordre et l'addendum F. Il y a cinq questions par
  catégorie, toutes sur des médicaments réels de l'archive, sans aucun
  patient. Deux questions portent sur un CIS absent du référentiel, et une
  seule question Historique a un début futur, voulu. Les questions Dépense
  sont renvoyées au Lot 4. Les valeurs sont brutes, avec leur graphie.
- Les champs `prudence` sont le meilleur du jeu : « aucun signalement à
  cette date » n'est pas « disponible partout », il y a trois SMR par
  indication, et un arrêt annoncé n'est pas un arrêt. C'est exactement ce
  que le Lot 3 devra noter, et ce qu'un assistant naïf rate.
- Les questions Hors périmètre et Médical ont chacune un motif et une
  orientation concrète (3237, signalement-sante.gouv.fr, ameli.fr), comme
  le demande l'annexe B.
- **Le vérificateur** : la lecture est stricte, contrôlée contre les
  contrats, et une archive non conforme arrête la comparaison. Il y a un
  verdict par cas, chacun testé sur un jeu dédié. Sortir `tomlstrict.py`
  pour le partager entre contrats et questions est le bon réflexe : il n'y
  a plus deux chargeurs stricts à tenir.

## Écarts

1. **Table `attendu` omise pour les questions Dépense** : accepté. C'est
   l'addendum F (« absent ») qui fait foi sur l'ordre (« vide »), et refuser
   une réponse qui aurait les deux, ou aucun des deux, ferme la porte aux
   jeux bancals.
2. **`valeurs = []` pour « aucune ligne »** : accepté, et c'est une
   amélioration. « Aucun générique » ou « aucun signalement » deviennent
   des faits vérifiés à une date au lieu d'affirmations.
3. **`prudence` non vérifié par la machine** : accepté. Ce texte est pour
   la notation du Lot 3, qui le reprendra.

## Réponses à tes questions

1. **Avis HAS lus dans les fichiers BDPM pour la v0 : oui.** Le corpus de
   l'ADR 0004 n'existe pas encore. Le niveau, la date et le lien, qui sont
   l'attendu de l'annexe B, sont tous dans SMR, ASMR et les liens CT. Les
   questions sur le texte des avis viendront au Lot 3, avec le corpus.
2. **`alternatives-004` : à garder en v0, à remplacer en v1.** Les
   présentations d'un même CIS ne sont pas une alternative au sens de
   l'annexe B, dont l'exemple vise le *groupe générique*. Cette question-là
   demande une jointure GENER × CIP, que l'attendu sur un seul fichier ne
   sait pas encore exprimer. Comme l'identifiant porte la catégorie, on ne
   déplace pas la question. En v1, `alternatives-004` est retirée et une
   nouvelle question sur le groupe la remplace, quand le gold du Lot 1
   permettra la jointure.

## Une correction pour moi, pas pour toi

J'avais demandé, dans l'addendum F, une **abstention motivée** sur un CIS
absent de `CIS_bdpm.txt`. Tu l'as appliquée à la lettre, et c'est juste
pour `disponibilite-005`. Pour `avis_has-005` en revanche, l'avis existe
(CT-21978 du 09/09/2026) : l'assistant devrait donner le niveau de SMR et
sa date, et dire en même temps que le référentiel ne connaît pas encore ce
CIS. C'est donc une réponse avec réserve, pas une abstention. Rien à
changer en v0, qui suit l'ordre. Je le note pour la v1 et pour le Lot 3.

## Proposition d'évolution

PRD, annexe B : retenue pour la v0.3. Elle dira que chaque question porte
un comportement attendu (réponse, abstention, refus), et que l'attendu
d'une réponse cite l'archive (chemin et sha256).

## Suite

Commite ce fichier tel quel. La suite de l'ordre est la relecture
(`/relire-mission 01`), que beko lance dans `pharmaflux-relecteur/`. Tu
attends ce fichier de relecture. N'écris pas encore `pr.md` : il vient
après « CONFORME ».
