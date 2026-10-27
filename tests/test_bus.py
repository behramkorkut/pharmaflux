"""Mission 03, décisions 3 et 4 : enveloppe des messages, schémas, registre, publication.

Tout en mémoire : un bus simulé et un registre simulé (``httpx.MockTransport``),
jamais de Docker ni de réseau. Les tests d'intégration sont dans
``test_bus_integration.py``.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft7Validator, ValidationError

from pharmaflux.bus import enveloppe as env
from pharmaflux.bus import publication, registre
from pharmaflux.bus.client import (
    CourtierInjoignable,
    DefinitionTopic,
    Livraison,
    MessageTropGros,
    Rappel,
)
from pharmaflux.bus.enveloppe import Enveloppe, Motif
from pharmaflux.bus.publication import LivraisonEchouee, PublicationRefusee
from pharmaflux.bus.registre import Registre, SchemaAbsent, SchemaIncompatible, enregistrer_tout
from pharmaflux.collecte.empreintes import sha256_hex
from pharmaflux.contrats.chargeur import charger_identifiant, charger_tous
from pharmaflux.contrats.modele import Regle
from pharmaflux.evenements import schema, snapshot
from pharmaflux.evenements.comparaison import comparer
from pharmaflux.evenements.schema import Evenement, EvenementInvalide, TypeEvenement
from pharmaflux.evenements.snapshot import Identite, Snapshot
from tests.conftest import FIXTURES, texte_nu

SHA_EVENEMENT = "a1e3ab77906cee3f6c9185880a23757c73bbf2e4c8e52c1037850b6dacdcf211"
SHA_ECHEC = "9f444172fc5e3bc24f5b858abb3971de31dd55fd0ec3cc1e04fe084e1e5e36f2"
PRESENTATIONS, DISPO = "bdpm.presentations", "bdpm.disponibilite"


def _snap(identifiant: str, nom: str, heure: str = "1417") -> Snapshot:
    contrat = charger_identifiant(identifiant)
    octets = (FIXTURES / "evenements" / nom).read_bytes()
    horodatage = datetime.strptime(f"2026-10-24T{heure}", "%Y-%m-%dT%H%M").replace(tzinfo=UTC)
    nom_archive = f"20261024T{heure}00Z__{sha256_hex(octets)[:12]}.txt.gz"
    archive = f"bronze/bdpm/{contrat.fichier}/2026-10-24/{nom_archive}"
    return snapshot.construire(contrat, octets, archive, horodatage)


def _evenements_presentations() -> tuple[list[Evenement], list[Evenement]]:
    a, b = (
        _snap(PRESENTATIONS, "presentations_a.txt"),
        _snap(PRESENTATIONS, "presentations_b.txt", "1517"),
    )
    return list(comparer(None, a, date_source="2026-10-24")), list(comparer(a, b))


# --- enveloppe -------------------------------------------------------------------------------


def test_nom_des_topics_et_cle_du_message() -> None:
    assert env.nom_topic(PRESENTATIONS) == "pharmaflux.bdpm.presentations.v1"
    assert env.nom_topic(DISPO, "pharmaflux.test.x1") == "pharmaflux.test.x1.bdpm.disponibilite.v1"
    assert env.topic_echecs() == "pharmaflux.echecs.v1"
    initiales, _ = _evenements_presentations()
    assert env.cle_message(initiales[0]) == b'{"code_cip13":"3400927849800"}', "1re clé triée"
    (e, *_) = comparer(None, _snap(DISPO, "dispo_a.txt"))
    cle = json.loads(env.cle_message(e))
    assert list(cle) == ["code_cip13", "code_cis", "lien_ansm"], (
        "clés triées, pas l'ordre du contrat"
    )
    assert env.cle_message(e) == env.cle_message(schema.deserialiser(schema.serialiser(e)))


def test_horodatage_du_message_est_la_date_d_observation() -> None:
    assert (
        env.horodatage_ms("2026-10-24T19:41:46Z")
        == calendar.timegm((2026, 10, 24, 19, 41, 46)) * 1000
    )
    assert env.horodatage_ms("2026-10-24T19:41:46Z") == 1792870906000


def test_envelopper_garde_la_ligne_a_l_octet() -> None:
    _, suivants = _evenements_presentations()
    ligne = schema.serialiser(suivants[0]).encode("utf-8")
    enveloppe = env.envelopper(ligne, "evenements/bdpm.presentations/x.jsonl", PRESENTATIONS, 7)
    assert enveloppe.valeur == ligne[:-1] and not enveloppe.valeur.endswith(b"\n")
    assert schema.deserialiser(enveloppe.valeur.decode()) == suivants[0]
    assert enveloppe.topic == "pharmaflux.bdpm.presentations.v1"
    assert enveloppe.cle == env.cle_message(suivants[0])
    assert enveloppe.horodatage_ms == env.horodatage_ms(suivants[0].date_observation)
    en_tetes = dict(enveloppe.en_tetes)
    assert en_tetes["id"] == suivants[0].id.encode() and en_tetes["schema_id"] == b"7"
    assert en_tetes["fichier"] == b"evenements/bdpm.presentations/x.jsonl"
    assert (
        en_tetes["type"] == suivants[0].type.value.encode()
        and en_tetes["entite"] == b"bdpm.presentations"
    )
    assert en_tetes["archive"] == suivants[0].archive.encode()
    assert en_tetes["producteur"].startswith(b"pharmaflux/") and en_tetes["version_schema"] == b"1"
    assert all(isinstance(v, bytes) for _, v in enveloppe.en_tetes)
    sans_retour = env.envelopper(ligne[:-1], "f", PRESENTATIONS, 7)
    assert sans_retour.valeur == enveloppe.valeur, "avec ou sans le retour final, même valeur"
    with pytest.raises(EvenementInvalide, match="version_schema"):
        env.envelopper(
            ligne.replace(b'"version_schema":1', b'"version_schema":2'), "f", PRESENTATIONS, 7
        )
    with pytest.raises(EvenementInvalide, match="UTF-8"):
        env.envelopper(b'\xff\xfe{"id":1}\n', "f", PRESENTATIONS, 7)
    with pytest.raises(EvenementInvalide, match="illisible"):
        env.envelopper(b"{pas du json\n", "f", PRESENTATIONS, 7)
    with pytest.raises(EvenementInvalide, match=r"dossier bdpm\.disponibilite") as info:
        env.envelopper(ligne, "f", DISPO, 7)  # le topic vient du dossier, pas de la ligne
    assert "bdpm.presentations" in str(info.value), "le détail nomme les deux entités"


def test_message_en_echec_illisible_et_trop_gros() -> None:
    validateur = Draft7Validator(registre.charger_schema(registre.SCHEMA_ECHEC))
    ligne = b"{pas du json\n"
    illisible = env.message_echec(
        Motif.ILLISIBLE, "JSON illisible", PRESENTATIONS, "evenements/p/x.jsonl", 12, ligne, 3
    )
    assert illisible.topic == "pharmaflux.echecs.v1" and illisible.cle == b"bdpm.presentations"
    assert illisible.horodatage_ms == 0, "l'horodatage est celui du courtier"
    contenu = json.loads(illisible.valeur)
    validateur.validate(contenu)
    assert contenu == {
        "version_echec": 1,
        "motif": "illisible",
        "detail": "JSON illisible",
        "entite": PRESENTATIONS,
        "fichier": "evenements/p/x.jsonl",
        "ligne": 12,
        "id": None,
        "taille": len(ligne) - 1,
        "sha256_ligne": hashlib.sha256(ligne[:-1]).hexdigest(),
        "ligne_brute": "{pas du json",
        "tronquee": False,
    }
    assert (
        dict(illisible.en_tetes)["motif"] == b"illisible"
        and dict(illisible.en_tetes)["schema_id"] == b"3"
    )
    initiales, _ = _evenements_presentations()
    e = initiales[0]
    grosse = schema.serialiser(e)[:-1] + " " * (100 * 1024) + "\n"
    gros = env.message_echec(
        Motif.TROP_GROS, "trop gros", PRESENTATIONS, "f", 1, grosse.encode(), 3
    )
    contenu = json.loads(gros.valeur)
    validateur.validate(contenu)
    assert contenu["tronquee"] and len(contenu["ligne_brute"].encode()) == env.TRONCATURE_ECHEC
    assert contenu["taille"] == len(grosse.encode()) - 1
    assert contenu["id"] == e.id, "la ligne entière se lit : l'identifiant est connu"
    assert contenu["sha256_ligne"] == hashlib.sha256(grosse[:-1].encode()).hexdigest()
    assert len(gros.valeur) < 70 * 1024


# --- schémas ----------------------------------------------------------------------------------


def _tous_les_evenements_des_fixtures() -> list[Evenement]:
    evenements: list[Evenement] = []
    for identifiant, contrat in sorted(charger_tous().items()):
        octets = (FIXTURES / "bdpm" / contrat.fichier).read_bytes()
        s = snapshot.construire(
            contrat,
            octets,
            f"bronze/bdpm/{contrat.fichier}/a.txt.gz",
            datetime(2026, 10, 24, 14, 17, tzinfo=UTC),
        )
        assert not s.ecarte, identifiant
        evenements.extend(comparer(None, s, date_source="2026-10-24"))
    initiales, suivants = _evenements_presentations()
    triple = _snap(DISPO, "dispo_triple.txt")
    evenements += initiales + suivants + list(comparer(None, triple))
    evenements += list(comparer(triple, _snap(DISPO, "dispo_simple.txt", "1517")))
    return evenements


def test_le_schema_accepte_tous_les_evenements_des_fixtures() -> None:
    validateur = Draft7Validator(registre.charger_schema(registre.SCHEMA_EVENEMENT))
    evenements = _tous_les_evenements_des_fixtures()
    assert len(evenements) > 300
    assert {e.type for e in evenements} == set(TypeEvenement) and {
        e.identite for e in evenements
    } == set(Identite)
    assert any(e.rang > 1 for e in evenements) and any(e.anomalies for e in evenements)
    for e in evenements:
        validateur.validate(json.loads(schema.serialiser(e)))


def test_le_schema_refuse_un_evenement_mal_forme() -> None:
    validateur = Draft7Validator(registre.charger_schema(registre.SCHEMA_EVENEMENT))
    (e, *_) = _evenements_presentations()[0]
    bon = json.loads(schema.serialiser(e))
    validateur.validate(bon)
    mauvais: list[dict[str, object]] = [
        {**bon, "en_plus": 1},
        {k: v for k, v in bon.items() if k != "rang"},
        {**bon, "rang": 0},
        {**bon, "rang": "1"},
        {**bon, "type": "renommee"},
        {**bon, "version_schema": 2},
        {**bon, "id": "abc"},
        {**bon, "cle": {}},
        {**bon, "cle": {"code_cip13": 3400930116791}},
        {**bon, "apres": {"prix": 12.5}},
        {**bon, "anomalies": [{"colonne": "x", "regle": "inconnue"}]},
        {**bon, "date_observation": "2026-10-24 14:17:00"},
        {**bon, "date_source": "24/10/2026"},
        {**bon, "etat_initial": "oui"},
    ]
    for cas in mauvais:
        with pytest.raises(ValidationError):
            validateur.validate(cas)


def test_le_schema_est_en_phase_avec_le_code_et_epingle() -> None:
    evenement = registre.charger_schema(registre.SCHEMA_EVENEMENT)
    proprietes = evenement["properties"]
    assert isinstance(proprietes, dict)
    (e, *_) = _evenements_presentations()[0]
    requis = evenement["required"]
    assert isinstance(requis, list)
    assert set(proprietes) == set(schema.en_dict(e)) == set(requis)
    assert proprietes["type"]["enum"] == [t.value for t in TypeEvenement]
    assert proprietes["identite"]["enum"] == [i.value for i in Identite]
    assert proprietes["anomalies"]["items"]["properties"]["regle"]["enum"] == [
        r.value for r in Regle
    ]
    assert evenement["additionalProperties"] is False
    dossier = Path(str(registre.dossier_schemas()))
    assert sha256_hex((dossier / registre.SCHEMA_EVENEMENT).read_bytes()) == SHA_EVENEMENT, (
        "schéma changé : si c'est voulu, mets à jour l'empreinte, l'historique et l'ADR 0007"
    )
    assert sha256_hex((dossier / registre.SCHEMA_ECHEC).read_bytes()) == SHA_ECHEC
    assert registre.historique(registre.SCHEMA_EVENEMENT) == [], (
        "aucune version publiée avant la v1"
    )


# --- registre ---------------------------------------------------------------------------------


class RegistreSimule:
    """Un registre de schémas en mémoire : l'API REST Confluent, réduite aux appels du projet."""

    def __init__(self) -> None:
        self.versions: dict[str, list[str]] = {}
        self.identifiants: dict[str, int] = {}  # schéma (texte) → identifiant global
        self.compatibilites: dict[str, str] = {}
        self.incompatibles: set[str] = set()  # sujets dont le registre refuse toute évolution
        self.appels: list[str] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.repondre)

    def repondre(self, requete: httpx.Request) -> httpx.Response:
        chemin, methode = requete.url.path, requete.method
        self.appels.append(f"{methode} {chemin}")
        assert requete.headers["content-type"] == registre.TYPE_CONTENU
        morceaux = chemin.strip("/").split("/")
        if methode == "PUT" and morceaux[0] == "config":
            self.compatibilites[morceaux[1]] = json.loads(requete.content)["compatibility"]
            return httpx.Response(200, json={"compatibility": self.compatibilites[morceaux[1]]})
        if morceaux[0] == "subjects":
            sujet_ = morceaux[1]
            versions = self.versions.get(sujet_, [])
            if methode == "POST" and morceaux[2:] == ["versions"]:
                texte = json.loads(requete.content)["schema"]
                assert json.loads(requete.content)["schemaType"] == "JSON"
                identifiant = self.identifiants.setdefault(texte, len(self.identifiants) + 1)
                if texte not in versions:
                    self.versions.setdefault(sujet_, []).append(texte)
                return httpx.Response(200, json={"id": identifiant})
            if methode == "POST" and len(morceaux) == 2:
                texte = json.loads(requete.content)["schema"]
                if texte in versions:
                    return httpx.Response(
                        200,
                        json={
                            "id": self.identifiants[texte],
                            "version": versions.index(texte) + 1,
                            "subject": sujet_,
                            "schema": texte,
                        },
                    )
                return httpx.Response(
                    404, json={"error_code": 40403, "message": "Schema not found"}
                )
            if methode == "GET" and morceaux[2:] == ["versions", "latest"]:
                if not versions:
                    return httpx.Response(
                        404, json={"error_code": 40401, "message": "Subject not found"}
                    )
                return httpx.Response(
                    200,
                    json={
                        "id": self.identifiants[versions[-1]],
                        "version": len(versions),
                        "subject": sujet_,
                        "schema": versions[-1],
                    },
                )
            if methode == "DELETE" and len(morceaux) == 2:
                if self.versions.pop(sujet_, None) is None:
                    return httpx.Response(
                        404, json={"error_code": 40401, "message": "Subject not found"}
                    )
                return httpx.Response(200, json=[1])
        if methode == "POST" and morceaux[0] == "compatibility":
            if not self.versions.get(morceaux[2]):
                return httpx.Response(
                    404, json={"error_code": 40401, "message": "Subject not found"}
                )
            return httpx.Response(
                200, json={"is_compatible": morceaux[2] not in self.incompatibles}
            )
        return httpx.Response(500, json={"message": f"inattendu : {methode} {chemin}"})


def test_registre_enregistre_et_rend_le_meme_identifiant() -> None:
    simule = RegistreSimule()
    with Registre("http://registre.test/", simule.transport()) as r:
        assert r.url == "http://registre.test"
        with pytest.raises(SchemaAbsent):
            r.identifiant("pharmaflux.bdpm.presentations.v1-value")
        assert r.compatible("pharmaflux.bdpm.presentations.v1-value", {"type": "object"}), (
            "sans version"
        )
        resultats = enregistrer_tout(r, [PRESENTATIONS, DISPO])
        assert [(x.sujet, x.identifiant, x.nouveau) for x in resultats] == [
            ("pharmaflux.bdpm.disponibilite.v1-value", 1, True),
            ("pharmaflux.bdpm.presentations.v1-value", 1, True),
            ("pharmaflux.echecs.v1-value", 2, True),
        ], "un même schéma a le même identifiant sur tous les sujets"
        assert simule.compatibilites == dict.fromkeys(
            [x.sujet for x in resultats], "BACKWARD_TRANSITIVE"
        )
        assert r.identifiant("pharmaflux.echecs.v1-value") == 2
        assert all(not x.nouveau for x in enregistrer_tout(r, [PRESENTATIONS, DISPO])), "idempotent"
        assert r.compatible(
            "pharmaflux.echecs.v1-value", registre.charger_schema(registre.SCHEMA_ECHEC)
        )
        r.supprimer("pharmaflux.echecs.v1-value")
        with pytest.raises(SchemaAbsent):
            r.identifiant("pharmaflux.echecs.v1-value")
        r.supprimer("pharmaflux.echecs.v1-value")  # déjà absent : sans erreur
    debut = simule.appels.index("PUT /config/pharmaflux.bdpm.disponibilite.v1-value")
    assert simule.appels[debut : debut + 4] == [
        "PUT /config/pharmaflux.bdpm.disponibilite.v1-value",
        "POST /compatibility/subjects/pharmaflux.bdpm.disponibilite.v1-value/versions/latest",
        "POST /subjects/pharmaflux.bdpm.disponibilite.v1-value",
        "POST /subjects/pharmaflux.bdpm.disponibilite.v1-value/versions",
    ], "le schéma courant est soumis à la règle avant d'être enregistré (mission 04, F.2)"


def test_historique_des_schemas_est_trie_par_numero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dossier = tmp_path / "schemas" / "historique"
    dossier.mkdir(parents=True)
    for numero in (10, 2, 1):
        (dossier / f"evenement.v1.schema.{numero}.json").write_text(json.dumps({"v": numero}))
    (dossier / "evenement.v1.schema.json").write_text('{"v": "sans numero"}')  # ignoré
    (dossier / "echec.v1.schema.3.json").write_text('{"v": "autre schema"}')  # ignoré
    (dossier / "README.md").write_text("ignoré")
    monkeypatch.setattr(registre, "dossier_schemas", lambda: tmp_path / "schemas")
    assert [v["v"] for v in registre.historique("evenement.v1.schema.json")] == [1, 2, 10], (
        "10 après 2, pas après 1 : le tri est numérique"
    )
    assert [v["v"] for v in registre.historique("echec.v1.schema.json")] == ["autre schema"]


def test_un_schema_courant_incompatible_est_refuse_avant_d_etre_enregistre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pharmaflux import cli
    from pharmaflux.cli import application

    simule = RegistreSimule()
    sujet_pres = registre.sujet(env.nom_topic(PRESENTATIONS))
    ancien = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}
    with Registre("http://registre.test", simule.transport()) as r:
        r.enregistrer(sujet_pres, ancien)  # une version déjà publiée sous ce sujet
        simule.incompatibles.add(sujet_pres)  # le registre juge le schéma du dépôt incompatible
        with pytest.raises(SchemaIncompatible, match="BACKWARD_TRANSITIVE") as info:
            enregistrer_tout(r, [DISPO, PRESENTATIONS])
    assert sujet_pres in str(info.value) and "nouveau topic" in str(info.value)
    assert simule.versions[sujet_pres] == [json.dumps(ancien, sort_keys=True)], (
        "rien n'est enregistré pour le sujet refusé"
    )
    assert registre.sujet(env.nom_topic(DISPO)) in simule.versions, (
        "le sujet précédent, compatible, est enregistré : la commande reste idempotente"
    )
    assert registre.sujet(env.topic_echecs()) not in simule.versions, "on s'arrête au refus"
    monkeypatch.setattr(cli, "fabriquer_transport_registre", simule.transport)
    from typer.testing import CliRunner

    resultat = CliRunner().invoke(application, ["schemas", "enregistrer"])
    assert resultat.exit_code == 1 and "registre : le schéma du dépôt" in resultat.output
    assert "incompatible" in resultat.output


def test_registre_injoignable_ou_en_erreur() -> None:
    def panne(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refusé")

    with (
        Registre("http://registre.test", httpx.MockTransport(panne)) as r,
        pytest.raises(registre.RegistreIndisponible, match="refusé"),
    ):
        r.identifiant("x")
    conflit = httpx.MockTransport(lambda _: httpx.Response(409, json={"message": "incompatible"}))
    with (
        Registre("http://registre.test", conflit) as r,
        pytest.raises(registre.RegistreIndisponible, match="HTTP 409"),
    ):
        r.enregistrer("x", {"type": "object"})
    assert registre.sujets_du_projet([DISPO], "p") == [
        ("p.bdpm.disponibilite.v1-value", "evenement.v1.schema.json"),
        ("p.echecs.v1-value", "echec.v1.schema.json"),
    ]


# --- publication ------------------------------------------------------------------------------


@dataclass
class BusSimule:
    """Un courtier en mémoire : les messages par topic, dans l'ordre d'arrivée."""

    taille_max: int = 10**9
    panne: str | None = None  # chaque livraison échoue avec ce motif
    injoignable: bool = False  # le courtier est arrêté : rien ne répond
    topics: dict[str, DefinitionTopic] = field(default_factory=dict)
    messages: dict[str, list[Enveloppe]] = field(default_factory=dict)
    en_vol: list[tuple[Enveloppe, Rappel]] = field(default_factory=list)

    def verifier_courtier(self, delai_s: float = 0.0) -> list[str]:
        if self.injoignable:
            raise CourtierInjoignable(f"aucun courtier sur simule:0 après {delai_s:.0f} s")
        return list(self.topics)

    def preparer_topics(self, definitions: list[DefinitionTopic]) -> None:
        for definition in definitions:
            self.topics.setdefault(definition.nom, definition)

    def produire(self, enveloppe: Enveloppe, rappel: Rappel) -> None:
        trop = len(enveloppe.valeur) + len(enveloppe.cle) > self.taille_max
        if trop and not enveloppe.topic.endswith(".echecs.v1"):
            raise MessageTropGros(f"{len(enveloppe.valeur)} octets")
        self.en_vol.append((enveloppe, rappel))

    def attendre(self, _delai_s: float) -> int:
        for enveloppe, rappel in self.en_vol:
            file = self.messages.setdefault(enveloppe.topic, [])
            file.append(enveloppe)
            rappel(Livraison(enveloppe.topic, 0, len(file) - 1, self.panne))
        self.en_vol.clear()
        return 0


def _ecrire_jsonl(sortie: Path, entite: str, nom: str, evenements: list[Evenement]) -> Path:
    chemin = sortie / "evenements" / entite / nom
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("".join(schema.serialiser(e) for e in evenements), encoding="utf-8")
    return chemin


def _sortie(tmp_path: Path) -> tuple[Path, int, int]:
    """Une sortie de « evenements » : présentations A puis A→B, disponibilité A."""
    initiales, suivants = _evenements_presentations()
    dispo = list(comparer(None, _snap(DISPO, "dispo_a.txt")))
    _ecrire_jsonl(tmp_path, PRESENTATIONS, "20261024T141700Z__aaaaaaaaaaaa.jsonl", initiales)
    _ecrire_jsonl(tmp_path, PRESENTATIONS, "20261024T151700Z__bbbbbbbbbbbb.jsonl", suivants)
    _ecrire_jsonl(tmp_path, DISPO, "20261024T141700Z__cccccccccccc.jsonl", dispo)
    return tmp_path, len(initiales) + len(suivants), len(dispo)


def _registre_pret(
    entites: tuple[str, ...] = (PRESENTATIONS, DISPO),
) -> tuple[RegistreSimule, Registre]:
    simule = RegistreSimule()
    r = Registre("http://registre.test", simule.transport())
    enregistrer_tout(r, list(entites))
    return simule, r


def test_publication_complete_dans_l_ordre_avec_etat(tmp_path: Path) -> None:
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    bus = BusSimule()
    _, r = _registre_pret()
    journal: list[str] = []
    rapport = publication.executer(sortie, bus, r, journal=journal.append)
    assert rapport.code_sortie == 0 and rapport.topics == {
        "pharmaflux.bdpm.disponibilite.v1": n_dispo,
        "pharmaflux.bdpm.presentations.v1": n_pres,
    }
    assert [
        (x.identifiant, x.fichiers, x.deja_publies, x.messages, x.echecs) for x in rapport.resumes
    ] == [
        (DISPO, 1, 0, n_dispo, 0),
        (PRESENTATIONS, 2, 0, n_pres, 0),
    ]
    assert [j.split(" : ")[0] for j in journal] == [
        f"{DISPO} 20261024T141700Z__cccccccccccc.jsonl",
        f"{PRESENTATIONS} 20261024T141700Z__aaaaaaaaaaaa.jsonl",
        f"{PRESENTATIONS} 20261024T151700Z__bbbbbbbbbbbb.jsonl",
    ], "entités puis fichiers dans l'ordre des noms"
    # Les topics sont créés avec leur configuration : 3 partitions, rétention sans limite.
    assert set(bus.topics) == set(rapport.topics) | {"pharmaflux.echecs.v1"}
    pres = bus.topics["pharmaflux.bdpm.presentations.v1"]
    assert pres.partitions == 3 and pres.configuration == {
        "retention.ms": "-1",
        "retention.bytes": "-1",
        "cleanup.policy": "delete",
        "message.timestamp.type": "CreateTime",
    }
    echecs = bus.topics["pharmaflux.echecs.v1"]
    assert (
        echecs.partitions == 1 and echecs.configuration["message.timestamp.type"] == "LogAppendTime"
    )
    # Chaque message est la ligne du fichier, dans l'ordre, avec le fichier en en-tête.
    messages = bus.messages["pharmaflux.bdpm.presentations.v1"]
    lignes = [
        ligne
        for nom in ("20261024T141700Z__aaaaaaaaaaaa.jsonl", "20261024T151700Z__bbbbbbbbbbbb.jsonl")
        for ligne in (sortie / "evenements" / PRESENTATIONS / nom).read_bytes().splitlines()
    ]
    assert [m.valeur for m in messages] == lignes
    assert (
        dict(messages[0].en_tetes)["fichier"]
        == b"evenements/bdpm.presentations/20261024T141700Z__aaaaaaaaaaaa.jsonl"
    )
    assert dict(messages[-1].en_tetes)["schema_id"] == b"1"
    assert "pharmaflux.echecs.v1" not in bus.messages
    # L'état : chaque fichier avec son sha256 et ses comptes.
    etat = json.loads((sortie / "publication.json").read_text(encoding="utf-8"))
    assert etat["version"] == 1 and sorted(etat["entites"]) == [DISPO, PRESENTATIONS]
    fichier_a = etat["entites"][PRESENTATIONS][
        "evenements/bdpm.presentations/20261024T141700Z__aaaaaaaaaaaa.jsonl"
    ]
    assert fichier_a == {
        "sha256": sha256_hex(
            (
                sortie / "evenements" / PRESENTATIONS / "20261024T141700Z__aaaaaaaaaaaa.jsonl"
            ).read_bytes()
        ),
        "messages": 17,
        "echecs": 0,
    }
    assert not list(sortie.glob(".publication.json.partiel"))


def test_reprise_ne_publie_que_les_nouveaux_fichiers_et_refuse_sans_option(tmp_path: Path) -> None:
    sortie, n_pres, _ = _sortie(tmp_path)
    bus = BusSimule()
    _, r = _registre_pret()
    publication.executer(sortie, bus, r)
    with pytest.raises(PublicationRefusee, match="--reprendre"):
        publication.executer(sortie, bus, r)
    rien = publication.executer(sortie, bus, r, reprendre=True)
    assert rien.topics == {} and all(x.fichiers == 0 and x.deja_publies for x in rien.resumes)
    initiales, _ = _evenements_presentations()
    _ecrire_jsonl(sortie, PRESENTATIONS, "20261024T161700Z__dddddddddddd.jsonl", initiales[:5])
    rapport = publication.executer(sortie, bus, r, reprendre=True)
    assert rapport.topics == {"pharmaflux.bdpm.presentations.v1": 5}
    (pres,) = [x for x in rapport.resumes if x.identifiant == PRESENTATIONS]
    assert (pres.fichiers, pres.deja_publies, pres.messages) == (1, 2, 5)
    assert len(bus.messages["pharmaflux.bdpm.presentations.v1"]) == n_pres + 5
    etat = publication.lire_etat(sortie / "publication.json")
    assert len(etat[PRESENTATIONS]) == 3


def test_un_fichier_publie_modifie_ou_disparu_fait_refuser(tmp_path: Path) -> None:
    sortie, _, _ = _sortie(tmp_path)
    bus = BusSimule()
    _, r = _registre_pret()
    publication.executer(sortie, bus, r)
    fichier = sortie / "evenements" / DISPO / "20261024T141700Z__cccccccccccc.jsonl"
    fichier.write_bytes(fichier.read_bytes() + b"\n")
    with pytest.raises(PublicationRefusee, match="a changé depuis sa publication"):
        publication.executer(sortie, bus, r, reprendre=True)
    fichier.unlink()
    with pytest.raises(PublicationRefusee, match="n'est plus dans la sortie"):
        publication.executer(sortie, bus, r, reprendre=True)
    assert sum(len(m) for m in bus.messages.values()) == 27, "rien de plus n'est parti"


def test_un_fichier_hors_d_ordre_fait_refuser_avant_le_premier_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    bus = BusSimule()
    simule, r = _registre_pret()
    publication.executer(sortie, bus, r)
    etat_avant = (sortie / "publication.json").read_bytes()
    initiales, _ = _evenements_presentations()
    # Un fichier copié à la main, rangé avant le dernier publié de son entité…
    _ecrire_jsonl(sortie, PRESENTATIONS, "20261024T131700Z__000000000000.jsonl", initiales[:3])
    # … et un fichier en ordre d'une autre entité : il ne part pas non plus, tout le lot est refusé.
    en_ordre = list(comparer(None, _snap(DISPO, "dispo_b.txt", "1517")))
    _ecrire_jsonl(sortie, DISPO, "20261024T151700Z__eeeeeeeeeeee.jsonl", en_ordre)
    with pytest.raises(
        PublicationRefusee, match="se range avant le dernier fichier publié"
    ) as info:
        publication.executer(sortie, bus, r, reprendre=True)
    assert "20261024T131700Z__000000000000.jsonl" in str(info.value)
    assert "20261024T151700Z__bbbbbbbbbbbb.jsonl" in str(info.value), "le dernier publié est nommé"
    assert "jamais réordonné" in str(info.value)
    assert (sortie / "publication.json").read_bytes() == etat_avant, "l'état ne bouge pas"
    assert sum(len(m) for m in bus.messages.values()) == n_pres + n_dispo, "rien n'est parti"
    from typer.testing import CliRunner

    from pharmaflux import cli
    from pharmaflux.cli import application

    monkeypatch.setattr(cli, "fabriquer_bus", lambda _courtier: bus)
    monkeypatch.setattr(cli, "fabriquer_transport_registre", simule.transport)
    resultat = CliRunner().invoke(application, ["publier", "--sortie", str(sortie), "--reprendre"])
    assert resultat.exit_code == 2 and "publication refusée" in texte_nu(resultat.output)


def test_un_fichier_d_evenements_vide_est_publie_et_inscrit_dans_l_etat(tmp_path: Path) -> None:
    sortie, n_pres, _ = _sortie(tmp_path)
    nom = (
        "20261024T161700Z__eeeeeeeeeeee.jsonl"  # un snapshot retenu « identique au dernier retenu »
    )
    vide = _ecrire_jsonl(sortie, PRESENTATIONS, nom, [])
    assert vide.stat().st_size == 0
    bus = BusSimule()
    _, r = _registre_pret()
    journal: list[str] = []
    rapport = publication.executer(sortie, bus, r, journal=journal.append)
    (pres,) = [x for x in rapport.resumes if x.identifiant == PRESENTATIONS]
    assert (pres.fichiers, pres.messages, pres.echecs) == (3, n_pres, 0)
    assert f"bdpm.presentations {nom} : 0 message(s), 0 échec(s)" in journal
    etat = publication.lire_etat(sortie / "publication.json")
    assert etat[PRESENTATIONS][f"evenements/bdpm.presentations/{nom}"] == publication.FichierPublie(
        hashlib.sha256(b"").hexdigest(), 0, 0
    )
    reprise = publication.executer(sortie, bus, r, reprendre=True)
    (pres,) = [x for x in reprise.resumes if x.identifiant == PRESENTATIONS]
    assert (pres.fichiers, pres.deja_publies) == (0, 3), "publié : la reprise ne le reprend pas"


def test_ligne_illisible_et_message_trop_gros_vont_dans_la_file(tmp_path: Path) -> None:
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    fichier = sortie / "evenements" / DISPO / "20261024T141700Z__cccccccccccc.jsonl"
    lignes = fichier.read_bytes().splitlines(keepends=True)
    lignes[2] = b"{cassee\n"
    lignes.insert(4, b"\n")  # une ligne vide est ignorée, comme par lire_evenements
    fichier.write_bytes(b"".join(lignes))
    bus = BusSimule(taille_max=len(lignes[0]) + 10)  # la 1re ligne passe de justesse
    _, r = _registre_pret()
    rapport = publication.executer(sortie, bus, r)
    assert rapport.code_sortie == 3, "un échec est visible, jamais absorbé"
    echecs = bus.messages["pharmaflux.echecs.v1"]
    contenus = [json.loads(m.valeur) for m in echecs]
    assert [c["motif"] for c in contenus].count("illisible") == 1
    (illisible,) = [c for c in contenus if c["motif"] == "illisible"]
    assert (illisible["ligne"], illisible["fichier"], illisible["ligne_brute"]) == (
        3,
        "evenements/bdpm.disponibilite/20261024T141700Z__cccccccccccc.jsonl",
        "{cassee",
    )
    gros = [c for c in contenus if c["motif"] == "trop_gros"]
    assert gros and all(c["id"] and not c["tronquee"] for c in gros)
    assert all(m.cle in (b"bdpm.disponibilite", b"bdpm.presentations") for m in echecs)
    (dispo,) = [x for x in rapport.resumes if x.identifiant == DISPO]
    assert dispo.messages + dispo.echecs == n_dispo, "la publication continue après un échec"
    etat = publication.lire_etat(sortie / "publication.json")
    publie = etat[DISPO]["evenements/bdpm.disponibilite/20261024T141700Z__cccccccccccc.jsonl"]
    assert publie.echecs == dispo.echecs and publie.messages == dispo.messages
    assert rapport.topics["pharmaflux.echecs.v1"] == len(echecs)
    assert sum(v for t, v in rapport.topics.items() if "echecs" not in t) == n_pres + n_dispo - len(
        echecs
    )


def test_une_ligne_d_une_autre_entite_va_dans_la_file(tmp_path: Path) -> None:
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    fichier = sorted((sortie / "evenements" / DISPO).glob("*.jsonl"))[0]
    presentations = sorted((sortie / "evenements" / PRESENTATIONS).glob("*.jsonl"))[0]
    lignes = fichier.read_bytes().splitlines(keepends=True)
    lignes.insert(1, presentations.read_bytes().splitlines(keepends=True)[0])
    fichier.write_bytes(b"".join(lignes))  # une ligne de presentations dans un fichier de dispo
    bus = BusSimule()
    _, r = _registre_pret()
    rapport = publication.executer(sortie, bus, r)
    assert rapport.code_sortie == 3
    (echec,) = bus.messages["pharmaflux.echecs.v1"]
    contenu = json.loads(echec.valeur)
    assert (contenu["motif"], contenu["ligne"], echec.cle) == (
        "illisible",
        2,
        b"bdpm.disponibilite",
    )
    assert "bdpm.presentations" in contenu["detail"] and "bdpm.disponibilite" in contenu["detail"]
    assert len(bus.messages["pharmaflux.bdpm.disponibilite.v1"]) == n_dispo
    assert len(bus.messages["pharmaflux.bdpm.presentations.v1"]) == n_pres, "rien ne part ailleurs"


def test_livraison_en_echec_arrete_sans_avancer_l_etat(tmp_path: Path) -> None:
    sortie, _, _ = _sortie(tmp_path)
    bus = BusSimule(panne="Local: Message timed out (-192)")
    _, r = _registre_pret()
    with pytest.raises(LivraisonEchouee, match="timed out"):
        publication.executer(sortie, bus, r)
    assert not (sortie / "publication.json").exists()


def test_schema_absent_ou_etat_illisible_refusent(tmp_path: Path) -> None:
    sortie, _, _ = _sortie(tmp_path)
    bus = BusSimule()
    _, r = _registre_pret((PRESENTATIONS,))
    with pytest.raises(PublicationRefusee, match="schemas enregistrer"):
        publication.executer(sortie, bus, r)
    assert not bus.topics and not bus.messages
    (sortie / "publication.json").write_text("{pas du json", encoding="utf-8")
    with pytest.raises(PublicationRefusee, match="illisible"):
        publication.executer(sortie, bus, r, reprendre=True)
    (sortie / "publication.json").write_text('{"version": 2, "entites": {}}', encoding="utf-8")
    with pytest.raises(PublicationRefusee, match="version 2"):
        publication.executer(sortie, bus, r, reprendre=True)
    assert publication.lister_fichiers(tmp_path / "vide") == []


# --- ligne de commande ------------------------------------------------------------------------


def test_commandes_publier_et_schemas_enregistrer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from pharmaflux import cli
    from pharmaflux.cli import application

    simule = RegistreSimule()
    bus = BusSimule()
    monkeypatch.setattr(cli, "fabriquer_transport_registre", simule.transport)
    monkeypatch.setattr(cli, "fabriquer_bus", lambda _courtier: bus)
    lanceur = CliRunner()
    sortie, n_pres, n_dispo = _sortie(tmp_path)
    # Sans schéma enregistré : refus, code 2, et le conseil.
    refus = lanceur.invoke(application, ["publier", "--sortie", str(sortie)])
    assert refus.exit_code == 2 and "schemas enregistrer" in texte_nu(refus.output)
    enregistrement = lanceur.invoke(
        application, ["schemas", "enregistrer", "--registre", "http://r.test"]
    )
    assert enregistrement.exit_code == 0, enregistrement.output
    assert "pharmaflux.bdpm.presentations.v1-value" in enregistrement.output
    assert enregistrement.output.count("(nouveau)") == 12, "onze entités et la file des échecs"
    assert enregistrement.output.count("id 1 ") == 11, "même schéma, même id sur les onze sujets"
    assert "pharmaflux.echecs.v1-value" in enregistrement.output
    encore = lanceur.invoke(application, ["schemas", "enregistrer"])
    assert encore.exit_code == 0 and "(nouveau)" not in encore.output, "idempotent"
    resultat = lanceur.invoke(
        application, ["publier", "--sortie", str(sortie), "--courtier", "x:1"]
    )
    assert resultat.exit_code == 0, resultat.output
    assert (
        f"bdpm.presentations           2 fichier(s) publié(s) (0 déjà), {n_pres} message(s),"
        " 0 en échec"
    ) in resultat.output
    assert f"pharmaflux.bdpm.disponibilite.v1 : {n_dispo} message(s)" in resultat.output
    assert "publication.json" in resultat.output
    deja = lanceur.invoke(application, ["publier", "--sortie", str(sortie)])
    assert deja.exit_code == 2 and "--reprendre" in texte_nu(deja.output), "état existant"
    reprise = lanceur.invoke(application, ["publier", "--sortie", str(sortie), "--reprendre"])
    assert reprise.exit_code == 0 and "(2 déjà), 0 message(s)" in reprise.output
    # Rien de nouveau, mais le courtier est arrêté : code non nul quand même (décision 4).
    monkeypatch.setattr(cli, "fabriquer_bus", lambda _courtier: BusSimule(injoignable=True))
    arrete = lanceur.invoke(application, ["publier", "--sortie", str(sortie), "--reprendre"])
    assert arrete.exit_code == 1, arrete.output
    assert "publication interrompue : aucun courtier sur simule:0" in arrete.output
    en_panne = BusSimule(panne="Local: Broker transport failure")
    monkeypatch.setattr(cli, "fabriquer_bus", lambda _courtier: en_panne)
    initiales, _ = _evenements_presentations()
    _ecrire_jsonl(sortie, PRESENTATIONS, "20261024T161700Z__dddddddddddd.jsonl", initiales[:2])
    panne = lanceur.invoke(application, ["publier", "--sortie", str(sortie), "--reprendre"])
    assert panne.exit_code == 1 and "publication interrompue" in panne.output
    monkeypatch.setattr(cli, "fabriquer_transport_registre", lambda: httpx.MockTransport(_refuser))
    hors_ligne = lanceur.invoke(application, ["schemas", "enregistrer"])
    assert hors_ligne.exit_code == 1 and "registre :" in hors_ligne.output


def _refuser(_: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connexion refusée")
