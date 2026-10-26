# Mission 03 — palier 1 : écriture des événements en flux (décision 1)

Addendum 1 lu (`28e905a`). Python pur, aucune commande `docker`. Archive
`~/pharmaflux-data` en lecture seule, aucune requête vers les sources.

**Fait**

- **`comparaison.comparer` rend un itérateur** (`Iterator[Evenement]`). Les
  vérifications (même fichier, horodatage connu) se font à l'appel ; le
  générateur construit un **squelette** par événement (clé de tri, type,
  ligne avant, ligne après, rang, empreinte), trie la liste sur la clé de
  tri calculée comme `Evenement.cle_de_tri` (colonnes de la clé par ordre de
  leur nom, ordre des types, empreinte, rang signé), puis fabrique chaque
  événement quand l'itérateur avance. L'empreinte, calculée une fois pour le
  tri, est passée à la fabrique. `appliquer` et `etat_du_snapshot` ne
  changent pas.
- **`volume.Resultat` ne porte plus ses événements** : il garde snapshot,
  verdict, dernier retenu et `date_source`, et `evenements()` rappelle
  `comparer` à la demande (rien n'est gardé, un test peut l'appeler deux
  fois). **`Suivi.resultats` est retiré** (K.1) ; `traiter` et `clore`
  rendent les mêmes résultats dans le même ordre.
- **`bilan.etablir(resultat, comptes=None)`** : les comptes par type viennent
  de celui qui a écrit les événements ; sans eux, il recompte en rappelant
  la comparaison (les tests appellent `etablir(r)` comme avant).
- **`rejeu`** : `_ecrire_evenements` sérialise et écrit chaque événement dès
  qu'il est produit dans le même `.<nom>.jsonl.partiel`, renommé à la fin
  (fichier vide quand rien n'a changé, `.partiel` ignoré par
  `lire_evenements`, comme avant) ; `_lire_snapshot` lit et construit dans la
  même fonction (octets et `Lecture` meurent au retour) ; le corps de la
  boucle est sorti dans **`_traiter_archive`**, pour qu'à la lecture d'une
  archive seuls le dernier retenu et le snapshot en attente soient encore en
  mémoire (sans cela, le `Resultat` de l'itération précédente gardait le
  retenu d'avant : trois snapshots de `presentations` vivants, 200 Mo).
- **Partage des valeurs répétées** (hors de la liste du §0 B, voir Écarts) :
  dans `contrats.verification._decouper`, une valeur brute qui se répète
  d'une ligne à l'autre (statut, taux, date, prix) n'est gardée qu'une
  fois ; dans `snapshot.depuis_lecture`, de même pour les valeurs
  normalisées qui changent (`_partager` ; une valeur inchangée reste la brute
  elle-même). Le texte décodé meurt dès qu'il est découpé (`verifier` passe
  `texte.split("\n")`, pas `texte`). Poids tracé d'un snapshot :
  presentations 26,6 → 14,7 Mo, compositions 23,8 → 12,5, smr 19,5 → 11,7,
  specialites 21,5 → 12,1, asmr 15,2 → 9,6.
- **Tests** : les 413 existants passent **sans changement d'attendu** ; les
  adaptations sont de forme : `list(comparer(…))` là où la liste était
  indexée, `r.evenements()` au lieu de `r.evenements`, et les deux
  assertions sur `suivi.resultats` portent sur les résultats que `traiter` a
  rendus (mêmes listes attendues). Un test de plus, **`tests/test_memoire.py`**
  (414) : deux snapshots fabriqués de 4 000 lignes (un libellé et une clé par
  ligne, toutes modifiées), `tracemalloc` mesure leur poids M puis le pic
  pendant que `rejeu` écrit les 4 000 `modifiee` ; le surplus doit rester
  sous M / 2 et le fichier écrit doit peser plus que ce surplus. Mesuré :
  M 6,1 Mo, surplus 1,0 Mo (ratio 0,16 ; 2,7 avec le code de la mission 02).
- **ADR 0006** : coût mis à jour, section datée « Mise à jour du 27/10/2026 »
  (décision, ce qui ne change pas, mesures, options écartées), références.

**Mesures** (copie du Mac, onze fichiers, 30 fichiers de sortie, 173 Mo)

| mesure | mission 02 (`647fb6a`) | palier 1 |
|---|---|---|
| rejeu complet, `/usr/bin/time -l uv run pharmaflux evenements`, trois exécutions | 474 Mo | **118, 134, 143 Mo** |
| durée du rejeu complet | 7,9 s | 7,9 s |
| `--reprendre` sans rien à faire | 121 Mo | 109 Mo |
| `--version` | 37 Mo | 37 Mo |
| `diff -r` contre la sortie du code fusionné | — | **identique** |
| pic tracé pendant l'écriture : compositions / presentations / conditions / specialites / smr / asmr | 218 / 173 / 150 / 132 / 122 / 91 Mo | 24 / 22 / 18 / 18 / 18 / 14 Mo |
| surplus tracé pendant l'écriture de 20 000 `modifiee` (deux snapshots de 53 puis 28 Mo) | 146 Mo (ratio 2,77) | 6 Mo (ratio 0,22) |

Le pic du rejeu complet est désormais la lecture de la troisième archive de
`bdpm.presentations` (dernier retenu + nouveau snapshot + texte en cours de
découpage), plus la sérialisation des 32 439 `creee` des compositions. Les
32 439 squelettes pèsent 11 Mo tracés (le §0 en estimait 6).

**Vérifications locales** (arbre committé comme fils de `8c2017e`)

| commande | résultat |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 132 files already formatted |
| `uv run mypy src` | Success: no issues found in 30 source files |
| `uv run pytest -q` | **414 passed** in 14,3 s (413 + `test_memoire`, 3,4 s) |
| `python3 infra/agents/test_garde_fou.py` | OK |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| rejeu complet ×3 puis `diff -r` contre la référence du code fusionné | 118, 134, 143 Mo ; identique |
| `evenements --reprendre` sur cette sortie | 109 Mo, rien à refaire, code 0 |

**Écarts à l'ordre**

1. **Le §0 B.5 disait « rien d'autre »** que le flux et la mort précoce des
   octets. Le flux seul donnait **171 Mo**, stables sur trois exécutions,
   au-dessus de la cible de 160 : il retirait la sérialisation (474 → 171),
   mais le pic restant était la coexistence de deux snapshots de
   `presentations` (26,6 Mo chacun) à la lecture de la troisième archive, un
   plancher que le flux ne touche pas. D'où le partage des valeurs répétées,
   deux lignes dans la lecture et la normalisation (`_decouper`,
   `depuis_lecture`), sans effet sur ce que les lignes contiennent (sortie
   identique, 413 tests inchangés, `brutes is` et `normalisees is brutes`
   conservés). Si l'IeC préfère ne pas toucher `contrats/verification.py`
   dans ce palier, je retire ces deux lignes par un commit : on revient à
   171 Mo.
2. **Test de mémoire à 4 000 lignes**, pas 20 000 : sous `tracemalloc`,
   20 000 lignes coûtent 15 s (toute la suite en fait 14) ; 4 000 lignes
   coûtent 3,4 s et le ratio y est le même (0,16 contre 0,22 à 20 000).
3. **La mesure résidente varie de 25 Mo** d'une exécution à l'autre (118 à
   143), à code et données égaux : allocateur et hachage. Le rapport donne
   les trois ; la cible de 160 est tenue à chaque fois, avec 17 Mo de marge
   au pire.
4. `_traiter_archive` a neuf paramètres : c'est le prix de sortir le corps de
   la boucle sans créer d'objet d'état ; je peux le regrouper si l'IeC le
   demande.

**Questions pour l'IeC** : garder le partage des valeurs répétées dans ce
palier (écart 1), ou le retirer ?

**Propositions d'évolution** (PRD, consignes) : aucune.
