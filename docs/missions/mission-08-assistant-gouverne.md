# Mission 08 — L'assistant gouverné : recherche hybride, réponses sourcées et datées, abstention, refus médical, jeu de questions v1

**À :** Claude Opus 5.5 (codeur) · **De :** ingénieur en chef (IeC)
**Réf. :** PRD v0.9 §1.6, §2.2, §4 (Lot 3), §6.7, §6.8, §7.4, §7.5, §9,
annexe B · mission 07 (`pr.md`, `controle-iec-final.md`) · ADR 0003, 0004,
0010 et 0011 · `evaluation/README.md` · `CLAUDE.md` ·
`docs/agents/processus.md`
**Statut :** ordre rédigé le 30/10/2026 — **§0 à rédiger**
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
