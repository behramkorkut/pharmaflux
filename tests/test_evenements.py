"""Mission 02, décisions 3 à 6 : comparaison, événements, garde-fou de volume, bilan par archive.

Sur les archives fabriquées de ``tests/fixtures/evenements/`` (lignes réelles
altérées, voir le README des fixtures), archivées sous des noms fixés.
"""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from pharmaflux.collecte.empreintes import sha256_hex
from pharmaflux.contrats.chargeur import charger_identifiant
from pharmaflux.contrats.modele import Regle
from pharmaflux.evenements import bilan, schema, snapshot, volume
from pharmaflux.evenements.comparaison import appliquer, comparer, etat_du_snapshot
from pharmaflux.evenements.schema import Evenement, EvenementInvalide, TypeEvenement
from pharmaflux.evenements.snapshot import Identite, Snapshot
from pharmaflux.evenements.volume import Decision, Suivi
from tests.conftest import FIXTURES

EVENEMENTS = FIXTURES / "evenements"
CIP_SUPPRIME, CIP_MODIFIE, CIP_CREE, CIP_GRAPHIE = (
    "3400936963504",
    "3400949497706",
    "3400949444137",
    "3400930116791",
)


def _snap(identifiant: str, nom: str, jour: str, heure: str) -> Snapshot:
    """Le snapshot d'une fixture fabriquée, sous un nom d'archive réaliste et fixé."""
    contrat = charger_identifiant(identifiant)
    dossier = "contrats" if nom.endswith("_anomalies.txt") else "evenements"
    octets = (FIXTURES / dossier / nom).read_bytes()
    horodatage = datetime.strptime(f"{jour}T{heure}", "%Y-%m-%dT%H%M").replace(tzinfo=UTC)
    nom_archive = f"{horodatage:%Y%m%dT%H%M%SZ}__{sha256_hex(octets)[:12]}.txt.gz"
    archive = f"bronze/bdpm/{contrat.fichier}/{jour}/{nom_archive}"
    return snapshot.construire(contrat, octets, archive, horodatage)


def _pres(nom: str, jour: str = "2026-10-24", heure: str = "1417") -> Snapshot:
    return _snap("bdpm.presentations", nom, jour, heure)


def _types(evenements: list[Evenement] | tuple[Evenement, ...]) -> dict[str, int]:
    comptes: dict[str, int] = {}
    for e in evenements:
        comptes[e.type.value] = comptes.get(e.type.value, 0) + 1
    return comptes


def test_premier_snapshot_une_creee_par_entite() -> None:
    a = _pres("presentations_a.txt")
    evenements = comparer(None, a, date_source="2026-10-24")
    assert len(evenements) == 17 and {e.type for e in evenements} == {TypeEvenement.CREEE}
    assert all(e.etat_initial and e.avant is None and e.apres is not None for e in evenements)
    assert all(
        e.archive_precedente is None and e.archive_precedente_sha256 is None for e in evenements
    )
    assert [e.cle for e in evenements] == sorted(
        (e.cle for e in evenements), key=lambda c: tuple(c.values())
    )
    assert len({e.id for e in evenements}) == 17
    premier = evenements[0]
    assert premier.entite == "bdpm.presentations" and premier.fichier == "CIS_CIP_bdpm.txt"
    assert premier.version_contrat == "v1" and premier.identite is Identite.CLE
    assert list(premier.cle) == ["code_cip13"] and premier.rang == 1
    assert (
        premier.date_observation == "2026-10-24T14:17:00Z" and premier.date_source == "2026-10-24"
    )
    assert premier.archive == a.archive and premier.archive_sha256 == a.sha256
    assert premier.apres is not None and list(premier.apres) == list(a.contrat.noms_colonnes)
    cher = next(
        e for e in evenements if e.apres is not None and e.apres["prix_medicament"] == "1466.29"
    )
    assert cher.apres is not None and cher.apres["prix_public"] == "1469.05"
    anciennes = [e for e in evenements if e.anomalies]
    assert len(anciennes) == 2 and all(
        e.anomalies == (("date_declaration_commercialisation", Regle.DATE_HORS_PLAGE),)
        for e in anciennes
    )
    assert anciennes[0].apres is not None
    assert anciennes[0].apres["date_declaration_commercialisation"] in ("1949-01-19", "2924-11-29")


def test_comparaison_a_cle_creee_modifiee_supprimee() -> None:
    a, b = _pres("presentations_a.txt"), _pres("presentations_b.txt", heure="1517")
    evenements = comparer(a, b)
    assert _types(evenements) == {"supprimee": 1, "modifiee": 1, "creee": 1}
    assert all(not e.etat_initial for e in evenements)
    par_type = {e.type: e for e in evenements}
    supprimee = par_type[TypeEvenement.SUPPRIMEE]
    assert supprimee.cle == {"code_cip13": CIP_SUPPRIME} and supprimee.apres is None
    assert supprimee.avant is not None and supprimee.avant["code_cip13"] == CIP_SUPPRIME
    modifiee = par_type[TypeEvenement.MODIFIEE]
    assert modifiee.cle == {"code_cip13": CIP_MODIFIE}
    assert modifiee.champs_modifies == ("prix_medicament", "prix_public")
    assert modifiee.avant is not None and modifiee.apres is not None
    assert (modifiee.avant["prix_medicament"], modifiee.apres["prix_medicament"]) == (
        "68.68",
        "69.00",
    )
    assert modifiee.empreinte_ligne == snapshot.empreinte_ligne(
        b.par_cle[(CIP_MODIFIE,)].normalisees
    )
    creee = par_type[TypeEvenement.CREEE]
    assert creee.cle == {"code_cip13": CIP_CREE} and creee.avant is None
    assert all(e.cle != {"code_cip13": CIP_GRAPHIE} for e in evenements), (
        "65 % → 65% : pas un changement"
    )
    assert all(
        e.archive_precedente == a.archive and e.archive_precedente_sha256 == a.sha256
        for e in evenements
    )
    assert [e.cle_de_tri() for e in evenements] == sorted(e.cle_de_tri() for e in evenements)
    assert [e.type for e in comparer(b, a)] == [
        TypeEvenement.CREEE,  # 3400936963504 revient
        TypeEvenement.SUPPRIMEE,  # 3400949444134 disparaît
        TypeEvenement.MODIFIEE,  # 3400949497706 reprend ses prix
    ]


def test_retour_et_oscillation_identifiants_distincts() -> None:
    """A → B → A → B : les chemins d'archive entrent dans l'identifiant (addendum 1, E)."""
    suite = [
        _pres("presentations_a.txt", "2026-10-24", "1417"),
        _pres("presentations_b.txt", "2026-10-24", "1517"),
        _pres("presentations_a.txt", "2026-10-25", "1417"),
        _pres("presentations_b.txt", "2026-10-25", "1517"),
    ]
    assert suite[0].sha256 == suite[2].sha256 and suite[0].archive != suite[2].archive
    tous: list[Evenement] = []
    precedent = None
    for s in suite:
        tous.extend(comparer(precedent, s))
        precedent = s
    assert len(tous) == 17 + 3 + 3 + 3 and len({e.id for e in tous}) == len(tous)
    premiere, seconde = tous[17:20], tous[23:26]
    assert [e.cle for e in premiere] == [e.cle for e in seconde]
    assert [e.apres for e in premiere] == [e.apres for e in seconde], "mêmes contenus"
    assert {e.id for e in premiere}.isdisjoint({e.id for e in seconde}), "archives différentes"
    rejoue = [e for s, p in zip(suite, [None, *suite[:-1]], strict=True) for e in comparer(p, s)]
    assert [schema.serialiser(e) for e in rejoue] == [schema.serialiser(e) for e in tous]


def test_comparaison_ligne_a_ligne_doublon_et_rangs() -> None:
    a = _snap("bdpm.disponibilite", "dispo_a.txt", "2026-10-24", "1417")
    b = _snap("bdpm.disponibilite", "dispo_b.txt", "2026-10-24", "1517")
    assert a.identite is Identite.LIGNE and a.bilan.entites == 6
    initiales = comparer(None, a)
    assert len(initiales) == 7 and {e.identite for e in initiales} == {Identite.LIGNE}
    rangs = sorted((e.empreinte_ligne, e.rang) for e in initiales)
    doublon = [r for r in rangs if r[1] == 2]
    assert len(doublon) == 1 and (doublon[0][0], 1) in rangs
    assert set(initiales[0].cle) == {"code_cis", "code_cip13", "lien_ansm"}
    evenements = comparer(a, b)
    assert _types(evenements) == {"supprimee": 2, "creee": 1}
    (rang_2,) = [e for e in evenements if e.rang == 2]
    assert rang_2.type is TypeEvenement.SUPPRIMEE and rang_2.empreinte_ligne == doublon[0][0]
    changee = [e for e in evenements if e.cle["code_cis"] == "66890524"]
    assert [e.type for e in changee] == [TypeEvenement.SUPPRIMEE, TypeEvenement.CREEE], (
        "même clé : la suppression précède la création"
    )
    assert changee[0].avant is not None and changee[1].apres is not None
    assert (changee[0].avant["date_debut"], changee[1].apres["date_debut"]) == (
        "2027-07-01",
        "2027-09-01",
    )
    assert all(e.champs_modifies == () for e in evenements)


def test_ligne_en_triple_ramenee_a_une_les_supprimee_du_rang_le_plus_haut_au_plus_bas() -> None:
    """Relecture 1, bloquant 2 : un consommateur qui suit le flux voit un compte toujours juste."""
    triple = _snap("bdpm.disponibilite", "dispo_triple.txt", "2026-10-24", "1417")
    une = _snap("bdpm.disponibilite", "dispo_simple.txt", "2026-10-24", "1517")
    perdues = comparer(triple, une)
    assert [(e.type, e.rang) for e in perdues] == [
        (TypeEvenement.SUPPRIMEE, 3),
        (TypeEvenement.SUPPRIMEE, 2),
    ]
    retrouvees = comparer(une, triple)
    assert [(e.type, e.rang) for e in retrouvees] == [
        (TypeEvenement.CREEE, 2),
        (TypeEvenement.CREEE, 3),
    ]
    etat = appliquer(appliquer({}, comparer(None, triple)), perdues)
    assert etat == etat_du_snapshot(une)
    assert appliquer(etat, retrouvees) == etat_du_snapshot(triple)
    relues = sorted(
        (schema.deserialiser(schema.serialiser(e)) for e in reversed(perdues)),
        key=Evenement.cle_de_tri,
    )
    assert [e.rang for e in relues] == [3, 2], "même ordre après relecture et tri"
    with pytest.raises(ValueError, match="mauvais rang"):
        appliquer(appliquer({}, comparer(None, triple)), list(reversed(perdues)))


def test_appliquer_les_evenements_redonne_le_snapshot() -> None:
    a, b = _pres("presentations_a.txt"), _pres("presentations_b.txt", heure="1517")
    etat = appliquer({}, comparer(None, a))
    assert etat == etat_du_snapshot(a)
    assert appliquer(etat, comparer(a, b)) == etat_du_snapshot(b)
    assert appliquer(appliquer(etat, comparer(a, b)), comparer(b, a)) == etat_du_snapshot(a)
    da = _snap("bdpm.disponibilite", "dispo_a.txt", "2026-10-24", "1417")
    db = _snap("bdpm.disponibilite", "dispo_b.txt", "2026-10-24", "1517")
    etat_d = appliquer({}, comparer(None, da))
    assert etat_d == etat_du_snapshot(da) and appliquer(
        etat_d, comparer(da, db)
    ) == etat_du_snapshot(db)
    with pytest.raises(ValueError, match="absente"):
        appliquer({}, comparer(a, b))
    with pytest.raises(ValueError, match="déjà présente"):
        appliquer(etat, comparer(None, a))


def test_identifiant_et_serialisation() -> None:
    a = _pres("presentations_a.txt")
    (e, *_) = comparer(None, a)
    attendu = hashlib.sha256(
        "\x1f".join(("bdpm.presentations", a.archive, "", "creee", e.cle["code_cip13"])).encode()
    ).hexdigest()
    assert e.id == attendu and e.identite_de_ligne == e.cle["code_cip13"]
    ligne = schema.serialiser(e)
    assert ligne.endswith("\n") and ligne.count("\n") == 1 and "é" in ligne, "UTF-8 tel quel"
    brut = json.loads(ligne)
    assert list(brut) == sorted(brut) and brut["version_schema"] == 1 and brut["rang"] == 1
    assert brut["cle"] == {"code_cip13": e.cle["code_cip13"]} and brut["avant"] is None
    assert isinstance(brut["apres"]["prix_medicament"], str), "jamais un nombre JSON"
    assert (
        ligne == json.dumps(brut, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    )
    assert schema.deserialiser(ligne) == e
    b = _pres("presentations_b.txt", heure="1517")
    for evenement in comparer(a, b):
        assert schema.deserialiser(schema.serialiser(evenement)) == evenement
    with pytest.raises(EvenementInvalide, match="version_schema"):
        schema.deserialiser(ligne.replace('"version_schema":1', '"version_schema":2'))
    with pytest.raises(EvenementInvalide, match="illisible"):
        schema.deserialiser("{")
    with pytest.raises(EvenementInvalide, match="mal formé"):
        schema.deserialiser(ligne.replace('"rang":1', '"rang":"un"'))


def test_aller_retour_json_sur_une_cle_a_plusieurs_colonnes() -> None:
    """Contrôle du palier 2, point 1 : rien ne dépend de l'ordre d'un objet JSON.

    ``bdpm.compositions`` a une clé à cinq colonnes dont l'ordre dans le contrat
    (``code_cis, designation_element, code_substance, …``) n'est pas l'ordre
    alphabétique que ``serialiser`` écrit.
    """
    contrat = charger_identifiant("bdpm.compositions")
    assert list(contrat.cle.colonnes) != sorted(contrat.cle.colonnes)
    octets = (FIXTURES / "bdpm" / "CIS_COMPO_bdpm.txt").read_bytes()
    horodatage = datetime(2026, 10, 24, 14, 17, tzinfo=UTC)
    s = snapshot.construire(contrat, octets, "bronze/bdpm/CIS_COMPO_bdpm.txt/a.txt.gz", horodatage)
    ecrits = comparer(None, s)
    assert len(ecrits) == 40 and list(ecrits[0].cle) == list(contrat.cle.colonnes)
    relus = [schema.deserialiser(schema.serialiser(e)) for e in ecrits]
    assert relus == ecrits, "un événement relu est égal à l'événement écrit"
    assert list(relus[0].cle) == sorted(contrat.cle.colonnes) and list(relus[0].cle) != list(
        ecrits[0].cle
    ), "l'objet JSON est relu dans l'ordre alphabétique"
    for ecrit, relu in zip(ecrits, relus, strict=True):
        assert relu.identite_de_ligne == ecrit.identite_de_ligne
        recalcule = schema.identifiant(
            relu.entite, relu.archive, relu.archive_precedente, relu.type, relu.identite_de_ligne
        )
        assert recalcule == relu.id == ecrit.id
        assert relu.cle_de_tri() == ecrit.cle_de_tri()
    melanges = sorted(reversed(relus), key=Evenement.cle_de_tri)
    assert [e.id for e in melanges] == [e.id for e in ecrits], "même tri après relecture"
    assert appliquer({}, relus) == appliquer({}, ecrits) == etat_du_snapshot(s)
    assert [schema.serialiser(e) for e in relus] == [schema.serialiser(e) for e in ecrits]


@pytest.mark.parametrize(
    ("ancien", "nouveau"),
    [
        ('"etat_initial":true', '"etat_initial":"false"'),
        ('"etat_initial":true', '"etat_initial":1'),
        ('"rang":1', '"rang":"1"'),
        ('"rang":1', '"rang":1.0'),
        ('"rang":1', '"rang":true'),
        ('"rang":1', '"rang":2.7'),
        ('"id":"', '"id":1,"autre":"'),
        ('"champs_modifies":[]', '"champs_modifies":"abc"'),
        ('"champs_modifies":[]', '"champs_modifies":{}'),
        ('"anomalies":[]', '"anomalies":"abc"'),
    ],
)
def test_deserialiser_exige_les_vrais_types_json(ancien: str, nouveau: str) -> None:
    """Contrôle du palier 2, point 2, et relecture 1 : un vrai booléen, un vrai entier, une vraie
    liste (une chaîne se lirait caractère par caractère), pas une conversion."""
    (e, *_) = comparer(None, _pres("presentations_a.txt"))
    ligne = schema.serialiser(e)
    assert ancien in ligne
    with pytest.raises(EvenementInvalide, match="mal formé"):
        schema.deserialiser(ligne.replace(ancien, nouveau, 1))


def test_comparer_refuse_deux_fichiers_ou_sans_horodatage() -> None:
    a = _pres("presentations_a.txt")
    with pytest.raises(ValueError, match="même fichier"):
        comparer(a, _snap("bdpm.disponibilite", "dispo_a.txt", "2026-10-24", "1417"))
    sans = snapshot.construire(a.contrat, b"", "vide")
    with pytest.raises(ValueError, match="horodatage"):
        comparer(None, sans)


def _derouler(suivi: Suivi, *suite: Snapshot) -> list[volume.Resultat]:
    resultats: list[volume.Resultat] = []
    for s in suite:
        resultats.extend(suivi.traiter(s))
    return resultats


def test_garde_fou_cas_du_26_10() -> None:
    """Décision 5 : snapshot normal, vide, identique au premier : zéro événement, écart consigné."""
    a = _pres("presentations_a.txt", "2026-10-24", "2317")
    vide = _pres("presentations_vide.txt", "2026-10-26", "1417")
    meme = _pres("presentations_a.txt", "2026-10-26", "1517")
    suivi = Suivi()
    resultats = _derouler(suivi, a, vide, meme)
    assert [r.verdict.decision for r in resultats] == [
        Decision.RETENU,
        Decision.ECARTE,
        Decision.RETENU,
    ]
    assert [len(r.evenements) for r in resultats] == [17, 0, 0]
    assert resultats[1].verdict.motif == "vide : aucune ligne bien formée"
    assert resultats[2].verdict.motif == f"identique au dernier retenu ({a.archive})"
    assert suivi.retenu is meme and suivi.en_attente is None
    b_vide = bilan.etablir(resultats[1])
    assert b_vide.ecart is not None and b_vide.ecart.lignes == -17 and b_vide.ecart.evenements == ()
    assert dict(b_vide.snapshot.anomalies) == {Regle.FICHIER_VIDE: 1}
    assert suivi.clore() == []


def test_vide_et_bloquant_ecartes_sans_appel() -> None:
    a = _pres("presentations_a.txt")
    bloquant = _pres("presentations_anomalies.txt", heure="1517")
    assert bloquant.ecarte and bloquant.bilan.lignes_bien_formees == 3
    suivi = Suivi()
    resultats = _derouler(suivi, a, bloquant, _pres("presentations_vide.txt", heure="1617"))
    assert [r.verdict.decision for r in resultats[1:]] == [Decision.ECARTE, Decision.ECARTE]
    assert resultats[1].verdict.motif.startswith(
        "bloquant : 2 anomalie(s) bloquante(s) : encodage (1)"
    )
    assert suivi.en_attente is None and suivi.retenu is a, "jamais en attente"
    assert volume.evaluer(bloquant, None).decision is Decision.ECARTE, "même sans retenu"
    assert volume.evaluer(_pres("presentations_vide.txt"), None).decision is Decision.ECARTE


def test_perte_confirmee_par_l_archive_suivante() -> None:
    a = _pres("presentations_a.txt", "2026-10-24", "1417")
    perte = _pres("presentations_perte.txt", "2026-10-24", "1517")
    encore = _pres("presentations_perte.txt", "2026-10-24", "1617")
    suivi = Suivi()
    suivi.traiter(a)
    (r_perte,) = suivi.traiter(perte)
    assert r_perte.verdict == volume.Verdict(
        Decision.EN_ATTENTE, "8 lignes au lieu de 17, perte de 52,9 %, en attente de confirmation"
    )
    assert r_perte.evenements == () and suivi.en_attente is perte and suivi.retenu is a
    tranche, r_encore = suivi.traiter(encore)
    assert tranche.snapshot is perte and tranche.verdict.decision is Decision.CONFIRME
    assert tranche.verdict.motif == (
        "8 lignes au lieu de 17, perte de 52,9 %, confirmée par l'archive suivante (8 lignes)"
    )
    assert _types(tranche.evenements) == {"supprimee": 9}
    assert all(
        e.archive == perte.archive and e.archive_precedente == a.archive for e in tranche.evenements
    )
    assert r_encore.verdict.decision is Decision.RETENU and r_encore.evenements == ()
    assert r_encore.verdict.motif == f"identique au dernier retenu ({perte.archive})"
    assert suivi.retenu is encore and suivi.en_attente is None
    assert [r.snapshot for r in suivi.resultats] == [a, perte, perte, encore], (
        "l'archive en attente a deux résultats : en attente, puis tranchée (bilan réécrit)"
    )
    assert [r.verdict.decision for r in suivi.resultats] == [
        Decision.RETENU,
        Decision.EN_ATTENTE,
        Decision.CONFIRME,
        Decision.RETENU,
    ]


def test_perte_jamais_confirmee_la_comparaison_porte_le_cumul() -> None:
    a = _pres("presentations_a.txt", "2026-10-24", "1417")
    perte = _pres("presentations_perte.txt", "2026-10-24", "1517")
    b = _pres("presentations_b.txt", "2026-10-24", "1617")
    suivi = Suivi()
    _derouler(suivi, a, perte)
    tranche, r_b = suivi.traiter(b)
    assert tranche.snapshot is perte and tranche.verdict.decision is Decision.ECARTE
    assert tranche.verdict.motif == (
        "8 lignes au lieu de 17, perte de 52,9 %, jamais confirmée (archive suivante : 17 lignes)"
    )
    assert tranche.evenements == ()
    assert r_b.verdict.decision is Decision.RETENU and _types(r_b.evenements) == {
        "supprimee": 1,
        "modifiee": 1,
        "creee": 1,
    }
    assert all(e.archive_precedente == a.archive for e in r_b.evenements), "du dernier retenu"
    assert appliquer(
        appliquer({}, suivi.resultats[0].evenements), r_b.evenements
    ) == etat_du_snapshot(b)


def test_perte_en_attente_a_la_fin_du_bronze_puis_confirmee_par_un_inchange() -> None:
    a = _pres("presentations_a.txt", "2026-10-24", "1417")
    perte = _pres("presentations_perte.txt", "2026-10-24", "1517")
    suivi = Suivi()
    _derouler(suivi, a, perte)
    (attente,) = suivi.clore()
    assert attente.verdict.decision is Decision.EN_ATTENTE and attente.evenements == ()
    assert suivi.en_attente is perte and suivi.retenu is a, "rien n'est tranché sans archive après"
    (confirme,) = suivi.clore(inchange_revu=True)
    assert confirme.verdict == volume.Verdict(
        Decision.CONFIRME,
        "8 lignes au lieu de 17, perte de 52,9 %, confirmée par un passage inchangé",
    )
    assert _types(confirme.evenements) == {"supprimee": 9} and suivi.retenu is perte
    assert suivi.clore() == []
    # Même chose quand l'inchangé est vu au moment où l'archive suivante arrive.
    suivi2 = Suivi()
    _derouler(suivi2, a, perte)
    tranche, r_b = suivi2.traiter(_pres("presentations_b.txt", heure="1617"), inchange_revu=True)
    assert tranche.verdict.decision is Decision.CONFIRME and r_b.verdict.decision is Decision.RETENU
    assert all(e.archive_precedente == perte.archive for e in r_b.evenements)


def test_perte_suivie_d_un_vide_est_ecartee() -> None:
    """Le vide ne confirme rien ; l'archive en attente est écartée dès qu'une archive la suit."""
    suivi = Suivi()
    _derouler(suivi, _pres("presentations_a.txt"), _pres("presentations_perte.txt", heure="1517"))
    tranche, r_vide = suivi.traiter(_pres("presentations_vide.txt", heure="1617"))
    assert (
        tranche.verdict.decision is Decision.ECARTE and r_vide.verdict.decision is Decision.ECARTE
    )
    assert tranche.verdict.motif.endswith("jamais confirmée (archive suivante : 0 lignes)")
    assert suivi.en_attente is None


def test_seuil_de_perte() -> None:
    """1 % des lignes bien formées du dernier retenu ; une croissance n'est jamais en attente."""
    a = _pres("presentations_a.txt")
    b = _pres("presentations_b.txt", heure="1517")  # 17 lignes aussi
    assert volume.evaluer(b, a).decision is Decision.RETENU
    assert volume.evaluer(b, a).motif == "17 lignes, dernier retenu 17"
    perte = _pres("presentations_perte.txt", heure="1617")
    assert volume.evaluer(perte, a, seuil=0.60).decision is Decision.RETENU
    assert volume.evaluer(perte, a, seuil=0.50).decision is Decision.EN_ATTENTE
    assert volume.evaluer(a, perte).decision is Decision.RETENU, "plus de lignes : retenu"
    assert volume.SEUIL_PERTE == 0.01


def test_bilan_par_archive_en_dict() -> None:
    a = _pres("presentations_a.txt", "2026-10-24", "1417")
    b = _pres("presentations_b.txt", "2026-10-24", "1517")
    suivi = Suivi()
    r_a, r_b = _derouler(suivi, a, b)
    premier = bilan.etablir(r_a)
    assert premier.ecart is None and premier.verdict.decision is Decision.RETENU
    second = bilan.etablir(r_b)
    assert second.ecart is not None and second.ecart.archive_retenue == a.archive
    assert second.ecart.lignes == 0 and second.ecart.entites == 0
    assert second.ecart.evenements == (("creee", 1), ("modifiee", 1), ("supprimee", 1))
    assert second.ecart.anomalies == ()
    brut = bilan.en_dict(second)
    assert brut["decision"] == "retenu" and brut["version_schema"] == 1
    assert brut["lignes_bien_formees"] == 17 and brut["entites"] == 17
    assert brut["anomalies"] == {"date_hors_plage": 2}
    assert brut["graphies"] == {"taux_remboursement": _graphies_de(b)}
    assert brut["ecart"] == {
        "archive_retenue": a.archive,
        "lignes": 0,
        "entites": 0,
        "anomalies": [],
        "evenements": {"creee": 1, "modifiee": 1, "supprimee": 1},
    }
    json.dumps(brut, sort_keys=True)  # sérialisable tel quel
    perte = _pres("presentations_perte.txt", "2026-10-24", "1617")
    (r_perte,) = suivi.traiter(perte)
    ecart = bilan.etablir(r_perte).ecart
    assert ecart is not None and ecart.lignes == -9 and ecart.evenements == ()
    assert ecart.anomalies == ((Regle.DATE_HORS_PLAGE, 2, 0),)
    assert bilan.en_dict(bilan.etablir(r_perte))["ecart"]["anomalies"] == [  # type: ignore[index]
        {"regle": "date_hors_plage", "retenu": 2, "nouveau": 0}
    ]


def _graphies_de(s: Snapshot) -> dict[str, int]:
    ((_, graphies),) = s.bilan.graphies
    return dict(graphies)


@pytest.mark.parametrize(
    ("identifiant", "nom", "bloquante"),
    [
        ("bdpm.presentations", "presentations_a.txt", False),
        ("bdpm.presentations", "presentations_b.txt", False),
        ("bdpm.presentations", "presentations_perte.txt", False),
        ("bdpm.presentations", "presentations_vide.txt", False),
        ("bdpm.disponibilite", "dispo_a.txt", False),
        ("bdpm.disponibilite", "dispo_b.txt", False),
    ],
)
def test_les_fixtures_fabriquees_passent_leur_contrat(
    identifiant: str, nom: str, bloquante: bool
) -> None:
    s = _snap(identifiant, nom, "2026-10-24", "1417")
    assert s.ecarte is bloquante
    assert s.archive.startswith(f"bronze/bdpm/{s.contrat.fichier}/2026-10-24/20261024T141700Z__")
    assert s.archive.endswith(f"{s.sha256[:12]}.txt.gz")


def test_suppression_retenue_a_travers_le_garde_fou_avec_un_seuil_large() -> None:
    """Contrôle du palier 2 (facultatif) : avec ``seuil=0.6``, la perte de 52,9 % est retenue."""
    a = _pres("presentations_a.txt")
    perte = _pres("presentations_perte.txt", heure="1517")
    suivi = Suivi(seuil=0.6)
    _, r_perte = _derouler(suivi, a, perte)
    assert r_perte.verdict.decision is Decision.RETENU and _types(r_perte.evenements) == {
        "supprimee": 9
    }
    assert suivi.retenu is perte and suivi.en_attente is None
