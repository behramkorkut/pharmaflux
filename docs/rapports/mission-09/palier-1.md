# Mission 09 — palier 1 : collecte et extraction des pages d'avis (décisions 1 et 2)

## Synthèse

**Fait** : le groupe `pharmaflux has` (paquet `src/pharmaflux/has/`). `has collecter` fait un
passage poli (`robots.txt`, mentions légales, pages), archive à l'octet, tient un manifeste en
ajout seul (`manifeste/has-pages.jsonl`), reprend après une coupure et simule sans requête.
`has extraire` rejoue l'extraction (`html.parser`) et vérifie la non-altération par un second
lecteur sans code commun. Une garde réseau fait échouer tout test qui sortirait de la machine.
**Simulation de la première étape sur l'archive du Mac** : 746 dossiers, 720 avec un lien,
**722 pages, 724 requêtes, ≈ 26 min ; plafond à passer : 761** (commande de beko plus bas).
**Vérifications locales** (commit testé : celui de ce palier, arbre propre) : vertes, voir
le détail ; `evenements` identique à `beba0c8`. **Aucun appel à l'API, aucune requête réseau.**
**Écarts** : quatre précisions prises en codant, déclarées plus bas (aucune ne change l'ordre).
**Questions pour l'IeC** : aucune. **Propositions** : aucune.
Ensuite : **beko lance la collecte** ; je cite sa sortie dans un commit à part, avant le palier 2.

## Ce qui est livré

| fichier | rôle |
|---|---|
| `has/perimetre.py` | les pages à demander, depuis la dernière archive des liens, du SMR et de l'ASMR, lues par leur contrat (une anomalie bloquante refuse) ; ordre : date d'avis décroissante, dossier, URL |
| `has/client.py` | `ClientHas` : pause tenue dans le client (2 s au moins, avant toute requête, réessai compris), aucune redirection suivie, plafond (la requête qui le dépasserait n'est pas envoyée), arrêt net au premier 429 ou à la seconde défaillance d'affilée (5xx ou réseau), un réessai après 10 s |
| `has/collecte.py` | le passage, sa reprise (`planifier`, `executer`), le bilan et ses codes 0 à 3 |
| `has/manifeste.py` | les lignes du manifeste HAS, par la porte d'écriture du manifeste de la BDPM |
| `has/extraction.py` | le texte d'une page, bloc par bloc, ses dates, ses métadonnées de contrôle, ses douze motifs de rejet ; le texte de `<main>` des mentions légales |
| `has/verification.py` | le second lecteur (expressions régulières, `html.unescape`, sans espaces) |
| `has/inspection.py` | `has extraire` : bilan des rejets, `--verifier`, `--sortie` JSON Lines |
| `collecte/manifeste.py` | factorisé : `ajouter_ligne` et `parcourir_lignes` servent aux deux manifestes ; comportement inchangé |
| `tests/conftest.py` | la garde réseau de session (`reseau_coupe`) |
| `tests/test_has_*.py`, `tests/test_reseau.py` | 75 tests (44 d'extraction, 25 de collecte, 6 de la garde réseau), tous sur les fixtures du §0 |

**L'archive** (sous `$PHARMAFLUX_DATA`, sinon `~/pharmaflux-data`) :
- `bronze/has/pages/<p_N|c_N>/<horodatage>__<sha12>.html.gz` : une page, à l'octet, par
  l'écriture du bronze (`collecte.archive.ecrire_archive` : fichier temporaire, `os.link`) ;
- `bronze/has/robots.txt/<jour>/…txt.gz` et `bronze/has/mentions-legales/<jour>/…html.gz` ;
- `manifeste/has-pages.jsonl` : une ligne par requête (`role` robots, mentions ou page ;
  `statut` ; `http_statut` ; `location` ; `taille` et `sha256` des octets ; `archive` ;
  `empreinte_texte` et `extracteur` ; `rejet` ; `dossiers` et `date_avis_bdpm` ; `essais` ;
  `version_collecteur`, `user_agent`). Jamais de cookie.

**Le passage** relit le manifeste (une page archivée n'est jamais redemandée ; une page en
erreur seulement avec `--reessayer-erreurs`), adopte les archives orphelines par une ligne
`repris` sans requête, lit `robots.txt` (archivé s'il change ; chaque URL passe par
`urllib.robotparser`), relit les mentions légales (une requête comptée ; l'empreinte du texte
de `<main>` comparée à la précédente ; un texte changé ouvre le bilan par « ATTENTION —
mentions légales : TEXTE CHANGÉ … », sans arrêter), puis les pages. Chaque page archivée est
extraite tout de suite : son empreinte de texte, ou son motif de rejet, entre au manifeste
(addendum 1, C2 et L.5).

**L'extraction** (addendum 1, D) garde, dans l'ordre de la page : la nature de la demande et
le motif ; chaque section du corps sous son titre de la page (« L'essentiel », « Quel
progrès ? », « Quelle place dans la stratégie thérapeutique ? » et ses intertitres,
« Recommandations particulières ») ; les tables SMR et ASMR, niveau puis libellé. Chaque
`Ligne` porte sa rubrique, son genre (`nature`, `intertitre`, `paragraphe`, `element`,
`niveau`) et son texte mot pour mot ; nos seuls ajouts sont des préfixes du rendu
(« Nature de la demande : », « - », « SMR : »), jamais dans le texte. Les dates : de l'avis
(`datePublished`, la date écrite, jamais convertie en UTC), de mise en ligne, et de mise à jour
si la page l'affiche (`date_mise_a_jour` la préfère, addendum 1, A1). Le JSON-LD ne sert que
de contrôle. Les douze motifs de rejet sont éprouvés chacun sur une copie retouchée d'une page
réelle.

**La preuve de non-altération**, en trois volets (addendum 1, D) : le second lecteur
(`verification.ecarts`) retrouve chaque ligne extraite, dans l'ordre, dans le texte visible de
la page ; deux extractions donnent la même empreinte ; l'empreinte est celle du manifeste. Une
retouche d'un mot, ou un ordre changé, se voient (tests). Deux extractions de référence sont
figées après relecture à la main (`p_4072400.extrait.json`, `c_2027377.extrait.json`).

**Aucune requête réseau dans les tests** : `tests/conftest.py::reseau_coupe` (portée de
session, automatique) remplace `socket.getaddrinfo` et `socket.socket.connect` ; tout hôte qui
n'est pas cette machine lève `ReseauInterdit`, quel que soit le client. Redpanda et Qdrant
(`127.0.0.1`) restent joignables. `tests/test_reseau.py` le prouve pour httpx (HAS, BDPM,
data.gouv.fr), urllib, une adresse IP et `ClientHas` sans transport simulé. Le script du §0 et
son journal plein restent, et un test vérifie qu'aucun test ne l'importe (addendum 1, E).

## La simulation de la première étape (archive du Mac, lecture seule)

```
$ /usr/bin/time -l uv run pharmaflux has collecter --simuler --racine ~/pharmaflux-data
simulation : aucune requête envoyée
  bdpm.liens_ct   bronze/bdpm/HAS_LiensPageCT_bdpm.txt/2026-10-24/20261024T194155Z__2f01ff1e13f8.txt.gz (sha256 2f01ff1e13f8…)
  bdpm.smr        bronze/bdpm/CIS_HAS_SMR_bdpm.txt/2026-10-24/20261024T194150Z__c2215af6b207.txt.gz (sha256 c2215af6b207…)
  bdpm.asmr       bronze/bdpm/CIS_HAS_ASMR_bdpm.txt/2026-10-24/20261024T194153Z__f849554030c7.txt.gz (sha256 f849554030c7…)
dossiers avec un avis SMR ou ASMR depuis le 2024-01-01 : 746, dont 720 avec un lien et 26 sans lien ; 722 page(s)
déjà archivées : 0 ; archives orphelines à reprendre : 0 ; en erreur, non redemandées : 0
requêtes : 724 (robots.txt, mentions légales et 722 page(s)) ; durée estimée ≈ 25 min 56 s à 2.0 s de pause ; plafond conseillé : 761
liste des URL (sha256 ed350d469132…), dans l'ordre :
  20260909 CT-21426 https://www.has-sante.fr/jcms/p_4460994
  20260909 CT-21704 https://www.has-sante.fr/jcms/p_4437700
  …  (722 lignes)
  20240110 CT-20629 https://www.has-sante.fr/jcms/p_3490839
        0.61 real   …   103776256  maximum resident set size
```

L'archive du Mac n'a pas bougé (`bronze/` et `manifeste/` relus avant et après). Le sha256 de
la liste des 722 URL est `ed350d4691325418…` ; il est le même sur le jeu de démo.

**Le plafond à passer : 761** = 724 requêtes (`robots.txt`, mentions légales, 722 pages) + 37
de marge pour les réessais (5 %, dix au moins). Un réessai n'a lieu qu'après une défaillance
isolée, et deux défaillances d'affilée arrêtent tout : 37 réessais isolés couvrent un passage
très dégradé sans laisser partir de rafale.

**La commande de beko**, depuis `pharmaflux-codeur/` (le code est sur la branche de mission),
le journal allant sous `data/` (ignoré par git) pour que je le cite :

```bash
/usr/bin/time -l uv run pharmaflux has collecter --plafond 761 --racine ~/pharmaflux-data 2>&1 | tee data/has-collecte-premiere-etape.log
```

Durée attendue ≈ 26 min ; elle n'écrit que sous `~/pharmaflux-data/bronze/has/` et
`~/pharmaflux-data/manifeste/has-pages.jsonl`. Si elle sort en code 3 (arrêt net : 429, 5xx
répété, plafond), la même commande, relancée plus tard, reprend où elle s'est arrêtée. Puis,
pour que je cite l'extraction réelle :

```bash
uv run pharmaflux has extraire --verifier --racine ~/pharmaflux-data --sortie data/has-extraits.jsonl 2>&1 | tee data/has-extraire.log
```

## La mémoire et le temps (ADR 0009, seuil 512 Mo ; `/usr/bin/time -l`)

| commande | données | durée | résident maximal |
|---|---|---|---|
| `has collecter --simuler` | archive du Mac, 722 pages | 0,61 s | 99 Mo |
| un passage complet, site simulé sans pause (scratchpad, les six pages du §0 en boucle) | 724 requêtes, 722 archives, 13 Mo écrits | 7,6 s | 88 Mo |
| `has extraire --verifier` | les 722 archives de ce passage | 5,0 s | 50 Mo |
| `has extraire --verifier --page …` | les six pages du §0 et la page de mesure d'audience | < 1 s | — |

Le passage réel sera dominé par les pauses (723 × 2 s) : ≈ 26 min pour < 100 Mo. Je citerai la
mesure de beko.

## Décisions prises en codant (écarts déclarés)

1. **`robots.txt` : refus ou arrêt.** Un `robots.txt` qui répond autre chose que 200 en
   `text/plain` non vide donne le **refus (code 2)**, comme au §0. Un 429 ou deux défaillances
   d'affilée sur lui donnent l'**arrêt net (code 3)** : c'est le serveur qui souffre, et la
   relance reprend.
2. **`robots.txt` et les mentions légales ne s'archivent que s'ils changent** (sha256 pour le
   premier, empreinte du texte de `<main>` pour les secondes, qui changent d'octets à chaque
   réponse) ; sinon la ligne est `inchange` et cite l'archive précédente. Toute requête a sa
   ligne.
3. **Le texte des mentions légales** est celui de `<main>` (le jeton CSRF et l'horodatage en
   sont dehors). Cette page n'a pas été demandée au §0 : la règle est éprouvée sur une page
   d'avis du même gabarit. Si la vraie page n'avait pas de `<main>`, le bilan s'ouvrirait sur
   « mentions légales illisibles … à relire », sans arrêter : le premier passage de beko le
   dira.
4. **`--simuler` n'exige pas `--plafond`** : il en conseille un. Un passage réel sans plafond
   est refusé (code 2), comme une pause sous 2 s.

Le reste est l'avis du §0 tel que l'addendum l'a retenu.

## Vérifications locales

Redpanda, Qdrant et les fichiers du modèle présents sur le Mac.

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 308 files already formatted |
| `uv run mypy src` | Success: no issues found in 86 source files |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **810 passed** en 6 min 16 (735 au départ de la mission) ; aucun saut ; la garde réseau active pour toute la session |
| `uv run pytest -q -rE -m "integration or modele"` | 17 passed, 793 deselected ; 0 réessai du registre sur 30 cycles |
| aucune requête réseau dans les tests | `tests/conftest.py::reseau_coupe` et `tests/test_reseau.py` (6 tests) |
| simulation du `Makefile` | aucune cible nouvelle ni modifiée à ce palier |
| `sh infra/git-hooks/test-crochets.sh` / `python3 infra/agents/test_garde_fou.py` | crochets git : tout est conforme / OK (24 tests) |
| shellcheck, YAML de la CI | aucun `.sh` ni `ci.yml` touché |
| `pharmaflux assistant depenses` | « mission 8 : 65 appel(s), 1.0309 $ » : le journal n'a que les 65 lignes de la mission 08 ; mission 09 : 0 appel, 0 $ (la constante `MISSION` passe à 9 au palier 2) |
| `demo verifier` | conforme |
| `profil --racine ~/pharmaflux-data` | 11 fichiers profilés, 0 anomalie bloquante |
| `questions verifier --racine ~/pharmaflux-data` (v0) | 40 : 25 conforme, 5 non calculable, 10 sans attendu |
| `evenements --racine ~/pharmaflux-data`, `diff -r` contre la sortie de `beba0c8` (extrait par `git archive`) | identique : 41 fichiers, `diff -r` vide (le manifeste de la BDPM a été factorisé, d'où cette preuve) |
| `has extraire --verifier --page` (les six pages du §0 et la page de mesure d'audience) | 7 pages : 6 extraites, 1 rejetée (`jsonld_absent`) ; 6 conformes, 0 écart, 0 divergence |

`silver verifier`, `make gold`, `index verifier` et la v1 renotée ne sont pas rejoués : ce palier
ne touche ni le silver, ni le gold, ni l'index, ni l'assistant (la séquence de beko les
rejouera au palier 3).
