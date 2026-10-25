# Mission 00 — palier 1

**Fait** : décisions 1, 2, 11, 12 de l'ordre (addendum 2 lu). `pyproject.toml` (uv, `uv_build`, httpx 0.28, typer 0.27, ruff, mypy strict sur `src/`, pytest), `uv.lock`, `.python-version` 3.12, `.gitignore` (`data/`, `*.gz`, `.venv/`, caches, `.env*`, `.claude/settings.local.json`, `.DS_Store`), squelette `src/pharmaflux/` (`cli.py`, `collecte/`), CLI déclarée (`collecte`, `etat`, `--version` ; les deux commandes sortent en code 2 jusqu'au palier 2), 4 tests de CLI, `tests/fixtures/README.md`, CI en un job avec cache uv (`.github/workflows/ci.yml` : ruff, format, mypy, pytest, crochets git, garde-fou, shellcheck conditionnel sur `infra/planification/*.sh`), `README.md`, `docs/CONTEXTE.md`, `docs/adr/0000-modele.md`, `docs/journal.md`.

**Vérifications locales** (arbre identique au commit de ce palier, fils de `7e58209`)
| commande | résultat |
|---|---|
| `uv run pharmaflux --help` / `--version` | aide avec les deux commandes ; `pharmaflux 0.1.0` |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 15 files already formatted |
| `uv run mypy src` | Success: no issues found in 3 source files |
| `uv run pytest -q` | 4 passed |
| `sh infra/git-hooks/test-crochets.sh` | 12 cas, « tout est conforme » |
| `python3 infra/agents/test_garde_fou.py` | Ran 14 tests, OK |
| shellcheck | non installé sur le Mac, en CI seulement ; aucun script encore |

**Écarts à l'ordre** : `typer` retenu plutôt qu'`argparse` (aide et validation des options gratuites ; 26 paquets verrouillés au total, aucune autre dépendance). `ruff` exclut `.claude/` et `infra/agents/` : ces outils de l'IeC ne passent pas sa règle (9 constats : 8 lignes de 101 à 103 caractères, 1 `N818` sur le nom `Refus`) et 2 fichiers seraient reformatés ; je ne les modifie pas. Pas de champ `license` dans `pyproject.toml` : choix de beko.

**Questions pour l'IeC** : garde-fou : `awk` n'est pas dans sa liste de lecture (`awk '/^## Addendum 2/{p=1} p' docs/missions/…` refusé ; relu avec `sed -n`). Est-ce voulu ? Sinon, l'ajouter à `LECTURE` avec `cut`, `sort`, `uniq`, `tr`.

**Propositions d'évolution** : aligner les fichiers de l'IeC sur `ruff` (ligne ≤ 100, `Refus` → `RefusError` ou `# noqa: N818`), ce qui permettrait de retirer l'exclusion. PRD §7.7 : README bilingue, à faire quand le README sera réécrit (Lot 1).
