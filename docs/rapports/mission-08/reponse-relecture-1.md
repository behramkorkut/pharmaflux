# Mission 08 — réponse à la relecture 1

Relecture 1 (Claude Fable 5.1, sur `98cdb69`) : **CONFORME, 0 bloquant**. Les six points non
bloquants sont corrigés, ainsi que cinq des remarques. Le fichier de la relecture est committé
tel quel, en `50ff304`.

Il y a trois commits, et cette réponse est complétée dans un quatrième :
- **`50ff304`** porte les points 1, 4, 5 et 6, et les remarques de rendu. Aucun ne touche le
  chemin ni la notation.
- **`3a102db`** porte les points 2 et 3, et la première version de cette réponse.
- **`a87a883`** porte les cas de test que l'IeC a demandés pour ces deux points, sans changer
  le code.

**Les points 2 et 3 sont corrigés après la mesure, sur relecture, sans effet sur les
indicateurs (preuve jointe).** L'IeC a décidé de les traiter dans cette mission. Sa règle
« rien ne change après le résultat » sert à empêcher d'ajuster l'assistant sur les réponses de
Claude, et ces deux défauts viennent de la relecture du code. Le point 2 est même un écart à
l'ordre, puisque l'exemple de son propre §0 D n'était pas refusé. La preuve est plus bas.

## À corriger

1. **Le test « clé absente » ne bloquait pas le réseau** : corrigé (`50ff304`). Le test isole
   maintenant l'environnement comme l'addendum 1 J le demande :
   - les variables `ANTHROPIC_*` sont retirées ;
   - le dossier personnel est temporaire et vide (`HOME`, `XDG_CONFIG_HOME`) ;
   - toute connexion réseau est refusée (`socket.socket.connect`).

   Le code ne lit d'ailleurs **aucun profil** : `cle_presente` ne regarde que
   `ANTHROPIC_API_KEY` et répond avant tout import du SDK. Le vrai client n'est jamais construit
   sans clé.

2. **Le cadre du refus médical** : **corrigé après la mesure, sur relecture, sans effet sur
   les indicateurs (preuve jointe)** (`3a102db`, `regles.py` ; cas de test en `a87a883`). En
   plus de
   « puis-je / dois-je / faut-il », il connaît les tournures de même structure :
   - « peut-on », « peut-il », « peut-elle », « peuvent-ils », « peuvent-elles » ;
   - « je peux », « on peut » ;
   - « doit-on », « doit-il », « doit-elle », « je dois », « on doit » ;
   - « est-il possible de », « est-ce que je », « est-ce qu'on ».

   Le cadre se cherche désormais **en mots entiers**. Auparavant, une sous-chaîne aurait fait de
   « depuis je » un « puis je ».

   Les tests vont dans les deux sens :
   - **refusées** : les quatre questions de la relecture, dont « Mon fils de 6 ans peut-il
     prendre le générique de DOLIPRANE ? », l'exemple du §0 D de l'ordre ;
   - **non refusées**, faute de geste de soin (les cas demandés par l'IeC) :
     - « LARIAM peut-il être en rupture ? » ;
     - « Est-il possible de connaître le taux de remboursement de DOLIPRANE 1000 mg ? » ;
     - « Peut-on savoir si DOLIPRANE 1000 mg est commercialisé ? » ;
     - « Est-ce que je peux trouver la date de l'avis de LEVOTHYROX ? » ;
     - « On peut trouver le prix public de DOLIPRANE où ? » ;
     - et « Depuis je ne sais quand… ».

   D2 reste vert **sur la v1 et sur la v0**, avec un test pour chacune : chaque question
   `medical` est refusée, et aucune autre (zéro faux refus, zéro oubli).

3. **« 1er juillet 2027 » n'était pas une date** : **corrigé après la mesure, sur relecture,
   sans effet sur les indicateurs (preuve jointe)** (`3a102db`, `controle.py` ; cas de test en
   `a87a883`). `_EN_LETTRES` accepte l'ordinal « 1er ». Le test va dans les deux sens :
   - « 1er juillet 2027 », appuyé par « 2027-07-01 », est accepté ;
   - « 1er août 2027 », non appuyé, donne une abstention ;
   - « 1er juillet », sans année, ne s'appuie pas non plus, puisque le jour et le mois sans année
     ne s'appuient jamais ;
   - « 1er » sans mois (« le 1er du mois ») ne devient pas une date.

   Aucune des réponses réelles de l'évaluation n'a écrit « 1er ».

4. **L'assertion de `test_index.py` qui ne pouvait pas échouer** : corrigée (`50ff304`). Le test
   vérifie la charge que `fusion_rrf` garde vraiment : `{"t": "X"}` pour `x`, et la charge de la
   dernière voie pour `y`.

5. **L'estimation d'entrée « majore »** : le commentaire est faux, et il est corrigé (`50ff304`,
   `budget.py`, ADR 0012). Recompté dans le journal :
   - l'entrée réelle des 62 appels est de **223 934 jetons**, soit 3 612 par appel, contre 1 768
     estimés. **L'entrée est minorée d'un facteur 2**, sur un contenu fait de codes, de dates et
     de nombres ;
   - la sortie réelle est de 259 jetons en moyenne et 661 au plus, contre 4 000 comptés ;
   - la porte reste donc prudente par la sortie : 0,087 $ estimés par appel, contre 0,016 $
     réels. L'addendum G2 est tenu.

   **La constante n'est pas changée** (`CARACTERES_PAR_JETON` reste à 3,8) : elle le serait
   après la mesure, et la porte n'en a pas besoin. La docstring de `jetons_estimes` ne dit plus
   « prudente ».

6. **Le miroir de D2 pour les abstentions dures** : ajouté (`50ff304`,
   `test_v1_aucune_reponse_attendue_n_est_abstenue_par_les_regles`). Aucune réponse attendue de
   la v1 n'est abstenue par `regles.abstention`, et les dix `depense` le sont toutes.

## La preuve que les scores ne bougent pas (condition de l'IeC)

La recette de `make evaluer` (telle que `make -n` l'affiche), toute en cache, a été lancée deux
fois : **avant** de committer les points 2 et 3, puis **au nouveau sommet `a87a883`**, sur
l'arbre propre. Les deux fois :
- aucun appel ;
- un journal des dépenses inchangé, de même empreinte (`fd9f7d50…`) et de 65 lignes, avant comme
  après ;
- **44/49 et 82/88**, exactement les chiffres du commit de clôture, et 0 citation invalide, 0
  conseil médical ;
- une sortie entière **identique à l'octet** à celle de `2891e98`, hors la ligne qui nomme le
  fichier de détail.

Rien d'autre ne pouvait bouger :
- toutes les questions `medical` de la v1 étaient déjà refusées par les règles, et D2 garantit
  qu'aucune autre ne l'est ;
- aucune réponse n'a écrit « 1er » ;
- les cinq constats restent les mêmes.

## Remarques

- **La condition dure « aucune citation invalide » est tenue par construction** : c'est écrit
  dans l'ADR 0012 (`50ff304`). Une étiquette hors des fournis devient une abstention dans le
  chemin, et la notation la revérifie de façon indépendante. Un compte à part de ces
  abstentions est une piste pour la mission 09.
- **Les mots courants qui « visent » des CIS** (« eau », « fer », « zinc »…) : je le note pour
  la mission 09. La v1, la v0 et les 200 tirages ne montrent aucun faux positif.
- **L'aide d'`index evaluer`** est mise à jour (`50ff304`) : elle dit la mesure dense, creux et
  hybride sur un jeu au choix.
- **`ColonneNonClassee`** sort maintenant en code 2, avec une ligne lisible (`50ff304`).
- **Les aides de rendu de la ligne de commande** sont typées (`Reponse`, `Note`, `Estimation`,
  `Indicateurs`, importés sous `TYPE_CHECKING`), et `mypy --strict` est vert (`50ff304`).
- **La docstring de `Reponse.decision`** liste les vraies provenances. Le cache se dit par
  `depuis_cache` (`50ff304`).
- **`--estimer` crée le sqlite du cache** : je ne le corrige pas. Le fichier est vide, sous
  `data/assistant` (hors git), et sans effet.
- **La graphie des sujets de commit** (accents ou non) et **la durée de `pytest`** (6 min 06
  contre 6 min 30, pour le même compte) sont notées. La première relève des consignes, et donc
  de l'IeC.
