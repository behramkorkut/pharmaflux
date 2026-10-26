# Mission 02 — réponse au contrôle du palier 1

Contrôle : `docs/relectures/mission-02/controle-palier-1.md` (commit
`55d0530`, committé tel quel). Les trois correctifs sont dans le commit qui
suit, tests compris. Aucun autre fichier de code touché.

## Correctifs

1. **Signe de `-0,50`** (`verification.forme_decimale`) : corrigé. La
   partie entière canonique garde le `-` dès qu'un chiffre du nombre n'est
   pas nul ; `-0,00` devient `0.00` (choix écrit dans l'ADR 0005, tableau
   des types). `_entier_canonique` est remplacé par
   `_partie_entiere_canonique(chiffres, decimales)`, docstring revue. Le
   type `entier` garde `str(int(...))` (`-0` → `0`), conforme à l'ADR.
   Tests : `-12,50` → `-12.50`, `-0,50` → `-0.50`, `-0,00` → `0.00`,
   `-00,01` → `-0.01`, `-1,003,48` → `-1003.48`.
2. **Chiffres non ASCII dans les milliers** : corrigé, `_motif_milliers`
   utilise `[0-9]`, docstring et ADR mis à jour. Tests : `٤,٢٠٠,48`,
   `1,٠٠٣,48`, `1,003,4٨` sont `decimal_illisible`.
3. **Clé normalisée répétée** : corrigé, le snapshot est **écarté**.
   `depuis_lecture` compte les collisions de clé normalisée ; `_motif_ecart`
   ajoute « clé normalisée non unique : N clé(s), M lignes, première ligne
   K » (M = toutes les lignes des clés répétées, K = première ligne de la
   première clé répétée), après le motif des bloquantes s'il y en a, séparé
   par « ; ». Le commentaire faux est remplacé. ADR 0005 : un paragraphe
   dans « Snapshot normalisé ». Tests : `" liste I"` / `"liste I"` /
   `"liste I "` et `"liste II"` / `"liste II "` dans la clé de
   `bdpm.conditions_prescription` (lignes fabriquées à partir de la première
   ligne de la fixture, aucune bloquante brute, trois `espace_parasite`) →
   écarté, « 2 clé(s), 5 lignes, première ligne 1 », entités 2, doublons 3 ;
   `01` / `1` dans `numero_liaison` de `bdpm.compositions` → écarté, sans
   `cle_non_unique`. La fixture fabriquée des spécialités (clés brutes
   répétées) porte désormais les deux motifs.

Vérification sur la copie du Mac (lecture seule) : **toutes** les archives
des onze fichiers relues en snapshot, aucun snapshot à clé écarté, aucune
collision.

## Vérifications rejouées (arbre committé comme fils de `55d0530`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 106 files already formatted |
| `uv run mypy src` | Success: no issues found in 25 source files |
| `uv run pytest -q` | 347 passed (+10) |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK |
| shellcheck | non lancé, aucun `.sh` touché (contrôle, « Refus signalé ») |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` ; `questions verifier` | 11 fichiers, 0 bloquante ; 25 / 5 / 10 |

## Écarts et proposition

Les deux écarts sont acceptés par le contrôle ; rien à ajouter. Pas de
nouvelle question. J'attends l'accord de l'IeC pour le palier 2.
