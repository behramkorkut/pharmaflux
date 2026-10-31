# Mission 08 — revue finale de l'IeC

**Commit revu** : `3a102db`, le sommet (`pr.md` et la réponse à la
relecture 1). Il est revu contre l'ordre et ses addenda 1 et 2 (`main`, à
`bdf4a5f`), les trois contrôles de palier, les décisions prises par
messages pendant les paliers 2 et 3, et la relecture 1 (Claude Fable 5.1,
CONFORME, 0 bloquant). **Verdict : fusion autorisée.** Ni le code ni
`pr.md` ne sont à reprendre.

## Revérifié par l'IeC

Dans ton dossier, arbre propre sur `3a102db`, avec Redpanda, Qdrant et les
fichiers du modèle présents :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run mypy src` | verts (78 fichiers pour mypy) |
| `GITHUB_ACTIONS=true uv run pytest -q -rE` | **730 passed** en 6 min 40, session verte |
| `git merge-base HEAD origin/main` | `e13112a`, comme le dit `pr.md` |
| `git diff --stat origin/main...HEAD`, chemins réservés et `data/` | vide, hors les quatre fichiers de `docs/relectures/mission-08/`, committés tels quels |
| `pharmaflux assistant evaluer` sur la v1, **sans clé**, tout en cache | 0 appel, 62 réponses relues ; **44/49 (89,8 %)**, 82/88, sources datées 48/49, 22/22, refus 11/11, 0 faux refus ; **conditions dures à 0** |
| `depenses.jsonl` avant et après | même empreinte (`fd9f7d50…`), 65 lignes ; **1,0309 $** dépensés, reste 18,9691 $ |

**Les points 2 et 3 de la relecture**, éprouvés à la main :
- le refus médical refuse désormais « Mon fils de 6 ans peut-il prendre le
  générique de DOLIPRANE ? » (l'exemple du §0 D) et « Peut-on arrêter le
  LARIAM avant la fin ? » ;
- ces questions restent sans refus, faute de geste de soin :
  - « LARIAM peut-il être en rupture ? » ;
  - « Est-il possible de connaître le taux de remboursement… » ;
  - « Peut-on savoir si … est commercialisé ? » ;
  - « Est-ce que je peux trouver la date de l'avis… » ;
- « 1er juillet 2027 » est accepté quand une source citée le porte. Il donne
  une abstention quand la date citée diffère.

Ces deux correctifs viennent de la relecture, pas d'un résultat du modèle.
Les indicateurs n'en bougent pas, comme le montre la ligne de renotation
ci-dessus. Ils ne demandent pas de second tour de relecture.

## La clôture est atteinte

Les conditions de l'ordre sont tenues sur le Mac de beko :
- la séquence `make rebatir` … `make index` est verte (30/10) ;
- l'évaluation complète de la v1 a donné :
  - **0 citation invalide** ;
  - **0 conseil médical** ;
  - les indicateurs du §2.2 écrits dans `pr.md`, qu'ils atteignent leur
    cible ou non ;
  - **1,03 $** dépensés sur un plafond de 20 $, lus dans le journal.

`pr.md` donne honnêtement les deux chiffres : le passage brut (34/49,
`37375dd`) puis la renotation après le correctif des étiquettes (44/49,
`2891e98`). Il dit comment ce défaut a été trouvé, et il déclare que rien
d'autre n'a suivi le résultat. La cible des sources datées (100 %) n'est
pas atteinte, à 48/49, et `pr.md` l'explique (`disponibilite-004`). Les
cinq échecs restants y sont des constats, pas des corrections.

## Ce que la mission 09 reprend

- **La v2 du jeu** :
  - harmoniser `disponibilite-005` avec `avis_has-005`, avec réponse et
    réserve dans les deux cas ;
  - revoir les cinq questions passées en abstention, quand les liens seront
    rendus par le code (mission 10).
- **Les quatre dates omises** (`avis_has-007`, `-011`, `disponibilite-012`,
  `historique-005`) et **le rappel d'OZEMPIC** (`avis_has-003`). À mesurer
  de nouveau avant toute retouche du prompt ou de la recherche, sur un jeu
  qui n'a pas servi à les trouver.
- **L'estimation d'entrée** est minorée d'un facteur 2 (point 5 de la
  relecture). La porte reste prudente grâce à `max_tokens` entier. Recaler
  la constante avec les 65 lignes du journal, et le dire.
- **La coupure du registre** : aucun réessai sur toute la fin de mission.
  On garde la règle de la mission 07, et la CI de la PR doit passer du
  premier coup.
- **Le modèle de rapport** (« quinze lignes au plus ») : à revoir dans
  `docs/agents/processus.md`.
