# ADR-0005 — Normalisation : une forme canonique par type, écrite dans le contrat ou ici, jamais cachée dans le code

**Statut :** accepté · **Date :** 2026-10-26 · **Mission :** 02
**Remplace / remplacé par :** — · complète l'ADR 0002 (`canonique`, `milliers`)

## Contexte

La détection des changements (mission 02) compare deux archives d'un même
fichier. Comparer les chaînes brutes produirait des événements qui ne sont
pas des changements : `65 %` contre `65%`, ` BIOGARAN` contre `BIOGARAN`,
et laisserait 995 prix par archive illisibles (`1,466,29`,
`decimal_illisible` avec le contrat v0). Le PRD §6.2 interdit de deviner :
la normalisation doit changer la **forme**, jamais le **sens**, et être
lisible dans le contrat ou dans un ADR. Mesures du §0 de la mission 02, sur
la copie du Mac (lecture seule, aucune requête réseau) :

- taux : 2 545 valeurs avec espace sur 13 624 ; **aucun** CIP13 ne change
  de graphie d'une archive à l'autre sur les trois archives du 24 et du
  26/10/2026 ;
- prix : 497 prix et 498 prix publics ont la forme `\d{1,3}(,\d{3})+,\d{2}`
  (maximum `66,596,25`), jamais les honoraires ; prix public = prix +
  honoraires sur les **13 125** lignes sans séparateur et sur **495 des
  498** lignes avec, les 3 écarts (2 centimes) étant dans la source ;
- mémoire : un snapshot de `CIS_COMPO_bdpm.txt` (32 439 lignes) tient en
  32,5 Mo, deux en mémoire en 65 Mo, loin des 256 Mo de l'unité du VPS ;
- fichier vide du 26/10 à 14:17 (0 octet) : aucune anomalie avec le
  contrat v0, donc invisible au profil.

## Décision

**Une valeur conforme prend sa forme canonique ; une valeur que le type ne
sait pas lire reste brute, avec sa règle ; une valeur vide reste vide.**
Les formes canoniques sont des **chaînes** : elles se comparent, se hachent
et s'écrivent en JSON sans conversion ; le type reste dans le contrat. Le
code est `contrats/normalisation.py` (`normaliser_valeur`), utilisé par le
snapshot (`evenements/snapshot.py`) et par les bornes du profil.

**Forme canonique par type** (ADR 0002 pour les types) :

| type | forme canonique | exemple |
|---|---|---|
| `texte` | espaces de tête et de fin retirés, intérieur intact | ` BIOGARAN` → `BIOGARAN` |
| `entier` | sans zéro de tête ni signe inutile | `007` → `7` |
| `decimal` | point décimal, exactement `decimales` chiffres après, sans séparateur de milliers ni zéro de tête ; le signe reste dès qu'un chiffre n'est pas nul, `-0,00` devient `0.00` | `12,50` → `12.50` ; `-0,50` → `-0.50` ; `1,003,48` → `1003.48` si `milliers` |
| `date` | ISO 8601 `AAAA-MM-JJ`, quel que soit le format du contrat | `19/01/2026`, `20260119` → `2026-01-19` |
| `booleen` | `true` / `false` | `Oui` → `true` |
| `enumeration` | la graphie de la table `canonique` du contrat, sinon telle quelle | `65 %` → `65%` |
| `code`, `url` | inchangés | |
| `liste` | chaque élément selon `de`, même séparateur, même ordre, pas de dédoublonnage | `65 %;100 %` → `65%;100%` |

**Partage règle par règle.** Ce qui décide, c'est ce que dit l'anomalie :

| règle | sorte | valeur normalisée |
|---|---|---|
| `entier_illisible`, `decimal_illisible`, `date_illisible`, `booleen_inconnu`, `valeur_inconnue`, `code_illisible`, `url_illisible` | lisibilité : le type ne lit pas la valeur | **brute**, règle consignée |
| `espace_parasite`, `longueur_depassee`, `date_hors_plage`, `hote_inconnu` | forme ou vraisemblance : la valeur se lit | **canonique**, règle consignée |
| `valeur_manquante` | porte sur la colonne, pas sur le type | vide reste `""` |
| les règles de ligne et de fichier (`encodage`, `fin_de_ligne`, `nombre_colonnes`, `cle_non_unique`, `retour_final`, `ligne_vide`, `ligne_dupliquee`, `fichier_vide`) | sans valeur à normaliser | — |

Une liste est normalisée élément par élément : `65 %;45%` donne `65%;45%`
avec `valeur_inconnue`. Une date de 1910 ou de 2924 devient ISO et garde
`date_hors_plage` : la colonne reste typable, l'invraisemblance reste dite.

**Contrat v1 : deux paramètres de type, chacun avec sa raison dans le
contrat.** Le chargeur admet `v0` et `v1` ; un paramètre de la v1 dans un
contrat `v0` est refusé, la v0 reste figée sur l'archive du 24/10/2026.

- `milliers = "<caractère>"` sur un `decimal` : la partie entière peut
  s'écrire par groupes de trois chiffres ASCII (`[0-9]{1,3}(?:<m>[0-9]{3})+`),
  la virgule restant le séparateur décimal ; forme canonique sans séparateur.
  Un seul caractère, ni chiffre, ni `-`, ni `.`. Déclaré sur les trois prix
  de `presentations.toml`. Ce n'est pas deviner : la lecture est vérifiée
  par une contrainte interne mesurée (prix public = prix + honoraires,
  ci-dessus). Les 3 écarts de 2 centimes sont une règle métier, à mesurer
  au Lot 2, pas une règle de schéma.
- `canonique = { "<graphie>" = "<graphie canonique>" }` sur une
  `enumeration` : chaque clé et chaque valeur sont dans `valeurs`, une clé
  ne renvoie pas à elle-même, une valeur n'est jamais une clé (pas de
  chaîne), la table n'est pas vide. Déclaré sur les taux de
  `presentations.toml` (`65 %` → `65%`…), graphie majoritaire sans espace.

**Snapshot normalisé** (`evenements/snapshot.py`). Une archive est lue une
seule fois par `contrats.verification` ; chaque ligne bien formée devient
une `Ligne` figée (numéro, brutes, normalisées, anomalies) dont le tuple
brut est **celui de la `Lecture`**, et dont chaque valeur inchangée est le
même objet chaîne. Un fichier à clé déclarée unique est un dictionnaire clé
normalisée → ligne ; un fichier sans clé unique (SMR, ASMR, Dispo_Spec) est
un multiensemble empreinte de la ligne normalisée (sha256 des valeurs
jointes par `\x1f`) → (ligne, occurrences). Une anomalie **bloquante** rend
un snapshot **écarté** avec son motif, jamais une exception. Une clé
**normalisée** qui se répète alors que les clés brutes sont distinctes
(`" X"` et `"X"`, `01` et `1` : aucune bloquante brute) écarte aussi le
snapshot, avec un motif qui la nomme (« clé normalisée non unique : 1
clé(s), 2 lignes, première ligne 812 ») : un fichier à clé dont la clé est
ambiguë ne se compare pas, et aucune ligne ne doit se perdre en silence
(contrôle du palier 1). Le snapshot
porte l'archive (chemin relatif, sha256, horodatage), la version du contrat
et son **bilan** : lignes, lignes bien formées, entités, occurrences en
doublon, anomalies par règle, graphies par colonne à `canonique`.

**`fichier_vide`**, anomalie **non bloquante** de la vérification : un
fichier sans aucune ligne non vide respecte la forme, et le contrat le dit
désormais (visible au profil et au bilan). La décision d'écarter un snapshot
vide appartient au garde-fou de volume (ADR 0006).

**Version de contrat.** Les deux côtés d'une comparaison sont lus avec le
contrat courant. Le choix d'une version de contrat par archive est hors de
la mission 02 ; il sera repris si une v2 change la lecture d'une colonne.

## Conséquences

- Un `modifiee` dû à une espace, à une graphie de taux ou au format d'une
  date n'existe pas : la comparaison se fait sur les valeurs normalisées. Le
  jour où la BDPM retire ses 15 883 espaces ou ses espaces de taux, c'est le
  **bilan** qui le dit (`espace_parasite` 15 883 → 0, graphies), pas des
  milliers d'événements.
- Les 995 prix par archive deviennent lisibles pour le Lot 2 et le Lot 4,
  précisément les plus chers ; le profil ne signale plus `decimal_illisible`
  sur `CIS_CIP_bdpm.txt` (995 → 0, seule différence de non-régression).
- Coût : une seconde vérification de chaque valeur (`verifier_valeur` dans
  la normalisation) ; 2,7 s pour les onze dernières archives, pic 38 Mo.
- À surveiller : une nouvelle graphie de taux ou un prix hors des deux
  formes apparaît comme `valeur_inconnue` ou `decimal_illisible` dans le
  bilan et dans le profil, et appelle une nouvelle version du contrat. Un
  type dont la forme canonique perdrait de l'information (un décimal arrondi,
  une date sans jour) demanderait un nouvel ADR : ici, toute normalisation
  est réversible depuis la brute, qui reste dans la `Ligne`.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| « non conforme = brute », sans partage | une date de 1949 lue et convertie n'est pas illisible ; la règle stricte aurait laissé des dates en deux formats dans la même colonne |
| valeurs normalisées typées (`date`, `Decimal`) | un prix deviendrait un flottant JSON à la sérialisation ; les chaînes se comparent et se hachent sans conversion, le type reste au contrat |
| garder `1,003,48` brut avec `decimal_illisible` | 995 prix inexploitables par archive, les plus chers, alors que l'égalité des prix vérifie la lecture |
| déduire la virgule des milliers dans le code, sans paramètre | la règle doit être lisible dans le contrat, avec sa raison, et refusable pour un autre fichier |
| une forme canonique des taux dans le code (`"65 %" → "65%"`) | même raison : c'est une donnée du contrat, versionnée |
| normaliser une liste en bloc (brute entière si un élément est illisible) | un élément illisible ne dit rien des autres ; élément par élément garde l'information |
| `fichier_vide` bloquante | un fichier vide respecte la forme déclarée ; écarter est une décision de volume, pas de schéma |

## Références

PRD v0.3 §6.2 · ordre de mission 02 (§0 A, B, J, K ; décisions 1, 2 ;
addendum 1) · `docs/rapports/mission-02/points-a-trancher.md` et
`palier-1.md` · ADR 0002 · `src/pharmaflux/contrats/normalisation.py`,
`src/pharmaflux/evenements/snapshot.py`, `src/pharmaflux/contrats/bdpm/presentations.toml`.
