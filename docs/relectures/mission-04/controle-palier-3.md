# Mission 04 — contrôle du palier 3 (IeC)

**Commit contrôlé** : `59421c7` (fils de `00cba9f`), contre l'ordre et
l'addendum 1. **Verdict : correctif demandé (deux points, un commit),
puis clôture sur le Mac par beko.**

## Revérifié par l'IeC

Sur une extraction du commit (`git archive 59421c7`) :

| commande | résultat |
|---|---|
| `git diff --stat 00cba9f 59421c7 -- src tests` | vide : les 470 tests du palier 2 valent ici |
| YAML du workflow (`ruby -ryaml`) | valide |
| `make -n demo DEMO_OPTIONS=--sans-pause` | prérequis, `up --pull never`, schémas, `demo rejouer … --sans-pause`, `verifier-bus --racine demo/archive` |
| `rpk topic list` sur le bus du Mac | les onze topics de la démo du palier 2, `echecs`, `_schemas` : aucun reste de test |

Relu, et conforme :

- **Le Makefile** : compatible GNU Make 3.81, il ne télécharge aucune
  image (`--pull never`) et ne nomme que le projet `pharmaflux`.
  `rebatir` n'efface que le volume de ce projet et `data/demo`.
- **`prerequis.sh`** : les deux corrections de l'addendum sont tenues.
  La liste des images vient de `config --images` (vérifiée sur le Mac),
  et la console n'est vérifiée que sous son profil. Le script ne fait
  que lire. La sortie est montrée dans les deux cas.
- **L'étape CI** vient après les tests d'intégration et avant `down -v`.
- **Le README** contient la séquence pour une machine qui a déjà un
  volume (refus, `make rebatir`, puis `make demo`). L'ADR 0008, CONTEXTE
  et le journal sont à jour.
- **Aucune IP, aucun hôte, aucun chemin personnel** n'apparaît dans le
  diff.

## Correctif demandé

1. **`verifier_etat_du_bus` compte trop large.** Le filtre
   `t.startswith(f"{prefixe}.")` compte comme topics du projet ceux des
   tests d'intégration, `pharmaflux.test-xxxxxxxx.…`, puisque leur
   préfixe commence par `pharmaflux.`. Ces topics sont effacés à la fin
   de chaque test, et le bus du Mac n'en garde aucun. Mais deux cas font
   refuser `make demo` avec « bus non vide sans état », qui renvoie vers
   `make rebatir` :
   - en CI, une suppression pas encore visible au moment où l'étape
     démarre, juste après les tests ;
   - sur le Mac, un test interrompu.

   En CI, cela ferait échouer à tort le seul push de la mission.
   **Correction** : compter seulement les topics exacts que la démo
   publierait, c'est-à-dire `nom_topic(e, prefixe)` pour chaque entité de
   la sélection, plus `topic_echecs(prefixe)`. **Test** : un courtier
   simulé qui porte des topics `pharmaflux.test-0000abcd.….v1` et aucun
   topic de la démo, sans état, ne fait pas refuser.
2. **Le README dit « trois suppressions de présentations ».** Or la copie
   donne dix événements `supprimee`, arrivés en trois fois (2, 1 puis 7),
   d'après tes mesures du §0. Il faut écrire les deux nombres. Vérifie le
   même passage dans l'ADR 0008, CONTEXTE et le journal. `test_demo.py`
   contrôle déjà les nombres du README : ajoute ce compte si c'est
   simple.

Un commit, un rapport court (`reponse-controle-3.md` ou une ligne dans
`palier-3.md`, comme tu préfères), puis l'annonce.

## Écarts du rapport

1. **`make --version` refusé** : refus signalé et non contourné, c'est
   bien. La proposition est retenue, et l'IeC la soumet à beko.
2. **`make demo` et `make rebatir` laissés à beko** : conforme. La
   clôture sur le Mac est la sienne, sur le commit du correctif :
   `make rebatir`, puis `make demo` dans `pharmaflux-codeur/`. Sa sortie
   est à citer dans `pr.md`.
3. **Les limites de la CI** (amd64, Make 4.3, Compose du runner) : elles
   iront dans `pr.md`.
4. **`pr.md` après la relecture** : conforme au circuit.
