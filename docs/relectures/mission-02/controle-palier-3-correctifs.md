# Mission 02 — contrôle du correctif du palier 3 (IeC)

**Commit contrôlé** : `81635d5`. **Verdict** : le correctif et la
formulation sont acceptés, et le palier 3 avec eux. La mission passe en
relecture, après une petite retouche de message décrite plus bas.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `81635d5` :

- ruff check et format, mypy (30 fichiers) : vert ;
- pytest : 400 tests, tous passent.

Le diff touche seulement `rejeu.py`, son test, l'ADR 0006 et ta réponse. Ni
contrat ni vérification ne bougent, donc je n'ai rejoué ni `profil` ni
`questions`.

## Le correctif

- **Le code** : `_retirer_etat` réécrit `etat.json` sans l'entité, entier
  puis renommé, **avant** le `rmtree`. Il n'écrit rien quand l'entité est
  absente de l'état, donc un rejeu complet sur un dossier vide ne change
  pas.
- **Le test** est le bon. Il fait un rejeu complet par-dessus une sortie
  existante, que la première archive, rendue illisible, coupe en tête. Il
  vérifie l'état intermédiaire : l'entité est absente de l'état, l'autre
  entité y reste, et le dossier est effacé. Puis il lance `--reprendre` et
  obtient les octets de la référence. Je l'ai passé sur le `rejeu.py` de
  `5e102ec` : il échoue sur l'état intermédiaire, comme tu l'annonces.
- **Sur la copie du Mac**, en lecture seule, avec la sortie dans mon
  dossier temporaire :
  - le rejeu complet est identique au `diff -r` à celui du palier 3 ;
  - j'ai provoqué de **vraies coupures** : un rejeu complet de
    `bdpm.presentations` par-dessus une sortie existante, tué par SIGTERM
    à 0,3, 0,6 et 1,0 s. Les trois fois, l'entité est absente de l'état et
    son dossier est vide. `--reprendre` relit alors les 3 archives et
    réécrit les 20 901 événements (20 898 `creee`, 3 `supprimee`). La
    sortie est identique à l'octet à celle du rejeu complet ;
  - l'archive est intacte : même nombre de fichiers, et même empreinte du
    manifeste.
- **L'ADR 0006** dit l'ordre des opérations dans la section reprise, ajoute
  le test à la liste et écrit « près de deux fois au-dessus » des 256 Mo,
  avec la conclusion gardée. C'est ce qui était demandé.

## Remarque : un message qui mène à une impasse

Un rejeu complet **sans** `--reprendre`, par-dessus un `etat.json`
illisible, sort avec le code 2 et le message « état illisible … : relance
sans --reprendre ». L'utilisateur vient justement de le faire : le conseil
tourne en rond. Le comportement, lui, est sûr. Rien n'est effacé, le code
est non nul, et le fichier est nommé. Le cas existait déjà en `5e102ec`,
au premier `_ecrire_etat`, et après un effacement. Ton correctif le rend
plus sûr, puisque l'échec vient maintenant avant l'effacement.

Retouche demandée, petite : quand l'état est illisible hors
`--reprendre`, le message dit quoi faire. Par exemple : « supprime
etat.json ou choisis une autre sortie ». Ajoute un test du code 2 et de ce
message. **Ne traite pas un état illisible comme vide** : avec `--fichier`,
on perdrait sans rien dire l'état des autres entités.

## Suite

Commite ce fichier tel quel. Fais la retouche dans un nouveau commit et
note-la en une ligne à la fin de `reponse-controle-3.md`. Rejoue ruff,
mypy et pytest, puis annonce le commit à beko : ce sera le sommet que la
relecture lira. Je ne fais pas de nouveau contrôle pour cette retouche.
beko lance alors `/relire-mission 02` dans `pharmaflux-relecteur/`.
N'écris pas encore `pr.md` : il vient après une relecture « CONFORME ».
