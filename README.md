# Pharmaflux

Plateforme temps réel de connaissance du médicament pour l'assurance
santé, construite sur des **données publiques réelles** : la Base de
données publique des médicaments (BDPM), Open Medic (Cnam) et les avis de
la Commission de la transparence (HAS).

Ces sources publient un **état**, jamais d'événement, et n'en gardent pas
l'historique : chaque mise à jour écrase la précédente. Pharmaflux les
archive, détecte ce qui change, publie des événements datés et rejouables,
et les met à la disposition d'un assistant qui cite ses sources et
s'abstient quand il ne sait pas.

Projet portfolio de Behram Korkut. Le cadrage complet est dans
[`01_Specifications/`](01_Specifications/PRD_Plateforme_Medicaments_v1.0.md)
et le point d'entrée technique dans [`docs/CONTEXTE.md`](docs/CONTEXTE.md).

## État

**Mission 00 fusionnée** (PR #1) : socle du dépôt et archivage horaire des
fichiers BDPM, sur un VPS depuis le 24/10/2026. L'archive brute est la seule
brique qui ne se rattrape pas : elle a démarré avant tout le reste.

**Mission 01 fusionnée** (PR #2) : contrats de schéma des onze fichiers BDPM,
profil des archives (`docs/donnees/`), premières décisions d'architecture
(`docs/adr/`) et jeu de questions de référence (`evaluation/`).

**Mission 02 fusionnée** (PR #3) : du bronze aux événements. Chaque archive
est normalisée selon son contrat, comparée à la dernière retenue, et chaque
changement devient un événement rejouable à l'identique, avec un garde-fou qui
écarte une réponse vide ou tronquée (ADR 0005, 0006).

**Mission 03 fusionnée** (PR #4) : le bus d'événements Redpanda, un topic par
entité, registre de schémas, publication sans perte ni doublon (ADR 0007).

**Mission 04 fusionnée** (PR #5) : le jeu de démo figé dans le dépôt et son
rejeu accéléré ; `make up` puis `make demo` (ADR 0008).

**Mission 05 fusionnée** (PR #6) : le silver, une table Iceberg historisée par
entité, « état à une date » vérifié contre l'archive ; `make silver`
(ADR 0009).

**Mission 06 fusionnée** (PR #7) : le gold, calculé à la demande depuis le
silver : colonnes typées, fiche médicament, disponibilité courante,
alternatives, contrôles de qualité, et le jeu de questions recalculé depuis
le gold ; `make gold` (ADR 0010). **Le Lot 2 est fait.**

**Mission 07 fusionnée** (PR #8) : l'index de l'assistant. La fiche médicament
devient des fragments datés et prudents, encodés par un modèle local épinglé
(multilingual-e5-small) dans Qdrant. L'index est mis à jour par incréments
depuis le silver, et vérifié contre sa reconstruction complète ; `make index`
(ADR 0011).

**Mission 08 fusionnée** (PR #9) : l'assistant gouverné. La recherche devient
hybride (le sens et les mots). Claude rédige à partir des seuls fragments, et
le code contrôle chaque citation, chaque nombre et chaque date. L'assistant
s'abstient quand il ne sait pas et refuse le conseil médical. Un jeu de
88 questions le note sans juge LLM : 44 bonnes réponses sur 49, aucune
citation invalide, aucun conseil médical, 1,03 $ (ADR 0012).

**Mission 09 en cours** : le corpus des avis de la HAS. Une collecte polie des
pages d'avis de la Commission de la transparence (722 pages, avis depuis 2024),
leur texte extrait mot pour mot et indexé à côté des fiches. L'assistant cite
une page d'avis : son lien, la date de l'avis et la date de consultation sont
rendus par le code, jamais écrits par le LLM. Une page d'avis ne se rattache
qu'aux fiches du référentiel des spécialités : 121 pages sur 721 (16,8 %),
liées seulement à des médicaments absents du référentiel, restent dans
l'archive mais hors de l'index. Un jeu v2 de 144 questions mesure le texte des
avis et les correctifs de la mission 08, sur des questions figées avant eux
(ADR 0013).

| Lot | Contenu | État |
|---|---|---|
| 0 | archivage des sources, profilage, décisions d'architecture | fait |
| 1 | collecte, détection des changements, flux d'événements (Redpanda) | fait sur le Mac ; le VPS reste |
| 2 | lakehouse Iceberg + DuckDB, historique, voyage dans le temps | fait |
| 3 | assistant gouverné (sources citées, abstention) | en cours : l'index (mission 07) et l'assistant (mission 08) faits ; les avis de la HAS (mission 09) |
| 4 | volet assurance : dépense exposée aux ruptures (Open Medic) | à venir |
| 5 | observabilité, objectifs de service, incidents provoqués | à venir |

## Lancer

### Démo : la chaîne entière en quatre minutes, sur une donnée réelle

Le dépôt porte un **jeu de démo figé**, [`demo/archive`](demo/README.md) :
trois jours de collecte réelle de la BDPM (du 24 au 27 octobre 2026, 71
passages, 22 archives, 6,7 Mo), repris à l'octet, et la seule donnée admise
dans git. `make demo` le rejoue sur le bus **en accéléré** : une heure
observée dure 3,6 s, un jour 86 s.

Prérequis : Docker avec Compose (sur le Mac, colima), [`uv`](https://docs.astral.sh/uv/),
`make`, et les images du bus déjà téléchargées, une fois :

```bash
docker compose -p pharmaflux --profile console pull   # une fois ; make ne télécharge jamais
```

Deux commandes :

```bash
make up      # vérifie les prérequis (sans rien télécharger) et démarre Redpanda
make demo    # enregistre les schémas, rejoue demo/archive sur le bus, puis verifier-bus
```

Ce qu'on voit, à l'heure observée : l'**état initial** du 24/10 à 19 h 41
(onze fichiers, 164 096 événements `creee`, une trentaine de secondes de
publication), puis l'horloge qui avance passage par passage, et les
changements réels tels qu'ils sont arrivés : dix présentations supprimées,
en trois fois (2 le 24 à 23 h 17, 1 le 26 à 0 h 17, 7 le 27 à 0 h 17), le fichier
des informations importantes servi **vide** quatre fois et écarté par le
garde-fou de volume, puis retenu identique au dernier retenu. La démo finit
par `verifier-bus --racine demo/archive` : le bus relu, dédoublonné, appliqué
et comparé au dernier snapshot recalculé depuis l'archive, « conforme » sur
les onze topics. Ce que la copie ne contient pas ne se voit pas : aucune
`modifiee`, aucun snapshot en attente, une file des échecs vide. Dans un
second terminal, `make suivre` (à lancer **avant** `make demo`) affiche
chaque événement publié en une ligne : heure observée, entité, type, clé.

Sur une machine qui a **déjà** un volume `pharmaflux` (le bus d'une mission
précédente, ou une démo déjà jouée), `make demo` refuse avec le code 2 et le
message qui renvoie à `make rebatir` : un événement publié ne se réécrit pas ;
`make rebatir` (efface le seul projet `pharmaflux` et `data/demo`) puis
`make demo` rejouent tout. Un rejeu interrompu se reprend avec
`uv run pharmaflux demo rejouer --reprendre` (ou `publier --reprendre
--sortie data/demo`, sans l'horloge). `make help` liste les cibles ; la même
démo tourne en CI sans pause (`make demo DEMO_OPTIONS=--sans-pause`). Le
détail des choix est dans l'[ADR 0008](docs/adr/0008-rejeu-accelere-et-jeu-de-demo.md).

### Le silver : l'histoire interrogeable, et vérifiée contre l'archive

Après `make demo`, une troisième commande construit le **silver** (mission 05,
[ADR 0009](docs/adr/0009-silver-iceberg-scd2-et-etat-a-une-date.md)) : une
table Iceberg par entité sous `data/demo/lakehouse`, où chaque ligne est une
**version** datée d'une ligne de la source, valable de la date d'observation
qui l'ouvre à celle qui la ferme (SCD2 sur le temps de la connaissance, borne
de fin exclue). Le consommateur lit le bus, garde sa position dans le commit
Iceberg lui-même, et reconnaît les doublons ; puis la vérification recalcule
le snapshot de chaque archive retenue depuis le bronze et le compare,
empreinte par empreinte, à l'état du silver au moment de son observation.

```bash
make silver  # consommer le bus → data/demo/lakehouse, puis silver verifier : 22/22 conforme
```

Deux questions sur le jeu, « que savait-on à cet instant ? », avec le temps
de la connaissance à la seconde : l'horodatage d'une archive est celui de
son téléchargement (`20261024T231712Z`), pas celui du passage de collecte.

```bash
# Une présentation déclarée en arrêt de commercialisation disparaît le 24/10 à 23:17:12 :
# encore là une seconde avant (une version ouverte), plus là à l'instant de l'archive.
make etat ENTITE=bdpm.presentations A=2026-10-24T23:17:11Z \
  ETAT_OPTIONS="--ou code_cip13=3400938844948 --format tableau --colonne code_cis --colonne etat_commercialisation --colonne fin_validite"
make etat ENTITE=bdpm.presentations A=2026-10-24T23:17:12Z ETAT_OPTIONS="--ou code_cip13=3400938844948"

# Le 26/10 juste après 14:17:39, le fichier des informations importantes a été servi vide
# et écarté par le garde-fou : l'état n'a pas bougé, 10 905 versions, toutes ouvertes.
make etat ENTITE=bdpm.infos_importantes A=2026-10-26T14:17:39Z ETAT_OPTIONS="--format csv --colonne code_cis --colonne fin_validite"
```

La première commande rend une version (`fin_validite` à `2026-10-24T23:17:12Z`),
la deuxième aucune, la troisième 10 905 lignes sans fin de validité. Et du
SQL libre, en lecture seule (DuckDB sans aucun accès fichier, seul un
`SELECT` passe) :

```bash
uv run pharmaflux silver sql --entrepot data/demo/lakehouse \
  "SELECT count(*) AS versions, count(fin_validite) AS fermees FROM presentations"
# 20 898 versions, 10 fermées : les suppressions des 24, 26 et 27/10
uv run pharmaflux silver sql --entrepot data/demo/lakehouse \
  "SELECT count(*) AS versions, count(fin_validite) AS fermees FROM infos_importantes"
# 10 905 versions, 0 fermée : en neuf archives, dont quatre servies vides et écartées,
# aucune information importante n'a jamais changé ni disparu
```

Le même silver se construit depuis les fichiers d'événements
(`uv run pharmaflux silver construire --sortie data/demo --entrepot <dossier>`),
et `silver comparer` montre qu'il est identique à celui du bus : le silver ne
dépend pas du chemin. `make rebatir` efface aussi `data/demo/lakehouse`.

### Le gold : la fiche médicament, la disponibilité, contrôlées et datées

Après `make silver`, une quatrième commande montre le **gold** (mission 06,
[ADR 0010](docs/adr/0010-gold-calcule-a-la-demande-types-vues-controles.md)).
Il n'est pas stocké : c'est une fonction du silver et d'un instant. Chaque
colonne y prend le type de son contrat (un prix est un décimal exact, une
date une date), et une valeur illisible dans la source reste **vide**, jamais
devinée ; trois vues métier s'en déduisent : la fiche médicament, la
disponibilité courante par présentation, les alternatives d'un groupe
générique.

```bash
make gold  # 14 contrôles de qualité (aucun bloquant), puis les 25 questions recalculées depuis le gold
```

`make gold` lance les quatorze contrôles de qualité (quatre bloquants, qui
sortent en code 2, et dix mesurés, toujours affichés : 4 présentations dont la
spécialité est absente du référentiel, 5 562 CIS cités ailleurs et absents de
`CIS_bdpm.txt`, une valeur illisible…), puis recalcule chacune des 25
questions du jeu de référence depuis le gold, à l'instant de son archive, et
exige qu'elle concorde avec le calcul depuis le bronze.

La fiche d'une spécialité, aux deux secondes qui encadrent la disparition de
sa présentation (le même cas que le silver plus haut) :

```bash
make fiche CIS=63830632 A=2026-10-24T23:17:11Z
make fiche CIS=63830632 A=2026-10-24T23:17:12Z
```

```text
CIS 63830632 — FOSINOPRIL HYDROCHLOROTHIAZIDE EG 20 mg/12,5 mg, comprimé sécable
État au 2026-10-24T23:17:11Z
Spécialité : comprimé sécable ; voie(s) orale ; Autorisation abrogée depuis le 2008-10-08 (Procédure nationale) ; Non commercialisée ; titulaire(s) EG LABO - LABORATOIRES EUROGENERICS
Présentations (1) :
  - 3400938844948 : plaquette(s) aluminium de 30 comprimé(s) ; Déclaration d'arrêt de commercialisation ; taux — ; prix public —
…
Disponibilité (signalements en cours) : aucun signalement dans le fichier de disponibilité (ce n'est pas « disponible »)
Sources (4) :
  - CIS_COMPO_bdpm.txt : observée depuis le 2026-10-24T19:41:48Z, source du 2026-09-29
  - CIS_CPD_bdpm.txt : observée depuis le 2026-10-24T19:41:59Z, source du 2026-09-29
  - CIS_CIP_bdpm.txt : observée depuis le 2026-10-24T19:41:46Z, source du 2026-10-23
  - CIS_bdpm.txt : observée depuis le 2026-10-24T19:41:43Z, source du 2026-09-29
```

Une seconde plus tard, la même fiche dit `Présentations : —`, et ses sources
ne citent plus `CIS_CIP_bdpm.txt`. Chaque section dit d'où elle vient, la date
de sa source et depuis quand la valeur est observée.

La disponibilité d'une présentation de LARIAM, que le fichier de l'ANSM ne
cite pas : la ligne de rupture vise la spécialité (sans CIP13), et le gold le
dit (`portee = specialite`), sans en dire plus.

```bash
uv run pharmaflux gold disponibilite --entrepot data/demo/lakehouse --cip13 3400933961688 \
  --colonne code_cip13 --colonne denomination --colonne etat_signalement \
  --colonne libelle_statut --colonne date_debut --colonne portee
```

```text
code_cip13     denomination                     etat_signalement  libelle_statut    date_debut  portee
-------------  -------------------------------  ----------------  ----------------  ----------  ----------
3400933961688  LARIAM 250 mg, comprimé sécable  declare           Rupture de stock  2026-06-25  specialite
```

Une présentation que rien ne cite est `aucun_signalement`, ce qui ne veut pas
dire « disponible » ; une fiche que l'ANSM cesse de publier devient
`fin_de_publication`, ce qui ne veut pas dire « remise à disposition »
(ADR 0003). Un instant où l'un des onze fichiers n'a pas encore été observé
est refusé, avec le premier instant où ils le sont tous : le gold ne dit pas
« aucun signalement » avant d'avoir lu le fichier. Et du SQL, sur les
entités typées et les trois vues (`fiche_medicament`,
`disponibilite_courante`, `alternatives`) :

```bash
uv run pharmaflux gold sql --entrepot data/demo/lakehouse \
  "SELECT etat_signalement, portee, count(*) AS n FROM disponibilite_courante GROUP BY ALL ORDER BY ALL"
# aucun_signalement 20 004 ; declare, presentation 36 ; declare, specialite 878
```

### L'index : la fiche en fragments, cherchée, tenue à jour

Après `make gold`, `make index` construit l'**index de l'assistant** (mission
07, [ADR 0011](docs/adr/0011-index-fragments-qdrant-e5-increment-verification.md)).

**Les fragments.** Chaque fiche du gold devient au plus cinq fragments :
identité, présentations, avis, disponibilité, informations importantes. Le
texte est déterministe, sans LLM, et garde la prudence du gold :
« aucun signalement » n'y devient jamais « disponible ». Chaque fragment
porte sa source et sa date ; l'index porte l'instant de l'état.

**L'encodage.** Les fragments sont encodés localement par
multilingual-e5-small (int8, ONNX, épinglé par révision et sha256), puis
rangés dans Qdrant. Chacun porte aussi un vecteur creux BM25 (mission 08) :
un nom, un CIS ou un CIP13 se cherchent mieux par les mots. La recherche
fusionne les deux voies (RRF).

**La mise à jour.** Elle ne recalcule que les médicaments touchés depuis
l'instant de l'index (versions du silver, liens vers les avis, débuts annoncés
et fenêtres qui basculent avec le jour). Puis `index verifier` compare l'index
à sa reconstruction complète depuis le gold.

```bash
make index   # 1re fois : construction complète (72 296 fragments, 18 min) ; ensuite : par incréments, puis vérifié
uv run pharmaflux index chercher "LARIAM 250 mg est-il en rupture de stock ?" -k 3
```

```text
1. score 0.033 — CIS 65999556, disponibilite
   sources : CIS_CIP_Dispo_Spec.txt (source du 2026-10-21, observée depuis le 2026-10-24T19:42:01Z) ; CIS_MITM.txt (source du 2026-10-13, observée depuis le 2026-10-24T19:42:03Z)
   état de l'index au 2026-10-27T00:17:12Z
   | CIS 65999556 — LARIAM 250 mg, comprimé sécable
   | Médicament d'intérêt thérapeutique majeur (ATC P01BC02, liste publiée le 2024-12-18).
   | Disponibilité, signalements en cours dans le fichier de l'ANSM (1) :
   |   - Rupture de stock depuis le 2026-06-25 ; mis à jour le 2026-10-08 ; vise la spécialité entière (toutes ses présentations), aucune présentation (CIP13) n'est nommée
2. score 0.016 — CIS 65999556, presentations
   …
```

Le score est celui de la fusion (RRF, `1/(60 + rang)` par voie). Ce n'est pas
encore l'assistant : ni décision, ni réponse rédigée (voir plus bas).

**Les mesures, sur le jeu.** À la clôture de la mission, la construction
complète a tenu en 411 Mo pour l'encodage et en 416 Mo pour le calcul des
fragments, qui tourne dans un sous-processus, en 18 minutes. La recherche est exacte : 7 ms par requête sur les 72 296
fragments.

`index evaluer` mesure la recherche sur les questions qui nomment un
médicament. Sur les 22 questions du jeu v0, le bon fragment est dans les
cinq premiers pour 17 d'entre elles avec le dense seul, et pour 20 avec
l'hybride. Le bon CIS est au premier rang pour 21 questions sur 22.

Le modèle et l'image Qdrant se téléchargent une fois, selon
[`infra/index/README.md`](infra/index/README.md) ; `make up` et `make index`
ne téléchargent rien.

### L'assistant : une réponse sourcée et datée, ou rien

`pharmaflux assistant demander` répond à une question en français (mission 08,
[ADR 0012](docs/adr/0012-recherche-hybride-et-assistant-gouverne.md)).
**Les faits viennent des fragments, Claude rédige, et le code décide,
contrôle et cite :**

- **le refus médical et les abstentions se décident d'abord hors du LLM**,
  par des règles écrites et testées sur tout le jeu : une demande de
  conseil (prendre, arrêter, remplacer, doser…), une question de dépense
  (au Lot 4), un sujet absent des sources, deux médicaments à la fois, un
  médicament qu'aucun fragment ne porte ;
- **Claude Opus 5.5 rédige** à partir des dix fragments de la recherche
  hybride, en sortie structurée, et cite chaque fait par l'étiquette d'un
  fragment fourni ;
- **le code contrôle** que chaque citation est un fragment fourni, et que
  chaque nombre et chaque date du texte s'y retrouvent. Un échec donne une
  abstention, jamais une réponse non vérifiée ;
- **le code rend lui-même** les sources, leurs dates et l'instant de l'index ;
- chaque appel est compté dans un journal local, sous le plafond de la
  mission (20 $ à la mission 08, 10 $ à la mission 09). Une question déjà
  posée sur le même index ne repaie pas.

Deux sorties réelles, celles de la démonstration du 30/10/2026. La clé de
l'API n'est donnée qu'au processus lancé par `infra/agents/avec-cle.sh`.

```bash
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander \
  "Quel est le taux de remboursement de DOLIPRANE 1000 mg, comprimé, boîte de 8 ?"
```

```text
Réponse :
Pour DOLIPRANE 1000 mg, comprimé (CIS 60234100), la présentation en plaquette(s) thermoformée(s) PVC-aluminium de 8 comprimés (CIP 3400935955838) est en déclaration de commercialisation, avec un taux de remboursement de 65 % et un prix public de 2,18 € [2]. À titre d'information, la présentation de 100 comprimés de cette même spécialité n'a ni taux ni prix renseignés [2].
  [2] CIS 60234100, presentations — CIS_CIP_bdpm.txt (source du 2026-10-23, observée depuis le 2026-10-24T19:41:46Z)
état de l'index au 2026-10-27T00:17:12Z
coût : 0.0126 $
```

```bash
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander \
  "Puis-je remplacer LARIAM 250 mg, en rupture, par un autre antipaludique pour mon voyage ?"
```

```text
Refus (question médicale) :
Cette question appelle une décision de soin : l'assistant ne la prend pas.
motif : la question demande une décision de soin (« remplacer »)
orientation : cette décision revient à un médecin ou à un pharmacien ; l'assistant n'est pas un dispositif médical et ne donne aucun conseil de soin
état de l'index au 2026-10-27T00:17:12Z
coût : 0 $ (décision hors LLM)
```

**L'évaluation.** `make evaluer` note l'assistant sur les 88 questions du
[jeu v1](evaluation/README.md), **sans juge LLM**. Une réponse est correcte si
elle porte les valeurs attendues et cite le bon médicament. Elle ne doit
contenir aucun mot interdit (« disponible » pour une absence de
signalement). Une abstention ou un refus sont justes quand ils sont
attendus. Deux conditions sont dures : aucune citation invalide, et aucun
conseil médical. La porte budgétaire chiffre toute l'évaluation avant le
premier appel, et `make evaluer EVALUER_OPTIONS=--estimer` la chiffre sans
clé ni appel.

**Mesuré le 30/10/2026** sur la v1, avec Claude Opus 5.5 à l'effort `low` :
- 62 appels, pour **0,99 $** ;
- **aucune citation invalide, aucun conseil médical** ;
- 100 % d'abstention hors périmètre et sur les questions médicales ;
- **44 réponses correctes sur 49 (89,8 %)**, 48 sur 49 citant une source datée.

Le premier passage donnait 34 sur 49. Le contrôle lisait comme des nombres les
renvois « [2] » que le modèle écrit dans son texte, et rejetait ainsi douze
réponses justes. Ce défaut est corrigé, puis l'évaluation est renotée sur les
mêmes réponses, en cache, sans nouvel appel. Les cinq échecs qui restent sont
réels : un fragment d'avis que la recherche n'a pas ramené, et quatre dates
omises.

**Le texte des avis de la HAS** (mission 09,
[ADR 0013](docs/adr/0013-corpus-has-collecte-extraction-fragments-liens.md)). La
page d'un avis de la Commission de la transparence est collectée poliment,
son texte extrait mot pour mot et indexé à côté de la fiche. Le LLM ne voit
aucune adresse. **Le code rend la page sous la réponse, avec la date de
l'avis, sa mise en ligne et sa consultation**, comme la licence de la HAS le
demande, et les deux horloges de l'index. Une sortie réelle de la
démonstration du 31/10/2026 :

```bash
sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander \
  "Quel SMR la Commission de la transparence a-t-elle rendu pour MOUNJARO dans le dossier CT-21681 ?"
```

```text
Réponse :
Selon l'avis de la Commission de la transparence du 2026-05-06 (dossier CT-21681, « MOUNJARO (tirzépatide) - Diabète de type 2 »), le service médical rendu est indiqué ainsi : « SMR : Modéré ». Il s'agit d'une évaluation collective, qui ne s'applique pas à une personne en particulier. Le fragment fourni donne ce niveau sans le texte qui le précise (fiche partielle). Dans le même avis, la Commission considère que MOUNJARO (tirzépatide) n'apporte pas d'amélioration du service médical rendu (ASMR V) par rapport à TRULICITY (dulaglutide), et indique « Dans les autres situations de l'AMM : sans objet ».
  [3] CIS 68186732, avis_has — has.avis (source du 2026-05-06, observée depuis le 2026-10-31T12:45:53Z)
      lien : avis de la Commission de la transparence du 2026-05-06 : https://www.has-sante.fr/jcms/p_4072400 (page mise en ligne le 2026-06-12, consultée le 2026-10-31)
  [6] CIS 68186732, avis_has — has.avis (source du 2026-05-06, observée depuis le 2026-10-31T12:45:53Z)
      lien : avis de la Commission de la transparence du 2026-05-06 : https://www.has-sante.fr/jcms/p_4072400 (page mise en ligne le 2026-06-12, consultée le 2026-10-31)
état de l'index : BDPM au 2026-10-27T00:17:12Z ; pages d'avis de la HAS collectées jusqu'au 2026-10-31T13:07:40Z
coût : 0.0234 $
```

Contenu de la Haute Autorité de santé, disponible sur <https://www.has-sante.fr>,
page consultée le 31/10/2026.

**Mesuré le 31/10/2026** sur le [jeu v2](evaluation/README.md) (144 questions,
dont 56 nouvelles) : 88 réponses correctes sur 91, aucune citation invalide,
aucun conseil médical, la page d'avis rendue sous les 26 réponses qui
l'attendent. La mission a dépensé 3,82 $ en tout, dont 1,62 $ pour la relance
de la v1 et de la v2 après le rattachement aux seules fiches du référentiel.

### Les commandes

Prérequis : [`uv`](https://docs.astral.sh/uv/). Python 3.12 est installé
par `uv` dans le projet.

```bash
uv sync
uv run pharmaflux --help
```

```bash
uv run pharmaflux catalogue          # les quatorze entrées collectées
uv run pharmaflux collecte           # un passage : télécharge, compare, archive, consigne
uv run pharmaflux etat               # dernière archive, dernier changement, erreurs, 24 h
uv run pharmaflux profil             # chaque archive contre son contrat : anomalies, clé, colonnes, liens
uv run pharmaflux questions verifier # le jeu de questions (v0, ou v1 par --questions) rejoué sur l'archive ; --entrepot : aussi depuis le gold
uv run pharmaflux evenements         # du bronze aux événements : rejeu complet, ou --reprendre
uv run pharmaflux schemas enregistrer # les schémas du dépôt dans le registre de Redpanda
uv run pharmaflux publier            # les fichiers d'événements sur le bus, ou --reprendre
uv run pharmaflux verifier-bus       # relit le bus et le compare à la référence (--racine : l'archive)
uv run pharmaflux suivre             # les événements publiés au fil de l'eau, une ligne par message
uv run pharmaflux demo verifier      # le jeu de démo demo/archive : manifeste, sha256, rien d'autre
uv run pharmaflux demo rejouer       # le jeu rejoué sur le bus, dans l'ordre observé, en accéléré
uv run pharmaflux silver consommer   # le bus → le silver Iceberg (une table par entité), position dans le commit
uv run pharmaflux silver construire  # le même silver, depuis les fichiers d'événements
uv run pharmaflux silver etat        # les versions valides à un instant (--entite, --a, --ou, --format)
uv run pharmaflux silver sql         # du SQL DuckDB sur le silver, en lecture seule
uv run pharmaflux silver comparer    # deux entrepôts : mêmes versions, mêmes validités
uv run pharmaflux silver verifier    # l'état à chaque observation contre le snapshot recalculé
uv run pharmaflux gold etat          # l'état typé d'une entité à un instant (--entite, --a, --ou, --format)
uv run pharmaflux gold fiche         # la fiche médicament d'un CIS (--cis, --format texte) ou toutes (--tout)
uv run pharmaflux gold disponibilite # la disponibilité courante par présentation (--cis, --cip13)
uv run pharmaflux gold alternatives  # les autres présentations du groupe générique (--cip13, --cis, --groupe)
uv run pharmaflux gold qualite       # les quatorze contrôles de qualité ; code 2 si un bloquant tombe
uv run pharmaflux gold sql           # du SQL DuckDB sur le gold à un instant, en lecture seule
uv run pharmaflux index construire   # l'index de l'assistant : fragments du gold, encodés (e5), dans Qdrant
uv run pharmaflux index mettre-a-jour # par incréments, de l'instant de l'index au silver
uv run pharmaflux index verifier     # l'index contre sa reconstruction depuis le gold (code 1 au moindre écart)
uv run pharmaflux index chercher "…" # recherche hybride : les fragments, leur source et l'instant de l'index
uv run pharmaflux index etat         # instant, modèle, format, fragments par section
uv run pharmaflux index evaluer      # le rappel dense, creux et hybride sur un jeu de questions, sans seuil
uv run pharmaflux assistant demander "…" # une réponse sourcée et datée, une abstention ou un refus (--format json : la trace)
uv run pharmaflux assistant evaluer  # l'assistant noté sur le jeu v1, sous le plafond (--estimer : sans clé ni appel)
uv run pharmaflux assistant depenses # le total dépensé pour la mission et ce qui reste du plafond
```

Un passage télécharge la page de téléchargement de la BDPM et ses onze
fichiers ; une fois par jour, la documentation PDF de leur format et les
métadonnées Open Medic. Chaque
fichier reçu est conservé à l'octet près, compressé, sous
`bronze/<source>/<fichier>/<jour>/<horodatage UTC>__<sha256, 12 car.>.<ext>.gz`, et
chaque passage laisse une ligne par fichier dans
`manifeste/collecte.jsonl`, même en erreur. L'archive s'écrit hors du
dépôt, sous `PHARMAFLUX_DATA` (défaut : `~/pharmaflux-data`). Rien de
`data/` n'entre dans git. En production, la collecte tourne toutes les
heures à `:17` sur un VPS (minuteur systemd) et une copie est rapatriée
chaque semaine : procédure dans
[`infra/planification/README.md`](infra/planification/README.md).

`profil` vérifie une archive contre son **contrat de schéma**
(`src/pharmaflux/contrats/bdpm/`, un TOML par fichier) et mesure ce
qu'elle contient : les anomalies sont signalées, jamais corrigées. Le
résultat sur l'archive du 24/10/2026 est dans
[`docs/donnees/`](docs/donnees/README.md). `questions verifier` rejoue le
[jeu de questions de référence](evaluation/README.md) : quarante questions
dont la réponse attendue est lue dans une archive précise.

`evenements` lit chaque archive du bronze avec son contrat, la normalise,
la compare à la dernière archive retenue du même fichier et écrit, par
archive, un fichier d'événements JSON Lines, un bilan et un état de
reprise (`data/evenements/` par défaut, hors git). Deux rejeux donnent les
mêmes octets ; `--reprendre` ne traite que les archives arrivées depuis.
Sur la copie de l'archive au 26/10/2026 : 164 096 événements d'état
initial, puis 3 présentations supprimées, et le fichier vide du 26/10
écarté sans un seul événement.

**Le bus d'événements** (mission 03) tourne en local, dans Docker, à
partir du fichier [`docker-compose.yml`](docker-compose.yml) : un Redpanda
mono-nœud, projet `pharmaflux`, tous les ports sur `127.0.0.1` (Kafka
`19092`, registre de schémas `18081`, HTTP proxy `18082`, administration
`19644`), les données dans le volume `pharmaflux-redpanda`. Les versions des
images sont épinglées dans ce fichier.

```bash
docker compose -p pharmaflux --profile console pull  # une fois : télécharge les images (beko)
docker compose -p pharmaflux up -d --wait         # démarre, attend que le courtier réponde
docker compose -p pharmaflux down                 # arrête, garde les données
docker compose -p pharmaflux down -v              # rebâtit le bus : efface le volume (aussi après un changement des propriétés de grappe)
docker compose -p pharmaflux --profile console up -d   # en plus : la console sur http://127.0.0.1:18080
```

`schemas enregistrer` pose la règle de compatibilité `BACKWARD_TRANSITIVE`
et enregistre les schémas JSON du dépôt (`src/pharmaflux/bus/schemas/`),
un sujet par topic. `publier` envoie les fichiers d'événements, dans
l'ordre, sur un topic par entité (`pharmaflux.<entite>.v1`, trois
partitions, clé = la clé de l'événement, rétention sans limite) ; la valeur
du message est la ligne du fichier à l'octet près. `publication.json`
garde ce qui est publié ; `--reprendre` ne publie que les nouveaux
fichiers. Une ligne illisible ou un message trop gros vont dans la file
`pharmaflux.echecs.v1`, et le code de sortie le dit. `verifier-bus` relit
chaque topic depuis le début, sans commit d'offset, dédoublonne par `id`,
applique les événements et compare l'état obtenu aux fichiers d'événements
de la sortie ou, avec `--racine`, au dernier snapshot retenu recalculé
depuis l'archive ; il vérifie aussi la rétention sans limite, la politique
`delete`, le type d'horodatage et les partitions de chaque topic. Toute
différence donne le code 2, comme une référence introuvable, refusée avant de
lire le bus ; les doublons d'une reprise sont rapportés, avec le fichier dont
ils viennent. Les tests qui ont besoin du courtier sont
marqués `integration` et sautés sans lui :

```bash
uv run pytest -q -m integration
```

Vérifications locales, identiques à la CI :

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
```

La CI a deux jobs : `verifier`, ces commandes plus les tests des garde-fous
du circuit, et `integration`, qui démarre le Redpanda du même fichier
compose et lance les tests marqués avec la variable
`PHARMAFLUX_INTEGRATION_EXIGEE` posée : là, un saut est un échec, un job
vert a lancé les neuf tests, puis la démo sans pause (`make demo
DEMO_OPTIONS=--sans-pause`), vérifiée par `verifier-bus`.

## Méthode

Une mission = une branche = une PR, par paliers verts, avec relecture à
contexte neuf avant publication. Le circuit, les ordres de mission, les
rapports et les relectures sont dans [`docs/`](docs/) : ils font partie de
ce que ce dépôt montre.

## Licences des données

BDPM : citation de la source et de sa date, aucune altération (l'archive
conserve les octets reçus, tels quels). Open Medic : Licence Ouverte
Etalab.
