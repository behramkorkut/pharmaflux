# Mission 01 — contrôle du palier 3 (IeC)

**Commit contrôlé** : `c98a750`. **Verdict** : palier 3 accepté **sans
correctif**. Une précision de chiffre est à glisser dans le commit du
palier 4 (ci-dessous). Passe au palier 4.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `c98a750` :

- ruff check et format (84 fichiers) : vert ;
- mypy strict (18 fichiers) : vert ;
- pytest : 198 tests, tous passent ;
- garde-fou : 16 tests, tous passent ;
- crochets git : vert.

Sur la copie rapatriée du Mac, en lecture seule :
`pharmaflux profil --racine ~/pharmaflux-data --markdown <dossier jetable>`
sort avec le code 0 et écrit onze fichiers. Ils sont **identiques** à ceux
de `docs/donnees/`, à la seule ligne « Produit le … » près. La promesse du
README (« seule la ligne Produit change ») est donc tenue, et chaque
chiffre de `docs/donnees/` peut être refait par une commande.

## Sur le fond

- **Profil (décision 4)** : il fait tout ce que demande l'ordre, et
  `valeur_inconnue` passe en tête comme le veut l'addendum. Les liens
  restent des mesures, jamais des anomalies. Le code de sortie 1 sur une
  bloquante est prêt pour l'alerte du Lot 5.
- **`docs/donnees/README.md` (décision 5)** : H.1 est en tête, comme
  demandé, avec le tableau des CIS absents. Les huit constats sont tous
  utiles au Lot 1. Le croisement MITM (83,8 %) et les 47 débuts postérieurs
  à la mise à jour sont mesurés, pas affirmés. La source et la date des
  extraits sont portées en tête de chaque profil, conformément à la licence
  BDPM. L'outil de lecture du PDF est documenté comme convenu.
- **ADR 0001 à 0004 (décision 6)** : ils suivent le gabarit et sont datés.
  La ligne demandée au contrôle du palier 2 figure dans 0002. Le 0003 est
  « proposé », avec sa revue au plus tard le 07/12/2026 et un critère de
  passage à « accepté » chiffré et réfutable : c'est ce qui était attendu.
  Le 0004 tient en un tableau les cinq requêtes, leur heure et ce que
  chacune apprend : un lecteur voit que le budget a été respecté.

## Précision à faire au palier 4

Le commentaire ajouté à `contrats/bdpm/specialites.toml` dit « 1 261 le
24/10 », alors que le README et le profil disent **1 263**. Les deux sont
justes, mais sur deux archives différentes de `CIS_CIP_bdpm.txt` du même
jour : j'ai recompté 1 261 contre celle de 19:41Z et 1 263 contre celle de
23:17Z. Il faut nommer l'archive dans le commentaire, ou s'aligner sur
1 263 (23:17Z), celle que le profil utilise. Cela ne touche que le
commentaire, sans changer la version.

## Écarts

1. **PDF d'avis non téléchargé** : accepté. Suivre la redirection aurait
   été une sixième requête, et s'arrêter était la bonne conduite. L'ADR le
   dit, et la mesure est renvoyée au Lot 3.
2. **Deux liens de mesure ajoutés à des contrats `v0`** : accepté. Un lien
   ne change pas la vérification, et les contrats ne sont pas encore
   fusionnés. Règle à partir de la fusion : tout changement de contenu d'un
   contrat, lien compris, passe par une nouvelle version.
3. **« Ordre des dates »** : accepté, c'est la mesure que demandait le
   contrôle du palier 2, rendue générale.
4. **`<identifiant>.md`** : accepté, le catalogue est la référence.
5. **Décision 12 au palier 4** : conforme à l'ordre.

## Réponse à ta question (ADR 0004)

**Les pages HTML d'abord, les PDF en second, par étapes depuis 2024 :
validé.** La synthèse HTML donne le motif, la date et le résumé, ce qui
suffit à citer et à orienter. Les PDF n'apportent le détail du
raisonnement de la Commission qu'au prix d'une redirection par document et
d'une extraction de texte. Le jeu de questions de référence dira au Lot 3
si ce détail manque. L'ADR reste « accepté » : la partie PDF est
explicitement conditionnelle et sa mesure est datée au Lot 3, ce qui
suffit.

## Refus du garde-fou

`awk` sur `01_Specifications/` est refusé à juste titre. `awk` peut écrire
depuis son propre programme (`print > fichier`), donc le garde-fou ne le
compte pas parmi les lectures sûres. `grep -n` puis `sed -n` est la bonne
méthode. Rien à changer.

## Proposition d'évolution

Colonne « Statut » de l'annexe A du PRD : retenue pour la v0.3, que
j'écrirai après la fusion de la mission.

## Suite

Commite ce fichier tel quel, puis passe au palier 4.
