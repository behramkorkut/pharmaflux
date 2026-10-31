# Jeu de démo : `demo/archive`, deux parties figées

Le jeu a **deux parties figées**, chacune avec son manifeste, que
`pharmaflux demo verifier` contrôle ensemble :
- **la BDPM** (mission 04), décrite d'abord : `manifeste/collecte.jsonl` et
  `bronze/bdpm/`. Elle n'a pas changé d'un octet depuis : un test
  (`tests/test_demo_has.py`) le vérifie contre le commit `beba0c8` ;
- **les pages d'avis de la HAS** (mission 09), décrites
  [plus bas](#les-pages-davis-de-la-has-mission-09) :
  `manifeste/has-pages.jsonl` et `bronze/has/pages/`.

La partie BDPM est une archive Pharmaflux comme les autres (`bronze/…`, `manifeste/collecte.jsonl`),
reprise **à l'octet** de la collecte réelle du 24 au 27 octobre 2026, coupée
à un passage et réduite aux onze fichiers TSV de la BDPM que `pharmaflux
evenements` lit. Toute commande qui prend `--racine` marche dessus :
`etat`, `profil`, `questions verifier`, `evenements`, `verifier-bus --racine`,
et le rejeu accéléré de la démonstration (`make demo`, mission 04).

C'est, avec les fixtures des tests, la **seule donnée admise dans le dépôt**
(`CLAUDE.md`, « Données ») : elle vient de services publics, elle ne contient
rien de personnel, chaque partie est figée (une partie ne se met pas à jour :
une autre serait un autre jeu) et `pharmaflux demo verifier` la contrôle sur
un clone neuf. Dans `.gitignore`, `*.gz` reste exclu partout sauf sous
`demo/archive/bronze/`.

## Source et licence

- **Source** : Base de données publique des médicaments (BDPM), ministère
  chargé de la santé et ANSM, page de téléchargement
  <https://base-donnees-publique.medicaments.gouv.fr/telechargement>, fichiers
  servis sous `/download/file/<nom>` (champ `url` de chaque ligne du manifeste).
- **Licence** : les fichiers de la BDPM se réutilisent avec citation de la
  source et de sa date, sans altération (`README.md` du dépôt, « Licences des
  données »). Ici, rien n'est altéré : chaque archive est le fichier reçu,
  compressé par le collecteur, et son `sha256` est consigné dans le manifeste.
  La date affichée par la BDPM pour chaque fichier est dans la table ci-dessous
  (`date_source_affichee` du manifeste).
- **Collecteur** : `pharmaflux collecte`, passage horaire sur le VPS-1, versions
  `0.1.0+a8aa07b` à `0.1.0+07c77a6` (commits de ce dépôt, champ
  `version_collecteur`).

## Fabrication

Le 27 octobre 2026, depuis la copie de l'archive rapatriée sur le poste de
travail (`~/pharmaflux-data`, lecture seule), par la commande du projet, jamais
à la main :

```bash
uv run pharmaflux demo fabriquer --racine ~/pharmaflux-data --destination demo/archive --jusqu-au-passage 20261027T151708Z
```

Elle lit le manifeste en flux, garde les lignes des onze entités dont le
`passage_id` est antérieur ou égal à la coupure, copie telles quelles les
archives citées par les lignes `nouveau` et écrit le manifeste filtré octet
pour octet (toutes les lignes, `inchange` compris, aucun champ retiré). Elle
refuse une destination non vide et n'écrit jamais dans la racine.

## Ce que le jeu contient

**22 archives**, **11 entités**, **781 lignes** de manifeste (22 `nouveau`,
759 `inchange`, aucune erreur), **71 passages** de collecte, du passage
`20261024T194141Z` au passage `20261027T151708Z` (UTC, 27 octobre à 15 h 17)
**inclus**. La coupure est la fin de la copie rapatriée : les deux derniers
passages (14 h 17 et 15 h 17) sont des passages inchangés, qui disent que le
fichier des informations importantes est resté complet après l'alternance du
matin.

| mesure | valeur |
|---|---|
| archives `.txt.gz` (compressées) | 6 223 606 octets |
| les mêmes, décompressées | 59 138 184 octets |
| `manifeste/collecte.jsonl` | 615 459 octets |

Cinq archives de `CIS_InfoImportantes.txt` ont le même contenu (même sha256)
et cinq fichiers `.gz` différents : le collecteur écrit l'horodatage de la
collecte dans l'en-tête gzip. Le jeu reste à l'octet, git fait un delta.

**Ce qui reste dehors**, avec leurs lignes de manifeste : la page de
téléchargement `telechargement.html` (son contenu change à chaque réponse),
le PDF de documentation de la BDPM et les métadonnées Open Medic de
data.gouv.fr. `evenements` ne les lit pas, et sans leurs lignes chaque archive
citée par le manifeste du jeu existe. `pharmaflux etat --racine demo/archive`
y voit donc onze fichiers.

## Ce que le jeu montre

- **L'état initial** du 24 octobre à 19 h 41 : les onze fichiers archivés en
  vingt-cinq secondes, 164 096 événements `creee`.
- **Des changements réels de `CIS_CIP_bdpm.txt`** (présentations) : le 24
  octobre à 23 h 17 (2 `supprimee`), le 26 à 00 h 17 (1), le 27 à 00 h 17 (7).
- **Le garde-fou de volume** : `CIS_InfoImportantes.txt` servi **vide** le 26
  octobre à 14 h 17 et le 27 à 08 h 17, 10 h 17 et 12 h 17 (snapshots écartés
  sans appel, aucune `supprimee`), puis complet à 15 h 17, 09 h 17, 11 h 17 et
  13 h 17 (retenus, identiques au dernier retenu : un fichier d'événements
  vide, pas de second état initial).
- **Les passages sans archive** : 759 lignes `inchange`, un passage par heure.

Il ne montre pas : d'événement `modifiee` ni de `creee` après l'état initial
(aucun sur la période), de snapshot en attente ou confirmé (ADR 0006), de
ligne de manifeste en erreur, de réponse HTTP 304.

## Vérifier le jeu

```bash
uv run pharmaflux demo verifier
```

Vérifie que le manifeste se lit et est dans l'ordre des passages, qu'aucune
ligne n'est en erreur, que chaque ligne `nouveau` cite une archive présente
dont le nom porte le début du sha256 et dont les octets décompressés ont ce
sha256 et la taille consignée, et que rien d'autre n'est dans le dossier.
`tests/test_demo.py` rejoue cette vérification et relit la table ci-dessous
contre le manifeste : chaque sha256 doit être celui de sa ligne `nouveau`, les
nombres ci-dessus aussi.

## Les 22 archives

Dans l'ordre du manifeste. `octets` : taille décompressée ; `date affichée` :
la date que la page de la BDPM annonçait pour le fichier (absente pour
`CIS_InfoImportantes.txt`).

| passage (UTC) | fichier | date affichée | octets | sha256 |
|---|---|---|---|---|
| 20261024T194141Z | `CIS_bdpm.txt` | 2026-09-29 | 3 175 357 | `332b95926f76f1a2ab3d70cdf64205397fc13e74b7cc9afad9b625fbb6961640` |
| 20261024T194141Z | `CIS_CIP_bdpm.txt` | 2026-10-23 | 4 148 805 | `99759e97dd0125e056adec387c0ee81b350e25eca562b95b860a247a424fe8be` |
| 20261024T194141Z | `CIS_COMPO_bdpm.txt` | 2026-09-29 | 2 735 840 | `90a6e8ee286b6245c3938dd417ac75d1135a61b15ba50cfad70ee6b3bd181b7a` |
| 20261024T194141Z | `CIS_HAS_SMR_bdpm.txt` | 2026-09-29 | 4 630 126 | `c2215af6b20705bb8b8eb6f447ebb2a45000c40e5cd8d3f575149832c639ffdd` |
| 20261024T194141Z | `CIS_HAS_ASMR_bdpm.txt` | 2026-09-29 | 4 605 173 | `f849554030c7dafdaf9ccf604dcdb8393590302f7a28f869a71a3fd798ae0a69` |
| 20261024T194141Z | `HAS_LiensPageCT_bdpm.txt` | 2026-09-29 | 517 390 | `2f01ff1e13f8431434d545d1c567368276223b7a5d9c5612fc423f4353c54a2b` |
| 20261024T194141Z | `CIS_GENER_bdpm.txt` | 2026-09-29 | 1 219 514 | `04ea92fb3d2e7682ed0720daea48ecf65f3459b4b0b61fe9160bb7cce82f152c` |
| 20261024T194141Z | `CIS_CPD_bdpm.txt` | 2026-09-29 | 1 336 246 | `e92ca48f83f54f6e2bca7248d3e8c24d7399402fd6b5b9058c41ad730529c237` |
| 20261024T194141Z | `CIS_CIP_Dispo_Spec.txt` | 2026-10-21 | 153 497 | `43b7d2f3cfe699fffded55893472d9fa17fd77964c5e3a31d4017160b8d35ed6` |
| 20261024T194141Z | `CIS_MITM.txt` | 2026-10-13 | 1 618 769 | `300f24c39e84466c617eedce9edfd491870259fd5abd2092b3f8296a3b6245fa` |
| 20261024T194141Z | `CIS_InfoImportantes.txt` | — | 4 510 790 | `a27b30e12c837fd709906513fb0fe8e8c16bd008d3d0fab2fd0dea8de46a39ff` |
| 20261024T231707Z | `CIS_CIP_bdpm.txt` | 2026-10-24 | 4 148 470 | `a6da566e803671a14e403c19a6983c79ce284ecadf947742dafd66a5d72bb0b2` |
| 20261026T001708Z | `CIS_CIP_bdpm.txt` | 2026-10-26 | 4 148 229 | `276207db57839385d2d6e6ba79feb04af56ac78f288bb5bb0f2cbb1cda901164` |
| 20261026T141708Z | `CIS_InfoImportantes.txt` | — | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 20261026T151708Z | `CIS_InfoImportantes.txt` | — | 4 510 790 | `a27b30e12c837fd709906513fb0fe8e8c16bd008d3d0fab2fd0dea8de46a39ff` |
| 20261027T001708Z | `CIS_CIP_bdpm.txt` | 2026-10-27 | 4 146 818 | `8e08b7a8fdada7be2c11ba45096ec03e1bef48c4f32491fa9d2b901aa6a1e7a8` |
| 20261027T081708Z | `CIS_InfoImportantes.txt` | — | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 20261027T091708Z | `CIS_InfoImportantes.txt` | — | 4 510 790 | `a27b30e12c837fd709906513fb0fe8e8c16bd008d3d0fab2fd0dea8de46a39ff` |
| 20261027T101708Z | `CIS_InfoImportantes.txt` | — | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 20261027T111708Z | `CIS_InfoImportantes.txt` | — | 4 510 790 | `a27b30e12c837fd709906513fb0fe8e8c16bd008d3d0fab2fd0dea8de46a39ff` |
| 20261027T121708Z | `CIS_InfoImportantes.txt` | — | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 20261027T131708Z | `CIS_InfoImportantes.txt` | — | 4 510 790 | `a27b30e12c837fd709906513fb0fe8e8c16bd008d3d0fab2fd0dea8de46a39ff` |

Le sha256 `e3b0c442…` est celui du contenu vide.

## Les pages d'avis de la HAS (mission 09)

**150 pages** d'avis de la Commission de la transparence, prises dans la
première étape du corpus (ADR 0004 : les dossiers avec un avis SMR ou ASMR
daté de 2024 ou après, 722 pages), et reprises **à l'octet** du passage de
collecte de beko (`20261031T124148Z`, le 31 octobre 2026 entre 12 h 41 et
13 h 08 UTC) : chaque archive est la page reçue, compressée par le collecteur,
et sa ligne de manifeste est recopiée telle quelle (extracteur v1, rejet
compris). Elles pèsent 2 574 863 octets compressés, sous le plafond de 10 Mo
de l'addendum 1 (E).

**Source et licence.** Haute Autorité de santé, pages
`https://www.has-sante.fr/jcms/p_N` que donne `HAS_LiensPageCT_bdpm.txt`.
Contenus réutilisés selon les mentions légales du site (article du
01/10/2015, relu le 26/10/2026 et le 31/10/2026, ADR 0004) : reproduits en
intégralité, sans altération, avec la source et la date. Document de la
Haute Autorité de santé, disponible sur <https://www.has-sante.fr>, pages
consultées le 31/10/2026 ; la date de mise en ligne de chaque avis est dans
sa page (« Mis en ligne le … »).

**Le choix**, une règle écrite (`src/pharmaflux/demo/has.py`), appliquée à la
BDPM du jeu, sans réseau :
1. **22 pages imposées** : les cinq fixtures du §0 qui sont dans la première
   étape (MOUNJARO, IMFINZI - LYNPARZA, KALYDECO, les deux pages d'ADEMPAS),
   et les cas que la collecte a montrés : les deux noms JSON-LD à entité
   (KEPPRA, XALKORI), les deux avis communs lus par l'extracteur v2 (les cinq
   vaccins méningococciques, les cinq NICORANDIL), FINLEE / SPEXOTRAS, la
   page rejetée (PEDMARQSI) et trois pages dont le contrôle de dossier est
   impossible ;
2. **3 pages** des CIS visés par une question de la v1 (`cis_attendu`) ;
3. **125 pages de complément** : les plus petits sha256 de l'URL.

La liste est `demo/has-pages.txt`, une URL et sa raison par ligne. Un test la
recalcule par la règle et exige la même. Les 572 autres pages, `robots.txt` et
les mentions légales restent dans l'archive de beko.

**Fabrication**, par les commandes du projet, jamais à la main :

```bash
uv run pharmaflux demo choisir-has
uv run pharmaflux demo fabriquer-has --racine ~/pharmaflux-data
```

La première écrit la liste. La seconde copie la dernière archive de chaque page
et sa ligne du manifeste HAS, dans l'ordre du manifeste source. Elle n'écrit
jamais dans la racine, et elle refuse un jeu qui a déjà ses pages.
`demo verifier` contrôle en plus chaque page : sa place
(`bronze/has/pages/<page>/`), son nom, son sha256 et sa taille décompressés.
