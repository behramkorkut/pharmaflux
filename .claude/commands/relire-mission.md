---
description: Relire une mission Pharmaflux contre son ordre de mission (relecteur à contexte neuf), puis écrire la relecture dans le dossier du codeur
argument-hint: <numéro de mission, ex. 00>
---

Tu es le **relecteur** de Pharmaflux pour la mission $ARGUMENTS.

1. Lis `docs/agents/relecteur.md` : c'est ta consigne, elle s'impose.
   Puis `CLAUDE.md` (règles communes) et `docs/agents/processus.md`.
2. Repère la branche : `git worktree list` (celle du dossier
   `pharmaflux-codeur`). Place-toi sur son sommet :
   `git switch --detach <branche>`, puis note `git rev-parse --short HEAD`.
3. Lis l'ordre de mission et ses addenda :
   `git show main:docs/missions/` puis le fichier `mission-$ARGUMENTS-…`.
4. Lis les rapports du codeur (`docs/rapports/mission-$ARGUMENTS/`) et les
   relectures et contrôles précédents (`docs/relectures/mission-$ARGUMENTS/`).
   Le numéro de ton tour R = nombre de `relecture-*.md` existants + 1.
5. Relis selon la consigne, relance les vérifications locales.
6. Écris ta relecture dans
   `../pharmaflux-codeur/docs/relectures/mission-$ARGUMENTS/relecture-R.md`,
   au format de la consigne.
7. Termine par trois lignes : verdict, nombre de bloquants, chemin du
   fichier écrit. Rien d'autre à faire : beko transmet.
