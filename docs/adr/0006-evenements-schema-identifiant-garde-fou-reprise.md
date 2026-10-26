# ADR-0006 — Événements : schéma v1, identifiant par chemins d'archive, comparaison ligne à ligne, garde-fou de volume, premier snapshot, reprise

**Statut :** accepté · **Date :** 2026-10-26 · **Mission :** 02
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
`creee`, puis empreinte, puis rang. Une graphie seule (`65 %`), une espace,
un format de date ne produisent rien.

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
recalcule depuis leur archive. Un snapshot en attente n'est pas « traité »
(la dernière archive traitée reste avant lui) ; quand une exécution
ultérieure le tranche, elle réécrit son bilan et écrit ses événements s'il
est confirmé, pour que la sortie égale celle d'un rejeu complet. Un rejeu
complet recalcule tout et repart de zéro pour l'entité. `--reprendre`
**refuse** quand une version de contrat diffère de celle de l'état
(code 2) : les événements écrits auraient une autre forme que les suivants.
Code de sortie 1 si une archive est illisible ; un snapshot écarté est un
constat, pas une panne. Le dossier de sortie n'est jamais sous la racine de
l'archive.

**Exactitude** (PRD §7.1), en tests : deux rejeux complets identiques à
l'octet ; une reprise après **chaque** point d'arrêt d'une suite de treize
archives fabriquées (dont une archive en attente tranchée dans les deux
sens, une confirmée par un passage inchangé à la fin du bronze, le retour
A → B → A, l'oscillation, le vide, le bloquant) égale au rejeu complet ;
`etat.json` supprimé puis `--reprendre` ; aucun identifiant en double ;
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
- Coût : 172 Mo d'état initial sur disque, hors dépôt (`data/`), une fois ;
  474 Mo de mémoire résidente au pic (les événements d'une comparaison sont
  construits en mémoire avant d'être écrits, 32 439 pour les compositions) ;
  loin des 256 Mo de l'unité du VPS si la chaîne devait y tourner : à
  revoir en flux avant un déploiement, ce que la mission 03 décidera.
- À surveiller : un `inchange` du manifeste ne confirme une archive en
  attente que dans la fenêtre entre son archivage et l'archive suivante ; au
  delà, il compare à l'archive suivante. Un changement de version de contrat
  impose un rejeu complet ; le choix d'une version de contrat par archive
  reste hors périmètre (ADR 0005). La révision du seuil (1 %) se ferait par
  cet ADR, sur mesure.

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
`src/pharmaflux/evenements/`.
