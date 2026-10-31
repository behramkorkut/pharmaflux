"""Les décisions prises **hors du LLM** : le refus médical et les abstentions dures (addendum 1
B, D). Un lexique et des motifs français, testés sur la v1 entière (aucun réseau).

Ordre du chemin : le **refus médical tout en tête** (B1), avant la recherche ; puis les
**abstentions dures** (dépense avant le Lot 4, sujet manifestement hors périmètre, effets
indésirables). Le refus est réservé au **conseil** — ce qu'il faut *faire* (prendre, arrêter,
remplacer, doser, associer), ou une situation individuelle (grossesse, « dans mon cas ». Une
question tournée vers « mon traitement » qui ne demande **aucune décision** n'est pas un refus
(la zone grise de D1 : on donnera le fait, sourcé et daté). Une question générale sur les
effets indésirables, sans personne, est une **abstention** hors périmètre, pas un refus.

Deux tests portent sur la v1 entière (test_assistant) : chaque question ``medical`` déclenche
le refus, et **aucune** question d'une autre catégorie ne le déclenche — un faux positif est
un défaut, au même titre qu'un oubli.
"""

from __future__ import annotations

from pharmaflux.index import lexical

# Le cadre d'une demande de décision : « puis-je … ? », « dois-je … ? », « faut-il … ? », et les
# tournures de même structure (« peut-on », « mon fils peut-il », « je peux », « est-ce que
# je … », « est-il possible de », relecture 1, point 2). Le tokenizer de l'index déplie
# « puis-je » en « puis je » : on cherche la suite aplatie, en mots entiers (« depuis je » n'est
# pas « puis je »).
_CADRE_DECISION = (
    "puis je",
    "dois je",
    "faut il",
    "peut on",
    "peut il",
    "peut elle",
    "peuvent ils",
    "peuvent elles",
    "je peux",
    "on peut",
    "doit on",
    "doit il",
    "doit elle",
    "je dois",
    "on doit",
    "est il possible de",
    "est ce que je",
    "est ce qu on",
)
# Les verbes d'un geste de soin : la question demande quoi faire d'un médicament.
_VERBES_SOIN = frozenset(
    {
        "prendre",
        "arreter",
        "remplacer",
        "substituer",
        "donner",
        "continuer",
        "associer",
        "augmenter",
        "diminuer",
        "interrompre",
        "combiner",
        "melanger",
        "doser",
        "dose",
    }
)
# Une situation individuelle : le refus ne s'y prononce jamais, même sans verbe de soin.
_MARQUEURS_PERSONNELS = ("grossesse", "enceinte", "allaitement", "allaite", "dans mon cas")

# L'orientation d'un refus médical (annexe B, D) : vers un professionnel, et le rappel que
# l'assistant n'est pas un dispositif médical.
ORIENTATION_MEDICALE = (
    "cette décision revient à un médecin ou à un pharmacien ; l'assistant n'est pas un"
    " dispositif médical et ne donne aucun conseil de soin"
)


def _aplatir(question: str) -> str:
    """La question en flux de jetons (minuscules, accents dépliés), pour chercher des suites."""
    return " ".join(lexical.jetons(question))


def refus_medical(question: str) -> str | None:
    """Le motif du refus si la question demande un conseil de soin, sinon ``None`` (B1, D1)."""
    flux = _aplatir(question)
    for marqueur in _MARQUEURS_PERSONNELS:
        if marqueur in flux:
            return f"situation de santé individuelle ({marqueur})"
    mots = set(flux.split())
    gestes = mots & _VERBES_SOIN
    if gestes and any(f" {cadre} " in f" {flux} " for cadre in _CADRE_DECISION):
        return f"la question demande une décision de soin (« {sorted(gestes)[0]} »)"
    return None


def abstention(question: str) -> str | None:
    """Le motif d'une abstention dure si une règle la décide, sinon ``None`` (B, D).

    Dépense remboursée (Open Medic, au Lot 4), sujet manifestement hors périmètre (tarif d'une
    complémentaire, conseil d'achat), effets indésirables (notice et RCP, pas nos données).
    """
    flux = _aplatir(question)
    mots = set(flux.split())
    if "depense" in flux or ("montant" in mots and "rembours" in flux):
        return "la dépense remboursée (Open Medic) n'est pas disponible avant le Lot 4"
    if "boites" in mots and "rembours" in flux:
        return "les volumes remboursés (Open Medic) ne sont pas disponibles avant le Lot 4"
    if "cout moyen" in flux:
        return "le coût moyen remboursé (Open Medic) n'est pas disponible avant le Lot 4"
    if "complementaire" in mots or "mutuelle" in mots:
        return "les tarifs des complémentaires ne sont dans aucune source du projet"
    if "acheter" in mots and any(x in flux for x in ("prix", "moins cher", "plus bas", "pas cher")):
        return "le projet ne connaît pas les prix de vente et ne recommande aucun achat"
    if "effet indesirable" in flux or "effets indesirables" in flux:
        return (
            "les effets indésirables figurent dans la notice et le RCP, pas dans les données"
            " structurées du projet"
        )
    return None
