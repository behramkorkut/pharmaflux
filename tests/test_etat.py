"""L'état calculé depuis le manifeste."""

from datetime import UTC, datetime, timedelta

from pharmaflux.collecte.etat import calculer_etat, formater_etat
from pharmaflux.collecte.manifeste import Enregistrement


def _ligne(
    passage: str, debut: datetime, statut: str, fichier: str = "CIS_bdpm.txt", **champs: object
) -> Enregistrement:
    return Enregistrement(
        passage_id=passage,
        identifiant="bdpm.specialites",
        source="bdpm",
        fichier=fichier,
        url="https://exemple.invalid",
        debut=debut.isoformat(),
        fin=(debut + timedelta(seconds=2)).isoformat(),
        statut=statut,
        version_collecteur="0.1.0",
        **champs,  # type: ignore[arg-type]
    )


def test_etat_par_fichier() -> None:
    maintenant = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    il_y_a = lambda heures: maintenant - timedelta(hours=heures)  # noqa: E731
    enregistrements = [
        _ligne("p1", il_y_a(50), "nouveau", chemin_archive="a", date_source_affichee="2026-09-29"),
        _ligne("p2", il_y_a(30), "inchange", date_source_affichee="2026-09-29"),
        _ligne("p3", il_y_a(20), "nouveau", chemin_archive="b", date_source_affichee="2026-10-25"),
        _ligne("p4", il_y_a(3), "erreur", erreur="HTTP 503"),
        _ligne("p4", il_y_a(3), "nouveau", fichier="CIS_MITM.txt", chemin_archive="c"),
        _ligne("p5", il_y_a(1), "inchange", date_source_affichee="2026-10-25"),
    ]
    specialites, mitm = calculer_etat(enregistrements, maintenant)
    assert specialites.fichier == "CIS_bdpm.txt"
    assert specialites.derniere_archive == "2026-10-25 16:00Z"
    assert specialites.dernier_changement == "2026-10-25 16:00Z"
    assert specialites.date_source == "2026-10-25"
    assert specialites.derniere_erreur == "2026-10-26 09:00Z HTTP 503"
    assert specialites.passages_24h == 3
    assert specialites.dernier_statut == "inchange"
    assert mitm.derniere_archive == "2026-10-26 09:00Z"
    assert mitm.dernier_changement is None, "première observation : pas un changement"
    assert mitm.passages_24h == 1

    texte = formater_etat([specialites, mitm])
    assert texte.splitlines()[0].startswith("fichier")
    assert "bdpm/CIS_bdpm.txt" in texte and "HTTP 503" in texte and "—" in texte
