# Mission 01 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `51a55e5`. **Verdict** : palier 1 accepté, avec
**un correctif** (C1) à livrer dans un commit à part avant le rapport du
palier 2. La décision 11 est validée par la mesure de beko sur le VPS
(ci-dessous) : score d'exposition **1,3**, passage manuel sans erreur.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `51a55e5` :

- ruff check et format (55 fichiers) : vert ;
- mypy strict (12 fichiers) : vert ;
- pytest : 80 tests, tous passent ;
- garde-fou : 16 tests, tous passent ;
- crochets git : vert ;
- shellcheck 0.11.0 : rien à signaler.

Sur la copie rapatriée du Mac, en lecture seule :

- `pharmaflux etat` lit les 352 lignes du manifeste en flux. Il affiche la
  colonne `identifiant` et « aucun fichier partiel dans bronze/ ».
- `bronze.lister` parcourt les quatorze entrées du catalogue : 16 archives,
  aucun `NomArchiveInvalide`, et la dernière archive de chaque entrée se
  décompresse.

## Mesure sur le VPS (beko, 26/10/2026, 00:28 UTC)

Branche déployée selon l'étape 7 du README, variante « branche de mission »,
unités réinstallées, passage manuel hors minuteur :

- passage `20261026T002839Z` : 0 nouveau, 12 inchangés, **0 erreur** ; les
  deux entrées quotidiennes sont `déjà collectée aujourd'hui` ;
- journal au format UTC (`2026-10-26T00:28:39Z INFO …`), décision 9 ;
- `Mem peak` 42,8 Mo, 1,155 s de CPU, comme sous l'unité de la mission 00 ;
- `systemd-analyze security` : **1,3 OK**, contre 6,3 avant le durcissement.
  `MemoryDenyWriteExecute=true` est donc conservé, et `PrivateUsers=true`
  reste inutile.

Le VPS tourne sur la branche de mission jusqu'à la fusion ; il reviendra
sur `main` ensuite (étape 4).

## Sur le fond

- **Décision 1** : c'est conforme. La règle « tout nom qui commence par un
  point est ignoré » est plus simple que deux motifs, et elle couvre aussi
  `.DS_Store` sur le Mac. L'erreur franche sur un nom visible hors forme est
  le bon choix : seul le collecteur écrit le bronze.
- **Décision 9** : c'est conforme. L'archive passe avant l'empreinte, et
  l'empreinte retombe sur le sha256, donc pas de réarchivage, ce qui est
  cohérent avec le C1 de la mission 00. La recherche des liens nouveaux est
  sous le filet, et `_signaler` regroupe enfin les trois endroits qui
  enchaînaient les motifs.
- **Décision 10** : c'est conforme.
- **Décision 11** : chaque directive est justifiée d'une ligne. Le couple
  `@system-service` puis `~@privileged @resources` est la forme que
  recommande systemd. `EPERM` laisse une trace lisible au lieu d'un
  `SIGSYS` muet. `Nice`, `IOSchedulingClass` et `MemoryMax` sont posés par
  systemd avant le filtre, donc `~@resources` ne les gêne pas.

## Écarts

1. **`UMask=0027`** : accepté. Le §0 proposait `0077`, ce qui aurait cassé
   le rapatriement. Le commentaire de l'unité le dit, c'est suffisant.
2. **`lien_change` sur l'entrée au lieu d'un `lien_nouveau`** : accepté,
   c'est la réponse à ta question. La ligne reste rattachée à
   `bdpm.documentation_formats` et l'archive est prise sans attendre, ce
   qui vaut mieux qu'une ligne orpheline. Il en découle une conséquence,
   traitée par C1. Une autre est notée pour plus tard : après la mise à jour
   du catalogue, les archives v5 et v6 sont dans deux dossiers de `bronze/`.
   Rien à faire aujourd'hui, puisque le PDF n'a pas de contrat. Mais le jour
   où un lecteur parcourt le PDF par identifiant, il devra suivre les deux
   noms.
3. **`PrivateUsers=true` non posé** : accepté comme réserve, si la mesure
   reste à 3 ou plus.

## Correctif demandé

**C1. Une documentation PDF archivée sous `lien_change` vaut collecte du
jour.** `manifeste.etat_connu` ne compte dans `collectes_du_jour` que les
lignes sans erreur. Une ligne `lien_change` est en erreur, alors que ses
octets ont bien été reçus et archivés. Résultat : tant que le catalogue
n'est pas mis à jour, l'entrée quotidienne est retéléchargée **à chaque
passage**, soit 24 fois par jour au lieu d'une. Cela peut durer plusieurs
jours, le temps d'un commit, d'une fusion et d'un déploiement. Le site est
un service public (règle commune du `CLAUDE.md`).

Attendu :

- une ligne compte comme collecte du jour quand **ses octets ont été reçus
  et son empreinte connue** et que ses seuls motifs sont des
  **signalements** : `lien_change`, et `lien_absent` sur une entrée
  quotidienne ;
- une erreur de téléchargement (HTTP, délai, `inattendue`) ne compte
  toujours pas : la règle de la mission 00 reste vraie pour elle.

Le critère exact est à toi. Il doit tenir dans le code, sans comparer des
chaînes de motifs dispersées. Une liste des motifs de signalement définie à
un seul endroit fait l'affaire.

Test : deux passages le même jour avec un `_v6.pdf` sur la page
téléchargent le PDF une seule fois, la deuxième ligne est `ignoré` comme
une collecte quotidienne normale, et l'erreur reste visible dans `etat`.

## Suite

Réponds au C1 dans le rapport du palier 2. Commite ce fichier tel quel, puis passe au palier 2.
