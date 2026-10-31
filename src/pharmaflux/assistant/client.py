"""Le client Claude (Opus 5.5) et le **double** de test, derrière une même interface.

Aucun test ne construit un client réel : ils passent tous par le double (addendum 1 J). Le
client réel (``ClientClaude``) n'importe ``anthropic`` que lorsqu'on le construit — jamais à
l'import du module — et il trouve la clé où le SDK la cherche (``ANTHROPIC_API_KEY``, posée par
``infra/agents/avec-cle.sh`` que beko seul lance). ``cle_presente`` répond sans importer
``anthropic`` ni toucher le réseau, pour que « clé absente » s'arrête net (code 2).

Sortie structurée (``output_config.format``, schéma JSON brut) : le LLM rend le comportement,
le texte, les **étiquettes** des fragments cités, le motif, l'orientation et la réserve. Les
CIS traités ne lui sont pas demandés — le code les tire des fragments cités. La pensée est
adaptative (toujours active sur Opus 5.5) ; l'effort démarre à ``low`` (addendum 1 G1).
``max_tokens`` à 4 000, pensée comprise. Un ``stop_reason`` ``refusal`` ou ``max_tokens`` est
une **abstention technique**, journalisée avec sa cause. Aucun modèle de repli.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from pharmaflux.assistant.budget import MODELE, Usage

MAX_TOKENS = 4000
EFFORT_DEFAUT = "low"

# Les comportements que le LLM peut rendre (mêmes valeurs que la notation du jeu).
REPONSE, ABSTENTION, REFUS_MEDICAL = "reponse", "abstention", "refus_medical"

# Le schéma de la sortie structurée. ``citations`` porte les étiquettes (1..k) des fragments
# fournis, jamais des identifiants libres ; le code vérifie qu'elles sont parmi les fournis.
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "comportement": {"type": "string", "enum": [REPONSE, ABSTENTION, REFUS_MEDICAL]},
        "texte": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "integer"}},
        "motif": {"type": ["string", "null"]},
        "orientation": {"type": ["string", "null"]},
        "reserve": {"type": "boolean"},
    },
    "required": ["comportement", "texte", "citations", "motif", "orientation", "reserve"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class ReponseLLM:
    """Ce que le client rend : la sortie du modèle (ou une abstention technique) et le coût."""

    comportement: str
    texte: str
    citations: tuple[int, ...]
    motif: str | None
    orientation: str | None
    reserve: bool
    usage: Usage
    stop_reason: str
    technique: bool = False  # refus du modèle ou max_tokens : abstention technique
    categorie_refus: str | None = None  # stop_details.category d'un refus du modèle

    def en_dict(self) -> dict[str, Any]:
        """La sortie du modèle, pour le cache des réponses (sans le coût, qui ne se rejoue pas)."""
        return {
            "comportement": self.comportement,
            "texte": self.texte,
            "citations": list(self.citations),
            "motif": self.motif,
            "orientation": self.orientation,
            "reserve": self.reserve,
            "stop_reason": self.stop_reason,
            "technique": self.technique,
            "categorie_refus": self.categorie_refus,
        }

    @classmethod
    def du_cache(cls, donnees: dict[str, Any]) -> ReponseLLM:
        """Une réponse relue du cache : coût nul (déjà payée, ou jamais pour un cache)."""
        return cls(
            comportement=donnees["comportement"],
            texte=donnees["texte"],
            citations=tuple(donnees["citations"]),
            motif=donnees["motif"],
            orientation=donnees["orientation"],
            reserve=donnees["reserve"],
            usage=Usage(0, 0),
            stop_reason=donnees["stop_reason"],
            technique=donnees["technique"],
            categorie_refus=donnees["categorie_refus"],
        )


class ClientLLM(Protocol):
    """L'interface commune au client réel et au double : une question, une réponse structurée."""

    def repondre(
        self, systeme: str, contenu: str, *, effort: str, max_tokens: int
    ) -> ReponseLLM: ...


class CleAbsente(Exception):  # noqa: N818 (nom français voulu)
    """Aucune clé d'API dans l'environnement : l'assistant s'arrête (code 2), sans réseau."""


class ErreurAPI(Exception):  # noqa: N818 (nom français voulu)
    """L'API n'a rendu aucune réponse (surcharge, délai, réseau, statut 4xx ou 5xx), après les
    réessais du SDK : rien à journaliser, la commande s'arrête en code 2 avec une ligne lisible
    (contrôle du palier 2). Les réponses déjà obtenues sont au cache : une reprise ne les repaie
    pas."""


def cle_presente() -> bool:
    """La clé d'API est-elle dans l'environnement ? (sans importer ``anthropic``, sans réseau)."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _technique(usage: Usage, motif: str, stop_reason: str, categorie: str | None) -> ReponseLLM:
    """Une abstention technique : le modèle n'a pas rendu de réponse exploitable, mais l'appel
    est payé — son ``usage`` est porté pour que le journal le compte (addendum G)."""
    return ReponseLLM(ABSTENTION, "", (), motif, None, False, usage, stop_reason, True, categorie)


def interpreter_reponse(reponse: Any) -> ReponseLLM:
    """La réponse du SDK (ou un objet qui la mime) traduite en ``ReponseLLM``.

    Un refus du modèle, une réponse tronquée (``max_tokens``) ou une **sortie illisible** (bloc
    texte absent, JSON invalide, clé manquante) deviennent une **abstention technique avec son
    ``usage``** : l'appel payé entre toujours au journal, jamais une exception avant le décompte.
    """
    usage = Usage(
        jetons_entree=reponse.usage.input_tokens,
        jetons_sortie=reponse.usage.output_tokens,
        jetons_cache_lecture=getattr(reponse.usage, "cache_read_input_tokens", 0) or 0,
        jetons_cache_ecriture=getattr(reponse.usage, "cache_creation_input_tokens", 0) or 0,
    )
    stop = reponse.stop_reason
    if stop in ("refusal", "max_tokens"):
        details = getattr(reponse, "stop_details", None)
        categorie = getattr(details, "category", None) if details else None
        cause = "refus du modèle" if stop == "refusal" else "réponse tronquée"
        return _technique(usage, f"réponse non obtenue ({cause})", stop, categorie)
    try:
        texte = next(bloc.text for bloc in reponse.content if bloc.type == "text")
        donnees = json.loads(texte)
        return ReponseLLM(
            comportement=donnees["comportement"],
            texte=donnees["texte"],
            citations=tuple(donnees["citations"]),
            motif=donnees.get("motif"),
            orientation=donnees.get("orientation"),
            reserve=bool(donnees.get("reserve", False)),
            usage=usage,
            stop_reason=stop,
        )
    except (StopIteration, ValueError, KeyError, TypeError) as exc:
        return _technique(usage, f"réponse illisible ({type(exc).__name__})", stop, None)


class ClientClaude:
    """Le client réel. ``anthropic`` n'est importé qu'ici, à la construction (jamais aux tests).

    ``sdk`` : un objet qui mime ``anthropic.Anthropic`` (le test de ``ErreurAPI``, sans réseau) ;
    absent, le vrai client du SDK, construit seulement si la clé est là.
    """

    def __init__(self, sdk: Any = None) -> None:
        if sdk is None and not cle_presente():
            raise CleAbsente("clé absente : ANTHROPIC_API_KEY n'est pas dans l'environnement")
        import anthropic  # importé seulement à la construction, jamais à l'import du module

        self._erreur_api = anthropic.APIError
        # Typé ``Any`` : l'appel ``messages.create`` passe des littéraux dict nus (system,
        # output_config) que les TypedDict du SDK n'acceptent pas sous mypy strict, et ce client
        # thin n'est exercé que par les commandes de beko (jamais aux tests, via le double).
        self._client: Any = sdk if sdk is not None else anthropic.Anthropic()

    def repondre(self, systeme: str, contenu: str, *, effort: str, max_tokens: int) -> ReponseLLM:
        try:
            reponse = self._client.messages.create(
                model=MODELE,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": systeme, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": contenu}],
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": SCHEMA},
                },
            )
        except self._erreur_api as exc:
            statut = getattr(exc, "status_code", None)
            precision = f", statut {statut}" if statut is not None else ""
            raise ErreurAPI(
                f"l'API Claude n'a rendu aucune réponse ({type(exc).__name__}{precision})"
            ) from exc
        return interpreter_reponse(reponse)


@dataclass
class DoubleClient:
    """Le double de test : une file de réponses, servies dans l'ordre des appels.

    Chaque appel consomme la réponse suivante (ou l'unique réponse ``fixe``). Les appels sont
    comptés et leurs arguments gardés, pour vérifier qu'un cache ou une porte a bien évité
    l'appel réel. Aucun réseau, aucune clé.
    """

    file: list[ReponseLLM] = field(default_factory=list)
    fixe: ReponseLLM | None = None
    appels: list[dict[str, Any]] = field(default_factory=list)

    def repondre(self, systeme: str, contenu: str, *, effort: str, max_tokens: int) -> ReponseLLM:
        self.appels.append(
            {"systeme": systeme, "contenu": contenu, "effort": effort, "max_tokens": max_tokens}
        )
        if self.file:
            return self.file.pop(0)
        if self.fixe is not None:
            return self.fixe
        raise AssertionError("DoubleClient : aucune réponse préparée pour cet appel")
