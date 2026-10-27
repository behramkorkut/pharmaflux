# Mission 03 — contrôle des correctifs du palier 2 (IeC)

**Commit contrôlé** : `a805da5`. **Verdict** : les trois correctifs sont
**acceptés**. Passe au palier 3.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `a805da5`, avec le courtier du
projet démarré :

- ruff check et format : vert ;
- mypy, 35 fichiers : vert ;
- pytest : 434 tests, tous passent ;
- `pytest -m integration` : 3 tests, verts en 5,5 s ;
- `rpk cluster config get auto_create_topics_enabled` : `false` ;
  `write_caching_default` : `"true"`, la propriété du mode dev-container
  est donc conservée.

## Sur les correctifs

1. **Création automatique coupée.** Passer par `.bootstrap.yaml` est la
   bonne voie en v26.2. Le compose dit qu'un changement de ce bloc demande
   `down -v`, et comment le vérifier. Le test d'intégration montre l'échec
   attendu, sans création de topic. Le délai de propagation en paramètre,
   avec le défaut de librdkafka gardé, est raisonnable.
2. **Topic pris du dossier.** Une ligne discordante est refusée et part
   dans la file des échecs, avec les deux entités nommées.
3. **sha256 des octets publiés.** Il est calculé dans la même lecture que
   la publication, lignes vides comprises : c'est donc le sha256 du
   fichier entier, et la vérification par blocs donne le même.

La docstring est alignée, et l'ADR 0007 dit pourquoi le `schema_id` est
partagé et comment la grappe est amorcée.

## Suite

Le palier 3 :
- `verifier-bus`, qui vérifie la rétention des topics ;
- le job `integration` de la CI ;
- le rapport, qui nomme les deux écarts possibles entre le Mac et la CI
  (l'architecture et la version de Compose).

Le garde-fou de `main` va recevoir deux affinements : les continuations
de ligne et `find` en lecture. beko fusionnera `main` dans ta branche ;
s'il ne l'a pas fait, ne t'en préoccupe pas.
