"""Les requêtes du §0 de la mission 09 vers www.has-sante.fr, une par appel.

Douze au plus pour toute la mission (ordre de mission 09, « Qui fait quelle
requête ») : le journal ``journal-s0.jsonl`` est en ajout seul, et le script
refuse la treizième. Les requêtes partent en série, deux secondes au moins
après la fin de la précédente (lue dans le journal), avec le ``User-Agent`` de
la collecte de la BDPM. Un seul hôte, en https. Aucune redirection n'est
suivie : on la suit à la main, requête par requête, et chacune compte. Le
corps d'une réponse ``GET`` est gardé à l'octet sous le nom donné, jamais
réécrit, et ses en-têtes dans le ``.headers`` voisin.

    uv run python tests/fixtures/has/requetes_s0.py GET <url> <nom>
    uv run python tests/fixtures/has/requetes_s0.py HEAD <url> [<nom>]
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from pharmaflux.collecte.telechargement import agent_utilisateur

DOSSIER = Path(__file__).resolve().parent
JOURNAL = DOSSIER / "journal-s0.jsonl"
HOTE = "www.has-sante.fr"
PLAFOND = 12
PAUSE_SECONDES = 2.0
DELAI_SECONDES = 60.0


def lire_journal() -> list[dict[str, object]]:
    if not JOURNAL.exists():
        return []
    texte = JOURNAL.read_text(encoding="utf-8")
    return [json.loads(ligne) for ligne in texte.splitlines() if ligne.strip()]


def refuser(motif: str) -> int:
    print(f"refusé : {motif}", file=sys.stderr)
    return 2


def ecrire_en_tetes(chemin: Path, reponse: httpx.Response) -> None:
    lignes = [f"{reponse.http_version} {reponse.status_code} {reponse.reason_phrase}"]
    lignes += [f"{nom}: {valeur}" for nom, valeur in reponse.headers.multi_items()]
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main(arguments: list[str]) -> int:
    if len(arguments) not in (2, 3) or arguments[0] not in ("GET", "HEAD"):
        return refuser(f"usage incorrect\n{__doc__}")
    methode, url = arguments[0], arguments[1]
    nom = arguments[2] if len(arguments) == 3 else None
    morceaux = urlsplit(url)
    if morceaux.scheme != "https" or morceaux.hostname != HOTE:
        return refuser(f"{url} : seul https://{HOTE} est permis")
    if methode == "GET" and nom is None:
        return refuser("un GET garde son corps : donner un nom")
    if nom is not None and ("/" in nom or (DOSSIER / nom).exists()):
        return refuser(f"{nom} : nom invalide ou déjà pris (rien n'est réécrit)")
    journal = lire_journal()
    if len(journal) >= PLAFOND:
        return refuser(f"{len(journal)} requêtes au journal : le plafond est {PLAFOND}")
    if journal:
        fin_precedente = datetime.fromisoformat(str(journal[-1]["fin"]))
        ecoule = (datetime.now(UTC) - fin_precedente).total_seconds()
        if ecoule < PAUSE_SECONDES:
            time.sleep(PAUSE_SECONDES - ecoule)

    ligne: dict[str, object] = {
        "n": len(journal) + 1,
        "methode": methode,
        "url": url,
        "user_agent": agent_utilisateur(),
        "fichier": nom,
    }
    debut = datetime.now(UTC)
    with httpx.Client(
        headers={"User-Agent": agent_utilisateur()},
        follow_redirects=False,
        timeout=httpx.Timeout(DELAI_SECONDES),
    ) as client:
        try:
            reponse = client.request(methode, url)
        except httpx.HTTPError as exc:
            ligne |= {"debut": debut.isoformat(), "fin": datetime.now(UTC).isoformat()}
            ligne |= {"statut": None, "erreur": f"{type(exc).__name__}: {exc}"}
            with JOURNAL.open("a", encoding="utf-8") as sortie:
                sortie.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            print(f"#{ligne['n']} {methode} {url} : erreur {ligne['erreur']}")
            return 1
    fin = datetime.now(UTC)
    contenu = reponse.content
    ligne |= {
        "debut": debut.isoformat(),
        "fin": fin.isoformat(),
        "statut": reponse.status_code,
        "taille": len(contenu),
        "sha256": hashlib.sha256(contenu).hexdigest(),
        "content_type": reponse.headers.get("content-type"),
        "content_length": reponse.headers.get("content-length"),
        "content_encoding": reponse.headers.get("content-encoding"),
        "location": reponse.headers.get("location"),
        "last_modified": reponse.headers.get("last-modified"),
    }
    if nom is not None:
        if methode == "GET":
            (DOSSIER / nom).write_bytes(contenu)
        ecrire_en_tetes(DOSSIER / f"{nom}.headers", reponse)
    with JOURNAL.open("a", encoding="utf-8") as sortie:
        sortie.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    print(
        f"#{ligne['n']} {debut:%H:%M:%S} UTC {methode} {url} -> {reponse.status_code}, "
        f"{len(contenu)} octets, {ligne['content_type']}, location={ligne['location']}, "
        f"content-length={ligne['content_length']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
