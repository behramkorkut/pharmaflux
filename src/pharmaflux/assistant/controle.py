"""Le contrôle de la réponse par le **code**, jamais par le LLM (addendum 1 C, C3).

Deux garanties, après l'appel :

- **les citations** du LLM sont parmi les fragments fournis (vérifié dans ``chemin`` sur les
  étiquettes) ;
- **chaque nombre et chaque date** du texte se retrouve, après normalisation, dans le texte
  ou les dates des sources d'un fragment **cité**, ou dans la question. Un « 65 % » et un
  « 65% », un « 1 000 » et un « 1000 », une date « 09/09/2026 », « 9 septembre 2026 »,
  « 2026-09-09 » et « 20260909 » se ramènent à une même forme.

Un échec ne se corrige pas : la réponse devient une **abstention** journalisée (« réponse non
vérifiable »). L'instant de l'index n'est pas dans le texte du LLM — le code le rend —, donc
il n'entre pas dans le contrôle.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

_MOIS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_JMA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_COMPACT = re.compile(r"\b(\d{4})(\d{2})(\d{2})\b")
_EN_LETTRES = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(sorted(_MOIS, key=len, reverse=True)) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)
# Un nombre : des milliers séparés par une espace (fine, insécable ou ordinaire) ou non, suivis
# d'une éventuelle part décimale (virgule ou point). La virgule décimale ne porte pas d'espace
# (« 12,50 »), à la différence d'une virgule de liste (« 65, 73 »), qui sépare deux nombres.
_NOMBRE = re.compile(r"\d{1,3}(?:[^\S\r\n]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")


def _jour_valide(annee: int, mois: int, jour: int) -> bool:
    return 1 <= mois <= 12 and 1 <= jour <= 31 and 2000 <= annee <= 2099


def _dates(texte: str) -> tuple[frozenset[tuple[int, int, int]], str]:
    """Les dates du texte (année, mois, jour), et le texte avec leurs empans blanchis."""
    trouvees: set[tuple[int, int, int]] = set()
    reste = texte
    for motif, ordre in (
        (_ISO, "amj"),
        (_JMA, "jma"),
        (_EN_LETTRES, "jMa"),
        (_COMPACT, "amj"),
    ):
        morceaux = []
        fin = 0
        for trouve in motif.finditer(reste):
            date = _lire_date(trouve, ordre)
            if date is None:
                continue
            trouvees.add(date)
            morceaux.append(reste[fin : trouve.start()])
            morceaux.append(" " * (trouve.end() - trouve.start()))
            fin = trouve.end()
        morceaux.append(reste[fin:])
        reste = "".join(morceaux)
    return frozenset(trouvees), reste


def _lire_date(trouve: re.Match[str], ordre: str) -> tuple[int, int, int] | None:
    if ordre == "amj":
        annee, mois, jour = int(trouve[1]), int(trouve[2]), int(trouve[3])
    elif ordre == "jma":
        jour, mois, annee = int(trouve[1]), int(trouve[2]), int(trouve[3])
    else:  # jMa : jour, mois en lettres, année
        jour, annee = int(trouve[1]), int(trouve[3])
        mois = _MOIS[trouve[2].lower()]
    return (annee, mois, jour) if _jour_valide(annee, mois, jour) else None


def _canon_nombre(brut: str) -> str | None:
    """Un nombre écrit (« 1 000 », « 12,50 », « 65 ») ramené à une forme canonique, ou rien."""
    sans_espace = re.sub(r"[^\S\r\n]", "", brut).replace(",", ".")
    if sans_espace.count(".") > 1 or sans_espace in ("", "."):
        return None
    try:
        valeur = Decimal(sans_espace)
    except InvalidOperation:
        return None
    texte = format(valeur, "f")
    if "." in texte:
        texte = texte.rstrip("0").rstrip(".")
    return texte


def _nombres(texte: str) -> frozenset[str]:
    canon = {_canon_nombre(t.group()) for t in _NOMBRE.finditer(texte)}
    return frozenset(n for n in canon if n is not None)


def extraire(texte: str) -> tuple[frozenset[str], frozenset[tuple[int, int, int]]]:
    """Les nombres (canoniques) et les dates (année, mois, jour) d'un texte."""
    dates, reste = _dates(texte)
    return _nombres(reste), dates


def controler(texte: str, appuis: Sequence[str], question: str) -> str | None:
    """``None`` si chaque nombre et chaque date du texte s'appuient sur les citations ou la
    question ; sinon le premier élément non vérifié (le motif de l'abstention technique)."""
    nombres_appui: set[str] = set()
    dates_appui: set[tuple[int, int, int]] = set()
    for source in (question, *appuis):
        nombres, dates = extraire(source)
        nombres_appui |= nombres
        dates_appui |= dates
    nombres_texte, dates_texte = extraire(texte)
    for nombre in sorted(nombres_texte):
        if nombre not in nombres_appui:
            return f"le nombre « {nombre} » du texte n'est dans aucun fragment cité ni la question"
    for annee, mois, jour in sorted(dates_texte):
        if (annee, mois, jour) not in dates_appui:
            return (
                f"la date {jour:02d}/{mois:02d}/{annee} du texte n'est dans aucun fragment cité"
                " ni la question"
            )
    return None
