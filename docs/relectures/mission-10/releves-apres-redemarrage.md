# Mission 10 — relevés après le redémarrage (IeC)

**Date** : 17/11/2026 · relevés de beko vers 14:13 UTC ; journal des passages
(`derive/chaine/passages.jsonl`) lu par l'IeC, en lecture.

## Le redémarrage

- beko a redémarré le VPS-1 le 16/11 à 19:31 UTC, entre deux passages.
- Les deux conteneurs sont revenus seuls (`healthy`). Les minuteurs de la collecte et de la
  vérification sont en place.
- **Le premier passage après le redémarrage** a démarré le 16/11 à 20:17:30 UTC. Il est
  complet, en code 0 et en 25,3 s, avec l'étape `index` à 377 Mo de résident.
- Personne n'a rien relancé : aucun `start`, aucun `reset-failed`.

## Le journal des passages, du 15/11 19:17 au 17/11 13:17 UTC

- **43 passages horaires et 2 vérifications**, tous complets, en code 0. Aucun signalement,
  aucun processus tué par manque de mémoire.
- **Un passage** dure de 24,8 à 36,8 s. Son étape `index` dure de 13,1 à 20,0 s et monte
  de 377 à 432 Mo de résident ; le seuil d'alerte est de 450 Mo.
- **Le pic du groupe** est de 512 Mo à chaque passage, parce que le cache compte, comme au
  remplissage.
- **Les vérifications** ont tourné le 16/11 à 03:40 (239,8 s) et le 17/11 à 03:40 (254,1 s),
  en code 0 toutes les deux.

**Les archives arrivées depuis la mise en service** :

| passage | archives | ce qu'en dit l'état |
|---|---|---|
| 16/11 00:17 | page de téléchargement, `CIS_CIP_bdpm`, `CIS_InfoImportantes` | porteur, 61,0 s |
| 17/11 00:17 | page de téléchargement, `CIS_CIP_bdpm` | porteur, 59,0 s |
| 17/11 09:17 | `CIS_InfoImportantes`, empreinte `e3b0c44298fc…` | à nommer |
| 17/11 10:17 | `CIS_InfoImportantes`, empreinte `0ccfbf8f6b6c…` | à nommer |

- **L'archive de 09:17** a l'empreinte d'un contenu vide : `e3b0c44298fc…` est le SHA-256 de
  zéro octet. La BDPM a donc servi ce fichier vide.
- **L'archive de 10:17** a la même empreinte que celle du 16/11 : le fichier est revenu tel
  qu'il était.
- C'est le premier cas réel du garde-fou de volume (ADR 0006) en service.

**Le délai** se décompose ainsi :

| passage | attente de la fin de la collecte | passage jusqu'à la fin de l'index | dont `index` |
|---|---|---|---|
| 16/11 | 25 s | 36 s | 20,0 s |
| 17/11 | 26 s | 33 s | 18,3 s |

- La chaîne ne part qu'à la fin de la collecte entière : après `CIS_CIP_bdpm`, la collecte
  continue pendant environ 25 s.

## La mémoire (relevés de beko, 17/11 vers 14:13 UTC)

| | `docker stats` | `memory.peak` | anon | file | max | oom_kill |
|---|---|---|---|---|---|---|
| Redpanda | 224,2 MiB | 486 785 024 (464,2 Mio) | 219,7 Mio | 228,3 Mio | 0 | 0 |
| Qdrant | 86,17 MiB | 493 264 896 (470,4 Mio) | 47,2 Mio | 404,7 Mio | 0 | 0 |

- Les compteurs sont repartis de zéro au redémarrage : ces pics comptent depuis le 16/11 à
  19:31 UTC.
- **Le résident propre (`anon`) n'a pas bougé** depuis le début de l'observation :
  Redpanda 220,7 → 219,7 Mio, Qdrant 47,2 → 47,2 Mio.
- **Le pic de Redpanda passe de 245,3 à 464,2 Mio**, par le seul cache (`file` 9,9 → 228,3
  Mio). Il reste loin de son plafond de 1 Gio, avec `max` à 0. Une hypothèse à vérifier :
  la relecture de ses segments au démarrage.
- **Qdrant** monte à 470,4 Mio, dont 404,7 de cache, sous son plafond de 512. Son compteur
  `max` est à 0 : depuis le redémarrage, le noyau n'a jamais eu à lui reprendre de mémoire.
- **La somme des pics**, calculée comme au début, reste sous 2 Gio :
  464,2 + 470,4 + 512 (chaîne) + 104,3 (collecte) = 1 550,9 Mio.

## Où en est la clôture (addendum 1, « La clôture »)

- **48 heures sans intervention** : atteintes le 17/11 à 19:17 UTC, si rien ne bouge d'ici là.
- **Passages porteurs** : 2 sur 5.
  - Le lot du mardi n'était pas encore arrivé au passage de 13:17 UTC. Les deux derniers
    lots sont arrivés le 03/11 vers 15 h et le 10/11 vers 16 h UTC.
  - Si les nuits continuent de porter, le cinquième passage porteur viendrait le 19/11 vers
    00:17 UTC.
- **Les vérifications** sont conformes chaque nuit. Celle qui clôt est la première après le
  cinquième passage porteur.
- **La fraîcheur** : 61,0 et 59,0 s, pour une cible de 60 s.

## Ce que le codeur en fait, à sa reprise

1. Il reporte ces relevés dans `observation.md`, à « Après le redémarrage ».
2. Il nomme la nature des quatre archives (`chaine etat --format json`), en particulier
   celle de 09:17, servie vide, et ce qu'elle a donné à 10:17.
3. Il relève le résident des fragments à chaque passage porteur, en premier au lot du mardi,
   et il explique le passage de 404 à 434 Mo.
4. Pour la fraîcheur, il dit ce qui ferait tenir 60 s : l'attente de la fin de la collecte,
   ou l'étape `index`.
5. Il commite ce fichier tel quel.
