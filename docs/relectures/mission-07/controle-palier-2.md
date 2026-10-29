# Mission 07 — contrôle du palier 2 (IeC)

**Commits contrôlés** : `96c896c` (le palier) et `22a2d6e` (la mémoire dans
le bilan de `construire`, et la piste des 624 Mo), fils de `62bbbb9`, qui
porte le contrôle du palier 1 tel quel. Ils sont contrôlés contre l'ordre,
l'addendum 1 et les décisions prises par messages pendant le palier.
**Verdict : conforme, passe au palier 3.**

## Revérifié par l'IeC

Dans ton dossier, Redpanda, Qdrant et les fichiers du modèle présents :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | verts |
| `uv run mypy src` | vert, 66 fichiers |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` sur `96c896c` | **585 passed** en 3 min 13 s ; reproduction : 0 réessai sur 30 cycles |
| `uv run pytest -q tests/test_index.py` sur `22a2d6e` | 11 passed |

Mon passage complet a tourné pendant que tu commitais `22a2d6e`. Ce commit
ne touche qu'un test et ton rapport : j'ai relancé ce test sur le sommet.

Relu :

- **Le choix du modèle suit la règle de l'addendum.**
  - potion est écarté sur la mémoire (1 099 Mo), puis sur la qualité (5/22).
  - e5 est retenu à 415 Mo sur une **construction complète**, 446 Mo pour
    `chercher` et 470 Mo pour `evaluer`, en 18 min, et 17/22 dans les cinq
    premiers.

  La cause des premiers dépassements est établie et écrite : les
  vocabulaires de `tokenizers`, la session ONNX Runtime et les formes de lot
  libres. Le remède est mesuré : le fichier SentencePiece amont et quatre
  formes de lot fixes. **Le seuil n'a pas bougé.**
- **Les jetons** sont identiques à `tokenizer.json` sur 72 295 fragments
  sur 72 296 et sur les 40 questions. Le test garde 145 fragments et les 40
  questions.
- **La borne de découpe** est recalée à 1 200 caractères (477 jetons au
  plus) **avant** que le format 1 soit figé, et les nombres sont remesurés.
- **La construction** :
  - une collection neuve, puis la bascule de l'alias, puis l'état, puis
    l'ancienne effacée ;
  - le contrôle du nombre de points avant la bascule ;
  - le nom « -bis », qui n'efface jamais la collection lue ;
  - l'espace des tests d'intégration, qui ne touche jamais l'index du Mac.
- **Les épinglages** :
  - les deux TOML, `sentencepiece.bpe.model` compris ;
  - Qdrant `v1.19.2@sha256:b7b0444c…` ;
  - les trois actions par SHA ;
  - les dépendances au 15/10, aucun paquet existant déplacé, `tokenizers`
    en développement seulement.
- **Les corrections du contrôle 1** sont faites.

## Écarts du rapport

1. **La recherche exacte** : décision de l'IeC pendant le palier. Le tableau
   HNSW contre exacte va dans l'ADR 0011.
2. **Le vecteur dépend un peu de ses voisins de lot** (quantification
   dynamique, cosinus ≥ 0,997) : accepté. Voir la question 2.
3. **potion est retiré du code**, et ses mesures vont dans l'ADR : accepté.
   Ses fichiers dans `~/pharmaflux-modeles` sont à beko.
4. **`prerequis.sh`** ne vérifie l'image et le modèle qu'au palier 3 :
   accepté, c'est la décision I.

## Tes questions

1. **Les 624 Mo** : la piste de `tokenizers` est écartée, avec les dates des
   fichiers et le code de cette version. La question reste ouverte, et c'est
   dit honnêtement. Chaque construction affiche maintenant le résident de
   ses deux processus. Le `make index` de beko à la clôture donne le second
   point. Ça me suffit, à une condition : si ce second point dépasse
   512 Mo, la clôture n'est pas atteinte, et on en reparle.
2. **`index verifier` et les vecteurs du vrai modèle** : les deux
   comparaisons, pas l'une ou l'autre.
   - **L'intégrité** : le vecteur de chaque point est **égal**, à l'octet
     près, à l'entrée du cache pour (modèle, révision, sha256 de son texte).
     C'est ce qui a été écrit, donc ce doit être ce qui est lu.
   - **Le modèle** : sur l'échantillon fixe de 100 fragments, le
     réencodage donne un cosinus **≥ 0,99** avec le vecteur de l'index.
     Cela détecte un mauvais modèle, une mauvaise révision ou un
     tokenizer cassé, ce que l'égalité contre le cache ne voit pas.

   Avec l'encodeur de test, l'égalité stricte de tous les vecteurs. L'ADR
   0011 explique pourquoi le vrai modèle ne permet pas l'égalité.

## Pour le palier 3

- **L'alias et l'état peuvent se contredire.** Une coupure entre
  `basculer_alias` et `ecrire_etat` laisse l'alias sur la nouvelle
  collection, et l'état sur l'ancienne, avec son instant. L'état nomme sa
  collection, donc l'écart se voit :
  - `index verifier` et `index etat` le signalent : refus, code 2 ;
  - `chercher` refuse, plutôt que d'annoncer un instant qui n'est pas celui
    des fragments qu'il rend ;
  - un test couvre cette coupure, comme les autres coupures de la mise à
    jour.

  La façon d'en sortir (`index construire` refait, ou l'état réécrit) est
  dans le message.
- `index mettre-a-jour` affiche le résident de ses deux processus, comme
  `construire`.
- Le reste suit l'ordre et l'addendum :
  - le test par tranches ;
  - les bascules du jour ;
  - `make index` qui dit ce qu'il a lancé ;
  - `prerequis.sh` ;
  - l'étape de CI avec l'encodeur de test sur tout le jeu, et le vrai
    modèle sur un sous-ensemble, avec un cache ;
  - l'ADR 0011 ;
  - la section « L'index » et la section « État » du README ;
  - la séquence de beko, deux `make index` de suite.
