# Mission 02 — réponse au contrôle du palier 3

Contrôle : `docs/relectures/mission-02/controle-palier-3.md` (commit
`91c68d5`, committé tel quel). Le correctif, son test et la formulation de
l'ADR 0006 sont dans le commit qui suit. Aucun autre fichier touché.

## Correctif

**Rejeu complet interrompu puis `--reprendre`** : corrigé, dans l'ordre
demandé. `_traiter_entite` appelle d'abord `_retirer_etat`, qui relit
`etat.json`, en retire l'entité et le réécrit entier puis renommé (même
`_ecrire` que le reste) ; les deux dossiers de l'entité ne sont effacés
qu'ensuite. Quand l'entité n'est pas dans l'état (première exécution),
rien n'est écrit : la sortie d'un rejeu complet sur un dossier vide est
inchangée à l'octet, ce que les deux rejeux de la démonstration
confirment ci-dessous. `_ecrire_etat` et `_retirer_etat` partagent la
sérialisation (`_sauver_etats`). Dit dans l'ADR 0006, section « sortie
par archive et reprise », et dans la liste des tests d'exactitude.

Test `test_rejeu_complet_interrompu_puis_reprise` : un rejeu complet
par-dessus une sortie existante, dont la première archive des
présentations est rendue illisible ; le rejeu sort en code 1 avec
0 archive lue pour les présentations, `etat.json` n'a plus l'entrée des
présentations et garde celle de la disponibilité, le dossier des
événements est effacé ; l'archive rendue lisible, `--reprendre` relit les
12 archives et redonne les octets du rejeu complet de référence. Sans le
correctif, ce test échoue sur l'état qui garde encore l'entrée des
présentations (vérifié en rejouant le test sur le `rejeu.py` de
`5e102ec`).

Sur la copie du Mac, j'ai reproduit ton scénario avec l'état intermédiaire
que laisse désormais une coupure (entité retirée de l'état, dossiers
effacés), puis `--reprendre --fichier bdpm.presentations` : 3 archives
lues, 20 898 `creee` et 3 `supprimee`, 20 901 lignes, `diff -r` sans
différence avec le rejeu complet.

## Formulation

ADR 0006, section « Conséquences », coût : « près de deux fois au-dessus
des 256 Mo de l'unité du VPS : la chaîne n'y tourne pas avant d'être
réécrite en flux, ce que la mission 03 décidera ». La conclusion est
gardée.

## Écarts et proposition

Les trois écarts sont acceptés comme tu l'écris, le troisième avec le
correctif ci-dessus. Rien à ajouter sur la proposition PRD §6.3.

## Vérifications rejouées (arbre committé comme fils de `91c68d5`)

- `uv run ruff check .` et `ruff format --check` : vert (122 fichiers).
- `uv run mypy src` : vert, 30 fichiers.
- `uv run pytest -q` : **400 tests**, tous passent (399 + le nouveau).
- `python3 infra/agents/test_garde_fou.py` : 17 tests, OK ; crochets git
  passés au commit.
- Démonstration sur la copie du Mac, en lecture seule, sortie dans mon
  dossier temporaire : rejeu complet identique au `diff -r` à la sortie
  du palier 3 ; `--reprendre` par-dessus une copie de cette sortie :
  0 archive lue, aucune différence ; scénario de coupure ci-dessus.
  L'archive est intacte : 21 fichiers, aucun modifié.
- Non rejoués : `profil` et `questions verifier` (ni contrat ni
  vérification touchés), shellcheck (aucun `.sh` touché).
