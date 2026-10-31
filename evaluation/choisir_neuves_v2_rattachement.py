"""Le choix des questions neuves qui mesurent le rattachement des pages d'avis (mission 09).

Décision de l'IeC (``decision-question-2.md`` et sa suite) : une page d'avis ne se rattache
qu'aux fiches que le référentiel des spécialités nomme. Le changement se mesure sur des questions
tirées **avant** lui, par cette règle écrite, sans LLM, sur les pages du jeu de démo ; sa sortie
est recopiée telle quelle dans ``evaluation/questions-reference-v2.toml``. Ce script n'est importé
par aucun test.

La règle :
- les pages du jeu extraites (v2) liées à un seul dossier, hors des pages de MOUNJARO (qui ont
  servi à trouver le défaut) et des pages qu'une question de la v2 cite déjà, rangées par sha256
  croissant de « rattachement/<page> » ;
- le nom du médicament est le titre de la page avant « ( » (« KEYTRUDA (pembrolizumab) - … » :
  « KEYTRUDA ») ; la question est celle de la démonstration : « Quel progrès <nom> apporte-t-il
  selon l'avis de la Commission de la transparence ? » ;
- **pages mixtes** (liées à des CIS du référentiel et à des CIS absents) : quatre au plus, dont
  le premier mot du nom est le premier mot de la dénomination d'une fiche du référentiel liée à
  la page, et qui ont la rubrique « Quel progrès ? ». Attendu : une réponse qui rend la page et
  porte la date de l'avis et l'extrait (les douze premiers mots de la rubrique) ;
- **pages sans fiche du référentiel** (liées seulement à des CIS absents) : deux au plus, dont
  le premier mot du nom n'est le premier mot d'aucune dénomination du référentiel (sinon la
  question viserait un autre médicament). Attendu : une abstention, orientée vers la HAS.

La règle se lit contre la v2 **d'avant** ces questions (celle du commit qui les précède) : sur la
v2 qui les contient, leurs pages sont « déjà citées » et la règle passe aux suivantes. Lancement :

    git show <commit d'avant>:evaluation/questions-reference-v2.toml > /tmp/v2-avant.toml
    uv run python evaluation/choisir_neuves_v2_rattachement.py /tmp/v2-avant.toml
"""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path

from pharmaflux import bronze
from pharmaflux.contrats.chargeur import charger_tous
from pharmaflux.contrats.verification import verifier
from pharmaflux.has import extraction
from pharmaflux.index import lexical

JEU = Path("demo/archive")
V2 = Path("evaluation/questions-reference-v2.toml")
PREMIER_NUMERO = 51  # après avis_has-050
MIXTES, SANS_FICHE = 4, 2
PRUDENCE = (
    "Page mixte : {} est liée à {} fiche(s) du référentiel et à {} CIS absent(s). La réponse cite"
    " la page par une fiche du référentiel."
)
A = "\u2019"  # l'apostrophe typographique des motifs
MOTIF = (
    "{} n"
    + A
    + "est pas dans le référentiel des spécialités : la page de son avis ({}, dossier {})"
    " est dans l" + A + "archive, mais l" + A + "index ne la rattache à aucune fiche (ADR 0013)."
    " L" + A + "identité d" + A + "un médicament vient du référentiel."
)
ORIENTATION = "La Haute Autorité de santé, qui publie l'avis de la Commission de la transparence."


def lire(identifiant: str, fichier: str) -> list[dict[str, str]]:
    contrat = charger_tous()[identifiant]
    archive = bronze.derniere(JEU, "bdpm", fichier)
    assert archive is not None
    lecture = verifier(contrat, archive.lire(), fichier=archive.relatif(JEU))
    noms = [c.nom for c in contrat.colonnes]
    return [dict(zip(noms, valeurs, strict=True)) for _, valeurs in lecture.lignes]


def premier_mot(texte: str) -> str:
    return next((j for j in lexical.jetons(texte) if j.isalpha() and len(j) >= 3), "")


def toml_texte(valeur: str) -> str:
    return '"' + valeur.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    jeu = Path(sys.argv[1]) if len(sys.argv) > 1 else V2
    v2 = tomllib.loads(jeu.read_text(encoding="utf-8"))["questions"]
    deja = {q["attendu_has"]["url"] for q in v2 if "attendu_has" in q}
    deja |= {q["lien_attendu"] for q in v2 if "lien_attendu" in q}
    denomination = {
        s["code_cis"]: s["denomination"] for s in lire("bdpm.specialites", "CIS_bdpm.txt")
    }
    premiers_du_referentiel = {premier_mot(d) for d in denomination.values()}
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
    lignes.sort(key=lambda d: hashlib.sha256(f"rattachement/{d['page_id']}".encode()).hexdigest())
    numero, blocs, mixtes, sans_fiche = PREMIER_NUMERO, [], 0, 0
    for ligne in lignes:
        if ligne["url"] in deja or len(ligne["dossiers"]) != 1:
            continue
        try:
            avis = extraction.extraire(
                bronze.lire_archive(JEU / ligne["archive"]), dossiers=tuple(ligne["dossiers"])
            )
        except extraction.PageRejetee:
            continue
        nom = avis.titre.split(" (")[0].strip()
        if "MOUNJARO" in avis.titre.upper() or not nom:
            continue
        (dossier,) = ligne["dossiers"]
        cis = cis_par_dossier.get(dossier, set())
        du_referentiel = sorted(c for c in cis if c in denomination)
        absents = sorted(c for c in cis if c not in denomination)
        question = (
            f"Quel progrès {nom} apporte-t-il selon l'avis de la Commission de la transparence ?"
        )
        if du_referentiel and absents and mixtes < MIXTES:
            if premier_mot(nom) not in {premier_mot(denomination[c]) for c in du_referentiel}:
                continue
            progres = [
                x.texte
                for x in avis.lignes
                if x.rubrique == "Quel progrès ?" and x.genre != "intertitre"
            ]
            if not progres:
                continue
            extrait = " ".join(progres[0].split()[:12])
            combien = (len(du_referentiel), len(absents))
            blocs.append("\n".join([
                "[[questions]]",
                f'id = "avis_has-{numero:03d}"',
                'categorie = "avis_has"',
                f"question = {toml_texte(question)}",
                'comportement = "reponse"',
                f"prudence = {toml_texte(PRUDENCE.format(ligne['page_id'], *combien))}",
                f"lien_attendu = {toml_texte(ligne['url'])}",
                "",
                "[questions.attendu_has]",
                f"archive = {toml_texte(ligne['archive'])}",
                f"sha256 = {toml_texte(ligne['sha256'])}",
                f"url = {toml_texte(ligne['url'])}",
                f"dossier = {toml_texte(dossier)}",
                f"date_avis = {toml_texte(avis.date_avis.isoformat())}",
                f"mis_en_ligne = {toml_texte(avis.mis_en_ligne.isoformat())}",
                f"nature_demande = {toml_texte(avis.nature_demande)}",
                f"extrait = {toml_texte(extrait)}",
            ]))  # fmt: skip
            print(f"avis_has-{numero:03d} mixte {ligne['page_id']} {nom}", file=sys.stderr)
        elif absents and not du_referentiel and sans_fiche < SANS_FICHE:
            if premier_mot(nom) in premiers_du_referentiel:
                continue
            blocs.append("\n".join([
                "[[questions]]",
                f'id = "avis_has-{numero:03d}"',
                'categorie = "avis_has"',
                f"question = {toml_texte(question)}",
                'comportement = "abstention"',
                f"motif = {toml_texte(MOTIF.format(nom, ligne['page_id'], dossier))}",
                f"orientation = {toml_texte(ORIENTATION)}",
            ]))  # fmt: skip
            print(f"avis_has-{numero:03d} sans fiche {ligne['page_id']} {nom}", file=sys.stderr)
        else:
            continue
        numero += 1
        if du_referentiel:
            mixtes += 1
        else:
            sans_fiche += 1
        if mixtes == MIXTES and sans_fiche == SANS_FICHE:
            break
    print("\n\n".join(blocs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
