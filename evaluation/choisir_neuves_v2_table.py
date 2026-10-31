"""Le choix des questions neuves qui mesurent le changement de la table des sections (mission 09).

Réponse de l'IeC à la question 1 du palier 2 (``controle-palier-2.md``) : la table tenait
« SMR » pour satisfait par un fragment ``avis_has``, alors que le dernier SMR d'un médicament
n'est sûrement que dans le fragment ``avis`` de la BDPM. Le changement de la table se mesure sur
des questions tirées **avant** lui, par cette règle écrite, sans LLM, sur le jeu de démo et son
index, avec le chemin de l'assistant tel qu'il est au commit qui les fige (déduplication et
rappel par section compris). Sa sortie est recopiée telle quelle dans
``evaluation/questions-reference-v2.toml``. Ce script n'est importé par aucun test.

La règle, sur les CIS qu'aucune question de la v2 ne vise encore, rangés par sha256 croissant de
« table/<genre>/<CIS> », pour le SMR (trois questions au plus) puis pour l'ASMR (deux au plus) :
- la question est « Quel est le dernier avis de SMR rendu sur <dénomination> ? » (ou « d'ASMR ») ;
- le CIS a un dernier dossier unique pour ce genre d'avis, à la date D ;
- aucune page d'avis du CIS dans l'index n'est datée de D : ce dernier avis n'est que dans le
  fragment ``avis`` de la BDPM ;
- parmi les dix fragments que le chemin fournit au LLM, un fragment ``avis_has`` du CIS, plus
  ancien que D, est présent, et son fragment ``avis`` ne l'est pas : le défaut, constaté par la
  recherche seule.

Lancement : ``uv run python evaluation/choisir_neuves_v2_table.py > /tmp/table.toml``.
"""

from __future__ import annotations

import hashlib
import sys
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

from pharmaflux import bronze
from pharmaflux.assistant import chemin
from pharmaflux.cli import _qdrant, fabriquer_transport_qdrant
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.contrats.verification import verifier
from pharmaflux.index import encodeur
from pharmaflux.index.qdrant import Qdrant

JEU = Path("demo/archive")
V2 = Path("evaluation/questions-reference-v2.toml")
DATE_REFERENCE = "2026-10-24"
PREMIER_NUMERO = 19  # après avis_has-018, la dernière question neuve figée par bbb9809
GENRES = (("smr", "bdpm.smr", "CIS_HAS_SMR_bdpm.txt", "de SMR", 3),
          ("asmr", "bdpm.asmr", "CIS_HAS_ASMR_bdpm.txt", "d'ASMR", 2))  # fmt: skip


def lire(identifiant: str, fichier: str) -> tuple[str, str, list[dict[str, str]]]:
    contrat = charger_tous()[identifiant]
    archive = bronze.derniere(JEU, "bdpm", fichier)
    assert archive is not None
    octets = archive.lire()
    lecture = verifier(contrat, octets, fichier=archive.relatif(JEU))
    assert not lecture.bloquantes
    noms = [c.nom for c in contrat.colonnes]
    lignes = [dict(zip(noms, valeurs, strict=True)) for _, valeurs in lecture.lignes]
    return archive.relatif(JEU), hashlib.sha256(octets).hexdigest(), lignes


def toml_texte(valeur: str) -> str:
    return '"' + valeur.replace("\\", "\\\\").replace('"', '\\"') + '"'


def bloc(numero: int, question: str, cis: str, attendu: dict[str, Any]) -> str:
    lignes = [
        "[[questions]]",
        f'id = "avis_has-{numero:03d}"',
        'categorie = "avis_has"',
        f"question = {toml_texte(question)}",
        'comportement = "reponse"',
        f"cis_attendu = {toml_texte(cis)}",
        'section_attendue = "avis"',
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
    v2 = tomllib.loads(V2.read_text(encoding="utf-8"))["questions"]
    pris = {str(q["cis_attendu"]) for q in v2 if q.get("cis_attendu")}
    _, _, specialites = lire("bdpm.specialites", "CIS_bdpm.txt")
    denomination = {s["code_cis"]: s["denomination"] for s in specialites}
    e5 = encodeur.charger("e5-small-int8")
    blocs: list[str] = []
    journal: list[str] = []
    numero = PREMIER_NUMERO
    with Qdrant(_qdrant(None), fabriquer_transport_qdrant()) as qdrant:
        dates_des_pages: dict[str, set[str]] = defaultdict(set)
        filtre = {"must": [{"key": "section", "match": {"value": "avis_has"}}]}
        for point in qdrant.parcourir(qdrant.alias_fragments, filtre, champs=["code_cis", "page"]):
            charge = point["payload"]
            dates_des_pages[charge["code_cis"]].add(charge["page"]["date_avis"].replace("-", ""))
        dictionnaire = chemin.charger_dictionnaire(qdrant)
        for genre, identifiant, fichier, libelle, nombre in GENRES:
            archive, sha256, lignes = lire(identifiant, fichier)
            par_cis: dict[str, list[dict[str, str]]] = defaultdict(list)
            for ligne in lignes:
                par_cis[ligne["code_cis"]].append(ligne)
            retenus = 0
            cle_tri = lambda c, g=genre: hashlib.sha256(f"table/{g}/{c}".encode()).hexdigest()  # noqa: E731
            for cis in sorted(dates_des_pages, key=cle_tri):
                if retenus == nombre or cis in pris or cis not in denomination:
                    continue
                avis = par_cis.get(cis, [])
                if not avis:
                    continue
                derniere = max(a["date_avis"] for a in avis)
                dossiers = {a["code_dossier_has"] for a in avis if a["date_avis"] == derniere}
                if len(dossiers) != 1 or derniere in dates_des_pages[cis]:
                    continue
                question = f"Quel est le dernier avis {libelle} rendu sur {denomination[cis]} ?"
                prepare = chemin.preparer(qdrant, e5, question, dictionnaire=dictionnaire)
                if not isinstance(prepare, chemin.Appel):
                    continue
                dix = [r.charge for r in prepare.resultats]
                avec_avis = any(c["code_cis"] == cis and c["section"] == "avis" for c in dix)
                anciennes = [
                    c for c in dix if c["code_cis"] == cis and c["section"] == "avis_has"
                    and c["page"]["date_avis"].replace("-", "") < derniere
                ]  # fmt: skip
                journal.append(
                    f"{genre} {cis} : avis {avec_avis}, avis_has plus ancien {bool(anciennes)}"
                )
                if avec_avis or not anciennes:
                    continue
                (dossier,) = dossiers
                colonnes = ["motif_evaluation", "date_avis", f"valeur_{genre}"]
                attendu = {
                    "fichier": identifiant, "archive": archive, "sha256": sha256,
                    "cle": {"code_cis": cis, "code_dossier_has": dossier}, "colonnes": colonnes,
                    "valeurs": [a for a in avis if a["code_dossier_has"] == dossier],
                }  # fmt: skip
                blocs.append(bloc(numero, question, cis, attendu))
                numero += 1
                retenus += 1
                pris.add(cis)
    print("\n\n".join(blocs))
    print("\n".join(journal), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
