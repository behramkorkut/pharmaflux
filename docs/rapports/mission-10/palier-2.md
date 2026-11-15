# Mission 10 — palier 2 : l'enchaînement

## Synthèse

**Fait** (`95a35ac`) :
- `chaine passer`, le passage horaire, avec son déclencheur ;
- `chaine verifier`, les vérifications quotidiennes ;
- `chaine etat`, en texte et en JSON ;
- le témoin des formats, avec `FORMAT_SILVER` ;
- trois unités et un complément, décrits plus bas ;
- la procédure (étape 9, l'état, les relevés de beko, la désinstallation) ;
- le script de mesure de l'encodage ;
- la CI ;
- les deux passages des README qui citaient `MemoryDenyWriteExecute` ;
- « 99,2 Mo » corrigé en Mio dans les mesures du remplissage (contrôle de
  `d543158`).

Les unités et le complément :
- `pharmaflux-chaine.service`, le passage horaire ;
- `pharmaflux-verification.service` et son minuteur, à 03:40 UTC ;
- le complément `OnSuccess=` et `OnFailure=` de la collecte.

**Vérifications locales** (commit testé : `95a35ac`, arbre propre) : vertes, sans service.
1033 tests passent et 14 d'intégration sautent ; la dernière retouche est couverte par les 129
tests de la chaîne et du VPS.

**Sur le VPS**, version déposée sans bascule (`courante` reste `eecc9f3`) :
- `systemd-analyze verify` : 0 ;
- score hors ligne : 1,1 pour le passage comme pour la vérification ;
- débit de l'encodage : la mesure ne tranche pas, parce que mon compte est plafonné à un cœur.
  Avec un seul cœur, un seul fil va 14 % plus vite que le défaut. La mesure sous l'unité est
  la question 1.

**Non vérifié** : `chaine passer`, `verifier` et `etat` contre un bus. C'est le rôle de la CI de
la PR, au commit poussé.

**Écarts** : deux, déclarés.
1. `evenements` 1 arrête le passage, au lieu de continuer comme le proposait mon §0. C'est la
   condition de la question 7.
2. Deux commits au lieu d'un : le code, puis ce rapport. La mesure de l'encodage demandait un
   commit à déposer.

**Questions pour l'IeC** : deux, en fin de rapport.

**Propositions** : une, l'encodage, en attente de ta décision.

## Détail

### Ce qui est livré

| fichier | rôle |
|---|---|
| `src/pharmaflux/chaine/horaire.py` | le plan du passage (5 étapes, jamais `index construire`), l'échec circonscrit (`publier` 3 prouvé par `publication.json`), le déclencheur (`MONITOR_UNIT`, `MONITOR_SERVICE_RESULT`, `MONITOR_EXIT_CODE`, `MONITOR_EXIT_STATUS`), les archives nouvelles du manifeste (`chemin_archive` non nul), les collections orphelines (comptées, jamais effacées) |
| `src/pharmaflux/chaine/verification.py` | `verifier-bus`, `silver verifier`, `index verifier`, `index etat --complet` ; une vérification en échec n'arrête pas les suivantes, sauf si elle est tuée |
| `src/pharmaflux/chaine/formats.py` | le témoin `derive/chaine/formats.json` (format de l'index, extracteur, modèle, `FORMAT_SILVER`, versions de contrat) ; le refus nomme le plus grand geste |
| `src/pharmaflux/chaine/etat.py` | `chaine etat` : verdict, derniers passages par genre, âge du dernier complet, passages de collecte non traités, disque (`statvfs`), orphelines, fraîcheur, formats, dernière erreur |
| `src/pharmaflux/chaine/passage.py` | `derouler` reçoit un contrôle (avant toute étape), un juge des échecs circonscrits, des relevés de départ et une conclusion ; le geste d'une étape qui refuse |
| `src/pharmaflux/chaine/remplissage.py` | le remplissage refuse un silver ou des contrats changés (il ne reconstruit que l'index), et écrit le témoin quand il est complet |
| `infra/vps/pharmaflux-chaine.service` | le passage : `CPUQuota=100%`, `TimeoutStartSec=50min`, le durcissement du remplissage, aucun `OnFailure=` |
| `infra/vps/pharmaflux-verification.service`, `.timer` | 03:40 UTC, `Persistent=true`, `TimeoutStartSec=40min` |
| `infra/vps/pharmaflux-collecte.service.d/chaine.conf` | `OnSuccess=` et `OnFailure=` vers le passage, rien d'autre |
| `infra/vps/README.md` | étape 9 (9a les unités, 9b la mise en service, 9c polkit vide), l'état, les relevés de beko, la bascule sous `flock`, la désinstallation dans l'ordre inverse |
| `infra/vps/mesurer_encodage.py` | le débit d'e5 selon `intra_op_num_threads` |
| `tests/test_chaine_horaire.py`, `tests/test_vps.py` | 32 tests neufs ; ceux des unités sont paramétrés sur les trois unités de la chaîne |
| `.github/workflows/ci.yml` | deux passages à vide, les vérifications, `chaine etat` en JSON : `à jour`, aucun écart de formats |

### Les décisions prises en codant

- **Le premier passage écrit le témoin.** Le remplissage du palier 1 l'a précédé : sans témoin,
  le passage passe, et il l'écrit s'il est complet. Les étapes refusent déjà d'elles-mêmes un
  format d'index, un extracteur, un modèle ou un contrat changés. Seul le silver n'avait rien,
  et il est au format 1 depuis le début.
- **Le verrou tenu sort aussi en 0 pour les vérifications**, comme pour le passage (question
  9). `chaine etat` montre l'âge de la dernière vérification.
- **La fraîcheur** suit l'archive jusqu'au premier passage complet dont l'étape `index` rend 0,
  même quand un passage coupé l'a vue avant lui.
  - Sont comptées les archives écrites après le départ du premier passage horaire, et non le
    rattrapage de la mise en service.
  - Nature d'une archive, d'après son bilan : `porteuse`, `sans_evenement`,
    `confirmee_apres_attente`, `en_attente`, `ecartee` ou `sans_bilan`.
  - Le délai d'un passage porteur est le maximum de ses archives porteuses. Le médian et le
    maximum sont rendus ; le p95 seulement à vingt valeurs.
- **Les collections orphelines** sont relevées par le passage, qui joint Qdrant. Le relevé est
  lu dans le journal : `chaine etat` ne joint rien.
- **Un processus tué au plafond n'est jamais circonscrit**, même pour une vérification qui rend
  1 : le compteur du noyau l'emporte.

### Les vérifications locales

| commande | résultat |
|---|---|
| `uv run ruff check .`, `ruff format --check .` | vertes |
| `uv run mypy src` | 101 fichiers, aucune erreur |
| `uv run pytest -q` | 1033 passés, 14 sautés (intégration, sans service), 6 min |
| `tests/conftest.py::reseau_coupe` | garde de session inchangée ; les sondes et les étapes des tests neufs sont simulées |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | 29 tests, OK |
| `docker compose -p pharmaflux … config -q`, les deux combinaisons | vertes (rien démarré) |
| YAML de la CI | `yaml.safe_load` sans erreur |
| `shellcheck`, `make -n` | sans objet : aucun `.sh` ni `Makefile` touché |

### Sur le VPS (mon compte), version `95a35ac` déposée sans bascule

| commande | résultat |
|---|---|
| `git archive` puis `uv sync --frozen --no-dev --no-editable --compile-bytecode` | fait ; `VERSION` = `95a35ac19195111f276949a54b654ec0bab00192` |
| `find … ! -group pharmaflux-chaine`, `-type d ! -perm -2000` | rien |
| `readlink /srv/pharmaflux/code/courante` | `versions/eecc9f3…` : rien n'a basculé |
| `systemd-analyze verify` sur le passage, la vérification et le minuteur | 0 (deux remarques sur `xfs_scrub`, une unité du système) |
| `systemd-analyze security --offline=true` | passage 1,1 ; vérification 1,1 ; remplissage 1,1 |

### L'encodage (décision de l'IeC au contrôle des mesures)

`infra/vps/mesurer_encodage.py`, lancé depuis la version déposée, par son chemin (`python -I`),
sous mon compte, le 15/11 vers 12:35 UTC. L'échantillon est fixe : 1024 fragments, un sur 73 de
`fragments.jsonl`. Les lots font 256 fragments, une première exécution est faite hors mesure,
et rien n'est écrit.

| `intra_op_num_threads` | durée | fragments/s | cœurs occupés | fils vus |
|---|---|---|---|---|
| 0 (défaut) | 215,2 s | 4,76 | 1,00 | 4 |
| 1 | 189,0 s | 5,42 | 0,99 | 3 |
| 2 | 213,1 s | 4,81 | 1,00 | 4 |

Contexte : `cpu_count` 2, affinité 2, `/proc/cpuinfo` lisible ; KVM, deux sockets d'un cœur.

**La mesure ne tranche pas l'hypothèse.** Ma tranche utilisateur est plafonnée à un cœur
(`systemctl show user-2101.slice` : `CPUQuotaPerSecUSec=1s`, `MemoryMax=536870912`). Sous mon
compte, deux fils ne peuvent donc pas occuper deux cœurs : 1,00 cœur dans les trois cas.
Elle montre seulement ceci :
- avec un seul cœur disponible, un seul fil va 14 % plus vite que le défaut (5,42 contre 4,76
  fragments/s) ;
- le défaut ouvre deux fils de calcul, qui se disputent le cœur. Le défaut d'onnxruntime
  compte donc bien deux cœurs quand `/proc/cpuinfo` est lisible.

Le remplissage, sous l'unité (`CPUQuota=150%`, `ProcSubset=pid`), a encodé 75 605 fragments
en 13 264 s, soit 5,70 fragments/s. C'est un peu plus que mes 4,76 au défaut, mais sur d'autres
fragments, et la longueur des textes pèse sur le débit.

**Ce qui trancherait** : la même mesure dans les conditions de l'unité (compte
`pharmaflux-chaine`, `CPUQuota=150%`, `ProcSubset=pid`). Mon compte ne peut pas lancer d'unité
transitoire. Je propose deux voies (question 1).

**Rien n'est changé** : ni `intra_op_num_threads`, ni `ProcSubset=pid`.

## Questions pour l'IeC

1. **La mesure de l'encodage sous l'unité.** Laquelle des deux voies ?
   - **(a)** beko lance le script par `systemd-run`, avec les propriétés de l'unité de
     remplissage. Commande à écrire, et à contrôler par toi.
   - **(b)** une unité de mesure à part dans `infra/vps/`, contrôlée et installée comme les
     autres, puis retirée.

   Les deux font tourner du code de ma branche sous `pharmaflux-chaine`, jamais sous root.
   Sans mesure, `intra_op_num_threads` reste au défaut (addendum 1, question 17).
2. **Le premier passage écrit le témoin des formats**, faute de témoin du remplissage du
   palier 1. Est-ce acceptable, ou préfères-tu que le témoin s'écrive avant la mise en
   service ? Il faudrait alors une commande à part, lancée sous l'unité de remplissage par le
   codeur.

## Ce qui reste au palier 2

1. Ton contrôle de `95a35ac`.
2. La CI de la PR sur le commit poussé : le passage, les vérifications et l'état contre un bus.
3. Le dépôt sous le verrou (4a), l'étape 9 par beko, puis l'observation de 48 heures au moins,
   avec un redémarrage.
4. Le passage à vide, mesuré sur le VPS dès le premier passage. Au-delà d'une minute, je
   proposerai le court-circuit.
