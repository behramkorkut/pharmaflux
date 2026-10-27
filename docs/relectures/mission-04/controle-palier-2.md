# Mission 04 — contrôle du palier 2 (IeC)

**Commit contrôlé** : `aa079da` (fils de `180f577`), contre l'ordre et
l'addendum 1. **Verdict : conforme, passe au palier 3.**

## Revérifié par l'IeC

Sur une extraction du commit (`git archive aa079da`), courtier
`pharmaflux` démarré :

| commande | résultat |
|---|---|
| `uv run pytest -q` | 470 passed (intégration comprise) |
| `uv run ruff check .` / `uv run mypy src` | verts (40 fichiers) |

Relu dans le code :

- **Le découpage `preparer` / `publier_fichier`** : `executer` enchaîne
  les deux, si bien que `publier` et `demo rejouer` partagent un seul
  code de publication. F.3 est dans `preparer` et couvre donc les deux
  reprises.
- **La table de `verifier_etat_du_bus`** compte quatre cas : bus vide
  sans état, bus publié avec état, bus non vide sans état, état sans bus.
  Le jugement passe avant le rejeu de 9 s, donc un refus est immédiat.
  Il ne compte que les topics du préfixe, si bien que les sujets créés
  par les tests d'intégration ne le faussent pas. Un rejeu coupé entre
  la création des topics et le premier fichier donne « bus non vide sans
  état », puis `make rebatir`. C'est l'issue prudente.
- **L'horloge** : chaque événement a une cible absolue, sans pause
  négative, donc un retard se rattrape au lieu de s'accumuler. L'horloge
  et le sommeil sont injectables, et les tests vérifient les instants
  sans dormir.
- **La reprise** écarte les fichiers déjà publiés et tout ce qui précède
  le premier fichier à publier. L'état est écrit après chaque fichier.
- **F.2 contre le vrai registre** : l'obligation du contrôle 1 est
  tenue.

## Mesures (Q5)

145 Mo de mémoire résidente maximale pour `demo rejouer`, sous le seuil
de 256 Mo. Le pic `tracemalloc` va de 0,7 à 35,8 Mo par entité. Le
déroulé dure 4 min 03 s pour 67 h 35 min observées. L'IeC reporte ces
mesures au PRD §9.

## Écarts du rapport

1. **59 passages sans archive, au lieu de 49** : accepté. Le §0 comptait
   mal, et ni l'ordre ni le README du jeu ne reprennent le chiffre faux.
2. **La troisième entité du test vient de `fixtures/bdpm`** : accepté.
3. **`down -v` après avoir prévenu, sans attendre** : conforme à la
   lettre de l'addendum (« préviens en une ligne »). Pour la suite,
   toute commande qui efface un volume attend la réponse de beko.
4. **Le motif sans l'archive** sur la ligne d'un fichier retenu sans
   événement : accepté, puisque le bilan garde l'archive.

Le rapport fait 13 lignes : merci.

## Pour le palier 3

- **`prerequis.sh`** : la sortie dans les deux cas, image présente puis
  absente, et la commande `docker compose config --images` vérifiée sur
  le Mac (correction 1 de l'addendum).
- **Le README** : la séquence pour une machine qui a déjà un volume
  `pharmaflux` (`make demo` refuse, `make rebatir`, puis `make demo`) et
  la sortie de `make -n rebatir` dans le rapport (correction 2).
- **L'étape CI** `make demo DEMO_OPTIONS=--sans-pause` : ses limites
  vont dans `pr.md`.
- **`pr.md`** devra citer la taille du jeu dans git, mesurée par beko :
  6,68 Mio d'objets en vrac contre un pack de 836 Kio avant le jeu.
