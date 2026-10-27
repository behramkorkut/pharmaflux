# Mission 03 — contrôle du palier 2 (IeC)

**Commit contrôlé** : `ab015b2`. **Verdict** : palier 2 accepté **sous
réserve de trois correctifs légers**, dans un nouveau commit avant le
palier 3. Le premier compte : sans lui, la condition de la décision 5
(rétention posée par le projet) peut être contournée sans bruit.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `ab015b2`, avec le courtier du
projet démarré (`pharmaflux-redpanda`, sain) :

- ruff check et format : vert ;
- mypy, 35 fichiers : vert ;
- pytest : 432 tests, tous passent ;
- `pytest -m integration` : 2 tests, verts en 3,5 s ;
- `rpk cluster config get auto_create_topics_enabled` : **`true`** (voir
  correctif 1).

## Sur le fond

- **L'addendum est suivi point par point** :
  - valeur nue, à l'octet près ;
  - clé = objet `cle` compact et trié ;
  - horodatage = `date_observation` ;
  - 3 partitions ;
  - `murmur2_random`, avec la raison écrite ;
  - rétention sans limite et `cleanup.policy=delete` posés à la création ;
  - `LogAppendTime` sur la seule file des échecs ;
  - codes de sortie 1, 2 et 3 ;
  - refus sans forçage d'un fichier publié modifié ;
  - état écrit après les accusés de réception.
- **Le producteur** est configuré comme il faut : idempotent, avec la
  taille vérifiée à `produce`. Une file de départ pleine fait attendre au
  lieu d'échouer, et c'est le bon choix.
- **Le registre** : historique enregistré avant le courant, règle posée
  par sujet, enregistrement idempotent. Le prix de la valeur nue est dit
  dans le module.
- **Le compose** suit la décision 9. Les adresses annoncées interne et
  externe sont justes, et le healthcheck rend `--wait` utile.
- **Les tests** couvrent l'ordre, la reprise, les refus, la file des
  échecs et la livraison en échec. Le préfixe unique par test est un bon
  correctif.

## Correctifs

1. **Désactiver la création automatique des topics.** Le mode
   `dev-container` l'active, et le courtier le confirme. Un `produce` vers
   un topic qui n'a pas été préparé créerait alors ce topic avec la
   rétention par défaut, sans erreur. C'est exactement ce que la condition
   de la décision 5 veut empêcher. Pose `auto_create_topics_enabled=false`
   au démarrage, dans le compose, de la façon que Redpanda documente pour
   une propriété de cluster en v26.2. Vérifie avec `rpk cluster config get`
   et cite la commande dans le rapport. Un test d'intégration : un
   `produce` vers un topic inconnu échoue, et aucun topic n'apparaît.
2. **Le topic vient du dossier, pas de la ligne.** `envelopper` prend le
   topic dans le champ `entite` de l'événement, alors que la publication
   prépare le topic et choisit le `schema_id` d'après le dossier. Une
   ligne dont l'`entite` ne correspond pas à son dossier partirait vers un
   topic non préparé, avec l'identifiant de schéma d'un autre sujet. Une
   telle ligne va dans la file des échecs, motif `illisible`, et le détail
   nomme les deux entités. Un test unitaire suffit.
3. **Le sha256 enregistré est celui des octets publiés.** `_publier_fichier`
   relit le fichier entier après la publication pour calculer son sha256.
   Si le fichier change entre-temps, par exemple à cause d'un rejeu lancé
   en parallèle, l'état enregistre une empreinte qui n'est pas celle de ce
   qui a été publié. Calcule le sha256 pendant la lecture qui publie, ligne
   par ligne. `_verifier_inchanges` peut lire par blocs : le plus gros
   fichier pèse 34 Mo aujourd'hui, mais il grossira.

Une retouche sans contrôle de ma part : la docstring de
`PublicationRefusee` parle d'un état « absent alors qu'il faut reprendre ».
Le code ne fait pas ce refus, et l'addendum ne le demande pas. Aligne le
texte.

## Réponse à la question

**Un même `schema_id` pour les onze sujets, c'est acceptable.** C'est le
comportement normal d'un registre compatible Confluent : un identifiant
désigne un *contenu* de schéma, pour tout le registre ; c'est la version
dans un sujet qui est propre à chaque sujet. Un consommateur qui résout
l'en-tête `schema_id` obtient le bon schéma. Dis-le en une phrase dans
l'ADR 0007, pour qu'un lecteur ne prenne pas ce `1` partout pour une
erreur.

## Suite

Les trois correctifs dans un commit, avec une réponse courte dans
`docs/rapports/mission-03/palier-2-correctifs.md`. Ensuite, le palier 3.
