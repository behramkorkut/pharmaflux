# Mission 09 — collecte de la première étape : la sortie de beko, les huit rejets, les mentions légales

## Synthèse

**Passage `20261031T124148Z`, lancé par beko sur l'archive du Mac** : 724 requêtes sur un
plafond de 761, toutes en 200, sans réessai ; 25 min 56 s ; 101,5 Mio de résident maximal.
722 pages archivées, 0 en erreur ; **8 rejetées à l'extraction** ; `has extraire --verifier` :
714 extraites, 0 écart, 0 divergence. Code de sortie absent du journal, déduit : 0.
**Les huit rejets** : sept viennent d'un **contrôle trop strict** de l'extracteur. Deux noms
JSON-LD gardent une entité `&lt;`. Cinq pages portent un avis commun à plusieurs dossiers.
Le huitième (PEDMARQSI) est un **vrai défaut de la page** : son document d'avis porte un autre
numéro de dossier que tout le reste de la page. **Correction proposée, non appliquée** : 721
pages extraites, PEDMARQSI toujours rejetée, aucun texte accepté modifié.
**Mentions légales** : conditions de réutilisation inchangées depuis le 26/10, l'ADR 0004 n'est
pas rouvert. Une clause qu'il ne note pas (liens dans une nouvelle fenêtre) concerne le palier 2.
**Aucune requête de plus vers la HAS** : tout ce qui suit est lu dans l'archive, sans y écrire.

## 1. La sortie de beko

Le journal `data/has-collecte-premiere-etape.log` (747 lignes), cité sans retouche pour le
bilan et `time -l` (les 724 lignes de requêtes `httpx` sont comptées, pas recopiées) :

```text
passage HAS 20261031T124148Z : 724 requête(s) sur un plafond de 761, 25 min 56 s
robots.txt : nouveau (109 octets, sha256 a66da4379296…)
mentions légales : pas encore de référence (premier passage) ; texte archivé
pages : 722 à demander ; 722 archivée(s) (dont 8 rejetée(s) à l'extraction : dossier_incoherent 6, nom_incoherent 2), 0 en erreur, 0 interdite(s) par robots.txt, 0 archive(s) orpheline(s) reprise(s), 0 non demandée(s)
     1556.76 real        15.96 user         2.30 sys
           106463232  maximum resident set size
```

Le journal `data/has-extraire.log` :

```text
722 page(s) : 714 extraite(s), 8 rejetée(s) (dossier_incoherent 6, nom_incoherent 2) ; extracteur v1
non-altération : 714 conforme(s), 0 avec écart ; déterminisme et empreintes du manifeste : 0 divergence(s)
```

| mesure | valeur |
|---|---|
| requêtes | 724 = `robots.txt` + mentions légales + 722 pages ; 37 de marge sous le plafond |
| réponses | 724 en HTTP 200, 724 à un seul essai, aucune redirection |
| pause entre deux requêtes | 2,11 s au moins, 4,18 s au plus, 2,15 s en moyenne (estimation du palier 1 : 2,15 s) |
| durée | 12:41:48Z → 13:07:44Z ; estimée ≈ 26 min à la simulation |
| mémoire | 106 463 232 octets de résident maximal ; 15,96 s de calcul pour 1 556,76 s réelles |
| archive | 722 pages, 59,2 Mo de HTML, 13 Mo compressés sous `bronze/has/pages/` |
| manifeste | 724 lignes, un seul passage, extracteur v1 sur les 722 pages |

**Code de sortie** : il n'est pas dans le journal. Le `tee` final du tuyau le masque, et
`time -l` ne l'imprime pas. Il se déduit de la règle de `Bilan.code_sortie`
(`src/pharmaflux/has/collecte.py:114`) : ni ligne `REFUS`, ni ligne `ARRÊT NET`, 0 en erreur,
donc **0**. Pour les prochains passages, la ligne qui suit la commande le consigne (zsh) :
`c=${pipestatus[1]}; echo "code de sortie : $c" | tee -a <journal>`.

**`robots.txt`** : 109 octets, identique à l'octet à la fixture du §0
(`tests/fixtures/has/robots.txt`, même sha256 `a66da4379296…`), même taille que le 26/10, sans
`Crawl-delay`. Le palier 2 en tiendra compte s'il en apparaît un.

## 2. Les huit rejets, un par un

Chaque page a été relue dans son archive et la BDPM du 24/10 a été consultée. Aucune page n'est
liée par plus d'un dossier BDPM. Le contrôle `nom_incoherent` compare le `name` du JSON-LD à
« Avis sur » + le `<h1>`. Le contrôle `dossier_incoherent` refuse une page dont le libellé du
document d'avis (`…_AVIS_CT…` dans `hasPart`) nomme un dossier qui ne la lie pas.

| # | page | dossier BDPM | motif | ce qui diffère | verdict |
|---|---|---|---|---|---|
| 1 | `p_3892357` XALKORI, pédiatrie | CT-21340, avis du 18/02/2026 | `nom_incoherent` | le `name` JSON-LD écrit `à &lt; 18 ans`, le `<h1>` `à < 18 ans` ; le reste est identique, et le libellé de l'avis nomme bien CT21340 | **contrôle trop strict** |
| 2 | `p_3638197` KEPPRA, épilepsie | CT-21259, 16/07/2025 | `nom_incoherent` | même cas : `(&lt; 4 ans)` contre `(< 4 ans)` ; libellé CT21259 | **contrôle trop strict** |
| 3 | `p_3687274` NIMENRIX | CT-21402, 10/09/2025 | `dossier_incoherent` | avis commun aux cinq vaccins méningococciques, `…_AVIS_CT21541&21424&21540&21402&21567` ; l'extracteur ne lit que le premier numéro (CT-21541, BEXSERO, dont la page `p_3686940` est acceptée) ; CT-21402 est bien nommé | **contrôle trop strict** |
| 4 | `p_3686928` MENQUADFI | CT-21424, 10/09/2025 | `dossier_incoherent` | même avis commun ; CT-21424 nommé | **contrôle trop strict** |
| 5 | `p_3686943` MENVEO | CT-21540, 10/09/2025 | `dossier_incoherent` | même avis commun ; CT-21540 nommé | **contrôle trop strict** |
| 6 | `p_3686931` TRUMENBA | CT-21567, 10/09/2025 | `dossier_incoherent` | même avis commun ; CT-21567 nommé | **contrôle trop strict** |
| 7 | `p_3530986` FINLEE / SPEXOTRAS, gliome | CT-20695, 10/07/2024 | `dossier_incoherent` | avis commun `…_AVIS_CT20655&20695` ; CT-20655 (CIS 61606482) a son SMR et son ASMR dans la BDPM mais aucun lien | **contrôle trop strict** |
| 8 | `p_3608587` PEDMARQSI | CT-21223, 28/05/2025, SMR insuffisant | `dossier_incoherent` | le libellé de l'avis est `PEDMARQSI_28052025_AVIS_CT21123`. Le même document a pour fichier `CT-21223_…_AvisDef_modifiele03062025_CT21223 1.pdf`. Les deux transcriptions et la synthèse disent CT21223. **CT-21123 n'existe pas dans la BDPM** du 24/10 (ni SMR, ni ASMR, ni lien) | **vrai défaut de la page** |

**Les deux `nom_incoherent`** : le CMS laisse l'entité HTML dans le JSON-LD, où rien ne la
décode (le contenu d'un `<script>` n'est pas du HTML), tandis que le `<h1>` est décodé par le
lecteur. L'ordre dit que « les entités HTML se normalisent » : le contrôle aurait dû comparer
après décodage. Le texte extrait de ces deux pages ne contient rien du JSON-LD : il n'est pas en
cause.

**Les cinq avis communs** : deux défauts s'ajoutent. Le motif `_AVIS_CT-?(\d{4,6})\b` ne lit que
le premier numéro. Et la règle « le document ne nomme aucun autre dossier » refuserait de toute
façon un avis commun, même lu en entier, puisqu'il nomme les dossiers voisins. En passant, deux
**trous silencieux** se sont montrés :
- le libellé `NICORANDIL_08072026_AVIS_CT21823_21827_21832_21871_21883` (cinq pages) n'est pas lu
  du tout, car `\b` ne sépare pas un chiffre d'un `_`. Ces cinq pages sont acceptées **sans
  contrôle** ;
- dix pages n'ont aucun numéro lisible et passent aussi sans contrôle : sept DESOGESTREL
  (`…_AVIS_CT-EVAL587`, une réévaluation de classe), deux sans document et une avec seulement sa
  synthèse.

**PEDMARQSI** : la page se contredit sur le dossier de son avis. Choisir le bon numéro serait
deviner, ce que l'ordre exclut. Le rejet est donc le bon résultat, et **c'est le candidat de la
question piège « page rejetée »** du jeu v2 : un avis dont la BDPM donne le SMR (insuffisant,
28/05/2025) mais dont le texte n'est pas dans le corpus.

## 3. La correction proposée (non appliquée, en attente de ta réponse)

Deux changements dans `src/pharmaflux/has/extraction.py`, rien d'autre :

1. **Nom** : comparer `normaliser(html.unescape(nom))` à `Avis sur <titre>`. Une page dont le
   JSON-LD décrit un autre avis reste rejetée.
2. **Dossier** : lire tous les numéros du libellé de l'avis, séparés par `&` ou `_`
   (`_AVIS_CT-?(\d{4,6}(?:[&_]\d{4,6})*)(?!\d)`). Puis renverser la règle : **chaque dossier
   BDPM qui lie la page doit être nommé par le document d'avis**, au lieu de « le document ne
   nomme aucun autre dossier ». Un libellé sans numéro lisible reste sans contrôle, comme en v1.
   Message : « le document d'avis nomme CT-21123, pas CT-21223 ».

Les deux règles disent la même chose quand le libellé ne porte qu'un numéro (699 des 726
libellés d'avis lus) et que la page n'a qu'un dossier BDPM (722 pages sur 722). Le relâchement
ne touche donc que les avis communs qui nomment le dossier de la page : de tels avis couvrent ce
dossier, par définition.

**Preuve**, par un script hors du dépôt qui lit les 722 archives sans rien écrire, `src/` intact :

| mesure | v1 (passage de beko) | proposée |
|---|---|---|
| extraites | 714 | **721** |
| rejetées | 8 (`nom` 2, `dossier` 6) | **1** (`dossier_incoherent` : PEDMARQSI) |
| issues changées | — | 7, exactement les pages 1 à 7 ci-dessus ; aucune page acceptée ne devient rejetée |
| empreinte du texte des 714 | — | identique pour les 714 : le texte n'est pas touché |
| pages acceptées sans contrôle de dossier | 15 (10 sans numéro + 5 NICORANDIL) | 10 (sans numéro) |
| contre-épreuve : 3 608 faux rattachements (chaque page reçoit le dossier BDPM d'une autre, décalage de 1 à 5) | 78 acceptés | **69 acceptés** : 50 sur les 10 pages sans numéro (comme en v1), 19 dont le dossier prêté est nommé par le même avis commun ; tous les autres rejetés |

`dossiers_documents` (une métadonnée, hors empreinte) devient complet pour 13 pages : les cinq
NICORANDIL, les cinq vaccins, FINLEE / SPEXOTRAS, EVENITY, IXPRIM / ZALDIAR.

**Version de l'extracteur** : je propose de **la garder à 1**, et d'écrire la règle à côté de la
constante : la version change quand le texte ou les dates d'une page déjà acceptée changent.
L'empreinte contient la version. Avec une v2, `has extraire --verifier` ne comparerait plus les
714 empreintes du manifeste, et c'est précisément la preuve que la correction ne touche aucun
texte accepté. En gardant v1, cette preuve se lit dans la sortie de la commande. Le manifeste
garde le rejet v1 des sept pages comme l'histoire du passage. L'autre voie (v2, comparaison
perdue jusqu'au prochain passage) se défend aussi : à toi de trancher.

**Après ton accord** :
- quatre fixtures reprises à l'octet de l'archive du Mac, soit 16 à 17 Ko compressées
  chacune : `p_3638197` (KEPPRA, entité), `p_3687274` (NIMENRIX, avis commun `&`), `p_4335961`
  (NICORANDIL, avis commun `_`), `p_3608587` (PEDMARQSI, rejet maintenu) ;
- des tests : nom à entité accepté, nom différent toujours rejeté ; avis commun accepté avec son
  dossier et rejeté avec un dossier qu'il ne nomme pas ; PEDMARQSI rejetée avec son message ;
- puis `has extraire --verifier` sur l'archive du Mac, en lecture, sortie dans `data/`.
  Attendu : 722 pages, 721 extraites, 1 rejetée, 0 écart, 0 divergence.

**Aucune requête** : les sept pages sont déjà archivées, et l'extraction se rejoue sur l'archive.

## 4. Les mentions légales, relues contre l'ADR 0004

L'archive `bronze/has/mentions-legales/2026-10-31/20261031T124150Z__e08f63449332.html.gz` pèse
69 897 octets, la taille relevée le 26/10 (ADR 0004, requête 5). Le texte de `<main>` fait
4 795 caractères, empreinte `2c27112614ea…`. C'est la référence du passage C2 suivant.

| point de l'ADR 0004 | texte du 31/10 |
|---|---|
| article mis en ligne le 01/10/2015 | inchangé (« Mis en ligne le 01 oct. 2015 », sans date de mise à jour) |
| hors contenus de tiers, informations publiques librement et gratuitement réutilisables, CRPA art. L 321-1 et suivants | inchangé ; les contenus de tiers demandent un accord préalable |
| condition : ni altération ni sens dénaturé, source et date de dernière mise à jour mentionnées | inchangé |
| reproduction d'un document entier avec la charte et le logo : intégralité, date, mention « document de la Haute Autorité de santé… », logo | inchangé |
| le paragraphe sur l'IA générative vise l'usage de la HAS elle-même | inchangé : outils internes, relecture humaine, aucune décision individuelle sur le seul fondement d'un traitement automatisé |
| — | aucune réserve de fouille de textes ou d'opposition aux robots dans le texte |

**Verdict** : les conditions de réutilisation n'ont pas changé depuis le 26/10. Une limite : la
réponse du 26/10 n'a pas été archivée, la comparaison se fait donc contre le résumé de l'ADR et
non à l'octet. Désormais l'empreinte `2c27…` le permet.

**Une clause que l'ADR 0004 ne note pas**, sous « Liens Hypertextes » : un lien vers
has-sante.fr est permis s'il s'ouvre dans une nouvelle fenêtre, et les pages du site ne doivent
jamais être incluses dans un autre site. Elle ne change rien à la collecte, mais elle touche le
palier 2 : les liens que rend le code de l'assistant s'ouvriront dans une nouvelle fenêtre, sans
cadre ni inclusion. Je propose de l'ajouter à l'ADR 0004 ou de la reprendre dans l'ADR 0013 :
à toi de dire où.
