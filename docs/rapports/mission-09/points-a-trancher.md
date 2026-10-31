# Mission 09 — réponses au §0 (points à trancher avant de coder)

**De :** codeur (Claude Opus 5.5) · **À :** IeC, beko · **Date :** 31/10/2026
**Branche :** `mission-09-corpus-des-avis-has` (sommet `d05355e`, identique à
`main`) · **Ordre lu sur `main`** (`d05355e`), avec le PRD v1.0 (§2.2, §4
Lot 3, §6.1, §6.7, §6.8, §7.4, §7.5, annexe B), les ADR 0004, 0011 et 0012, le
`pr.md` et le contrôle final de la mission 08, `evaluation/README.md` et
`docs/agents/processus.md`.

## Synthèse

**Fait** : les **douze requêtes** vers `www.has-sante.fr` (31/10, 10:41:23 à 10:43:24 UTC), par un
script qui tient le journal et refuse la treizième ; réponses en fixtures (`tests/fixtures/has/`).
Rien d'autre n'est codé ; **aucun appel à l'API**.
- **Pages** (A, J) : un **JSON-LD `Review`** donne la date de l'avis, SMR, ASMR, CIP13 et l'**URL
  directe du PDF** ; corps stable de 2015 à 2026 ; 110 à 2 002 jetons e5 de texte utile ; seule
  date de mise à jour affichée : « **Mis en ligne le** ». Un PDF mesuré : 631 564 octets.
- **Pièges réels** : un second lien qui est **une autre décision** (ADEMPAS, 2025, sans SMR) ;
  **OZEMPIC (`avis_has-003`) n'a pas de page** dans le fichier des liens.
- **Première étape** (B) : 746 dossiers, **720 avec un lien**, **722 pages** (`p_N`), 978 CIS,
  1 178 paires (page, CIS) ; collecte **≈ 26 min**.
- **Estimation** (I) : entrée des 65 appels reconstituée sans API (62 clés de cache retrouvées) :
  **1,86 caractère par jeton** (1,73 à 2,08), contre 3,8 ; je propose **1,7**.
- **Avis** : rien à installer (`html.parser`, 720 pages en 3,6 s, 19 Mo) ; un fragment par
  (page, CIS, partie), section `avis_has`, format 3 ; ≈ 2,7 $ probables sur 10 $.
- **16 questions pour l'IeC**, récapitulées à la fin. Le document est long (≈ 860 lignes) : douze
  points, et des mesures que l'IeC ne peut pas refaire sans réseau.

## Les douze requêtes

Le script `tests/fixtures/has/requetes_s0.py` s'invoque une requête par
appel :
- un seul hôte, en https ;
- `User-Agent` de la collecte de la BDPM
  (`pharmaflux/0.1.0 (+https://github.com/behramkorkut/pharmaflux)`) ;
- `follow_redirects=False` ;
- deux secondes au moins après la fin de la précédente, lues au journal ;
- refus d'écraser un fichier ;
- refus de la treizième, éprouvé (`refusé : 12 requêtes au journal : le
  plafond est 12`, code 2).

Le journal brut est `tests/fixtures/has/journal-s0.jsonl`. La durée des
réponses va de 0,10 à 0,17 s.

| # | UTC | requête | statut | taille (octets) | sha256 |
|---|---|---|---|---|---|
| 1 | 10:41:23 | GET `/robots.txt` | 200 | 109 | `a66da4379296fcdc…` |
| 2 | 10:41:29 | GET `/jcms/p_4072400` | 200 | 93 034 | `cf98a7fc6844378e…` |
| 3 | 10:41:56 | GET `/jcms/p_3590639` | 200 | 87 511 | `7e295c47fd2cb806…` |
| 4 | 10:41:58 | GET `/jcms/p_3577036` | 200 | 83 796 | `d6af550bc8520fa6…` |
| 5 | 10:42:00 | GET `/jcms/p_3500927` | 200 | 81 235 | `b5481cc7c389b134…` |
| 6 | 10:42:06 | GET `/jcms/p_3741668` | 200 | 69 943 | `bbadbf914eca4477…` |
| 7 | 10:42:09 | GET `/jcms/c_2027377` | 200 | 71 530 | `c1e320698ff0c1c4…` |
| 8 | 10:42:16 | HEAD `/jcms/p_4072399/fr/mounjaro-06052026-avis-ct21681` | 302 → `/plugins/ModuleXitiKLEE/types/FileDocument/doXiti.jsp?id=p_4072399` | en-tête 20 | — |
| 9 | 10:42:21 | HEAD `…/doXiti.jsp?id=p_4072399` | 200, `text/html` | en-tête 395 | — |
| 10 | 10:42:39 | GET `…/doXiti.jsp?id=p_4072399` | 200 | 549 | `c13ebbc0aea04d30…` |
| 11 | 10:42:46 | HEAD `/upload/docs/evamed/CT-21681_MOUNJARO_PIC_INS_AvisDef_CT21681.pdf` | 200, `application/pdf` | en-tête **631 564** | — |
| 12 | 10:43:23 | HEAD `/jcms/c_2027376/fr/doliprane-geluprane-paracetamol-zentiva-01042015-avis-ct14040` | 302 → `…/doXiti.jsp?id=c_2027376` | en-tête 20 | — |

**Le choix des pages** a été fait depuis l'archive du Mac, sans réseau. Il
couvre :
- les deux formes d'URL, et 2015, 2024, 2025 et 2026 ;
- le dossier aux **douze spécialités** (CT-21681, MOUNJARO) ;
- un dossier qui couvre **deux marques** (CT-21088, IMFINZI - LYNPARZA) ;
- un dossier des questions v1 (CT-21030, KALYDECO) ;
- un **dossier à deux liens** (CT-20568, ADEMPAS) ;
- un `c_N` de 2015 à vingt spécialités (CT-14040, DOLIPRANE).

**Les documents** : le budget n'a permis de suivre **qu'un** lien jusqu'à sa
réponse finale. Le premier saut est un 302 ; puis `doXiti.jsp` répond 200 en
HTML, ce qui coûte une requête de plus pour lire la cible, et le PDF vient en
`HEAD`. La douzième requête montre que le document de 2015 passe par le même
302. Le troisième lien n'a pas été suivi : c'est un écart à « au plus
trois », dans le sens de la prudence (J).

**Retouche des fixtures** : la valeur du cookie de session `JSESSIONID` est
remplacée par `<retiré>` dans les `.headers`. Les corps sont intacts : leur
sha256 est celui du journal (`tests/fixtures/README.md`, section `has/`).

## A. La page d'avis

**Constat** (les six pages, `tests/fixtures/has/`) :

| page | dossier, forme, année | brut | gzip servi | texte utile | jetons e5 | `datePublished` | « Mis en ligne le » | sections du corps | lignes SMR / ASMR |
|---|---|---|---|---|---|---|---|---|---|
| `p_4072400` | CT-21681 MOUNJARO, `p`, 2026 | 93 034 | 18 649 | 7 336 car. | 2 002 | 2026-05-06 | 12 juin 2026 | 4 | 2 / 2 |
| `p_3590639` | CT-21088 IMFINZI - LYNPARZA, `p`, 2025 | 87 511 | 18 050 | 4 775 | 1 317 | 2025-01-15 | 19 févr. 2025 | 3 | 1 / 1 |
| `p_3577036` | CT-21030 KALYDECO, `p`, 2024 | 83 796 | 17 570 | 3 915 | 1 142 | 2024-12-18 | 10 janv. 2025 | 4 | 2 / 1 |
| `p_3500927` | CT-20568 ADEMPAS, `p`, 2024 | 81 235 | 17 290 | 3 169 | 830 | 2024-02-28 | 15 mars 2024 | 3 | 1 / 1 |
| `p_3741668` | CT-20568 (2ᵉ lien), `p`, 2025 | 69 943 | 15 229 | 493 | 131 | **2025-11-10** | 21 nov. 2025 | 0 | 0 / 0 |
| `c_2027377` | CT-14040 DOLIPRANE…, `c`, 2015 | 71 530 | 15 933 | 388 | 110 | 2015-04-01 | 07 mai 2015 | 0 | 1 / 0 |

Le texte utile est mesuré par un prototype `html.parser`, gardé hors du
dépôt. Les jetons e5 sont comptés avec le `sentencepiece.bpe.model` épinglé
(préfixe `passage: ` compris).

**Où sont les champs.** La page est générée par Jalios ; ses champs sont aux
mêmes places dans les six pages, et les deux formes `c_N` et `p_N` sont le
même gabarit.

- **Le JSON-LD** (un seul bloc `application/ld+json`, `@type` `Review`) :
  - `name` vaut « Avis sur » suivi du titre ;
  - `datePublished` est la **date de l'avis**, égale au `date_avis` de la
    BDPM sur 5 pages sur 6 (la sixième est le piège ci-dessous) ;
  - `reviewBody` aplatit la synthèse ;
  - `reviewAspect[]` donne chaque ligne SMR et ASMR (`propertyID`, `value`,
    `description`) ;
  - `hasPart[]` liste les documents (`name`, `contentUrl` du PDF) ;
  - `itemReviewed` porte `dosageForm` (« CIP : » puis les CIP13), l'ATC
    (`code.codeValue`) et le laboratoire (`brand.name`) ;
  - **il n'y a jamais de `dateModified`**.
- **Les balises `meta`** : `description` (le début de la synthèse),
  `og:title` et `og:url`. L'URL canonique a la forme
  `/jcms/p_4072400/fr/<slug>`.
- **Le corps** commence au `<h1>`, avec le titre :
  - « Avis sur les Médicaments - Mis en ligne le 12 juin 2026 » ;
  - puis un encart « Nature de la demande » (`<h4>` et sa valeur :
    « Inscription », « Extension d'indication non sollicitée »…) ;
  - puis un paragraphe de motif (« Maintien du remboursement dans les mêmes
    conditions ») ;
  - puis un bloc HTML qui donne les sections : « L'essentiel », « Quel
    progrès ? », « Quelle place dans la stratégie thérapeutique ? » (avec ses
    `<h4>`), « Recommandations particulières » ;
  - puis les deux tables `tableService` : SMR (`<a id="smr">`) et ASMR
    (`<a id="asmr">`), une ligne par niveau, la première cellule portant le
    niveau (« Modéré », « V (absence) », « Sans objet »), la seconde son
    libellé ;
  - enfin « Documents » (`li.pdf`), « Nous contacter », les étiquettes, le
    pied de page.
- **Les tables et le JSON-LD concordent** sur les six pages : même nombre de
  lignes, mêmes niveaux, à la casse près.

**Ce qui varie.** Ce n'est pas la forme de l'URL : `c_N` et `p_N` partagent
le gabarit. C'est **l'année et la nature de la demande** :
- en 2015 (renouvellement), il n'y a ni « L'essentiel » ni « Quel
  progrès ? », seulement le motif et le SMR, en 388 caractères ;
- de 2024 à 2026, on trouve trois ou quatre sections, de 3 000 à 7 300
  caractères ;
- une « extension d'indication non sollicitée » n'a ni table ni document.

Sur les 722 pages de la première étape, **toutes sont des `p_N`** (B) :
les `c_N` s'arrêtent en 2019.

**Ce qui change à chaque réponse.** La page porte un jeton CSRF (`<div
id="CSRFTokenElm">`) et un horodatage (`id="AjaxCtxt-0-1793443289907"`,
1 793 443 289 s : l'heure de la réponse). Deux requêtes de la même page ne
donnent donc pas le même sha256.

**Aucun en-tête de fraîcheur.** Les pages arrivent avec
`Cache-Control: no-cache, no-store`, sans `Last-Modified` ni `ETag`. Le PDF,
lui, a un `Last-Modified` (12/06/2026 09:30 GMT), égal à la date de mise en
ligne de la page.

**La « date de dernière mise à jour »** que demande la licence :
- les six pages n'en affichent qu'une, « **Mis en ligne le** », 11 à 37
  jours après la date de l'avis ;
- je n'ai vu ni « Mis à jour le », ni `dateModified`, ni `Last-Modified` sur
  une page ;
- le gabarit laisse de la place autour de « Mis en ligne le » (des
  conditions JSP vides) : une page republiée pourrait afficher une seconde
  date.

**Avis** :
- citer **trois dates**, rendues par le code : la date de l'avis
  (`datePublished`), la date de mise en ligne (la date de mise à jour de la
  licence), et la date de consultation (la collecte) ;
- l'extraction lit « Mis à jour le » s'il paraît, et le préfère alors à la
  mise en ligne ;
- le JSON-LD sert de **contrôle**, jamais de texte : le texte indexé vient du
  corps, que le lecteur voit.

**Question A1** : la date de mise à jour citée est-elle bien « Mis en ligne
le » (ou « Mis à jour le » s'il paraît), à côté de la date de l'avis et de
celle de la collecte ?

## B. Le périmètre de la première étape

**Constat.** Calculé depuis la dernière archive du Mac, sans réseau, par un
script du scratchpad. Les trois archives sont `HAS_LiensPageCT` `2f01ff1e…`,
`CIS_HAS_SMR` `c2215af6…` et `CIS_HAS_ASMR` `f8495540…`, toutes du
24/10 à 19:41 UTC. Le **jeu de démo** porte les **mêmes trois archives**
(même sha256), et ces fichiers n'ont pas changé jusqu'au 27/10 : les
décomptes à l'instant de l'index du jeu (`2026-10-27T00:17:12Z`) sont
identiques.

| mesure | valeur |
|---|---|
| dossiers avec un avis SMR ou ASMR daté de 2024 ou après | **746** (745 avec SMR, 678 avec ASMR, 1 avec ASMR seul) |
| dont avec un lien / sans lien | **720** / **26** |
| les 26 sans lien, par mois d'avis | 2025-09 : 15 ; 2026-09 : 6 ; 2024-07, 2024-09, 2024-11, 2026-07, 2026-08 : 1 chacun |
| URL distinctes à demander | **722**, toutes de forme `p_N` (2024 : 270, 2025 : 249, 2026 : 203) |
| dossiers à plusieurs liens | 2 : CT-20568 (ADEMPAS, mesuré en A) et CT-21304 (2025, deux CIS hors du référentiel) |
| liens partagés par plusieurs dossiers | aucun dans la première étape ; 18 dans le fichier entier (20 lignes), le plus récent de 2021 |
| CIS concernés | 1 020, dont **978** avec au moins une page (**766** dans le référentiel, 212 hors) |
| paires (page, CIS) | **1 178**, soit 1,63 CIS par page, 12 au plus (CT-21681) |
| CIS de la première étape qui ont aussi un avis antérieur à 2024 | 435 : leur fiche porte des avis dont le texte ne sera pas collecté |

`avis_has-003` (OZEMPIC, CT-21716, avis du 16/09/2026) fait partie des 26
dossiers **sans lien** : sa page n'est pas dans le corpus.

**La durée.** Il faut 723 requêtes (`robots.txt` et 722 pages), à deux
secondes de pause et 0,15 s de réponse en moyenne : **≈ 26 min**. Avec trois
secondes de pause, ≈ 38 min. Le volume :
- ≈ 12,6 Mo transférés (gzip, 17,5 Ko par page) ;
- ≈ 58 Mo décompressés ;
- ≈ 12,4 Mo d'archive compressée.

**L'ordre de collecte.**
- On trie par date d'avis décroissante, puis par dossier, puis par URL :
  c'est déterministe, et le plus récent passe d'abord si la commande
  s'arrête ;
- un dossier à plusieurs liens donne une requête par lien ;
- un lien partagé par plusieurs dossiers ne se demande qu'une fois : la page
  est la clé de l'archive, et le manifeste note les dossiers qui la lient.

**Avis** : la date d'un fragment d'avis est celle de **sa page**
(`datePublished`), jamais celle de la BDPM. CT-20568 en donne la preuve : son
second lien est une décision du 10/11/2025, « extension d'indication non
sollicitée », alors que la BDPM ne connaît pour ce dossier que l'avis du
28/02/2024.

## C. La collecte

**Avis — la commande** : un groupe `pharmaflux has`.

- `has collecter --racine <archive> --plafond N [--depuis 2024-01-01]
  [--dossier CT-… …] [--pause 2.0] [--simuler] [--reessayer-erreurs]`.
- **`--plafond` est obligatoire.** Il compte toutes les requêtes, réessais et
  `robots.txt` compris. La commande s'arrête net quand il est atteint.
- **`--pause`** vaut deux secondes au moins ; une valeur plus courte est
  refusée.
- **`--simuler`** lit seulement l'archive (les liens, le SMR, l'ASMR, le
  manifeste HAS). Il dit ce qui serait demandé (les URL dans l'ordre, leur
  nombre, la durée estimée), sans aucune requête, `robots.txt` compris.
- **Codes de sortie** :

  | code | sens |
  |---|---|
  | 0 | tout ce qui était à demander est archivé |
  | 1 | fini, mais des pages sont en erreur visible (redirection, 404, type ou corps inattendu), listées |
  | 2 | refus avant toute requête : option invalide, `robots.txt` qui interdit le chemin, archive des liens illisible |
  | 3 | arrêt net : premier 429, 5xx répété, ou plafond atteint. Relancer reprend |

**Avis — le client** : il est **à côté** de celui de la BDPM, dans
`has/client.py`. Il en reprend `agent_utilisateur()` et l'injection d'un
transport (`httpx.MockTransport`) pour les tests. Il diffère sur quatre
points, que la BDPM n'a pas à changer :
- il ne suit **aucune redirection** ;
- **la pause est tenue dans le client**, pour toute requête, réessai et
  `robots.txt` compris ;
- il s'arrête au **premier 429** (avec le `Retry-After` noté) ;
- il fait **un seul réessai** sur un 5xx ou une erreur réseau, après une
  pause de 10 s. Un second 5xx, sur la même URL ou sur la suivante, arrête
  tout.

Le délai est de 30 s, les pages pesant moins de 100 Ko. Le cookie de session
reste en mémoire le temps d'un passage, ce qui fait une session côté serveur
au lieu de 723. Il n'est jamais écrit, et `set-cookie` n'entre pas au
manifeste.

`robots.txt` est lu à chaque passage, archivé, et analysé par
`urllib.robotparser` (bibliothèque standard). Un chemin interdit n'est pas
demandé : la page est notée `interdit_robots`, et un `robots.txt` illisible
donne le code 2.

**Avis — l'archive** est immuable, sous `$PHARMAFLUX_DATA` :
- les pages vont sous `bronze/has/pages/<p_N|c_N>/<horodatage>__<sha12>.html.gz`,
  par l'écriture du bronze (fichier temporaire, puis `os.link`) ;
- `robots.txt` va sous `bronze/has/robots.txt/<jour>/…` ;
- le manifeste en ajout seul est `manifeste/has-pages.jsonl` : une ligne par
  requête. Il est séparé de `collecte.jsonl`, que `evenements` lit, et qui
  ne change donc pas. Chaque ligne porte :
  - `passage_id`, `url`, `page_id` ;
  - `dossiers` : ceux qui lient la page, avec l'archive des liens citée et
    son sha256 ;
  - `debut`, `fin`, `statut`, `http_statut`, `content_type`, `location` ;
  - `taille`, `sha256`, `archive`, `essais` ;
  - `version_collecteur`, `user_agent`.

**Les statuts du manifeste** :

| statut | ce que c'est | archivé ? |
|---|---|---|
| `nouveau` | une page reçue en 200, en `text/html` et non vide | oui |
| `redirection` | la `location` est notée, la redirection n'est pas suivie | non |
| `erreur_http` | un 4xx ou un 5xx | non |
| `vide` | un corps vide | non |
| `type_inattendu` | un autre type que `text/html` | non |
| `erreur_reseau` | une erreur de transport | non |
| `interdit_robots` | un chemin que `robots.txt` interdit | non |

Une réponse en erreur garde sa taille et son sha256, sans archive. Son corps
est une page d'erreur du site : l'archiver n'apprend rien.

**Avis — la reprise.** Le manifeste fait foi.
- Une relance ne demande que les pages **jamais tentées**. Les pages en
  erreur ne sont redemandées qu'avec `--reessayer-erreurs`, pour qu'une
  page disparue ne soit pas redemandée à chaque passage.
- Si une coupure tombe entre l'archive et sa ligne de manifeste, la relance
  trouve l'archive orpheline au départ. Elle l'adopte par une ligne
  `repris`, sans la redemander.
- Les tests coupent la commande à chaque étape, sur un serveur simulé.

**Avis — plus tard (à proposer, pas à faire).** Sur le VPS, après
mi-novembre :
- un passage **quotidien**, à côté de la collecte horaire de la BDPM, qui ne
  demande que les liens nouveaux, quelques-uns par semaine ;
- une **revisite lente** (par exemple dix pages par jour, chaque page tous
  les deux à trois mois), qui compare l'empreinte du texte extrait et jamais
  le sha256 brut, puisqu'il change à chaque réponse (A).

Cette revisite rouvre la règle « une page archivée n'est pas redemandée » :
ce sera une ADR à elle.

**Question C1** : le contrat des codes de sortie (0, 1, 2, 3) et la politique
de réessai (un seul, puis l'arrêt) conviennent-ils ?
**Question C2** : faut-il un `robots.txt` par passage seulement, ou aussi une
relecture des mentions légales (une requête de plus) ? Voir L.

## D. L'extraction

**Avis — l'analyseur** : `html.parser`, de la bibliothèque standard. Le
prototype extrait les six pages en 5 à 7 ms chacune, et 720 pages en 3,6 s
pour 19 Mo de résident. Il n'y a pas de dépendance nouvelle, donc rien à
justifier au titre de l'ADR 0009.

**Le texte gardé**, dans l'ordre de la page et avec les étiquettes de la
page :
1. le titre (`<h1>`) ;
2. « Nature de la demande », puis sa valeur ;
3. le paragraphe de motif ;
4. chaque section du corps (« L'essentiel », « Quel progrès ? », « Quelle
   place dans la stratégie thérapeutique ? » et ses `<h4>`, « Recommandations
   particulières »), un paragraphe ou un élément de liste par ligne ;
5. la table SMR, puis la table ASMR, une ligne par niveau, au format
   « niveau : libellé », dont seul le « : » est à nous.

Les dates (de l'avis, de mise en ligne) vont en métadonnée et, en ISO, dans
la ligne d'en-tête du fragment (F). « Mis en ligne le 10 janv. 2025 » se lit
par une table des douze abréviations, testée, et la valeur brute reste en
métadonnée.

**Ce qui est écarté** : l'en-tête, les menus, la table des matières (`nav`),
les boutons de partage, « Citer cette publication », la liste des documents
(son PDF d'avis va en métadonnée), « Nous contacter », les étiquettes, le
pied de page, les scripts et le JSON-LD. Le JSON-LD ne sert que de contrôle.

**Les motifs de rejet** : une page rejetée est comptée par motif. Le
bilan de `has extraire` la rend, l'index en garde le compte dans son état, et
elle n'entre jamais dans l'index.
- l'archive est illisible, ou la page n'est pas en UTF-8 ;
- il n'y a pas de JSON-LD `Review`, ou son `datePublished` est illisible ;
- il manque le `<h1>`, la mention « Avis sur les Médicaments », la date
  « Mis en ligne le » ou « Nature de la demande » ;
- **le corps est vide** : ni section, ni motif, ni table ;
- **une incohérence** : le `name` du JSON-LD n'est pas « Avis sur » suivi
  du titre ; ou les niveaux des tables diffèrent de `reviewAspect` ; ou le
  titre du document d'avis (`…_AVIS_CTNNNNN`) nomme un autre dossier que
  ceux qui lient la page.

**Ce qui n'est pas un rejet** : une page sans table SMR (CT-20568, second
lien) ; des CIP13 de `dosageForm` qui ne correspondent pas tous aux CIS de la
BDPM. Sur CT-21681, 6 des 12 CIP13 sont inconnus de `CIS_CIP_bdpm.txt`, mais
les 12 CIS de la BDPM sont les bons. C'est une **remarque** du bilan, jamais
un rattachement : **les CIS d'une page viennent de la BDPM** (les dossiers
qui la lient, puis leurs avis SMR et ASMR).

**La preuve de non-altération**, en trois volets :
1. **Deux lecteurs indépendants.** Le texte de référence d'une page s'obtient
   par une autre voie : expressions régulières qui ôtent les balises,
   `html.unescape`, espaces (insécables compris) normalisées. Le test exige
   que **chaque ligne extraite**, hors nos étiquettes, soit une sous-chaîne
   de ce texte. Il tourne sur les fixtures dans `pytest`, et sur toute
   l'archive par `has extraire --verifier`.
2. **Le JSON-LD** : les niveaux SMR et ASMR doivent égaler `reviewAspect`,
   sinon la page est rejetée (ci-dessus).
3. **Le déterminisme** : les mêmes octets donnent le même texte. Une
   extraction attendue est figée pour deux fixtures
   (`p_4072400.extrait.json`, `c_2027377.extrait.json`).

**Stocker ou recalculer ?** Je propose de **recalculer** l'extraction à
chaque construction de l'index, dans le sous-processus des fragments
(≈ 4 s pour 722 pages). L'archive reste la seule vérité, sans couche dérivée
à tenir à jour. `has extraire` sert à l'inspection et à la vérification, et
peut écrire un JSONL pour lire, jamais lu par l'index.

**Question D1** : faut-il garder toutes les sections du corps, « Quelle place
dans la stratégie thérapeutique ? » et « Recommandations particulières »
comprises ? Je le propose, car couper serait déjà choisir dans le texte, et
ce sont ces sections qui disent pourquoi un SMR ou un périmètre. Le refus
médical reste décidé en amont sur la question (G). L'autre voie est de les
écarter, pour réduire ce qui ressemble à une stratégie de soin.
**Question D2** : faut-il recalculer à chaque construction (ma proposition),
ou stocker une couche d'extraits ?

## E. Le jeu de démo

**Avis — le choix** : environ **150 pages**, tirées de l'archive de beko par
une liste committée (`demo/has-pages.txt`), dans cet ordre :
1. les pages des questions v2 sur le texte des avis (≈ 25 dossiers) ;
2. les pages des CIS visés par une question v1 ou v2 qui en ont une
   (KALYDECO CT-21030…) ;
3. les pièges : les deux pages de CT-20568, celle d'IMFINZI - LYNPARZA, et
   une page rejetée si la collecte réelle en donne une ;
4. un complément déterministe (les plus petits sha256 de l'URL) pour
   varier les années et les formats.

La taille : 150 pages à 17,5 Ko compressées font **≈ 2,6 Mo sur disque**,
sous le plafond de 10 Mo. Le paquet git grossit d'autant (du gzip ne se
recompresse pas). Il pèse 6,39 Mio aujourd'hui (`git count-objects -vH`). Les
722 pages feraient ≈ 12,6 Mo, au-dessus du plafond.

**Où.** Sous `demo/archive/bronze/has/pages/…`, avec un manifeste à part
(`demo/archive/manifeste/has-pages.jsonl`). `collecte.jsonl` reste ainsi
identique à l'octet, et `--racine demo/archive` suffit à `make index` comme
à la CI, sans réseau. `.gitignore` admet déjà `demo/archive/bronze/**/*.gz`.

**La commande** : `pharmaflux demo fabriquer-has --racine ~/pharmaflux-data
--destination demo/archive --liste demo/has-pages.txt`.
- Elle copie les archives citées à l'octet, et leurs lignes de manifeste
  telles quelles.
- Elle refuse un `bronze/has` déjà présent, et n'écrit jamais dans la
  racine.
- `demo verifier` contrôle en plus le sha256 de chaque page et la présence
  de chaque archive citée.

**Question E1** : le `README` du jeu (« figé ; un autre jeu serait un autre
dossier ») et `CLAUDE.md` (« des fichiers BDPM ») disent que le jeu ne
grossit pas. Faut-il ajouter les pages sous `demo/archive` (ma proposition,
avec le `README` revu), ou dans une racine sœur `demo/has/` (ce qui ferait
une option `--racine-has` de plus) ? Dans les deux cas, la ligne de
`CLAUDE.md` est à revoir par l'IeC.

## F. L'index

**Avis — le fragment d'avis** : un par **(page, CIS, partie)**, dans une
section `avis_has`.
- **Pourquoi par CIS** : l'invariant « un fragment, un CIS » tient alors
  partout. La porte structurelle, le repérage, la citation du CIS attendu,
  l'incrément par lots de CIS et `verifier` restent ce qu'ils sont.
- **Ce que ça coûte** : la première étape fait 1 178 paires (page, CIS).
  Avec ≈ 4 parties par page (moyenne des cinq pages récentes), cela donne
  **≈ 4 700 fragments, soit 6,5 % de plus** que les 72 296. Sur le jeu de
  démo, ≈ 1 000.
- **La voie écartée** : un fragment par (page, partie), avec une liste de CIS
  (≈ 2 900 fragments). Le « un fragment, un CIS » des ADR 0011 et 0012 ne
  tiendrait plus, et retirer les points d'un CIS pourrait retirer ceux d'un
  autre.
- **L'identifiant** : `uuid5("f3/<cis>/avis_has/<page_id>/<partie>")`. Un
  dossier à deux pages donne donc deux suites de fragments.
- **Le texte** :
  - la ligne d'identité (`CIS … — dénomination`) ;
  - une ligne d'en-tête à nous : « Avis de la Commission de la transparence
    (HAS), dossier CT-21030, du 2024-12-18 ; page mise en ligne le
    2025-01-10 » ;
  - puis les lignes extraites, mot pour mot.
- **La découpe** suit la règle de l'ADR 0011 : par ligne, sous 1 200
  caractères, « (partie k sur n) » et « (suite) ». Le texte d'avis est de la
  prose, à 3,6 caractères par jeton e5 sur les six pages, donc ≈ 330 jetons
  par partie, loin des 512. Une ligne seule de plus de 1 200 caractères se
  couperait entre deux phrases. Je n'en ai vu aucune, la plus longue fait
  686 caractères, et la mesure sur les 722 pages est au palier 2.
- **Les métadonnées** :
  - `url`, `page_id`, `date_avis`, `mis_en_ligne` (ISO et brut),
    `collectee_le`, `archive`, `sha256`, `pdf_avis` (le `contentUrl`),
    `dossiers`, `extracteur` (version) ;
  - `sources` : `has.avis`, `date_source` = la date de l'avis,
    `observee_depuis` = la collecte.

**Le format et la collection** : format 3, collection neuve (ADR 0011).
- Les textes des fiches ne changent pas : leurs 72 296 vecteurs denses sont
  repris du cache, et seuls les fragments d'avis sont encodés.
- **Le lexical** pose une vraie question : l'`avgdl` de BM25 est figée à
  53,29 dans le format, mesurée sur les fiches. Un fragment d'avis de ≈ 180
  mots aurait `|d|/avgdl` ≈ 3,4, et BM25 l'écraserait. Je propose de
  **remesurer `avgdl` une fois**, sur les fragments du jeu (fiches et avis),
  et de la figer dans le format 3, en montrant par `index evaluer` (v0 et v1)
  que le rappel des fiches ne recule pas.

**La mise à jour par incréments.** Il y a deux horloges, et l'état les tient
toutes les deux :
- `instant` : la dernière observation du silver appliquée. Il ne change pas
  de sens.
- `has` : la position appliquée du manifeste HAS (nombre de lignes et
  empreinte de ce préfixe), la dernière collecte appliquée, le nombre de
  pages lues et rejetées, et la version de l'extracteur.

`mettre-a-jour` touche :
- les CIS que le silver touche, comme aujourd'hui. Les liens CT et les avis
  SMR et ASMR y sont déjà, et un avis qui change recalcule `avis_has` ;
- les CIS des dossiers qui lient une page **arrivée au manifeste** depuis la
  position. Les liens sont lus au silver à `instant` ;
- un manifeste HAS dont le préfixe a changé, ou un extracteur d'une autre
  version : refus, et il faut reconstruire.

**« L'instant de l'index » et la vérité.** Une page est rattachée à un CIS
par les liens de la BDPM **à l'instant du silver**, jamais l'inverse.
- Une page collectée après cet instant n'apporte que ce qu'elle date
  elle-même : la date de l'avis, la mise en ligne, la consultation.
- Le code rend les deux horloges : « BDPM au 27/10/2026 00:17 UTC ; pages
  d'avis de la HAS collectées jusqu'au <date> ».
- L'index ne prétend donc à rien qu'il ne sache : un fait de la BDPM est
  daté par le silver, un fait de la HAS par sa page.

**`index verifier`** reconstruit depuis le gold à `instant` et depuis
l'archive HAS jusqu'à la position de l'état. Il exige les mêmes
identifiants, les mêmes charges et les mêmes vecteurs, avis compris. Le test
par tranches gagne deux tranches HAS (deux préfixes du manifeste) : mise à
jour, `verifier` conforme à chaque étape, et égalité finale avec la
construction d'un coup.

**Question F1** : un fragment par (page, CIS, partie), ma proposition, ou par
(page, partie) avec une liste de CIS ?
**Question F2** : faut-il remesurer `avgdl` sur fiches et avis au format 3,
ou garder 53,29 ?
**Question F3** : les deux horloges (`instant` du silver et position HAS),
rendues toutes les deux, conviennent-elles ?

## G. L'assistant

**Le rendu des liens par le code.** Sous la réponse, pour chaque fragment
cité :
- un fragment `avis_has` donne « Avis de la CT du 2024-12-18, page
  <url> (mise en ligne le 2025-01-10, consultée le <collecte>) » ;
- un fragment de fiche donne ses `liens` : la page de l'avis pour `avis`, la
  fiche de l'ANSM pour `disponibilite` et `informations`.

**Le LLM ne voit aucune URL.** Il ne peut donc ni en inventer ni en altérer
une. L'étiquette d'un fragment dit seulement « section avis_has (page de
l'avis, lien rendu sous la réponse) ». Une question « Où lire l'avis ? » se
note par le **lien rendu** (H), et pas par le texte.

**Le prompt système** gagne trois consignes générales :
- le texte d'un avis est une **évaluation collective** par la Commission ; il
  se cite comme tel (« selon l'avis de la CT du … ») et ne s'applique
  jamais à une personne ;
- ne jamais écrire d'adresse : les liens sont rendus par le code ;
- **donner la date de chaque fait daté avec le fait** (la retouche qui
  répond aux dates omises, mesurée sur les questions neuves).

**Le contrôle des nombres et des dates** ne change pas de règle :
- les dates de l'avis et de mise en ligne sont dans le texte du fragment, en
  ISO, et la collecte est dans ses sources : elles s'appuient donc ;
- le texte d'un avis est plein de nombres (« 1,5 mg/semaine », « > 1%
  d'HbA1c », « 24 semaines ») ; ils s'appuient s'ils viennent du fragment
  cité. Le risque est la paraphrase, qui donnera « non vérifiable », le sens
  prudent ;
- je testerai les formes vues (« 2ème ligne », « GLP-1 », « m² ») contre le
  lecteur de nombres.

**La sélection des dix fragments** gagne deux règles, sans aucun réglage sur
un jeu :
- **la déduplication** : les fragments d'une même (page, partie) pour des CIS
  différents (douze pour MOUNJARO) ne comptent qu'une fois. On garde celui du
  CIS visé, sinon le mieux classé ;
- **le rappel par section** : voir le premier constat ci-dessous.

**Les constats de la mission 08** :

| constat | proposition | mesure (questions neuves, H) |
|---|---|---|
| le rappel par section (`avis_has-003`) | une table écrite : des mots de la question vers des sections (« SMR », « ASMR », « avis », « HAS », « CT- » vont vers `avis` et `avis_has` ; « rupture », « tension » vers `disponibilite`, etc.). Quand un CIS est visé et qu'aucun fragment de la section demandée ne lui appartient dans les dix, on joint sa première partie (filtre Qdrant `code_cis` et `section`) à la place du dernier fragment d'un autre CIS | 4 questions sur des CIS dont le fragment de la section demandée **n'est pas** dans les dix, constat fait par la recherche seule, sans LLM, avant la retouche |
| les dates secondaires | l'annexe B dit « niveau + date de l'avis + lien » et « statut + source + date » : la date est **due**, et les quatre échecs étaient justes. La retouche est la consigne générale du prompt | 6 questions (3 dates d'avis, 3 dates de mise à jour de signalement), sur d'autres CIS que la v1 |
| les citations hors des fragments fournis | un compte à part dans le bilan de l'évaluation, distinct de « non vérifiable ». C'est un indicateur, pas une retouche | sur tout le jeu |
| les mots courants qui visent un CIS | sur le jeu, 13 dénominations commencent par EAU, 5 par FER, 4 par GEL, 1 par OR, 6 par HUILE. Si le premier mot d'un nom est dans une courte liste de mots courants, il faut les **deux premiers mots** pour viser (« EAU OXYGENEE »). On éprouve la règle comme celle de « deux médicaments », sur 200 médicaments tirés au hasard | 3 questions pièges (« eau », « fer », « gel ») |

**Le refus médical devant les mots d'un avis.**
- « L'avis dit-il que je peux le prendre pendant ma grossesse ? » est déjà
  refusé par les règles (« je peux », un geste de soin, « grossesse »).
- Le risque nouveau vient de tournures que les règles ne connaissent pas
  encore : « chez mon bébé », « pour ma mère ».
- Je propose 4 questions médicales neuves, écrites avant toute retouche des
  règles. Une règle ne s'étend que si l'une d'elles passe, et l'extension
  s'éprouve sur 200 questions factuelles tirées du jeu.

**Un cas limite à trancher** : « Quelle est la durée du traitement par
KALYDECO selon l'avis ? ». C'est une question sur le texte d'un avis, sans
décision ni situation individuelle : je propose une **réponse** citée,
pas un refus.

**Question G1** : la consigne « date de chaque fait daté » est-elle la bonne
retouche pour les dates omises, plutôt que de compter la date rendue par le
code sous la réponse ?
**Question G2** : la question sur la durée de traitement selon l'avis
appelle-t-elle une réponse citée, ou un refus ?
**Question G3** : une question qui compare deux médicaments à partir d'un
avis (« MOUNJARO apporte-t-il un progrès par rapport à TRULICITY ? »)
déclenche « deux médicaments », donc une abstention. Je propose de garder
cette règle et d'en faire une question piège de la v2.

## H. Le jeu de questions v2

**La reprise de la v1.** `evaluation/questions-reference-v2.toml` est un
nouveau fichier. La v0 et la v1 restent intactes.
- Les 88 questions de la v1 sont reprises **sous leurs identifiants**, au
  même texte. Elles reprennent donc aussi les réponses du cache de la v1 sur
  le même index (I).
- `disponibilite-005` devient une **réponse avec réserve**, comme
  `avis_has-005`. La v1 a déjà changé ainsi le comportement attendu
  d'`avis_has-005`.
- **Sur les cinq abstentions « faute de lien », deux seulement sont des
  liens.** `avis_has-004` (CT-14040) et `avis_has-009` (CT-21030) deviennent
  des réponses notées par le **lien rendu**. `historique-003`, `-008` et
  `remboursement-010` restent des abstentions : la date de déclaration de
  commercialisation et l'agrément aux collectivités ne sont toujours pas dans
  le texte des fragments.

**Les questions sur le texte des avis** (≈ 24), toutes sur des pages du
jeu :

| thème | nombre |
|---|---|
| la nature de la demande et le motif | 4 |
| la date de l'avis et de mise en ligne | 4 |
| ce que dit « L'essentiel » | 4 |
| « Quel progrès ? » et le libellé de l'ASMR | 4 |
| le lien de la page | 3 |
| piège : un avis plus ancien que celui demandé (ADEMPAS, BDPM 2024 contre page 2025) | 1 |
| piège : un dossier sans page (OZEMPIC CT-21716 : le SMR de la BDPM, sans lien de page) | 2 |
| piège : la synthèse d'un avis antérieur à 2024, hors corpus (abstention) | 1 |
| piège : une page rejetée, seulement si la collecte réelle en donne une | 1 |

**Les questions neuves qui mesurent les correctifs** (≈ 17) :
- 4 pour le rappel ;
- 6 pour les dates ;
- 3 pour les mots courants ;
- 4 médicales.

**Ce qui garantit qu'elles n'ont pas servi à mettre au point la retouche** :
1. les CIS sont choisis par une **règle écrite d'abord**, déterministe et
   dite dans l'en-tête du fichier (par exemple, le plus petit sha256 du CIS
   parmi ceux qui remplissent le critère). Je ne les choisis pas à la main
   parmi des cas que je saurais réussis ;
2. le fichier est **committé et figé** (sha256 cité au rapport) dans un
   commit qui **précède** tout commit de retouche. L'IeC vérifie l'ordre ;
3. aucun appel ne part avant : aucun ne part d'une session d'agent, et la
   démonstration de beko vient après les retouches ;
4. la retouche est décrite **ici**, avant que les questions existent.

**Le total** : 88 repris, ≈ 24 sur le texte, ≈ 17 pour les correctifs, 3
qui demandent le PDF (J) et 1 comparaison (G3), soit **≈ 133 questions**.

**Vérifier sans LLM.** Un attendu d'un nouveau genre, `fichier = "has.avis"`,
cite l'archive de la page (chemin, sha256), son URL, et des valeurs :
`date_avis`, `mis_en_ligne`, `nature_demande`, et un `extrait` (une suite de
mots, d'un bloc nommé). `questions verifier` :
- relit l'archive et contrôle son sha256 ;
- réextrait la page et contrôle chaque valeur ;
- vérifie, dans le bronze des liens, que l'URL est bien celle du dossier.

Ces attendus n'ont pas de gold : ils sont « vérifiés depuis l'archive HAS et
le bronze ». Les autres gardent la double vérification.

**La notation déterministe** gagne trois choses :
- **`lien_attendu`** : l'URL doit être rendue par le code sous la réponse,
  depuis une citation valide ;
- **la date de l'avis** est due quand l'attendu la porte ;
- **`extrait_attendu`** : une suite de douze mots au plus, en mots entiers,
  casse et accents ignorés, avec une citation valide vers la section
  `avis_has`. Une paraphrase compte comme absente : c'est une borne basse,
  comme en v1.

Les indicateurs de la v1 et de la v2 sont rendus **séparément**.

**Question H1** : faut-il reprendre la v1 sous ses identifiants, au même
texte, dans la v2 ?
**Question H2** : le nouveau genre d'attendu (`has.avis`, vérifié sans gold)
et les trois ajouts de notation conviennent-ils ?

## I. Le coût

**La constante d'estimation, recalée.** Le journal porte 65 lignes, mais pas
le texte envoyé. Je l'ai **reconstitué sans API** :
- `assistant.chemin.preparer` est rejoué sur l'index du Mac, au même
  instant et au même format, pour la question de chaque ligne. Le journal
  note l'identifiant pour les 62 appels de l'évaluation, et le texte pour les
  3 de la démonstration ;
- **les 62 clés de cache de l'évaluation sont retrouvées**, ce qui prouve que
  l'entrée reconstituée est celle qui est partie. Les 3 appels de la
  démonstration ont été faits avec le prompt d'avant le palier 3 de la
  mission 08, plus court de deux consignes ;
- le script tourne en 7,7 s, pour 435 Mo de résident ;
- la commande officielle `assistant evaluer --estimer`, sans clé, dit de
  même : 62 en cache, 0 appel à faire.

Les chiffres :
- l'entrée réelle (non cachée, plus lue et écrite au cache) est de
  **3 582 jetons en moyenne** (de 2 581 à 6 142) ;
- les caractères (système et contenu) sont de 6 664 en moyenne ;
- **caractères par jeton réel** : moyenne **1,858**, médiane 1,862, de 1,731
  à 2,081. La constante 3,8 minorait d'un facteur 2,04 ;
- **la proposition** : `CARACTERES_PAR_JETON = 1,7`. À cette valeur,
  **aucun des 65 appels n'est sous-estimé**, et l'écart moyen est d'environ
  +9 %. Un modèle affine (319 jetons fixes, plus les caractères divisés par
  2,04) colle mieux (10,9 % d'écart au plus), mais il sous-estime la moitié
  des appels : je l'écarte, la porte devant rester prudente ;
- la prose d'avis se découpe sans doute mieux que les codes des fiches : la
  constante resterait prudente. Je le vérifierai sur les appels de la
  démonstration.

**Le coût d'une question qui porte des fragments d'avis** :
- un fragment d'avis fait ≈ 1 300 caractères avec son étiquette, contre
  ≈ 520 pour un fragment de fiche ;
- avec trois fragments d'avis sur dix, l'entrée fait ≈ 9 000 caractères,
  soit ≈ 4 800 jetons, soit **≈ 0,025 $ probables** et 0,101 $ prudents ;
- avec dix fragments d'avis (le pire), l'entrée fait ≈ 14 500 caractères,
  soit **≈ 0,036 $ probables** et 0,114 $ prudents ;
- aujourd'hui, c'est 0,016 $ réels et 0,087 $ estimés.

**L'évaluation complète** : le cache de la mission 08 ne sert plus, puisque
l'index change.
- La **v1** fait 62 appels : **≈ 1,3 à 1,6 $ probables**, ≈ 6,3 $ prudents.
- La **v2** reprend les 88 questions de la v1 au même texte. Sur le même
  index, avec le même prompt, elles sont **en cache** : la v2 n'ajoute que
  ses ≈ 45 appels nouveaux, soit **≈ 1,1 $ probables** et ≈ 4,6 $ prudents.

**Le plan de dépense**, sur 10 $, avant le 16/11 (UTC). Il passe à
`MISSION = 9` et `PLAFOND = 10.0`, sur le même journal.

| quand | quoi | probable | porte (prudente) |
|---|---|---|---|
| palier 1 | rien | 0 $ | — |
| palier 2, vers le 04/11 | la démonstration de 5 questions (dont 1 refus, sans appel) | ≈ 0,10 $ | ≈ 0,45 $ |
| palier 3, vers le 07/11 | l'évaluation complète de la v1 | ≈ 1,5 $ | ≈ 6,3 $, sur ≈ 9,9 $ restants |
| palier 3 | la v2 (questions nouvelles seulement) | ≈ 1,1 $ | ≈ 4,6 $, sur ≈ 8,4 $ restants |
| **total** | | **≈ 2,7 $** | |
| réserve | un second passage complet si un défaut se trouve, comme à la mission 08 | ≈ 2,6 $ | il passe la porte, de peu (v1 : ≈ 6,3 $ sur ≈ 7,3 $ restants) |

Si la porte devait bloquer, le levier serait `max_tokens`. Passer de 4 000 à
2 000 (sortie observée : 661 jetons au plus) divise par deux la part de
sortie de l'estimation. Je ne le propose pas d'emblée : cela change la clé
du cache, et le risque de troncature.

**Question I1** : la constante 1,7 (prudente sur les 65 appels) est-elle
retenue ?
**Question I2** : le plan de dépense, avec une réserve pour un second
passage, convient-il ?

## J. Les PDF

**Constat** (requêtes 8 à 12) :
- **La chaîne de redirection** : le lien du document (`/jcms/p_4072399/fr/…`)
  répond **302** vers `doXiti.jsp?id=p_4072399`, une page de **mesure
  d'audience**. Celle-ci répond 200 en `text/html` : 549 octets qui chargent
  le traceur AT Internet (`tag.aticdn.net`), puis
  `<META http-equiv="Refresh" content="0; URL='../../../../upload/docs/evamed/CT-21681_…_AvisDef_CT21681.pdf'">`.
  Le PDF répond 200, en `application/pdf`, pour **631 564 octets**, avec un
  `Last-Modified` égal à la mise en ligne.
- Le document de 2015 (`c_2027376`) passe par le même 302.
- **Le JSON-LD donne l'URL directe du PDF** (`hasPart[].contentUrl`), la même
  que celle de la redirection. Une future collecte ferait donc **une requête
  par PDF**, sans le 302, sans la page de mesure d'audience et sans son
  traceur.
- **Chaque page liste de 1 à 4 PDF** : l'avis
  (`/upload/docs/evamed/CT-…_AvisDef_….pdf`, ou `Avis1` en 2015), la
  transcription de la séance, les contributions d'associations, et un résumé
  en anglais (« SUMMARY »). Seul l'avis compte.
- **Un seul PDF mesuré** : l'extrapolation est mince.

**Les questions v2 qui demandent le PDF.** Les ≈ 24 questions sur le texte
sont écrites depuis la page : aucune ne le demande, par construction. Pour
mesurer le besoin, je propose **3 questions** dont la réponse n'est que dans
l'avis complet (la population cible chiffrée, le critère de jugement d'une
étude, le détail d'un comparateur). Elles attendent une abstention motivée
(« la page de l'avis ne le dit pas ; l'avis complet, oui »).

**Ma recommandation** : pas de mission PDF, sauf si l'usage ou la v2 montre
qu'une part notable des questions sur les avis en a besoin. Le chiffrage
d'une telle mission :
- 722 requêtes par `contentUrl`, ≈ 27 min ;
- ≈ 0,45 Go, à 0,6 Mo par PDF, à remesurer sur un échantillon ;
- une dépendance pour lire le PDF, à justifier au titre de l'ADR 0009 ;
- des PDF de 20 à 60 pages, soit ≈ 40 000 à 90 000 fragments de plus : un
  index qui double, un encodage de 25 à 45 min, et sans doute le retour à la
  recherche approchée (HNSW) ;
- une mission et une ADR à elles.

## K. La mémoire et le temps

| commande | sur le jeu | sur la première étape (Mac) | base de l'estimation |
|---|---|---|---|
| `has collecter --simuler` | < 100 Mo, < 2 s | idem | trois fichiers BDPM lus et triés |
| `has collecter` (beko) | — | < 150 Mo, **≈ 26 min** | une page en mémoire à la fois ; 0,15 s de réponse et 2 s de pause |
| `has extraire` (et `--verifier`) | ≈ 150 pages, < 1 s | 722 pages, **3,6 s, 19 Mo** | prototype mesuré |
| `index fragments` (sous-processus) | ≈ 416 Mo + ε | idem | le gold domine (ADR 0011) ; les pages se lisent une à une |
| `index construire` (format 3) | 72 296 repris du cache, ≈ 1 000 encodés : ≈ 1 min | ≈ 4 700 encodés : ≈ 2 à 3 min | 15 ms par fragment, doublé pour la prose longue ; 415 Mo mesurés pour l'encodage |
| `index verifier` | ≈ 420 Mo | idem | inchangé, plus la reconstruction des avis |
| `assistant evaluer --estimer` | ≈ 440 à 470 Mo | — | 439 à 462 Mo aujourd'hui ; le contenu plus long ajoute peu |

Toutes ces valeurs sont **à mesurer** sous `/usr/bin/time -l` à chaque
palier. Le point à surveiller est `evaluer --estimer`, déjà à 462 Mo pour un
seuil de 512 Mo.

## L. Autre

1. **Les conditions de réutilisation**, d'après ce que j'ai lu :
   - `robots.txt` est **inchangé** depuis le 26/10 : 109 octets, mêmes deux
     interdits (ADR 0004). Il n'interdit ni `/jcms/p_…`, ni `/jcms/c_…`, ni
     `/upload/`, ni `/plugins/ModuleXitiKLEE/` ;
   - le lien « Mentions légales » du pied de page est toujours `c_518191`.
     **Je n'ai pas relu les mentions légales**, qui n'étaient pas dans la
     liste des requêtes. Leur contenu n'est attesté qu'au 26/10. La relecture
     peut se faire par la collecte de beko (C2) ;
   - rien n'est donc rouvert dans l'ADR 0004 à ce jour.
2. **La licence et le dépôt public.** Les fixtures et le sous-ensemble du jeu
   reproduisent des pages HTML **entières**, sans altération. Les mentions
   légales demandent, pour la reproduction d'un document entier, la date et
   la mention « document de la Haute Autorité de santé, disponible sur … ».
   Elles sont dans `tests/fixtures/README.md` et iront dans le `README` du
   jeu. **À valider par l'IeC.**
3. **`CLAUDE.md`, « Données »**, dit « des fichiers BDPM » pour le jeu de
   démo. Les pages de la HAS (le jeu et `tests/fixtures/has/`) demandent
   d'élargir la ligne (E1). C'est un chemin réservé : je le propose, je ne
   l'écris pas.
4. **Le fichier des liens est en retard** sur les avis. Sur les 26 dossiers
   de 2024 et après sans lien, 15 datent de septembre 2025, et OZEMPIC
   (CT-21716, `avis_has-003`) en fait partie. Une page arrive 11 à 37 jours
   après l'avis, et le fichier des liens ensuite.
5. **Une page ne se compare pas par son sha256**, qui change à chaque
   réponse (jeton CSRF, horodatage). Toute revisite future comparera
   l'empreinte du texte extrait. Je propose de l'écrire au manifeste dès
   cette mission.
6. **Le traceur de mesure d'audience** n'est jamais exécuté par nos
   clients, qui ne lancent pas de JavaScript. Le passer par `contentUrl`
   l'évite même côté serveur (J).
7. **Le texte d'un avis nomme d'autres médicaments** : le comparateur
   (TRULICITY), d'autres molécules (metformine, liraglutide). La recherche
   lexicale peut ramener l'avis de MOUNJARO à une question sur TRULICITY :
   la porte structurelle et la déduplication (G) le contiennent, et la v2
   le mesurera.
8. **Le script des douze requêtes** (`tests/fixtures/has/requetes_s0.py`)
   reste dans le dépôt, avec son journal. Il ne peut plus rien demander,
   puisque le journal est plein. `ruff check` et `ruff format --check` sont
   verts sur lui ; il est hors de `src`, donc hors de mypy.
9. **Une proposition** : rien dans l'ordre ne pose d'en-tête `From:` (un
   contact) dans les requêtes. Le `User-Agent` porte l'URL du dépôt, qui
   suffit à joindre le projet. Je n'en ajoute pas.

## Récapitulatif des questions

| # | point | question | ma proposition |
|---|---|---|---|
| A1 | date citée | La date de mise à jour citée est-elle « Mis en ligne le » (ou « Mis à jour le ») ? | oui, à côté de la date de l'avis et de la collecte |
| C1 | collecte | Les codes 0, 1, 2, 3 et un seul réessai conviennent-ils ? | oui |
| C2 | collecte | `robots.txt` seul par passage, ou aussi les mentions légales ? | `robots.txt` seul dans cette mission ; les mentions à chaque collecte de beko si l'IeC le veut (une requête) |
| D1 | extraction | Toutes les sections du corps, stratégie thérapeutique comprise ? | oui, garde médicale en amont |
| D2 | extraction | Recalculer ou stocker l'extraction ? | recalculer |
| E1 | jeu | Les pages sous `demo/archive` ou `demo/has` ; et la ligne de `CLAUDE.md` ? | `demo/archive`, manifeste à part ; `CLAUDE.md` revu par l'IeC |
| F1 | index | Un fragment par (page, CIS, partie), ou par (page, partie) ? | par (page, CIS, partie) |
| F2 | index | Remesurer `avgdl` au format 3 ? | oui, avec `index evaluer` avant et après |
| F3 | index | Les deux horloges rendues ? | oui |
| G1 | assistant | Dates omises : la consigne du prompt, ou compter la date rendue par le code ? | la consigne du prompt |
| G2 | assistant | Durée de traitement selon l'avis : réponse ou refus ? | réponse citée |
| G3 | assistant | Une comparaison tirée d'un avis donne « deux médicaments » : garder ? | garder, et en faire un piège |
| H1/H2 | v2 | La v1 reprise sous ses identifiants ; l'attendu `has.avis` et la notation ? | oui |
| I1/I2 | coût | La constante 1,7 ; le plan de dépense ? | oui |
