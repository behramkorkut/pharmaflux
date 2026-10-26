# Mission 02 — réponse au contrôle du palier 2

Contrôle : `docs/relectures/mission-02/controle-palier-2.md` (commit
`bc90ef2`, committé tel quel). Les deux correctifs sont dans le commit qui
suit, tests compris. Aucun autre fichier touché.

## Correctifs

1. **Rien ne dépend de l'ordre d'un objet JSON** : corrigé. Choix retenu :
   `cle`, `avant` et `apres` restent des objets colonne → valeur, et tout ce
   qui en dérive prend les colonnes dans **l'ordre alphabétique de leur
   nom**, qui est aussi celui que `serialiser` écrit (clés triées à tous
   les niveaux) : `valeurs_de_cle(cle)` sert à `identite_de_ligne` et à
   `cle_de_tri` ; `appliquer` et `etat_du_snapshot` comparent des
   dictionnaires colonne → valeur, sans égard à l'ordre. Ni liste pour
   `cle`, ni champ des noms de colonnes : un consommateur qui veut l'ordre
   du fichier le trouve dans le contrat que `entite` et `version_contrat`
   désignent. Conséquence visible : l'identifiant d'un événement à clé
   composée est calculé sur les valeurs dans l'ordre alphabétique des
   colonnes (pas celui du contrat) ; les identifiants de palier 2 n'ont
   été écrits nulle part. Dit dans la docstring de `schema.py`, et sera
   dans l'ADR 0006 au palier 3 (section « identifiant »), comme demandé.
   Test `test_aller_retour_json_sur_une_cle_a_plusieurs_colonnes` sur les
   40 lignes réelles de `CIS_COMPO_bdpm.txt` (clé à cinq colonnes, ordre du
   contrat différent de l'alphabétique) : événements relus égaux aux
   écrits, identifiant recalculé égal à `id`, `cle_de_tri` égal et tri
   identique après mélange, `appliquer` sur les relus égal à
   `etat_du_snapshot`, sérialisation identique.
2. **`deserialiser` strict** : corrigé. `_booleen` exige un `bool`,
   `_entier` un `int` qui n'est pas un `bool`, comme `_texte` pour les
   chaînes. Test paramétré : `"false"` et `1` pour `etat_initial`, `"1"`,
   `1.0`, `true`, `2.7` pour `rang`, et un `id` non chaîne, tous refusés
   (`EvenementInvalide`, « mal formé »).

## Écarts et proposition

Les trois écarts sont acceptés. Le test de `Suivi` avec `seuil=0.10`,
facultatif, sera fait au palier 3 s'il tient en quelques lignes.

## Vérifications rejouées (arbre committé comme fils de `bc90ef2`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 115 files already formatted |
| `uv run mypy src` | Success: no issues found in 29 source files |
| `uv run pytest -q` | 376 passed (+8) |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK |
| shellcheck | non lancé, aucun `.sh` touché |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` ; `questions verifier` | 11 fichiers, 0 bloquante ; 25 / 5 / 10 |

Pas de nouvelle question. J'attends l'accord de l'IeC pour le palier 3.
