# Mission 10 — contrôle des retouches du palier 2 (IeC)

**Commit contrôlé** : `f35d79702a8d66fa8cb1ca2f1c09b41e062fe79b` · **Date** : 15/11/2026

**Verdict : accepté.**
- Le codeur peut déposer ce commit et basculer `courante` sous le verrou (4a).
- beko pourra ensuite installer les unités depuis ce commit (9a, 9b, 9c).

## Ce que l'IeC a vérifié

**Le commit.**
- `controle-palier-2.md` est commité tel quel.
- Les quatre unités sont identiques à celles de `95a35ac` : `dd8234f6…`, `52d180b4…`,
  `f7890ec7…`, `fe92cab7…`.
- `git diff --stat eecc9f3 f35d797 -- src` ne touche que `chaine/` et `cli.py`. La condition
  de la question 2 tient donc pour ce commit : le témoin que le premier passage écrira dira
  vrai.
- **`chaine etat`** : le verdict signale maintenant trois cas, chacun avec un test :
  - une vérification en échec, avec son code et son étape ;
  - une vérification de plus de 26 h, ou aucune après 26 h de service ;
  - un échec circonscrit, nommé avec son étape, au lieu de « en panne ».

  La ligne `vérification` donne son âge, et le JSON porte `age_verification_h`.
- **Le README, étape 9** : le dépôt et la bascule avant 9b ; en 9b, le minuteur, puis une
  vérification lancée par beko et relue par l'IeC, et seulement ensuite le complément de la
  collecte.
- **`formats.py`** : le commentaire renvoie au bon test.

**La CI** : run `43732456597`, vert à la troisième tentative.
- **Les tentatives 1 et 2** (15:55 et 16:53 UTC) ont échoué sur la règle A2 de la mission 07.
  Chaque fois, un `POST …/versions` au registre a été coupé sans réponse
  (`RemoteProtocolError`), et le réessai a servi. Les 14 tests d'intégration passaient. L'IeC
  a lu les deux journaux avant chaque relance, et beko a relancé.
- **La tentative 3** est verte de bout en bout. L'étape du palier 2 a tourné contre le bus,
  sur le jeu de démo :
  - deux passages horaires à vide, complets, en 10,2 s et 10,0 s ;
  - les vérifications :
    - `verifier-bus` : code 0 ;
    - `silver verifier` : code 0 ;
    - `index verifier` : conforme, 73 551 points, aucun manquant ni orphelin ;
    - `index etat` : code 0 ;
  - `chaine etat` : `à jour`, aucun écart de formats, la vérification en code 0.
- **Le job sans services** est vert à la première tentative. Les deux tests de la collecte
  HAS qui dépendent du temps (rouges au run de `d543158`) sont passés.

## À surveiller au premier passage sur le VPS

1. **La mémoire de l'étape `index`.** En CI, sur le jeu de démo, un passage à vide fait
   monter l'étape `index` à 481 Mo de résident. `index verifier` y monte à 504 Mo dans son
   sous-processus, contre 404 Mo sur le VPS au remplissage.
   - Le plafond du passage est de 512 Mo pour tout le groupe. Le seuil d'alerte du README
     est de 450 Mo.
   - Le premier passage horaire sur le VPS donne le chiffre qui compte. S'il dépasse 450 Mo,
     ou si un processus est tué, le codeur le signale aussitôt à l'IeC, sans attendre la fin
     de l'observation.
2. **La durée du passage à vide.** Au-delà d'une minute sur le VPS, le codeur propose le
   court-circuit (addendum 1, C).

## Reports pour la mission 11

- **Le registre.**
  - La coupure frappe maintenant :
    - la CI : `13168f5`, puis `f35d797` à deux tentatives sur trois ;
    - le VPS : l'étape `schemas` du remplissage, où le réessai a suffi.
  - Une hypothèse à vérifier : le client (`bus/registre.py`) réutilise ses connexions
    (le réglage par défaut de `httpx`), et le registre en ferme une au moment où un `POST` y
    part.
  - À traiter en premier dans la mission 11, avec la reproduction et le journal du courtier.
- **Les deux tests de la collecte HAS** (`test_un_passage_complet`,
  `test_un_crawl_delay_allonge_la_pause`). Ils remplacent la pause, pas l'horloge
  (`time.monotonic`) : sur une machine lente, la pause calculée tombe sous 1,9 s. Il leur
  faut une horloge simulée.

## La suite

1. **Le codeur** dépose `f35d797` et bascule `courante` sous le verrou (4a). Puis il retire
   `versions/95a35ac…`, qui n'a jamais été en service. `eecc9f3`, la version précédente,
   reste pour un retour en arrière.
2. **Le codeur** cite dans un court rapport de dépôt : la bascule, les droits (les deux
   `find`), `pharmaflux --version`, `VERSION`, et le `diff --stat` de la question 2. Le même
   commit :
   - corrige `ls -l` en `sudo ls -l` dans « Avant 9b, le code » (le compte de beko ne
     traverse pas `/srv/pharmaflux/code`) ;
   - commite ce fichier tel quel.

   Il s'arrête ensuite.
3. **beko** installe les unités depuis `f35d797` (9a), et l'IeC compare les empreintes
   installées. Puis viennent 9b et 9c, dans l'ordre du README.
