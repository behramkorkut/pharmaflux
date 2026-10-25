# Mission 00 — palier 2 : collecteur

**Fait** : décisions 3 à 7 et addendum 2. `src/pharmaflux/collecte/` :
`catalogue.py` (13 entrées : page, 11 fichiers BDPM, métadonnées Open Medic
quotidiennes ; cadence et mode d'empreinte par entrée), `page.py`
(analyseur HTML de la bibliothèque standard : lien, date et taille lus dans
le même `<a>`), `empreintes.py` (sha256 brut + empreinte de comparaison :
octets, lignes triées, couples de la page, projection data.gouv),
`telechargement.py` (httpx, 60 s, 3 essais : connexion → relance immédiate
puis 2 s, 4 s ; 5xx → 2 s, 4 s d'emblée ; 4xx sans relance ; `User-Agent:
pharmaflux/0.1.0 (+https://github.com/behramkorkut/pharmaflux)`),
`archive.py` (temporaire + `os.link`, refus si le chemin existe, aucun
partiel visible), `manifeste.py` (JSONL ajout seul, `fsync`), `passage.py`
(série, pause 2 s, une erreur n'arrête pas les autres, code de sortie 1 si
erreur, `lien_absent` / `lien_nouveau`), `etat.py`. CLI : `collecte
[--source …] [--racine …]`, `etat [--racine …]`, `catalogue`.
45 tests sans réseau (`httpx.MockTransport` sur `tests/fixtures/`, extraits
réels documentés dans `tests/fixtures/README.md`) : premier passage,
inchangé, octets différents à fond identique (ordre, `nonce`, robot
data.gouv), changement réel, 304, erreur réseau puis succès, erreur
définitive, archive existante, écriture interrompue, lien absent/nouveau,
page illisible, cadence quotidienne, manifeste complet. `extend-exclude`
retiré de `pyproject.toml` : les fichiers de l'IeC passent ruff.

**Requête supplémentaire sur `CIS_InfoImportantes.txt`** (14:37:16 UTC, 76 min
après la première) : fichier **identique à l'octet près** (10 905 lignes,
4 510 790 octets, même sha256 `a27b30e12c83…`, même ordre des lignes) ; seul
le nom `Content-Disposition` change (`…_20261024143716_bdpm.txt`). L'ordre
n'est donc pas instable entre deux générations espacées d'une heure.
L'empreinte sur lignes triées reste en place (coût nul, filet si l'ordre
bouge un jour) ; les 24 premières heures sur le VPS le confirmeront.

**Vérifications locales** (arbre committé comme fils de `e8b331a`)

| commande | résultat |
|---|---|
| `uv run ruff check .` | All checks passed (sans `extend-exclude`) |
| `uv run ruff format --check .` | 36 files already formatted |
| `uv run mypy src` | Success: no issues found in 11 source files |
| `uv run pytest -q` | 45 passed |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 15 tests, OK |
| `shellcheck` | pas encore de script (palier 3) |

**Écarts à l'ordre et interprétations** :

1. **Douzième lien sur la page** : la documentation PDF du format
   (`Contenu_et_format_des_fichiers_telechargeables_dans_la_BDM_v5.pdf`),
   même classe CSS que les fichiers. Elle entre dans l'empreinte de la page
   (un passage en v6 archivera la page) mais pas dans le contrôle
   `lien_nouveau`, réservé aux liens `.txt` : sinon chaque passage serait en
   erreur.
2. **`lien_absent`** : le fichier est quand même téléchargé et archivé s'il
   est nouveau ; la ligne est en `erreur` (motif `lien_absent`) pour
   alerter. Choix : l'archive est irremplaçable, l'alerte suffit.
3. **Manifeste** : champ `identifiant` ajouté (clé du catalogue ; `null`
   pour un `lien_nouveau`) ; `chemin_archive` **relatif à la racine** pour
   que la copie rapatriée sur le Mac reste lisible ; `version_collecteur` =
   `0.1.0+<commit court>` via `git rev-parse` (version seule hors dépôt).
4. **Cadence quotidienne** : quand Open Medic a déjà été collecté le jour
   même (UTC), le passage ne le télécharge pas et **n'écrit pas de ligne**
   (23 lignes « différé » par jour n'apporteraient rien aux mesures) ; une
   ligne en `erreur` ne compte pas comme collecte du jour.
5. **`etat`, « dernier changement »** : dernier `nouveau` qui n'est pas la
   première observation du fichier ; colonne « date source » à côté
   (`date_source_affichee`).
6. **Forme inattendue** (page sans lien, JSON invalide) : archivé quand
   même, ligne en `erreur` motif `analyse_impossible`.
7. Commande `catalogue` ajoutée (liste les 13 entrées) ; `tests/` devient un
   paquet (`tests/__init__.py`) pour partager `conftest.py` ; 304 géré bien
   que la BDPM ne puisse pas l'envoyer.

**Questions pour l'IeC** : les interprétations 1, 2 et 4 te conviennent-elles ?

**Propositions d'évolution** : (a) une 14e entrée
`bdpm.documentation_formats` (le PDF du format, archivé sur changement
d'octets) : c'est le signal d'un changement de schéma, utile à la mission
01 ; (b) PRD annexe A : mentionner ce PDF et sa version.
