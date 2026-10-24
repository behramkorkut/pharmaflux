# Journal du projet

Une entrée par étape marquante, en fin de fichier. Les chiffres cités sont
mesurés ; la commande ou le rapport qui les produit est indiqué.

## 2026-10-23 — Cadrage

PRD v0.1 rédigé (`01_Specifications/`). Deux axes : transformer des
publications d'état en flux d'événements rejouable ; une IA gouvernée qui
cite et s'abstient. Lot 0 découpé en deux missions : archivage d'abord
(mission 00), profilage ensuite (mission 01).

## 2026-10-24 — Mission 00, §0 : les sources telles qu'elles sont

Treize requêtes HTTP, une par URL (`docs/rapports/mission-00/points-a-trancher.md`) :

- un passage complet BDPM = 11 fichiers, 28,7 Mo bruts, 3,7 Mo gzip ; si
  tout changeait chaque jour, 1,3 Go par an compressés ;
- aucun validateur HTTP (`Last-Modified`, `ETag`, `Content-Length`) sur
  les téléchargements : pas de requête conditionnelle possible ;
- la page de téléchargement affiche une date et une taille par fichier,
  dans le même élément HTML que le lien ;
- `CIS_InfoImportantes.txt` est généré à la demande, non trié ; les
  métadonnées Open Medic de data.gouv portent des dates de robot.

Tranché (addendum 2) : collecte horaire à `:17` sur le VPS de beko
(systemd), copie hebdomadaire sur le Mac ; empreinte de comparaison par
entrée du catalogue ; métadonnées Open Medic une fois par jour.

## 2026-10-24 — Mission 00, palier 1 : socle

`pyproject.toml` (uv, httpx, typer, ruff, mypy strict, pytest), squelette
`src/pharmaflux/`, CLI déclarée (`collecte`, `etat`, `--version`), CI en
un job, `.gitignore`, README, `docs/CONTEXTE.md`, gabarit d'ADR. Le
collecteur arrive au palier 2.

## 2026-10-24 — Mission 00, palier 2 : collecteur

Catalogue déclaratif (13 entrées), téléchargement httpx (60 s, trois
essais, `User-Agent` du projet), archive bronze immuable (temporaire puis
`os.link`, jamais de réécriture), manifeste JSONL en ajout seul, `collecte`
et `etat` réels. 45 tests sans réseau sur des extraits réels
(`tests/fixtures/`). Seconde requête autorisée sur
`CIS_InfoImportantes.txt` : fichier identique à l'octet près 76 min plus
tard, l'ordre des lignes n'a pas bougé. Découverte : la page offre un
douzième lien, la documentation PDF du format (v5).

## 2026-10-24 — Mission 00, correctifs du contrôle du palier 2

C1 : une ligne qui a écrit une archive laisse toujours son empreinte
connue, quel que soit son statut ; `analyse_impossible` compare sur les
octets ; `lien_absent` s'ajoute à l'erreur existante (`HTTP 404 ;
lien_absent`) au lieu de l'écraser. Sans cela, un lien disparu ou une page
illisible aurait réarchivé le même contenu 24 fois par jour. C2 : une
dernière ligne tronquée du manifeste (coupure pendant l'écriture) est
ignorée avec un avertissement, `ajouter` repart sur une ligne propre ; une
ligne illisible au milieu reste une erreur franche. Quatorzième entrée du
catalogue : la documentation PDF du format BDPM, quotidienne, empreinte
octets (une requête réelle pour la fixture, 4 Ko conservés).
