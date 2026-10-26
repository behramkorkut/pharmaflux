# Mission 01 — palier 2 : contrats de schéma et vérification (décisions 2, 3)

**Fait**

- **Décision 2**, `src/pharmaflux/contrats/` : onze contrats TOML v0 dans
  `bdpm/<identifiant>.toml` (`specialites.toml`… `mitm.toml`), un par fichier
  TSV du catalogue, `version = "v0"` dans le fichier. Chacun porte `source`
  (documentation v5 et son sha256 `db10d5a6…`, section du PDF, date de
  vérification, archive de référence du 24/10 avec son sha256), `format`
  (encodage, fin de ligne, séparateur, `retour_final`, `lignes_vides`), les
  colonnes dans l'ordre (nom `snake_case`, type parmi les neuf du §0 C avec
  ses paramètres, `obligatoire`, description qui cite les constats du 24/10),
  `cle` (`unique`, `raison` obligatoire si faux : SMR, ASMR, Dispo_Spec) et
  `liens` (mesure des correspondances au palier 3, jamais une anomalie).
  `modele.py` : dataclasses figées, `TypeNom`, `Regle`, `REGLES_BLOQUANTES`,
  `Anomalie`. `chargeur.py` : `tomllib`, toute clé inconnue ou sans objet pour
  le type refusée avec le fichier, la table et la clé en cause (`ContratInvalide`),
  `charger_identifiant("bdpm.specialites")`, `charger_tous()` qui vérifie en
  plus que chaque lien vise un contrat chargé et une de ses colonnes.
- **Décision 3**, `verification.py` : `verifier(contrat, octets)` rend une
  `Lecture` (lignes bien formées en chaînes, compte des lignes, anomalies
  triées par ligne, `bloquantes`, `par_regle()`). Dans l'ordre : décodage
  strict (BOM, octet illisible avec son numéro de ligne, lecture poursuivie
  par substitution), fin de ligne par ligne, retour final, lignes vides,
  nombre de colonnes, type de chaque valeur, obligatoires, clé déclarée
  unique, lignes entières en doublon. Rien n'est corrigé : la valeur brute
  est rendue, tronquée à 80 caractères. Bloquantes : les quatre de
  l'addendum ; `valeur_inconnue` et le reste ne bloquent pas.
- **Fixtures** (H.3) : les dix fichiers TSV ont reçu des lignes réelles
  choisies dans l'archive du 24/10 (numéros de ligne et archives dans
  `tests/fixtures/README.md` ; `CIS_MITM.txt` finit désormais sans retour à
  la ligne, comme l'archive). Six fichiers fabriqués dans
  `tests/fixtures/contrats/`, chacun décrit ligne par ligne dans le README,
  couvrent les dix-neuf règles. Tests : chaque fixture réelle passe son
  contrat **sans anomalie bloquante** et avec exactement les anomalies
  connues attendues ; 28 contrats mal formés refusés ; 40 cas de
  `verifier_valeur`. **Roue** : `uv build --wheel` (dans le dossier
  temporaire de session) embarque les onze `.toml` sous
  `pharmaflux/contrats/bdpm/` ; le test qui charge les onze contrats passe
  par `importlib.resources`.
- **Sur l'archive réelle du 24/10** (lecture seule, les onze archives de
  référence, `pharmaflux.contrats.verification` lancé depuis un
  interpréteur) : **0 anomalie bloquante**, 0,2 s au plus par fichier. Non
  bloquantes : `CIS_bdpm.txt` 17 016 `espace_parasite` (15 883 titulaires,
  1 133 formes) et 1 `code_illisible` (`EU/1/17/1235/`, barre finale) ;
  `CIS_CIP_bdpm.txt` 995 `decimal_illisible` (497 prix + 498 prix publics),
  52 `date_hors_plage` (51 de 1910 à 1949, une en 2924), 3 espaces ;
  `CIS_COMPO_bdpm.txt` 1 309 espaces de fin ; `CIS_CPD_bdpm.txt` 3
  `ligne_vide` et 3 espaces (un `\r` de plus en fin de valeur juste avant
  chaque ligne vide) ; `CIS_CIP_Dispo_Spec.txt` 5 `ligne_dupliquee`. Les
  six autres : aucune. Ces comptes sont ceux du §0 ; `pharmaflux profil`
  les reproduira au palier 3 avec les archives et sha256 en tête.

**Réponse au C1 du contrôle du palier 1** (commit `ee50cdc`, à part) : les
motifs d'erreur sont définis une seule fois dans `manifeste.py` (`MOTIF_*`,
`SEPARATEUR_MOTIFS`) avec la liste fermée `MOTIFS_SIGNALEMENT = {lien_absent,
lien_change}` ; `Enregistrement.vaut_collecte` est vrai pour une ligne sans
erreur, ou en erreur quand son empreinte de comparaison est connue et que
tous ses motifs sont des signalements ; `etat_connu` s'en sert pour
`collectes_du_jour`. Une erreur de téléchargement, d'analyse, d'écriture ou
le filet `inattendue` ne vaut toujours pas collecte (`HTTP 404 ; lien_change`
repasse). Test demandé : deux passages le même jour avec un `_v6.pdf`
téléchargent le PDF une fois, la documentation est sautée au second passage
comme toute quotidienne déjà collectée (pas de ligne, journal « déjà
collectée aujourd'hui »), l'alerte reste visible dans `etat`, et le
lendemain elle repasse sans réarchiver ; même chose pour un `lien_absent`
quotidien. Conséquence à connaître : le code de sortie 1 (et le `failed` de
l'unité) n'apparaît que sur le passage qui archive le changement, une fois
par jour, tant que le catalogue n'est pas mis à jour ; les entrées horaires
(`CIS_MITM.txt` absent de la page) continuent de le signaler à chaque
passage, comme avant.

**Vérifications locales** (commit testé : celui de ce palier, arbre propre)

| commande | résultat |
|---|---|
| `uv run ruff check .` et `ruff format --check .` | ok (62 fichiers) |
| `uv run mypy src` | ok, 16 fichiers |
| `uv run pytest -q` | **190 passed** (80 + 16 pour C1 + 94 pour les contrats) |
| `sh infra/git-hooks/test-crochets.sh` | tout est conforme |
| `python3 infra/agents/test_garde_fou.py` | 16 tests, OK |
| `uvx --from shellcheck-py==0.11.0.1 shellcheck infra/planification/*.sh` | rien à signaler |
| `uv build --wheel` puis `unzip -l` | les onze `.toml` dans la roue |

**Garde-fou, refus signalé (non contourné)** : `uv run pytest .claude/hooks -q`
(enchaînée à d'autres vérifications) a été refusée : « uv » sur un chemin
réservé à l'IeC. J'ai utilisé la commande du tableau de l'ordre,
`python3 infra/agents/test_garde_fou.py`, qui passe.

**Écarts à l'ordre**

1. **Lignes vides** : `lignes_vides = "anomalie"` (CPD) donne `ligne_vide`,
   non bloquante ; partout ailleurs une ligne vide est comptée comme un
   nombre de colonnes faux, donc bloquante. Une seule règle `ligne_vide`,
   une seule gravité ; la distinction tient dans le contrat.
2. **Encodage, un contrôle de plus** : un fichier déclaré cp1252 qui
   arriverait en UTF-8 se décoderait sans erreur (les deux octets d'un `é`
   UTF-8 sont valides en cp1252). Pour un encodage à un octet, un fichier
   non ASCII qui se décode entièrement en UTF-8 est signalé `encodage`
   (ligne 0, bloquant). Vérifié sans faux positif sur les neuf fichiers
   cp1252 du 24/10.
3. **Énumérations au-delà de la documentation** : `motif_evaluation` (SMR,
   ASMR) est une énumération des douze libellés observés, pour qu'un
   nouveau motif ressorte en `valeur_inconnue` ; `agrement_collectivites`
   garde `inconnu`, documenté mais absent le 24/10 ; `taux_remboursement`
   est une `liste` d'énumération (séparateur `;` documenté), les neuf
   graphies étant les éléments.
4. **Lignes vides de CPD** : les trois lignes de données qui les précèdent
   finissent par un `\r` qui reste dans la valeur ; signalé
   `espace_parasite`, pas corrigé.
5. **Plages de dates** (non bloquantes) : 1950–2030 pour les déclarations et
   AMM, 2002–2030 pour les avis HAS, 2000–2030 pour Dispo_Spec (le
   `01/07/2027` d'un arrêt annoncé passe), 2000–2035 pour la fin des
   informations importantes. La règle « début postérieur à la mise à jour »
   (47 lignes) croise deux colonnes : hors du v0, à mesurer par le profil.

**Questions pour l'IeC** : l'écart 5 te convient-il (plages par colonne, pas
de règle entre colonnes dans le v0, le profil mesure les 47 débuts futurs
au palier 3) ?

**Propositions d'évolution** : aucune.
