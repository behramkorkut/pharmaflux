# Profil — les pages d'avis de la Commission de la transparence (has.avis)

Pages HTML d'avis de la HAS, `https://www.has-sante.fr/jcms/p_N`, que donne
`HAS_LiensPageCT_bdpm.txt` (ADR 0004, ADR 0013).

- **Archive** : la première étape du corpus, collectée par beko le 31/10/2026 (passage
  `20261031T124148Z`, 722 pages), sous `bronze/has/pages/` de `~/pharmaflux-data`. Le jeu de démo
  en reprend 150 (`demo/has-pages.txt`).
- **Lu** par l'extracteur v2 (`src/pharmaflux/has/extraction.py`), sans réseau, le 01/11/2026.
- Contenus de la Haute Autorité de santé, réutilisés selon ses mentions légales (article du
  01/10/2015, relu le 31/10/2026) : document de la Haute Autorité de santé, disponible sur
  <https://www.has-sante.fr>. Les chiffres ci-dessous sont des mesures, pas des extraits.

## Ce qu'est une page

Une page Jalios. Le corps (`div.content--main`) porte, dans l'ordre :
1. le titre (`<h1>`, « DÉNOMINATION (DCI) - Indication ») ;
2. le sous-titre « Avis sur les Médicaments - Mis en ligne le … », avec parfois « Mis à jour
   le … » ;
3. l'encart « Nature de la demande », puis le paragraphe de motif ;
4. les sections, sous leurs intertitres : « L'essentiel », « Quel progrès ? », « Quelle place
   dans la stratégie thérapeutique ? », « Recommandations particulières » ;
5. les tables du SMR et de l'ASMR (niveau, puis libellé).

Le JSON-LD `Review` donne la date de l'avis (`datePublished`), les documents (`hasPart`, dont le
PDF de l'avis et son libellé `…_AVIS_CT…`), les CIP13 et l'ATC. Il sert de **contrôle**, jamais
de texte.

## Mesures sur la première étape (722 pages)

| mesure | valeur |
|---|---|
| extraites / rejetées | 721 / 1 (`dossier_incoherent` : PEDMARQSI, le libellé de l'avis nomme CT-21123) |
| octets bruts d'une page | 69 947 au moins, 81 166 en médiane, 120 384 au plus ; 59,2 Mo en tout |
| texte rendu d'une page | 439 caractères au moins, 2 886 en médiane, 19 545 au plus |
| année de l'avis (`datePublished`) | 2023 : 1 ; 2024 : 268 ; 2025 : 249 ; 2026 : 203 |
| mise en ligne après l'avis | 1 jour au moins, 19 en médiane, 375 au plus ; « Mis à jour le » affiché sur 13 pages |
| CIP13 dans le JSON-LD | 0 à 25 par page, 2 en médiane |
| documents d'avis sans numéro de dossier lisible | 10 (contrôle de dossier impossible : listées par `has extraire`) |
| avis communs à plusieurs dossiers | 13 pages (« & » ou « _ » dans le libellé) |

**Nature de la demande** : Inscription 469 ; Extension d'indication 139 ; Réévaluation suite à
résultats étude post-inscription 45 ; Réévaluation SMR et ASMR 32 ; Réévaluation SMR 15 ;
Modification des conditions d'inscription 7 ; Réévaluation ASMR 4 ; Nouvel examen suite au
dépôt de nouvelles données 3 ; et d'autres, plus rares.

**Les sections présentes** (sur 721) : la demande 721 ; SMR 719 ; ASMR 719 ; « L'essentiel »
718 ; « Quel progrès ? » 650 ; « Quelle place dans la stratégie thérapeutique ? » 436 ;
« Recommandations particulières » 202.

**Le texte est gardé tel quel, coquilles comprises.** Les intertitres du site en portent :
« L'esssentiel » (1 page), « Recommandations partciulières » (2), « Quel place dans la stratégie
thérapeutique ? » (2). L'extracteur ne les corrige pas, et une règle qui cherche « L'essentiel »
ne voit pas la page qui l'écrit autrement.

## Pièges

- **La date d'une page** est celle de **son** avis : un dossier peut lier deux pages (CT-20568
  d'ADEMPAS : l'avis de 2024 et une décision de 2025 sans SMR). Une page peut aussi dater d'avant
  la date du dossier dans la BDPM (une page de 2023).
- **Une ligne de texte** peut faire 1 781 caractères : l'index la coupe entre deux phrases.
- **Le texte d'un avis cite parfois une adresse** (`http://lecrat.fr/`, 3 fragments du jeu) :
  elle reste dans l'index, et elle est masquée pour le LLM.
