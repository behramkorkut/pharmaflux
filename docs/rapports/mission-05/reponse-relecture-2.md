# Mission 05 — réponse à la relecture 2

Relecture du commit `4fa1cb3`, verdict CONFORME, aucun bloquant, un point
non bloquant et deux remarques de forme. Tout est corrigé dans ce commit,
son fils ; la relecture est commitée telle quelle. Aucun refus du garde-fou.

## À corriger

1. **Date seule impossible (`2026-02-30`) : trace Python, code 1.** La
   branche « date seule » de `lire_instant` appelait `fromisoformat` hors
   du `try`. Les deux formes bien formées (date seule, instant complet)
   passent maintenant par le même `try` : `SilverRefuse` « illisible » avec
   les formes acceptées, et la date seule reçoit minuit UTC après coup.
   Deux cas ajoutés à `test_lire_instant_utc_a_la_seconde` (`2026-02-30`,
   `2026-13-45`) ; `silver etat --a 2026-02-30` dit « état refusé : instant
   illisible » et sort en **code 2** ; `--a 2026-10-26` rend toujours les
   20 896 versions valides à minuit UTC. L'ADR 0009 ajoute « d'une date
   impossible » à la liste des refus.

## Remarques

- **Message de `uri_entrepot`** : il dit maintenant aussi qu'un caractère
  non imprimable est refusé.
- **ADR 0009, ligne trop longue** du paragraphe « État à une date » :
  reprise à la largeur du fichier.
- **Mesures** du relecteur (`construire` 10,4 s et 295 Mo, `verifier`
  10,8 s et 333 Mo) : cohérentes avec celles du palier 1 et du palier 2 ;
  rien à ajouter.
- **Non-régression sur `~/pharmaflux-data`** : en une passe pour `pr.md`,
  sur le commit testé.

**Vérifications locales** (commit testé : ce commit, fils de `4fa1cb3`,
courtier du Mac en marche)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 207 files already formatted |
| `uv run mypy src` | Success: no issues found in 51 source files |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true` | **500 passed** en 2 min 03 s, intégration comprise |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| `uv lock --check` | Resolved 56 packages, verrou inchangé |
| `silver etat … --a 2026-02-30` / `--a 2026-10-26` | code 2, « illisible » / 20 896 versions à `2026-10-26T00:00:00Z` |

**Écarts à l'ordre** : aucun nouveau.
