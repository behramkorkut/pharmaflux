# Mission 02 — contrôle des correctifs du palier 2 (IeC)

**Commit contrôlé** : `155941f`. **Verdict** : les deux correctifs sont
acceptés, et le palier 2 avec eux. Le palier 3 peut commencer.

## Vérifications rejouées

Sur l'arbre du codeur, propre :

- ruff check et format, mypy : vert ;
- pytest : 376 tests, tous passent ;
- crochets git et garde-fou : OK ;
- `profil` : 11 fichiers, 0 bloquante ;
- `questions verifier` : 25 / 5 / 10.

## Les deux correctifs

1. **Ordre des colonnes.** J'ai rejoué ma sonde sur les **archives
   réelles complètes**, pas seulement sur les fixtures. J'ai pris l'état
   initial de trois fichiers, passé ses événements par `serialiser` puis
   `deserialiser`, et vérifié quatre choses : l'identifiant recalculé vaut
   `id`, le tri est inchangé et déjà trié, `appliquer` sur les relus égale
   `etat_du_snapshot`, et les identifiants sont tous distincts. Les quatre
   tiennent pour les trois fichiers :

   - `bdpm.compositions`, clé à 5 colonnes, 32 439 événements ;
   - `bdpm.infos_importantes`, clé à 4 colonnes, 10 905 événements ;
   - `bdpm.smr`, ligne à ligne, 15 547 événements.

   **Le choix de l'ordre alphabétique des noms est accepté.** C'est l'ordre
   que le JSON écrit, donc un consommateur qui ne lit que le JSON le
   retrouve sans le contrat. L'ADR 0006 doit le dire explicitement, en deux
   points :

   - l'identité de ligne et l'identifiant joignent les valeurs de la clé
     dans l'ordre alphabétique des noms de colonnes ;
   - le tri des événements d'une comparaison suit ce même ordre, et non
     l'ordre du fichier.

2. **`deserialiser` strict.** `"false"` et `1` sont refusés pour
   `etat_initial`, et `2.7`, `true` et `"2"` le sont pour `rang`.

## Suite

Commite ce fichier tel quel, puis passe au palier 3 : décisions 7 à 10,
ordre et addendum 1. Points à ne pas manquer :

- **la sortie par archive**, écrite atomiquement dans l'ordre événements,
  bilan, état ;
- **un snapshot en attente n'est pas traité** : son bilan est réécrit quand
  il est tranché (F.2) ;
- **les tests de reprise** : un point d'arrêt après chaque archive, dont un
  juste après une archive en attente tranchée dans chacun des deux sens.
  Ajoute la suppression de `etat.json`, l'oscillation, et `appliquer` sur
  la sortie **relue depuis le disque** ;
- **`--reprendre` refuse** quand une version de contrat a changé, avec un
  code de sortie non nul ;
- **la démonstration sur la copie du Mac**, en lecture seule, selon
  l'addendum ;
- **l'ADR 0006**, `CONTEXTE.md`, le journal (en fin de fichier) et le
  `README.md` ;
- facultatif : un test de `Suivi` avec `seuil=0.10` pour une suppression
  retenue à travers le garde-fou.

À la fin du palier : vérifications, rapport, un commit, et tu t'arrêtes.
