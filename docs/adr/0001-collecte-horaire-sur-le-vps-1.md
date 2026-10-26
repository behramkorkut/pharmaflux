# ADR-0001 — Collecter toutes les heures sur le VPS-1, sans requête conditionnelle

**Statut :** accepté (décision prise à la mission 00, consignée ici) · **Date :** 2026-10-26 · **Mission :** 01
**Remplace / remplacé par :** —

## Contexte

La BDPM publie onze fichiers texte sans historique : un jour sans collecte
est perdu pour toujours. Mesures de la mission 00 (24/10/2026,
`docs/rapports/mission-00/points-a-trancher.md`) : le serveur n'envoie **ni
`Last-Modified`, ni `ETag`, ni `Content-Length`** sur les fichiers, donc
aucune requête conditionnelle (`If-None-Match`, `If-Modified-Since`) n'est
possible ; un passage complet transfère 28,7 Mo bruts (3,7 Mo compressés)
en treize requêtes, une pause de 2 s entre deux. La page de téléchargement
affiche une date par fichier, mais rien ne dit à quelle heure un fichier
change. Le Mac de beko dort ; beko dispose d'un VPS-1 qui héberge aussi,
jusqu'à mi-novembre 2026, une pré-production d'Alamel. Les VPS d'Alamel
eux-mêmes sont interdits.

## Décision

La collecte tourne **sur le VPS-1 de beko, toutes les heures à `:17`**,
en série, sous un compte dédié sans droits, dans une unité systemd durcie
(score d'exposition mesuré à 1,3 le 26/10/2026). Chaque passage télécharge
tout ; la décision « nouveau / inchangé » se prend localement sur une
empreinte de comparaison par entrée, et seul un contenu nouveau est
archivé. Le manifeste, en ajout seul, consigne chaque tentative. L'archive
principale est sur le VPS ; une **copie** est rapatriée chaque semaine sur
le Mac (`rsync` en tirage, jamais `--delete`). La fraîcheur n'est pas
promise, elle est **mesurée** : pour chaque fichier, l'écart entre la date
affichée par la page (`date_source_affichee`, au jour près, heure de Paris)
et l'horodatage UTC de l'archive qui l'a captée.

## Conséquences

- Un changement est vu au plus tard une heure après sa mise en ligne (le
  premier, `CIS_CIP_bdpm.txt` daté du 24/10, a été capté à 23:17Z, quatre
  heures après l'installation). Le coût est de 264 requêtes et 89 Mo
  compressés par jour, pour un service public : `User-Agent` identifiant
  le projet, téléchargements en série, aucun parallélisme.
- Entre deux rapatriements, jusqu'à une semaine d'archive n'existe qu'en
  un exemplaire. `pharmaflux etat` sur la copie dit où en est le
  rapatriement ; c'est le point à surveiller.
- Le VPS est partagé jusqu'à mi-novembre 2026 : l'unité ne voit que ses
  trois chemins et plafonne mémoire et CPU. Rien de la collecte ne touche
  la pré-production ; rien ne change à la décision quand elle partira.
- **Signal de révision** : la BDPM se met à envoyer `ETag` ou
  `Last-Modified` (passer aux requêtes conditionnelles et resserrer
  l'intervalle), ou publie un flux de mises à jour ; ou le VPS-1 disparaît.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| Collecte sur le Mac (`launchd`) | la machine dort et se déplace : des trous dans l'archive, et l'archive n'a pas de seconde chance |
| Une fois par jour | la BDPM publie en journée sans heure fixe ; un changement intrajournalier serait daté du lendemain ; le coût horaire est faible |
| Requêtes conditionnelles | impossibles : aucun validateur HTTP envoyé par le serveur |
| Plus souvent qu'une heure | sans validateur, chaque passage coûte 3,7 Mo ; rien n'indique des mises à jour infrajournalières fréquentes (une version distincte par fichier en 27 h au 25/10) |
| VPS d'Alamel | interdits : ils appartiennent au client |

## Références

PRD v0.2 §6.1, §7.2, §9, §10.1 (point 6), §10.2 (points 2 et 4) · ordre de
mission 00 (addendum 2) et `docs/rapports/mission-00/pr.md` ·
`infra/planification/README.md` · `docs/relectures/mission-01/controle-palier-1.md`
(mesure du VPS).
