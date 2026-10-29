# Mission 07 — réponse à la relecture 1

Relecture 1 (`041b4d1`) : CONFORME, 0 bloquant. Les trois points non bloquants
sont corrigés, ainsi que quatre des remarques. Le fichier de la relecture est
commité tel quel.

## À corriger

1. **La collection orpheline après une coupure entre l'alias et l'état** —
   corrigé (`construction.construire`). Avant de construire, la commande lit
   l'état (sans exiger qu'il s'accorde avec l'alias). Après la bascule, elle
   efface la collection de l'ancien alias **et** celle que l'ancien état
   décrivait, sauf la nouvelle. Le test de la coupure
   (`test_une_coupure_entre_l_alias_et_l_etat_fait_refuser_la_lecture`)
   vérifie maintenant qu'il ne reste que l'état et la collection de l'alias.

2. **Un index réduit ne se reconnaissait pas** — corrigé :
   - `construire --cis` écrit les CIS dans l'état (`cis_reduits`), et
     `fiches` y compte les seules fiches de l'index ;
   - `index etat` affiche « réduit à N CIS » ;
   - `index etat --complet` sort en code 2 pour un index réduit, et
     `make index` s'en sert : un index réduit est reconstruit en entier ;
   - `mettre-a-jour` refuse un index réduit (code 2), avec le message ;
   - `verifier` compare un index réduit à la reconstruction de ses seuls
     CIS. La CI vérifie donc maintenant aussi son index réduit au vrai
     modèle.

   Test : `test_un_index_reduit_se_declare_et_ne_se_met_pas_a_jour`. Un état
   écrit avant ce changement n'a pas la clé, et se lit comme un index
   complet : vérifié sur l'index du Mac, `etat --complet` rend 0.

3. **`index verifier` sans verrou** — corrigé : il prend le verrou comme
   `construire` et `mettre-a-jour` (code 2 s'il est tenu). Test :
   `test_verifier_prend_le_verrou`. Sur l'index du Mac : conforme, 424 Mo.

## Remarques

- **La perte du cache des vecteurs** : faite.
  - `verifier` ajoute une ligne quand des vecteurs sont absents du cache :
    la cause probable, et la seule sortie, `index construire`, qui réencode
    tout.
  - L'ADR 0011 et `infra/index/README.md` le disent aussi.
- **Le double compte de `vecteurs_differents`** : fait. Un identifiant n'y
  entre plus qu'une fois ; le test vérifie la liste exacte.
- **`Qdrant.supprimer`** : sa docstring dit que seuls les tests d'intégration
  s'en servent, la mise à jour retirant par identifiants.
- **`FORMAT`** : le commentaire est passé au-dessus de la ligne.
- **README** : la section « L'index » cite la clôture (411 et 416 Mo,
  18 minutes).
- **Le healthcheck du registre** (une lecture) : rien à changer dans cette
  mission, comme le note la relecture. L'étape « Schémas » de la CI reste la
  preuve qu'une écriture passe, et le réessai strict en test signalerait un
  retour de la coupure.
- **Les nombres en dur des tests de prudence** : voulu. Ce sont aussi des
  tests de non-régression du jeu figé (`demo/`).

## Vérifications (commit testé : celui de cette réponse)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 262 files already formatted |
| `uv run mypy src` | Success: no issues found in 67 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **601 passed** en 261 s (599 avant), Qdrant, courtier et modèle présents |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | tout est conforme / OK |
| YAML de `ci.yml` (`ruby -ryaml`) | lu sans erreur |
| `make -n index` | `index etat --complet` dans le test de la recette |
| `index etat --complet` ; `index verifier` (index du Mac) | code 0 ; conforme, cosinus minimal 0,9954, 424 et 423 Mo |
