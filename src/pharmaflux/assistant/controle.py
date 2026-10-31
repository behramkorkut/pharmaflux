"""Le contrôle de la réponse par le **code**, jamais par le LLM (addendum 1 C, C3).

Deux garanties, après l'appel :

- **les citations** du LLM sont parmi les fragments fournis (vérifié dans ``chemin`` sur les
  étiquettes) ;
- **chaque nombre et chaque date** du texte se retrouve, après normalisation, dans le texte
  ou les dates des sources d'un fragment **cité**, ou dans la question. Un « 65 % » et un
  « 65% », un « 1 000 » et un « 1000 », une date « 09/09/2026 », « 9 septembre 2026 » et
  « 2026-09-09 » se ramènent à une même forme. Une date d'appui appuie aussi son année seule
  (« en 2026 ») et son mois (« juin 2026 ») ; un mois écrit sans jour se vérifie contre les mois
  des dates d'appui. Le jour et le mois sans année ne sont jamais des nombres appuyés.

Les dates se lisent de 1900 à 2099 (les AMM anciennes : 1978, 1985). La forme compacte
« 20260909 », celle de la BDPM brute, ne se lit que dans une **valeur attendue** du jeu
(``compacte=True``, la notation) : dans un texte, elle se confond avec un montant à huit chiffres
(« 20101010 »), et le texte des fragments rend ses dates en ISO. Un CIS, un CIP13 ou un montant
ne sont donc jamais lus comme une date par le contrôle. La notation de l'évaluation se sert du
même normaliseur pour chercher une valeur attendue dans le texte.

Les **étiquettes de citation** que le LLM écrit dans son texte (« … 2,18 € [2] ») ne sont pas des
faits : celles qu'il a déclarées dans « citations » sont retirées avant le contrôle
(``sans_etiquettes``). Une étiquette non déclarée reste, et son nombre doit s'appuyer comme un
autre. Sans cela, le « 2 » de « [2] » rendait non vérifiable une réponse juste (douze sur
quarante-neuf à l'évaluation du palier 3 de la mission 08).

Un échec ne se corrige pas : la réponse devient une **abstention** journalisée (« réponse non
vérifiable »). L'instant de l'index n'est pas dans le texte du LLM — le code le rend —, donc
il n'entre pas dans le contrôle.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
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
_NOMS_MOIS = "|".join(sorted(_MOIS, key=len, reverse=True))
# Le jour peut porter l'ordinal du premier du mois (« 1er juillet 2027 », relecture 1, point 3).
_EN_LETTRES = re.compile(r"\b(\d{1,2})(?:er)?\s+(" + _NOMS_MOIS + r")\s+(\d{4})\b", re.IGNORECASE)
# Un mois sans jour (« juin 2026 »), cherché après les dates entières, qui sont déjà blanchies.
_MOIS_ANNEE = re.compile(r"\b(" + _NOMS_MOIS + r")\s+(\d{4})\b", re.IGNORECASE)
# Un nombre : des milliers séparés par une espace (fine, insécable ou ordinaire) ou non, suivis
# d'une éventuelle part décimale (virgule ou point). La virgule décimale ne porte pas d'espace
# (« 12,50 »), à la différence d'une virgule de liste (« 65, 73 »), qui sépare deux nombres.
# Au début, (?<!\w) empêche de commencer au milieu d'un code alphanumérique (« CIP13 3400… » ne
# doit pas donner « 13 340 », ni « P01BC02 » donner « 1 »). À la fin, (?!\d) interdit seulement un
# chiffre qui suit (pas de coupure au milieu d'un nombre) mais laisse une unité collée : « 250mg »
# et « 5ml » sont lus, pour qu'un nombre inventé et collé à son unité ne passe pas inaperçu.
_NOMBRE = re.compile(r"(?<!\w)(?:\d{1,3}(?:[^\S\r\n]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?!\d)")


def _jour_valide(annee: int, mois: int, jour: int) -> bool:
    return 1 <= mois <= 12 and 1 <= jour <= 31 and 1900 <= annee <= 2099


def _dates(
    texte: str, compacte: bool = False
) -> tuple[frozenset[tuple[int, int, int]], frozenset[tuple[int, int]], str]:
    """Les dates du texte (année, mois, jour), les mois sans jour (année, mois), et le texte
    avec leurs empans blanchis. ``compacte`` : lire aussi « AAAAMMJJ » (une valeur attendue)."""
    trouvees: set[tuple[int, int, int]] = set()
    reste = texte
    motifs = [(_ISO, "amj"), (_JMA, "jma"), (_EN_LETTRES, "jMa")]
    if compacte:
        motifs.append((_COMPACT, "amj"))
    for motif, ordre in motifs:
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
    mois_seuls: set[tuple[int, int]] = set()
    for trouve in _MOIS_ANNEE.finditer(reste):
        annee = int(trouve[2])
        if 1900 <= annee <= 2099:
            mois_seuls.add((annee, _MOIS[trouve[1].lower()]))
            reste = (
                reste[: trouve.start()]
                + " " * (trouve.end() - trouve.start())
                + reste[trouve.end() :]
            )
    return frozenset(trouvees), frozenset(mois_seuls), reste


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


def elements(
    texte: str, *, compacte: bool = False
) -> tuple[frozenset[str], frozenset[tuple[int, int, int]], frozenset[tuple[int, int]]]:
    """Les nombres (canoniques), les dates (année, mois, jour) et les mois sans jour (année,
    mois) d'un texte ; ``compacte`` pour une valeur attendue (« 20260909 »)."""
    dates, mois_seuls, reste = _dates(texte, compacte)
    return _nombres(reste), dates, mois_seuls


def extraire(texte: str) -> tuple[frozenset[str], frozenset[tuple[int, int, int]]]:
    """Les nombres (canoniques) et les dates (année, mois, jour) d'un texte."""
    nombres, dates, _ = elements(texte)
    return nombres, dates


# Une étiquette de citation dans le texte : « [2] », « [1, 3] », « [1; 3] ».
_ETIQUETTES = re.compile(r"\[\s*(\d+(?:\s*[,;]\s*\d+)*)\s*\]")


def sans_etiquettes(texte: str, declarees: Collection[int]) -> str:
    """Le texte sans les étiquettes de citation que le LLM a déclarées : ce sont des renvois vers
    les fragments, que le code rend lui-même, pas des nombres à appuyer. Une étiquette dont un
    nombre n'est pas déclaré reste telle quelle."""

    def blanchir(trouve: re.Match[str]) -> str:
        nombres = {int(n) for n in re.findall(r"\d+", trouve[1])}
        return " " if nombres <= set(declarees) else trouve[0]

    return _ETIQUETTES.sub(blanchir, texte)


def controler(texte: str, appuis: Sequence[str], question: str) -> str | None:
    """``None`` si chaque nombre et chaque date du texte s'appuient sur les citations ou la
    question ; sinon le premier élément non vérifié (le motif de l'abstention technique)."""
    nombres_appui: set[str] = set()
    dates_appui: set[tuple[int, int, int]] = set()
    mois_appui: set[tuple[int, int]] = set()
    for source in (question, *appuis):
        nombres, dates, mois_seuls = elements(source)
        nombres_appui |= nombres
        dates_appui |= dates
        mois_appui |= mois_seuls
    # Une date d'appui appuie aussi son mois et son année écrits seuls.
    mois_appui |= {(annee, mois) for annee, mois, _ in dates_appui}
    nombres_appui |= {str(annee) for annee, _ in mois_appui}
    nombres_texte, dates_texte, mois_texte = elements(texte)
    for nombre in sorted(nombres_texte):
        if nombre not in nombres_appui:
            return f"le nombre « {nombre} » du texte n'est dans aucun fragment cité ni la question"
    for annee, mois, jour in sorted(dates_texte):
        if (annee, mois, jour) not in dates_appui:
            return (
                f"la date {jour:02d}/{mois:02d}/{annee} du texte n'est dans aucun fragment cité"
                " ni la question"
            )
    for annee, mois in sorted(mois_texte):
        if (annee, mois) not in mois_appui:
            return (
                f"le mois {mois:02d}/{annee} du texte n'est dans aucun fragment cité ni la question"
            )
    return None
