# Mission 06 — palier 3 : `Makefile`, CI, docs (décisions 5, 6 et 7)

Contrôle du palier 2 lu et committé tel quel (`e2d8e79`). Aucune commande
`docker`, `colima` ni `make <cible>` de ma part (seulement `make -n`) ;
`~/pharmaflux-data` en lecture seule ; aucune requête vers les sources ;
aucun refus du garde-fou.

**Fait**

- **Les deux demandes du contrôle du palier 2** : le refus d'un instant non
  observé donne le premier instant où les onze entités le sont (« les onze
  sont observées à partir de 2026-10-24T19:42:06Z » sur le jeu), testé ;
  `conftest.py` dit pourquoi `pharmaflux.silver` est importé en premier
  (allocateur système d'Arrow, 524 Mo contre 945).
- **`Makefile`** : `make gold` (`gold qualite`, puis `questions verifier
  --racine demo/archive --entrepot data/demo/lakehouse`) et `make fiche
  CIS=… A=…` (`A` n'est pris que s'il est donné sur la ligne de commande :
  son défaut sert à `make etat`) ; l'aide les décrit.
- **CI** : l'étape « Gold du jeu, contrôles de qualité et questions (make
  gold) » dans le job `integration`, juste après « make silver » ; le job
  `verifier` ne change pas.
- **Docs** : ADR 0010 (forme, instants et jour UTC, typage, vues, contrôles,
  questions, `fin_validite` hors du gold, texte de la fiche qui n'engage pas le
  Lot 3, section « Limites ») ; README, section « Le gold », avec la fiche de
  63830632 à 23:17:11 et à 23:17:12 le 24/10 et la disponibilité de LARIAM
  (3400933961688, `portee = specialite`), et les six commandes `gold` ;
  `CONTEXTE.md` ; journal.

**`make -n`**

```text
$ make -n gold
uv run pharmaflux gold qualite --entrepot data/demo/lakehouse
uv run pharmaflux questions verifier --racine demo/archive --entrepot data/demo/lakehouse
$ make -n fiche
uv run pharmaflux gold fiche --entrepot data/demo/lakehouse --cis 65999556  --format texte
$ make -n fiche CIS=63830632 A=2026-10-24T20:00:00Z
uv run pharmaflux gold fiche --entrepot data/demo/lakehouse --cis 63830632 --a 2026-10-24T20:00:00Z --format texte
$ make -n etat
uv run pharmaflux silver etat --entrepot data/demo/lakehouse --entite bdpm.presentations --a 2026-10-26T14:00:00Z
```

**Démonstration de beko** (29/10/2026, Mac, dans `pharmaflux-codeur/`,
`make rebatir`, `make demo`, `make silver`, `make gold`) :

- `make demo` : schémas enregistrés neufs (`id 1`), 22 archives, 18 fichiers
  publiés, 4 écartés, 67 h 35 min observées rejouées en 4 min 03 s ;
  `verifier-bus` conforme sur les onze topics et la file des échecs (vide).
- `make silver` : 164 106 messages en 14,2 s, grappe neuve
  `redpanda.16b5a664-…` ; `silver verifier` **22/22 conformes** en 10,0 s.
- `make gold` : « 14 contrôles à 2026-10-27T00:17:12Z : 4 bloquants, 10
  mesurés ; **aucun bloquant ne tombe** », chaque contrôle à son chiffre du
  §0 (5 → 4, 6 → 5 562, 7 → 1 268, 8 → 1, 9 → 23, 10 → 2 375, 11 → 5,
  12 → 1, 13 → 18 383, 14 → présentations 20 888, −7) ; puis « 40
  question(s) : 25 conforme, 5 non calculable, 10 sans attendu. » et
  « **25 question(s) depuis le gold : 25 concorde.** »

La mission est close au sens de l'ordre. Chaque commande `uv run` affichait
un avertissement d'`uv` : le shell de beko avait le `.venv` de `pharmaflux/`
actif (`VIRTUAL_ENV`), qu'`uv` ignore au profit de celui du projet. Sans
effet sur le résultat.

**Vérifications locales** (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | verts (228 fichiers) |
| `uv run mypy src` | vert, 58 fichiers |
| `GITHUB_ACTIONS=true uv run pytest -q` | **535 passed** en 145 s (les 11 `integration` ont tourné) |
| crochets git / garde-fou | conformes / OK |
| YAML de la CI (`ruby -ryaml`) | lu sans erreur |
| shellcheck | sans objet : aucun `.sh` touché |
| `demo verifier` ; `profil`, `questions verifier` sur `~/pharmaflux-data` | conforme ; 0 bloquante ; 25 / 5 / 10 |
| `evenements` sur la copie du Mac, `diff -r` contre `53f261b` | identique |
| `silver verifier` sur le jeu ; `gold qualite` | 22/22 ; aucun bloquant |

**Écarts à l'ordre** : aucun.

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** (pour `pr.md`) :
1. une mission de détection qui compare aussi les règles d'anomalie d'une
   ligne (ADR 0010, « Limites ») ;
2. la date du dernier fichier retenu par entité, portée par le silver, pour
   que la fiche cite la dernière republication et non la seule ouverture de
   la version ;
3. la section « État » du README est restée à la mission 02 (tableau des lots
   compris) : une mise à jour, hors de l'ordre de cette mission.
