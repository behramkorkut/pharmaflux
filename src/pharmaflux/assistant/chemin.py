"""Le chemin d'une question (addendum 1 B, C, D) : de la question à une réponse gouvernée.

Dans l'ordre : **refus médical** (tout en tête, hors LLM), **abstentions dures** (dépense,
hors périmètre, hors LLM), **deux médicaments** (abstention « un à la fois »), **recherche
hybride**, **porte structurelle** (aucun fragment du médicament visé → abstention), puis le
**LLM** (sous le plafond, caché), et enfin le **contrôle** du code : citations parmi les
fragments fournis, nombres et dates du texte retrouvés dans les fragments cités ou la
question. Un échec devient une abstention. Les sources, leurs dates et l'instant de l'index
sont **rendus par le code**, pas par le LLM.
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
    "- Prudence : « aucun signalement » ne veut pas dire « disponible » ; un arrêt annoncé n'est"
    " pas un arrêt déjà commencé ; une fiche partielle se dit telle. Ne requalifie pas un"
    " statut.\n"
    "- Un médicament absent du référentiel des spécialités dont une donnée existe ailleurs : tu"
    " peux donner la donnée, avec « reserve » à vrai, en disant que le référentiel ne connaît"
    " pas ce médicament.\n"
    "- N'écris ni l'instant de l'index, ni les dates des sources : le code les rend lui-même"
    " sous ta réponse. N'écris que les faits des fragments.\n"
    "- Tu n'es pas un dispositif médical."
)


@dataclass(frozen=True, slots=True)
class Citation:
    """Un fragment cité, tel que le code le rend sous la réponse (sa source, sa date)."""

    etiquette: int
    code_cis: str
    section: str
    denomination: str | None
    dans_referentiel: bool
    sources: str


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


def _dictionnaire(qdrant: Qdrant) -> repere.Dictionnaire:
    """Le dictionnaire du repérage, tiré une fois des fragments ``identite`` de l'index."""
    charges = (
        point["payload"]
        for point in qdrant.parcourir(
            qdrant.alias_fragments,
            filtre_egal("section", "identite"),
            champs=["denomination", "code_cis"],
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

    dictionnaire = _dictionnaire(qdrant)
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
    cle_ = cle_cache(systeme, contenu, MODELE, effort, max_tokens, SCHEMA)
    en_cache = cache.lire(cle_)
    if en_cache is not None:
        llm, depuis_cache, cout_ = ReponseLLM.du_cache(en_cache), True, 0.0
    else:
        exiger_budget(journal, cout_estime(systeme + contenu, max_tokens))
        llm = client.repondre(systeme, contenu, effort=effort, max_tokens=max_tokens)
        cout_ = cout(llm.usage)
        journal.ajouter(
            Ligne(
                instant=_maintenant(),
                mission=MISSION,
                question=identifiant or question,
                modele=MODELE,
                effort=effort,
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
            cache.ecrire(cle_, llm.en_dict())
        depuis_cache = False
    return _apres_llm(llm, resultats, question, instant, effort, cout_, depuis_cache, trace)


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
    if llm.comportement != REPONSE:
        trace["decision_controle"] = f"le LLM rend « {llm.comportement} »"
        comportement = REFUS_MEDICAL if llm.comportement == REFUS_MEDICAL else ABSTENTION
        return fini(comportement, llm.texte, llm.motif, llm.orientation, False, citations, "llm")
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
    appuis: list[str] = []
    for _, resultat in cites:
        appuis.append(str(resultat.charge["texte"]))
        for source in resultat.charge["sources"]:
            appuis += [s for s in (source.get("date_source"), source.get("observee_depuis")) if s]
    echec = controle.controler(llm.texte, appuis, question)
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
        texte="Cette question appelle une décision de soin : l'assistant ne la prend pas.",
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
