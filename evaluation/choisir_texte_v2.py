"""Le choix des questions de la v2 sur le texte des avis de la HAS (mission 09, palier 3).

Une règle écrite d'abord, appliquée ici sans LLM ni réseau, sur les pages d'avis du jeu de démo
(``demo/archive``, manifeste ``has-pages.jsonl``) ; sa sortie est recopiée telle quelle dans
``evaluation/questions-reference-v2.toml``. Ce script n'est importé par aucun test.

La règle :
- les pages du jeu dont l'extraction (v2) aboutit et dont le contrôle de dossier est possible,
  liées à un seul dossier, hors des pages imposées par la collecte (``demo.has``, elles servent
  aux pièges), rangées par sha256 croissant de « texte/<page> » ;
- pour chacune, le CIS lié au dossier le plus petit, qu'aucune question de la v2 ne vise encore ;
- les thèmes, dans l'ordre et en tournant, chacun jusqu'à son nombre : la nature de la demande
  (4), la date de l'avis (4), « L'essentiel » (4), « Quel progrès ? » (4), le lien (3). Une page
  qui n'a pas la rubrique du thème passe au thème suivant ;
- l'extrait dû : la nature de la demande, ou les douze premiers mots de la première ligne qui
  n'est pas un intertitre dans la rubrique ; aucun pour la date et le lien ;
- chaque question attend la page d'avis rendue sous la réponse (``lien_attendu``), et la date de
  l'avis dans le texte.

Lancement : ``uv run python evaluation/choisir_texte_v2.py > /tmp/texte.toml``.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from pharmaflux import bronze
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.contrats.verification import verifier
from pharmaflux.demo.has import PAGES_IMPOSEES
from pharmaflux.has import extraction

JEU = Path("demo/archive")
V2 = Path("evaluation/questions-reference-v2.toml")
THEMES = (("nature", 4), ("date", 4), ("essentiel", 4), ("progres", 4), ("lien", 3))
RUBRIQUES = {"essentiel": "L'essentiel", "progres": "Quel progrès ?"}
PREMIER_NUMERO = 24  # après avis_has-023


def lire(identifiant: str, fichier: str) -> list[dict[str, str]]:
    contrat = charger_tous()[identifiant]
    archive = bronze.derniere(JEU, "bdpm", fichier)
    assert archive is not None
    lecture = verifier(contrat, archive.lire(), fichier=archive.relatif(JEU))
    noms = [c.nom for c in contrat.colonnes]
    return [dict(zip(noms, valeurs, strict=True)) for _, valeurs in lecture.lignes]


def toml_texte(valeur: str) -> str:
    return '"' + valeur.replace("\\", "\\\\").replace('"', '\\"') + '"'


def question_texte(theme: str, nom: str, dossier: str) -> str:
    return {
        "nature": f"Quelle demande la Commission de la transparence a-t-elle examinée dans le"
        f" dossier {dossier} de {nom} ?",
        "date": f"À quelle date la Commission de la transparence a-t-elle rendu son avis sur {nom}"
        f" dans le dossier {dossier} ?",
        "essentiel": f"Que dit l'essentiel de l'avis de la Commission de la transparence sur {nom}"
        f" (dossier {dossier}) ?",
        "progres": f"Quel progrès {nom} apporte-t-il selon l'avis de la Commission de la"
        f" transparence (dossier {dossier}) ?",
        "lien": f"Où lire l'avis de la Commission de la transparence sur {nom}"
        f" (dossier {dossier}) ?",
    }[theme]


def extrait_du_theme(theme: str, avis: extraction.AvisExtrait) -> str | None:
    if theme == "nature":
        return avis.nature_demande if len(avis.nature_demande.split()) <= 12 else None
    if theme in RUBRIQUES:
        for ligne in avis.lignes:
            if ligne.rubrique == RUBRIQUES[theme] and ligne.genre != "intertitre":
                return " ".join(ligne.texte.split()[:12])
    return None


def bloc(numero: int, question: str, cis: str, has: dict[str, Any]) -> str:
    lignes = [
        "[[questions]]",
        f'id = "avis_has-{numero:03d}"',
        'categorie = "avis_has"',
        f"question = {toml_texte(question)}",
        'comportement = "reponse"',
        f"cis_attendu = {toml_texte(cis)}",
        'section_attendue = "avis_has"',
        f"lien_attendu = {toml_texte(has['url'])}",
        "",
        "[questions.attendu_has]",
    ]
    lignes += [f"{cle} = {toml_texte(valeur)}" for cle, valeur in has.items() if valeur is not None]
    return "\n".join(lignes)


def main() -> int:
    v2 = tomllib.loads(V2.read_text(encoding="utf-8"))["questions"]
    pris = {str(q["cis_attendu"]) for q in v2 if q.get("cis_attendu")}
    denomination = {
        s["code_cis"]: s["denomination"] for s in lire("bdpm.specialites", "CIS_bdpm.txt")
    }
    cis_par_dossier: dict[str, set[str]] = {}
    for genre, fichier in (
        ("bdpm.smr", "CIS_HAS_SMR_bdpm.txt"),
        ("bdpm.asmr", "CIS_HAS_ASMR_bdpm.txt"),
    ):
        for ligne in lire(genre, fichier):
            cis_par_dossier.setdefault(ligne["code_dossier_has"], set()).add(ligne["code_cis"])
    lignes = [
        json.loads(x) for x in (JEU / "manifeste" / "has-pages.jsonl").read_text().splitlines()
    ]
    lignes.sort(key=lambda d: hashlib.sha256(f"texte/{d['page_id']}".encode()).hexdigest())
    restants = dict(THEMES)
    ordre = [theme for theme, _ in THEMES]
    rang_theme, numero, blocs = 0, PREMIER_NUMERO, []
    for ligne in lignes:
        if not any(restants.values()):
            break
        if ligne["page_id"] in PAGES_IMPOSEES or len(ligne["dossiers"]) != 1:
            continue
        octets = bronze.lire_archive(JEU / ligne["archive"])
        try:
            avis = extraction.extraire(octets, dossiers=tuple(ligne["dossiers"]))
        except extraction.PageRejetee:
            continue
        if not avis.dossiers_documents:
            continue
        (dossier,) = ligne["dossiers"]
        candidats = sorted(c for c in cis_par_dossier.get(dossier, ()) if c in denomination)
        candidats = [c for c in candidats if c not in pris]
        if not candidats:
            continue
        cis = candidats[0]
        for decalage in range(len(ordre)):
            theme = ordre[(rang_theme + decalage) % len(ordre)]
            if not restants[theme]:
                continue
            extrait = extrait_du_theme(theme, avis)
            if theme in ("nature", "essentiel", "progres") and extrait is None:
                continue
            has = {
                "archive": ligne["archive"],
                "sha256": ligne["sha256"],
                "url": ligne["url"],
                "dossier": dossier,
                "date_avis": avis.date_avis.isoformat(),
                "mis_en_ligne": avis.mis_en_ligne.isoformat(),
                "nature_demande": avis.nature_demande,
                "extrait": extrait if theme != "date" and theme != "lien" else None,
            }
            blocs.append(bloc(numero, question_texte(theme, denomination[cis], dossier), cis, has))
            print(f"avis_has-{numero:03d} {theme} {ligne['page_id']} {cis}", file=sys.stderr)
            numero += 1
            restants[theme] -= 1
            rang_theme = (ordre.index(theme) + 1) % len(ordre)
            pris.add(cis)
            break
    print("\n\n".join(blocs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
