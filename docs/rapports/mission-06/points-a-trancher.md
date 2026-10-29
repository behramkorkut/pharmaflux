# Mission 06 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Opus 5.5) · **À :** IeC, beko · **Date :** 29/10/2026
**Branche :** `mission-06-gold-et-qualite` (sommet `aedf134`, identique à
`main`) · **Ordre lu sur `main`** (`aedf134`), après `CLAUDE.md`,
`docs/agents/processus.md`, le PRD v0.7 (§2, §4 Lot 2, §6.1 à 6.5, §7.1, §9,
annexes A et B) et les ADR 0002, 0003 et 0009.

**Ce que j'ai lu, et comment.** Le code utile au gold : `contrats/`
(`modele.py`, `normalisation.py`, `verification.py`, les onze contrats),
`silver/` (`schema.py`, `etat.py`, `sql.py`, `entrepot.py`),
`evaluation/` (`questions.py`, `verification.py`) et le jeu
`evaluation/questions-reference-v0.toml`, le `Makefile`. Les mesures : dans le
dossier temporaire de la session, `pharmaflux evenements --racine
demo/archive`, puis `pharmaflux silver construire` (9,9 s, 295 Mo résidents),
puis trois scripts de mesure hors dépôt, lancés avec `uv run python -I`, qui
lisent ce silver par l'API du dépôt (`Entrepot`, `etat_a`,
`connexion_verrouillee`) et maquettent le typage, la fiche et la
disponibilité. Mémoire : `/usr/bin/time -l` (résident maximal du
processus) et `getrusage` entre les étapes. **Aucune commande `docker`,
`colima` ni `make`, aucune requête vers les sources, rien d'écrit dans le
dépôt (hors ce fichier), dans `data/` ni dans `~/pharmaflux-data`, aucun refus
du garde-fou. Rien n'a été codé** : les scripts sont des brouillons de
mesure.

Sauf mention contraire, les chiffres sont l'**état du jeu à sa dernière
observation**, `2026-10-27T00:17:12Z` (164 086 versions valides, onze
entités).

**Lecture rapide, les constats qui pèsent sur l'ordre :**

1. **Une seule valeur illisible dans tout l'état du jeu** :
   `specialites.numero_autorisation_europeenne` = `EU/1/17/1235/`
   (CIS 61096104, `code_illisible`). Les 18 383 autres anomalies sont de
   forme (espace parasite, date hors plage) : leur valeur canonique se type.
2. **Le gold à la demande est rapide** : l'état des onze tables 0,12 s, le
   typage 0,10 s, la fiche médicament de tout le jeu 0,10 s ; le processus
   entier, imports compris, 1,4 à 1,7 s.
3. **La mémoire tranche la technique de la fiche** : faite en SQL DuckDB
   (onze jointures, `list(struct) … ORDER BY`), elle monte à **552 à 705 Mo**
   résidents selon le nombre de fils, au-dessus du seuil de 512 Mo ; faite en
   PyArrow (tri, décalages, `take`), **318 Mo**. Je propose PyArrow pour les
   vues, DuckDB pour le SQL libre et les contrôles (point K).
4. **La fiche ne peut pas être une ligne plate par CIS** : 63 CIS sont dans
   plusieurs groupes génériques, un CIS a jusqu'à 37 présentations et 44 avis
   SMR, 12 dossiers HAS ont plusieurs liens. Il faut des `list<struct>`.
5. **5 562 CIS sont cités ailleurs et absents de `CIS_bdpm.txt`** (2 470 par
   les génériques, 2 938 par les SMR, 1 662 par les ASMR, 1 138 par les
   informations importantes, 23 par la disponibilité, 4 par les
   présentations). Je propose une fiche partielle marquée (point D).
6. **849 présentations sont couvertes par expansion** d'une ligne sans
   CIP13, 36 par une ligne directe, aucune par les deux. Mais **23 CIS
   signalés n'ont aucune présentation** dans le référentiel : une vue « par
   présentation » stricte perdrait leurs signalements (point E).
7. **Les SMR et ASMR n'ont pas d'identifiant d'indication** : « le plus
   récent par indication » ne se calcule pas sans deviner l'indication dans
   le libellé. Je propose tous les avis, datés et triés (point D).
8. **Le silver ne sait pas quand une version a été confirmée pour la
   dernière fois** : une archive retenue sans changement ne laisse aucune
   trace. La date qu'une fiche peut citer est celle de la version (sa source,
   son ouverture), pas celle du dernier fichier qui l'a reconduite (point L.1).
9. **`fin_validite` ne doit pas sortir du gold** : à un instant passé, elle
   dit ce qu'on a appris *après* cet instant (point C).

## A. Le typage

**Le principe.** Le typage part de la valeur du silver (canonique, ou brute)
**et de ses anomalies**, jamais de la valeur seule :

1. valeur vide → typée vide (nulle) ;
2. la version porte, pour cette colonne, une règle de **lisibilité**
   (`REGLES_DE_LISIBILITE` de `normalisation.py` : `entier_illisible`,
   `decimal_illisible`, `date_illisible`, `booleen_inconnu`,
   `valeur_inconnue`, `code_illisible`, `url_illisible`) → typée vide : la
   valeur est brute, on ne la relit pas ;
3. sinon, la valeur est canonique (PRD §6.2) et se convertit par une règle
   **stricte sur la forme canonique** (tableau ci-dessous).

Pourquoi les anomalies et pas un simple essai de conversion : une brute
illisible peut avoir l'air canonique. Un prix écrit `12.50` dans la source
est illisible pour le contrat (virgule attendue), il voyage brut, et un
`CAST` le lirait comme 12,50 € : ce serait deviner. Sur le jeu, la seule
valeur illisible n'a pas cette forme, mais la règle doit tenir pour la
prochaine.

Une valeur **sans** règle de lisibilité que la règle stricte refuse ne vient
pas de la source : c'est une rupture de l'invariant du silver (forme
canonique garantie). Elle n'est pas typée vide en silence : elle est comptée
par un contrôle **bloquant** (G, contrôle 3). 0 sur le jeu.

| type du contrat | type Arrow | conversion depuis la forme canonique |
|---|---|---|
| `texte` | `string` | telle quelle (déjà sans espaces de tête ni de fin) |
| `code` | `string` | telle quelle ; un CIS ou un CIP13 reste une chaîne (identifiant, pas un nombre) |
| `url` | `string` | telle quelle |
| `enumeration` | `string` | telle quelle (la graphie canonique) |
| `entier` | `int64` | `-?[0-9]+` sans zéro de tête, puis entier |
| `decimal` | `decimal128(18, d)`, `d` = `decimales` du contrat (2 partout) | `-?[0-9]+\.[0-9]{d}`, puis décimal exact |
| `date` | `date32` | `AAAA-MM-JJ` qui existe au calendrier |
| `booleen` | `bool` | `true` → vrai, `false` → faux |
| `liste` | `list<T>`, `T` le type de `de` | découpe sur le `separateur` du contrat, chaque élément typé selon `de` ; un élément illisible rend toute la liste vide |

**Les décimaux : `decimal128(18, 2)`, pas `float64`.** Un prix reste exact
(`1,16` → `1.16`, jamais `1.1600000000000001`), se somme sans dérive et se
compare à l'égalité, ce que les questions de remboursement demandent.
Précision 18 : DuckDB la range sur 64 bits, et elle tient
9 999 999 999 999 999,99 ; le plus grand prix du jeu est 66 597,27 € (cinq
chiffres entiers). L'échelle vient du contrat, pas du code.

**Les listes.** La forme canonique garde le séparateur du contrat (`;` pour
les trois listes) et l'ordre de la source, sans dédoublonnage
(`normaliser_valeur`) : la découpe est sans ambiguïté, aucun élément ne
contient `;`. `list<string>` suffit pour les trois (leurs éléments sont
`enumeration` ou `texte`). Sur le jeu :
- `taux_remboursement` : 13 621 valeurs, **toutes à un seul élément**
  (`65%` 10 851, `100%` 1 252, `30%` 1 145, `15%` 369, `35%` 4), 7 267
  vides ; une liste quand même, puisque le contrat le dit ;
- `voies_administration` : 15 883 valeurs, de 1 à 8 éléments (2 201 en ont
  plusieurs), 68 voies distinctes ;
- `titulaires` : 15 883 valeurs, toutes à un élément, 666 titulaires.

Une valeur vide donne une liste **nulle**, pas une liste vide : la source ne
dit pas « aucun taux », elle ne dit rien.

**Les énumérations : `string`, pas `dictionary`.** Le gold est calculé à la
demande (point B) : rien n'est stocké, le gain de place ne joue pas, et le
Parquet du silver dictionne déjà. Un `dictionary` complique les
concaténations Arrow et le passage à DuckDB pour 21 000 lignes au plus. Les
énumérations du jeu ont de 2 à 12 valeurs distinctes.

**Les dates : `date32`**, y compris les 52 dates de déclaration de
commercialisation hors plage (1910-1949, 2924) : elles se lisent, la règle
`date_hors_plage` reste dans `anomalies`, et le contrôle de forme les compte
(G, contrôle 13).

**Les valeurs illisibles par colonne, état à la dernière observation** :

| entité | colonne | règle | nombre |
|---|---|---|---|
| `specialites` | `numero_autorisation_europeenne` | `code_illisible` | 1 (`EU/1/17/1235/`, motif `EU/\d/\d{2}/\d+`) |
| les dix autres | — | — | 0 |

Anomalies de forme (typées, comptées à part) : `specialites.titulaires`
espace parasite 15 883 et `forme_pharmaceutique` 1 133 ;
`compositions.denomination_substance` 1 288, `reference_dosage` 11,
`dosage` 9, `designation_element` 1 ; `conditions_prescription.condition`
3 ; `presentations.date_declaration_commercialisation` date hors plage 52,
`libelle_presentation` espace parasite 3.

**Questions A.**
- A.1 D'accord pour typer depuis les anomalies, et pour un contrôle bloquant
  sur une valeur canonique non typable ?
- A.2 Une `valeur_inconnue` d'énumération donne une colonne typée vide (la
  règle de l'ordre). Or un statut de disponibilité nouveau est « le premier
  signe d'un changement de format » (ADR 0002) : dans la vue de
  disponibilité, il deviendrait une ligne au statut vide. Je propose de le
  laisser vide **et** de porter dans chaque vue une colonne
  `colonnes_illisibles` (`list<string>`) qui nomme les colonnes vidées, pour
  qu'un vide se distingue d'une absence. D'accord ?

## B. La forme du gold : calculé à la demande

**Avis : d'accord avec l'IeC, aucune table gold stockée.** Mesures (Mac
arm64, maquette, 2026-10-27T00:17:12Z ; même ordre de grandeur à
2026-10-24T20:00:00Z) :

| étape | temps | résident maximal cumulé |
|---|---|---|
| imports (PyArrow, PyIceberg, DuckDB) | — | 120 Mo |
| état des onze tables à l'instant (`etat_a`) | 0,12 s | 282 Mo |
| typage des onze tables | 0,10 s | 304 Mo |
| fiche médicament, tout le jeu (PyArrow) | 0,10 s | 318 Mo |
| disponibilité courante (maquette DuckDB) | 0,03 s | — |
| processus entier | 1,4 à 1,7 s | 318 Mo (PyArrow) ; 552 à 705 Mo (fiche en DuckDB) |

La fiche fait 21 445 lignes et 31 Mo en Arrow. À ces volumes, matérialiser
ne gagne rien de visible.

**Ce qu'une matérialisation (une table Iceberg du gold courant) apporterait** :
une lecture directe par le Lot 3 sans recalcul, et un instantané comparable
d'une exécution à l'autre. **Ce qu'elle coûterait** : une écriture de plus
par lot du silver, un état à garder synchrone (un silver qui avance laisse
une fiche périmée tant qu'elle n'est pas recalculée), et surtout « l'état à
une date » perdu pour le gold, sauf à historiser le gold lui-même, ce que le
PRD exclut (§6.5 : pas d'histoire propre). **Pour qu'elle reste juste**, il
faudrait la recalculer entière à chaque commit du silver et y écrire
l'instant et le dernier snapshot du silver qu'elle reflète, pour refuser une
lecture désynchronisée : du travail pour rien aujourd'hui. Si le Lot 3 a
besoin de fiches en fichier, une commande d'export à un instant
(`gold fiche --tout --format jsonl`) suffit, sans état à tenir.

## C. Les colonnes typées par entité

**Noms.** Le nom court du silver (`presentations`, `specialites`…), sans
préfixe, dans les commandes `gold` seulement : `gold sql` enregistre les onze
entités typées sous ces noms, à l'instant de `--a`, plus les vues métier.
`silver sql` ne change pas. Un préfixe (`gold_presentations`) ne servirait
que si silver et gold devaient vivre dans la même connexion ; ce n'est pas
le cas, et l'instant fixé à l'ouverture de `gold sql` change déjà le sens
des tables. En Python : `gold.typage.etat_type(entrepot, entite, instant)`.

**Colonnes.** Les colonnes du contrat, typées, dans son ordre, puis les
colonnes de version utiles à une réponse datée et sourcée :

| colonne | gardée | pourquoi |
|---|---|---|
| `identite` | oui | l'identité de la ligne ; pour les trois fichiers sans clé unique, `<empreinte>#<rang>` distingue deux lignes identiques |
| `rang` | oui | idem, lisible |
| `date_source` | oui | la date de la source portée par la version (licence BDPM : citer la date) |
| `debut_validite` | oui | « connu depuis » : l'instant où la version a été observée |
| `archive_ouverture` | oui | le chemin de l'archive qui l'a apportée : la source exacte |
| `version_contrat` | oui | la grille de lecture |
| `anomalies` | oui | explique une colonne typée vide (`list<struct<colonne, regle>>`) |
| `fin_validite`, `id_fermeture`, `archive_fermeture` | **non** | à un instant passé, la fin est postérieure à l'instant : la garder, c'est répondre avec ce qu'on ne savait pas encore |
| `empreinte_ligne`, `id_ouverture`, `etat_initial` | non | utiles à l'audit du silver, pas à une réponse ; `silver etat` les donne |

**Les trois fichiers sans clé unique** (disponibilité, SMR, ASMR) : une
ligne par version valide, comme le fichier, doublons compris. La
disponibilité a 703 lignes, dont 5 doublons exacts (rang 1). Les SMR et ASMR
n'en ont aucun. Le dédoublonnage se fait dans les vues métier, avec un
compte d'occurrences (points D et E), jamais dans la colonne typée.

**Question C.1** : d'accord pour écarter `fin_validite` du gold ?

## D. La fiche médicament

**Grain : une ligne par CIS.** **Univers : tout CIS connu à l'instant**,
c'est-à-dire cité par au moins une des dix entités qui portent `code_cis`,
avec `dans_referentiel` (vrai si le CIS est dans `CIS_bdpm.txt`). Sur le
jeu : 21 445 fiches, dont 15 883 dans le référentiel et **5 562
partielles**. Pourquoi des fiches partielles : l'annexe B prévoit la
« réponse avec réserve » (un avis SMR d'un CIS sorti de la base se donne,
en disant que le référentiel ne le connaît pas), et le Lot 3 indexe des
fiches ; sans fiche, ces 5 562 CIS seraient invisibles pour lui. Une fiche
partielle n'a que les sections que les fichiers lui donnent, et le dit.

**Colonnes** (une colonne plate quand l'entité a au plus une ligne par CIS,
une `list<struct>` sinon ; les champs gardent leur type du point A) :

| colonne | type | depuis |
|---|---|---|
| `code_cis`, `dans_referentiel` | `string`, `bool` | univers |
| `denomination`, `forme_pharmaceutique`, `voies_administration`, `statut_amm`, `type_procedure_amm`, `etat_commercialisation`, `date_amm`, `statut_bdm`, `numero_autorisation_europeenne`, `titulaires`, `surveillance_renforcee` | plates | `specialites` (clé CIS) |
| `mitm` | `bool` | présence dans `CIS_MITM.txt` (un drapeau par CIS, profil mission 01) ; faux si absent |
| `code_atc`, `date_publication_mitm` | plates | `mitm` ; le code ATC n'existe que là dans la BDPM |
| `presentations` | `list<struct<code_cip13, code_cip7, libelle_presentation, statut_administratif, etat_commercialisation, date_declaration_commercialisation, agrement_collectivites, taux_remboursement, prix_medicament, prix_public, honoraires_dispensation, indications_remboursement>>`, triée par CIP13 | `presentations` |
| `composition` | `list<struct<designation_element, code_substance, denomination_substance, dosage, reference_dosage, nature_composant, numero_liaison>>`, triée par élément, liaison, nature | `compositions` |
| `groupes_generiques` | `list<struct<identifiant_groupe, libelle_groupe, type_generique, numero_tri>>`, triée par groupe | `generiques` (63 CIS dans plusieurs groupes) |
| `conditions_prescription` | `list<string>`, triée | `conditions_prescription` |
| `avis_smr` | `list<struct<code_dossier_has, motif_evaluation, date_avis, valeur_smr, libelle_smr, liens_avis list<string>, occurrences>>`, triée par date décroissante puis dossier | `smr` × `liens_ct` |
| `avis_asmr` | idem avec `valeur_asmr`, `libelle_asmr` | `asmr` × `liens_ct` |
| `disponibilite` | `list<struct<code_cip13, code_statut, libelle_statut, date_debut, date_mise_a_jour, date_remise_a_disposition, lien_ansm, portee, occurrences>>` | `disponibilite` : les lignes de signalement du CIS, non dépliées (`portee` = `presentation` ou `specialite`) |
| `infos_importantes` | `list<struct<date_debut, date_fin, texte_et_lien>>`, en cours à l'instant | `infos_importantes` |
| `provenance` | `list<struct<entite, fichier, date_source, connu_depuis>>` | une entrée par entité qui contribue à la fiche : la plus récente `date_source` et le plus récent `debut_validite` de ses versions |
| `instant` | `timestamp` UTC | l'instant demandé |

**Les avis SMR et ASMR : tous, pas « le plus récent par indication ».**
Les fichiers n'ont pas d'identifiant d'indication : un couple
(CIS, dossier) a jusqu'à 8 lignes (une par indication), et rien d'autre que
le libellé, un texte libre, ne dit de quelle indication il s'agit. Choisir
« le plus récent par indication » obligerait à deviner l'indication dans ce
texte. Tous les avis, chacun avec sa date, triés du plus récent au plus
ancien, laissent la lecture au Lot 3, qui cite. Sur le jeu : jusqu'à 44
avis SMR par CIS.

**Les liens vers les avis** : `liens_ct` est unique par (dossier, lien),
mais 12 dossiers ont plusieurs liens, d'où `liens_avis list<string>`. 1 023
dossiers SMR sur 7 574 et 1 352 dossiers ASMR sur 6 019 n'ont aucun lien
(liste nulle, comptée en G).

**Ce qui sert au Lot 3.** La fiche se transforme en texte de façon
déterministe (PRD §6.7) parce que chaque section est ordonnée de façon
stable et que la `provenance` donne, par fichier, la source et ses dates.
Le rendu texte lui-même est du Lot 3 ; je propose d'écrire dès cette mission
un rendu `--format texte` de `gold fiche` pour un CIS, lisible par un humain
(c'est aussi le premier exemple du README), sans engager le format des
fragments du Lot 3.

**Questions D.**
- D.1 Fiches partielles (5 562, marquées) plutôt que pas de fiche ?
- D.2 « En cours » pour une information importante : `date_debut <= jour
  <= date_fin`, bornes incluses, où `jour` est la date **UTC** de l'instant ?
  Sur le jeu, les 10 905 lignes sont en cours à la dernière observation ; la
  date de Paris ne diffère que entre 22 h et minuit UTC, mais la règle doit
  être écrite.

## E. La disponibilité courante

**Grain : une ligne par (présentation, ligne de signalement distincte)**,
plus une ligne par présentation sans signalement, plus une ligne par
signalement qui ne vise aucune présentation connue. Le grain « fiche ANSM »
ne suffit pas : la ligne de BEFIZAL L.P. (CIS 62119207) apparaît deux fois
sur la **même** fiche avec deux statuts (4 et 2). Le grain « présentation »
seul obligerait à résumer plusieurs statuts en un, donc à en dire plus que
l'ANSM.

| colonne | sens |
|---|---|
| `code_cis`, `code_cip13`, `libelle_presentation`, `denomination` | la présentation visée (et sa spécialité) |
| `etat_signalement` | `declare` (une ligne en cours), `fin_de_publication` (la dernière ligne de cette présentation a été retirée du fichier avant l'instant, ADR 0003), `aucun_signalement` |
| `code_statut`, `libelle_statut`, `date_debut`, `date_mise_a_jour`, `date_remise_a_disposition`, `lien_ansm` | la ligne de signalement, typée ; vides pour `aucun_signalement` |
| `portee` | `presentation` (la ligne cite ce CIP13) ou `specialite` (ligne sans CIP13, dépliée sur toutes les présentations de la spécialité) : la colonne qui marque l'expansion |
| `occurrences` | nombre de lignes identiques dans le fichier (2 pour les 5 doublons, 1 sinon) |
| `presentation_connue` | faux quand la ligne vise un CIP13 ou un CIS sans présentation au référentiel |
| `fin_publication` | pour `fin_de_publication` : l'instant où la ligne a disparu, avec son dernier statut |
| `date_source`, `connu_depuis`, `colonnes_illisibles` | comme en C et A.2 |

**« Aucun signalement » n'est pas « remise à disposition ».** Le statut 4
est un statut déclaré (`declare`, code 4, daté) ; `aucun_signalement` dit
seulement que le fichier ne cite pas la présentation ; `fin_de_publication`
dit que l'ANSM a cessé de publier la fiche, sans en déduire de remise (ADR
0003, « la fiche n'est plus publiée par l'ANSM depuis le <date> »). Ce
dernier état se lit dans l'histoire du silver (une version de disponibilité
fermée avant l'instant, et aucune ouverte ensuite pour la même présentation).
Sur le jeu, le fichier de disponibilité n'a qu'une archive : 0
`fin_de_publication` ; le test se fera sur une fixture.

**Chiffres du jeu** (dernière observation ; vue maquettée) :

| mesure | nombre |
|---|---|
| lignes du fichier / sans CIP13 / fiches ANSM | 703 / 667 / 290 |
| présentations couvertes (au moins une ligne `declare`) | 885 |
| dont par expansion seulement / directe seulement / les deux | **849** / 36 / 0 |
| présentations visées par plusieurs fiches / plusieurs statuts | 4 / 2 |
| doublons exacts (même ligne deux fois) | 5, sur des fiches « spécialités à base de propranolol 40 mg » |
| signalements sans présentation connue | 24 lignes : 23 CIS sans présentation (tous hors référentiel), 1 CIP13 inconnu (3400957382070, CIS 62924833) |
| présentations sans signalement | 20 004 |
| lignes de la vue | 20 918 |

**Questions E.**
- E.1 D'accord avec le grain et avec `fin_de_publication` comme troisième
  état ?
- E.2 Un arrêt **annoncé** (`date_debut` postérieure à l'instant : 1 ligne
  sur le jeu, CIS 66890524 au 01/07/2027, la question `historique-005`)
  reste `declare`, avec son statut et sa date. Faut-il une colonne
  `debut_a_venir` (comparaison de deux dates, sans interprétation) pour que
  le Lot 3 ne dise pas « arrêté » ? Je la propose ; elle n'ajoute rien que
  la source ne dise.

## F. Les alternatives

**Avis : une troisième vue, petite, sans recommandation.** Grain : une
ligne par (groupe générique, présentation d'une spécialité du groupe), avec
le groupe (`identifiant_groupe`, `libelle_groupe`), la spécialité
(`code_cis`, `denomination`, `type_generique`, `numero_tri`), la
présentation (`code_cip13`, `libelle_presentation`, `etat_commercialisation`,
`statut_administratif`) et la disponibilité de la présentation (les
colonnes de E, une ligne par signalement). Sur le jeu : 12 153 lignes avant
disponibilité, 1 535 groupes qui ont au moins une présentation, jusqu'à 69
présentations par groupe ; les 2 470 CIS de génériques hors référentiel n'y
ont pas de présentation et restent dans la fiche.

Pourquoi une vue plutôt qu'une requête laissée au lecteur : la jointure
groupe × présentations × disponibilité porte l'expansion des lignes sans
CIP13 et les trois états de E, qu'il ne faut écrire qu'une fois. « Les
alternatives de X » est alors un filtre sur le groupe de X, X exclu. Elle
ne trie que par `numero_tri`, l'ordre que donne la BDPM, et ne classe rien :
pas de « meilleure alternative », pas de filtre implicite sur la
commercialisation ou la disponibilité.

**Question F.1** : vue `alternatives` à ce grain, retenue ?

## G. Les contrôles de qualité

**La règle qui classe.** **Bloquant** : un invariant que la chaîne
garantit elle-même (contrats, garde-fou de volume, SCD2, normalisation) ;
s'il tombe, c'est notre code ou notre silver qui est faux, et rien de ce que
le gold affiche n'est sûr. **Mesuré** : un fait de la source, que le gold
doit montrer et ne peut pas corriger ; une source publique ne fait pas
tomber la chaîne. Un mesuré s'affiche toujours, même à 0, avec son chiffre.

| # | contrôle | requête (à l'instant) | classe | jeu |
|---|---|---|---|---|
| 1 | unicité des clés déclarées uniques | huit entités : `count(*) − count(distinct clé)` | bloquant (un snapshot à clé non unique est écarté entier : un doublon ici vient du silver) | 0 partout |
| 2 | une version par identité | `identite` unique à l'instant, onze entités (couvre aussi les trois fichiers sans clé) | bloquant (invariant SCD2) | 0 |
| 3 | valeur canonique non typable | valeur sans règle de lisibilité que la règle stricte de A refuse | bloquant (invariant de la normalisation) | 0 |
| 4 | entité vide | aucune version après sa première observation | bloquant (le garde-fou de volume écarte un snapshot vide) | 0 |
| 5 | présentations dont le CIS est absent des spécialités | `presentations` anti-jointure `specialites` | mesuré | **4** présentations, 4 CIS |
| 6 | CIS des autres fichiers absents des spécialités | par entité, `count(distinct code_cis)` anti-jointure | mesuré | génériques 2 470, SMR 2 938, ASMR 1 662, infos 1 138, disponibilité 23, compositions 0, conditions 0, MITM 0 ; union 5 562 |
| 7 | spécialités sans présentation | anti-jointure inverse | mesuré | 1 268 |
| 8 | CIP13 de disponibilité absent des présentations | idem | mesuré | 1 |
| 9 | signalements sans présentation connue | lignes sans CIP13 dont le CIS n'a aucune présentation | mesuré | 23 CIS |
| 10 | dossiers SMR / ASMR sans lien vers l'avis | anti-jointure `liens_ct` | mesuré | 1 023 / 1 352 |
| 11 | lignes répétées des fichiers sans clé | `count(*) − count(distinct empreinte_ligne)` | mesuré | disponibilité 5, SMR 0, ASMR 0 |
| 12 | valeurs illisibles, par colonne | règles de lisibilité dans `anomalies` | mesuré | 1 (`specialites.numero_autorisation_europeenne`) |
| 13 | anomalies de forme, par colonne | règles de forme dans `anomalies` | mesuré | 18 383 (détail en A) |
| 14 | volumes par entité | lignes à l'instant, et écart à l'état de la **précédente observation de l'entité** (en lignes et en %) | mesuré | voir ci-dessous |

**Les volumes : comparés à quoi.** Pas aux bilans : le gold ne lit que le
silver, et `silver verifier` compare déjà l'état aux bilans archive par
archive. Pas à une plage écrite à la main : elle vieillirait avec la base.
Je propose le volume à l'instant et son écart à l'état juste avant la
dernière observation de l'entité qui précède l'instant : c'est le signal
« ce fichier a perdu 3 % de ses lignes au dernier changement », que le
garde-fou n'autorise qu'après confirmation. Le seul volume bloquant est le
vide (contrôle 4). Sur le jeu : `presentations` 20 888 (−7, −0,03 % au
27/10 ; 10 de moins qu'à l'état initial, en trois changements), les dix autres à leur état initial (asmr 10 117, compositions
32 439, conditions 28 532, disponibilité 703, génériques 10 737, infos
10 905, liens 10 480, MITM 7 855, SMR 15 547, spécialités 15 883).

**« Référentiel CIS ↔ CIP13 cohérent » (PRD Lot 2)** se lit par les
contrôles 1 (CIP13 unique), 5, 7 et 8 ; s'y ajoute le CIP7 unique (0
doublon sur le jeu), que je range en mesuré (le contrat ne le déclare pas
clé).

**Aucun contrôle bloquant ne tombe sur le jeu.**

**Question G.1** : le contrôle 5 est mesuré selon ma règle (4 sur le jeu :
la BDPM publie ces présentations). Le PRD (Lot 2) en fait un contrôle
automatique sans dire s'il bloque : le classer bloquant ferait échouer la
démo sur une donnée publique. Je le laisse mesuré, sauf avis contraire.

## H. Les questions depuis le gold

**Le calcul.** Pour chaque question qui a un attendu : l'instant est
l'horodatage de son archive citée (le nom `AAAAMMJJThhmmssZ`, comme
`silver verifier`) ; les lignes attendues, **brutes**, passent par
`normaliser_valeur` (le type du contrat de la colonne), puis par le typage de
A ; la clé de la question est traitée de même. Le gold rend, à l'instant,
les lignes de l'entité qui portent la clé, projetées sur les colonnes ; les
deux ensembles se comparent **en valeurs typées** (un `65 %` attendu et un
`65%` canonique sont le même `["65%"]` ; `25/06/2026` et `2026-06-25` la
même `date32`). Une brute attendue illisible se compare en typée vide, et
la valeur brute du silver doit alors être égale à l'attendue.

**L'ordre.** Le bronze compare dans l'ordre du fichier ; le gold ne connaît
pas cet ordre (une version garde son identité, pas sa ligne). La
comparaison gold se fait **en multiensemble** (lignes triées, occurrences
comptées). La vérification depuis le bronze garde son ordre : les deux
calculs se complètent.

**Les routes.** Une question passe par la vue qui sert le Lot 3 quand sa clé
s'y prête, sinon par les colonnes typées :

| route | questions | nombre |
|---|---|---|
| fiche médicament, par CIS | disponibilite-001 à 005, alternatives-002 à 004, avis_has-001, 002, 003, 005, historique-001, 002, 004, 005 | 16 |
| fiche médicament, par CIP13 (dans `presentations`) | remboursement-001 à 005, historique-003 | 6 |
| vue `alternatives`, par groupe | alternatives-001, 005 | 2 |
| colonnes typées (`liens_ct`, par dossier) | avis_has-004 | 1 |

Soit **24 par une vue métier, 1 par les colonnes typées**. Les deux
abstentions à attendu vide (disponibilite-005, avis_has-005) vérifient
qu'aucune fiche de ce CIS n'est `dans_referentiel`. Les signalements d'une
fiche ne sont pas dépliés et portent `occurrences` : la comparaison redéplie
les occurrences, pour garder la multiplicité du fichier. Si l'IeC préfère
une seule route, les colonnes typées couvrent les 25 ; mais alors les vues
ne sont vérifiées que par leurs tests.

**Fenêtre.** Une question dont l'instant est avant la première observation
de son entité, ou après la dernière observation du silver, est « non
calculable depuis le gold » (annexe B). La borne haute n'est pas parfaite :
une archive retenue sans changement après le dernier événement est dans la
fenêtre, mais le silver ne le sait pas (L.1). Sur le jeu, les 25 sont dans
la fenêtre.

**La sortie.** Une option : `pharmaflux questions verifier --racine
demo/archive --entrepot data/demo/lakehouse`. Sans `--entrepot`, rien ne
change (code 1 sur un écart au bronze, comme aujourd'hui). Avec, chaque
question a ses deux verdicts sur sa ligne (`bronze`, `gold`, route), et une
discordance affiche les deux lignes calculées. Codes : 1 si un attendu
diffère du bronze (inchangé), **2** si un calcul gold diffère, ou n'a pas
pu se faire pour une question calculable depuis le bronze.

**Questions H.**
- H.1 Les routes par les vues (24 + 1) plutôt que les colonnes typées seules ?
- H.2 Avec `--entrepot`, une question « non calculable depuis le gold »
  fait-elle sortir en 2 ? Je propose oui : l'option demande les deux
  calculs, en rendre un seul n'est pas concorder. Sans l'option, pas de
  changement.

## I. Les commandes

Un groupe `pharmaflux gold`, sur le modèle de `silver` : `--entrepot`
(défaut `data/lakehouse`), `--a` (les trois formes de `silver etat` ; défaut
la dernière observation du silver, dite sur la sortie d'erreur), imports
paresseux, code 2 sur un refus.

| commande | ce qu'elle rend | formats |
|---|---|---|
| `gold etat --entite E [--ou col=val] [--colonnes …]` | l'état typé d'une entité | `jsonl` (défaut), `tableau`, `csv` |
| `gold fiche (--cis X \| --tout)` | la fiche d'un CIS, ou toutes | `jsonl`, `texte` (un CIS) |
| `gold disponibilite [--cis X \| --cip13 Y]` | la disponibilité courante | `jsonl`, `tableau`, `csv` |
| `gold alternatives (--cip13 Y \| --cis X \| --groupe G)` | les présentations du ou des groupes | idem |
| `gold qualite` | les quatorze contrôles, un par ligne, puis le résumé ; code 2 si un bloquant tombe | `tableau` (défaut), `jsonl` |
| `gold sql "SELECT …"` | du SQL libre sur les onze entités typées et les trois vues, à l'instant | `jsonl`, `tableau`, `csv` |

**Le SQL : une commande à part**, qui réutilise `connexion_verrouillee`
et `executer` de `silver/sql.py` sans les modifier. Mettre les vues gold
dans `silver sql` mêlerait deux mondes : le silver y est l'histoire entière,
le gold un instant ; les mêmes noms y désigneraient deux choses. Un JSON de
`decimal128` sort en chaîne (`"1.16"`), pour ne pas repasser par un
flottant ; une date en `AAAA-MM-JJ`.

**Question I.1** : les noms et la séparation `silver sql` / `gold sql`
conviennent-ils ?

## J. `Makefile` et CI

**`make gold`**, après `make silver`, sur le silver de la démo :

```make
gold:
	$(PHARMAFLUX) gold qualite --entrepot $(ENTREPOT_DEMO)
	$(PHARMAFLUX) questions verifier --racine $(JEU) --entrepot $(ENTREPOT_DEMO)
```

Le nom `gold` plutôt que `qualite` : la cible montre le gold entier
(contrôles et questions), comme `silver` montre le silver. Une cible de
confort `make fiche CIS=… A=…`, sur le modèle de `make etat`, pour le
premier exemple du README. **CI** : une étape « make gold » dans le job
`integration`, juste après « make silver » ; le job `verifier` ne change pas.
**Durée estimée : 5 à 10 s** (deux processus de 1,5 à 3 s chacun, imports
compris ; `questions verifier` depuis le bronze prend 1,1 s aujourd'hui).

## K. La mémoire

| calcul | résident maximal |
|---|---|
| imports seuls | 120 Mo |
| état typé des onze tables | 304 Mo |
| fiche en PyArrow (tri, décalages de liste, `take` par index) | **318 Mo** |
| fiche en DuckDB, 8 fils (défaut du Mac) / 4 / 2 / 1 | **705 / 600 / 573 / 552 Mo** |
| fiche en DuckDB avec `memory_limit = 256MB` | échec (hors mémoire : pas de débordement sur disque, l'accès aux fichiers est coupé) |
| contrôles de qualité en DuckDB (maquette des requêtes de G) | 364 Mo |
| `gold sql` sur la fiche (dépliage d'un CIS) | 334 Mo |

**Avis.** Les vues (fiche, disponibilité, alternatives) se construisent en
**PyArrow** : tri par clé, `run_end_encode` pour les décalages de liste,
`ListArray.from_arrays`, puis `take` sur l'index de l'univers des CIS ;
l'agrégation `hash_list` de PyArrow refuse les `struct`, et ses jointures
refusent les colonnes `list`, d'où la jointure par index. DuckDB garde ce
qu'il fait bien et à petit coût ici : les contrôles (agrégats simples) et
`gold sql`. Toutes les commandes `gold` mesurées restent sous 512 Mo ; je
les mesurerai à chaque palier, comme à la mission 05.

## L. Autre

1. **La date que cite une fiche.** `date_source` est celle de la version,
   donc de l'archive qui l'a ouverte : une présentation inchangée depuis le
   24/10 cite la source du 23/10, même si le fichier a été republié trois
   fois depuis. La date de la dernière republication est dans les bilans de
   `evenements`, pas dans le silver, et le gold ne lit que le silver. Je
   propose de dire honnêtement dans la fiche « valeur observée depuis
   `connu_depuis`, source du `date_source` », et de proposer pour plus tard
   (Lot 3) la date du dernier fichier retenu par entité, à mettre au silver
   (une propriété de table, par exemple) : hors périmètre ici, puisque le
   silver ne change pas.
2. **`CIS_InfoImportantes.txt` n'a pas de `date_source`** (fichier généré à
   la demande) : sa `provenance` n'a que `connu_depuis`.
3. **Le taux de remboursement reste une chaîne** (`65%`), parce que le
   contrat dit énumération. Le Lot 4 voudra un nombre : ce sera une
   colonne dérivée documentée, ou une nouvelle version du contrat, pas un
   typage du gold.
4. **Le libellé des codes** (`type_generique` 0 à 4, `code_statut` 1 à 4) :
   la documentation BDPM les définit, mais aucun contrat ne les porte. Le
   gold garde le code ; la disponibilité a déjà son libellé dans le fichier.
   Les ajouter serait une nouvelle version de contrat.
5. **La non-régression sur la copie du Mac** : `questions verifier --entrepot`
   n'a de sens que sur un silver de la même archive. Je propose de lancer
   la commande sans `--entrepot` sur `~/pharmaflux-data`, comme aujourd'hui,
   et de ne faire le calcul gold que sur le jeu de démo (la copie du Mac
   était encore le jeu de démo à la mission 05 ; je le revérifierai au
   palier 1).
6. **Les tests** réutilisent la fixture de session de la mission 05 qui
   construit le silver du jeu une fois ; le gold n'ajoute que ses calculs
   (une à deux secondes par instant). Les tests sur fixtures partent d'un
   silver construit par `silver construire` sur `tests/fixtures/`, auquel
   j'ajouterai une archive de disponibilité où une ligne disparaît (pour
   `fin_de_publication`), une valeur illisible et une ligne sans CIP13 sur
   une spécialité à plusieurs présentations.
7. **Dépendances** : aucune. Le verrou ne bouge pas, donc les plafonds de
   `constraint-dependencies` (ADR 0009) ne sont pas à remonter dans cette
   mission.
8. **Le fuseau d'un « jour »** : un `date32` n'a pas de fuseau, l'instant
   est en UTC. Partout où le gold compare une date de la source à l'instant
   (infos importantes en cours, D.2 ; arrêt annoncé, E.2), il prend la date
   UTC de l'instant ; à écrire dans l'ADR 0010.

**Rien n'a été codé. J'attends l'addendum.**
