# ADR-0013 — Corpus HAS : collecte des pages d'avis, extraction, fragments d'avis, rendu des liens

**Statut :** accepté · **Date :** 2026-11-01 · **Mission :** 09
**Remplace / remplacé par :** — · **Complète :** ADR 0004 (le corpus HAS), ADR 0011 (l'index),
ADR 0012 (l'assistant)

## Contexte

L'ADR 0004 a choisi les pages HTML d'avis de la Commission de la transparence (CT) comme corpus,
et leur licence : réutilisation libre, sans altération, avec la source et la date de dernière
mise à jour. La mission 09 en fait la **première étape** : les dossiers avec un avis SMR ou ASMR
daté de 2024 ou après, liés par `HAS_LiensPageCT_bdpm.txt`. Cela fait 746 dossiers, dont 720
avec un lien, et 722 pages.

Mesures de la mission :
- **le passage de beko** (31/10/2026) : 724 requêtes sur un plafond de 761, 25 min 56 s,
  101,5 Mio de résident maximal. 722 pages archivées, 0 erreur ;
- **l'extracteur v2** : 721 pages extraites, 1 rejetée, 10 contrôles de dossier impossibles ;
- **le jeu de démo** : 150 de ces pages, 1 543 fragments d'avis ;
- **la première étape entière** : 6 165 fragments d'avis.

## Décision

### La collecte (`pharmaflux has collecter`)

- **La politesse** :
  - `robots.txt` est lu à chaque passage, et un chemin interdit n'est jamais demandé ;
  - un `Crawl-delay` qui vise notre `User-Agent` allonge la pause du client, jamais ne
    l'abrège ; un délai décimal est arrondi au-dessus ;
  - les requêtes partent en série, avec deux secondes de pause au moins ;
  - aucune redirection n'est suivie ;
  - le plafond est explicite, et passer `--plafond` est obligatoire ;
  - la collecte s'arrête net au premier 429, ou au second 5xx d'affilée (un réessai après
    10 s).
- **Les mentions légales** sont relues à chaque passage réel. Si leur texte change, c'est
  signalé en tête du bilan.
- **L'archive** suit la règle du bronze : chaque page est gardée à l'octet, compressée, sous
  `bronze/has/pages/<page>/`. Le manifeste `manifeste/has-pages.jsonl` est en ajout seul ; il
  porte l'empreinte du texte extrait et la version de l'extracteur.
- **La reprise** : une page archivée n'est jamais redemandée, et une archive orpheline est
  adoptée sans requête.
- **La simulation** (`--simuler`) donne le plan et le plafond conseillé, sans requête.
- **Les codes de sortie** : 0 complet, 1 erreurs de pages, 2 refus, 3 arrêt net.

### L'extraction (`has.extraction`, version 2)

- **La lecture** se fait par `html.parser`, bloc par bloc et dans l'ordre de la page. Toutes
  les sections du corps sont gardées, mot pour mot ; seules les espaces et les entités se
  normalisent.
- **Le JSON-LD** sert de contrôle, jamais de texte. Douze motifs de rejet, dont deux
  contrôles, comptés et rendus :
  - le nom, comparé après décodage des entités ;
  - le dossier : chaque dossier qui lie la page doit être nommé par son document d'avis. Tous
    les numéros d'un avis commun sont lus (« & » ou « _ »).
- **La version** de l'extracteur change avec ce qu'il rend **ou refuse**. `has extraire
  --verifier` compare le texte au manifeste quelle que soit la version, et liste à part les
  statuts changés.
- **La non-altération** se prouve par un second lecteur, sans code commun avec l'extracteur.
- **L'index réextrait** les pages à chaque construction ; il ne lit jamais la sortie de
  `has extraire`.

### Les fragments d'avis (index au format 3)

- **Le découpage** : un fragment par (page, CIS, partie), dans la section `avis_has`, avec
  l'identifiant `f3/<cis>/avis_has/<page>/<partie>`. L'invariant « un fragment, un CIS » des
  ADR 0011 et 0012 tient.
- **Le texte** commence par la ligne d'identité et une ligne d'en-tête à nous (titre, dossier,
  date de l'avis, mise en ligne), répétées à chaque partie, puis les lignes de la page. La
  découpe se fait sous 1 200 caractères. Une ligne trop longue (jusqu'à 1 781 caractères) se
  coupe entre deux phrases, mot pour mot : au plus 381 jetons e5. **Aucune URL dans le texte.**
- **Le rattachement** : une page se rattache à un CIS par les liens de la BDPM **à l'instant
  du silver**, jamais l'inverse. Le contrôle de dossier se refait fiche par fiche.
- **L'avgdl de BM25** est remesurée une fois, à 55,44 (fiches et avis). Elle ne fait perdre
  aucun rappel à 10 et gagne au rappel à 5.
- **Les deux horloges** : l'état de l'index porte l'instant du silver **et** la position du
  manifeste HAS (lignes, empreinte du préfixe), avec la dernière collecte.
  - La mise à jour touche les CIS des pages arrivées.
  - Un préfixe changé ou un autre extracteur impose la reconstruction.
  - `make index` reconstruit un index d'un autre format.
- **La mémoire** reste sous 512 Mo. Les textes absents du cache sont encodés **avant**
  l'écriture, et le modèle se charge au premier besoin puis se rend. La vérification réencode
  son échantillon **avant** de lire les points. Mesures :
  - le jeu : `construire` 493 Mo, `verifier` 496 Mo ;
  - la première étape entière (78 461 fragments) : 471 Mo et 483 Mo.

### L'assistant

- **Le LLM ne voit aucune URL.** Les adresses que cite le texte d'un avis sont masquées à
  l'envoi, et une adresse écrite par le LLM rend sa réponse non vérifiable.
- **Le code rend le lien** de chaque fragment cité :
  - la page d'avis avec ses trois dates (avis, mise en ligne ou mise à jour, consultation),
    comme l'exige la licence ;
  - les liens d'une fiche ;
  - les deux horloges de l'index.
- **La clause « Liens hypertextes »** des mentions légales (relue le 31/10/2026) se lit ainsi :
  - la CLI rend un lien en texte et n'inclut aucune page ;
  - la reproduction des pages dans `demo/` et dans les fixtures relève de la clause de
    reproduction (intégralité, date, mention de la HAS) ;
  - **l'interface de la mission 10** ouvre le lien dans une nouvelle fenêtre, et jamais dans un
    cadre (`iframe`).
- **Le prompt** demande la date de chaque fait daté, et traite l'avis comme une évaluation
  collective, jamais pour une personne.
- **La sélection des dix fragments** :
  - une même (page, partie) ne compte qu'une fois ;
  - le rappel par section joint la première partie de la section demandée pour le CIS visé le
    mieux classé ;
  - sa table envoie « SMR » et « ASMR » vers le fragment `avis` seul.
- **Le refus médical** couvre la dose, la durée, le rythme et le mode de prise, même « selon
  l'avis », ainsi que la convenance pour une personne.

### Les PDF d'avis : pas de collecte

La page suffit aux questions sur le texte : les 19 questions de la v2 sont écrites depuis elle.
Trois questions demandent ce que seul le PDF porte (le vote, la population cible, les
comparateurs) : elles attendent une abstention motivée. Une mission PDF, si l'usage la
demandait, coûterait :
- 722 requêtes (le `contentUrl` du JSON-LD, sans le 302 ni la page de mesure d'audience),
  environ 27 min ;
- environ 0,45 Go ;
- une dépendance de lecture de PDF ;
- 40 000 à 90 000 fragments de plus, c'est-à-dire un index qui double.

C'est une mission et une ADR à elles.

### Le coût

`CARACTERES_PAR_JETON = 1,7`, recalé sur les 65 appels de la mission 08, dont l'entrée est
reconstituée sans API. À cette valeur, aucun appel n'est sous-estimé, avec un écart moyen de
+9 %. La v2 complète, seule, passerait la porte au pire (10,55 $ estimés, pour 10 $) : elle se
lance après la v1, dont elle relit les 62 appels du cache.

## Conséquences

- L'assistant cite le texte d'un avis de la HAS avec sa page et ses dates, rendues par le code,
  sans jamais écrire une adresse.
- **Limites, écrites ici** :
  - **19 faux rattachements possibles par avis commun.** Un dossier qu'un avis commun nomme
    serait accepté pour toute page de cet avis : c'est voulu, l'avis le couvre. Une contre-épreuve
    sur 3 608 faux rattachements essayés en accepte 69 (50 sur des pages sans numéro, 19 par avis
    commun).
  - **Dix pages sans contrôle de dossier.** Leur document d'avis ne porte aucun numéro lisible :
    elles sont acceptées, comptées et listées dans le bilan et dans l'état.
  - **La cible du rappel** est le CIS visé le mieux classé. Quand plusieurs CIS d'un même nom
    sont visés (WEGOVY, OZEMPIC), le rappel peut servir une autre dose que celle de la question.
    Une heuristique de plus a été refusée (contrôle du palier 2, question 2).
  - **La table des sections** fait l'union des lignes qui correspondent. Une question qui dit à
    la fois « SMR » et « Commission » demande encore `avis_has`, qu'un avis plus ancien peut
    satisfaire.
  - Ajouter les avis coûte **un rang à 1** sur la v0 et la v1 de la recherche.
- **À surveiller** : un changement de `robots.txt` ou des mentions légales rouvre l'ADR 0004, et
  un changement de structure des pages se voit dans les rejets.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| Un fragment par (page, partie) avec une liste de CIS | casse « un fragment, un CIS » (ADR 0011, 0012) : retirer les points d'un CIS en retirerait d'un autre |
| Garder la règle v1 « le document ne nomme aucun autre dossier » | rejette tout avis commun (5 pages sur 722), et laissait passer sans contrôle les libellés à « _ » |
| Lire la sortie de `has extraire` dans l'index | deux vérités ; l'extraction se recalcule (addendum D2) |
| Un analyseur HTML tiers | `html.parser` suffit (ADR 0009) |
| Une cible du rappel par recouvrement de la dénomination | réglée sur la question qui la motive (contrôle du palier 2) |
| Collecter les PDF dès cette mission | hors périmètre ; coût chiffré plus haut |

## Références

ADR 0004, 0009, 0011, 0012 · ordre de mission 09 et son addendum 1 ·
`docs/rapports/mission-09/` (§0, paliers, collecte, correction de l'extracteur) ·
`docs/relectures/mission-09/controle-palier-1.md`, `controle-palier-2.md`.
