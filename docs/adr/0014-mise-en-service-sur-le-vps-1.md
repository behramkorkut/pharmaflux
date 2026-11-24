# ADR-0014 — Mettre la chaîne en service sur le VPS-1, au fil de la collecte

**Statut :** accepté (mission 10) · **Date :** 2026-11-19 · **Mission :** 10
**Remplace / remplacé par :** — · complète l'ADR 0001 (la collecte horaire)

## Contexte

Jusqu'à la mission 09, le VPS-1 ne faisait que collecter (ADR 0001). Les événements, le bus,
le silver et l'index ne tournaient que sur le Mac, à la main. Aucun changement de la BDPM
n'arrivait donc tout seul jusqu'à l'index, et beko ne veut plus de processus Pharmaflux sur son
Mac.

Les contraintes de départ :
- **le VPS-1**, relevé le 14/11 : 2 cœurs, 3,8 Go de mémoire, 28 Go de disque libres ;
- **le partage avec Alamel** : sa pré-production y reste installée, et elle doit pouvoir
  redémarrer à côté. Pharmaflux tient donc dans 2 Go résidents, conteneurs compris ;
- **aucun port entrant, aucun secret, aucun compte de Pharmaflux dans le groupe `docker`.**

Ce qui a été mesuré sur le VPS (`docs/rapports/mission-10/`) :
- **le premier remplissage** (14-15/11) : 3 h 51 min, dont 3 h 41 min pour encoder 75 605
  fragments à 5,7 fragments/s ;
- **l'observation**, à partir du 15/11 : 99 passages horaires et 6 vérifications, tous complets,
  sans processus tué.

## Décision

La chaîne tourne **sur le VPS-1, lancée par chaque passage de la collecte**, une commande à la
fois, sous un compte sans droits, dans des unités systemd durcies. L'archive reste la seule
source ; tout le reste est dérivé et se rebâtit.

**La topologie.**
- **Les conteneurs.** Redpanda et Qdrant tournent dans le projet compose `pharmaflux`, avec
  `docker-compose.yml` et un second fichier, `infra/vps/vps.yml`. Ils écoutent sur `127.0.0.1`
  et sont plafonnés à 1 Go et 512 Mo, sans échange. Ils démarrent par une unité système,
  `pharmaflux-conteneurs.service`, et les fichiers compose appartiennent à root.
- **Les comptes.** La collecte reste sous `pharmaflux`. La chaîne tourne sous
  `pharmaflux-chaine`, qui lit l'archive et écrit `/srv/pharmaflux/derive`. Un filtre `nft` lui
  ferme Internet et les ports d'Alamel.
- **Le code.** Une version par dossier, `/srv/pharmaflux/code/versions/<commit>/`, avec son
  `.venv` et son `VERSION`. La version en service est le lien `courante`, basculé de façon
  atomique sous le verrou de la chaîne. Chaque étape lance l'interprète de sa version.

**L'enchaînement** (`pharmaflux chaine …`).
- **`passer`, le passage horaire**, est lancé par `OnSuccess=` et `OnFailure=` de la collecte,
  par un complément qui ne change rien d'autre. Il enchaîne `evenements`, `schemas`, `publier`,
  `silver consommer` et `index mettre-a-jour`.
- **Le verrou.** Un `flock` : une seule commande à la fois. Quand il est tenu, la commande sort
  en code 0 avec une ligne, et le passage suivant rattrape.
- **Les échecs.**
  - Le seul échec circonscrit est `publier` en code 3, prouvé par `publication.json`, et jamais
    par une sortie texte. Tout autre échec arrête le passage.
  - Un format changé (index, extracteur, modèle, contrat, silver) est refusé avant toute étape,
    avec le geste à faire. Le témoin `derive/chaine/formats.json` porte ces formats.
- **`verifier`**, chaque jour à 03:40 UTC : `verifier-bus`, `silver verifier`, `index verifier`
  et `index etat --complet`.
- **`remplir`** rebâtit tout depuis l'archive. Il est lancé à la main, sous sa propre unité.
- **`etat`**, en texte et en JSON, ne lance rien, n'écrit rien et ne joint aucun service. Sa
  première ligne dit tout. Il donne aussi le délai de chaque archive, de son arrivée dans le
  manifeste à la fin de l'étape `index`, étape par étape.

**Le durcissement.**
- `MemoryMax=512M` sans échange, et `OOMPolicy=continue` : un processus tué se compte, il ne
  coupe pas l'unité.
- `CPUQuota=100%` pour le passage et la vérification, 150 % pour le remplissage, et
  `CPUWeight=20`.
- Un score d'exposition de 1,1 à 1,2 pour chaque unité installée. `MemoryDenyWriteExecute` est retiré,
  parce que le Python d'uv n'a pas d'en-tête `GNU_STACK`.

## Conséquences

- **La BDPM va seule jusqu'à l'index.**
  - Les quatre premiers passages porteurs d'événements ont un délai médian de 63 s, et 115 s
    au plus.
  - Les fichiers servis vides sont écartés sans faire échouer la chaîne : quatre fois en trois
    jours pour `CIS_InfoImportantes`.
- **La cible de 60 s du PRD n'est pas tenue**, et ce qui pèse est connu :
  - la chaîne attend la fin de la collecte entière, soit 25 s le plus souvent et 84 s une fois ;
  - l'étape `index` a un coût fixe de 14 s.

  La déclencher archive par archive changerait la collecte : c'est une autre décision.
- **La mémoire.**
  - Le groupe de la chaîne touche 512 Mo à chaque passage, mais c'est du cache.
  - Le plus gros processus, celui des fragments, monte à 432 Mio au plus. Le seuil d'alerte
    est de 450 Mio, et aucun processus n'a été tué.
  - Avec Alamel en marche, les passages prennent 2 s de plus, et rien ne casse.
- **Le disque est partagé.** Redpanda garde ses valeurs de développement, dont
  `storage_min_free_bytes` à 10 Mo : il remplirait le disque, Alamel compris, presque
  jusqu'au bout. `chaine etat` montre donc la place libre, 22 Gio sur 37,6 au 19/11. Une
  rétention du bus, ou un plancher plus haut, reste à décider si l'archive grossit.
- **Ce qui coûte.**
  - Chaque fichier que root lit passe par la branche, le contrôle de l'IeC, puis beko.
  - Un changement de format demande un geste écrit, et non une reprise silencieuse.
  - Rien de dérivé n'est sauvegardé : après une perte, on rebâtit en 4 h environ.
- **Le Mac est au repos.** Plus de conteneur ni de tâche planifiée : il ne garde que le
  développement, les tests et la copie de l'archive (`rapatrier.sh`, chaque semaine).
- **À surveiller.**
  - Le résident des fragments : il suit la taille du silver, sans dériver pendant l'observation.
  - La place libre du disque.
  - L'âge de la dernière vérification.
  - Un passage à vide qui dépasserait la minute : il faudrait un court-circuit quand le silver
    n'a rien reçu.
- **Un écart connu.** Les variables `MONITOR_*` n'arrivent pas au passage : systemd voit deux
  déclencheurs, la même collecte par `OnSuccess=` et par `OnFailure=`. Le champ `declencheur`
  est donc vide. Il n'est qu'informatif, et le correctif est proposé après l'observation.

## Options écartées

| Option | Pourquoi pas |
|---|---|
| Un minuteur propre à la chaîne, ou au démarrage | un déclencheur de plus ; la collecte rattrape déjà après un redémarrage (`Persistent=true`) |
| Attendre quand le verrou est tenu | un passage bloqué en cache un autre ; le suivant rattrape une heure plus tard au plus |
| Le compte de la chaîne dans le groupe `docker` | un accès root ; la chaîne joint les services par leurs ports locaux |
| Le code par un clone de git sur le VPS, mis à jour sur place | sans version par dossier, un passage pourrait mélanger deux versions ; `git archive` et une bascule sous le verrou l'évitent |
| Un fichier d'environnement ou un dossier de travail dans les unités | systemd les lit en root, et suivrait un lien vers du code que le codeur écrit |
| Un plafond processeur dans `vps.yml` | Redpanda tient sur un cœur (`--smp=1`), et Qdrant ne travaille fort que pendant une construction |
| Rester sur le Mac | le Mac dort, et beko n'en veut plus pour ce qui tourne en continu |

## Références

- PRD §2.2 (délai de traitement) et §10.1 (sauvegarde).
- Ordre de la mission 10 et ses addendums.
- `infra/vps/README.md` (la procédure) et `infra/agents/vps/README.md` (le compte du codeur).
- `docs/rapports/mission-10/` : `mesures-remplissage.md`, `palier-2.md`, `observation.md`.
- ADR 0001 (la collecte), 0006 (le garde-fou de volume), 0007 (le bus), 0009 (le silver), 0011
  (l'index).
