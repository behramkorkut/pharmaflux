# Mission 07 — l'index de l'assistant : fragments du gold, Qdrant, e5-small-int8, mise à jour par incréments vérifiée ; une CI fiable

Branche `mission-07-fragments-et-index`, depuis `69b2df1` (le `main` du
départ). `main` porte en plus l'addendum 1 (`241bff0`) et les écritures de
l'IeC ; il n'y a pas de conflit, la branche ne touche à aucun chemin réservé.

- Ordre de mission : `docs/missions/mission-07-fragments-et-index.md`
  (addendum 1) ; codeur : Claude Opus 5.5.
- §0 en `f7e4d1b` ; trois paliers acceptés par l'IeC ; trois contrôles
  commités tels quels dans `docs/relectures/mission-07/`.
- Relecture 1 : **CONFORME**, 0 bloquant. Ses trois points non bloquants
  sont corrigés en `50e7533` (`reponse-relecture-1.md`) ; pas de tour 2.
- Revue finale de l'IeC : à venir, sur le commit qui porte cette
  description.

## Ce qui est livré

**Une CI fiable** (palier 1). La coupure du registre de schémas se
reproduisait sur le Mac : un `POST …/versions` sans réponse, 15 à 20 ms après
que le test précédent avait effacé ses topics. La cause interne à Redpanda
reste une hypothèse. Les corrections :
- le client réessaie deux fois un appel coupé **sans réponse** (0,2 puis
  0,8 s), jamais une réponse ni un délai dépassé, avec une ligne horodatée ;
- les tests effacent sujets et topics une fois, en fin de session ;
- un réessai pendant les tests d'intégration fait échouer la session, sauf
  dans le test de reproduction, qui en affiche le nombre (30 cycles) ;
- `supprimer` tente la suppression définitive même après un 404 ;
- le healthcheck attend aussi le registre ;
- en CI, les loggers du registre passent en `debug`, `-rE` est actif, et le
  diagnostic du courtier part en artefact en cas d'échec ;
- les quatre actions de la CI sont épinglées par empreinte.

**Les fragments** (`index/fragments.py`, ADR 0011) : une fonction de la fiche
du gold, déterministe, en cinq sections au plus par fiche, découpées par
élément sous 1 200 caractères (477 jetons au plus).
- Sur le jeu : **72 296 fragments**, dont l'identifiant ne dépend pas du
  texte.
- La prudence du gold est écrite en toutes lettres : « aucun signalement »
  n'est jamais « disponible » (testé sur tout le jeu) ; une ligne sans CIP13
  vise la spécialité entière ; un début à venir est « annoncé » ; une fiche
  partielle le dit ; une valeur illisible n'est pas écrite.
- Les sources et les liens sont des métadonnées. **L'instant de l'état n'est
  pas dans le texte** : l'index le tient une fois, et `chercher` le **rend
  avec chaque résultat**. La mission 08 devra le citer avec chaque réponse.

**L'index** (palier 2) :
- Qdrant v1.19.2, épinglé par empreinte, sur `127.0.0.1:16333`, avec un
  client `httpx` à nous ;
- un vecteur nommé `dense`, un alias `pharmaflux-fragments`, un état ;
- une **recherche exacte** (7 ms par requête ; l'approchée par défaut ne
  rendait que 82 % des dix premiers) ;
- le modèle **multilingual-e5-small int8** par ONNX Runtime, avec le
  tokenizer SentencePiece d'origine. Il est retenu sur mesure contre
  potion-multilingual-128M : 17/22 contre 5/22 dans les cinq premiers ;
- les fichiers épinglés par révision et sha256 ; seul beko les télécharge ;
- deux processus, chacun sous 512 Mo ; un cache des vecteurs et un verrou
  sous `data/index`.

**Les commandes** : `index construire`, `chercher`, `etat`, `evaluer`,
`fragments`, et `modele relever | installer | verifier`.

**La mise à jour par incréments et la vérification** (palier 3) :
- `index mettre-a-jour` ne recalcule que les CIS touchés depuis l'instant de
  l'index : versions du silver, liens vers les avis, **bascules du jour**.
  Il écrit avant de retirer, pose `vise` d'abord et l'instant à la fin, et
  reprend après une coupure à n'importe quelle étape.
- `index verifier` compare l'index à sa reconstruction complète depuis le
  gold : identifiants, charges, chaque vecteur égal au cache, 100 fragments
  réencodés à un cosinus ≥ 0,99.
- Un alias que l'état ne décrit pas fait refuser la lecture.
- Le jeu publié en quatre tranches reste égal à sa reconstruction à chaque
  étape.
- `make index` construit ou met à jour (la sortie dit lequel), puis vérifie.
- La CI fait toute la chaîne avec l'encodeur de test. Elle installe ensuite
  le vrai modèle, en cache, et le passe sur un index réduit, vérifié, et
  trois recherches.
- Docs : ADR 0011, README (section « L'index », « État »), `CONTEXTE.md`,
  journal.

## Vérifications locales (commit testé : `50e7533`, le sommet qui porte les corrections de la relecture)

Redpanda, Qdrant et les fichiers du modèle présents sur le Mac.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 263 files already formatted |
| `uv run mypy src` | Success: no issues found in 67 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **601 passed** en 262 s (538 au départ de la mission) |
| `uv run pytest -q -rE -m "integration or modele"` | 17 passed ; reproduction : 2 réessais sur 30 cycles (une mesure, retirée du décompte de la session) |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/demo/prerequis.sh` | rien à signaler |
| YAML de `ci.yml` (`ruby -ryaml`) | lu sans erreur |
| `demo verifier` | conforme |
| `profil`, `questions verifier` sur `~/pharmaflux-data` | 0 bloquante ; 25 conformes, 5 non calculables, 10 sans attendu |
| `evenements` sur la copie du Mac, `diff -r` contre la sortie de `98505d3` | identique |
| `silver verifier` sur le jeu | 22/22 conformes |
| `gold qualite` ; `questions verifier --entrepot` sur le jeu | aucun bloquant ; 25 concordent |
| `index verifier` (index du Mac, construit à la clôture) | conforme, cosinus minimal 0,9954 ; 422 et 413 Mo |

## La clôture de beko (29/10, sur le Mac)

Cache des vecteurs vidé, puis `make rebatir && make demo && make silver &&
make gold && make index && make index` :
- `make demo` : 22 archives, 18 fichiers publiés, 4 écartés ;
  `verifier-bus` conforme ;
- `make silver` : 22/22 ;
- `make gold` : aucun bloquant ; 25 questions concordent.

```
make index : aucun index lisible, construction complète (index construire)
2048/72296 fragments, 29 s ; résident max 411 Mo
…
71680/72296 fragments, 1069 s ; résident max 411 Mo
index construit : 72296 fragments de 21445 fiches, 72296 encodé(s), 0 repris du cache, 1078 s ; état au 2026-10-27T00:17:12Z ; collection pharmaflux-f1-e5-small-int8-20261027T001712Z
résident maximal : encodage 411 Mo, fragments (sous-processus) 416 Mo
index au 2026-10-27T00:17:12Z, … : 72296 points, 72296 fragments attendus (reconstruction depuis le gold)
manquants 0 ; orphelins 0 ; texte ou métadonnées différents 0 ; vecteurs différents 0 ; vecteurs absents du cache 0
échantillon réencodé 100, cosinus minimal 0.9954 (au moins 0.99)
conforme
résident maximal : encodage 418 Mo, fragments (sous-processus) 416 Mo

make index : un index existe, mise à jour par incréments (index mettre-a-jour)
index à jour : rien à faire de 2026-10-27T00:17:12Z à 2026-10-27T00:17:12Z ; 72296 fragments
résident maximal : encodage 418 Mo, fragments (sous-processus) 419 Mo
… conforme
résident maximal : encodage 418 Mo, fragments (sous-processus) 418 Mo
```

**Clôture atteinte** : tous les résidents restent sous 512 Mo, et `verifier`
est conforme les deux fois. C'était le second point de mémoire demandé par
l'IeC : les 624 Mo de la première construction du palier 2 ne se sont pas
reproduits, et restent inexpliqués (ADR 0011, « Limites »).

La relecture a changé `make index` : il demande désormais `index etat
--complet`, pour reconstruire un index réduit. **La clôture n'en dépend
pas** : un index complet passe toujours par `mettre-a-jour`.

## La mémoire (Mac arm64, jeu de démo ; seuil de 512 Mo par commande, ADR 0009)

| commande | résident maximal |
|---|---|
| `index construire`, cache vide (clôture) | encodage 411 Mo ; fragments 416 Mo ; 18 min |
| `index mettre-a-jour` (rien à faire) | 418 / 419 Mo |
| `index verifier` | 418 à 424 Mo |
| `index chercher` | 446 Mo |
| `index evaluer` | 470 Mo |
| `index fragments --tout` (le gold) | 418 Mo |

Conteneurs au repos, relevés par beko : Qdrant 99,2 Mio sur 512 Mio ;
Redpanda 200,8 Mio sur 1 Gio.

## Durée de l'étape `make index` dans la CI

À compléter après la publication : les deux `make index INDEX_MODELE=test`,
puis l'étape du modèle (téléchargement à froid, puis cache).

## Écarts acceptés

**Palier 1** :
- `index fragments` sort dans l'ordre des CIS, pas trié par identifiant ;
- les liens d'un fragment découpé sont ceux de sa section ;
- les avis gardent la forme de la fiche texte, sans leur libellé long ;
- « aucun signalement » cite `CIS_CIP_Dispo_Spec.txt` sans date.

**Palier 2** :
- la recherche est exacte (décision de l'IeC) ;
- le vecteur d'un texte dépend un peu de ses voisins de lot (cosinus
  ≥ 0,997), d'où les deux comparaisons de `verifier` ;
- potion est retiré du code, ses mesures sont dans l'ADR ;
- `prerequis.sh` ne vérifiait l'image et le modèle qu'au palier 3.

**Palier 3** :
- le cache du modèle en CI est venu après le palier (`97c09fd`) ;
- le test par tranches tourne dans le job `verifier`, contre le Qdrant
  simulé ;
- `make index` choisit par `index etat`, donc un Qdrant injoignable mène à
  une construction, qui échoue à son tour en code 2.

**Relecture 1** : trois points non bloquants, corrigés.
- `construire` efface la collection que l'ancien état décrivait.
- Un index réduit se déclare : `etat --complet`, refus de `mettre-a-jour`,
  `verifier` sur ses CIS.
- `verifier` prend le verrou.
- Remarques faites : la perte du cache est dite, et le double compte est
  retiré.

**Connus et écrits dans l'ADR 0011** :
- une égalité de score entre deux découpages en jetons (un fragment sur
  72 296) ;
- les 624 Mo non reproduits.

## Propositions

- **K2** : le job `verifier` attend un courtier absent avant de sauter les
  tests d'intégration. Il passe d'environ 4 à 6 min avec les tests du jeu en
  tranches. Un saut décidé par une seule tentative courte en regagnerait une
  partie.
- **La date du dernier fichier retenu, par entité**, au silver. Elle
  daterait « aucun signalement » et les absences, qui citent aujourd'hui un
  fichier sans date.
- **La limite de la détection** (ADR 0010) : une valeur brute illisible égale
  à la forme canonique de la précédente ne produit aucun événement.
- **Pour la mission 08** :
  - citer l'instant de l'index avec chaque réponse ;
  - le score dense est serré : médiane 0,905 dans le périmètre, contre
    0,873 hors périmètre et pour les questions médicales (max 0,897). Une
    abstention ne tiendra pas sur ce seul score ; le lexical (format 2,
    vecteur creux à côté de `dense`) et des règles devront s'y ajouter ;
  - les questions les plus manquées ont leur réponse dans `identite`
    (commercialisation, statut).
- **Le PRD v0.8** dit « PR #7 » pour le run en échec : c'était le run de
  `main` sur `98505d3`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
