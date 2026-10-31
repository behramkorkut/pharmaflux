# Mission 09 — décision de l'IeC sur la mesure du palier 4

**Objet** : la mesure de `9694be7`. Avec la règle stricte (une page ne se
rattache qu'aux fiches que le référentiel nomme), 121 pages sur 721 perdraient
tout rattachement, dont 18 dans le jeu. Le codeur propose trois voies.
**Décision : la voie C.** La règle A s'applique, et la perte se rend visible.
Reprends au point 2 de `decision-question-2.md`.

## Pourquoi C

- **Le projet a déjà tranché ce cas.** Une fiche absent du référentiel n'a ni
  dénomination ni statut d'AMM. La v1 attend déjà une abstention pour un tel
  CIS (`disponibilite`, CIS 68705771, depuis la mission 08). L'identité d'un
  médicament vient du référentiel, pas du titre d'une page. Répondre sur
  KISUNLA à partir d'une page rattachée à une fiche sans nom contredirait
  cette règle.
- **On ne perd rien de la collecte.** Les 121 pages restent dans l'archive,
  immuable, et dans le manifeste. Seul l'index les écarte, et l'index se
  reconstruit.
- **B laisse le défaut en place.** La page « Obésité » de MOUNJARO n'a que des
  CIS absents : la question 2 resterait à la merci de son classement.

## Ce que C demande en plus de A

1. **Un rattachement recalculé à chaque construction**, contre le référentiel
   du moment. Quand une de ces spécialités entre au référentiel (une première
   commercialisation, par exemple), sa page doit revenir dans l'index à la
   construction suivante, ou à la mise à jour incrémentale, sans nouvelle
   collecte. Un test le prouve sur une fixture : la page est écartée avec un
   référentiel sans la fiche, puis rattachée avec la fiche.
2. **La perte rendue visible.** `index etat` et le bilan de construction
   comptent et listent les « pages sans fiche du référentiel », comme les
   contrôles de dossier impossibles. `index verifier` les compte aussi.
3. **La limite écrite dans l'ADR 0013**, avec les chiffres de la mesure
   (121 pages, 16,8 %, 1 111 fragments) et les exemples (médicaments récents
   ou pas encore commercialisés). Le profil `has.pages_avis.md` le dit aussi.

## Les questions neuves du point 2

Elles restent tirées par une règle écrite, sans LLM, et figées dans un commit
avant le changement :
- **au moins trois questions sur des pages mixtes**, de la forme de la
  question 2, sans MOUNJARO. Attendu : une réponse qui cite un fragment d'une
  fiche du référentiel ;
- **au moins une question sur une page qui n'a que des CIS absents**, parmi
  les 18 du jeu, de la même forme. Attendu : une abstention, au motif que le
  médicament n'est pas dans le référentiel, avec l'orientation vers la HAS.
  C'est la mesure de la perte.

Le reste de `decision-question-2.md` tient : un commit qui ne change que le
rattachement, l'état et leurs tests, puis la mémoire sur les 721 pages,
`--estimer`, et les commandes pour beko.
