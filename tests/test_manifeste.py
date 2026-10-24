"""Le manifeste : ajout seul, lecture tolérante à une coupure, intolérante à la corruption."""

import json
import logging
import tracemalloc
from dataclasses import asdict
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


def _ecrire_lignes(racine: Path, nombre: int) -> Path:
    """Un manifeste réaliste de ``nombre`` lignes, écrit d'un bloc (pas un fsync par ligne)."""
    chemin = manifeste.chemin_manifeste(racine)
    chemin.parent.mkdir(parents=True)
    identifiants = [f"bdpm.fichier_{i:02d}" for i in range(14)]
    with chemin.open("wb") as fichier:
        for numero in range(nombre):
            enregistrement = _enregistrement(f"2026{numero:011d}")
            enregistrement.identifiant = identifiants[numero % 14]
            enregistrement.empreinte_comparaison = f"e{numero:064d}"
            enregistrement.sha256 = enregistrement.empreinte_comparaison
            enregistrement.chemin_archive = f"bronze/bdpm/x/2026-10-24/{numero}__abc.txt.gz"
            enregistrement.last_modified = "Mon, 29 Sep 2026 15:48:06 GMT"
            enregistrement.etag = '"1cf7a-6403c5b4c5a9d"'
            enregistrement.debut = f"2026-10-{25 if numero % 3 else 24}T14:17:00+00:00"
            fichier.write(json.dumps(asdict(enregistrement), ensure_ascii=False).encode() + b"\n")
    return chemin


def test_etat_connu_retient_empreintes_et_collectes_du_jour(racine: Path) -> None:
    hier_ok = _enregistrement("p1")
    hier_ok.debut = "2026-10-23T14:17:00+00:00"
    hier_ok.empreinte_comparaison = "e1"
    aujourdhui_erreur = _enregistrement("p2")
    aujourdhui_erreur.statut = "erreur"
    aujourdhui_erreur.erreur = "HTTP 503"
    aujourdhui_autre = _enregistrement("p3")
    aujourdhui_autre.identifiant = "openmedic.metadonnees"
    aujourdhui_autre.statut = "inchange"
    aujourdhui_autre.empreinte_comparaison = "e3"
    for enregistrement in (hier_ok, aujourdhui_erreur, aujourdhui_autre):
        manifeste.ajouter(racine, enregistrement)
    connu = manifeste.etat_connu(racine, "2026-10-24")
    assert connu.empreintes == {"bdpm.specialites": "e1", "openmedic.metadonnees": "e3"}
    assert connu.collectes_du_jour == {"openmedic.metadonnees"}, "l'erreur du jour ne compte pas"
    assert manifeste.etat_connu(racine / "vide", "2026-10-24") == manifeste.EtatConnu()
    assert not (racine / "vide").exists()


def test_parcourir_applique_les_regles_de_lecture(
    racine: Path, caplog: pytest.LogCaptureFixture
) -> None:
    manifeste.ajouter(racine, _enregistrement("p1"))
    chemin = manifeste.chemin_manifeste(racine)
    with chemin.open("ab") as fichier:
        fichier.write(TRONQUEE)
    manifeste.ajouter(racine, _enregistrement("p3"))
    with chemin.open("ab") as fichier:
        fichier.write(b"\n\nfin coupee")
    with caplog.at_level(logging.WARNING, logger="pharmaflux.collecte"):
        assert [e.passage_id for e in manifeste.parcourir(racine)] == ["p1", "p3"]
    assert "ligne 2 tronquée" in caplog.text and "dernière ligne (4) illisible" in caplog.text
    with chemin.open("ab") as fichier:
        fichier.write(b"\n")
    manifeste.ajouter(racine, _enregistrement("p5"))
    parcours = manifeste.parcourir(racine)
    assert next(parcours).passage_id == "p1" and next(parcours).passage_id == "p3"
    with pytest.raises(ManifesteCorrompu, match=r"ligne 4 illisible"):
        next(parcours)


def test_etat_connu_en_flux_memoire_bornee(racine: Path) -> None:
    """Relecture 1, bloquant 2 : la mémoire d'un passage ne dépend pas de l'âge du manifeste."""
    nombre = 30_000
    chemin = _ecrire_lignes(racine, nombre)
    taille = chemin.stat().st_size
    assert taille > 20_000_000, "un manifeste de quelques mois"
    tracemalloc.start()
    try:
        connu = manifeste.etat_connu(racine, "2026-10-25")
        _, pic = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(connu.empreintes) == 14 and len(connu.collectes_du_jour) == 14
    dernier = f"bdpm.fichier_{(nombre - 1) % 14:02d}"
    assert connu.empreintes[dernier] == f"e{nombre - 1:064d}", "la dernière ligne gagne"
    assert pic < 4 * 1024 * 1024, f"pic de {pic / 1e6:.1f} Mo pour {taille / 1e6:.0f} Mo"
