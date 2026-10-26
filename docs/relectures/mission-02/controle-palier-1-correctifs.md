# Mission 02 — contrôle des correctifs du palier 1 (IeC)

**Commit contrôlé** : `95958dc`. **Verdict** : les trois correctifs sont
acceptés, et le palier 1 avec eux. Le palier 2 peut commencer.

## Vérifications rejouées

Sur l'arbre du codeur, propre :

- ruff check et format : vert ;
- mypy, 25 fichiers : vert ;
- pytest : 347 tests, tous passent ;
- crochets git et garde-fou : OK ;
- `profil` : 11 fichiers, 0 bloquante ;
- `questions verifier` : 25 / 5 / 10.

## Les trois correctifs

J'ai rejoué mes trois sondes du contrôle.

1. `-0,50` donne `-0.50`, et `-0,00` donne `0.00`. Le choix est écrit
   dans l'ADR 0005 : accepté.
2. Les chiffres arabes-indiens (`١,٠٠٣,48`) sont maintenant refusés : le
   motif est `[0-9]`.
3. Une clé normalisée qui se répète écarte le snapshot, avec un motif
   lisible. Les tests portent sur les deux contrats exposés, et l'ADR a
   son paragraphe.

**Une remarque, sans correctif.** Quand des clés **brutes** se répètent,
le motif nomme la bloquante `cle_non_unique` et ajoute la collision
normalisée, ce qui fait double emploi. Le motif reste juste, et ce cas est
déjà écarté. Tu peux garder les deux mentions, ou n'ajouter la seconde que
lorsqu'il n'y a pas de bloquante brute, à ton choix, au palier 2.

## Suite

Commite ce fichier tel quel, puis passe au palier 2 : décisions 3, 4, 5 et
6, ordre et addendum 1. À la fin du palier : vérifications, rapport, un
commit, et tu t'arrêtes.
