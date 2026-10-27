"""Mission 03, palier 1 : écrire une comparaison ne garde rien en mémoire (ADR 0006, mise à jour).

Deux snapshots fabriqués dans le test (4 000 lignes tirées des fixtures, un
libellé et une clé par ligne, toutes modifiées entre les deux) ;
``tracemalloc`` mesure la mémoire des deux snapshots (M), puis le pic pendant
que ``rejeu`` écrit les 4 000 ``modifiee`` : le surplus doit rester sous
M / 2. Le code de la mission 02 donnait près de 3 M (tous les événements
étaient construits puis sérialisés avant d'être écrits) ; le flux donne
environ M / 6, et le fichier écrit pèse plus que ce surplus. C'est un test de
**structure**, en octets d'objets Python, le même sur le Mac et en CI : la
mémoire résidente du rejeu complet est mesurée dans le rapport du palier,
pas ici.
"""

import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from pharmaflux.contrats.chargeur import charger_identifiant
from pharmaflux.evenements import rejeu, snapshot
from pharmaflux.evenements.rejeu import ResumeEntite
from pharmaflux.evenements.snapshot import Snapshot
from pharmaflux.evenements.volume import Suivi
from tests.conftest import FIXTURES

LIGNES = 4_000
MODELE = (FIXTURES / "evenements" / "presentations_a.txt").read_text(encoding="utf-8").splitlines()


def _fabriquer(jour: int, heure: str) -> Snapshot:
    """Des présentations plausibles, une clé par ligne, la date de déclaration au ``jour``."""
    lignes = []
    for i in range(LIGNES):
        champs = MODELE[i % len(MODELE)].split("\t")
        champs[1] = f"{1000000 + i:07d}"
        champs[2] = f"{champs[2]}, lot {i}"
        champs[5] = f"{jour:02d}/03/2011"
        champs[6] = f"34009{i:08d}"
        lignes.append("\t".join(champs))
    octets = ("\n".join(lignes) + "\n").encode("utf-8")
    horodatage = datetime.strptime(f"2026-10-24T{heure}", "%Y-%m-%dT%H%M").replace(tzinfo=UTC)
    archive = f"bronze/bdpm/CIS_CIP_bdpm.txt/2026-10-24/20261024T{heure}00Z__{heure * 3}.txt.gz"
    return snapshot.construire(
        charger_identifiant("bdpm.presentations"), octets, archive, horodatage
    )


def test_ecrire_une_comparaison_ne_garde_rien_en_memoire(tmp_path: Path) -> None:
    deja = tracemalloc.is_tracing()
    if not deja:
        tracemalloc.start()
    try:
        avant = tracemalloc.get_traced_memory()[0]
        a, b = _fabriquer(16, "1417"), _fabriquer(17, "1517")
        m = tracemalloc.get_traced_memory()[0] - avant
        assert not a.ecarte and not b.ecarte and a.bilan.entites == b.bilan.entites == LIGNES
        suivi = Suivi()
        resume = ResumeEntite("bdpm.presentations", a.contrat.fichier)
        for resultat in suivi.traiter(a):
            rejeu._ecrire_resultat(tmp_path, resultat, resume, lambda _: None)
        tracemalloc.reset_peak()
        base = tracemalloc.get_traced_memory()[0]
        for resultat in suivi.traiter(b):
            rejeu._ecrire_resultat(tmp_path, resultat, resume, lambda _: None)
        surplus = tracemalloc.get_traced_memory()[1] - base
    finally:
        if not deja:
            tracemalloc.stop()
    assert dict(resume.evenements) == {"creee": LIGNES, "modifiee": LIGNES}
    (fichier,) = (tmp_path / "evenements" / "bdpm.presentations").glob("20261024T1517*.jsonl")
    assert fichier.read_text(encoding="utf-8").count("\n") == LIGNES
    assert surplus < m / 2, f"surplus {surplus / 1e6:.1f} Mo pour {m / 1e6:.1f} Mo de snapshots"
    assert fichier.stat().st_size > surplus, (
        "le fichier écrit pèse plus que ce qui reste en mémoire"
    )
