# Mission 08 — L'assistant gouverné : recherche hybride, réponses sourcées et datées, abstention, refus médical, jeu de questions v1

**À :** Claude Opus 5.5 (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.9 §1.6, §2.2, §4 (Lot 3), §6.7, §6.8, §7.4, §7.5, §9,
annexe B · mission 07 (`pr.md`, `controle-iec-final.md`) · ADR 0003, 0004,
0010 et 0011 · `evaluation/README.md` · `CLAUDE.md` ·
`docs/agents/processus.md`
**Statut :** ordre rédigé le 30/10/2026 — §0 rendu (`314bd46`), tranché
par les **addenda 1 et 2** (en fin de fichier) — **palier 2 ouvert**
**Branche :** `mission-08-assistant-gouverne`, dans `pharmaflux-codeur/`
(préparée par beko avec `preparer-mission.sh`). Trois paliers, chacun
committé en local et contrôlé par l'IeC ; **aucun push** de ta part.

Tu as codé les missions 06 et 07 : le circuit est le même, messages directs
compris. Lis le PRD v0.9 (§4, Lot 3 : le découpage revu ; §6.7 : ce que la
mission 07 a fait ; §6.8 et §7.5 : précisés pour cette mission ; annexe B :
la v1), puis cet ordre. Tes commits portent les trailers
`Commis-par: codeur` et
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Constat

L'index est fait : 72 296 fragments datés et prudents, une mise à jour par
incréments vérifiée, une recherche exacte qui rend chaque fragment avec sa
source, sa date et l'instant de l'index. Mais personne ne répond encore à une
question :

1. **La recherche n'est que dense.** Le score est serré (0,905 dans le
   périmètre, 0,873 hors périmètre), et les questions dont la réponse est
   dans `identite` sont les plus manquées. Un nom de médicament, un CIS ou
   un code se cherchent mieux par les mots.
2. **Rien ne rédige une réponse.** Le PRD demande une réponse sourcée et
   datée, qui s'abstient quand elle ne sait pas, et qui refuse le conseil
   médical. Aucun appel à un LLM n'existe dans le dépôt.
3. **Le jeu de questions ne sait pas noter un assistant.** La v0 vérifie
   des lignes de fichier à une date ; elle ne dit pas si une réponse
   rédigée est juste, bien citée, ou s'abstient à bon escient. La v1 est
   prévue par l'annexe B.

**Objectif** : à la fusion, quatre choses sont vraies.
- Une **recherche hybride** (dense et lexicale, fusionnées) rend mieux les
  bons fragments que le dense seul, mesuré sur le jeu de questions.
- Une commande **répond à une question** : les faits viennent des fragments
  et du gold, le LLM rédige, chaque phrase factuelle cite un fragment
  réellement fourni, avec le fichier, la date de la source et l'instant de
  l'index.
- L'assistant **s'abstient** hors du périmètre ou quand rien ne répond, et
  **refuse le conseil médical** avec un renvoi vers un professionnel ; ces
  décisions sont journalisées avec leur motif.
- Le **jeu de questions v1** existe et **note l'assistant** : bonnes
  réponses, citations justes, abstentions et refus. L'évaluation complète a
  tourné au moins une fois sur le jeu de démo, sous le plafond de dépense.

## Ce qui est déjà tranché (pas de §0 là-dessus)

- **L'assistant lit l'index et le gold, rien d'autre.** Pas de lecture du
  bronze, du silver brut, du bus ou des événements pour répondre. Le corpus
  des avis HAS n'est pas dans cette mission (mission 09).
- **Les faits ne viennent jamais du LLM** (PRD §6.8). Un taux, un prix, une
  date, un statut, une liste d'alternatives sont dans un fragment donné au
  LLM, ou lus dans le gold par le code. Le LLM rédige et ne doit rien
  ajouter. Une réponse dont une phrase factuelle ne s'appuie sur aucun
  fragment fourni est un échec, pas une approximation.
- **Citation vérifiable par la machine.** Chaque réponse porte la liste des
  fragments cités (leur identifiant), et chacun doit faire partie de ceux
  qui ont été donnés au LLM pour cette question. Elle dit l'instant de
  l'index.
- **La prudence du gold passe dans la réponse** : « aucun signalement »
  n'est jamais « disponible » (ADR 0003) ; un arrêt annoncé n'est pas un
  arrêt ; une fiche partielle se dit (réponse avec réserve, annexe B) ; une
  question de dépense s'abstient avant le Lot 4.
- **Pas de conseil médical, jamais** (PRD §6.8, §7.4) : posologie,
  substitution pour un patient, interactions, effets chez une personne. Le
  refus renvoie vers un médecin ou un pharmacien. L'assistant dit qu'il
  n'est pas un dispositif médical.
- **L'abstention et le refus se décident d'abord hors du LLM**, par des
  règles écrites et testées, quand c'est possible. Le LLM ne tranche que ce
  que les règles ne savent pas trancher, et le motif de chaque décision est
  journalisé.
- **Le LLM est Claude, par le SDK officiel `anthropic`**, jamais par un
  client HTTP fait main ni par une couche compatible OpenAI. Le modèle par
  défaut est **Claude Opus 5.5** (`claude-opus-5-5`). Un autre modèle se
  propose au §0, mesures à l'appui, et c'est beko qui décide.
- **Budget** : **20 $ au plus** pour toute la mission, sur les 100 $ du
  Lot 3 (PRD §7.5). Chaque appel est compté (jetons d'entrée, de sortie, en
  cache, et coût calculé) dans un journal local hors de git. Une commande
  refuse de partir si son estimation dépasserait ce qui reste. Le cache des
  réponses évite de repayer une question déjà posée sur le même index.
- **La clé de l'API** : aucun agent ne la lit, ne l'affiche, ne l'écrit ni ne
  la demande. Le code la trouve où le SDK la cherche (l'environnement, ou un
  profil `ant auth login` de beko). Aucun `.env` n'est lu ni affiché par
  toi. Si la clé manque, la commande le dit et s'arrête.
- **Les tests n'appellent jamais l'API** ni le réseau. Le client Claude est
  remplacé dans les tests par un double déterministe, derrière la même
  interface. Les appels réels ne partent que des commandes, lancées à la
  main, et comptées.
- **La CI n'appelle pas l'API** dans cette mission. L'évaluation dans la CI
  est à la mission 10, avec son propre budget.
- **L'index, le gold, le silver, les événements, le bus et les contrats ne
  changent pas**, sauf ce que demande la recherche lexicale (§0 A), qui
  peut demander un nouveau format de fragments et une nouvelle collection
  (ADR 0011 : un format qui change est une collection de plus).
- **Le jeu v0 reste rejouable tel quel.** La v1 est un nouveau fichier.
- **Le colima est toujours partagé avec Alamel** (`alamel-dev-postgres`
  sur 5432, `alamel-dev-minio` sur 9000-9001). Projet `pharmaflux` partout,
  `--pull never`. Toute commande qui efface un volume attend la réponse de
  beko.
- **Dépendances** : le SDK `anthropic`, et ce que la recherche lexicale
  demande, se justifient au §0 avec la règle des deux semaines et les
  plafonds de l'ADR 0009.

## Sources de données pour cette mission

- **Le jeu de démo** et ce qu'en tirent `make silver`, `make gold` et
  `make index` : la source de la mission, de ses tests et de sa
  démonstration.
- **L'archive du Mac, en lecture seule** (`$PHARMAFLUX_DATA`, sinon
  `~/pharmaflux-data`), pour la non-régression. Tu n'y écris jamais rien.
- **L'API Claude**, sous le plafond, par les seules commandes de
  l'assistant.
- **Aucune requête réseau vers les sources** (BDPM, data.gouv, HAS).

## §0 — Points à trancher avant de coder

Réponds dans `docs/rapports/mission-08/points-a-trancher.md` : pour chaque
point, ton **constat** (mesuré quand c'est possible, avec la commande), ton
**avis**, et tes **questions**. Rien n'est codé avant l'addendum de l'IeC.
**Aucun appel à l'API au §0** : les coûts sont estimés par le décompte des
jetons, pas par des appels payants.

**A. La recherche lexicale et la fusion.**
- Le moyen : un vecteur creux nommé dans Qdrant à côté de `dense` (prévu à
  la mission 07), une BM25 calculée par nous, ou autre. Le tokenizer
  lexical (le français, les accents, les CIS et CIP13, les dosages comme
  « 500 mg »).
- La fusion : RRF ou autre, et ses paramètres.
- Ce que cela change à l'index : un format 2 et une collection neuve ? La
  mise à jour par incréments et `index verifier` le suivent-ils ?
- La mémoire et le temps, contre le seuil de 512 Mo.
- **Mesure attendue** : le rappel à 1, 5 et 10 sur les questions du jeu
  v0 qui nomment un médicament, dense seul contre hybride, avec
  `index evaluer` ou son équivalent.

**B. Le chemin d'une question.** Les étapes, dans l'ordre : règles de refus
et d'abstention, recherche, lecture du gold si nécessaire, appel au LLM,
contrôle de la réponse. Pour chaque étape, ce qu'elle décide, ce qu'elle
journalise, et ce qui l'arrête. Ce que l'on fait d'une question qui nomme un
médicament introuvable, ou deux médicaments.

**C. Ce que le LLM reçoit et ce qu'il rend.**
- Le prompt système (en français), les fragments fournis (combien, dans
  quel ordre, avec quelles métadonnées), l'instant de l'index.
- La forme de la réponse : des sorties structurées (`output_config.format`)
  avec le texte, les identifiants des fragments cités, le comportement
  (`reponse`, `abstention`, `refus_medical`) et le motif.
- Le contrôle après l'appel : chaque fragment cité est-il parmi les
  fournis ? Les nombres et les dates du texte se retrouvent-ils dans les
  fragments cités ? Que fait-on d'une réponse qui échoue au contrôle ?
- Le traitement d'un refus du modèle (`stop_reason: "refusal"`) et des
  erreurs de l'API.

**D. L'abstention et le refus médical.**
- Les règles hors du LLM : lesquelles, sur quoi elles portent, comment
  elles se testent. Les cas difficiles : une question médicale déguisée
  (« mon fils peut-il prendre le générique ? »), une question de
  disponibilité pour un patient, une question de dépense.
- Le rôle du score de recherche, sachant qu'il est serré (mission 07).
- La forme d'une abstention et d'un refus : le motif, l'orientation
  concrète, le renvoi vers un professionnel.

**E. Le jeu de questions v1.**
- Ce que devient chaque question de la v0 : gardée, retirée, remplacée
  (l'annexe B en cite deux).
- Les nouvelles questions : combien par catégorie (l'objectif du PRD est
  cent au Lot 3 ; la mission 09 ajoutera celles sur le texte des avis HAS),
  et les questions pièges.
- **La date de référence** : la v0 vise l'archive du 24/10 ; l'assistant
  répond à l'instant de l'index (la dernière observation du jeu). Comment
  la v1 date ses attendus, et comment ils se vérifient sans LLM (depuis le
  gold à cet instant, et depuis le bronze, comme `questions verifier
  --entrepot`).
- Le format : ce qui s'ajoute au format v0 pour noter une réponse rédigée
  (les valeurs qui doivent apparaître, le CIS et la section attendus, ce qui
  ne doit pas apparaître).

**F. La notation.**
- Ce qui se note **sans LLM** : le comportement attendu, les valeurs
  présentes, les citations valides, l'instant cité, les mots interdits
  (« disponible » pour un `aucun_signalement`).
- Ce qui demanderait un juge LLM, son coût, et si on en a besoin dans cette
  mission. L'IeC penche pour une notation **entièrement déterministe** dans
  cette mission, si elle suffit à mesurer les indicateurs du §2.2.
- Les indicateurs rendus : réponses correctes, réponses citant une source
  et sa date, abstentions et refus justes, et le coût par question.

**G. Le modèle, l'effort et le coût.**
- Le modèle par défaut est Claude Opus 5.5. Estime, par le décompte des
  jetons, le coût d'une question et d'une évaluation complète de la v1.
  `messages.count_tokens` est un appel à l'API, donc hors du §0 : une
  estimation hors ligne suffit ici, et tu dis si tu proposes ce décompte
  pour la suite.
- L'effort (`output_config.effort`) et ce qu'il change.
- Le cache des prompts (le prompt système et les fragments stables) et le
  cache des réponses (sa clé : question, instant de l'index, format, modèle,
  prompt).
- Le **journal des dépenses** : où il vit (hors de git), ce qu'il compte, et
  comment une commande refuse de dépasser le plafond.
- Combien d'évaluations complètes tiennent dans 20 $, et le plan de
  dépense de la mission, palier par palier.

**H. Les commandes.** Le groupe (`pharmaflux assistant` ?) : `demander`,
`evaluer`, `depenses`, et ce qui manque. Les formats de sortie (texte pour
un humain, JSON Lines pour l'évaluation), les codes de sortie. Les cibles du
`Makefile`, et ce qu'elles enchaînent après `make index`.

**I. La mémoire et le temps.** Pour chaque commande, sur le jeu : le
résident maximal contre le seuil de 512 Mo (ADR 0009), et la durée.
L'assistant charge le modèle d'embeddings (446 Mo pour `chercher`) : le SDK
et la recherche lexicale tiennent-ils dans la marge, ou faut-il séparer ?

**J. Autre.** Tout ce que cet ordre n'a pas vu.

## Décisions (sous réserve du §0)

1. **Recherche hybride** (§0 A) : la recherche lexicale, la fusion, la
   mesure contre le dense seul.
2. **Jeu de questions v1** (§0 E) : le fichier, son format, ses attendus
   vérifiés sans LLM.
3. **Assistant** (§0 B, C, D, G) : le chemin d'une question, les règles
   d'abstention et de refus, l'appel à Claude, le contrôle des citations, le
   journal des dépenses, le cache.
4. **Évaluation** (§0 F) : la notation, ses indicateurs, et une évaluation
   complète de la v1, sous le plafond.
5. **`Makefile`** (§0 H) : les cibles. La CI ne change que pour les tests
   sans API.
6. **Démonstration sur le Mac** :
   - toi, au palier 2 : cinq questions réelles du jeu, dont une
     abstention et un refus, avec leurs réponses, leurs citations et leur
     coût ;
   - beko, au palier 3 : la séquence jusqu'à `make index`, puis
     l'évaluation complète de la v1. Il te transmet la sortie, et tu la
     cites dans le rapport.
7. **Docs** :
   - ADR 0012 : la recherche hybride, l'assistant gouverné (le chemin, les
     règles, le contrôle des citations), le modèle et le budget, la
     notation, ce que l'assistant ne fait pas ;
   - `README.md` : une section « L'assistant », avec deux exemples réels
     (une réponse citée et datée, un refus médical), et la section « État » ;
   - `evaluation/README.md` pour la v1 ;
   - `docs/CONTEXTE.md`, et `docs/journal.md` en fin de fichier. La
     **première entrée du journal** donne les durées de la CI de la PR #8 :
     deux `make index` avec l'encodeur de test en 66 s, le cache du modèle
     absent au premier run, l'installation et la vérification du modèle en
     3 s, le vrai modèle sur un sous-ensemble en 62 s, la sauvegarde du
     cache en 4 s ; le job `integration` en 6 min 24 s, `verifier` en
     5 min 23 s.

**Outillage** : le SDK `anthropic` est attendu ; le reste selon le §0 A.

## Paliers

1. **Recherche hybride et jeu v1** : décisions 1 et 2.
   - La recherche lexicale, la fusion, ce qu'elles demandent à l'index, et
     leurs tests (encodeur de test, Qdrant simulé, puis le vrai).
   - La mesure du rappel, dense seul contre hybride.
   - Le jeu v1, ses attendus vérifiés depuis le gold et le bronze.
   - **Aucun appel à l'API.**
   - L'entrée du journal sur la CI de la PR #8.
   - Rapport, commit.
2. **Assistant** : décision 3.
   - Le chemin d'une question, les règles, l'appel à Claude par le SDK, le
     contrôle des citations, le journal des dépenses, le cache.
   - Les tests, tous avec le double du client.
   - Ta démonstration de la décision 6, avec les coûts réels et ce qui
     reste du plafond.
   - Rapport, commit.
3. **Évaluation, `Makefile`, docs** : décisions 4, 5, 6 (beko) et 7.
   - La notation et ses tests.
   - `make -n` de chaque cible nouvelle ou modifiée dans le rapport.
   - L'évaluation complète de la v1 lancée par beko.
   - L'ADR 0012 et les docs.
   - Rapport, commit.

Après le contrôle du palier 3, la suite est celle du circuit :
1. la relecture (`/relire-mission 08`), jusqu'à « CONFORME » ;
2. `pr.md` ;
3. la **revue finale écrite de l'IeC** (`controle-iec-final.md`) ;
4. la publication et la fusion par beko.

**La mission est close** quand beko, sur le Mac, a enchaîné la séquence
jusqu'à `make index`, puis l'évaluation complète de la v1. Celle-ci doit
finir :
- **sans aucune citation invalide** ;
- **sans aucun conseil médical** sur les questions `medical` ;
- avec les indicateurs du §2.2 mesurés et écrits dans `pr.md`, qu'ils
  atteignent leur cible ou non ;
- avec une dépense totale de la mission **sous 20 $**, lue dans le journal
  des dépenses.

## Vérifications locales (à chaque palier, consignées dans le rapport)

| Vérification | Commande |
|---|---|
| lint | `uv run ruff check .` et `uv run ruff format --check .` |
| types | `uv run mypy src` |
| tests | `GITHUB_ACTIONS=true uv run pytest -q -rE -rs`, services et modèle présents |
| tests d'intégration et du modèle | `uv run pytest -q -rE -m "integration or modele"` |
| simulation du `Makefile` (palier 3) | `make -n <cible>` pour chaque cible nouvelle ou modifiée |
| crochets git | `sh infra/git-hooks/test-crochets.sh` |
| garde-fou Claude Code | `python3 infra/agents/test_garde_fou.py` |
| shellcheck | si un `.sh` est touché |
| YAML de la CI | si `ci.yml` est touché |
| dépenses | `pharmaflux assistant depenses` (ou l'équivalent) : le total de la mission et ce qui reste |
| non-régression | `demo verifier` ; `profil` et `questions verifier` sur `~/pharmaflux-data` ; `evenements` contre `85ec0ab` ; `silver verifier` 22/22 ; `make gold` sans bloquant et 25 concordantes ; `index verifier` conforme |

## Hors périmètre

- **Le corpus des avis HAS** et sa collecte (mission 09) ; l'API,
  l'interface, l'évaluation dans la CI et le test de fraîcheur de bout en
  bout (mission 10) ; les indicateurs de dépense (Lot 4).
- Tout appel à l'API Claude dans les tests ou dans la CI ; tout dépassement
  du plafond ; toute lecture, tout affichage ou toute écriture de la clé.
- Toute requête vers les sources ; toute écriture dans l'archive.
- Tout changement du gold, du silver, du schéma d'événement v1, des
  contrats, de la normalisation, des topics ou de la publication.
- **Toute exécution sur le VPS**. Le VPS-1 reste partagé avec la
  pré-production d'Alamel jusqu'à mi-novembre.
- **Pas d'usage des VPS d'Alamel**, et rien qui touche aux conteneurs
  d'Alamel du colima (`alamel-dev-postgres`, `alamel-dev-minio`) ni à la
  pré-production du VPS-1.

## Addendum 1 — le §0 tranché (30/10/2026)

Réponse au §0 du codeur (`points-a-trancher.md`, commit `314bd46`). Les
avis sont **retenus**, avec les précisions et les trois écarts ci-dessous
(B2, C : le rendu des sources par le code, E2). Ce qui n'est pas cité ici
est retenu tel que proposé. L'IeC a vérifié dans la documentation de l'API
ce que le §0 en dit : Opus 5.5 à 4 $ / 20 $ par million de jetons (lecture
de cache 0,20 $), effort `medium` par défaut, pensée adaptative non
désactivable, `temperature`, `top_p` et `top_k` refusés depuis le
21/10/2026. C'est exact.

### Ce que l'addendum change dans l'ordre

- **L'assistant ne lit que les fragments** dans cette mission (B2). Le
  gold sert à vérifier les attendus de la v1, hors ligne, pas à répondre.
  « L'index et le gold, rien d'autre » se lit donc « l'index, rien
  d'autre » pour l'assistant.
- **Les sources, leurs dates et l'instant de l'index sont rendus par le
  code**, pas rédigés par le LLM (C). Le LLM cite des identifiants ; le
  code écrit, sous la réponse, chaque fragment cité avec son fichier et la
  date de sa source, puis l'instant de l'index. « Chaque réponse cite une
  source et sa date » devient une propriété du code, testée, et non un
  espoir sur la rédaction.
- **La cible du jeu v1 est d'environ 90 questions** (E2), pas cent : la
  mission 09 dépasse la centaine avec les questions sur le texte des avis.

### A. La recherche lexicale et la fusion

- **A1 : oui, `FORMAT` passe à 2.** Collection neuve, reconstruction unique,
  vecteurs denses relus du cache. Le rapport du palier 1 donne la durée de
  cette reconstruction et le nombre de vecteurs repris (72 296 attendu).
- **A2 : oui, l'IDF à Qdrant** (`"modifier": "idf"`). Mais la BM25 a aussi
  un terme de document qui dépend du corpus : la saturation de la fréquence
  et la normalisation par la longueur moyenne. **La longueur moyenne est
  une constante du format**, écrite dans le code et dans l'ADR (mesurée une
  fois sur les fragments du jeu, puis figée), jamais recalculée. `k1 = 1,2`
  et `b = 0,75`, figés aussi. Ainsi le vecteur creux d'un fragment ne
  dépend que de son texte, et l'incrément et `verifier` restent justes.
- **Les indices des termes** viennent d'un hachage stable de la
  bibliothèque standard (par exemple les 4 premiers octets de `blake2b`,
  sur 31 bits), pas de `hash()` de Python, qui change à chaque processus.
  Aucune dépendance de plus. Les collisions sont acceptées et dites dans
  l'ADR.
- **A3 : le tokenizer est retenu.** Les CIS et les CIP13 restent entiers,
  les unités se normalisent. Deux précisions :
  - **pas de racinisation** dans cette mission (les noms et les codes sont
    la cible) ; une courte liste de mots vides français, versionnée dans le
    code, est permise ;
  - un test fixe la sortie du tokenizer sur une dizaine de cas
    (« DOLIPRANE 1000 mg », « 3400930000000 », « µg », une élision
    « l'avis », un accent).
- **La fusion : RRF côté serveur, `k = 60`, 50 candidats par `prefetch`.**
  **Pas de réglage sur les 22 questions** : ce serait apprendre le jeu
  d'évaluation. Une seule mesure, avec ces valeurs. Si l'hybride perd une
  question que le dense trouvait dans ses dix premiers, le rapport la
  nomme et l'explique.
- **`verifier`** compare le vecteur creux brut au recalcul, indices égaux,
  valeurs égales à la précision du `float32` stocké.
- **La mesure** : `index evaluer` sort dense seul, creux seul et hybride
  côte à côte, sur les questions de la v0 qui nomment un médicament **et**
  sur celles de la v1. La cible : l'hybride au moins égal au dense pour le
  bon CIS à 5 et à 10, et meilleur sur `identite`.

### B. Le chemin d'une question

- **B1 : oui, le refus médical tout en tête**, avant la recherche.
- **B2 : les fragments seulement** (voir plus haut). La catégorie
  `alternatives` se sert des fragments `identite` et `presentations`. Si une
  question v1 ne peut pas être répondue par les fragments, c'est un attendu
  d'abstention ou une question à retirer, pas une raison de lire le gold.
- **B3 : deux médicaments, abstention motivée** (« une question sur un
  médicament à la fois »), avec l'orientation de reformuler. La v1 en porte
  au moins une.
- **Le repérage du médicament visé est une règle écrite et testée.** Un CIS
  ou un CIP13 explicite d'abord ; sinon les dénominations de l'index dont
  le premier mot significatif apparaît dans la question (un dictionnaire
  tiré des fragments `identite`, chargé une fois). La porte structurelle
  (B6) s'appuie sur ce repérage : aucun des fragments rendus n'appartient
  aux CIS visés → abstention. Les pièges du « nom proche » se testent ici.
- Une question **sans médicament repéré** qui n'est ni refusée ni
  abstenue par les règles va au LLM avec ses fragments ; son contrôle (C)
  reste le même.

### C. Ce que le LLM reçoit et ce qu'il rend

- **C1 : le schéma est retenu, avec un champ de plus** : `reserve`
  (booléen), pour la réponse avec réserve de l'annexe B. Les CIS traités ne
  sont **pas** demandés au LLM : le code les tire des fragments cités.
- **C2 : 10 fragments**, fixés. Un autre nombre se propose dans un rapport,
  mesures à l'appui.
- **C3 : oui, aucune seconde rédaction.** Un échec du contrôle devient une
  abstention journalisée (« réponse non vérifiable »).
- **Le contrôle des nombres et des dates** : chaque nombre et chaque date du
  texte se retrouve, après normalisation (« 65 % » et « 65% », « 1 000 » et
  « 1000 », les dates en clair et en ISO), dans le texte **ou les
  métadonnées** (dates des sources) d'un fragment cité, ou dans la question
  elle-même (un CIS, un dosage). L'instant de l'index n'est pas dans le texte
  du LLM, puisque le code le rend (voir plus haut).
- **`max_tokens` à 4 000**, pensée comprise. Un `stop_reason` égal à
  `max_tokens` ou à `refusal` devient une **abstention technique**,
  journalisée avec la cause (et `stop_details.category` pour un refus).
- **Pas de modèle de repli** (`fallbacks`) dans cette mission. Un refus du
  modèle sur des données publiques de médicaments est un signal à
  journaliser et à compter, pas à faire passer par un autre modèle, qui
  changerait le prix et la clé du cache sans qu'on le voie.
- **Le contenu des fragments est de la donnée** : le prompt système le dit,
  et le texte des fragments est placé dans un bloc délimité.

### D. L'abstention et le refus médical

- **D1 : la zone grise est retenue** : le fait, sourcé et daté, sans
  conseil ni réassurance, et l'orientation vers un pharmacien. Dès qu'une
  question demande quoi **faire** (prendre, arrêter, remplacer, doser,
  associer), c'est un refus.
- **Le refus médical sur une question générale sans personne** (« quels
  sont les effets indésirables de X ? ») n'a pas de réponse dans nos
  sources : c'est une **abstention** hors périmètre, avec l'orientation vers
  la notice et un professionnel. Le refus est réservé au conseil.
- **D2 : les motifs vivent dans le code, avec leurs tests.** Deux tests
  portent sur la v1 entière : chaque question `medical` déclenche le refus
  par les règles, et **aucune** question d'une autre catégorie ne le
  déclenche. Un faux positif est un défaut, au même titre qu'un oubli.

### E. Le jeu de questions v1

- **E1 : la v1 est datée à l'instant de l'index du jeu de démo.** Le
  fichier déclare cet instant dans son en-tête. Le rapport du palier 1
  **montre** que deux constructions depuis le jeu de démo donnent le même
  instant, et `assistant evaluer` refuse de partir si l'index n'est pas à
  cet instant ou s'il est réduit. Les attendus se vérifient sans LLM, depuis
  le gold à cet instant et depuis les fichiers du jeu de démo, avec leur
  sha256.
- **E2 : environ 90 questions**, au moins 10 par catégorie, `avis_has` sur
  les seules données structurées. Les pièges de ton §0 sont retenus, plus
  « deux médicaments » (B3).
- **E3 : les champs sont retenus.** Les mots interdits se cherchent en mots
  entiers, accents dépliés : « disponible » ne doit pas attraper
  « indisponible » ni « disponibilité ».
- La v0 reste intacte. `questions verifier` sait vérifier la v1 comme la v0.

### F. La notation

- **F1 : oui, entièrement déterministe.** Pas de juge LLM.
- **F2 : la définition est retenue, et durcie** : comportement attendu,
  toutes les valeurs attendues présentes, au moins une citation valide qui
  pointe le CIS attendu (et la section attendue quand elle est donnée), et
  aucun mot interdit.
- **« Aucun conseil médical sur `medical` »** se note ainsi : une question
  `medical` dont le comportement n'est pas `refus_medical` est un échec de la
  condition dure, quel que soit le texte.
- Les indicateurs sont ceux du §0, avec le nombre d'abstentions techniques
  (refus du modèle, `max_tokens`) à part.

### G. Le modèle, l'effort et le coût

- **Opus 5.5**, comme l'ordre le dit.
- **G1 : `low` au départ**, remonté à `medium` seulement si la démonstration
  du palier 2 montre des échecs du contrôle ou des réponses incomplètes.
  Le rapport donne le coût moyen par question au niveau retenu.
- **G2 : la porte par estimation locale est retenue, et prudente** : avant
  chaque appel, entrée estimée **plus `max_tokens` entier** en sortie.
  `assistant evaluer` fait ce calcul pour **toutes** les questions non
  cachées **avant** de commencer, et refuse de partir si le total dépasse le
  reste. Aucune évaluation ne s'arrête au milieu faute de budget.
- **La grille de prix** est dans le code, avec sa date et sa source. Le
  plafond (20 $) est une constante de la mission, et chaque ligne du journal
  porte le numéro de la mission.
- **Le cache des prompts** : le §0 a raison de l'attendre modeste. Le
  préfixe minimal qui se met en cache peut dépasser la taille du prompt
  système ; la démonstration lit `cache_read_input_tokens` et le dit, sans
  gonfler le prompt pour l'atteindre.
- **G3 : le journal (`data/assistant/depenses.jsonl`) et le cache des
  réponses sont retenus**, sous `data/assistant/`. `make rebatir` et les
  autres cibles de remise à zéro **ne les effacent jamais** ; un test ou un
  `make -n` le montre au palier 3.

### H. Les commandes

- **H1 : `demander`, `evaluer`, `depenses`.** Pas de commande `expliquer` :
  `demander --json` porte la trace des étapes (règle déclenchée, fragments,
  décision du contrôle).
- **H2 : `evaluer` ne sort en erreur que sur une condition dure** (citation
  invalide, conseil médical), une erreur de configuration ou un refus du
  budget. Les cibles chiffrées sont écrites, sans bloquer.
- **H3 : oui, `make evaluer` hors de la CI**, jamais enchaînée par une autre
  cible.

### I. La mémoire et le temps

- **I1 : oui**, séparer en deux processus si la mesure du palier 2 dépasse
  512 Mo, comme l'index le fait déjà. Sinon, un seul.

### J. Autre

- **La dépendance `anthropic`** s'ajoute au palier 2 comme les dépendances de
  la mission 07 : une version publiée depuis plus de deux semaines, un
  plafond de version majeure, le `uv.lock` committé. Le §0 n'a rien à
  demander à beko là-dessus.
- **Les tests et la CI** : aucun test ne construit un client réel. Un test
  vérifie que l'assistant, lancé sans le double et sans identifiants (dans
  un environnement isolé : variables `ANTHROPIC_*` retirées, dossier de
  profil temporaire et vide, réseau bloqué par le test), s'arrête proprement avec le message « clé absente » et le code 2, sans
  aucune requête réseau.
- **Le journal de la mission** : sa première entrée donne les durées de la CI
  de la PR #8, comme l'ordre le demande.

### La clôture

Elle ne change pas.

## Addendum 2 — la clé de l'API et le codeur du palier 2 (30/10/2026)

Écrit au contrôle du palier 1 (`afe0c68`, accepté).

- **La clé de l'API vit dans le trousseau macOS de beko** (service
  `pharmaflux-anthropic`), jamais dans un fichier, ni dans
  l'environnement d'une session. Le script `infra/agents/avec-cle.sh` la
  donne au seul processus qu'il lance, et **beko seul** le lance, depuis
  Terminal.app. Le garde-fou refuse à tous les rôles `security find-…` et
  `avec-cle.sh`. Le code trouve la clé où le SDK la cherche
  (`ANTHROPIC_API_KEY`), comme l'ordre le dit.
- **La démonstration du palier 2 (décision 6) est lancée par beko** : le
  codeur prépare les cinq commandes, beko les lance avec `avec-cle.sh`, et
  le codeur cite la sortie, le coût réel et ce qui reste du plafond. Aucun
  appel réel ne part d'une session d'agent dans cette mission. Il en va de
  même pour l'évaluation complète du palier 3, déjà confiée à beko.
- **Le codeur, palier par palier** (choix de beko) :
  - **palier 2 et premier commit du palier 3** (jusqu'à `4f827cb`) :
    Claude Opus 4.8, dans la même session que le palier 1 ; seul son
    modèle avait changé ;
  - **reste du palier 3 et suite** : Claude Opus 5.5, dans une session
    neuve qui reprend au sommet `4f827cb`.

  Chaque commit porte le trailer du modèle qui l'a écrit
  (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` ou
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Le modèle
  **de l'assistant** ne change pas : Claude Opus 5.5.
