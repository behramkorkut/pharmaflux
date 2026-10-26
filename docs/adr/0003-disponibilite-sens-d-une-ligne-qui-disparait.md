# ADR-0003 — Disponibilité : une ligne qui disparaît est une fin de publication, pas une remise à disposition

**Statut :** **proposé**, à revoir au plus tard le **07/12/2026** · **Date :** 2026-10-26 · **Mission :** 01
**Remplace / remplacé par :** —

## Contexte

`CIS_CIP_Dispo_Spec.txt` reprend les fiches « Disponibilité des produits
de santé » de l'ANSM (`docs/donnees/bdpm.disponibilite.md`, archive du
24/10/2026) : 703 lignes, 679 CIS, 290 fiches distinctes. Quatre statuts :
tension d'approvisionnement 499, **remise à disposition 119**, rupture de
stock 61, arrêt de commercialisation 24. La date de remise à disposition
est renseignée sur les 119 lignes de statut 4 et sur elles seules, toujours
égale à la date de début. 47 lignes ont un début postérieur à leur mise à
jour (un arrêt annoncé au `01/07/2027`). Aucune combinaison de colonnes
n'est unique ; 5 lignes entières sont en doublon. Le PRD v0.1 (§6.3)
lisait une ligne qui disparaît comme une « fin de la situation (remise à
disposition probable) ». L'archive ne compte encore qu'une version du
fichier (datée du 21/10 par la page BDPM) : aucune disparition n'a été
observée.

## Décision

**La remise à disposition est un statut explicite du fichier (code 4,
daté). Une ligne qui disparaît est une fin de publication de la fiche par
l'ANSM**, qui survient après une remise (la ligne 4 reste un temps puis
part), après un arrêt de commercialisation, ou par retrait ou correction de
la fiche ; ce n'est pas, en règle, une remise à disposition. L'entité
suivie est la **fiche** (CIS, CIP13, lien ANSM), comparée ligne à ligne.
Tant que cet ADR est « proposé », l'assistant (Lot 3) dit d'une ligne
disparue : « la fiche n'est plus publiée par l'ANSM depuis le <date> », sans
affirmer de remise à disposition.

**Méthode d'observation**, sur les archives successives, par fiche :
(a) combien de lignes passent par le statut 4 avant de disparaître, et
combien disparaissent directement depuis 1 ou 2 ; (b) la durée de vie d'une
ligne 4 ; (c) si une ligne disparue réapparaît, et avec quel statut ;
(d) la fréquence de changement du fichier. Les archives se listent avec
`pharmaflux.bronze.lister`, se lisent avec les contrats, et deux versions se
comparent sur l'ensemble des triplets (CIS, CIP13, lien).

**Critère de passage à « accepté »** : au moins trente disparitions
observées, dont au moins quatre sur cinq précédées d'un statut 4 ou d'un
statut 3 sur la même fiche. Si la majorité des disparitions viennent
directement d'un statut 1 ou 2, la lecture du PRD v0.1 reprend du poids
(la fin de la situation ne serait pas toujours publiée) et l'ADR est
réécrit, avec une règle d'inférence prudente et datée.

## Conséquences

- Le Lot 1 émet un événement `supprimee` daté pour une fiche disparue, sans
  en déduire un statut ; le statut 4 donne un événement `modifiee` ordinaire.
- Le Lot 3 ne répond jamais « remis à disposition » à partir d'une
  disparition ; il cite le dernier statut publié et sa date.
- À surveiller : les quatre mesures ci-dessus, relevées au plus tard le
  07/12/2026 par l'IeC ou le codeur, avec les archives alors disponibles
  (environ six semaines, soit quelques dizaines de transitions si le
  fichier change toutes les semaines).

## Options écartées

| Option | Pourquoi pas |
|---|---|
| Disparition = remise à disposition probable (PRD v0.1) | contredit par le fichier : la remise est un statut daté, et des tensions de 2023 sont toujours publiées alors qu'aucune remise antérieure à 2025 ne l'est |
| Ignorer les disparitions | une fiche qui part est une information (fin d'arrêt annoncé, correction) ; l'événement `supprimee` doit exister |
| Déduire le statut de `CIS_bdpm.txt` (commercialisé ou non) | autre granularité (spécialité, pas fiche) et autre rythme de mise à jour ; 34 lignes de Dispo_Spec portent déjà sur des CIS « Non commercialisée » |

## Références

PRD v0.2 §6.3, §9 (risque « sens d'une disparition ») · ordre de mission 01
(§0 E, question 3 ; addendum 1) · `docs/rapports/mission-01/points-a-trancher.md`
(E) · `docs/donnees/bdpm.disponibilite.md` · `docs/donnees/README.md`.
