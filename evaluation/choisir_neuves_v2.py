"""Le choix des questions neuves de la v2 qui mesurent les correctifs de la mission 08 (mission 09).

Une règle écrite d'abord, appliquée ici sans LLM ni réseau, sur le jeu de démo et son index
(format 3, avant toute retouche de l'assistant) ; sa sortie est recopiée telle quelle dans
``evaluation/questions-reference-v2.toml``, puis le fichier est figé et committé avant le premier
commit de retouche (addendum 1 G, H). Ce script n'est importé par aucun test.

La règle, pour chaque groupe, sur les CIS du référentiel des spécialités qui ne sont visés par
aucune question de la v1, rangés par sha256 croissant de « <groupe>/<CIS> » :

- **rappel** (4) : « Quel est le dernier avis de SMR rendu sur <dénomination> ? » ; le CIS a un
  dernier dossier SMR unique (une seule date la plus récente) ; on garde les quatre premiers dont
  **aucun fragment ``avis`` n'est dans les dix** que rend la recherche hybride (le constat de
  ``avis_has-003``, fait par la recherche seule) ;
- **date_avis** (3) : « Quel SMR la Commission de la transparence a-t-elle rendu dans le dossier
  <dossier> (<dénomination>) ? », le plus ancien dossier du CIS qui n'a qu'une ligne SMR, le CIS
  en ayant au moins deux (la forme d'``avis_has-007`` et ``-011``) ;
- **date_maj** (3) : « Où en est l'approvisionnement de <dénomination> ? », un CIS qui n'a qu'une
  ligne dans le fichier de disponibilité, avec une date de mise à jour (la forme de
  ``disponibilite-012`` et ``historique-005``).

Un CIS déjà pris par un groupe ne l'est pas par un autre. Lancement :

    uv run python evaluation/choisir_neuves_v2.py > /tmp/neuves.toml
"""

from __future__ import annotations

import hashlib
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

from pharmaflux import bronze
from pharmaflux.cli import _qdrant, fabriquer_transport_qdrant
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.contrats.verification import verifier
from pharmaflux.index import construction, encodeur
from pharmaflux.index.qdrant import Qdrant

JEU = Path("demo/archive")
V1 = Path("evaluation/questions-reference-v1.toml")
DATE_REFERENCE = "2026-10-24"
FICHIERS = {
    "bdpm.specialites": "CIS_bdpm.txt",
    "bdpm.smr": "CIS_HAS_SMR_bdpm.txt",
    "bdpm.disponibilite": "CIS_CIP_Dispo_Spec.txt",
}


def lire(identifiant: str) -> tuple[str, str, list[dict[str, str]]]:
    """L'archive (chemin, sha256) et les lignes du fichier, en dictionnaires par colonne."""
    contrat = charger_tous()[identifiant]
    archive = bronze.derniere(JEU, "bdpm", FICHIERS[identifiant])
    assert archive is not None
    octets = archive.lire()
    lecture = verifier(contrat, octets, fichier=archive.relatif(JEU))
    assert not lecture.bloquantes
    noms = [c.nom for c in contrat.colonnes]
    lignes = [dict(zip(noms, valeurs, strict=True)) for _, valeurs in lecture.lignes]
    return archive.relatif(JEU), hashlib.sha256(octets).hexdigest(), lignes


def ordre(groupe: str, cis: str) -> str:
    return hashlib.sha256(f"{groupe}/{cis}".encode()).hexdigest()


def toml_texte(valeur: str) -> str:
    return '"' + valeur.replace("\\", "\\\\").replace('"', '\\"') + '"'


def bloc(identifiant: str, question: str, cis: str, section: str, attendu: dict) -> str:
    categorie = identifiant.rsplit("-", 1)[0]
    lignes = [
        "[[questions]]",
        f"id = {toml_texte(identifiant)}",
        f"categorie = {toml_texte(categorie)}",
        f"question = {toml_texte(question)}",
        'comportement = "reponse"',
        f"cis_attendu = {toml_texte(cis)}",
        f"section_attendue = {toml_texte(section)}",
        "",
        "[questions.attendu]",
        f"date_reference = {DATE_REFERENCE}",
        f"fichier = {toml_texte(attendu['fichier'])}",
        f"archive = {toml_texte(attendu['archive'])}",
        f"sha256 = {toml_texte(attendu['sha256'])}",
        "cle = { " + ", ".join(f"{k} = {toml_texte(v)}" for k, v in attendu["cle"].items()) + " }",
        "colonnes = [" + ", ".join(toml_texte(c) for c in attendu["colonnes"]) + "]",
    ]
    for valeurs in attendu["valeurs"]:
        lignes += ["", "[[questions.attendu.valeurs]]"]
        lignes += [f"{c} = {toml_texte(valeurs[c])}" for c in attendu["colonnes"]]
    return "\n".join(lignes)


def main() -> int:
    v1 = tomllib.loads(V1.read_text(encoding="utf-8"))["questions"]
    exclus = {str(q["cis_attendu"]) for q in v1 if q.get("cis_attendu")}
    _, _, specialites = lire("bdpm.specialites")
    denomination = {s["code_cis"]: s["denomination"] for s in specialites}
    archive_smr, sha_smr, smr = lire("bdpm.smr")
    archive_dispo, sha_dispo, dispo = lire("bdpm.disponibilite")
    smr_par_cis: dict[str, list[dict[str, str]]] = defaultdict(list)
    for ligne in smr:
        smr_par_cis[ligne["code_cis"]].append(ligne)
    dispo_par_cis: dict[str, list[dict[str, str]]] = defaultdict(list)
    for ligne in dispo:
        dispo_par_cis[ligne["code_cis"]].append(ligne)
    colonnes_smr = ["motif_evaluation", "date_avis", "valeur_smr"]
    colonnes_dispo = ["libelle_statut", "date_debut", "date_mise_a_jour"]
    pris: set[str] = set()
    blocs: list[str] = []
    journal: list[str] = []

    # Le rappel : la recherche seule, sur l'index du jeu (format 3), avant toute retouche.
    encodeur_ = encodeur.charger("e5-small-int8")
    rappel = []
    with Qdrant(_qdrant(None), fabriquer_transport_qdrant()) as qdrant:
        for cis in sorted(smr_par_cis, key=lambda c: ordre("rappel", c)):
            if cis in exclus or cis not in denomination or len(rappel) == 4:
                continue
            lignes = smr_par_cis[cis]
            derniere = max(ligne["date_avis"] for ligne in lignes)
            dossiers = {
                ligne["code_dossier_has"] for ligne in lignes if ligne["date_avis"] == derniere
            }
            if len(dossiers) != 1:
                continue
            question = f"Quel est le dernier avis de SMR rendu sur {denomination[cis]} ?"
            _, resultats = construction.chercher(qdrant, encodeur_, question, 10)
            trouves = [(r.charge["code_cis"], r.charge["section"]) for r in resultats]
            journal.append(f"rappel {cis} : avis dans les dix = {(cis, 'avis') in trouves}")
            if (cis, "avis") in trouves:
                continue
            (dossier,) = dossiers
            valeurs = [ligne for ligne in lignes if ligne["code_dossier_has"] == dossier]
            rappel.append((cis, question, dossier, valeurs))
            pris.add(cis)
    for rang, (cis, question, dossier, valeurs) in enumerate(rappel, start=12):
        attendu = {
            "fichier": "bdpm.smr", "archive": archive_smr, "sha256": sha_smr,
            "cle": {"code_cis": cis, "code_dossier_has": dossier}, "colonnes": colonnes_smr,
            "valeurs": valeurs,
        }  # fmt: skip
        blocs.append(bloc(f"avis_has-{rang:03d}", question, cis, "avis", attendu))

    rang = 12 + len(rappel)
    choisis = 0
    for cis in sorted(smr_par_cis, key=lambda c: ordre("date_avis", c)):
        if cis in exclus or cis in pris or cis not in denomination or choisis == 3:
            continue
        par_dossier: dict[str, list[dict[str, str]]] = defaultdict(list)
        for ligne in smr_par_cis[cis]:
            par_dossier[ligne["code_dossier_has"]].append(ligne)
        uniques = [d for d, lignes in par_dossier.items() if len(lignes) == 1]
        if len(par_dossier) < 2 or not uniques:
            continue
        dossier = min(uniques, key=lambda d: (par_dossier[d][0]["date_avis"], d))
        question = (
            "Quel SMR la Commission de la transparence a-t-elle rendu dans le dossier"
            f" {dossier} ({denomination[cis]}) ?"
        )
        attendu = {
            "fichier": "bdpm.smr", "archive": archive_smr, "sha256": sha_smr,
            "cle": {"code_cis": cis, "code_dossier_has": dossier}, "colonnes": colonnes_smr,
            "valeurs": par_dossier[dossier],
        }  # fmt: skip
        blocs.append(bloc(f"avis_has-{rang:03d}", question, cis, "avis", attendu))
        rang += 1
        choisis += 1
        pris.add(cis)

    choisis = 0
    for cis in sorted(dispo_par_cis, key=lambda c: ordre("date_maj", c)):
        lignes = dispo_par_cis[cis]
        if cis in exclus or cis in pris or cis not in denomination or choisis == 3:
            continue
        if len(lignes) != 1 or not lignes[0]["date_mise_a_jour"]:
            continue
        question = f"Où en est l'approvisionnement de {denomination[cis]} ?"
        attendu = {
            "fichier": "bdpm.disponibilite", "archive": archive_dispo, "sha256": sha_dispo,
            "cle": {"code_cis": cis}, "colonnes": colonnes_dispo, "valeurs": lignes,
        }  # fmt: skip
        blocs.append(
            bloc(f"disponibilite-{13 + choisis:03d}", question, cis, "disponibilite", attendu)
        )
        choisis += 1
        pris.add(cis)

    print("\n\n".join(blocs))
    print("\n".join(journal), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
