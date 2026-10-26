# Mission 01 — contrôle du palier 2 (IeC)

**Commits contrôlés** : `ee50cdc` (correctif C1 du palier 1) et `787e035`
(palier 2). **Verdict** : C1 levé, palier 2 accepté **sans correctif**.
Passe au palier 3.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `787e035` :

- ruff check et format (63 fichiers) : vert ;
- mypy strict (16 fichiers) : vert ;
- pytest : 190 tests, tous passent ;
- garde-fou : 16 tests, tous passent ;
- crochets git : vert.

Sur la copie rapatriée du Mac, en lecture seule, avec un script jetable qui
passe par `charger_tous`, `bronze.lister` et `verifier` : les onze contrats
se chargent. Les douze archives TSV de la copie (onze du 24/10 et une
seconde de `CIS_CIP_bdpm.txt`, 23:17Z) donnent **0 anomalie bloquante**, et
exactement les comptes du rapport :

- 17 016 `espace_parasite` et 1 `code_illisible` dans `CIS_bdpm.txt` ;
- 995 `decimal_illisible`, 52 `date_hors_plage` et 3 espaces dans
  `CIS_CIP_bdpm.txt` ;
- 1 309 espaces dans `CIS_COMPO_bdpm.txt` ;
- 3 `ligne_vide` et 3 espaces dans `CIS_CPD_bdpm.txt` ;
- 5 `ligne_dupliquee` dans `CIS_CIP_Dispo_Spec.txt` ;
- rien dans les six autres.

## C1 (palier 1)

Levé. Les motifs sont définis à un seul endroit, et la liste des
signalements est fermée et commentée. `vaut_collecte` exige à la fois une
empreinte connue et de seuls signalements, donc `HTTP 404 ; lien_change`
repasse bien. La conséquence que tu signales est acceptée : le code de
sortie 1 n'apparaît qu'une fois par jour pour une entrée quotidienne en
alerte, et l'alerte reste visible dans `etat`, qui est l'outil de
surveillance.

## Sur le fond

- **Contrats** : chaque contrat cite la section du PDF, son sha256 et
  l'archive de référence avec son sha256. Les descriptions portent les
  constats datés (667 lignes sur 703 sans CIP13, 290 fiches ANSM). C'est
  exactement ce qu'un lecteur doit pouvoir retrouver. La `raison` de la clé
  de Dispo_Spec dit pourquoi aucune combinaison n'est unique et renvoie au
  Lot 1.
- **Chargeur strict** : refuser une clé inconnue ou sans objet pour le type
  protège des fautes de frappe silencieuses dans un TOML. La vérification
  des liens entre contrats est un bon ajout.
- **Vérification** : elle ne corrige jamais, la valeur brute est rendue, et
  la lecture continue après une anomalie. Les quatre règles bloquantes sont
  celles de l'addendum.

## Écarts

1. **Ligne vide bloquante, sauf contrat qui la déclare** : accepté. Une
   seule règle, et la tolérance est écrite dans le contrat de CPD, là où on
   la cherchera.
2. **Fichier cp1252 qui se décode entier en UTF-8** : accepté, c'est un vrai
   trou que le décodage strict ne voit pas. Le faux positif théorique (un
   texte cp1252 qui contiendrait littéralement des suites comme `Ã©`) est
   négligeable, et vérifié absent sur les neuf fichiers.
3. **Énumérations au-delà de la documentation** : accepté. Faire de
   `motif_evaluation` une énumération des douze libellés observés, c'est ce
   qui fera sortir un nouveau motif. C'est le rôle d'un contrat.
4. **`\r` de CPD laissé dans la valeur** : accepté, on constate sans
   corriger.
5. **Plages de dates par colonne, sans règle entre colonnes** : accepté,
   c'est la réponse à ta question. Une règle entre colonnes (début
   postérieur à la mise à jour) est une règle métier, pas de schéma. Le
   profil mesure les 47 cas au palier 3, et le Lot 1 décidera s'il faut
   l'alerter. Une remarque : les bornes hautes fixes (2030, 2035) devront
   être relevées avant d'être atteintes. Mets-le en une ligne dans l'ADR des
   contrats au palier 3, avec la règle « une borne haute se relève par une
   nouvelle version du contrat ».

## Refus du garde-fou

`uv run pytest .claude/hooks` est refusé à juste titre : pytest écrirait
son cache et ses `__pycache__` dans `.claude/`, qui m'est réservé. La
commande prévue, `python3 infra/agents/test_garde_fou.py`, est la bonne.
Rien à changer.

## Suite

Commite ce fichier tel quel, puis passe au palier 3.
