"""La mise à jour de l'index en lots bornés (mission 10, addendum 3, incident du 20/11).

La mémoire ne dépend plus de la taille d'un lot de la BDPM : les textes absents du cache sont
encodés d'abord, par ``LOT_TEXTES``, puis le modèle est rendu ; l'écriture ne lit que le cache,
par requêtes de ``LOT_POINTS`` points, retraits compris. Une coupure à n'importe quel lot, puis
la reprise, donnent l'index de la reconstruction complète. Sans réseau : Qdrant est simulé.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pharmaflux.index import construction
from pharmaflux.index.construction import Cache, Fragments
from pharmaflux.index.encodeur import E5Onnx, EncodeurTest, Vecteurs
from pharmaflux.index.qdrant import COLLECTION_ETAT, Qdrant, QdrantIndisponible
from tests.qdrant_simule import QdrantSimule
from tests.test_encodeur_modele import e5  # noqa: F401 (la fixture du vrai modèle)
from tests.test_index_maj import (
    APRES,
    APRES_FICHES,
    AVANT,
    AVANT_FICHES,
    TOUCHES,
    assert_egal_a_la_reconstruction,
    client,
    construire,
    contenu,
    ecrire,
    index_avant,  # noqa: F401 (la fixture)
)

# Plus petites que le lot de test : 5 CIS touchés, des dizaines de fragments à écrire.
BORNES = {"LOT_CIS": 2, "LOT_TEXTES": 4, "LOT_POINTS": 3}


class Coupure(Exception):  # noqa: N818 (nom français voulu)
    """Le processus tué pendant un encodage (le noyau, au plafond)."""


class EncodeurTrace(EncodeurTest):
    """Note chaque appel au modèle dans le journal des appels ; peut mourir au n-ième."""

    def __init__(self, appels: list[tuple[str, int]], mort_au: int | None = None) -> None:
        self.appels = appels
        self.mort_au = mort_au
        self.libere = 0

    def passages(self, textes: Sequence[str]) -> Vecteurs:
        self.appels.append(("encoder", len(textes)))
        if self.mort_au is not None and sum(a == "encoder" for a, _ in self.appels) == self.mort_au:
            raise Coupure
        return super().passages(textes)

    def liberer(self) -> None:
        self.libere += 1
        self.appels.append(("liberer", 0))


@pytest.fixture
def bornes(monkeypatch: pytest.MonkeyPatch) -> None:
    for nom, valeur in BORNES.items():
        monkeypatch.setattr(construction, nom, valeur)


@pytest.fixture
def trace(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Le journal des appels : encodages, libération, écritures et retraits de points."""
    appels: list[tuple[str, int]] = []
    ecrire_, supprimer = Qdrant.ecrire, Qdrant.supprimer_ids

    def ecrire_trace(self: Qdrant, collection: str, points: Sequence[Any]) -> None:
        if collection != COLLECTION_ETAT:
            appels.append(("ecrire", len(points)))
        ecrire_(self, collection, points)

    def supprimer_trace(self: Qdrant, collection: str, identifiants: Sequence[str]) -> None:
        appels.append(("retirer", len(identifiants)))
        supprimer(self, collection, identifiants)

    monkeypatch.setattr(Qdrant, "ecrire", ecrire_trace)
    monkeypatch.setattr(Qdrant, "supprimer_ids", supprimer_trace)
    return appels


def maj(
    simule: QdrantSimule,
    travail: Path,
    frags: Fragments,
    encodeur: EncodeurTest,
    lignes: list[str] | None = None,
) -> construction.BilanMiseAJour:
    cache = Cache(travail, EncodeurTest.empreinte)
    try:
        with client(simule) as q:
            return construction.mettre_a_jour(
                q, encodeur, frags, cache, None if lignes is None else lignes.append
            )
    finally:
        cache.close()


def maj_tranche(tmp_path: Path) -> Fragments:
    return ecrire(tmp_path, "maj", APRES_FICHES, APRES, TOUCHES)


@pytest.mark.usefixtures("bornes")
def test_l_encodeur_n_est_plus_appele_apres_la_premiere_ecriture(
    index_avant: QdrantSimule,  # noqa: F811
    tmp_path: Path,
    trace: list[tuple[str, int]],
) -> None:
    trace.clear()  # la construction de l'index d'avant ne compte pas
    encodeur = EncodeurTrace(trace)
    bilan = maj(index_avant, tmp_path / "travail", maj_tranche(tmp_path), encodeur)
    genres = [genre for genre, _ in trace]
    assert "ecrire" in genres and "encoder" in genres
    premiere = genres.index("ecrire")
    assert "encoder" not in genres[premiere:], "aucun encodage après la première écriture"
    assert genres.index("liberer") < premiere, "le modèle est rendu avant d'écrire"
    assert bilan.encodes == 7
    assert_egal_a_la_reconstruction(index_avant, tmp_path, "ordre")


@pytest.mark.usefixtures("bornes")
def test_les_appels_et_les_requetes_sont_bornes(
    index_avant: QdrantSimule,  # noqa: F811
    tmp_path: Path,
    trace: list[tuple[str, int]],
) -> None:
    trace.clear()
    bilan = maj(index_avant, tmp_path / "travail", maj_tranche(tmp_path), EncodeurTrace(trace))
    tailles: dict[str, list[int]] = {}
    for genre, taille in trace:
        tailles.setdefault(genre, []).append(taille)
    assert max(tailles["encoder"]) <= BORNES["LOT_TEXTES"]
    assert max(tailles["ecrire"]) <= BORNES["LOT_POINTS"]
    assert max(tailles["retirer"]) <= BORNES["LOT_POINTS"]
    # Le lot de test dépasse chaque borne : la mise à jour l'a bien découpé.
    assert bilan.ajoutes + bilan.remplaces > BORNES["LOT_POINTS"]
    assert bilan.retires > BORNES["LOT_POINTS"] or len(tailles["retirer"]) > 1
    assert bilan.cis_touches > BORNES["LOT_CIS"]
    assert_egal_a_la_reconstruction(index_avant, tmp_path, "bornes")


@pytest.mark.usefixtures("bornes")
def test_une_ligne_d_avancee_par_lot(
    index_avant: QdrantSimule,  # noqa: F811
    tmp_path: Path,
) -> None:
    lignes: list[str] = []
    maj(index_avant, tmp_path / "travail", maj_tranche(tmp_path), EncodeurTest(), lignes)
    encodage = [ligne for ligne in lignes if ", encodage :" in ligne]
    ecriture = [ligne for ligne in lignes if ", écriture :" in ligne]
    assert len(encodage) > 1 and len(ecriture) > 1, lignes
    for ligne in lignes:
        assert ligne.startswith("mise à jour, ") and " Mio" in ligne, ligne
        assert "encodé(s)" in ligne and "écrit(s)" in ligne and "retiré(s)" in ligne, ligne
    assert ecriture[-1].split(" ; ")[0].endswith(f"CIS {len(TOUCHES)}/{len(TOUCHES)}"), (
        "la dernière ligne : tous les CIS faits"
    )


COUPURES = {
    "ecriture": ("PUT /collections/pharmaflux-f4-test-", "ecrire"),
    "retrait": ("POST /collections/pharmaflux-f4-test-20261026T001712Z/points/delete", "retirer"),
}


@pytest.mark.usefixtures("bornes")
@pytest.mark.parametrize("genre", sorted(COUPURES))
def test_une_coupure_a_chaque_lot_puis_la_reprise_egale_la_reconstruction(
    tmp_path: Path, trace: list[tuple[str, int]], genre: str
) -> None:
    """Pour chaque requête d'écriture (ou de retrait) d'une mise à jour sans coupure : une
    coupure juste avant elle, puis la reprise, donnent l'index de la reconstruction."""
    prefixe, nom = COUPURES[genre]
    frags = maj_tranche(tmp_path)
    temoin = index_neuf(tmp_path / "temoin")
    trace.clear()
    maj(temoin, tmp_path / "temoin" / "travail", frags, EncodeurTest())
    requetes = sum(g == nom for g, _ in trace)
    assert requetes > 1, "le lot de test demande plusieurs requêtes"
    for rang in range(1, requetes + 1):
        dossier = tmp_path / f"{genre}-{rang}"
        simule = index_neuf(dossier)
        simule.couper(prefixe, rang)
        with pytest.raises(QdrantIndisponible, match="coupure simulée"):
            maj(simule, dossier / "travail", frags, EncodeurTest())
        etat = next(iter(simule.points(COLLECTION_ETAT).values()))["payload"]
        assert etat["vise"] == APRES and etat["instant"] != APRES, "« vise », l'ancien instant"
        assert maj(simule, dossier / "travail", frags, EncodeurTest()).reprise
        assert_egal_a_la_reconstruction(simule, dossier, f"reprise-{genre}-{rang}")


def index_neuf(dossier: Path) -> QdrantSimule:
    dossier.mkdir(parents=True)
    simule = QdrantSimule()
    construire(simule, dossier / "travail", ecrire(dossier, "avant", AVANT_FICHES, AVANT))
    return simule


@pytest.mark.usefixtures("bornes")
@pytest.mark.parametrize("mort_au", [1, 2])
def test_une_mort_pendant_l_encodage_ne_perd_qu_un_lot(
    index_avant: QdrantSimule,  # noqa: F811
    tmp_path: Path,
    mort_au: int,
) -> None:
    frags = maj_tranche(tmp_path)
    appels: list[tuple[str, int]] = []
    with pytest.raises(Coupure):
        maj(index_avant, tmp_path / "travail", frags, EncodeurTrace(appels, mort_au))
    gardes = sum(taille for genre, taille in appels[: mort_au - 1] if genre == "encoder")
    appels_reprise: list[tuple[str, int]] = []
    reprise = maj(index_avant, tmp_path / "travail", frags, EncodeurTrace(appels_reprise))
    assert reprise.reprise
    assert reprise.encodes == 7 - gardes, "ce qui était encodé avant la mort est au cache"
    assert_egal_a_la_reconstruction(index_avant, tmp_path, f"mort-{mort_au}")


@pytest.mark.modele
@pytest.mark.usefixtures("bornes")
def test_le_vrai_modele_en_lots_bornes_est_conforme_cosinus_compris(
    e5: E5Onnx,  # noqa: F811 (la fixture importée)
    tmp_path: Path,
) -> None:
    """Le découpage change les voisins de lot d'e5 (la quantification dynamique) : l'index mis à
    jour en lots bornés reste conforme à sa reconstruction, cosinus compris (addendum 3)."""

    def avec(simule: QdrantSimule, travail: Path, frags: Fragments, faire: Any) -> Any:
        cache = Cache(travail, e5.empreinte)
        try:
            with client(simule) as q:
                return faire(q, e5, frags, cache)
        finally:
            cache.close()

    simule = QdrantSimule()
    avant = ecrire(tmp_path, "avant", AVANT_FICHES, AVANT)
    avec(simule, tmp_path / "travail", avant, construction.construire)
    avec(simule, tmp_path / "travail", maj_tranche(tmp_path), construction.mettre_a_jour)
    complets = ecrire(tmp_path, "complets", APRES_FICHES, APRES)
    rapport = avec(simule, tmp_path / "travail", complets, construction.verifier)
    assert rapport.conforme, construction.formater_verification(rapport)
    reference = QdrantSimule()
    avec(reference, tmp_path / "reference", complets, construction.construire)
    pas_a_pas, en_une_fois = contenu(simule), contenu(reference)
    assert {i: c for i, (c, _) in pas_a_pas.items()} == {
        i: c for i, (c, _) in en_une_fois.items()
    }, "mêmes identifiants, mêmes charges"
    for identifiant, (_, vecteur) in pas_a_pas.items():
        a = np.asarray(vecteur["dense"], np.float64)
        b = np.asarray(en_une_fois[identifiant][1]["dense"], np.float64)
        assert float(a @ b) >= construction.COSINUS_MINIMAL, identifiant
