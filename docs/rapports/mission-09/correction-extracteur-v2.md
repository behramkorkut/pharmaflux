# Mission 09 — extracteur v2 : la correction des rejets de la première étape

## Synthèse

**Fait** : la correction acceptée par l'IeC sur `3ea9651`, en un commit.
- Le nom JSON-LD se compare après `html.unescape`.
- Tous les numéros d'un libellé d'avis commun sont lus (`&` ou `_`), et chaque dossier BDPM
  de la page doit y être nommé.
- `VERSION_EXTRACTEUR` passe à **2**.
- `has extraire` compte à part les pages dont le contrôle de dossier est impossible. Avec
  `--verifier`, il compare le texte au manifeste quelle que soit la version, et liste à part
  les changements de statut.

**Sur l'archive du Mac**, en lecture : 722 pages, **721 extraites, 1 rejetée** (PEDMARQSI),
0 écart, 0 divergence, **714 empreintes égales** à celles du manifeste, **7 changements de
statut** (rejetée → extraite 7, extraite → rejetée 0), 10 contrôles de dossier impossibles.
C'est l'attendu de l'IeC, au chiffre près.
**Vérifications locales** (commit testé : celui-ci) : vertes, voir le détail.
**Aucune requête vers la HAS**, aucun appel à l'API.
**Écarts** : l'ADR 0013 et la ligne de l'ADR 0004 sont reportés au palier 3, où l'ordre place
l'ADR 0013 (point 5 ci-dessous).

## Ce qui change

| fichier | changement |
|---|---|
| `has/extraction.py` | `VERSION_EXTRACTEUR = 2`, avec la règle de la version en commentaire (elle change avec ce que la fonction rend **ou refuse**) ; `unescape` sur le `name` JSON-LD ; `_DOSSIERS_AVIS` lit tous les numéros ; la règle « chaque dossier BDPM est nommé par le document d'avis, s'il en nomme » ; `empreinte(version)` recalcule l'empreinte sous une version consignée (forme canonique inchangée depuis la v1) |
| `has/inspection.py` | `rejet_consigne` lu du manifeste ; le bilan compte `contrôle de dossier impossible` et liste les pages ; `--verifier` compte les empreintes égales au manifeste quelle que soit la version, liste les changements de statut d'une version à l'autre et tient pour divergence un statut ou un texte qui change à version égale ; `controle_dossier` dans chaque ligne de `--sortie` |
| `tests/fixtures/has/` | quatre pages copiées à l'octet de l'archive du Mac (KEPPRA, NIMENRIX, NICORANDIL, PEDMARQSI), sha256 égal à celui du manifeste ; README avec leur heure de réception et la mention de la HAS ; les deux extractions de référence passent en v2 (seuls `extracteur` et `empreinte` changent) |
| `tests/test_has_extraction.py` | +9 tests : nom à entité accepté et nom différent refusé ; avis communs `&` et `_` qui confirment chacun de leurs dossiers ; faux rattachement refusé, y compris un dossier nommé accompagné d'un dossier qui ne l'est pas ; PEDMARQSI rejetée avec son message ; document sans numéro accepté ; empreinte v1 retrouvée sous `empreinte(1)` ; sha256 des quatre pages |
| `tests/test_has_collecte.py` | +2 tests : un manifeste v1 relu en v2 (texte égal, statut changé listé, code 0) ; un texte ou un statut qui change à version égale diverge (code 1) |

## La sortie sur l'archive du Mac

Commande, en lecture : l'archive n'est pas écrite, seule la sortie va dans `data/`.

```bash
/usr/bin/time -l uv run pharmaflux has extraire --verifier --racine ~/pharmaflux-data --sortie data/has-extraits-v2.jsonl
```

```text
722 page(s) : 721 extraite(s), 1 rejetée(s) (dossier_incoherent 1) ; extracteur v2
contrôle de dossier impossible : 10 (le document d'avis ne porte aucun numéro de dossier lisible)
  sans contrôle de dossier : p_3534726 (CT-20796)
  sans contrôle de dossier : p_3639721 (CT-21304)
  sans contrôle de dossier : p_3741668 (CT-20568)
  sans contrôle de dossier : p_3861350 (CT-21525)
  sans contrôle de dossier : p_3861356 (CT-21493)
  sans contrôle de dossier : p_3861364 (CT-21464)
  sans contrôle de dossier : p_3861367 (CT-21475)
  sans contrôle de dossier : p_3861373 (CT-21473)
  sans contrôle de dossier : p_3861376 (CT-21472)
  sans contrôle de dossier : p_3861379 (CT-21528)
non-altération : 721 conforme(s), 0 avec écart ; déterminisme et empreintes du manifeste : 0 divergence(s)
empreintes du texte égales à celles du manifeste : 714
statut changé depuis la version du manifeste : 7 (rejetée → extraite 7, extraite → rejetée 0)
  statut changé : p_3530986 : rejetée (dossier_incoherent) en v1 → extraite en v2
  statut changé : p_3638197 : rejetée (nom_incoherent) en v1 → extraite en v2
  statut changé : p_3686928 : rejetée (dossier_incoherent) en v1 → extraite en v2
  statut changé : p_3686931 : rejetée (dossier_incoherent) en v1 → extraite en v2
  statut changé : p_3686943 : rejetée (dossier_incoherent) en v1 → extraite en v2
  statut changé : p_3687274 : rejetée (dossier_incoherent) en v1 → extraite en v2
  statut changé : p_3892357 : rejetée (nom_incoherent) en v1 → extraite en v2
```

Code de sortie 0 ; 8,35 s réelles, 48 Mo de résident maximal. Le rejet qui reste, tel que
`--sortie` le rend : `p_3608587`, `dossier_incoherent`, « le document d'avis nomme CT-21123,
pas CT-21223 ». La ligne « extraite → rejetée 0 » s'affiche même à zéro, pour que l'absence se
lise.

## Les points de la réponse de l'IeC

1. **Correction (1)+(2)** : appliquée telle qu'acceptée. Elle ferme aussi le trou NICORANDIL :
   les cinq pages sont désormais contrôlées et confirmées.
2. **Les 10 pages sans numéro lisible** : acceptées, comptées et listées par `has extraire`.
   L'état de l'index les comptera de même au palier 2. Les 19 faux rattachements possibles
   par avis commun iront dans l'ADR 0013.
3. **Version 2** : faite, avec les trois garanties demandées : texte comparé quelle que soit la
   version, changements de statut listés, index pas encore construit.
4. **Fixtures** : les quatre pages, la mention de la HAS dans le README, un test par cas.
5. **La clause « Liens hypertextes »** : l'ordre place l'ADR 0013 au palier 3. La ligne
   « complété par ADR 0013 » dans l'ADR 0004 renverrait d'ici là à un fichier qui n'existe
   pas. Je fais donc les deux ensemble au palier 3, avec les trois lectures que tu as fixées :
   - la CLI rend un lien en texte, n'inclut aucune page ;
   - `demo/` et les fixtures relèvent de la clause de reproduction (intégralité, date, mention) ;
   - l'interface de la mission 10 ouvre le lien dans une nouvelle fenêtre, jamais dans un cadre.

   Le palier 2 respecte déjà la première : les liens de l'assistant sont rendus en texte par
   le code.
6. **Code de sortie** : la ligne zsh est au §1 de `collecte-premiere-etape.md`. Elle suivra
   toute commande de collecte donnée à beko.
7. **Le refus de `shasum`** : noté par l'IeC comme faux positif, rien à faire de mon côté.

## Vérifications locales

Commit testé : celui de cette correction, arbre propre en dehors de `data/` (non suivi).

| vérification | résultat |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 310 fichiers déjà formatés |
| `uv run mypy src` | 86 fichiers, aucune erreur |
| `uv run pytest -q` | 821 passés (810 + 11), 6 min 17 s, code 0 |
| tests HAS seuls (`test_has_extraction`, `test_has_collecte`, `test_reseau`) | 86 passés, garde réseau active |
| `has extraire --verifier` sur l'archive du Mac | ci-dessus, code 0 |
