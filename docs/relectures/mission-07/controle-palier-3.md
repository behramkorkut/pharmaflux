# Mission 07 — contrôle du palier 3 (IeC)

**Commits contrôlés** : `8aaa58d` (le palier) et `97c09fd` (le modèle en
cache dans la CI), fils de `738b1b0`, qui porte le contrôle du palier 2 tel
quel. Ils sont contrôlés contre l'ordre, l'addendum 1 et les contrôles 1
et 2. **Verdict : conforme.** La clôture reste à faire : la séquence de
beko, avec le second point de mémoire.

## Revérifié par l'IeC

Dans ton dossier, arbre propre sur `97c09fd`, Redpanda, Qdrant et les
fichiers du modèle présents :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts (260 fichiers) |
| `uv run mypy src` | vert, 67 fichiers |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **599 passed** en 4 min 15 s |

Relu :

- **Les CIS touchés** (`index/changements.py`) :
  - versions ouvertes ou fermées dans `]t0, t1]` ;
  - liens vers les avis, à `t0` et à `t1` ;
  - bascules du jour.

  J'ai vérifié les bornes des bascules contre le calcul de la fiche
  (`gold/vues.py`) :
  - `debut_a_venir = date_debut > jour` change quand `date_debut` tombe dans
    `]j0, j1]` ;
  - une information est en cours quand `date_debut <= jour <= date_fin`.
    Elle entre quand `date_debut` tombe dans `]j0, j1]`, et elle sort quand
    `date_fin` tombe dans `[j0, j1[`.

  Rien d'autre dans la fiche ne dépend du jour. Les bornes sont justes.
- **La mise à jour** :
  - `vise` est écrit d'abord, l'instant à la fin ;
  - les nouveaux fragments sont écrits avant que les anciens soient
    retirés ;
  - un CIS disparu perd tous ses points ;
  - « rien à faire » est un succès ;
  - une coupure à chacune des quatre étapes, puis la reprise, redonne la
    reconstruction.
- **La vérification** suit les règles du contrôle 2. Elle compte en plus une
  mise à jour en suspens comme un écart. La correction de mémoire (une
  empreinte de 32 octets par fragment, des pages de 100) la fait passer de
  815 à **422 Mo** : c'est le genre de dépassement que la mesure
  systématique devait faire voir.
- **L'alias et l'état** : un alias que l'état ne décrit pas fait refuser
  `etat`, `chercher`, `verifier` et `mettre-a-jour`, avec la commande pour
  en sortir. `make index` reconstruit dans ce cas.
- **Les tranches** : 4 tranches, `verifier` conforme à chacune. À la fin,
  l'index est égal point pour point, vecteurs compris, à celui construit
  en une fois.
- **CI** :
  - deux `make index` avec l'encodeur de test ;
  - le modèle par `actions/cache@0057852b… # v4.3.0`, clé = le TOML,
    `installer` puis `verifier` ;
  - les tests `modele` exigés ;
  - un index réduit aux 16 CIS des questions, et trois recherches réelles ;
  - `timeout-minutes` à 20.
- **Docs** :
  - l'ADR 0011 est complet, avec les mesures des deux modèles, la recherche
    exacte et quand en revenir, et des limites honnêtes (les voisins de lot,
    le jeton « 3333 », les 624 Mo, l'état courant seulement, le score
    serré) ;
  - la section « État » du README est à jour.

## Écarts du rapport

1. **Le modèle en cache dans la CI** : levé par `97c09fd`.
2. **Le test par tranches tourne dans le job `verifier`**, contre le Qdrant
   simulé : accepté. Le job `integration` fait la même chaîne contre le vrai
   Qdrant. Le job `verifier` passe à environ 6 minutes : la proposition K2
   (le saut du courtier absent, plus rapide) est notée pour une mission
   ultérieure.
3. **`make index` choisit par `index etat`** : accepté. Un Qdrant injoignable
   fait échouer la construction en code 2, avec le message de Qdrant. Rien
   n'est écrit en silence.

## Pour la clôture

La séquence de beko, dans ton dossier :
- **Avant**, effacer `data/index/cache-vecteurs.sqlite`, pour que la
  première construction encode vraiment. Sans cela, le second point de
  mémoire et la durée ne mesurent rien.
- Puis `make rebatir`, `make demo`, `make silver`, `make gold`, et
  `make index` deux fois.

La clôture est atteinte si :
- **le premier `make index`** construit, et affiche un résident **sous
  512 Mo** pour chacun des deux processus, puis `verifier` est conforme ;
- **le second** dit « mise à jour par incréments », ne trouve rien à faire,
  puis `verifier` est conforme.

Tu cites la sortie dans `pr.md`, avec la durée de l'encodage. Si l'un des
deux résidents dépasse 512 Mo, la mission n'est pas close, et tu me le dis
avant toute autre chose.

Ensuite, la suite du circuit : la relecture (`/relire-mission 07`), `pr.md`,
puis la revue finale de l'IeC.
