# Mission 02 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Fable 5.1) · **À :** IeC, beko · **Date :** 26/10/2026
**Branche :** `mission-02-normalisation-et-evenements` · **Ordre lu sur `main`**
(commit `83de6d1`), après `CLAUDE.md`, `docs/agents/processus.md` et le PRD
v0.3.

**Ce que j'ai lu, et comment.** La copie rapatriée `~/pharmaflux-data`
(`PHARMAFLUX_DATA` non posée), en lecture seule : 20 archives, dont 17
fichiers `.txt` (3 de `CIS_CIP_bdpm.txt`, 3 de `CIS_InfoImportantes.txt`,
1 pour chacun des 9 autres), et le manifeste, 582 lignes du 24/10 19:41 au
26/10 16:17 UTC, 20 `nouveau`, 562 `inchange`, 0 erreur. Les mesures : des
scripts jetables qui n'utilisent que la bibliothèque standard et les
modules du projet (`bronze`, `contrats.chargeur`, `contrats.verification`),
passés sur l'entrée standard de `uv run python -`, sans rien écrire dans le
dépôt ni dans l'archive. **Aucune requête réseau**, ni BDPM, ni data.gouv,
ni HAS. Rien n'a été codé.

**Un refus, signalé sans variante.** Pour relire le PDF de documentation
(point B, prix), je l'ai décompressé dans le dossier temporaire de session
(`gunzip -c <archive> > …/m02/pdf/doc_v5.pdf`, passé), puis la commande
documentée dans `docs/donnees/README.md` a été **refusée par le
classificateur du mode auto de Claude Code** (motif affiché : « Code from
External »), pas par le garde-fou du projet :

```bash
uvx --from pdfminer.six==20250506 pdf2txt.py -o /private/tmp/claude-501/-Users-behramko-Postule-folder-Data-Engineer-apply-pharmaflux-codeur/6a06d2c6-7a8c-4511-aa78-b58327201bcd/scratchpad/m02/pdf/doc_v5.txt /private/tmp/claude-501/-Users-behramko-Postule-folder-Data-Engineer-apply-pharmaflux-codeur/6a06d2c6-7a8c-4511-aa78-b58327201bcd/scratchpad/m02/pdf/doc_v5.pdf
```

Je n'ai pas cherché d'autre voie. Le point B.3 s'appuie donc sur ma lecture
du 26/10 consignée au §0 de la mission 01 (tableau A) et dans les
descriptions du contrat `presentations.toml`, plus une vérification
arithmétique faite aujourd'hui sur l'archive.

**Lecture rapide, les constats qui pèsent sur l'ordre :**

1. **L'archive ne contient aucune `modifiee` réelle.** Les deux changements
   de `CIS_CIP_bdpm.txt` sont des suppressions seules : 20 898 → 20 896
   lignes (24/10 19:41 → 23:17 UTC, 2 présentations retirées) puis
   20 896 → 20 895 (26/10 00:17, 1 retirée), les trois en « Déclaration
   d'arrêt de commercialisation » ; 0 création, 0 modification, 0 ligne
   qui ne change que par des blancs. La démonstration de la décision 9
   montrera **3 `supprimee`** et rien d'autre ; les `modifiee`, les
   doublons et le retour A → B → A viendront des fixtures.
2. **Le fichier vide est invisible pour le contrat.** L'archive de 14:17
   (`e3b0c44298fc`, 0 octet) donne 0 ligne et **0 anomalie**, même pas
   bloquante : le garde-fou doit nommer « vide » explicitement (F), et je
   propose une anomalie `fichier_vide` non bloquante pour que `profil` le
   voie aussi (K). Dans le manifeste, le passage suivant (15:17) est un
   `nouveau` à l'empreinte du 24/10 (`a27b30e12c83`, identique à l'octet),
   pas un `inchange` : le snapshot vide n'est jamais confirmé, il reste
   écarté, et 15:17 est identique au dernier retenu. Zéro événement, comme
   voulu. Détail : la réponse vide n'avait **pas d'en-tête
   `Content-Disposition`** (champ `null` dans le manifeste, présent sur les
   deux autres).
3. **L'identifiant proposé en E entre en collision si une source oscille.**
   Deux comparaisons A → B puis, plus tard, A → B (mêmes empreintes) donnent
   les mêmes identifiants. Ce n'est pas théorique : `CIS_InfoImportantes.txt`
   a déjà fait `a27b…` → vide → `a27b…`, et un second passage à vide demain
   referait les mêmes couples. Le chemin d'archive (horodatage + sha, unique
   dans le bronze) doit entrer dans l'identifiant.
4. **La virgule des milliers se vérifie, elle ne se devine pas.** Sur les
   13 125 lignes de la dernière archive dont les trois prix sont conformes,
   prix public = prix + honoraires **sur 13 125**. Sur les 498 lignes à
   virgule des milliers, la lecture `1,003,48` = 1003.48 vérifie la même
   égalité sur **495** ; les 3 autres diffèrent de 2 centimes dans la source
   elle-même (B.3).
5. **Les graphies des taux sont stables** : 0 CIP13 a changé de graphie
   entre les trois archives (2 545 valeurs avec espace sur 13 624 non vides
   dans chacune). Normaliser ne coûtera aucun événement.
6. **Mémoire et volume.** Snapshot de `CIS_COMPO_bdpm.txt` (32 439 lignes) :
   32,5 Mo au total, deux snapshots en mémoire ≈ 65 Mo (A). Les `creee`
   du premier snapshot des onze fichiers : **164 093 événements, 155 Mo de
   JSON Lines** (G).

---

## A. Représentation d'un snapshot normalisé

**Constat (mesuré avec `tracemalloc`, archive `90a6e8ee286b` de
`CIS_COMPO_bdpm.txt`, 2,7 Mo bruts, 32 439 lignes, 5 colonnes de clé).**

| étape | mémoire |
|---|---|
| `verification.verifier` seul (la `Lecture` : tuples de chaînes, anomalies) | 19,5 Mo (pic 29,5 pendant le décodage) |
| + dictionnaire clé → (valeurs brutes, valeurs normalisées) | + 13,0 Mo, **32,5 Mo** au total |
| même chose en partageant l'objet chaîne quand la valeur normalisée est égale à la brute | + 9,3 Mo au lieu de 13,0 |
| durée (lecture, vérification, deux constructions, sous `tracemalloc`) | 2,5 s |

Deux snapshots en mémoire pour une comparaison : ≈ 65 Mo pour le plus
gros fichier, loin du plafond de 256 Mo de l'unité du VPS, et sans objet
sur le Mac.

**Avis : d'accord avec la proposition, avec trois précisions.**

- **Une `Ligne` figée** (`dataclass(frozen=True, slots=True)`) : `numero`
  (ligne dans le fichier, pour citer l'archive), `brutes: tuple[str, ...]`,
  `normalisees: tuple[str, ...]`, `anomalies: tuple[tuple[str, Regle], ...]`
  (colonne, règle). Les tuples bruts sont **ceux de la `Lecture`**, pas une
  copie ; une valeur normalisée identique à la brute est le même objet.
- **Les valeurs normalisées sont des chaînes canoniques**, pas des objets
  Python typés (`date`, `Decimal`). Elles se comparent, se hachent et
  s'écrivent en JSON sans conversion ; le type est dans le contrat. C'est
  aussi ce qui évite de sortir un prix en nombre flottant JSON (D).
- **Fichier à clé** : `dict[tuple[str, ...], Ligne]`, clé = valeurs
  normalisées des colonnes de la clé. **Fichier ligne à ligne** :
  `dict[str, tuple[Ligne, int]]`, empreinte de la ligne normalisée →
  (ligne, nombre d'occurrences), c'est-à-dire un multiensemble. Le snapshot
  porte aussi l'archive (chemin, sha256, horodatage), la version du
  contrat, et son bilan (J).

## B. Ce que la normalisation change

**Règle générale, à écrire dans l'ADR 0005.** Une valeur **conforme**
(`verifier_valeur` rend `None`) prend sa forme canonique ; une valeur
**non conforme** reste brute, et la ligne porte (colonne, règle) ; une
valeur **vide** reste vide (`""`, pas de `null` inventé). La forme
canonique est définie par le type et, quand le type ne suffit pas, par le
contrat. Rien dans le code qui ne soit lisible dans l'un ou l'autre.

| type | conforme → forme canonique | exemple |
|---|---|---|
| `texte` | espaces de tête et de fin retirés (`strip`), intérieur intact | `" BIOGARAN"` → `"BIOGARAN"` (et `espace_parasite` reste consigné) |
| `entier` | entier décimal sans zéro de tête ni `+` | `"01"` → `"1"` (deux colonnes : `numero_liaison`, `numero_tri`) |
| `decimal` | point décimal, **exactement** `decimales` chiffres après, pas de séparateur de milliers | `"12,50"` → `"12.50"`, `"1,003,48"` → `"1003.48"` si le contrat déclare les milliers (B.3) |
| `date` | ISO 8601 `AAAA-MM-JJ`, quel que soit le format du contrat | `"19/01/2026"` et `"20260119"` → `"2026-01-19"` |
| `booleen` | `"true"` / `"false"` (chaînes) | `"Oui"` → `"true"` |
| `enumeration` | la graphie canonique déclarée par le contrat, sinon inchangée | `"65 %"` → `"65%"` (B.1) |
| `code` | inchangé (le motif couvre déjà toute la valeur) | |
| `url` | inchangée | |
| `liste` | chaque élément normalisé selon `de`, même séparateur, même ordre, pas de dédoublonnage | `"65 %;100 %"` → `"65%;100%"` |

Un cas à trancher : **`date_hors_plage`** (51 dates de 1910 à 1949, une en
2924). La valeur se lit sans ambiguïté, la conversion en ISO est une pure
forme, réversible, et l'anomalie dit que la date est invraisemblable, pas
qu'elle est illisible. Avis : la normaliser (`1949-01-19`) **en gardant
l'anomalie**, pour que la colonne reste typable au Lot 2 ; `date_illisible`
reste brute. Si l'IeC préfère la règle stricte « non conforme = brute »,
c'est un `if` de moins, pas un désaccord (question 1).

**B.1 — Taux `65%` / `65 %`.** Constat : 0 CIP13 change de graphie d'une
archive à l'autre (trois archives, 13 624 puis 13 623 valeurs non vides ; seule
différence, `30%` passe de 860 à 859 avec la ligne supprimée du 26/10).
Avis : **une seule forme normalisée, sans espace** (`65%`, la graphie
majoritaire : 11 079 contre 2 545), déclarée dans le contrat et non dans le
code : `presentations.toml` passe en **v1** avec, sur l'énumération des
taux, une table `canonique = { "65 %" = "65%", "100 %" = "100%", "30 %" =
"30%", "15 %" = "15%" }`, et sa raison. Le chargeur vérifie que chaque clé
et chaque valeur de `canonique` sont dans `valeurs`. Un taux qui ne
changerait que de graphie ne produit aucun événement ; le bilan (J) garde
le compte des graphies.

**B.2 — Espaces parasites.** Constat : 15 883 titulaires précédés d'une
espace, 1 133 formes, 1 309 substances avec espace finale, 3 lignes de
`CIS_CIP_bdpm.txt` (dernière archive). Avis : **retirées
dans la valeur normalisée**, la ligne portant `espace_parasite`. Un
`modifiee` dû à une seule espace n'est pas un changement : la comparaison
se fait sur les valeurs normalisées, donc il n'existe pas. Le jour où la
BDPM retire les 15 883 espaces, c'est le bilan qui le dit (`espace_parasite`
15 883 → 0), ce qui est la bonne place : une mesure, pas 15 883 événements.

**B.3 — Prix `1,003,48`.** Constat : je n'ai pas pu relire le PDF
aujourd'hui (refus ci-dessus). D'après ma lecture du 26/10 (§0 de la
mission 01, tableau A, et descriptions du contrat), la documentation §3.2
dit « Prix du médicament en euro », « Prix public en euro, honoraires
compris », « Honoraires de dispensation en euro », sans format ni
séparateur. Mais l'archive, elle, tranche : sur la dernière archive
(`276207db5783`), 13 623 lignes ont leurs trois prix renseignés ;

| lignes | prix public = prix + honoraires |
|---|---|
| 13 125 sans virgule des milliers | **13 125** (0 écart) |
| 498 avec virgule des milliers, lues `1,003,48` = 1003.48 | **495** |

Les 3 écarts sont dans la source : l. 5247 `10,226,20` + `1,02` donne
`10,227,22`, le fichier écrit `10,227,20` (de même l. 5303 et l. 10574,
2 centimes chaque fois). Les 497 prix à plusieurs virgules ont tous la
forme `\d{1,3}(,\d{3})+,\d{2}` (maximum `66,596,25`), et les honoraires
(1,02 à 2,76) ne l'ont jamais. Avis : **ce n'est pas deviner, c'est
déclarer une forme vérifiée**. `presentations.toml` v1 ajoute aux trois
colonnes `decimal` le paramètre `milliers = ","` avec la raison (« la BDPM
écrit les prix ≥ 1 000 € avec une virgule des milliers, 497 lignes le
24/10 ; lecture vérifiée par prix public = prix + honoraires sur 495 des
498 lignes »), le type `decimal` accepte alors `1,003,48` (groupes de trois
chiffres exactement) et le normalise en `1003.48` ; `decimal_illisible`
disparaît pour ces lignes. L'alternative, garder la brute avec l'anomalie,
laisse 995 prix inexploitables au Lot 2 et au Lot 4, précisément les plus
chers. Les 3 écarts de 2 centimes sont une règle métier (cohérence des
trois prix), à mesurer comme l'ordre des dates du profil, pas une règle de
schéma (question 2).

## C. Comparaison et types d'événements

**Avis : d'accord**, sur les valeurs normalisées, avec ces précisions.

- **Fichier à clé** : `creee`, `supprimee`, `modifiee` avec
  `champs_modifies` (noms de colonnes, dans l'ordre du contrat). Deux
  lignes dont seule la graphie change (taux, espace) sont égales : pas
  d'événement. Deux valeurs non conformes différentes (`1,003,48` →
  `1,003,50`, si les milliers n'étaient pas déclarés) sont deux brutes
  différentes : `modifiee`, honnêtement.
- **Fichier ligne à ligne** (SMR, ASMR, Dispo_Spec) : multiensemble des
  lignes normalisées ; une ligne qui change = `supprimee` + `creee` ; pas
  de `modifiee`. Pour relier les deux au Lot 2 : chaque événement porte
  **`cle`** (les colonnes de la clé déclarée non unique : CIS + dossier
  pour SMR et ASMR, CIS + CIP13 + lien pour Dispo_Spec, l'entité « fiche »
  de l'ADR 0003) et **`identite = "ligne"`** (contre `"cle"` pour les
  fichiers à clé), plus `empreinte_ligne` (sha256 de la ligne normalisée).
  Le Lot 2 peut rapprocher une `supprimee` et une `creee` de même `cle`
  dans la même comparaison et le présenter comme « avis remplacé,
  probablement » ; l'événement, lui, ne l'affirme pas.
- **Doublons** (5 lignes × 2 dans Dispo_Spec, 0 dans SMR et ASMR) : un
  compte qui passe de 2 à 1 donne une `supprimee` de rang 2 (E).
- **Ordre des événements d'une comparaison** : par `cle` normalisée, puis
  `supprimee` < `modifiee` < `creee`, puis `empreinte_ligne`, puis rang.
  Déterministe, et pour une même clé la suppression précède la création,
  ce qui est l'ordre qu'un topic partitionné par clé devra garder
  (mission 03).

## D. Contenu d'un événement

**Schéma proposé, `version_schema = 1`**, toutes les valeurs de données en
chaînes (A) :

| champ | type | contenu |
|---|---|---|
| `id` | chaîne, 64 hex | identifiant déterministe (E) |
| `version_schema` | entier | `1` |
| `entite` | chaîne | identifiant du catalogue (`bdpm.presentations`) ; c'est aussi l'identifiant du contrat |
| `fichier` | chaîne | `CIS_CIP_bdpm.txt` |
| `version_contrat` | chaîne | version du contrat qui a lu les deux snapshots (`v0`) |
| `type` | chaîne | `creee`, `modifiee`, `supprimee` |
| `etat_initial` | booléen | vrai pour les `creee` du premier snapshot d'un fichier (G) |
| `identite` | chaîne | `cle` ou `ligne` (C) |
| `cle` | objet colonne → valeur normalisée | les colonnes de la clé déclarée, unique ou non |
| `empreinte_ligne` | chaîne, 64 hex | sha256 de la ligne normalisée après (ou avant pour `supprimee`) |
| `rang` | entier | occurrence dans le multiensemble, `1` sauf doublon |
| `avant` | objet ou `null` | état normalisé avant (`null` pour `creee`) |
| `apres` | objet ou `null` | état normalisé après (`null` pour `supprimee`) |
| `champs_modifies` | liste de chaînes | vide sauf `modifiee` |
| `anomalies` | liste de `{colonne, regle}` | de la ligne après (ou avant pour `supprimee`) ; la valeur brute n'y est pas répétée, elle est dans l'archive citée et, pour une valeur illisible, dans l'état lui-même |
| `date_source` | chaîne `AAAA-MM-JJ` ou `null` | `date_source_affichee` de la ligne de manifeste de l'archive ; `null` pour `CIS_InfoImportantes.txt`, que la page ne date pas (K) |
| `date_observation` | chaîne ISO UTC | horodatage de l'archive (son nom) |
| `archive`, `archive_sha256` | chaînes | chemin relatif à la racine, sha256 complet |
| `archive_precedente`, `archive_precedente_sha256` | chaînes ou `null` | le dernier snapshot retenu ; `null` pour l'état initial |

**Sérialisation** : une ligne JSON par événement, `sort_keys=True`,
`separators=(",", ":")`, `ensure_ascii=False`, UTF-8, `\n`. Aucun champ
qui dépende de l'horloge ou du poste (pas de « produit le », pas de chemin
absolu).

**Format de sortie.** L'ordre propose un fichier par source ; je propose
**un fichier par archive retenue**, `<sortie>/evenements/<entite>/<horodatage>__<sha12>.jsonl`
(vide si la comparaison ne donne rien : la preuve que l'archive a été
traitée), écrit entier puis renommé (`os.replace`). Les snapshots écartés
ou en attente et les bilans vont dans
`<sortie>/bilans/<entite>/<horodatage>__<sha12>.json`, un par archive lue.
Raisons : une écriture atomique par archive, une reprise qui se lit sur le
disque (H), et un flux par source qui reste la concaténation des fichiers
dans l'ordre des noms, ce que les tests de la décision 8 compareront à
l'octet. Si l'IeC tient à un seul fichier par source, l'écriture devient
un ajout en fin de fichier et la reprise doit se protéger d'une coupure
entre les événements et l'état (troncature au dernier décalage connu) :
faisable, moins simple (question 3).

**Ce qui changera avec Redpanda (mission 03).** Le fichier devient un
puits parmi d'autres : le même JSON est la valeur du message ; la clé du
message est `cle` (ou `empreinte_ligne` pour `identite = "ligne"`) ; le
topic est l'entité, versionné par `version_schema` ; `id` sert à
l'idempotence des consommateurs ; l'état de reprise (H) devient un
décalage de consommation ; les bilans et les écartés vont dans un topic à
part ou restent des fichiers. Rien dans le contenu de l'événement n'a à
changer, c'est le but de cette mission.

## E. Identifiant déterministe

**Avis : sha256 d'une chaîne canonique**
`entite \x1f archive \x1f archive_precedente \x1f type \x1f identite_de_ligne`,
où `archive` et `archive_precedente` sont les **chemins relatifs** (donc
horodatage + sha, uniques dans le bronze ; `""` pour l'état initial) et
`identite_de_ligne` est la clé normalisée (colonnes jointes par `\x1f`)
pour un fichier à clé, `empreinte_ligne \x1f rang` pour un fichier ligne à
ligne. Le séparateur `\x1f` (unit separator ASCII) ne peut pas apparaître
dans une valeur de TSV.

Cas limites vérifiés sur le papier :

- **Doublon qui disparaît une fois sur deux** (Dispo_Spec, 5 cas) : les
  deux occurrences ont la même empreinte ; la comparaison des comptes
  (2 → 1) produit une `supprimee` de `rang = 2`, et le retour (1 → 2) une
  `creee` de `rang = 2`. Le rang entre dans l'identifiant : deux
  disparitions successives de la même ligne ont des archives différentes,
  donc des identifiants différents ; deux disparitions dans la même
  comparaison (2 → 0) ont des rangs différents.
- **Retour A → B → A** : les deux comparaisons ont des chemins d'archive
  différents, donc des identifiants différents, même si les deux « A »
  sont identiques à l'octet (c'est le cas réel : 24/10 et 26/10 15:17 ont
  le même sha `a27b30e12c83`).
- **Oscillation A → B → A → B** : avec les seules empreintes (proposition
  de l'ordre), la seconde comparaison A → B reproduirait les identifiants
  de la première ; avec les chemins, non. C'est le constat 3.
- **Deux rejeux** : les chemins, les contrats et les valeurs sont les
  mêmes, donc les identifiants aussi ; un rapatriement conserve les
  chemins relatifs. La décision 8 (aucun identifiant en double sur
  l'ensemble) se teste sur la concaténation de toutes les sorties.

## F. Garde-fou de volume

**Constat sur l'archive.** Pertes réelles observées : −0,010 % et
−0,005 % (`CIS_CIP_bdpm.txt`, 2 puis 1 ligne), puis le cas du 26/10 :
−100 % (10 905 → 0) suivi d'un retour à 10 905. Le fichier vide n'a
**aucune anomalie**, bloquante ou non (constat 2). Dans le manifeste, le
passage qui suit le vide est un `nouveau`, pas un `inchange` : le vide ne
serait jamais confirmé.

**Règle proposée**, par fichier, dans l'ordre des archives :

1. **écarté** : une anomalie bloquante, ou **aucune ligne bien formée**
   (le vide, nommé explicitement : le contrat ne le voit pas) ;
2. **en attente** : moins de (1 − X) × lignes du dernier snapshot retenu ;
3. **confirmé** si, plus tard dans le manifeste, une ligne `inchange` du
   même identifiant revoit son empreinte de comparaison (celle de sa propre
   ligne `nouveau`, retrouvée par `chemin_archive` ; pour les informations
   importantes c'est l'empreinte sur lignes triées, donc un contenu
   regénéré identique confirme) ; **ou** si l'archive suivante du même
   fichier, ni vide ni bloquante, a au plus (1 + X) × ses lignes : la
   source confirme la baisse en la maintenant. Confirmé, il est comparé
   normalement au dernier retenu, puis devient le dernier retenu ;
4. **écarté** sinon, dès qu'une archive postérieure existe sans
   confirmation ; **en attente** tant qu'il n'y a rien après lui (fin du
   manifeste) : rien n'est émis, le résumé le dit, la prochaine exécution
   tranchera.

La seconde condition du point 3 est mon ajout : sans elle, une source qui
rétrécit vraiment et change à chaque passage (jamais servie deux fois à
l'identique) ne serait plus jamais retenue, et la comparaison resterait
bloquée sur un snapshot ancien. Avec elle, un vrai rétrécissement coûte
une heure de retard (le temps d'un `inchange` ou de l'archive suivante),
les événements gardant la `date_observation` de l'archive, et aucun
changement n'est perdu : quand un snapshot en attente est finalement
écarté, la comparaison suivante va du dernier retenu à la nouvelle archive
et porte le cumul. Seul l'état intermédiaire d'une heure est perdu, et il
est consigné comme écarté avec son motif.

**X proposé : 1 %.** Les pertes réelles sont 100 fois en dessous ; le coût
d'une fausse attente est une heure de délai, celui d'un faux retenu est
des milliers de fausses `supprimee` suivies d'autant de `creee`. Une
troncature au milieu d'une ligne est de toute façon bloquante
(`nombre_colonnes`) ; une troncature en fin de ligne doit tomber sous X
pour être vue : à 1 %, il faut qu'elle garde 99 % du fichier pour passer.
Pour `CIS_CIP_Dispo_Spec.txt` (703 lignes), 1 % est 7 lignes : l'ANSM
retire des fiches par poignées, elles attendront une heure, c'est voulu.
Si l'IeC préfère un seuil plus lisible (5 %), rien d'autre ne change
(question 4).

**Enregistrement d'un écarté ou d'un en attente** (dans le bilan de
l'archive, D) : motif lisible (« vide », « bloquante : encodage, ligne
12 », « 20 lignes au lieu de 10 905, perte de 99,8 %, jamais confirmée »),
lignes, lignes du dernier retenu, archive du dernier retenu. Jamais
d'événement. **Cas du 26/10** : 14:17 écarté (vide) ; 15:17 comparé au
24/10, identique, 0 événement, bilan « identique au dernier retenu ».

## G. Premier snapshot

**Constat (dernière archive de chaque fichier, événements construits
selon D avec `sort_keys`, séparateurs compacts).**

| fichier | `creee` initiales | JSON Lines |
|---|---|---|
| `CIS_COMPO_bdpm.txt` | 32 439 | 29,5 Mo |
| `CIS_CPD_bdpm.txt` | 28 532 | 19,9 Mo |
| `CIS_CIP_bdpm.txt` | 20 895 | 22,3 Mo |
| `CIS_bdpm.txt` | 15 883 | 16,1 Mo |
| `CIS_HAS_SMR_bdpm.txt` | 15 547 | 15,5 Mo |
| `CIS_InfoImportantes.txt` | 10 905 | 16,4 Mo (1,5 ko par événement : le texte est une balise `<a>`) |
| `CIS_GENER_bdpm.txt` | 10 737 | 8,5 Mo |
| `HAS_LiensPageCT_bdpm.txt` | 10 480 | 7,4 Mo |
| `CIS_HAS_ASMR_bdpm.txt` | 10 117 | 11,8 Mo |
| `CIS_MITM.txt` | 7 855 | 6,8 Mo |
| `CIS_CIP_Dispo_Spec.txt` | 703 | 0,8 Mo |
| **total** | **164 093** | **155 Mo** (≈ 945 octets par événement) |

**Avis : une `creee` par entité, `etat_initial = true`.** Le Lot 2 n'a
alors qu'un seul chemin, appliquer des événements, et la propriété
« appliquer les événements au vide redonne le dernier snapshot » (décision
8) se teste sans cas particulier. 155 Mo, c'est une fois, sur disque, hors
dépôt (`data/`), et 164 093 messages sont un volume modeste pour un
topic (mission 03). L'alternative, un seul événement « état initial » qui
renvoie à l'archive, oblige chaque consommateur à relire le bronze avec le
contrat, c'est-à-dire à réécrire le normaliseur en aval : non. Pas de
compression de la sortie : `gzip` écrit une date dans son en-tête, ce qui
casserait l'identité à l'octet, sauf à la forcer à zéro ; inutile ici.

## H. Reprise et rejeu

**Avis.** La sortie par archive (D) rend la reprise lisible sur le
disque : une archive est traitée quand son fichier de bilan existe. Un
état minimal `<sortie>/etat.json` évite quand même de parcourir la sortie :
par entité, `derniere_archive_traitee`, `dernier_retenu` (chemin, sha256),
`en_attente` (chemin, lignes) ou `null`, `version_contrat`. Il est réécrit
entier, par fichier temporaire et `os.replace`, **après** les fichiers de
l'archive. Ordre d'écriture : événements, bilan, état. Une coupure entre
deux laisse au pire une archive à retraiter, et le retraitement réécrit
les mêmes octets (rejeu déterministe), donc aucun doublon.

**Reprise** : lire l'état, relister le bronze (`bronze.lister`),
recalculer le snapshot du dernier retenu **depuis son archive** (une
lecture de plus par fichier, 2,5 s pour le plus gros), relire le manifeste
en flux (`manifeste.parcourir`, 582 lignes aujourd'hui), traiter les
archives postérieures à la dernière traitée. Le snapshot retenu n'est
jamais sérialisé : l'archive est sa source de vérité, et c'est ce qui rend
le point I gratuit.

**Test sans dépendre de l'heure.** Rien dans la sortie ne vient de
l'horloge : les dates viennent des noms d'archive et du manifeste, qui sont
des fixtures. Les tests construisent un bronze de synthèse dans `tmp_path`
avec `collecte.archive.ecrire_archive` et `manifeste.ajouter`, à partir des
fixtures TSV existantes (horodatages fixés, 24/10 → 26/10) : par fichier,
une suite d'archives qui couvre création, modification, suppression,
doublon, A → B → A, vide, perte partielle confirmée et non confirmée. Puis :
(1) rejeu complet deux fois, octets identiques ; (2) pour chaque préfixe de
la suite des archives (toutes entités confondues, dans l'ordre des
horodatages), un bronze réduit au préfixe, rejeu complet, puis le bronze
entier et `--reprendre`, comparaison à l'octet de l'arborescence de sortie
avec celle du rejeu complet ; (3) suppression de `etat.json` après un
rejeu, `--reprendre`, mêmes octets (la coupure entre bilan et état) ;
(4) aucun `id` en double ; (5) application des événements au vide, par
entité, égale au dernier snapshot retenu (empreinte des lignes normalisées
triées). Une dizaine d'archives par fichier suffit ; la combinatoire reste
sous la seconde.

## I. Changement de version de contrat

**Avis.** Le snapshot précédent étant **recalculé depuis son archive avec
le contrat courant** (H), les deux côtés d'une comparaison sont toujours
lus avec la même version : un `v1` qui change une forme canonique
(`65 %` → `65%`, `1,003,48` → `1003.48`) ne produit **aucun** événement
parasite, et `version_contrat` dans l'événement dit avec quoi il a été
calculé. Ce qui ne marche pas tout seul, c'est la **reprise** après un
changement de version : les événements déjà écrits ont la forme `v0`, les
suivants auraient la forme `v1`, et la concaténation ne serait plus celle
d'un rejeu complet. Donc : `--reprendre` **refuse** quand la version du
contrat enregistrée dans l'état diffère de la version courante, avec un
message qui demande un rejeu complet (« le contrat bdpm.presentations est
passé de v0 à v1 : relance sans --reprendre »). C'est tout ce qu'il faut
pour ne pas se fermer la porte. Le cas d'un `v1` qui change les colonnes
(vrai changement de format de la BDPM) demandera de choisir la version du
contrat **par archive** (date ou première archive conforme), ce qui est
une évolution du chargeur ; hors de cette mission, noté dans l'ADR 0005.

## J. Reliquats de la mission 01

**`_decoder`** : oui, compter les lignes touchées est utile et peu
coûteux : après l'échec du décodage strict, le texte de substitution est
déjà calculé ; compter les lignes qui contiennent U+FFFD donne le nombre
de lignes touchées (un U+FFFD légitime dans un fichier source est à peu
près impossible, et ce serait une mesure, pas une décision). Le texte de
l'anomalie `encodage` devient « octets e9 illisibles en utf-8, ligne 12,
3 lignes touchées » et le bilan porte le compte. Ça touche
`verification.py` et `profil`, à la marge, au palier 1.

**Bilan par snapshot** : oui, une mesure, pas une alerte. Contenu proposé
(un par archive lue, retenue ou non, D) : archive, sha256, lignes, lignes
bien formées, entités (clés distinctes ou lignes distinctes), occurrences
en doublon, anomalies par règle (compte), graphies par énumération à
`canonique`, décision (retenu, écarté, en attente, confirmé) et motif,
écart avec le dernier retenu (lignes, entités, anomalies par règle en
différence, événements par type). Le compte attendu de l'option (b) de la
mission 01 devient ainsi une différence lisible entre deux bilans, sans
seuil ni tolérance dans un contrat. Code de sortie : inchangé par le bilan.

## K. Autres remarques

1. **Une anomalie `fichier_vide`, non bloquante**, dans `verification` :
   aujourd'hui un fichier de 0 octet passe le contrat sans un mot, et
   `pharmaflux profil` sur l'archive de 14:17 dirait « 0 ligne, conforme ».
   Le garde-fou (F) nomme le vide de toute façon ; l'anomalie le rend
   visible au profil et au bilan. Petit changement de la mission 01,
   palier 1 (question 5).
2. **`date_source` nulle pour `CIS_InfoImportantes.txt`** : la page ne le
   date pas (`date_source_affichee` toujours `null` dans le manifeste). Le
   nom `Content-Disposition` (`CIS_InfoImportantes_20261026151731_bdpm.txt`)
   porte l'heure de **génération**, c'est-à-dire de téléchargement, pas une
   date de publication : je ne le mets pas dans `date_source`.
   `date_observation` est toujours là.
3. **La réponse vide n'avait pas de `Content-Disposition`** (constat 2).
   La collecte est hors périmètre ; c'est un signal gratuit pour le Lot 5
   (ou un futur motif de signalement dans le manifeste), à noter dans le
   rapport, pas à coder ici.
4. **Les trois prix incohérents de 2 centimes** (B.3) : mesure de
   cohérence entre colonnes, de la famille « ordre des dates » du profil ;
   je ne propose pas de l'ajouter dans cette mission.
5. **Découpage du code** : `src/pharmaflux/evenements/` plutôt que
   `normalisation/` (la normalisation n'est qu'une étape du chemin bronze →
   événements) : `snapshot.py` (lecture + normalisation + bilan),
   `comparaison.py`, `volume.py` (garde-fou), `schema.py` (événement,
   identifiant, sérialisation), `rejeu.py` (chaîne, état, reprise), et la
   commande `evenements` dans `cli.py`. Les règles par type vivent dans
   `snapshot.py` et sont citées par l'ADR 0005.
6. **La `Lecture` suffit** : `verifier` garde toutes les lignes bien
   formées avec leur numéro ; le snapshot les prend telles quelles, sans
   seconde lecture (décision 1 tenue sans effort). Temps total d'une
   vérification des onze derniers fichiers : quelques secondes.
7. **Fixtures** : les TSV de `tests/fixtures/bdpm/` (40 lignes réelles +
   lignes choisies) sont la matière des archives fabriquées ; chaque
   variante fabriquée sera décrite dans `tests/fixtures/README.md` comme
   telle, à côté des lignes réelles, comme l'addendum 1 de la mission 01 le
   demandait.
8. **`data/` est déjà ignoré** par git (`.gitignore`, avec `*.gz`) :
   la sortie par défaut `data/evenements/` n'y entrera pas.

## Questions pour l'IeC

1. **Dates hors plage** : normalisées en ISO avec l'anomalie (mon avis) ou
   brutes ?
2. **Prix** : `presentations.toml` v1 avec `milliers = ","` sur les trois
   colonnes `decimal`, lecture vérifiée par l'égalité des prix (mon avis),
   ou brutes avec `decimal_illisible` ? Et le `canonique` des taux dans la
   même v1 (B.1) ?
3. **Sortie** : un fichier d'événements et un bilan **par archive** (mon
   avis), ou un fichier par source ?
4. **X = 1 %**, avec la confirmation par `inchange` **ou** par l'archive
   suivante dans la même proportion (mon ajout) ?
5. **`fichier_vide`**, anomalie non bloquante dans `verification` (touche
   le profil, à la marge) ?
6. **`--reprendre` refusé** quand une version de contrat a changé depuis
   l'état enregistré (mon avis), ou reprise avec mélange de versions
   annoncé dans l'événement ?
7. **Valeurs toutes en chaînes** dans l'événement (dates ISO, décimaux à
   point, booléens `"true"`/`"false"`), le typage restant au contrat : mon
   avis, pour qu'aucun prix ne devienne un flottant JSON. D'accord ?

## Propositions d'évolution

Aucune sur les chemins réservés. Pour beko : le refus signalé en tête vient
du classificateur du mode auto, pas du garde-fou du dépôt ; si la relecture
du PDF est utile à l'addendum, elle se refait avec la commande ci-dessus
depuis une session qui en a la permission.
