"""Garde-fou de volume : retenu, écarté, en attente, confirmé (ADR 0006).

Par fichier, dans l'ordre des archives. Le **vide** (aucune ligne bien formée)
et le **bloquant** (snapshot écarté par la vérification) sont écartés sans
appel : jamais en attente, jamais confirmés. Un snapshot qui perd plus de
``SEUIL_PERTE`` des lignes bien formées du dernier retenu est **en attente** ;
il est **confirmé** si un passage ultérieur du manifeste revoit son empreinte
(``inchange``), ou si l'archive suivante, ni vide ni bloquante, a au plus
(1 + seuil) fois ses lignes : la source maintient la baisse. Sinon il est
écarté dès qu'une archive postérieure existe, et reste en attente tant qu'il
n'y a rien après lui. Un snapshot écarté ou en attente ne produit jamais
d'événement ; la comparaison suivante repart du dernier retenu et porte le
cumul. ``Suivi`` déroule cette règle sur une suite de snapshots ; la lecture
du bronze et du manifeste, l'écriture et la reprise sont dans ``rejeu``. Un
``Resultat`` ne garde pas ses événements : il les recalcule à la demande, et
``Suivi`` ne garde rien de ce qu'il a produit (mission 03, palier 1).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from pharmaflux.evenements.comparaison import comparer
from pharmaflux.evenements.schema import Evenement
from pharmaflux.evenements.snapshot import Snapshot

SEUIL_PERTE = 0.01  # 1 % : les pertes réelles sont cent fois en dessous (§0 F de la mission 02)


class Decision(StrEnum):
    RETENU = "retenu"
    ECARTE = "ecarte"
    EN_ATTENTE = "en_attente"
    CONFIRME = "confirme"


@dataclass(frozen=True, slots=True)
class Verdict:
    decision: Decision
    motif: str  # lisible, avec les deux comptes de lignes et le pourcentage s'il y a lieu

    @property
    def compare(self) -> bool:
        """Le snapshot devient le dernier retenu et produit ses événements."""
        return self.decision in (Decision.RETENU, Decision.CONFIRME)


def evaluer(nouveau: Snapshot, retenu: Snapshot | None, seuil: float = SEUIL_PERTE) -> Verdict:
    """Le verdict de ``nouveau`` face au dernier retenu : écarté, en attente ou retenu."""
    lignes = nouveau.bilan.lignes_bien_formees
    if nouveau.ecarte:
        return Verdict(Decision.ECARTE, f"bloquant : {nouveau.motif_ecart}")
    if lignes == 0:
        return Verdict(Decision.ECARTE, "vide : aucune ligne bien formée")
    if retenu is None:
        return Verdict(Decision.RETENU, f"premier snapshot, {lignes} lignes")
    reference = retenu.bilan.lignes_bien_formees
    if lignes < (1 - seuil) * reference:
        return Verdict(
            Decision.EN_ATTENTE, f"{_perte(lignes, reference)}, en attente de confirmation"
        )
    if nouveau.sha256 == retenu.sha256:
        return Verdict(Decision.RETENU, f"identique au dernier retenu ({retenu.archive})")
    return Verdict(Decision.RETENU, f"{lignes} lignes, dernier retenu {reference}")


def trancher(
    en_attente: Snapshot,
    retenu: Snapshot | None,
    suivant: Snapshot | None,
    *,
    inchange_revu: bool,
    seuil: float = SEUIL_PERTE,
) -> Verdict:
    """Confirme ou écarte un snapshot en attente ; le laisse en attente sans archive après lui.

    ``inchange_revu`` : un passage ultérieur du manifeste a revu l'empreinte de
    comparaison de l'archive en attente. ``suivant`` : l'archive qui la suit,
    ou None à la fin du bronze.
    """
    lignes = en_attente.bilan.lignes_bien_formees
    reference = retenu.bilan.lignes_bien_formees if retenu is not None else 0
    perte = _perte(lignes, reference)
    if inchange_revu:
        return Verdict(Decision.CONFIRME, f"{perte}, confirmée par un passage inchangé")
    if suivant is None:
        return Verdict(Decision.EN_ATTENTE, f"{perte}, en attente de confirmation")
    suivant_lignes = suivant.bilan.lignes_bien_formees
    if not suivant.ecarte and suivant_lignes and suivant_lignes <= (1 + seuil) * lignes:
        return Verdict(
            Decision.CONFIRME,
            f"{perte}, confirmée par l'archive suivante ({suivant_lignes} lignes)",
        )
    return Verdict(
        Decision.ECARTE, f"{perte}, jamais confirmée (archive suivante : {suivant_lignes} lignes)"
    )


def _perte(lignes: int, reference: int) -> str:
    pourcentage = 100 * (reference - lignes) / reference if reference else 0.0
    return f"{lignes} lignes au lieu de {reference}, perte de {pourcentage:.1f} %".replace(".", ",")


@dataclass(frozen=True, slots=True)
class Resultat:
    """Ce qu'une archive produit : son verdict, et de quoi redonner ses événements."""

    snapshot: Snapshot
    verdict: Verdict
    retenu_precedent: Snapshot | None  # le dernier retenu au moment de la comparaison
    date_source: str | None

    def evenements(self) -> Iterator[Evenement]:
        """Les événements, recalculés à chaque appel : aucun quand le snapshot n'est pas comparé.

        Rien n'est gardé : celui qui les écrit les consomme une fois, et un
        test peut les redemander.
        """
        if not self.verdict.compare:
            return iter(())
        return comparer(self.retenu_precedent, self.snapshot, date_source=self.date_source)


@dataclass(slots=True)
class Suivi:
    """L'état du garde-fou pour un fichier : dernier retenu, snapshot en attente.

    ``traiter`` rend un résultat pour l'archive en attente si elle est tranchée,
    puis un pour la nouvelle archive. ``clore`` rend celui d'un snapshot encore
    en attente à la fin du bronze. Les résultats sortent dans l'ordre des
    archives, ce qui permet de les écrire et de les rejouer tels quels.
    """

    retenu: Snapshot | None = None
    en_attente: Snapshot | None = None
    date_source_en_attente: str | None = None
    seuil: float = SEUIL_PERTE

    def traiter(
        self, nouveau: Snapshot, *, date_source: str | None = None, inchange_revu: bool = False
    ) -> list[Resultat]:
        """``inchange_revu`` porte sur le snapshot en attente, s'il y en a un."""
        produits: list[Resultat] = []
        if self.en_attente is not None:
            produits.append(self._trancher(nouveau, inchange_revu))
        verdict = evaluer(nouveau, self.retenu, self.seuil)
        produits.append(self._appliquer(nouveau, verdict, date_source))
        return produits

    def clore(self, *, inchange_revu: bool = False) -> list[Resultat]:
        """Fin du bronze : le snapshot en attente est confirmé par un ``inchange`` ou le reste."""
        if self.en_attente is None:
            return []
        return [self._trancher(None, inchange_revu)]

    def _trancher(self, suivant: Snapshot | None, inchange_revu: bool) -> Resultat:
        assert self.en_attente is not None
        verdict = trancher(
            self.en_attente, self.retenu, suivant, inchange_revu=inchange_revu, seuil=self.seuil
        )
        en_attente, date_source = self.en_attente, self.date_source_en_attente
        if verdict.decision is not Decision.EN_ATTENTE:
            self.en_attente = self.date_source_en_attente = None
        return self._appliquer(en_attente, verdict, date_source)

    def _appliquer(self, snapshot: Snapshot, verdict: Verdict, date_source: str | None) -> Resultat:
        retenu_precedent = self.retenu
        if verdict.compare:
            self.retenu = snapshot
        elif verdict.decision is Decision.EN_ATTENTE and self.en_attente is None:
            self.en_attente, self.date_source_en_attente = snapshot, date_source
        return Resultat(snapshot, verdict, retenu_precedent, date_source)
