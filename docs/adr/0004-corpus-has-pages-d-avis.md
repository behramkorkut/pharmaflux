# ADR-0004 — Corpus HAS : les pages d'avis de la Commission de la transparence, les PDF en second

**Statut :** accepté · **Date :** 2026-10-26 · **Mission :** 01
**Remplace / remplacé par :** — · **Complété par :** ADR 0013 (la collecte, l'extraction, les
fragments d'avis, le rendu des liens et la clause « Liens hypertextes », mission 09)

## Contexte

L'assistant du Lot 3 doit citer les avis de la HAS (SMR, ASMR) avec leur
lien. La BDPM fournit `HAS_LiensPageCT_bdpm.txt` : **10 480 liens**, un seul
hôte (`www.has-sante.fr`), deux formes d'URL (`/jcms/c_N` 7 996, `/jcms/p_N`
2 484), un couple (dossier, lien) unique ; 86,5 % des dossiers SMR et
77,5 % des dossiers ASMR ont un lien (`docs/donnees/README.md`), et 745
dossiers SMR datent de 2024 ou après (§0 de la mission 01). Cinq requêtes
HAS, au plus, étaient permises pour cette mission ; toutes les cinq ont été
faites le 26/10/2026, en série, `User-Agent` du projet :

| # | heure UTC | URL | réponse | ce qu'elle apprend |
|---|---|---|---|---|
| 1 | 13:31:05 | `/robots.txt` | 200, 109 octets | deux chemins interdits seulement (`/jcms/fc_2875171/`, un export du plugin Scope Santé) : les pages d'avis ne sont pas interdites aux robots |
| 2 | 13:31:32 | `/jcms/p_4461003` (CT-21902, SUNITINIB BIOGARAN) | 200, HTML 77 465 octets | page de synthèse de l'avis : titre, motif, résumé (`description`), date (`datePublished` 2026-09-09), lien vers le document `p_4461002` « …avis-ct21902 » |
| 3 | 13:31:35 | `/jcms/c_2973834` (CT-17553, CELSIOR) | 200, HTML 77 776 octets | même structure pour la forme `c_N` (avis de 2019) : les deux formes sont des pages Jalios équivalentes |
| 4 | 13:35:15 | `/jcms/p_4461002/fr/sunitinib-biogaran-09092026-avis-ct21902` | **302** vers `/plugins/ModuleXitiKLEE/…/doXiti.jsp?id=p_4461002` | le document d'avis est servi derrière une redirection de mesure d'audience ; **non suivie**, le PDF n'a pas été téléchargé ni mesuré |
| 5 | 13:35:17 | `/jcms/c_518191/fr/mentions-legales` | 200, HTML 69 897 octets | conditions de réutilisation (ci-dessous) |

**Licence** (mentions légales, article mis en ligne le 01/10/2015) : hors
contenus de tiers, les contenus du site sont des informations publiques
librement et gratuitement réutilisables (code des relations entre le
public et l'administration, art. L. 321-1 et suivants), à condition de ne
pas les altérer ni en dénaturer le sens, et de **mentionner la source et la
date de dernière mise à jour**. La reproduction d'un document entier avec
la charte et le logo de la HAS impose l'intégralité, la date et la mention
« document de la Haute Autorité de santé, disponible … ». Le paragraphe sur
l'IA générative concerne l'usage que la HAS en fait elle-même, pas les
réutilisateurs.

## Décision

Le corpus HAS du Lot 3 est constitué **d'abord des pages HTML d'avis**
(`/jcms/p_N` et `/jcms/c_N` du fichier des liens) : elles portent le titre,
la date, le motif et la synthèse de l'avis, suffisent à citer et à
orienter, pèsent 77 Ko brutes pour quelques Ko de texte utile, et sont
atteintes sans redirection. **Les PDF d'avis viennent en second**, un par
page, derrière la redirection de mesure d'audience : ils ne seront
téléchargés que pour les dossiers où la synthèse ne suffit pas, après avoir
suivi la redirection une fois pour en mesurer la taille. Le corpus se
constitue **par étapes** : les dossiers avec un avis depuis 2024 d'abord
(745 dossiers SMR), puis le reste si l'évaluation le demande. Chaque
document conservé porte l'URL, la date de collecte et la date de l'avis ;
rien n'est altéré, et l'assistant cite la source et la date de mise à jour,
comme la licence l'exige. La collecte respecte `robots.txt`, se fait en
série avec une pause d'au moins deux secondes, avec le `User-Agent` du
projet, et met les pages en cache dans l'archive bronze : une page n'est
demandée qu'une fois tant que l'avis n'a pas changé.

## Conséquences

- Volume de la première étape : de l'ordre de 750 pages, soit environ
  60 Mo bruts et moins de 5 Mo de texte ; le corpus complet (10 480 pages)
  tiendrait en 800 Mo bruts. Les PDF restent à mesurer.
- Le Lot 3 doit garder la date de l'avis (`datePublished`) et l'URL dans
  chaque extrait indexé : c'est à la fois une obligation de licence et la
  condition d'une réponse datée.
- Ce qu'il faudra surveiller : un changement de `robots.txt`, une
  redirection ou un blocage des pages d'avis, ou des mentions légales plus
  restrictives ; l'un ou l'autre rouvre cet ADR.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| Les PDF d'abord | une redirection de mesure d'audience par document, taille inconnue, texte à extraire de PDF de plusieurs dizaines de pages ; la synthèse HTML répond déjà aux questions « quel SMR, quand, où le lire » |
| Tout le corpus d'un coup | 10 480 requêtes vers un service public pour des avis dont beaucoup datent de plus de dix ans ; l'évaluation dira si l'on en a besoin |
| Un index tiers ou une API | il n'en existe pas d'officielle pour les avis de la CT ; la BDPM donne déjà les liens |

## Références

PRD v0.2 §6.7, §10.2 (point 7) · ordre de mission 01 (sources, H.5 ;
addendum 1) · `docs/rapports/mission-01/points-a-trancher.md` (H.5) ·
`docs/donnees/bdpm.liens_ct.md`, `bdpm.smr.md`, `bdpm.asmr.md` ·
`docs/rapports/mission-01/palier-3.md` (journal des cinq requêtes).
