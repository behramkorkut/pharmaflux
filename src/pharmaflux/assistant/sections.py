"""La section qu'une question demande (mission 09, addendum 1 G : le rappel par section).

Constat de la mission 08 (``avis_has-003``, OZEMPIC) : le médicament visé avait bien sa
section dans l'index, mais aucun des dix fragments fournis n'en venait. La réponse retenue est
une **table écrite** : des mots de la question vers les sections de l'index. Quand un
médicament est visé et qu'aucun des dix fragments ne lui appartient dans la section demandée,
le chemin joindra sa première partie à la place du dernier fragment d'un autre CIS.

La table est écrite et committée **avant** les questions neuves de la v2 qui la mesurent ; elle
ne bouge plus après leur commit sans le dire au rapport. Elle n'est branchée sur le chemin
qu'après ce commit (addendum 1 G, H).

Les mots se comparent après le tokenizer de l'index (``index.lexical`` : minuscules, sans
accents) ; une expression de plusieurs mots doit paraître telle quelle, mots consécutifs.
"""

from __future__ import annotations

from pharmaflux.index import lexical

# (mots ou expressions de la question, sections de l'index), dans l'ordre de lecture.
# Changée une fois, au palier 3 (controle-palier-2.md, question 1), et la dernière : le dernier
# SMR ou ASMR d'un médicament est toujours dans le fragment ``avis`` de la BDPM, alors qu'une page
# d'avis peut être plus ancienne. « SMR » et « ASMR » demandent donc ``avis`` seul, et le mot
# « avis », trop général, ne demande plus rien. Mesurée sur avis_has-019 à -023, figées avant.
TABLE: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (
            "smr",
            "asmr",
            "service medical rendu",
            "amelioration du service medical rendu",
        ),
        ("avis",),
    ),
    (
        ("commission de la transparence", "has", "haute autorite de sante"),
        ("avis_has", "avis"),
    ),
    (
        (
            "rupture",
            "ruptures",
            "tension",
            "tensions",
            "approvisionnement",
            "remise a disposition",
            "arret de commercialisation",
            "signalement",
            "signalements",
            "mitm",
            "interet therapeutique majeur",
        ),
        ("disponibilite",),
    ),
    (
        (
            "prix",
            "rembourse",
            "remboursement",
            "rembourses",
            "taux",
            "presentation",
            "presentations",
            "cip13",
        ),
        ("presentations",),
    ),
    (
        (
            "information importante",
            "informations importantes",
            "securite",
            "lettre aux professionnels",
        ),
        ("informations",),
    ),
    (
        (
            "composition",
            "substance active",
            "substances actives",
            "titulaire",
            "laboratoire",
            "generique",
            "generiques",
            "princeps",
            "conditions de prescription",
            "liste i",
            "liste ii",
            "autorisation de mise sur le marche",
            "amm",
        ),
        ("identite",),
    ),
)


def sections_demandees(question: str) -> tuple[str, ...]:
    """Les sections que demandent les mots de la question, dans l'ordre de la table, sans double."""
    jetons = lexical.jetons(question)
    texte = f" {' '.join(jetons)} "
    sections: list[str] = []
    for mots, cibles in TABLE:
        if any(f" {' '.join(lexical.jetons(m))} " in texte for m in mots):
            sections += [s for s in cibles if s not in sections]
    return tuple(sections)
