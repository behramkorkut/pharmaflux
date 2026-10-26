# Mission 02 — contrôle du palier 1 (IeC)

**Commit contrôlé** : `370d087`. **Verdict** : palier 1 accepté **sous
réserve de trois correctifs**, à faire dans un nouveau commit avant le
palier 2. Les trois sont petits ; le troisième est le plus important.

## Vérifications rejouées

Sur l'arbre du codeur, propre, au commit `370d087` :

- ruff check et format : vert ;
- mypy strict (25 fichiers) : vert ;
- pytest : 337 tests, tous passent ;
- crochets git : conformes ; garde-fou : 17 tests, tous passent ;
- shellcheck : non rejoué. `git diff --stat a28969f 370d087` ne touche
  aucun `.sh`, et la commande a été refusée chez toi par le mode auto. Je
  ne la relance pas à ta place.

Sur la copie rapatriée du Mac, en lecture seule :

- `pharmaflux profil` : 11 fichiers, 0 bloquante, code 0 ;
- `questions verifier` : 25 conformes, 5 non calculables, 10 sans
  attendu ;
- snapshots des dernières archives des huit fichiers à clé : entités =
  lignes bien formées, 0 doublon, aucun écarté.

## Sur le fond

- **Le partage lisibilité / forme** est fait règle par règle, dans le code
  (`REGLES_DE_LISIBILITE`, `REGLES_DE_FORME`) et dans le tableau de
  l'ADR 0005, qui se correspondent. `longueur_depassee` et `hote_inconnu`
  rangés côté forme : d'accord, la valeur se lit.
- **Le contrat v1** porte ses deux raisons, avec la mesure, et le chargeur
  refuse `milliers` et `canonique` dans un contrat v0. C'est le bon
  verrou : une forme ne s'ajoute pas sans changer de version.
- **Le snapshot** ne relit jamais le fichier, partage les tuples de la
  `Lecture`, et un vide n'est pas écarté ici : c'est bien au garde-fou
  du palier 2 de le faire.
- **La non-régression** est exactement celle annoncée : `decimal_illisible`
  995 → 0, rien d'autre.
- **L'ADR 0005** est clair et ses options écartées sont les bonnes.

## Correctifs

1. **`-0,50` devient `0.50` : le signe est perdu, donc le sens change.**
   `forme_decimale` passe la partie entière par `int`, qui rend `0` pour
   `-0`. C'est juste pour un entier, faux pour un décimal : −0,50 € n'est
   pas 0,50 €. La forme canonique doit garder le signe quand la partie
   entière est `-0` (et seulement le `-` utile : `-0,00` peut rester
   `-0.00` ou devenir `0.00`, au choix, dit dans l'ADR). Ajoute le test.
   La docstring de `_entier_canonique` (« `-0` → `0` ») est à revoir
   dans le même sens.

2. **Le motif des milliers accepte des chiffres non ASCII.**
   `_motif_milliers` utilise `\d` sans `re.ASCII` : `١,٠٠٣,48` (chiffres
   arabes-indiens) est déclaré conforme et lu `1003.48`. Le reste du type
   exige des chiffres ASCII (`_entier`, et le commentaire sur « ²³ »).
   Utilise `[0-9]` ou `re.ASCII`, et ajoute le cas aux tests.

3. **Une clé normalisée qui se répète fait perdre une ligne sans rien
   dire.** L'unicité de la clé est vérifiée sur les valeurs **brutes**
   (`verification`), alors que `par_cle` est indexé par la clé
   **normalisée**. Deux clés brutes distinctes qui se normalisent pareil ne
   donnent aucune bloquante, et `depuis_lecture` garde la première ligne,
   compte la seconde en doublon, et le snapshot reste retenu. Le
   commentaire « bloquant, snapshot écarté » n'est vrai que si les brutes
   se répètent.

   Ce n'est pas théorique : `bdpm.compositions` a dans sa clé
   `designation_element` (texte) et `numero_liaison` (entier, la colonne de
   tes `01`), et `bdpm.conditions_prescription` a `condition` (texte). Une
   espace en fin de valeur ou un `01` à côté d'un `1` suffisent. Aucune
   collision dans les archives d'aujourd'hui (je l'ai mesuré), mais une
   ligne perdue est exactement ce que la décision 8 interdit.

   Correctif attendu : une collision de clé normalisée sans bloquante
   brute **écarte** le snapshot, avec un motif qui la nomme (« clé
   normalisée non unique : 2 lignes, première ligne 812 »). On écarte parce
   qu'un fichier à clé dont la clé est ambiguë ne se compare pas. Un test
   sur une fixture fabriquée (`" X"` / `"X"` dans une clé texte). Une ligne
   dans l'ADR 0005.

## Écarts

1. **Règles par type dans `contrats/normalisation.py`** et non dans
   `evenements/snapshot.py` : accepté. Le profil s'en sert, et `contrats`
   ne doit pas dépendre de `evenements`.
2. **`CONTEXTE.md` et `README.md` au palier 3** : accepté, c'est l'ordre.

## Refus signalé

Le refus de la commande composée vient du classificateur du mode auto de
Claude Code, pas du garde-fou du dépôt. Tu as relancé séparément les parties
sans téléchargement, sans contourner : c'est la bonne conduite. Rien de
cette commande n'est à faire par une autre session. Si le shellcheck devient
nécessaire, c'est-à-dire si un palier touche un `.sh`, signale-le à beko et
la CI le passera.

## Proposition d'évolution

`Content-Disposition` absent : déjà noté pour le Lot 5, rien à faire ici.

## Suite

Commite ce fichier tel quel. Fais les trois correctifs dans un nouveau
commit, réponds point par point dans
`docs/rapports/mission-02/reponse-controle-1.md`, rejoue les vérifications,
puis arrête-toi et annonce le commit. Le palier 2 commence après mon accord.
