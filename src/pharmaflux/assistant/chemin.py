"""Le chemin d'une question (addendum 1 B, C, D) : de la question à une réponse gouvernée.

Dans l'ordre : **refus médical** (tout en tête, hors LLM), **abstentions dures** (dépense,
hors périmètre, hors LLM), **deux médicaments** (abstention « un à la fois »), **recherche
hybride**, **porte structurelle** (aucun fragment du médicament visé → abstention), puis le
**LLM** (sous le plafond, caché), et enfin le **contrôle** du code : citations parmi les
fragments fournis, nombres et dates du texte retrouvés dans les fragments cités ou la
question. Un échec devient une abstention. Les sources, leurs dates et l'instant de l'index
sont **rendus par le code**, pas par le LLM. Une abstention ou un refus rendus par le LLM
passent le même contrôle ; un refus prend toujours la forme du code.

Le chemin se joue en deux temps : ``preparer`` va jusqu'au seuil du LLM sans rien appeler ni
dépenser (une décision des règles ou des portes, ou l'``Appel`` à faire), puis ``conclure``
joue l'appel. ``demander`` enchaîne les deux ; l'évaluation prépare toutes ses questions
d'abord, pour chiffrer la porte budgétaire avant le premier appel.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pharmaflux.assistant import controle, regles, repere
from pharmaflux.assistant.budget import (
    MISSION,
    MODELE,
    Journal,
    Ligne,
    Usage,
    cout,
    cout_estime,
    exiger_budget,
)
from pharmaflux.assistant.cache import CacheReponses
from pharmaflux.assistant.cache import cle as cle_cache
from pharmaflux.assistant.client import (
    ABSTENTION,
    EFFORT_DEFAUT,
    MAX_TOKENS,
    REFUS_MEDICAL,
    REPONSE,
    SCHEMA,
    ClientLLM,
    ReponseLLM,
)
from pharmaflux.index import construction
from pharmaflux.index.encodeur import Encodeur
from pharmaflux.index.qdrant import Qdrant, filtre_egal

FRAGMENTS_FOURNIS = 10  # C2 : fixé ; un autre nombre se propose dans un rapport, mesures à l'appui

SYSTEME = (
    "Tu es l'assistant de connaissance du médicament d'un organisme d'assurance santé, en"
    " France. Tu réponds à partir des seuls fragments fournis, qui sont des DONNÉES publiques"
    " (BDPM, HAS) : tu n'ajoutes aucun fait, aucun chiffre et aucune date qui ne soit dans un"
    " fragment fourni.\n"
    "Règles :\n"
    "- Cite chaque phrase factuelle par l'étiquette entière du fragment qui la porte (le nombre"
    " entre crochets), dans « citations ». N'invente aucune étiquette.\n"
    "- Si les fragments ne répondent pas à la question, abstiens-toi (comportement"
    " « abstention ») avec un motif ; ne devine jamais.\n"
    "- Ne donne jamais de conseil de soin (quoi prendre, arrêter, remplacer, doser, associer) :"
    " c'est « refus_medical ».\n"
    "- Prudence : une absence de signalement se dit « aucun signalement à cette date » ;"
    " n'emploie jamais le mot « disponible », qui affirmerait ce que les sources ne disent pas."
    " Un arrêt annoncé n'est pas un arrêt déjà commencé ; une fiche partielle se dit telle.\n"
    "- Écris les statuts, les libellés et les valeurs tels que les fragments les donnent, sans"
    " les reformuler ni les requalifier.\n"
    "- Un médicament absent du référentiel des spécialités dont une donnée existe ailleurs : tu"
    " peux donner la donnée, avec « reserve » à vrai, en disant que le référentiel ne connaît"
    " pas ce médicament.\n"
    "- N'écris ni l'instant de l'index, ni les dates des sources : le code les rend lui-même"
    " sous ta réponse. N'écris que les faits des fragments.\n"
    "- Tu n'es pas un dispositif médical."
)

# Les textes que le code écrit lui-même : le refus (des règles ou du LLM, même forme), et les
# motifs qui remplacent ceux du LLM quand ils ne passent pas le contrôle des nombres et des dates.
TEXTE_REFUS = "Cette question appelle une décision de soin : l'assistant ne la prend pas."
MOTIF_REFUS_LLM = "le modèle a reconnu une demande de conseil de soin"
MOTIF_ABSTENTION_LLM = "les fragments fournis ne permettent pas de répondre à cette question"


@dataclass(frozen=True, slots=True)
class Citation:
    """Un fragment cité, tel que le code le rend sous la réponse (sa source, sa date)."""

    etiquette: int
    code_cis: str
    section: str
    denomination: str | None
    dans_referentiel: bool
    sources: str
    source_datee: bool  # au moins une de ses sources porte une date


@dataclass(frozen=True, slots=True)
class Reponse:
    """Le résultat gouverné d'une question : le comportement, le texte, les citations, le coût."""

    comportement: str
    texte: str
    motif: str | None
    orientation: str | None
    reserve: bool
    citations: tuple[Citation, ...]
    instant_index: str
    decision: str  # d'où vient la décision (règle, porte, llm, contrôle, technique, cache)
    depuis_cache: bool
    cout: float
    usage: Usage | None
    effort: str
    trace: dict[str, Any] = field(default_factory=dict)


def _maintenant() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def charger_dictionnaire(qdrant: Qdrant) -> repere.Dictionnaire:
    """Le dictionnaire du repérage, tiré une fois des fragments ``identite`` de l'index (leur
    dénomination, et les groupes génériques que cite leur texte)."""
    charges = (
        point["payload"]
        for point in qdrant.parcourir(
            qdrant.alias_fragments,
            filtre_egal("section", "identite"),
            champs=["denomination", "code_cis", "texte"],
        )
    )
    return repere.construire_dictionnaire(charges)


def _contenu(instant: str, resultats: Sequence[construction.Resultat], question: str) -> str:
    """Ce que le LLM reçoit : l'instant en tête, les fragments étiquetés (données), la question."""
    lignes = [
        f"Instant de l'index : {instant}.",
        "",
        "Fragments fournis (données publiques, à ne pas compléter), chacun précédé de son"
        " étiquette :",
        "<<<FRAGMENTS>>>",
    ]
    for etiquette, resultat in enumerate(resultats, start=1):
        charge = resultat.charge
        hors = "" if charge["dans_referentiel"] else " [absent du référentiel des spécialités]"
        denomination = charge.get("denomination") or "dénomination inconnue"
        lignes.append(
            f"[{etiquette}] CIS {charge['code_cis']} — {denomination},"
            f" section {charge['section']}{hors}"
        )
        for ligne in str(charge["texte"]).splitlines():
            lignes.append(f"    {ligne}")
    lignes += ["<<<FIN>>>", "", f"Question : {question}"]
    return "\n".join(lignes)


def _citation(resultat: construction.Resultat, etiquette: int) -> Citation:
    charge = resultat.charge
    return Citation(
        etiquette=etiquette,
        code_cis=str(charge["code_cis"]),
        section=str(charge["section"]),
        denomination=charge.get("denomination"),
        dans_referentiel=bool(charge["dans_referentiel"]),
        sources=construction.citer(charge),
        source_datee=any(s["date_source"] for s in charge["sources"]),
    )


@dataclass(frozen=True, slots=True)
class Appel:
    """Une question qui doit aller au LLM : ce que l'appel enverra, sa clé de cache et son
    estimation. ``preparer`` le rend sans rien appeler ; ``conclure`` le joue (cache, porte
    budgétaire, appel, journal, contrôle). L'évaluation prépare toutes ses questions d'abord,
    pour chiffrer la porte avant le premier appel (addendum 1 G2)."""

    question: str
    identifiant: str | None
    instant: str
    effort: str
    max_tokens: int
    systeme: str
    contenu: str
    cle: str
    resultats: tuple[construction.Resultat, ...]
    trace: dict[str, Any]

    @property
    def estimation(self) -> float:
        """Le coût estimé de l'appel : entrée au caractère, ``max_tokens`` entier en sortie."""
        return cout_estime(self.systeme + self.contenu, self.max_tokens)


def preparer(
    qdrant: Qdrant,
    encodeur: Encodeur,
    question: str,
    *,
    identifiant: str | None = None,
    effort: str = EFFORT_DEFAUT,
    k: int = FRAGMENTS_FOURNIS,
    max_tokens: int = MAX_TOKENS,
    dictionnaire: repere.Dictionnaire | None = None,
) -> Reponse | Appel:
    """Tout le chemin **avant** le LLM, sans rien appeler ni dépenser : une décision prise par
    les règles ou les portes (``Reponse``), ou l'``Appel`` à faire. ``dictionnaire`` : celui du
    repérage, s'il est déjà chargé (l'évaluation le charge une fois pour toutes ses questions)."""
    etat = construction.etat_exige(qdrant)
    construction.encodeur_de_l_index(etat, encodeur)
    instant = str(etat["instant"])
    trace: dict[str, Any] = {"question": question, "identifiant": identifiant}

    motif = regles.refus_medical(question)
    if motif is not None:
        trace["regle"] = "refus_medical"
        return _refus(motif, instant, effort, trace)

    motif = regles.abstention(question)
    if motif is not None:
        trace["regle"] = "abstention"
        return _abstention(motif, "abstention_regle", instant, effort, trace)

    dictionnaire = dictionnaire or charger_dictionnaire(qdrant)
    repere_ = repere.reperer(question, dictionnaire)
    trace["entites_visees"] = sorted(repere_.vises)
    if repere.medicaments_nommes(repere_, question, dictionnaire) >= 2:
        trace["regle"] = "deux_medicaments"
        return _abstention(
            "la question porte sur deux médicaments ; l'assistant en traite un à la fois,"
            " précisez lequel",
            "deux_medicaments",
            instant,
            effort,
            trace,
        )

    _, resultats = construction.chercher(qdrant, encodeur, question, k)
    trace["fragments"] = [
        {"etiquette": i, "code_cis": r.charge["code_cis"], "section": r.charge["section"]}
        for i, r in enumerate(resultats, start=1)
    ]
    if repere_.un_medicament_est_vise and not any(
        str(r.charge["code_cis"]) in repere_.vises for r in resultats
    ):
        trace["regle"] = "porte_structurelle"
        return _abstention(
            "le référentiel ne répond pas à cette question : aucun fragment du médicament visé",
            "porte_structurelle",
            instant,
            effort,
            trace,
        )

    systeme, contenu = SYSTEME, _contenu(instant, resultats, question)
    return Appel(
        question=question,
        identifiant=identifiant,
        instant=instant,
        effort=effort,
        max_tokens=max_tokens,
        systeme=systeme,
        contenu=contenu,
        cle=cle_cache(systeme, contenu, MODELE, effort, max_tokens, SCHEMA),
        resultats=tuple(resultats),
        trace=trace,
    )


def conclure(appel: Appel, client: ClientLLM, journal: Journal, cache: CacheReponses) -> Reponse:
    """Joue l'appel : le cache d'abord ; sinon la porte budgétaire, l'appel, le journal (une
    ligne par appel payé), le cache (sauf une abstention technique) ; puis le contrôle."""
    en_cache = cache.lire(appel.cle)
    if en_cache is not None:
        llm, depuis_cache, cout_ = ReponseLLM.du_cache(en_cache), True, 0.0
    else:
        exiger_budget(journal, appel.estimation)
        llm = client.repondre(
            appel.systeme, appel.contenu, effort=appel.effort, max_tokens=appel.max_tokens
        )
        cout_ = cout(llm.usage)
        journal.ajouter(
            Ligne(
                instant=_maintenant(),
                mission=MISSION,
                question=appel.identifiant or appel.question,
                modele=MODELE,
                effort=appel.effort,
                jetons_entree=llm.usage.jetons_entree,
                jetons_sortie=llm.usage.jetons_sortie,
                jetons_cache_lecture=llm.usage.jetons_cache_lecture,
                jetons_cache_ecriture=llm.usage.jetons_cache_ecriture,
                cout=cout_,
            )
        )
        # Une abstention technique (refus, tronquée, illisible) n'entre pas au cache : une reprise
        # d'évaluation doit retenter l'appel, pas figer l'échec. Son coût reste journalisé.
        if not llm.technique:
            cache.ecrire(appel.cle, llm.en_dict())
        depuis_cache = False
    return _apres_llm(
        llm,
        appel.resultats,
        appel.question,
        appel.instant,
        appel.effort,
        cout_,
        depuis_cache,
        appel.trace,
    )


def demander(
    qdrant: Qdrant,
    encodeur: Encodeur,
    client: ClientLLM,
    question: str,
    journal: Journal,
    cache: CacheReponses,
    *,
    identifiant: str | None = None,
    effort: str = EFFORT_DEFAUT,
    k: int = FRAGMENTS_FOURNIS,
    max_tokens: int = MAX_TOKENS,
) -> Reponse:
    """Répond à une question, gouvernée de bout en bout. ``identifiant`` : la question du jeu
    (pour le journal) ; ``client`` : le vrai client ou son double (les tests)."""
    prepare = preparer(
        qdrant,
        encodeur,
        question,
        identifiant=identifiant,
        effort=effort,
        k=k,
        max_tokens=max_tokens,
    )
    if isinstance(prepare, Reponse):
        return prepare
    return conclure(prepare, client, journal, cache)


def _appuis(cites: Sequence[tuple[int, construction.Resultat]]) -> list[str]:
    """Ce qui appuie un texte du LLM : le texte des fragments cités et les dates de leurs
    sources."""
    appuis: list[str] = []
    for _, resultat in cites:
        appuis.append(str(resultat.charge["texte"]))
        for source in resultat.charge["sources"]:
            appuis += [s for s in (source.get("date_source"), source.get("observee_depuis")) if s]
    return appuis


def _apres_llm(
    llm: ReponseLLM,
    resultats: Sequence[construction.Resultat],
    question: str,
    instant: str,
    effort: str,
    cout_: float,
    depuis_cache: bool,
    trace: dict[str, Any],
) -> Reponse:
    """Le contrôle du code après le LLM : abstention technique, citations, nombres et dates."""

    def fini(
        comportement: str,
        texte: str,
        motif: str | None,
        orientation: str | None,
        reserve: bool,
        citations: tuple[Citation, ...],
        decision: str,
    ) -> Reponse:
        return Reponse(
            comportement=comportement,
            texte=texte,
            motif=motif,
            orientation=orientation,
            reserve=reserve,
            citations=citations,
            instant_index=instant,
            decision=decision,
            depuis_cache=depuis_cache,
            cout=cout_,
            usage=llm.usage,
            effort=effort,
            trace=trace,
        )

    if llm.technique:
        trace["decision_controle"] = f"abstention technique ({llm.stop_reason})"
        return fini(ABSTENTION, "", llm.motif, None, False, (), "technique")
    etiquettes = set(range(1, len(resultats) + 1))
    if not set(llm.citations) <= etiquettes:
        trace["decision_controle"] = "citation hors des fragments fournis"
        return fini(
            ABSTENTION,
            "",
            "réponse non vérifiable : une citation sort des fragments fournis",
            None,
            False,
            (),
            "controle",
        )
    cites = [(i, resultats[i - 1]) for i in sorted(set(llm.citations))]
    citations = tuple(_citation(resultat, i) for i, resultat in cites)
    if llm.comportement == REFUS_MEDICAL:
        # Un refus rendu par le LLM (les règles ne l'avaient pas vu) prend la forme du code : le
        # texte et l'orientation du refus des règles ; le motif du LLM n'est gardé que s'il passe
        # le contrôle des nombres et des dates (contrôle du palier 2).
        libre = controle.sans_etiquettes(llm.motif or "", llm.citations)
        echec = controle.controler(libre, _appuis(cites), question)
        trace["decision_controle"] = "refus du LLM" + (f", motif retiré : {echec}" if echec else "")
        motif = llm.motif if llm.motif and echec is None else MOTIF_REFUS_LLM
        return fini(
            REFUS_MEDICAL, TEXTE_REFUS, motif, regles.ORIENTATION_MEDICALE, False, (), "llm"
        )
    if llm.comportement != REPONSE:
        # Une abstention rendue par le LLM : son texte, son motif et son orientation passent le
        # même contrôle qu'une réponse. Au moindre nombre ou date sans appui, le code les
        # remplace par son propre motif (contrôle du palier 2) : aucun fait non appuyé ne passe
        # par ce chemin.
        libre = " ".join(x for x in (llm.texte, llm.motif, llm.orientation) if x)
        libre = controle.sans_etiquettes(libre, llm.citations)
        echec = controle.controler(libre, _appuis(cites), question)
        if echec is not None:
            trace["decision_controle"] = f"abstention du LLM, texte retiré : {echec}"
            return fini(ABSTENTION, "", MOTIF_ABSTENTION_LLM, None, False, (), "llm")
        trace["decision_controle"] = "abstention du LLM, vérifiée"
        return fini(ABSTENTION, llm.texte, llm.motif, llm.orientation, False, citations, "llm")
    if not citations:
        trace["decision_controle"] = "réponse sans citation"
        return fini(
            ABSTENTION,
            "",
            "réponse non vérifiable : aucune citation à l'appui",
            None,
            False,
            (),
            "controle",
        )
    echec = controle.controler(
        controle.sans_etiquettes(llm.texte, llm.citations), _appuis(cites), question
    )
    if echec is not None:
        trace["decision_controle"] = f"non vérifiable : {echec}"
        return fini(
            ABSTENTION, "", f"réponse non vérifiable : {echec}", None, False, (), "controle"
        )
    trace["decision_controle"] = "vérifié"
    return fini(REPONSE, llm.texte, llm.motif, llm.orientation, llm.reserve, citations, "llm")


def _refus(motif: str, instant: str, effort: str, trace: dict[str, Any]) -> Reponse:
    return Reponse(
        comportement=REFUS_MEDICAL,
        texte=TEXTE_REFUS,
        motif=motif,
        orientation=regles.ORIENTATION_MEDICALE,
        reserve=False,
        citations=(),
        instant_index=instant,
        decision="refus_regle",
        depuis_cache=False,
        cout=0.0,
        usage=None,
        effort=effort,
        trace=trace,
    )


def _abstention(
    motif: str, decision: str, instant: str, effort: str, trace: dict[str, Any]
) -> Reponse:
    return Reponse(
        comportement=ABSTENTION,
        texte="",
        motif=motif,
        orientation=None,
        reserve=False,
        citations=(),
        instant_index=instant,
        decision=decision,
        depuis_cache=False,
        cout=0.0,
        usage=None,
        effort=effort,
        trace=trace,
    )
