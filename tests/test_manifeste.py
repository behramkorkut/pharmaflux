"""Le manifeste : ajout seul, lecture tolérante à une coupure, intolérante à la corruption."""

import logging
from pathlib import Path

import pytest

from pharmaflux.collecte import manifeste
from pharmaflux.collecte.manifeste import MARQUE_TRONCATURE, Enregistrement, ManifesteCorrompu

TRONQUEE = b'{"passage_id": "p2", "identifiant": "bd'


def _enregistrement(passage_id: str) -> Enregistrement:
    return Enregistrement(
        passage_id=passage_id,
        identifiant="bdpm.specialites",
        source="bdpm",
        fichier="CIS_bdpm.txt",
        url="https://exemple.invalid",
        debut="2026-10-24T14:17:00+00:00",
        fin="2026-10-24T14:17:01+00:00",
        statut="nouveau",
        version_collecteur="0.1.0",
    )


def test_derniere_ligne_coupee_ignoree_avec_avertissement(
    racine: Path, caplog: pytest.LogCaptureFixture
) -> None:
    manifeste.ajouter(racine, _enregistrement("p1"))
    chemin = manifeste.chemin_manifeste(racine)
    with chemin.open("ab") as fichier:
        fichier.write(TRONQUEE)
    with caplog.at_level(logging.WARNING, logger="pharmaflux.collecte"):
        relus = manifeste.lire(racine)
    assert [e.passage_id for e in relus] == ["p1"]
    assert "dernière ligne" in caplog.text and "ignorée" in caplog.text


def test_ajouter_repart_sur_une_ligne_propre(
    racine: Path, caplog: pytest.LogCaptureFixture
) -> None:
    manifeste.ajouter(racine, _enregistrement("p1"))
    chemin = manifeste.chemin_manifeste(racine)
    with chemin.open("ab") as fichier:
        fichier.write(TRONQUEE)
    manifeste.ajouter(racine, _enregistrement("p3"))
    manifeste.ajouter(racine, _enregistrement("p4"))
    with caplog.at_level(logging.WARNING, logger="pharmaflux.collecte"):
        assert [e.passage_id for e in manifeste.lire(racine)] == ["p1", "p3", "p4"]
    assert "ligne 2 tronquée" in caplog.text
    lignes = chemin.read_bytes().split(b"\n")
    assert len(lignes) == 5 and lignes[-1] == b"", "quatre lignes, retour à la ligne final"
    assert lignes[1] == TRONQUEE + MARQUE_TRONCATURE, "marquée, jamais réécrite"
    assert lignes[0].startswith(b"{") and lignes[2].startswith(b"{")


def test_ligne_illisible_au_milieu_est_une_erreur_franche(racine: Path) -> None:
    manifeste.ajouter(racine, _enregistrement("p1"))
    chemin = manifeste.chemin_manifeste(racine)
    with chemin.open("ab") as fichier:
        fichier.write(b"ceci n'est pas du JSON\n")
    manifeste.ajouter(racine, _enregistrement("p3"))
    with pytest.raises(ManifesteCorrompu, match=r"ligne 2 illisible"):
        manifeste.lire(racine)


def test_ligne_json_sans_les_champs_obligatoires_compte_comme_illisible(racine: Path) -> None:
    chemin = manifeste.chemin_manifeste(racine)
    chemin.parent.mkdir(parents=True)
    chemin.write_bytes(b'{"passage_id": "p1"}\n')
    assert manifeste.lire(racine) == [], "dernière ligne : ignorée"
    manifeste.ajouter(racine, _enregistrement("p2"))
    with pytest.raises(ManifesteCorrompu):
        manifeste.lire(racine)


def test_dernieres_empreintes_retiennent_toute_archive(racine: Path) -> None:
    archivee_en_erreur = _enregistrement("p1")
    archivee_en_erreur.statut = "erreur"
    archivee_en_erreur.erreur = "lien_absent"
    archivee_en_erreur.chemin_archive = "bronze/bdpm/CIS_bdpm.txt/a.gz"
    archivee_en_erreur.empreinte_comparaison = "e1"
    erreur_sans_archive = _enregistrement("p2")
    erreur_sans_archive.statut = "erreur"
    erreur_sans_archive.empreinte_comparaison = "e2"
    for enregistrement in (archivee_en_erreur, erreur_sans_archive):
        manifeste.ajouter(racine, enregistrement)
    assert manifeste.dernieres_empreintes(manifeste.lire(racine)) == {"bdpm.specialites": "e1"}
