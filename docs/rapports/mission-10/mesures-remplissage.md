# Mission 10 — les mesures du premier remplissage sur le VPS-1

## Synthèse

**Le premier remplissage est complet.** Passage `20261114T232834Z` :
- `issue` `complet`, code 0, 11 étapes sur 11, aucune non lancée ;
- `morts_par_memoire` 0 ;
- 13 885,1 s (3 h 51 min), de 23:28:34 à 03:19:59 UTC.

L'index est **conforme** à la reconstruction depuis le gold : 75 605 points, 21 463 fiches,
aucun manquant ni orphelin.

**Deux points pour l'IeC** :
1. Le groupe du remplissage a touché son plafond de 512 Mio pendant l'index, sans aucun
   processus tué. Le résident des étapes reste sous 450 Mo (404 Mo au plus).
2. Qdrant a touché son plafond de 512 Mio, lui aussi, par le cache de fichiers et sans
   processus tué.

L'index prend 3 h 41 min, soit 61 % du délai de 6 h de l'unité.

**Les collectes horaires** ont toutes tourné pendant le remplissage : 14 passages dans la nuit,
sans erreur.

**Ce que je n'ai pas pu lire** : le journal système de la collecte (il faut `sudo`) et les
compteurs systemd de l'unité après sa fin. Le groupe est détruit à l'arrêt, donc `MemoryPeak`
et `CPUUsageNSec` valent `[not set]`.

## Ce qui a tourné

| | |
|---|---|
| code déposé | `eecc9f3` (`VERSION` = `eecc9f3478a07e86fe60af8b01f9a3bc5edecf9a`), sous `code/courante` |
| `git diff --stat eecc9f3 e12c14d -- src/` | vide : le code de `e12c14d` est celui qui a tourné |
| unités installées | celles de `e12c14d`. sha256 vérifiés par l'IeC : remplissage `f9b05d8e…`, collecte `3a0d0834…` |
| `docker-compose.yml`, `infra/vps/vps.yml`, unité des conteneurs | inchangés depuis `13168f5` |
| CI | verte, run `43640515099` sur `eecc9f3`. Le run de la fusion `5febda7` est demandé à l'IeC |
| modèle | `e5-small-int8`, révision `761b726`, 4 empreintes conformes |

**La preuve de polkit** : le premier `systemctl start --no-block
pharmaflux-remplissage.service`, depuis mon compte, a rendu 0. Ce n'est pas le `reset-failed`
d'avant : il a répondu « Unit … not loaded », ce qui ne prouve rien, puisque l'unité est
statique et n'était pas chargée.

**Le lien `courante` a été posé sans le verrou** (voie a de l'IeC), parce que le verrou
n'existait pas encore. Il existe maintenant (`derive/chaine/verrou`). La bascule sous `flock`
vient au palier 2.

## Les étapes

Le pic du groupe est cumulatif : `memory.peak` du groupe de l'unité, cache compris, lu à la fin
de chaque étape. Les Mo de la chaîne sont des Mio (2²⁰ octets, `eecc9f3`).

| # | étape | durée | résident | pic du groupe | remarque |
|---|---|---|---|---|---|
| 1 | `modele` | 1,1 s | 54 Mo | 136 Mo | 4 fichiers, sha256 vérifiés |
| 2 | `pages-has` | 19,0 s | 54 Mo | 136 Mo | p_3892357 : rejetée (`nom_incoherent`) en v1, extraite en v2 |
| 3 | `evenements` | 70,1 s | 115 Mo | 458 Mo | smr `20261110T161712Z` : perte de 3,4 %, confirmée par un passage inchangé |
| 4 | `schemas` | 1,0 s | 58 Mo | 458 Mo | un POST coupé sans réponse (`RemoteProtocolError`), réussi au 2ᵉ essai |
| 5 | `publier` | 234,4 s | 69 Mo | 458 Mo | environ 4 fois les 59,8 s du Mac |
| 6 | `verifier-bus` | 31,2 s | 185 Mo | 512 Mo | |
| 7 | `silver` | 49,4 s | 384 Mo | 512 Mo | 212 546 messages, 0 doublon |
| 8 | `silver-verifier` | 98,5 s | 292 Mo | 512 Mo | 73/73 archives conformes |
| 9 | `index` | 13 263,7 s | 386 Mo | 512 Mo | encodage 356 Mo, fragments (sous-processus) 404 Mo |
| 10 | `index-verifier` | 115,5 s | 379 Mo | 512 Mo | conforme ; échantillon de 100, cosinus minimal 0,9956 |
| 11 | `index-etat` | 0,9 s | 64 Mo | 512 Mo | |

`partage_groupe_mo` vaut 0.

**L'index.**
- Collection `pharmaflux-f4-e5-small-int8-20261113T001710Z`, sous l'alias
  `pharmaflux-fragments`, au format 4.
- Instant : `2026-11-13T00:17:10Z`. Aucune mise à jour en suspens.
- 75 605 fragments :

  | identite | presentations | avis | avis_has | disponibilite | informations |
  |---|---|---|---|---|---|
  | 21 602 | 14 744 | 9 031 | 3 406 | 21 463 | 5 359 |

- Pages HAS :
  - manifeste lu jusqu'à la ligne 724 (`29ae40733a42…`) ;
  - 722 pages archivées, dont 485 rattachées à une fiche ;
  - 484 extraites, 1 rejet (`dossier_incoherent`) ;
  - 3 contrôles de dossier impossibles ;
  - 81 pages sans fiche du référentiel, hors de l'index (ADR 0013).

**Pendant l'encodage de l'index**, mon relevé sur le groupe de l'unité :
- `memory.peak` : 537 477 120 octets (512,6 Mio) ;
- `anon` 291 Mio, `file` 172 Mio ;
- `memory.events` : `max` 3 654, `oom_kill` 0 ;
- environ un cœur occupé.

Le plafond est donc atteint, et le noyau reprend le cache de fichiers au lieu de tuer un
processus.

**L'avertissement d'onnxruntime.** `cpuinfo` ne lit pas `/proc/cpuinfo`, que
`ProcSubset=pid` cache. onnxruntime annonce alors « May cause CPU EP performance
degradation ». Je ne sais pas encore si cela pèse sur les 3 h 41 min de l'index : je propose de
le mesurer au palier 2, sans rien changer d'ici là.

## Les conteneurs (relevés de beko)

La mesure est celle du 14/11 : `docker stats`, soit `memory.current` − `inactive_file`.

| moment | Redpanda (plafond 1 Gio) | Qdrant (plafond 512 Mio) |
|---|---|---|
| au repos, avant le remplissage (14/11, vers 23:25) | 149,7 Mio | 15,16 Mio (aucune collection) |
| pendant `evenements` (vers 23:30) | 151,6 Mio | 17,0 à 17,2 Mio |
| pendant l'encodage de l'index (15/11, vers 00:00) | 222,5 Mio | 18,05 Mio (rien d'écrit encore) |
| le 15/11 au matin, conteneurs `Up 13 hours (healthy)` | 223,4 Mio | 156,1 Mio |

**`memory.peak` des deux scopes**, relevé par beko le 15/11 au matin. C'est une borne haute,
cache compris, sur toute la vie des conteneurs, et non une lecture instantanée.

| scope | `memory.peak` | `anon` | `file` | `max` | `oom_kill` |
|---|---|---|---|---|---|
| Redpanda | 253 415 424 (241,7 Mio) | 219,5 Mio | 7,2 Mio | 0 | 0 |
| Qdrant | 539 193 344 (514,2 Mio) | 47,0 Mio | 305,4 Mio | 5 981 | 0 |

`anon` et `file` sont lus au matin.

**Qdrant a touché son plafond** pendant l'écriture des 75 605 points :
- 5 981 événements `max` : le noyau a repris de la mémoire au plafond ;
- aucun processus tué ;
- au matin, le résident est de 156 Mio, dont 47 Mio anonymes, et le cache de fichiers est de
  305 Mio.

La pression vient donc du cache des segments, pas de la mémoire propre de Qdrant. Les deux pics
(Qdrant, et le groupe du remplissage à 512,6 Mio) dépassent de 2 Mio le plafond nominal. C'est
la marge de facturation du noyau, et non un dépassement réel.

## Les collectes pendant la nuit

Le relevé vient du manifeste (`collecte.jsonl`, 6 322 lignes au matin), par passage :
- **14 passages, de 23:17 le 14/11 à 11:17 le 15/11** : 12 fichiers `inchange` à chacun, aucune
  erreur. Ce compte inclut le passage manuel de 23:23:56, qui prouvait le correctif sous
  l'unité ;
- **à 00:17** : en plus, 2 `nouveau`. Ce sont les sources quotidiennes.

Le verrou de la chaîne et la collecte ne se sont pas gênés.

## L'incident de la collecte du 14/11 (rappel, pour le journal)

- **Les passages perdus** : 21:02 (lancé à la main), 21:17 et 22:17 UTC.
- **La cause** : `MemoryDenyWriteExecute`, avec le `python3.12` d'uv, qui n'a pas d'en-tête
  `GNU_STACK`. glibc rend alors exécutable la pile de chaque fil, et le noyau refuse (EACCES).
  L'import de numpy (OpenBLAS) en mourait.
- **Le correctif** :
  - retour à `67d9d3c`, avec un passage à 22:48 ;
  - correctif `e12c14d` (contrôle `a1b7e09`), et collecte sur `main` (`a38436b`) ;
  - passage manuel `20261114T232356Z` : 12 fichiers inchangés, 0 erreur, pic de 99,2 Mo avec
    numpy chargé.
- **Le bilan** : aucune version perdue.

## La copie des pages HAS (étape 3)

- 724 fichiers.
- `has-pages.jsonl` a la même empreinte des deux côtés (`29ae4073…`).
- `rsync -rnci` ne liste aucun fichier.
- Droits `pharmaflux:pharmaflux` 0750/0640, sans écart.
- `collecte.jsonl` est le même avant et après (6 152 lignes, `ed80ba17…`).

## Les refus du garde-fou pendant ces étapes

- Une variable (`$V`) en tête d'une commande passée à `ssh` : j'ai relancé avec les chemins en
  entier.
- Une écriture dans le scratchpad, hors du dossier du codeur : mes notes sont allées dans
  `data/m10/`, qui est ignoré de git.
- **Un trou, signalé puis fermé par l'IeC sur `main`** : un programme `python -c` sur plusieurs
  lignes, dans une boucle `ssh` entre guillemets, passait. Je n'emploie plus cette forme. Un
  diagnostic passe désormais par un script déposé avec le code.

## Pour le palier 2

- `infra/vps/README.md` et `infra/planification/README.md` §5 : les deux passages qui citent
  `MemoryDenyWriteExecute` comme premier suspect sont à remettre à jour.
- La bascule de version sous `flock` (point 2 du contrôle du palier 1).
- Mesurer l'effet de `ProcSubset=pid` sur la durée de l'encodage (avertissement `cpuinfo`).
- Les plafonds touchés, par Qdrant et par le groupe du remplissage : à décider par l'IeC, rien
  n'est changé ici.
