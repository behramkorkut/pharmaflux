# Mission 03 — palier 3, réponse au contrôle

Contrôle du commit `be0ec60` ; le correctif est dans ce commit, fils de la fusion `2bd87e4`, et le contrôle est commité tel quel.

**Une référence introuvable est refusée avant la lecture du bus.** `reference_fichiers` et `reference_archive` lèvent `ReferenceIntrouvable` quand le dossier des fichiers d'événements de la sortie, ou `etat.json` avec `--racine`, n'existe pas ; `verifier-bus` sort avec le code 2 et « référence introuvable : <chemin> » avant de fabriquer le lecteur. La référence est devenue un objet (protocole `Reference`, classes `ReferenceFichiers` et `ReferenceArchive`) qui sait si une entité a une référence : au moins un fichier `.jsonl` dans son dossier, ou une entrée dans `etat.json` (`rejeu.entites_suivies`, nouvelle fonction publique). Une entité sélectionnée sans référence porte la différence « aucune référence pour cette entité : topic non relu » : son topic est décrit (configuration, partitions) mais ni relu ni comparé à un état vide. Trois tests unitaires : dossier d'événements absent (par la fabrique et par la commande, le lecteur n'est jamais fabriqué), `etat.json` absent, entité sans référence sous chacune des deux références ; les deux assertions qui comptaient sur la comparaison à vide sont remplacées. README et ADR 0007 : une phrase chacun.

**Sur le bus local** (topics de la démonstration) : `verifier-bus` sans `--sortie` → « référence introuvable : data/evenements/evenements », code 2 en 0,3 s (le dossier des événements est dans la sortie, d'où le chemin doublé : c'est bien lui qui manque) ; `--racine` sur une sortie sans `etat.json` → refus nommant le fichier ; la sortie de la démonstration sans le dossier `bdpm.disponibilite` → cette entité en différence « aucune référence », `bdpm.generiques` et la file conformes, code 2 en 0,4 s.

**Vérifications locales** (commit testé : ce commit, fils de `2bd87e4`, sur l'arbre commité tel quel)
| commande | résultat |
|---|---|
| `uv run ruff check .` (tout le dépôt, après la fusion de `main` qui raccourcit la ligne du garde-fou) | vert |
| `uv run ruff format --check .`, `uv run mypy src` | verts ; mypy sur 36 fichiers |
| `uv run pytest -q` avec le courtier | 446 passed en 28 s (dont les 6 d'intégration) |
| `python3 infra/agents/test_garde_fou.py`, `sh infra/git-hooks/test-crochets.sh` | OK ; conformes |

**Écarts à l'ordre** : aucun. **Questions pour l'IeC** : aucune. **Propositions d'évolution** : aucune.

**Refus de garde-fou** (signalé, non contourné) : `awk 'length > 100 {print FILENAME": "FNR}' infra/agents/test_garde_fou.py`, « awk » sur un chemin réservé ; je voulais voir si la ligne longue avait disparu, `ruff check .` le disait déjà.
