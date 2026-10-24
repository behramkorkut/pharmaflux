# Mission 00 — contrôle des correctifs et du palier 3 (IeC)

**Commits contrôlés** : `3b805c7` (correctifs), `891efb6` (palier 3).
**Verdict** : correctifs acceptés ; palier 3 accepté **sous réserve
d'un correctif de procédure** (P1).

## Vérifications rejouées

ruff (check et format), mypy strict, pytest (54 tests), garde-fou
(15 tests), `sh -n`, et **shellcheck** sur `rapatrier.sh` (lancé par
`uvx --from shellcheck-py`, sans installation) : tout est vert.

## Correctifs du palier 2

- **C1** : conforme. Toute archive écrite laisse son empreinte, et les
  motifs d'erreur s'enchaînent au lieu de s'écraser.
- **C2** : conforme. **Ta marque de troncature me convient** (ta
  question) : on ne fait qu'ajouter en fin de fichier, rien n'est
  réécrit, et la règle « ligne illisible au milieu = erreur franche »
  reste vraie. Un simple `\n` aurait obligé à affaiblir cette règle.
- **Entrée `bdpm.documentation_formats`** : conforme.

## Correctif demandé

**P1. La procédure échoue à l'étape 4.** `useradd --create-home` crée
`/home/pharmaflux` en 750 (Ubuntu ≥ 21.04) ou en 700. Or
`cd /home/pharmaflux/pharmaflux` est lancé par l'utilisateur SSH de
beko, qui n'est pas dans le groupe `pharmaflux` avant l'étape 8. Le
`cd` échoue, et `sudo install infra/planification/…` à l'étape 5
(chemins relatifs) aussi. Attendu :

- **aucun `cd` dans la procédure** : uniquement des chemins absolus
  (`sudo install -m 644 /home/pharmaflux/pharmaflux/infra/planification/… /etc/systemd/system/`),
  et `git -C /home/pharmaflux/pharmaflux pull --ff-only` à l'étape 7.
  Cette règle vaut pour beko sur son VPS, pas pour toi ;
- l'ajout au groupe (`usermod -aG`, `chmod 750`) passe **à l'étape 2**,
  avec la mention « se reconnecter en SSH pour que le groupe prenne
  effet ».

## Point à ajouter dans la procédure : installer depuis la branche de mission

Le code du collecteur ne sera sur `main` qu'après la fusion de la PR, et
la mission ne se ferme qu'après 24 h de passages sur le VPS. L'étape 4
doit donc prévoir :

- le clone de la branche de mission : `git clone --branch mission-00-socle-et-archivage …` ;
- le retour sur `main` après la fusion : `git -C … switch main` puis
  `pull --ff-only` et `uv sync --frozen --no-dev`.

Ajoute ces deux variantes.

## Écarts et interprétations

Les points 1, 2, 4 et 5 sont acceptés : `.venv/bin/pharmaflux` direct,
`--no-dev`, `failed` visible quand une entrée est en erreur, unités
relues mais pas exécutées.

## Remarques mineures (pas bloquantes, à faire si tu touches au fichier)

- Coquille du compte : `--shell /usr/sbin/nologin` suffit, puisque toutes
  les commandes passent par `sudo -u pharmaflux … <commande>`. Un compte
  sans shell de connexion réduit la surface d'attaque.
- Installation d'`uv` : figer la version dans l'URL
  (`https://astral.sh/uv/<version>/install.sh`, la version de `uv.lock`
  ou celle de ton Mac), plutôt que la dernière à chaque installation.

## Propositions

- **(a) `etat` affiche l'identifiant** : accepté, à la mission 01.
- **(b) `etat` signale les `.partiel-*` orphelins** : accepté, à la
  mission 01.
- **(c) Journal en UTC** : accepté, à faire au prochain passage dans
  `cli.py`.

Une alerte sur échec (`OnFailure=` vers une notification) sera traitée
plus tard. Pour l'instant, beko lit `pharmaflux etat`.

## Suite

1. Un commit « correctifs du contrôle du palier 3 » (P1 et l'installation
   depuis la branche, plus les remarques mineures si tu le veux), puis
   arrêt avec « correctifs palier 3 `<sha>` ».
2. Ensuite, beko pousse la branche, installe sur le VPS et lance le
   relecteur pendant les 24 h.
3. Ne pas écrire `pr.md` maintenant : il attend le résultat des 24 h de
   passages.
