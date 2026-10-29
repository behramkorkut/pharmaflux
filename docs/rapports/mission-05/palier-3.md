# Mission 05 — palier 3 : `make silver`, la CI, les docs, et D.1

Contrôle du palier 2 lu et commis tel quel (`b90c492`). Aucune commande
`docker compose` d'écriture de ma part ; c'est beko qui a enchaîné
`make rebatir` (avec son `down -v`), `make demo` puis `make silver` dans
`pharmaflux-codeur`, et m'a collé la sortie. `make` seulement en `-n` de
mon côté. Aucun refus du garde-fou, aucune requête vers les sources.

**Fait**

- **`Makefile`** : cible **`silver`** (après `make demo` : `silver
  consommer --entrepot data/demo/lakehouse`, puis `silver verifier` contre
  `demo/archive`, qui a le dernier mot : un écart arrête la cible en code 2)
  et cible **`etat`** (`ENTITE`, `A`, `ETAT_OPTIONS`, par défaut les
  présentations au 26/10 à 14:00) ; `make help` et `make rebatir` (qui
  efface aussi `data/demo/lakehouse`, dans `data/demo`) mis à jour.
- **CI** : étape « Silver du jeu depuis le bus, puis vérification contre
  l'archive (`make silver`) » dans le job `integration`, après `make demo`
  et avant le `down -v` ; le job `verifier` ne change pas.
- **Docs** : ADR 0009 (catalogue, schéma, SCD2 sur la date d'observation,
  application des événements, positions, reprise, vérification, mémoire,
  ce que le silver ne fait pas, les plafonds de versions **temporaires**) ;
  `README.md`, section « Le silver » avec les deux exemples réels (la
  présentation `3400938844948`, en arrêt de commercialisation, présente le
  24/10 à 23:17:11 et absente à 23:17:12 ; les informations importantes
  inchangées le 26/10 juste après 14:17:39, 10 905 versions ouvertes) ;
  `docs/CONTEXTE.md` ; l'entrée du journal.

**Sortie de beko** (`make silver`, Mac, 28/10 22:25 UTC, extraits) :

```
uv run pharmaflux silver consommer --entrepot data/demo/lakehouse
2026-10-28T22:25:29Z INFO bdpm.asmr : pharmaflux.bdpm.asmr.v1, 10117 message(s) à lire, lots de 10000
…
2026-10-28T22:25:39Z INFO bdpm.presentations : lot de 10000 (p0 5834-6884, p1 4166-6979, p2 0-6134) : 9993 ouverture(s), 7 fermeture(s), 0 doublon(s)
…
bdpm.presentations           20908 message(s), 0 doublon(s), 20898 ouverture(s), 10 fermeture(s), 3 commit(s) ; positions : p0 → 6885, p1 → 6980, p2 → 7043
…
entrepôt : data/demo/lakehouse ; grappe : redpanda.f614c4ee-52e8-4bc8-bf3b-b815f6773a3a ; 164106 message(s) ; durée : 14.4 s
uv run pharmaflux silver verifier --entrepot data/demo/lakehouse --sortie data/demo --racine demo/archive
…
bdpm.presentations           20898 version(s), 20888 ouverte(s), 3 fichier(s) Parquet, 5 snapshot(s) ; invariants : conformes
…
22/22 archive(s) conforme(s) ; durée : 10.4 s
```

Onze entités, 164 106 messages, 0 doublon, 24 commits, 10 fermetures (toutes
dans `presentations`) ; 22 archives conformes (18 retenues, 4 écartées),
invariants conformes ; mêmes comptes et mêmes positions qu'au palier 2.
Sur ce silver rebâti, les trois `make etat` du README rendent 1 version,
0 version et 10 905 lignes, comme écrit.

**D.1 : `down -v` et l'identifiant de grappe.** Témoin
`data/lakehouse-temoin-d1` (hors de `data/demo`) construit **avant** la
séquence par `silver consommer --fichier bdpm.presentations` sur la grappe
`redpanda.990d5d4e-41d8-4ab7-b318-a41701404a42` (20 908 messages, 3
commits, positions p0 → 6 885, p1 → 6 980, p2 → 7 043). La même commande,
**après** la séquence :

```
AVERTISSEMENT : bdpm.presentations : la table a été construite sur la grappe redpanda.990d5d4e-41d8-4ab7-b318-a41701404a42, le courtier est redpanda.f614c4ee-52e8-4bc8-bf3b-b815f6773a3a ; le contrôle des identifiants décide
bdpm.presentations           0 message(s), 0 doublon(s), 0 ouverture(s), 0 fermeture(s), 0 commit(s) ; positions : p0 → 6885, p1 → 6980, p2 → 7043 ; rien de nouveau
entrepôt : data/lakehouse-temoin-d1 ; grappe : redpanda.f614c4ee-52e8-4bc8-bf3b-b815f6773a3a ; 0 message(s) ; durée : 0.2 s
```

Donc : **la grappe change** à chaque `down -v` (Redpanda la tire de son
volume), **l'avertissement sort**, et **le contrôle des identifiants a
décidé « rien de nouveau »** : le jeu republié par `make demo` est le même,
dans le même ordre, et l'`id` d'un événement est le sha256 de son contenu,
si bien que le message à `offset − 1` de chaque partition porte bien l'`id`
gardé ; les positions tiennent, aucun commit, code 0, 128 Mo. L'attente du
palier 2 est confirmée. **beko efface le témoin** (`data/lakehouse-temoin-d1`)
quand il le veut ; je n'y touche pas.

**Vérifications locales** (commit testé : celui de ce rapport)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 202 files already formatted |
| `uv run mypy src` | Success: no issues found in 51 source files (0 `type: ignore`) |
| `uv run pytest -q` avec `GITHUB_ACTIONS=true` | **498 passed** en 2 min 00 s, dont 11 `integration` sur le courtier rebâti |
| `make -n silver`, `make -n etat`, `make -n help`, `make -n rebatir`, `make -n demo` | recettes relues ; les trois `make -n etat … \| sh` du README : 1 / 0 / 10 905 |
| `ruby -ryaml` sur `.github/workflows/ci.yml` | yaml ok |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK (21 tests) |
| `uv run pharmaflux demo verifier` ; `verifier-bus --sortie data/demo --racine demo/archive` | conforme ; 12/12 conforme sur le bus rebâti |

**Écarts à l'ordre**

1. **Non-régression** : `profil` et `questions verifier` sur
   `~/pharmaflux-data` ne sont pas rejoués à ce palier (aucun fichier de
   `src/` touché depuis le palier 2, où `bus/client.py` n'a gagné que des
   méthodes) ; `demo verifier` et `verifier-bus` le sont, sur le jeu rebâti.
2. **La durée réelle de l'étape CI** `make silver` n'est pas connue avant
   la publication par beko ; elle ira dans `pr.md`. Localement : 14,4 s +
   10,4 s.

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** : `--continu` (consommer en boucle) et une
`A` par défaut lue de `etat.json` iront dans `pr.md`, hors mission.
