"""Le débit de l'encodage d'e5-small-int8 sur le VPS, selon le nombre de fils d'onnxruntime.

Mission 10, palier 2 (décision de l'IeC au contrôle des mesures). Le premier
remplissage a encodé ses 75 605 fragments sur environ un cœur, alors que l'unité
en permet un et demi : onnxruntime choisit-il son nombre de fils d'après
``/proc/cpuinfo``, que ``ProcSubset=pid`` lui cache ?

Le script encode un échantillon fixe de fragments (un sur ``pas``, lus dans
``fragments.jsonl`` du dossier de travail de l'index), par lots de 256 comme la
construction, avec ``intra_op_num_threads`` laissé au défaut (0), puis fixé à
1 et à 2. Il rend, pour chaque réglage, le débit, le temps processeur et le
nombre de fils vus. Il n'écrit rien, ne joint aucun service et ne change rien
au code de l'index : la décision se prend sur ses chiffres.

Lancé par le codeur, depuis la version déposée, par son chemin :
``<version>/.venv/bin/python -I <version>/infra/vps/mesurer_encodage.py
--fragments /srv/pharmaflux/derive/index/fragments.jsonl --modeles /srv/pharmaflux/modeles``
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import threading
import time
from pathlib import Path
from typing import Any

LOT = 256  # comme pharmaflux.index.construction.LOT
REGLAGES = (0, 1, 2)  # 0 : le défaut d'onnxruntime


def echantillon(fragments: Path, taille: int) -> list[str]:
    """Un fragment sur ``pas``, du premier au dernier : le même échantillon à chaque lancement."""
    with fragments.open("rb") as fichier:
        total = sum(1 for _ in fichier)
    pas = max(1, total // taille)
    textes: list[str] = []
    with fragments.open("rb") as fichier:
        for rang, ligne in enumerate(fichier):
            if rang % pas == 0 and len(textes) < taille:
                textes.append(json.loads(ligne)["texte"])
    return textes


def fils_vus() -> int:
    try:
        return sum(1 for _ in Path("/proc/self/task").iterdir())
    except OSError:
        return threading.active_count()


def mesurer(textes: list[str], modeles: Path, fils: int) -> dict[str, Any]:
    import onnxruntime

    from pharmaflux.index import encodeur

    modele = encodeur.charger("e5-small-int8", modeles)
    assert isinstance(modele, encodeur.E5Onnx)
    options = onnxruntime.SessionOptions()
    options.log_severity_level = 3
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    options.intra_op_num_threads = fils
    modele._session_ = onnxruntime.InferenceSession(
        str(modele._dossier / "onnx" / "model_quantized.onnx"),
        options,
        providers=["CPUExecutionProvider"],
    )
    modele._entrees = {e.name for e in modele._session_.get_inputs()}
    modele.passages(textes[:8])  # la première exécution prépare les noyaux : hors mesure
    maximum = fils_vus()
    avant, depart = resource.getrusage(resource.RUSAGE_SELF), time.monotonic()
    for debut in range(0, len(textes), LOT):
        modele.passages(textes[debut : debut + LOT])
        maximum = max(maximum, fils_vus())
    duree = time.monotonic() - depart
    apres = resource.getrusage(resource.RUSAGE_SELF)
    processeur = (apres.ru_utime - avant.ru_utime) + (apres.ru_stime - avant.ru_stime)
    return {
        "intra_op_num_threads": fils,
        "fragments": len(textes),
        "duree_s": round(duree, 1),
        "fragments_par_s": round(len(textes) / duree, 2),
        "coeurs_occupes": round(processeur / duree, 2),
        "fils_vus": maximum,
    }


def main() -> int:
    analyse = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyse.add_argument("--fragments", type=Path, required=True)
    analyse.add_argument("--modeles", type=Path, required=True)
    analyse.add_argument("--taille", type=int, default=1024)
    options = analyse.parse_args()
    contexte = {
        "cpu_count": os.cpu_count(),
        "affinite": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "cpuinfo_lisible": os.access("/proc/cpuinfo", os.R_OK),
    }
    print(json.dumps({"contexte": contexte}, ensure_ascii=False), flush=True)
    textes = echantillon(options.fragments, options.taille)
    for fils in REGLAGES:
        print(json.dumps(mesurer(textes, options.modeles, fils), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
