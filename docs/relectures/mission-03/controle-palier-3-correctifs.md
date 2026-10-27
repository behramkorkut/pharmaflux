# Mission 03 — contrôle du correctif du palier 3 (IeC)

**Commit contrôlé** : `24a9242`, fils de la fusion `2bd87e4`. **Verdict** :
le correctif est **accepté**. La mission est prête pour la relecture.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `24a9242`, avec le courtier du
projet démarré :

- `ruff check .` sur tout le dépôt : vert ; l'E501 corrigée sur `main` est
  arrivée par la fusion ;
- ruff format et mypy (36 fichiers) : verts ;
- pytest : 446 tests, tous passent ;
- `pytest -m integration` : 6 tests, verts en 13,7 s ;
- `verifier-bus` sans `--sortie` : « référence introuvable :
  data/evenements/evenements », code 2, avant toute lecture du bus ;
- `verifier-bus --racine` sur une sortie sans `etat.json` : le refus nomme
  le fichier ;
- `verifier-bus` sur la sortie de démonstration : code 0, 12 topics sur 12
  conformes.

## Sur le fond

- Le refus intervient avant la création du lecteur. Une référence absente
  ne touche donc jamais au courtier.
- La référence devient un objet qui sait si une entité a une référence :
  - avec les fichiers d'événements, il faut au moins un `.jsonl` dans le
    dossier de l'entité ;
  - avec `--racine`, il faut une entrée dans `etat.json`.

  Une entité sans référence est dite en clair, et son topic n'est ni relu
  ni comparé à un état vide. Sa configuration est quand même vérifiée.
- Une entité connue d'`etat.json` mais sans snapshot retenu est comparée à
  un état vide. C'est juste : son état attendu est bien vide.
- Les trois tests couvrent les cas demandés, et le README et l'ADR 0007 sont
  alignés.

## Garde-fou

Le refus de `awk` sur un chemin réservé est le comportement voulu, pas un
faux positif : `awk` peut écrire (`print > fichier`) et lancer des commandes
(`system()`), il n'est donc pas classé en lecture. `wc -L` ou `grep -n` font
le même contrôle de longueur.

## Suite

Commite ce contrôle tel quel. beko lance ensuite `/relire-mission 03`.
