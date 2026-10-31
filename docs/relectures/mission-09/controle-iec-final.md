# Mission 09 — revue finale de l'IeC

**Sommet revu** : `2aa19f7` (branche `mission-09-corpus-des-avis-has`).
**Verdict : fusion autorisée.** beko peut publier avec
`sh infra/agents/publier-mission.sh 09-corpus-des-avis-has`. La CI doit être
verte, et `pr.md` sert tel quel de description.

## Ce que l'IeC a vérifié

- **Les quatre paliers** ont été acceptés par contrôle écrit
  (`controle-palier-1.md` à `-4.md`). Le palier 4 a été ouvert par
  `decision-question-2.md` et sa suite (voie C).
- **La relecture 1** (Claude Fable 5.1, sur `4eaea81`) est CONFORME, sans
  bloquant. Ses cinq points non bloquants ont été tranchés, et les corrections
  sont faites :
  - `1c88fe7` corrige les chiffres, le journal et les dates. Je ne retrouve
    plus aucun chiffre d'avant le palier 4 hors des passages qui le disent.
    Le journal ne reçoit que des ajouts par rapport à `main`, plus une date
    corrigée dans l'entrée de cette mission ;
  - `881300b` ajoute le test direct de `couper_ligne`, sans toucher au code ;
  - `2aa19f7` contient la réponse point par point et la relecture, committée
    sans modification.
- **Le code** est identique, depuis `aba5173`, à celui de l'évaluation
  finale. Les commits suivants ne touchent que les docs et les tests.
- **`--estimer` sur la v2** affiche 0 appel à faire : les descriptions
  corrigées ne changent ni la clé du cache, ni les empreintes figées.
- **`GITHUB_ACTIONS=true uv run pytest -q -rE -rs`** sur `2aa19f7` :
  **919 passed**.
- **`main` est poussé** : `git log origin/main..main` est vide après
  `git fetch`.

## Le bilan de la mission

- **Le corpus** :
  - 722 pages d'avis collectées poliment par beko (724 requêtes,
    0 erreur) ;
  - 721 extraites, 1 rejetée pour un vrai défaut de la page (PEDMARQSI) ;
  - à l'index, 121 pages sans fiche du référentiel restent dans l'archive,
    comptées et listées.
- **L'assistant** cite la page d'avis avec ses trois dates, et le LLM ne voit
  aucune adresse.
- **L'évaluation finale** :
  - v1 : 48/49 réponses correctes ;
  - v2 entière : 88/91 réponses correctes, 26/26 liens rendus ;
  - conditions dures à 0, aucun faux refus.
- **Le coût** : 3,82 $ sur un plafond de 10 $, tout parti avant le 16/11. La
  constante 1,7 n'a sous-estimé aucun des 190 appels.
- **La rigueur de mesure a tenu.** Les questions qui mesurent chaque retouche
  ont été figées avant elle, à trois reprises (`bbb9809`, `c80b795`,
  `34dca25`). Rien n'a été retouché après une évaluation. Les échecs sont
  analysés depuis le texte des réponses, y compris la régression de
  `historique-008`.

## Sur `pr.md`

La description est longue (environ 420 lignes). Je l'accepte : elle porte
deux évaluations, un palier ouvert en cours de mission et une relecture, et
chaque section se lit seule. Les chiffres que j'ai recoupés concordent avec
les sorties de beko et les fichiers de détail.

## Reporté à la mission 10 ou plus tard

À reprendre dans l'ordre de la mission 10 :
- **le filtre des liens par dossier** (`avis_has-044`) ;
- **le regroupement des citations d'une même page** sous un seul lien ;
- **la marge mémoire de `index verifier`** : 502 Mo chez beko, pour un seuil
  de 512 Mo.

Pour plus tard :
- **la consigne des dates** à mesurer sur plusieurs tirages
  (`historique-008`) ;
- **la branche inatteignable du client HAS** et le statut des mentions sans
  `<main>`, à la prochaine évolution de la collecte ;
- **les PDF d'avis** et **la collecte périodique**, chacun avec sa mission et
  son ADR ;
- **la liste des faux positifs du garde-fou**, à corriger par l'IeC :
  `shasum` sur `docs/relectures/`, et une commande `sed` qui nommait
  `avec-cle.sh`.

## Commande pour beko

Depuis `pharmaflux/`, dans Terminal.app, une fois le codeur ayant committé ce
fichier :

```bash
git fetch origin && git log --oneline origin/main..main
sh infra/agents/publier-mission.sh 09-corpus-des-avis-has
```

La première commande ne doit rien afficher. Si la CI échoue, lire le journal
de la CI avant toute relance.
