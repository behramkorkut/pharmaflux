# Mission 01 — palier 1 : reliquats (décisions 1, 9, 10, 11)

**Fait**

- **Décision 1**, `src/pharmaflux/bronze.py` : `lister(racine, source, fichier)`
  rend les `Archive` d'un fichier source dans l'ordre chronologique (horodatage
  UTC lu dans le nom, puis nom complet) ; `Archive.lire()` donne les octets
  bruts décompressés, `relatif()` le chemin tel que le manifeste l'écrit ;
  `derniere()` ; `fichiers_partiels(racine)` liste les `.<nom>.partiel-<pid>`.
  Tout nom qui commence par un point est ignoré (`.partiel-*`,
  `.rsync-partiel/`, `.DS_Store`) ; un fichier visible qui n'a pas la forme
  d'une archive lève `NomArchiveInvalide` (erreur franche, pas un silence).
  `lire_archive` quitte `collecte/archive.py`, qui n'écrit plus que.
- **Décision 9**, `passage.py` : une exception autre qu'`AnalyseImpossible`
  levée par l'empreinte de comparaison donne `empreinte_impossible: <type>:
  <message>`, l'archive est écrite, l'empreinte retombe sur le sha256 (pas de
  réarchivage au passage suivant), la trace est dans le journal. Les lignes
  `lien_nouveau` passent par `_consigner_liens_nouveaux`, sous le filet : si
  la recherche casse, une ligne en erreur est consignée pour la page, et le
  résumé comme le code de sortie sont conservés. **Documentation PDF** :
  `Entree.lien_page` porte le préfixe du nom (`Contenu_et_format_…_BDM`) ;
  à chaque passage, `_suivre_lien_page` prend dans la page le lien qui porte
  ce préfixe si l'URL connue n'y est plus ; un `_v6.pdf` est téléchargé à
  son URL, archivé sous `bronze/bdpm/<nom v6>/`, consigné sous l'identifiant
  `bdpm.documentation_formats` avec `fichier` et `url` de la page, et la ligne
  est en erreur `lien_change: <v6> (catalogue : <v5>)` jusqu'à la mise à
  jour du catalogue ; il n'est pas un `lien_nouveau` à chaque passage horaire.
  Sans lien au préfixe : repli sur l'URL du catalogue, `lien_absent`. Un
  `.pdf` inconnu de la page est désormais un `lien_nouveau` (`est_suivi`).
  Journal `logging` en UTC (`FormateurUTC` : `2026-10-24T14:17:03Z INFO …`).
- **Décision 10**, `etat` : `calculer_etat` prend un itérable et rend un
  `Etat` (lignes, nombre d'enregistrements, dernier passage) ; `cli etat`
  parcourt le manifeste en flux (`manifeste.parcourir`), affiche une colonne
  `identifiant` (`— (bdpm)` pour un lien nouveau) et, sous le tableau, les
  fichiers partiels de `bronze/` avec leur date de modification UTC, via la
  décision 1.
- **Décision 11**, `pharmaflux-collecte.service`, chaque directive justifiée
  d'une ligne : `CapabilityBoundingSet=`, `AmbientCapabilities=`,
  `SystemCallFilter=@system-service` puis `~@privileged @resources`,
  `SystemCallErrorNumber=EPERM`, `SystemCallArchitectures=native`,
  `RestrictNamespaces`, `ProtectKernelLogs`, `ProtectClock`,
  `ProtectHostname`, `ProtectProc=invisible`, `ProcSubset=pid`,
  `MemoryDenyWriteExecute` (à retirer si le passage manuel échoue),
  `RemoveIPC`, `UMask=0027`. Pas d'`OnFailure=`, pas d'`IPAddressDeny`.
  README : cible « sous 3 », conduite à tenir si le passage manuel échoue,
  variante « déployer une branche de mission » à l'étape 7 (c'est la
  procédure pour ce palier), étape 6 et rubrique Sécurité à jour.
- Tests : 14 ajoutés (80), tous sur fixtures, dont un par reliquat demandé :
  exception de l'empreinte, liens nouveaux sous le filet, lien du PDF qui
  change (et absent, et deux versions à la fois), orphelins `.partiel-*`,
  `.rsync-partiel/` ignoré, journal UTC.

**Vérifications locales** (arbre committé comme fils de `695cdfc`)

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 54 files already formatted |
| `uv run mypy src` | Success: no issues found in 12 source files |
| `uv run pytest -q` | 80 passed |
| `sh infra/git-hooks/test-crochets.sh` | crochets git : tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | Ran 16 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` ; `sh -n` | rien à signaler |
| unité systemd | relue contre `systemd.exec(5)` ; mesure par beko sur le VPS (étape 7 du README, variante branche) |

**Écarts à l'ordre**

1. `UMask=0027` et non le `0077` que je proposais au §0 : avec `0077`,
   l'archive et le manifeste ne seraient plus lisibles par le groupe
   `pharmaflux`, donc par le compte SSH qui rapatrie la copie (étapes 2 et
   8 du README).
2. Un changement de version du PDF n'est pas consigné comme `lien_nouveau`
   (ligne sans identifiant) mais comme une ligne en erreur `lien_change` de
   l'entrée elle-même, archivée tout de suite sous son nouveau nom : l'alerte
   est aussi visible (code de sortie 1, colonne « dernière erreur » de
   `etat`), l'archive est prise sans attendre une mise à jour du code, et la
   ligne reste rattachée à `bdpm.documentation_formats`. Tant que le
   catalogue n'est pas mis à jour, l'entrée en erreur est recollectée à
   chaque passage (règle de la mission 00 : une erreur ne vaut pas collecte
   du jour), soit 300 Ko par heure, sans réarchivage.
3. `PrivateUsers=true` n'est pas posé : non proposé au §0, non testé ici ;
   c'est la réserve si le score mesuré reste à 3 ou plus.

**Questions pour l'IeC** : l'écart 2 te convient-il, ou veux-tu une ligne
`lien_nouveau` en plus de la collecte ?

**Propositions d'évolution** (PRD, consignes) : aucune.

**Pour beko** (après ce commit, entre deux passages) : étape 7 du README,
variante « déployer une branche de mission », puis relever le passage manuel
(`0 erreur(s)`, entrées `inchangé`), `Mem peak` et le score
`systemd-analyze security … | tail -1`. Si le passage échoue, la ligne du
journal suffit ; je retire la directive en cause par un nouveau commit.
