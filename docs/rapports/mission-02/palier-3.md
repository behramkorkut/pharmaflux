# Mission 02 — palier 3 : chaîne, rejeu et reprise, démonstration, docs (décisions 7 à 10)

**Fait**

- **Décision 7, `evenements/rejeu.py` et `pharmaflux evenements [--fichier …]
  [--racine …] [--sortie …] [--reprendre]`** (défaut de sortie
  `data/evenements/`, hors git ; refusé sous la racine de l'archive, qui ne
  s'écrit pas). Par fichier, les archives dans l'ordre du bronze passent par
  `volume.Suivi` ; chaque archive lue laisse `evenements/<entite>/<horodatage>__<sha12>.jsonl`
  quand elle est retenue ou confirmée (vide si rien n'a changé),
  `bilans/<entite>/<même nom>.json` toujours, puis `etat.json`, dans cet
  ordre, chaque fichier écrit entier puis renommé. Le flux d'une source est
  la concaténation de ses fichiers dans l'ordre des noms
  (`rejeu.lire_evenements`). L'état garde par entité la version du contrat,
  la dernière archive traitée, le dernier retenu et l'archive en attente,
  par leurs chemins : les snapshots ne sont **jamais sérialisés**, la
  reprise les recalcule depuis le bronze. Le manifeste est lu une fois en
  flux : `date_source_affichee` par archive, et les passages `inchange` qui
  confirment une archive en attente entre son archivage et l'archive
  suivante. **Une archive en attente n'est pas traitée** : l'état reste
  avant elle ; quand elle est tranchée, son bilan est réécrit et ses
  événements écrits si elle est confirmée (F.2), y compris à la fin du
  bronze par un `inchange`. Un rejeu complet repart de zéro pour l'entité.
  `--reprendre` **refuse** (code 2, message « le contrat X est passé de v0 à
  v1 : relance sans --reprendre ») quand une version de contrat diffère de
  l'état, quand l'état est illisible ou quand une archive de l'état a
  disparu du bronze ; sans `etat.json`, la reprise est un rejeu complet.
  Code 1 si une archive est illisible (le fichier s'arrête là, les autres
  continuent) ; un snapshot écarté ne change pas le code. Résumé par
  fichier dans le terminal : archives lues, retenues, écartées, en attente,
  événements par type.
- **Décision 8, `tests/test_rejeu.py`** sur un bronze de synthèse dans
  `tmp_path` (archives fabriquées du palier 2, manifeste aux horodatages
  fixés, quinze collectes dont un passage inchangé) : deux rejeux complets
  identiques à l'octet, y compris par-dessus une sortie existante ;
  **reprise après chacun des treize points d'arrêt** (bronze tronqué,
  rejeu complet, puis le reste avec `--reprendre`), dont le point juste
  après une archive en attente tranchée dans chacun des deux sens et une
  archive en attente à la fin du bronze ; `etat.json` supprimé puis
  `--reprendre` ; reprise sans rien de nouveau ; aucun identifiant en
  double ; `appliquer` sur la sortie **relue depuis le disque** égal à
  `etat_du_snapshot` du dernier retenu ; refus de `--reprendre` (version,
  état illisible) ; archive illisible ; la commande (sélection,
  `--reprendre`, sortie sous la racine refusée) ; un fichier étranger à la
  sortie ne survit pas à un rejeu complet. La disponibilité y finit **en
  attente** (B perd une ligne sur sept) : l'état la porte. Test facultatif
  du contrôle : `Suivi(seuil=0.6)` retient une suppression.
- **Décision 10** : ADR 0006 (schéma, ordre alphabétique des colonnes pour
  l'identifiant et le tri, identifiant, comparaison ligne à ligne,
  garde-fou, premier snapshot, sortie et reprise, exactitude),
  `docs/CONTEXTE.md` (section « Du bronze aux événements », ligne des
  contrats v0/v1, table des chemins), `docs/journal.md` (une entrée en fin
  de fichier pour la mission), `README.md` (état, commande, paragraphe).
- **Tests** : 376 → **399** (+23).

**Décision 9, démonstration** (copie du Mac, lecture seule : `ls ~/pharmaflux-data`
donne toujours `bronze` et `manifeste` seuls ; sortie dans le dossier
temporaire de session ; `/usr/bin/time -l`) :

| mesure | résultat |
|---|---|
| rejeu complet des onze fichiers (20 archives) | **7,9 s**, mémoire résidente de pointe **474 Mo**, 172 Mo d'événements, 60 Ko de bilans |
| `--reprendre` juste après | 0 archive lue, 2,9 s, 124 Mo (les onze snapshots retenus recalculés) |
| `creee` initiales, par fichier (événements, Ko) | compositions 32 439 (33 712) ; conditions_prescription 28 532 (23 652) ; presentations 20 898 (24 892) ; specialites 15 883 (18 796) ; smr 15 547 (17 484) ; infos_importantes 10 905 (17 564) ; generiques 10 737 (9 908) ; liens_ct 10 480 (8 884) ; asmr 10 117 (13 088) ; mitm 7 855 (7 740) ; disponibilite 703 (876) ; **total 164 096** |
| `CIS_CIP_bdpm.txt`, 24/10 23:17 (dernier retenu 19:41) | retenu, **2 `supprimee`** : CIP13 3400938844948 (CIS 63830632, « plaquette(s) aluminium de 30 comprimé(s) », « Déclaration d'arrêt de commercialisation », déclarée le 2021-10-25) et 3400949939374 (CIS 66317873, « plaquette(s) thermoformée(s) PVC aluminium de 28 comprimé(s) », même état, même date) ; `date_source` 2026-10-24, `date_observation` 2026-10-24T23:17:12Z |
| `CIS_CIP_bdpm.txt`, 26/10 00:17 | retenu, **1 `supprimee`** : 3400930151181 (CIS 69161828, flacon PEHD de 16 g, arrêt de commercialisation déclaré le 2021-10-26) ; `date_source` 2026-10-26 |
| `CIS_InfoImportantes.txt`, 26/10 14:17 (0 octet) | **écarté**, « vide : aucune ligne bien formée », écart −10 905 lignes consigné, aucun fichier d'événements |
| `CIS_InfoImportantes.txt`, 26/10 15:17 | retenu, « identique au dernier retenu (…24/10 19:42…) », fichier d'événements **vide**, écart 0 |
| prix normalisés grâce à `milliers` (état initial des présentations) | **995** valeurs ≥ 1 000 € écrites en `1003.48` (497 prix, 498 prix publics) |
| total | 164 099 événements ; 1 archive écartée, 0 en attente |

Les `modifiee`, les doublons et les retours ne sont pas dans l'archive
réelle : ils viennent des fixtures (palier 2 et `test_rejeu.py`).

**Vérifications locales** (arbre committé comme fils de `fd0d1ab`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 120 files already formatted |
| `uv run mypy src` | Success: no issues found in 30 source files |
| `uv run pytest -q` | 399 passed |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | OK |
| shellcheck | non lancé : aucun `.sh` touché |
| `uv run pharmaflux profil --racine ~/pharmaflux-data` ; `questions verifier` | 11 fichiers, 0 bloquante ; 25 / 5 / 10 |
| `uv run pharmaflux evenements --racine ~/pharmaflux-data --sortie <jetable>` puis `--reprendre` | ci-dessus |

**Écarts à l'ordre**

1. **Mémoire de pointe 474 Mo** en rejeu complet : les événements d'une
   comparaison sont construits en mémoire avant l'écriture (32 439 pour les
   compositions), plus les deux snapshots. C'est au-dessus des 256 Mo de
   l'unité systemd du VPS, où cette chaîne n'a pas à tourner dans cette
   mission ; noté dans l'ADR 0006 pour la mission 03 (écriture en flux).
2. Un `inchange` ne confirme une archive en attente que dans la fenêtre
   entre son archivage et l'archive suivante (au-delà, il compare à
   l'archive suivante) : précision de la règle F.3, dite dans l'ADR 0006.
3. `rejeu complet` supprime d'abord la sortie de l'entité
   (`evenements/<entite>/`, `bilans/<entite>/`) : sans cela, un fichier
   d'une exécution antérieure survivrait et deux rejeux ne seraient plus
   identiques à l'octet. Dit dans l'aide de la commande et l'ADR.

**Questions pour l'IeC** : aucune.

**Propositions d'évolution** (PRD, consignes) : pour le PRD §6.3, préciser
que l'identité d'une ligne sans clé unique est l'empreinte de la ligne
normalisée plus un rang, et que l'ordre des colonnes dans un événement est
alphabétique (ADR 0006).
