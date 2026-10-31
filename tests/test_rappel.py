"""Mission 09 (addendum 1 G) : la déduplication des pages d'avis et le rappel par section.

Deux retouches de la sélection des dix fragments, branchées après le commit des questions
neuves qui les mesurent (bbb9809). Contre un Qdrant de poche, qui ne sait que parcourir.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pharmaflux.assistant import chemin
from pharmaflux.index.construction import Resultat


def charge(
    cis: str, section: str, partie: int = 1, page: str | None = None, date: str = ""
) -> dict[str, Any]:
    valeurs: dict[str, Any] = {"code_cis": cis, "section": section, "partie": partie}
    if page is not None:
        valeurs["page"] = {"page_id": page, "date_avis": date}
    return valeurs


def resultats(*charges: dict[str, Any]) -> list[Resultat]:
    return [Resultat(rang, 1.0 / rang, c) for rang, c in enumerate(charges, start=1)]


def test_une_partie_de_page_ne_compte_qu_une_fois() -> None:
    """Douze CIS pour la page de MOUNJARO : la partie 1 n'occupe qu'une place."""
    entree = resultats(
        charge("60000001", "avis_has", 1, "p_4072400"),
        charge("60000002", "avis_has", 1, "p_4072400"),
        charge("60000003", "identite"),
        charge("60000002", "avis_has", 2, "p_4072400"),
        charge("60000003", "avis_has", 2, "p_4072400"),
    )
    sortie = chemin.dedoublonner(entree, frozenset())
    assert [
        (r.rang, r.charge["code_cis"], r.charge["section"], r.charge["partie"]) for r in sortie
    ] == [
        (1, "60000001", "avis_has", 1),
        (2, "60000003", "identite", 1),
        (3, "60000002", "avis_has", 2),
    ]
    # Le CIS visé prend la place du mieux classé de sa (page, partie).
    vise = chemin.dedoublonner(entree, frozenset({"60000002"}))
    assert [r.charge["code_cis"] for r in vise] == ["60000002", "60000003", "60000002"]


def test_les_fragments_des_fiches_ne_sont_jamais_fusionnes() -> None:
    entree = resultats(charge("60000001", "avis"), charge("60000002", "avis"))
    assert chemin.dedoublonner(entree, frozenset()) == entree


class QdrantDePoche:
    alias_fragments = "pharmaflux-fragments"

    def __init__(self, charges: list[dict[str, Any]]) -> None:
        self.charges = charges
        self.filtres: list[dict[str, object]] = []

    def parcourir(self, collection: str, filtre: dict[str, Any]) -> Iterator[dict[str, Any]]:
        assert collection == self.alias_fragments
        self.filtres.append(filtre)
        conditions = {c["key"]: c["match"]["value"] for c in filtre["must"]}
        for valeurs in self.charges:
            if all(valeurs.get(k) == v for k, v in conditions.items()):
                yield {"id": "x", "payload": valeurs}


INDEX = [
    charge("63210923", "avis", 1),
    charge("63210923", "avis_has", 2, "p_2", "2026-09-16"),
    charge("63210923", "avis_has", 1, "p_1", "2024-01-10"),
    charge("63210923", "avis_has", 1, "p_2", "2026-09-16"),
]


def test_le_rappel_joint_la_premiere_partie_de_la_section_demandee() -> None:
    """Le constat d'avis_has-003 (OZEMPIC) : la fiche visée est là, mais pas sa section avis."""
    entree = resultats(
        charge("63210923", "identite"),
        charge("63210923", "presentations"),
        charge("60000001", "avis"),
        charge("60000002", "avis"),
    )
    trace: dict[str, Any] = {}
    sortie = chemin._rappel_par_section(
        QdrantDePoche(INDEX),
        entree,
        frozenset({"63210923"}),
        "Quel est le dernier SMR d'OZEMPIC ?",
        trace,  # type: ignore[arg-type]
    )
    assert [(r.charge["code_cis"], r.charge["section"]) for r in sortie] == [
        ("63210923", "identite"),
        ("63210923", "presentations"),
        ("60000001", "avis"),
        ("63210923", "avis"),  # à la place du dernier fragment d'un autre CIS
    ]
    assert trace["rappel_section"]["remplace"] == {"code_cis": "60000002", "section": "avis"}


def test_le_rappel_prend_l_avis_le_plus_recent_pour_une_page() -> None:
    sans_fiche = [c for c in INDEX if c["section"] == "avis_has"]
    entree = resultats(charge("63210923", "identite"), charge("60000001", "identite"))
    sortie = chemin._rappel_par_section(
        QdrantDePoche(sans_fiche),
        entree,
        frozenset({"63210923"}),
        "Que dit l'avis de la HAS ?",
        {},  # type: ignore[arg-type]
    )
    assert sortie[1].charge["page"]["page_id"] == "p_2" and sortie[1].charge["partie"] == 1


def test_le_rappel_ne_change_rien_sans_raison() -> None:
    qdrant = QdrantDePoche(INDEX)
    vises = frozenset({"63210923"})
    deja = resultats(charge("63210923", "avis"), charge("60000001", "avis"))
    assert chemin._rappel_par_section(qdrant, deja, vises, "Quel SMR ?", {}) == deja  # type: ignore[arg-type]
    autre = resultats(charge("60000001", "identite"))
    assert chemin._rappel_par_section(qdrant, autre, vises, "Quel SMR ?", {}) == autre  # type: ignore[arg-type]
    rien = resultats(charge("63210923", "identite"))
    assert chemin._rappel_par_section(qdrant, rien, vises, "Bonjour", {}) == rien  # type: ignore[arg-type]
    assert qdrant.filtres == []  # aucune lecture de l'index quand rien n'est à joindre
