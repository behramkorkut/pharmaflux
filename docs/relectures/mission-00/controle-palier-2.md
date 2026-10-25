# Mission 00 — contrôle du palier 2 (IeC)

**Commit contrôlé** : `91f4c62`. **Verdict** : palier 2 accepté **sous
réserve de deux correctifs** (C1, C2), à livrer dans un commit à part
avant le palier 3.

## Vérifications rejouées

ruff (check et format, sans `extend-exclude`), mypy strict (11 fichiers),
pytest (45 tests), garde-fou (15 tests) : tout est vert. Les en-têtes
enregistrés dans `tests/fixtures/` ne contiennent ni cookie ni secret.

La requête supplémentaire sur `CIS_InfoImportantes.txt` est bien
documentée : l'empreinte sur lignes triées reste en place comme filet.

## Correctifs demandés

**C1. Une archive écrite doit toujours laisser son empreinte connue.**
Dans `passage.py`, `_appliquer_page` passe en `erreur` une ligne déjà
archivée (`lien_absent`), et `analyse_impossible` archive sans empreinte
de comparaison. Or `manifeste.dernieres_empreintes` ne retient que
`nouveau` et `inchange`. Conséquence : tant que le lien reste absent ou
que la page reste illisible, le **même contenu est réarchivé à chaque
passage**, soit 24 copies par jour. Attendu :

- toute ligne avec un `chemin_archive` met à jour l'empreinte connue,
  quel que soit son statut ;
- pour `analyse_impossible`, l'empreinte de comparaison retombe sur le
  `sha256` des octets, ce qui évite de réarchiver un contenu identique ;
- `_appliquer_page` **n'écrase pas** une erreur existante. Par exemple,
  un `HTTP 404` sur un lien absent donne `HTTP 404 ; lien_absent`.

Tests : deux passages successifs avec un lien absent donnent une seule
archive. Même chose avec une page illisible identique aux deux passages.

**C2. Une ligne tronquée en fin de manifeste ne doit pas arrêter la
collecte.** Après une coupure de courant pendant `ajouter`, la dernière
ligne peut être incomplète. `manifeste.lire` lève alors une erreur, et
**tous les passages suivants échouent** sur un VPS que personne ne
surveille. Attendu :

- une dernière ligne illisible est ignorée, avec un avertissement dans
  le journal ;
- une ligne illisible **au milieu** du fichier reste une erreur franche,
  car c'est un signe de corruption ;
- `ajouter` garantit qu'une nouvelle ligne commence sur une ligne
  propre : si le fichier ne finit pas par `\n`, il en écrit un d'abord.

Test : manifeste terminé par une ligne coupée, puis passage, puis
lecture. Le passage réussit et la ligne coupée est ignorée.

## Tes questions

1. **PDF du format exclu du contrôle `lien_nouveau`** : d'accord.
2. **`lien_absent` téléchargé et archivé quand même** : d'accord sur le
   principe (l'archive est irremplaçable), avec le correctif C1.
3. **Cadence quotidienne sans ligne « différé »** : d'accord. Les mesures
   de fraîcheur tiendront compte de la cadence de chaque entrée.

Les écarts 3, 5, 6 et 7 sont acceptés : chemin relatif, champ
`identifiant`, `version_collecteur`, commande `catalogue`, gestion du 304.

## Tes propositions

- **(a) 14e entrée `bdpm.documentation_formats`** : acceptée, en cadence
  **quotidienne** et en empreinte `octets`. Un changement de ce PDF
  signale un changement de schéma. Ajoute-la avec C1 et C2.
- **(b) PRD annexe A** : je l'intègre au PRD v0.2.

## Remarques mineures (pas bloquantes)

- Un `SIGKILL` pendant l'écriture laisse un fichier caché
  `.….partiel-<pid>`. C'est sans danger : `etat` peut le signaler plus
  tard, rien à faire maintenant.

## Suite

1. Un commit « correctifs du contrôle du palier 2 » (C1, C2, entrée
   documentation), avec ses tests. Ajoute une courte section en tête du
   rapport du palier 3 qui donne ce commit et ce qui a changé.
2. Puis le palier 3 selon l'ordre et l'addendum 2 : unités systemd,
   `rapatrier.sh`, procédure. Commit du palier 3, puis arrêt avec
   « correctifs `<sha>`, palier 3 prêt `<sha>` ».
