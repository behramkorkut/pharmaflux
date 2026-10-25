# Mission 00 — revue finale (IeC)

**Commit revu** : `ad42b79` (`pr.md`), arbre testé `0832dad`.
**Verdict** : **feu vert**, sous réserve de deux corrections factuelles
dans `pr.md`. Elles se font dans un commit à part, sans nouvelle relecture.

## Ce que j'ai vérifié

- Le critère de clôture de l'ordre (addendum 2) : **atteint**. `pharmaflux
  etat`, relevé sur le VPS le 25/10/2026 à 21:17 UTC, montre 24 passages
  planifiés en 24 h sur les douze entrées horaires, 1 sur les deux
  quotidiennes, 0 erreur. Le premier changement réel de la BDPM a été
  capté et archivé une seule fois. Les 302 dernières lignes du manifeste
  sont en `1ccc9c0` : le filet et la lecture en flux tournent en
  production.
- Le circuit : trois contrôles de palier, une consigne et deux relectures
  (NON CONFORME, puis CONFORME) sont tous traités, avec leur réponse
  commitée. Les fichiers de `docs/relectures/` sont commités tels quels.
- Les vérifications, rejouées pendant les contrôles : ruff, format, mypy,
  pytest (66), garde-fou, crochets git et shellcheck (par `uvx`).
- `pr.md` : la structure demandée est respectée, et le contenu concorde
  avec le code, les rapports et les relevés du VPS, à deux points près.

## Corrections demandées dans `pr.md`

1. **Écart 1** : « `ruff` exclut `.claude/` et `infra/agents/` » n'est
   plus vrai. `extend-exclude` a été retiré de `pyproject.toml`, comme le
   demandait le contrôle du palier 1, et ces fichiers passent ruff. Garde
   `typer` (prévu par l'ordre) et remplace le reste par l'alignement
   réellement fait : les fichiers de l'IeC suivent la configuration ruff du
   projet.
2. **Archive bronze** : « écrite par fichier temporaire puis renommage » ne
   décrit pas le code. `archive.py` publie par **lien dur** (`os.link`), qui
   échoue si le nom existe déjà : la réécriture est impossible, pas
   seulement interdite. C'est le point fort que le relecteur a relevé, il
   faut le décrire exactement.

Une retouche facultative : l'écart 8 se lit mal (« `main` a reçu depuis la
branche »). Propose plutôt : « Depuis la création de la branche, `main` a
reçu… ».

## Suite

1. Fable : un commit « pr.md, corrections de la revue finale », qui commite
   aussi ce fichier sans le modifier. Puis arrêt avec « pr.md corrigé
   `<sha>` ».
2. beko : `sh infra/agents/publier-mission.sh 00-socle-et-archivage`, puis
   fusion après la CI verte.
3. Après la fusion : sur le VPS, retour sur `main` (étape 4 du README de
   planification) entre deux passages. Puis un premier rapatriement sur le
   Mac (étape 8), seul livrable qui n'a pas encore tourné pour de vrai.
