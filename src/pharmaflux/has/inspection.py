"""``has extraire`` : l'extraction rejouée sur les pages archivées, pour lire et pour vérifier.

L'index ne lit jamais ce que produit cette commande : il recalcule l'extraction à chaque
construction (addendum 1, D2). Elle sert à **inspecter** (le bilan des rejets, un JSON Lines à
lire) et à **vérifier** (``--verifier``) :

- la non-altération : chaque ligne extraite se retrouve, dans l'ordre, dans le texte que le
  second lecteur tire de la page (``verification``) ;
- le déterminisme : une seconde extraction des mêmes octets donne la même empreinte ;
- la constance : le texte est celui que la collecte a consigné au manifeste, quelle que soit la
  version de l'extracteur (l'empreinte est recalculée sous la version consignée) ;
- les changements de statut d'une version à l'autre (« rejetée » en v1, « extraite » en v2) :
  listés à part, attendus ; à version égale, ce serait une divergence.

Une page dont le document d'avis ne porte aucun numéro de dossier lisible est acceptée (le
rattachement vient de la BDPM), mais comptée à part : son contrôle de dossier est impossible.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from pharmaflux import bronze
from pharmaflux.has import extraction, verification
from pharmaflux.has import manifeste as mf

_SENS = ("rejetée → extraite", "extraite → rejetée")


@dataclass(frozen=True, slots=True)
class PageArchivee:
    page_id: str
    url: str
    archive: Path
    dossiers: tuple[str, ...] | None
    empreinte_consignee: str | None
    extracteur_consigne: int | None
    rejet_consigne: str | None = None


@dataclass(slots=True)
class BilanExtraction:
    verifier: bool
    pages: int = 0
    extraites: int = 0
    rejets: Counter[str] = field(default_factory=Counter)
    ecarts: list[str] = field(default_factory=list)
    divergences: list[str] = field(default_factory=list)
    sans_controle: list[str] = field(default_factory=list)
    empreintes_egales: int = 0
    changements: list[str] = field(default_factory=list)
    changements_sens: Counter[str] = field(default_factory=Counter)

    @property
    def code_sortie(self) -> int:
        if self.pages == 0:
            return 2
        return 1 if self.ecarts or self.divergences else 0

    def resume(self) -> str:
        rejets = ", ".join(f"{motif} {n}" for motif, n in sorted(self.rejets.items()))
        lignes = [
            f"{self.pages} page(s) : {self.extraites} extraite(s),"
            f" {sum(self.rejets.values())} rejetée(s){' (' + rejets + ')' if rejets else ''}"
            f" ; extracteur v{extraction.VERSION_EXTRACTEUR}",
            f"contrôle de dossier impossible : {len(self.sans_controle)}"
            " (le document d'avis ne porte aucun numéro de dossier lisible)",
        ]
        lignes += [f"  sans contrôle de dossier : {page}" for page in self.sans_controle]
        if self.verifier:
            lignes.append(
                f"non-altération : {self.extraites - len(self.ecarts)} conforme(s),"
                f" {len(self.ecarts)} avec écart ; déterminisme et empreintes du manifeste :"
                f" {len(self.divergences)} divergence(s)"
            )
            lignes += [f"  écart : {ecart}" for ecart in self.ecarts]
            lignes += [f"  divergence : {divergence}" for divergence in self.divergences]
            lignes.append(
                f"empreintes du texte égales à celles du manifeste : {self.empreintes_egales}"
            )
            sens = ", ".join(f"{s} {self.changements_sens[s]}" for s in _SENS)
            lignes.append(
                f"statut changé depuis la version du manifeste : {len(self.changements)} ({sens})"
            )
            lignes += [f"  statut changé : {changement}" for changement in self.changements]
        return "\n".join(lignes)


def pages_archivees(racine: Path) -> list[PageArchivee]:
    """La dernière archive de chaque page, d'après le manifeste (qui fait foi)."""
    dernieres: dict[str, PageArchivee] = {}
    for ligne in mf.lire(racine):
        if ligne.role != mf.Role.PAGE or ligne.statut not in mf.ARCHIVES or not ligne.archive:
            continue
        assert ligne.page_id is not None
        dernieres[ligne.page_id] = PageArchivee(
            page_id=ligne.page_id,
            url=ligne.url,
            archive=racine / ligne.archive,
            dossiers=tuple(ligne.dossiers) if ligne.dossiers else None,
            empreinte_consignee=ligne.empreinte_texte,
            extracteur_consigne=ligne.extracteur,
            rejet_consigne=ligne.rejet,
        )
    return [dernieres[page] for page in sorted(dernieres)]


def pages_de_fichiers(chemins: Iterable[Path]) -> list[PageArchivee]:
    """Des fichiers donnés à la main (``.html`` ou ``.html.gz``), sans manifeste."""
    return [
        PageArchivee(chemin.name, chemin.as_posix(), chemin, None, None, None) for chemin in chemins
    ]


def extraire(
    pages: Iterable[PageArchivee], *, verifier: bool, sortie: TextIO | None = None
) -> BilanExtraction:
    bilan = BilanExtraction(verifier=verifier)
    for page, octets in _lire(pages):
        bilan.pages += 1
        try:
            extrait = extraction.extraire(octets, dossiers=page.dossiers)
        except extraction.PageRejetee as exc:
            bilan.rejets[exc.motif] += 1
            if verifier:
                _comparer_statut(bilan, page, exc.motif)
            _ecrire(sortie, page, {"statut": "rejetee", "motif": exc.motif, "detail": exc.detail})
            continue
        bilan.extraites += 1
        controle = page.dossiers is None or bool(extrait.dossiers_documents)
        if not controle:
            bilan.sans_controle.append(f"{page.page_id} ({', '.join(page.dossiers or ())})")
        if verifier:
            _comparer_statut(bilan, page, None)
            _verifier(bilan, page, octets, extrait)
        _ecrire(sortie, page, {**_description(extrait), "controle_dossier": controle})
    return bilan


def _lire(pages: Iterable[PageArchivee]) -> Iterator[tuple[PageArchivee, bytes]]:
    for page in pages:
        if page.archive.name.endswith(".gz"):
            yield page, bronze.lire_archive(page.archive)
        else:
            yield page, page.archive.read_bytes()


def _verifier(
    bilan: BilanExtraction, page: PageArchivee, octets: bytes, extrait: extraction.AvisExtrait
) -> None:
    for ecart in verification.ecarts(octets, extrait):
        bilan.ecarts.append(f"{page.page_id}, bloc {ecart.position} : « {ecart.texte[:80]} »")
    empreinte = extrait.empreinte()
    if extraction.extraire(octets, dossiers=page.dossiers).empreinte() != empreinte:
        bilan.divergences.append(f"{page.page_id} : deux extractions, deux empreintes")
    if page.empreinte_consignee:
        version = page.extracteur_consigne or extraction.VERSION_EXTRACTEUR
        if extrait.empreinte(version) == page.empreinte_consignee:
            bilan.empreintes_egales += 1
        else:
            bilan.divergences.append(
                f"{page.page_id} : texte différent de celui du manifeste (v{version})"
            )


def _comparer_statut(bilan: BilanExtraction, page: PageArchivee, motif: str | None) -> None:
    """Le statut consigné par la collecte contre celui de l'extracteur courant."""
    if page.rejet_consigne is None and page.empreinte_consignee is None:
        return  # pas de manifeste (fichiers donnés à la main)
    if (page.rejet_consigne is None) == (motif is None):
        return
    avant = "extraite" if page.rejet_consigne is None else f"rejetée ({page.rejet_consigne})"
    apres = "extraite" if motif is None else f"rejetée ({motif})"
    version = page.extracteur_consigne
    if version == extraction.VERSION_EXTRACTEUR:
        bilan.divergences.append(f"{page.page_id} : {avant} au manifeste, {apres} à version égale")
        return
    bilan.changements.append(
        f"{page.page_id} : {avant} en v{version} → {apres} en v{extraction.VERSION_EXTRACTEUR}"
    )
    bilan.changements_sens[_SENS[0] if motif is None else _SENS[1]] += 1


def _description(extrait: extraction.AvisExtrait) -> dict[str, object]:
    return {
        "statut": "extraite",
        "titre": extrait.titre,
        "date_avis": extrait.date_avis.isoformat(),
        "mis_en_ligne": extrait.mis_en_ligne.isoformat(),
        "mis_a_jour": extrait.mis_a_jour.isoformat() if extrait.mis_a_jour else None,
        "nature_demande": extrait.nature_demande,
        "smr": list(extrait.niveaux(extraction.RUBRIQUE_SMR)),
        "asmr": list(extrait.niveaux(extraction.RUBRIQUE_ASMR)),
        "pdf_avis": extrait.pdf_avis,
        "empreinte": extrait.empreinte(),
        "texte": extrait.lignes_rendues(),
    }


def _ecrire(sortie: TextIO | None, page: PageArchivee, valeurs: dict[str, object]) -> None:
    if sortie is not None:
        ligne = {"page_id": page.page_id, "url": page.url, **valeurs}
        sortie.write(json.dumps(ligne, ensure_ascii=False) + "\n")
