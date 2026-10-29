# L'index : télécharger le modèle et l'image Qdrant (mission 07)

Deux téléchargements, que **beko seul** lance (`CLAUDE.md`, addendum 1 K7).
Les agents écrivent la procédure et vérifient sans réseau ; ils ne la lancent
pas. Les deux suivent la règle des deux semaines de l'ADR 0009 : une version
publiée depuis moins de quatorze jours n'entre pas.

## 1. Les fichiers des deux modèles candidats

Deux candidats, mesurés au début du palier 2 avant d'en retenir un
(addendum 1 C1) :

| nom | dépôt Hugging Face | fichiers | licence |
|---|---|---|---|
| `e5-small-int8` | `Xenova/multilingual-e5-small` (export ONNX quantifié de `intfloat/multilingual-e5-small`) | `onnx/model_quantized.onnx`, `tokenizer.json`, `config.json` | MIT |
| `potion-multilingual-128m` | `minishlab/potion-multilingual-128M` (Model2Vec, statique) | `model.safetensors`, `tokenizer.json`, `config.json` | MIT |

L'épinglage de chacun est un TOML du dépôt,
`src/pharmaflux/index/modeles/<nom>.toml`. Aujourd'hui, il ne contient que
le dépôt et la liste des fichiers : ni révision, ni empreinte.

Les fichiers vont sous `$PHARMAFLUX_MODELES`, par défaut
`~/pharmaflux-modeles`, dans `<nom>/<révision>/`. Ils restent hors de git,
et hors de `data/`, que `make rebatir` vide.

**Étape 1, relever** (télécharge, environ 120 Mo pour e5 et 500 Mo pour
potion) :

```bash
uv run pharmaflux index modele relever e5-small-int8
```

```bash
uv run pharmaflux index modele relever potion-multilingual-128m
```

Chaque commande :
- lit la liste des commits du dépôt (`/api/models/<dépôt>/commits/main`) ;
- choisit le plus récent qui a au moins quatorze jours ;
- télécharge chaque fichier à cette révision, à sa place sous
  `$PHARMAFLUX_MODELES` ;
- affiche **le TOML complet**, avec la révision, sa date et le sha256 de
  chaque fichier.

Si un fichier manque au dépôt (HTTP 404), la commande s'arrête avec le code 1
et le dit. Le TOML se corrige alors avant de relancer.

**Étape 2, transmettre** les deux TOML affichés au codeur. Il les recopie
dans le dépôt au palier 2, tels quels.

**Étape 3, vérifier** (sans réseau, une fois les TOML recopiés) :

```bash
uv run pharmaflux index modele verifier e5-small-int8
```

`installer` télécharge de nouveau, à la révision épinglée, seulement un
fichier absent ou altéré. C'est aussi ce que fera la CI, avec un cache.

## 2. L'image Qdrant, épinglée par empreinte

Le service `qdrant` entre dans `docker-compose.yml` au palier 2, avec
`image: qdrant/qdrant:vX.Y.Z@sha256:<empreinte>`. L'empreinte est celle de
l'**index multi-architecture**, valable sur le Mac (arm64) comme sur la CI
(amd64).

**Étape 1, choisir la version.** Prendre la dernière version `vX.Y.Z`
publiée depuis au moins quatorze jours. La date de publication fait foi sur
la page des versions, pas la date de mise à jour de Docker Hub, qui bouge
quand une image est repoussée :

```bash
gh release list -R qdrant/qdrant --limit 15
```

Écarter les préversions (`-rc`, `-beta`) et les versions de moins de
quatorze jours.

**Étape 2, télécharger et relever l'empreinte** :

```bash
docker pull qdrant/qdrant:vX.Y.Z
```

```bash
docker buildx imagetools inspect qdrant/qdrant:vX.Y.Z
```

La ligne `Digest:` de la seconde commande est l'empreinte de l'index
multi-architecture. Elle doit lister `linux/amd64` et `linux/arm64` sous
`Manifests:`.

**Étape 3, transmettre** au codeur la version, la date de publication et
l'empreinte (`sha256:…`). Il les écrit dans le compose au palier 2, puis
`make up` démarre Qdrant avec `--pull never`, sur l'image déjà présente.
