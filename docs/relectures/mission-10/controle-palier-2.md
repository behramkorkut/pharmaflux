# Mission 10 — contrôle du palier 2 (IeC)

**Commits contrôlés** : `95a35ac19195111f276949a54b654ec0bab00192` (le code) et `06201e0` (le
rapport) · **Date** : 15/11/2026

**Verdict : accepté, avec trois retouches avant la mise en service.**
- Les quatre fichiers que root lira sont acceptés tels quels.
- La mise en service (étape 9b) attend un commit de retouches, sa CI verte, son contrôle et
  son dépôt.

## Ce que l'IeC a vérifié

**Les fichiers que root lira.**
- `pharmaflux-chaine.service` et `pharmaflux-verification.service`, sans les commentaires,
  sont l'unité de remplissage contrôlée à `e12c14d`, à quatre lignes près :
  - la description ;
  - `ExecStart` (`chaine passer`, `chaine verifier`) et `SyslogIdentifier` ;
  - `TimeoutStartSec` (50 min, 40 min) ;
  - `CPUQuota` (100 %, addendum 1, question 16).
- Le durcissement, le compte, les chemins, le plafond de mémoire et le réseau sont donc ceux
  qui tournent déjà sous le remplissage.
- Ni l'une ni l'autre n'a d'`OnSuccess=` ou d'`OnFailure=` : un échec du passage ne relance
  rien.
- Le minuteur : 03:40 UTC, `Persistent=true`, et rien d'autre.
- Le complément de la collecte n'ajoute que `OnSuccess=` et `OnFailure=` dans `[Unit]`
  (question 6). L'unité de la collecte n'en avait aucun.
- Les autres fichiers que root lit n'ont pas changé depuis `e12c14d` : les unités du
  remplissage, de la collecte (et son minuteur) et des conteneurs, `docker-compose.yml`,
  `vps.yml`.

**Le dépôt sur le VPS** (lu par `pharmaflux-vps`) :
- `versions/95a35ac…` est en place, avec le `VERSION` entier ;
- aucun fichier hors du groupe `pharmaflux-chaine`, aucun dossier sans `setgid` ;
- `courante` pointe toujours vers `eecc9f3…` ;
- les quatre fichiers d'unité déposés ont les empreintes de `95a35ac` dans git :

  | fichier | sha256 |
  |---|---|
  | `pharmaflux-chaine.service` | `dd8234f6…` |
  | `pharmaflux-verification.service` | `52d180b4…` |
  | `pharmaflux-verification.timer` | `f7890ec7…` |
  | `pharmaflux-collecte.service.d/chaine.conf` | `fe92cab7…` |

- `chaine etat`, lancé depuis la version déposée sur le vrai journal, dit `jamais lancée`.
  Il montre le remplissage complet, aucun témoin et aucune erreur, et il n'écrit rien.

**Le code, contre l'addendum 1.**
- **Question 7** : le seul échec circonscrit est `publier` 3. Ce code ne vient que des
  messages rangés dans la file des échecs (`publication.py`, l. 99), et le passage le confirme
  par `publication.json`. Il ne lit aucune sortie texte.
  `evenements` 1 arrête le passage : ce n'est pas un écart, c'est la condition de la question
  appliquée.
- **Question 8** : un témoin différent refuse avant toute étape et nomme le geste.
- **Question 9** : le verrou tenu sort en 0 avec une ligne, pour le passage comme pour la
  vérification.
- **Question 18** : `FORMAT_SILVER` existe, avec un test qui échoue si le schéma change sans
  lui.
- Le passage ne construit jamais l'index. Chaque étape choisit l'interprète de sa version, pas
  le lien `courante`.
- Le verrou de la chaîne est un `flock` (`fcntl.flock`), le même que celui de la commande
  `flock` de la bascule.
- La CI gagne deux passages à vide, les vérifications et l'état en JSON (`à jour`, aucun écart
  de formats, vérification en code 0).

**Les écarts déclarés** : acceptés tous les deux. Le second commit portait le script de mesure
à déposer.

## Les deux questions

**Question 1, la mesure de l'encodage sous l'unité : ni (a) ni (b). La question est close.**

Ta mesure ne tranche pas l'hypothèse, mais elle suffit pour décider :
- Le passage horaire a un cœur (`CPUQuota=100%`). Sur un cœur, un fil est le meilleur
  réglage : 5,42 fragments/s, contre 4,76 au défaut.
- Sous l'unité, le remplissage a encodé à 5,70 fragments/s en occupant environ un cœur. C'est
  le comportement d'un seul fil.
- Quoi que choisisse onnxruntime sous l'unité, le passage horaire n'y perd donc au plus que
  14 %, sur des lots de quelques milliers de fragments.
- Le remplissage seul pourrait gagner à deux fils. Il ne sert qu'à rebâtir, et il garde 39 %
  de marge sur ses 6 h.

Faire tourner une mesure sous `pharmaflux-chaine`, par root ou par une unité de plus, n'en
vaut pas le risque. `intra_op_num_threads` reste au défaut (question 17), et `ProcSubset=pid`
reste. `infra/vps/mesurer_encodage.py` reste dans le dépôt, avec ta mesure dans le rapport.

**Question 2, le témoin écrit par le premier passage : accepté.**

Le dérivé a été bâti par `eecc9f3`. Entre `eecc9f3` et `95a35ac`, `src/` ne change que dans
`chaine/` et `cli.py` : aucun format du dérivé n'a pu changer. Le témoin que le premier
passage écrira dit donc vrai.

La condition : le commit que tu déposeras vérifie la même chose. Tu cites
`git diff --stat eecc9f3 <commit> -- src` dans ton rapport : rien hors de `chaine/` et de
`cli.py`.

## Les trois retouches (un commit, avant le dépôt)

1. **`chaine etat` : la première ligne doit tout dire**, comme l'écrit le README. Aujourd'hui,
   le verdict ne lit que le dernier passage horaire.
   - Une vérification quotidienne en échec (code 1, par exemple `index verifier` non
     conforme) laisse le verdict à `à jour`. Elle n'apparaît qu'à la cinquième ligne.
   - Une vérification qui ne tourne plus (minuteur arrêté, ou sautée deux jours de suite
     parce que le verrou était tenu) ne se voit nulle part.

   Ce qui est demandé :
   - le verdict ajoute la dernière vérification quand son code n'est pas 0, avec l'étape en
     cause ;
   - il l'ajoute aussi quand elle date de plus de 26 h, ou qu'il n'y en a aucune alors que le
     premier passage horaire a plus de 26 h ;
   - la ligne `vérification` donne son âge, en heures ;
   - un passage horaire en code 1 sans `arret`, c'est-à-dire un échec circonscrit, est nommé
     comme tel, avec son étape, et non `en panne (code 1)` ;
   - des tests pour chacun de ces cas.

2. **`infra/vps/README.md`, étape 9 : l'ordre de la mise en service.**
   - **Avant 9b**, le commit contrôlé est déposé et `courante` basculé sous le verrou (4a).
     beko le vérifie par `ls -l /srv/pharmaflux/code/courante` : sans cela, chaque passage
     lancerait `chaine passer` sur `eecc9f3`, qui ne la connaît pas.
   - **En 9b**, après le minuteur et avant le complément de la collecte, beko lance une
     vérification (question 21, « après chaque dépôt ») :
     `sudo systemctl start pharmaflux-verification.service`. Elle dure environ quatre
     minutes. Puis il colle à l'IeC `systemctl show pharmaflux-verification.service -p Result
     -p ExecMainStatus` et `chaine etat`.
   - Seulement ensuite, le complément de la collecte, entre deux passages.

3. **`src/pharmaflux/chaine/formats.py`, l. 29** : le commentaire renvoie à
   `tests/test_chaine_formats.py`, qui n'existe pas. Le test est
   `tests/test_chaine_horaire.py::test_le_numero_du_silver_suit_son_schema`.

Les unités ne changent pas dans ce commit. Leurs empreintes doivent rester celles du tableau
ci-dessus, et le rapport des retouches le montre.

## La suite

1. **Le codeur** : le commit des retouches, avec un court rapport
   (`docs/rapports/mission-10/palier-2-retouches.md`), et ce fichier de contrôle commité tel
   quel. Puis il s'arrête.
2. **beko** pousse. La CI de la PR brouillon doit être verte à ce commit, et le codeur cite le
   run.
3. **L'IeC** contrôle les retouches.
4. **Le codeur** dépose ce commit et bascule `courante` sous le verrou (4a). Il cite la
   bascule, les droits, et le `diff --stat` de la question 2.
5. **beko** installe les unités : 9a, puis 9b dans l'ordre retouché, puis 9c (la liste polkit
   vidée). L'IeC compare les empreintes installées à celles du tableau.
6. **L'observation** commence au premier passage horaire.
