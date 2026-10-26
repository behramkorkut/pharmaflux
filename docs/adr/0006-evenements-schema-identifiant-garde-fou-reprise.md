# ADR-0006 — Événements : schéma v1, identifiant par chemins d'archive, comparaison ligne à ligne, garde-fou de volume, premier snapshot, reprise

**Statut :** accepté · **Date :** 2026-10-26 · **Mission :** 02 ·
**Mis à jour :** 2026-10-27, écriture en flux (mission 03, palier 1)
**Remplace / remplacé par :** — · s'appuie sur l'ADR 0005 (normalisation)

## Contexte

Le Lot 1 doit transformer le bronze (une archive par passage et par
fichier) en un flux d'**événements** : ce qui a changé, quand, d'où (PRD
§6.3), rejouable à l'identique (PRD §7.1), avant Redpanda (mission 03) et
le lakehouse (Lot 2). Mesures du §0 de la mission 02 et de la
démonstration (copie du Mac, lecture seule) :

- trois fichiers sur onze n'ont pas de clé unique (SMR, ASMR, Dispo_Spec,
  ADR 0002) ; Dispo_Spec a 5 lignes en double ;
- les changements réels observés sont minuscules : 2 puis 1 `supprimee`
  sur `CIS_CIP_bdpm.txt` (−0,010 %, −0,005 %), et le 26/10 à 14:17 un
  `CIS_InfoImportantes.txt` **vide** (0 octet, aucune anomalie de contrat),
  suivi à 15:17 d'un contenu identique à celui du 24/10 ;
- l'état initial des onze fichiers : 164 096 `creee`, 172 Mo de JSON Lines,
  7,9 s, 474 Mo de mémoire résidente ;
- une oscillation A → B → A → B rendrait deux fois les mêmes identifiants
  si ceux-ci ne portaient que les empreintes des archives (§0 E).

## Décision

**Schéma v1** (`evenements/schema.py`). Un événement est un objet JSON à
plat, `version_schema = 1`, dont **toutes les valeurs de données sont des
chaînes** normalisées (ADR 0005) : `id`, `entite` (identifiant du catalogue
et du contrat), `fichier`, `version_contrat`, `type` (`creee` | `modifiee` |
`supprimee`), `etat_initial`, `identite` (`cle` | `ligne`), `cle` (colonnes
de la clé déclarée → valeur), `empreinte_ligne`, `rang`, `avant`, `apres`
(objets colonne → valeur, `null` selon le type), `champs_modifies`,
`anomalies` (`{colonne, regle}` de la ligne après, ou avant pour une
`supprimee`), `date_source` (date affichée par la source, `null` pour les
informations importantes), `date_observation` (horodatage de l'archive,
UTC), `archive`, `archive_sha256`, `archive_precedente`,
`archive_precedente_sha256` (chemins relatifs à la racine). Une ligne JSON
par événement : clés triées à tous les niveaux, séparateurs compacts, UTF-8
tel quel. Rien ne vient de l'horloge ni du poste.

**Rien ne dépend de l'ordre d'un objet JSON.** L'identité de ligne et
l'identifiant joignent les valeurs de `cle` dans l'**ordre alphabétique des
noms de colonnes** ; le tri des événements d'une comparaison suit ce même
ordre, et non l'ordre des colonnes du fichier ; le rejeu des événements
compare des objets colonne → valeur. C'est l'ordre que le JSON écrit : un
consommateur qui ne lit que le JSON le retrouve sans le contrat, et un
événement relu est égal à l'événement écrit (contrôle du palier 2).

**Identifiant.** `id` = sha256 de `entite \x1f archive \x1f
archive_precedente \x1f type \x1f identite_de_ligne`, où les deux archives
entrent par leur **chemin relatif** (`""` pour l'état initial) et
`identite_de_ligne` est la clé normalisée (valeurs jointes par `\x1f`,
ordre alphabétique des colonnes) pour `identite = "cle"`, ou `empreinte_ligne
\x1f rang` pour `identite = "ligne"`. Le même à chaque rejeu, différent
pour deux comparaisons même de contenu identique (A → B → A → B), différent
pour deux occurrences d'une même ligne.

**Comparaison** (`evenements/comparaison.py`), sur les valeurs normalisées
du dernier snapshot **retenu** au nouveau, lus avec le contrat courant.
Fichier à clé : `creee`, `supprimee`, `modifiee` avec `champs_modifies`
dans l'ordre du contrat. Fichier **ligne à ligne** : multiensemble des
lignes normalisées (empreinte → occurrences) ; une ligne qui change donne
une `supprimee` puis une `creee`, jamais de `modifiee` ; le `rang` distingue
les occurrences ; `cle` porte les colonnes de la clé déclarée non unique,
pour que le Lot 2 rapproche une `supprimee` et une `creee` de même clé sans
que l'événement l'affirme. Ordre : clé, puis `supprimee` < `modifiee` <
`creee`, puis empreinte, puis rang, **décroissant pour les `supprimee`**
(supprimer le rang r ramène les occurrences à r − 1) et croissant pour les
`creee` (créer le rang r les porte à r) : un consommateur qui suit le flux
dans l'ordre, comme `appliquer`, voit un compte toujours juste, même quand
une ligne perd plusieurs occurrences d'un coup. Une graphie seule (`65 %`),
une espace, un format de date ne produisent rien.

**Premier snapshot.** Une `creee` par entité, `etat_initial = true`, sans
compression : le Lot 2 n'a qu'un chemin, appliquer des événements, et la
propriété « appliquer les événements au vide redonne le dernier snapshot
retenu » se teste sans cas particulier.

**Garde-fou de volume** (`evenements/volume.py`), par fichier, dans l'ordre
des archives, sur les lignes bien formées :

1. **écarté sans appel** : une anomalie bloquante, ou aucune ligne bien
   formée (le vide) ; jamais en attente, jamais confirmé ;
2. **en attente** : moins de 99 % des lignes du dernier retenu (seuil
   `SEUIL_PERTE` = 1 %, cent fois au-dessus des pertes réelles) ;
3. **confirmé** si un passage `inchange` du manifeste revoit son empreinte
   de comparaison entre son archivage et l'archive suivante, **ou** si
   l'archive suivante, ni vide ni bloquante, a au plus 101 % de ses lignes
   (la source maintient la baisse) ; il est alors comparé normalement au
   dernier retenu et devient le dernier retenu ;
4. **écarté** sinon, dès qu'une archive postérieure existe ; en attente tant
   que rien ne la suit.

Un snapshot écarté ou en attente ne produit jamais d'événement ; la
comparaison suivante repart du dernier retenu et porte le cumul. Un vrai
rétrécissement coûte une heure de retard, les événements gardant la
`date_observation` de leur archive. Si une source est un jour vidée ou
abandonnée, rien n'émet des milliers de `supprimee` : un écart est consigné
à chaque passage, et c'est un humain qui tranche (alerte au Lot 5).

**Bilan par archive** (`evenements/bilan.py`), une mesure, jamais une
alerte : lignes, lignes bien formées, entités, occurrences en doublon,
anomalies par règle, graphies des énumérations à `canonique`, décision et
motif, écart avec le dernier retenu (lignes, entités, anomalies en
différence, événements par type). Il ne change pas le code de sortie.

**Sortie par archive et reprise** (`evenements/rejeu.py`,
`pharmaflux evenements`). Chaque archive lue laisse
`evenements/<entite>/<horodatage>__<sha12>.jsonl` quand elle est retenue
ou confirmée (vide quand rien n'a changé), `bilans/<entite>/<même nom>.json`
toujours, puis `etat.json`, dans cet ordre, chaque fichier écrit entier
puis renommé. Le flux d'une source est la concaténation de ses fichiers
dans l'ordre des noms. L'état garde par entité la version du contrat, la
dernière archive traitée, le dernier retenu et le snapshot en attente, par
leurs chemins : **les snapshots ne sont jamais sérialisés**, la reprise les
recalcule depuis leur archive. Un snapshot en attente n'est pas « traité » :
**la dernière archive traitée est la dernière dont le verdict est
définitif** (retenue, confirmée ou écartée), ce qui peut être l'archive en
attente que la dernière archive lue vient de trancher, quand celle-ci passe
à son tour en attente ; sinon la reprise relirait une archive déjà traitée
et effacerait ses événements. Quand une exécution ultérieure tranche un
snapshot en attente, elle réécrit son bilan et écrit ses événements s'il
est confirmé, pour que la sortie égale celle d'un rejeu complet. Un rejeu
complet recalcule tout et repart de zéro pour l'entité : il **retire
d'abord l'entité de `etat.json`** (réécriture atomique), puis efface ses
dossiers, pour qu'une coupure entre les deux laisse une entité sans état,
que `--reprendre` rejoue en entier au lieu de la croire traitée.
`--reprendre` **refuse** quand une version de contrat diffère de celle de l'état
(code 2) : les événements écrits auraient une autre forme que les suivants.
Code de sortie 1 si une archive est illisible ; un snapshot écarté est un
constat, pas une panne. Le dossier de sortie n'est jamais sous la racine de
l'archive.

**Exactitude** (PRD §7.1), en tests : deux rejeux complets identiques à
l'octet ; une reprise après **chaque** point d'arrêt d'une suite de
vingt-deux archives fabriquées (dont une archive en attente tranchée dans
les deux sens, une confirmée par un passage inchangé, deux pertes en attente
qui se suivent, tranchées dans les deux sens par une archive elle-même en
attente, une ligne en triple ramenée à une puis remontée à trois, le retour
A → B → A, l'oscillation, le vide, le bloquant) égale au rejeu complet ;
`--reprendre` sans rien de nouveau ne change pas un octet ;
`etat.json` supprimé puis `--reprendre` ; un rejeu complet interrompu par
une archive illisible en tête, après l'effacement de la sortie, puis
`--reprendre` une fois l'archive lisible ; aucun identifiant en double ;
`appliquer` sur la sortie **relue du disque** redonne le dernier snapshot
retenu.

## Conséquences

- Le Lot 2 ouvre ses lignes SCD2 depuis les `creee` initiales et les
  ferme ou les remplace avec les suivantes ; il n'a jamais à relire le
  bronze avec un contrat.
- Mission 03 : le même JSON devient la valeur d'un message Redpanda, la
  clé du message est `cle` (ou `empreinte_ligne`), le topic est l'entité
  versionnée par `version_schema`, `id` sert à l'idempotence des
  consommateurs, l'état de reprise devient un décalage de consommation. Rien
  dans l'événement n'a à changer.
- Coût : 172 Mo d'état initial sur disque, hors dépôt (`data/`), une fois.
  Mémoire résidente au pic du rejeu complet : 474 Mo à la mission 02 (les
  événements d'une comparaison étaient construits puis sérialisés en mémoire
  avant d'être écrits, 32 439 pour les compositions), près de deux fois les
  256 Mo de l'unité du VPS ; **118 à 143 Mo** depuis la mise à jour du
  27/10/2026 ci-dessous.
- À surveiller : un `inchange` du manifeste ne confirme une archive en
  attente que dans la fenêtre entre son archivage et l'archive suivante ; au
  delà, il compare à l'archive suivante. Un changement de version de contrat
  impose un rejeu complet ; le choix d'une version de contrat par archive
  reste hors périmètre (ADR 0005). La révision du seuil (1 %) se ferait par
  cet ADR, sur mesure.

## Mise à jour du 27/10/2026 — écriture en flux (mission 03, palier 1)

**Décision.** La chaîne n'a plus de structure dont la taille dépend du
nombre d'événements.

- `comparer` rend un **itérateur**. Il construit un squelette par
  événement (type, ligne avant, ligne après, rang, empreinte) avec sa clé
  de tri, la même que `Evenement.cle_de_tri` calculée sur les mêmes
  valeurs ; il trie les squelettes, puis fabrique chaque événement quand
  l'itérateur avance. L'ordre et chaque octet écrit sont ceux d'avant **par
  construction**, et aucun événement n'existe avant d'être écrit ni ne
  survit après.
- `rejeu` sérialise et écrit chaque événement dès qu'il est produit, dans le
  même `.<nom>.jsonl.partiel` renommé à la fin ; un `Resultat` ne porte plus
  ses événements (`evenements()` rappelle la comparaison à la demande), les
  comptes par type sont faits à l'écriture et passés au bilan, et `Suivi` ne
  garde rien de ce qu'il a produit. Chaque archive est traitée dans une
  fonction dont tout meurt au retour : à la lecture de l'archive suivante,
  seuls le dernier retenu et le snapshot en attente sont en mémoire.
- La `Lecture` et le snapshot **partagent les valeurs qui se répètent**
  d'une ligne à l'autre (un statut, un taux, une date, un prix) : un objet
  chaîne par valeur distincte, brute ou normalisée ; le texte décodé meurt
  dès qu'il est découpé en lignes. Le poids d'un snapshot est divisé par
  près de deux (presentations : 26,6 → 14,7 Mo tracés ; compositions : 23,8
  → 12,5).

**Ce qui ne change pas.** Le schéma v1, l'identifiant, l'ordre de tri, la
reprise, `appliquer`, et la sortie : le rejeu complet des onze fichiers de
la copie du Mac donne un `diff -r` vide contre celle du code de la
mission 02 (30 fichiers, 173 Mo).

**Mesures** (copie du Mac, `/usr/bin/time -l`, trois exécutions) : rejeu
complet **474 → 118, 134 et 143 Mo** résidents (7,9 s inchangées) ;
`--reprendre` sans rien à faire 121 → 109 Mo ; `--version` 37 Mo. Le pic
est désormais la lecture de la troisième archive de `bdpm.presentations`,
quand le dernier retenu et le nouveau snapshot coexistent, pas plus la
sérialisation des compositions. Le surplus de mémoire tracée pendant
l'écriture de 20 000 `modifiee` passe de 146 à 6 Mo. `tests/test_memoire.py`
garde la **structure** : sur deux snapshots fabriqués, le surplus pendant
l'écriture reste sous la moitié de leur poids (près de trois fois avant).

**Écartées** : fusionner deux snapshots triés par clé ou émettre clé par
clé (même ordre, mais à démontrer : clé triée par nom de colonne, rangs
décroissants des `supprimee`) ; un tri externe (fichier intermédiaire pour
gagner quelques mégaoctets) ; un seuil absolu en mégaoctets résidents dans
un test (dépend de la machine, de Python et de l'allocateur : les trois
exécutions ci-dessus varient de 25 Mo).

## Options écartées

| Option | Pourquoi pas |
|---|---|
| un seul événement « état initial » qui renvoie à l'archive | chaque consommateur devrait relire le bronze avec le contrat, c'est-à-dire réécrire le normaliseur |
| identifiant sur les empreintes des archives (proposition de l'ordre) | A → B → A → B donnerait deux fois les mêmes identifiants (§0 E) ; les chemins relatifs sont uniques dans le bronze et survivent au rapatriement |
| `modifiee` pour un fichier sans clé unique | il n'y a pas d'identité de ligne ; une `supprimee` puis une `creee` de même `cle` laissent le rapprochement au Lot 2 sans l'affirmer |
| un fichier d'événements par source, en ajout | la reprise devrait se protéger d'une coupure entre les événements et l'état par une troncature ; un fichier par archive rend l'écriture atomique et la reprise lisible sur le disque |
| sérialiser les snapshots dans l'état | l'archive est la source de vérité ; recalculer coûte 2,9 s pour les onze fichiers et rend le changement de contrat gratuit pour un rejeu |
| confirmer une archive en attente par `inchange` seul | une source qui rétrécit vraiment et change à chaque passage ne serait plus jamais retenue |
| `fichier_vide` bloquante, ou vide confirmable | un fichier vide respecte la forme ; le vide n'est pas un changement de la BDPM, c'est une réponse incomplète : écarté sans appel |
| ordre des colonnes du contrat dans l'identifiant et le tri | un événement relu depuis le JSON (clés triées) changeait d'identifiant et de tri ; l'ordre alphabétique se retrouve sans le contrat |
| compresser la sortie | `gzip` écrit une date dans son en-tête et casserait l'identité à l'octet |

## Références

PRD v0.3 §6.3, §7.1 · ordre de mission 02 (§0 C à I ; décisions 3 à 8 ;
addendum 1) · `docs/rapports/mission-02/points-a-trancher.md`, `palier-2.md`,
`palier-3.md` · contrôles des paliers 1 et 2 · ADR 0002, 0003, 0005 ·
`src/pharmaflux/evenements/` · mission 03 : §0 (A, B), addendum 1
(décision 1), `docs/rapports/mission-03/palier-1.md`.
