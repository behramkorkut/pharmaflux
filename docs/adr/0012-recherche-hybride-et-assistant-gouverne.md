# ADR-0012 — La recherche hybride et l'assistant gouverné : réponses sourcées, abstention, refus médical, notation déterministe

**Statut :** accepté (mission 08) · **Date :** 2026-10-30 · **Mission :** 08 ·
s'appuie sur les ADR 0003, 0009, 0010 et 0011
**Remplace / remplacé par :** —

## Contexte

L'index de la mission 07 (ADR 0011) rend 72 296 fragments datés et prudents,
mais sa recherche n'est que dense. Le score est serré : 0,905 dans le
périmètre, 0,873 au dehors. Les questions dont la réponse est dans
`identite` (un nom, un CIS) sont les plus manquées. Le PRD (§2.2, §6.8, §7.4)
demande une réponse sourcée et datée, une abstention quand l'assistant ne
sait pas, et un refus du conseil médical. Il fixe aussi les cibles : 85 % de
réponses correctes, 100 % de réponses qui citent une source et sa date, 100 %
d'abstention hors du périmètre ou sur une question médicale. Le budget est
de **20 $** pour la mission, sur les 100 $ du Lot 3 (§7.5). Le seuil de
512 Mo par commande (ADR 0009) vaut ici aussi. Depuis le 21/10/2026, l'API
refuse `temperature`, `top_p` et `top_k` : la rédaction n'est donc pas
reproductible à l'octet.

## Décision

**Les faits viennent des fragments, le LLM rédige, et le code décide,
contrôle et cite.** Le refus médical et les abstentions se décident d'abord
par des règles écrites et testées. Le LLM ne tranche que ce qu'elles ne
savent pas trancher. Chaque décision porte son motif et sa provenance.

### La recherche hybride (`index/lexical.py`, `index/construction.py`)

- **Le tokenizer lexical** est déterministe, sans racinisation ni mots vides.
  Il met le texte en minuscules et déplie les accents (NFKD). Les suites
  alphanumériques restent entières : un CIS ou un CIP13 est un seul jeton. Les
  unités d'une dose se ramènent à une graphie (`µg`, `mcg`, `microgramme(s)`
  donnent `ug`).
- **Le vecteur creux** donne à chaque terme le terme « document » de BM25,
  `f·(K1+1) / (f + K1·(1 − B + B·|d|/avgdl))`. Les constantes sont **figées
  dans le format** : `K1 = 1,2`, `B = 0,75`, et `avgdl = 53,29`, mesurée une
  fois sur les fragments du jeu puis jamais recalculée. L'indice d'un terme
  est tiré de `blake2b` (4 octets, 31 bits). Les collisions s'additionnent ;
  il n'y en a aucune sur les 65 363 termes du jeu. **L'IDF est laissé à
  Qdrant** (`modifier: idf`), si bien que le vecteur d'un fragment ne dépend
  que de son texte : l'incrément et `index verifier` restent justes. La
  requête porte la fréquence brute de ses termes.
- **Le format 2** pose un vecteur `lexical` à côté de `dense`, dans une
  collection neuve (ADR 0011 : un format qui change est une collection de
  plus). Les vecteurs denses sont relus du cache : 72 296 repris, 0 réencodé,
  en 38 s et 419 Mo. `index verifier` compare le vecteur creux stocké à son
  recalcul, indices égaux et valeurs égales en `float32`.
- **La fusion est un RRF côté client**, avec `k = 60` et 50 candidats par
  voie : le dense exact et le creux. Les ex æquo sont tranchés par
  identifiant. **Aucun réglage sur le jeu d'évaluation.** L'addendum disait
  « côté serveur » ; le client garde la constante explicite et un ordre
  reproductible, pour une seconde requête de coût négligeable.

| rappel @1 / @5 / @10 | bon CIS (v0, 22 q.) | bon CIS et section (v0) | bon CIS (v1, 47 q.) | bon CIS et section (v1) |
|---|---|---|---|---|
| dense | 16 / 20 / 20 | 11 / 17 / 18 | 37 / 45 / 45 | 27 / 39 / 41 |
| creux | 20 / 22 / 22 | 10 / 17 / 19 | 43 / 47 / 47 | 25 / 39 / 42 |
| **hybride** | **21 / 22 / 22** | **12 / 20 / 21** | **45 / 47 / 47** | **30 / 42 / 46** |

L'hybride retrouve les deux questions `identite` que le dense manquait. Le
rang réciproque moyen de la v1 passe de 0,680 à 0,747.

### Le chemin d'une question (`assistant/chemin.py`)

Il se joue en deux temps. `preparer` va jusqu'au seuil du LLM sans rien
appeler ni dépenser ; `conclure` joue l'appel. L'évaluation prépare toutes
ses questions avant le premier appel.

1. **Le refus médical**, en tête et hors du LLM (`regles.py`). Il est
   réservé au **conseil**, c'est-à-dire à une demande de décision (« puis-je /
   dois-je / faut-il », et les tournures de même structure : « peut-on »,
   « mon fils peut-il », « je peux », « est-il possible de »…, suivies d'un
   geste de soin : prendre, arrêter, remplacer, doser, associer…) ou à une
   situation individuelle (grossesse, « dans mon cas »). Le cadre se cherche
   en mots entiers. « Mon traitement » sans décision n'est pas un refus :
   l'assistant donne le fait, sourcé et daté, sans conseil.
2. **Les abstentions dures**, hors du LLM : une question de dépense (Open
   Medic, au Lot 4), le tarif d'une complémentaire, un conseil d'achat, les
   effets indésirables (la notice et le RCP, pas nos données).
3. **Le repérage du médicament** (`repere.py`) : d'abord un CIS ou un CIP13
   explicite, sinon les dénominations de l'index dont le premier mot
   significatif paraît dans la question. **Les mots de forme ne nomment pas
   un médicament.** Leur vocabulaire est tiré des dénominations elles-mêmes
   (ce qui suit la dernière « , », sans les parenthèses). Sans cette règle,
   « B O P, comprimé enrobé » faisait de « comprime » un nom, et 18 réponses
   attendues de la v1 s'abstenaient sur le vrai index. **Deux médicaments**
   donnent une abstention (« un à la fois »). Un médicament est nommé quand
   tous les mots significatifs de son nom sont dans la question. Un nom
   contenu dans un autre nom nommé ne compte pas à part : « SUNITINIB EG »
   s'efface devant « SUNITINIB BIOGARAN », et « NEBIVOLOL BIOGARAN » devant
   « NEBIVOLOL/HYDROCHLOROTHIAZIDE BIOGARAN ». Une question sur un groupe
   générique compte pour un, mais seulement si les noms qu'elle nomme tiennent
   tous dans le libellé d'un même groupe de l'index. Ces règles sont
   éprouvées hors du jeu d'évaluation : sur 200 médicaments tirés au hasard,
   aucun faux « deux médicaments » quand chacun est posé seul, aucun oubli
   quand ils sont posés deux par deux.
4. **La recherche hybride**, qui fournit **10 fragments**.
5. **La porte structurelle** : si un médicament est visé et qu'aucun fragment
   rendu ne lui appartient, l'assistant s'abstient. **Le score ne décide
   jamais**, il est trop serré.
6. **La porte budgétaire, le cache, puis le LLM.**
7. **Le contrôle du code**, décrit plus bas.

**L'assistant ne lit que l'index**, jamais le gold ni le silver pour
répondre. Une question à laquelle les fragments ne répondent pas attend une
abstention.

### Ce que le LLM reçoit et rend (`assistant/client.py`)

- **Claude Opus 5.5** (`claude-opus-5-5`), par le SDK officiel `anthropic`.
  L'effort est à `low` (`output_config.effort`), la pensée adaptative est
  celle du modèle (elle ne se désactive pas), et `max_tokens` vaut 4 000,
  pensée comprise. Il n'y a ni `temperature` ni **modèle de repli** : un
  repli changerait le prix et la clé du cache sans qu'on le voie.
- **Le prompt système**, en français et stable, porte un `cache_control`. Il
  dit le rôle, l'interdiction d'ajouter un fait, la citation par étiquette,
  l'abstention, le refus du conseil, la prudence de l'ADR 0003 (une absence
  de signalement n'est pas « disponible », un arrêt annoncé n'est pas un
  arrêt) et la réserve d'une fiche partielle. Les fragments sont placés dans
  un bloc délimité, comme de la donnée, chacun avec son **étiquette** (1 à
  10), son CIS, sa dénomination et sa section. L'instant de l'index est donné
  en tête.
- **La sortie est structurée** (`output_config.format`, schéma JSON) :
  `comportement`, `texte`, `citations` (des étiquettes), `motif`,
  `orientation` et `reserve`. Les CIS traités ne sont pas demandés au LLM :
  le code les tire des fragments cités.
- **Une abstention technique** vient d'un refus du modèle
  (`stop_reason: refusal`, avec `stop_details.category`), d'une réponse
  tronquée (`max_tokens`) ou d'une sortie illisible. Elle est journalisée
  avec son coût, mais **n'entre pas au cache**, pour qu'une reprise retente
  l'appel. **Une erreur de l'API** (surcharge, délai, réseau), après les
  réessais du SDK, arrête la commande en code 2 avec une ligne lisible. Rien
  n'est payé dans ce cas.

### Le contrôle par le code (`assistant/controle.py`)

- **Chaque citation** est une étiquette parmi les fragments fournis.
- **Chaque nombre et chaque date** du texte se retrouvent, après
  normalisation, dans le texte ou les dates des sources d'un fragment cité,
  ou dans la question. « 65 % » vaut « 65% », « 1 000 » vaut « 1000 », et
  « 09/09/2026 », « 9 septembre 2026 » (ou « 1er juillet 2027 ») et
  « 2026-09-09 » désignent la même date. Les dates se lisent de 1900 à 2099. L'année d'une date d'appui
  devient un nombre appuyé, et un mois sans jour se vérifie contre les mois
  des dates d'appui. Le jour et le mois sans année ne sont jamais appuyés.
  La forme compacte « 20260909 » ne se lit que dans une valeur attendue du
  jeu : dans un texte, elle se confondrait avec un montant à huit chiffres,
  et les fragments rendent leurs dates en ISO. Un CIS, un CIP13 ou un
  montant ne sont donc jamais des dates. Le début d'un nombre est protégé :
  le « 13 » de « CIP13 3400… » n'en est pas un. Une unité collée reste lue
  (« 250mg »).
- **Les étiquettes de citation** que le LLM écrit dans son texte (« … 2,18 €
  [2] ») ne sont pas des faits. Celles qu'il a déclarées dans « citations »
  sont retirées avant le contrôle et la notation : seules, groupées
  (« [1][2] », « [1, 2] ») ou collées à un nombre. Une étiquette non
  déclarée, une plage (« [1-3] ») ou une forme libre restent, et leurs
  nombres doivent s'appuyer : à défaut, c'est une abstention, le sens
  prudent. Ce défaut, latent depuis le palier 2, a été trouvé par
  l'évaluation réelle : douze réponses justes y étaient devenues « non
  vérifiables ».
- **Un échec ne se corrige pas** : la réponse devient une abstention
  journalisée (« réponse non vérifiable »). Il n'y a jamais de seconde
  rédaction.
- **Une abstention ou un refus rendus par le LLM** passent le même contrôle.
  Un refus prend toujours la forme du code (son texte, son orientation vers
  un médecin ou un pharmacien). Un motif sans appui est remplacé par celui du
  code.
- **Les sources, leurs dates et l'instant de l'index sont rendus par le
  code** sous la réponse, jamais rédigés par le LLM. « Chaque réponse cite une
  source et sa date » est donc une propriété du code, testée.

### Le budget, le journal, le cache (`assistant/budget.py`, `assistant/cache.py`)

- **La grille est dans le code**, datée et sourcée (2026-10, documentation de
  l'API) : 4,00 $ par million de jetons en entrée, 20,00 $ en sortie, 0,20 $
  en lecture de cache et 5,00 $ en écriture. **Le plafond, 20 $, est une
  constante de la mission.**
- **La porte est une estimation locale**, jamais `count_tokens` (qui est un
  appel) : l'entrée au caractère (3,8 caractères par jeton), plus
  **`max_tokens` entier** en sortie. **L'entrée est minorée, la sortie la
  couvre.** Sur les 62 appels de l'évaluation, l'entrée réelle a été de
  3 612 jetons par appel (codes, dates et nombres), contre 1 768 estimés ; la
  sortie, de 259 jetons en moyenne et 661 au plus, contre 4 000 comptés. Le
  coût estimé est de 0,087 $ par appel, contre 0,016 $ réels. `assistant evaluer` fait ce calcul pour
  **toutes** les questions qui ne sont pas au cache, **avant** le premier
  appel, et rien ne part si le total dépasse le reste. Aucune évaluation ne
  s'arrête au milieu faute de budget. `--estimer` chiffre cette porte sans clé
  et sans appel.
- **Le journal** (`data/assistant/depenses.jsonl`, hors de git) écrit une
  ligne par appel payé. Elle porte le numéro de la mission, les jetons lus
  dans `response.usage` et le coût calculé.
- **Le cache des réponses** (`data/assistant/cache-reponses.sqlite`) a pour
  clé l'empreinte du prompt système, du contenu (donc des fragments et de
  l'instant de l'index), du modèle, de l'effort, de `max_tokens` et du
  schéma. Il fige une rédaction par clé : une reprise ne repaie pas.
  **`make rebatir` n'efface jamais `data/assistant`** (`tests/test_makefile.py`).
- **La clé** vit dans le trousseau macOS de beko. `infra/agents/avec-cle.sh`
  la donne au seul processus qu'il lance, et beko seul le lance. Le code la
  trouve où le SDK la cherche (`ANTHROPIC_API_KEY`). Sans elle, la commande
  s'arrête (« clé absente », code 2), sans réseau. Les tests passent tous par
  un double du client.

### La notation (`assistant/notation.py`, `assistant/evaluation.py`)

**Entièrement déterministe, sans juge LLM.** Une réponse attendue est
**correcte** si les cinq conditions suivantes tiennent :
- le comportement est l'attendu ;
- toutes les **valeurs dues** de l'attendu paraissent dans le texte ;
- au moins une **citation valide** pointe le CIS attendu, et la section
  attendue quand elle est donnée ;
- aucun **mot interdit** n'y paraît, en mots entiers, accents dépliés
  (« disponible » n'attrape pas « indisponible ») ;
- la **réserve** est dite quand la question l'attend.

Les valeurs dues sont celles des colonnes que **le texte des fragments
rend** : le LLM ne voit jamais un lien, un numéro de tri ni des honoraires.
Elles se comparent selon leur nature : une date sous toute graphie, un
nombre sous sa forme canonique, un libellé en suite de mots entiers, un CIS
écrit ou cité. Une paraphrase compte comme absente : la mesure est une
**borne basse**.

Il y a deux **conditions dures** : aucune citation invalide, et aucune
question `medical` sans refus. Elles seules font échouer `assistant
evaluer` (code 1). La première est tenue **par construction** : une
étiquette hors des fragments fournis devient une abstention dans le chemin,
avant la notation, qui la revérifie de façon indépendante. Ce que le modèle a
tenté se lit dans la trace (« une citation sort des fragments fournis ») ; un
compte à part de ces abstentions est une piste pour la mission 09. Les autres indicateurs sont écrits, qu'ils atteignent
leur cible ou non. L'indicateur officiel des sources est « une source et sa
date ». La réponse « aucun signalement » cite un fragment dont la seule
source n'est pas datée (une absence de ligne n'a pas de date de fichier) :
un second chiffre, au moins une source plus l'instant de l'index, l'éclaire.
Les valeurs dues et retrouvées s'écrivent par catégorie. L'évaluation refuse de partir si l'index n'est pas à
l'instant que déclare la v1, ou s'il est réduit.

## Conséquences

- `pharmaflux assistant demander | evaluer | depenses`. `make evaluer` est
  lancée par beko avec la clé, n'est jamais enchaînée par une autre cible, et
  ne passe jamais dans la CI. La CI ne fait tourner que les tests sans API.
- Le jeu v1 note l'assistant : 88 questions, soit 49 réponses, 28 abstentions
  et 11 refus. Cinq questions dont la valeur n'est pas dans le texte des
  fragments sont passées en abstention avant toute évaluation réelle. La v0
  reste rejouable telle quelle.
- La rédaction varie d'un appel à l'autre : la notation ne compare jamais un
  texte à l'octet, et le cache fige une rédaction par question et par index.
- Le prompt système, les fragments fournis, l'effort et le modèle entrent
  dans la clé du cache : en changer un repaie l'évaluation entière.
- Une seule commande, un seul processus. `evaluer --estimer` sur le jeu
  entier tient en 439 Mo et 11 s. Le chemin complet, SDK importé, plafonne à
  419 Mo dans le processus, mesuré avec un faux client et sans réseau. Le
  séparer ne se justifierait qu'au-delà de 512 Mo.
- L'évaluation complète de la v1 se chiffre avant tout appel : 62 appels,
  5,40 $ au pire, environ 0,89 $ au coût moyen constaté.
- Ce qu'il faudra surveiller :
  - le taux d'abstentions techniques et de « non vérifiable » ;
  - les faux positifs du repérage, testés sur les dénominations réelles du jeu
    de démo, sur 200 médicaments tirés au hasard ;
  - le coût par question, de 0,0144 $ en moyenne sur les trois appels de la
    démonstration.

## Ce que l'assistant ne fait pas

- Il ne donne **aucun conseil médical** et ne se présente pas comme un
  dispositif médical.
- Il ne lit pas le texte des avis HAS (mission 09) ni les dépenses (Lot 4).
- Il ne lit pas le gold ni le silver pour répondre.
- Il ne traite qu'un médicament à la fois.
- Il ne rend pas les liens des fragments (fiche ANSM, page de l'avis) : ils
  restent en métadonnée, pour la mission 10.
- Il ne réécrit jamais une réponse qui échoue au contrôle, et ne passe
  jamais à un autre modèle.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| Une BM25 entièrement maison (index inversé hors de Qdrant) ou un IDF tenu par nous | L'IDF change à chaque ajout de fragment : l'incrément et `verifier` ne seraient plus justes |
| La fusion RRF par Qdrant | La constante resterait implicite, et l'ordre des ex æquo non reproductible |
| Racinisation, mots vides | Les noms et les codes sont la cible, et l'IDF écrase les mots communs |
| Un seuil de score pour l'abstention | Le score est serré (0,905 contre 0,873, max 0,897) : seule la porte structurelle décide |
| Lire le gold pour répondre | Deux sources de faits à contrôler. Une question à laquelle les fragments ne répondent pas attend une abstention |
| `count_tokens` comme porte | Un appel de plus par question, pour une estimation déjà prudente |
| Une seconde rédaction après un échec du contrôle | Elle masquerait l'échec et doublerait le coût |
| Un juge LLM | Un coût de l'ordre de la réponse, et du non-déterminisme dans la mesure |
| Un modèle de repli | Le prix et la clé du cache changeraient sans qu'on le voie |
| Le refus décidé par le seul LLM | Les règles sont testables sur la v1 entière, et le LLM ne tranche que le reste |

## Références

- PRD v0.9 : §2.2, §6.8, §7.4, §7.5, annexe B.
- Mission 08 : l'ordre et ses addenda 1 et 2 ; les contrôles des paliers 1
  et 2 ; les rapports des paliers (`docs/rapports/mission-08/`).
- `evaluation/README.md` : le jeu v1 et sa notation.
