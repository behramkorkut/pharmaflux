# ADR-0002 — Contrats de schéma en TOML, neuf types, anomalies constatées jamais corrigées

**Statut :** accepté · **Date :** 2026-10-26 · **Mission :** 01
**Remplace / remplacé par :** — · complété par l'ADR 0005 (`canonique`, `milliers`)

## Contexte

Les onze fichiers TSV de la BDPM n'ont pas d'en-tête, et leur forme
varie : neuf en Windows-1252 avec CRLF, deux en UTF-8 avec LF, un sans
retour final, un avec des lignes vides au milieu, trois formats de date,
des prix à virgule des milliers, neuf graphies pour un taux
(`docs/donnees/README.md`). Le Lot 1 a besoin de savoir, fichier par
fichier et de façon versionnée, ce qu'il doit recevoir, et le Lot 5 d'un
signal quand la forme change (PRD §9, risque n° 1). Trois fichiers n'ont
pas de clé unique par construction. Contrainte : aucune nouvelle
dépendance.

## Décision

Un **contrat TOML par fichier source**, dans le paquet
(`src/pharmaflux/contrats/bdpm/<identifiant>.toml`, `version = "v0"` dans
le fichier), lu par `tomllib` avec un chargeur **strict** : toute clé
inconnue ou sans objet pour le type est refusée. Un contrat déclare la
source (section du PDF de documentation et son sha256, archive de
référence et son sha256), le format (encodage, fin de ligne, séparateur,
retour final, lignes vides), les colonnes dans l'ordre avec un type parmi
**neuf** (`texte`, `entier`, `decimal`, `date` paramétré par son format,
`booleen`, `enumeration`, `code`, `url`, `liste`), la clé avec `unique =
true | false` et une `raison` obligatoire si elle n'est pas unique, et les
`liens` vers d'autres fichiers. La vérification rend des **anomalies**
(fichier, ligne, colonne, règle, valeur brute), **jamais une correction**.
Quatre règles sont bloquantes, parce qu'elles empêchent de lire le fichier
comme attendu : encodage, fin de ligne, nombre de colonnes, clé déclarée
unique qui ne l'est pas. Tout le reste porte sur une valeur et ne bloque
pas, `valeur_inconnue` comprise, que le profil met néanmoins en tête : un
statut nouveau est le premier signe d'un changement de format. Les
anomalies connues et systématiques (titulaire précédé d'une espace sur
toutes les lignes, 497 prix `1,466,29`) sont **signalées à chaque
profil**, avec leur compte et cinq exemples : aucune tolérance n'est écrite
dans un contrat. Les énumérations listent les graphies telles qu'elles sont
dans le fichier ; la normalisation est au Lot 1. Les `liens` servent à
mesurer des taux de correspondance, jamais à produire une anomalie.

**Bornes des dates.** Les plages (`plage_min`, `plage_max`) ne servent qu'à
signaler une date manifestement fausse ; leurs bornes hautes sont fixes
(2030, 2035 pour la fin des informations importantes) et **se relèvent par
une nouvelle version du contrat**, avant d'être atteintes.

## Conséquences

- Le Lot 1 lit chaque fichier avec son contrat et sait quoi convertir ; le
  Lot 5 fait d'une anomalie bloquante une alerte de changement de format
  (`pharmaflux profil` sort avec le code 1).
- Un changement de forme de la BDPM se traduit par une **nouvelle version**
  du contrat, pas par une retouche silencieuse : `v0` est figée sur
  l'archive du 24/10/2026.
- Le coût : un contrat verbeux (douze colonnes font soixante lignes), et un
  compte élevé d'anomalies non bloquantes à chaque profil (17 016 espaces
  dans `CIS_bdpm.txt`). C'est voulu : rien n'est caché, et le Lot 1 pourra
  proposer une détection d'écart au compte attendu.
- Une ligne faite seulement de blancs (espaces, tabulations, un `\r`
  isolé) est une **ligne vide**, pas une ligne dont toutes les valeurs
  manquent : elle est signalée comme telle (`ligne_vide`, ou
  `nombre_colonnes` quand le contrat interdit les lignes vides) et n'entre
  pas dans les lignes lues. Voulu : une telle ligne ne porte aucune clé et
  ne dit rien d'une colonne (précisé après la relecture 1).
- À surveiller : les fichiers d'autres sources (CSV Open Medic au Lot 4,
  JSON de data.gouv) demanderont peut-être d'autres types (décimal à point,
  entier avec séparateur) ; ce sera une extension du jeu, par ADR.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| JSON Schema, pydantic, pandera | une dépendance de plus, pour des fichiers sans en-tête où le vrai travail est de nommer et typer les colonnes, pas de valider du JSON |
| YAML | pas dans la bibliothèque standard ; TOML suffit et `tomllib` est fourni |
| Contrats en Python (dataclasses) | moins lisibles pour un non-développeur, pas versionnables comme une donnée, pas embarquables tels quels dans une roue |
| Trois types de date | un seul type paramétré : les trois formats coexistent dans la base, le Lot 1 n'aura qu'une conversion à écrire |
| Tolérances dans les contrats (`espaces_toleres`) | masquer une anomalie connue, c'est ne plus voir le jour où elle change ; on constate |
| Compte attendu par anomalie connue (`attendu = 497`) | utile, mais c'est déjà de la détection de changement : Lot 1 |

## Références

PRD v0.2 §6.2, §9 · ordre de mission 01 (§0 B, C, D ; addendum 1) ·
`docs/rapports/mission-01/points-a-trancher.md` et `palier-2.md` ·
`docs/donnees/README.md`.
