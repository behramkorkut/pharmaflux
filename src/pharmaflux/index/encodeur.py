"""Les encodeurs : un texte devient un vecteur normé (ADR 0011).

Deux encodeurs derrière la même interface :

- ``E5Onnx`` : multilingual-e5-small quantifié int8, par ONNX Runtime (sans
  PyTorch). Le texte est préfixé ``passage: `` ou ``query: ``, découpé par le
  tokenizer SentencePiece d'origine (``sentencepiece.bpe.model``, quelques Mo,
  là où ``tokenizer.json`` en coûte 384 une fois chargé), tronqué à 512
  jetons ; le vecteur est la moyenne des états du dernier niveau sur les
  jetons réels, normée ;
- ``EncodeurTest`` : déterministe, sans fichier, pour les tests et pour la
  chaîne complète en CI (addendum 1 C2). Il ne dit rien de la qualité.

Chaque encodeur a une ``empreinte`` (nom, révision) : elle nomme la collection
et le cache des vecteurs. Un modèle se charge seulement si ses fichiers ont
les empreintes de son épinglage (``modeles.verifier``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

from pharmaflux.index import modeles

Vecteurs = npt.NDArray[np.float32]
# Jetons par appel au modèle, remplissage compris. Mesuré au palier 2 sur les 1 000 fragments
# les plus longs du jeu : 477 Mo résidents à 1 024, 500 Mo à 2 048, au même débit.
BUDGET_JETONS = 1024
FENETRE_E5 = 512
# (lignes, largeur) : quatre formes de lot seulement. ONNX Runtime garde de la mémoire pour
# chaque forme qu'il a vue : avec des lots de largeur libre, l'encodage du jeu passait 2 Go.
FORMES = tuple((BUDGET_JETONS // w, w) for w in (64, 128, 256, FENETRE_E5))
PREFIXE_PASSAGE, PREFIXE_REQUETE = "passage: ", "query: "
DEBUT, REMPLISSAGE, FIN, INCONNU, DECALAGE = 0, 1, 2, 3, 1  # fairseq (XLM-R)


class ModeleIndisponible(Exception):  # noqa: N818 (nom français voulu)
    """Les fichiers du modèle manquent ou n'ont pas les empreintes de leur épinglage."""


class Encodeur(Protocol):
    nom: str
    empreinte: str  # « <nom>@<révision> » : nomme la collection et le cache
    dimension: int

    def passages(self, textes: Sequence[str]) -> Vecteurs: ...

    def requete(self, texte: str) -> Vecteurs: ...

    def liberer(self) -> None: ...


def charger(nom: str, racine: Path | None = None) -> Encodeur:
    """L'encodeur ``nom`` : ``test``, ou un modèle épinglé dont les fichiers sont vérifiés."""
    if nom == EncodeurTest.nom:
        return EncodeurTest()
    epinglage = modeles.lire(nom)
    racine = racine or modeles.racine_modeles()
    ecarts = modeles.verifier(epinglage, racine)
    if ecarts:
        raise ModeleIndisponible("; ".join(ecarts))
    if nom != E5Onnx.nom:
        raise ModeleIndisponible(f"{nom} : aucun encodeur pour ce modèle")
    return E5Onnx(modeles.dossier(epinglage, racine), f"{epinglage.nom}@{epinglage.revision}")


def normer(vecteurs: npt.NDArray[Any]) -> Vecteurs:
    normes = np.linalg.norm(vecteurs, axis=1, keepdims=True)
    resultat: Vecteurs = (vecteurs / np.maximum(normes, 1e-12)).astype(np.float32)
    return resultat


class E5Onnx:
    nom = "e5-small-int8"
    dimension = 384

    def __init__(self, dossier: Path, empreinte: str) -> None:
        from sentencepiece import SentencePieceProcessor

        self.empreinte = empreinte
        self._dossier = dossier
        self._jetons = SentencePieceProcessor(model_file=str(dossier / "sentencepiece.bpe.model"))
        self._session_: Any = None  # chargée au premier encodage, libérable (mission 09)
        self._entrees: set[str] = set()

    @property
    def _session(self) -> Any:
        """La session ONNX, chargée au premier besoin : une construction tout en cache ne la
        charge pas, et une construction qui encode la libère avant d'écrire (``liberer``)."""
        if self._session_ is None:
            import onnxruntime

            options = onnxruntime.SessionOptions()
            options.log_severity_level = 3
            options.enable_cpu_mem_arena = False  # l'arène gardait le pic du plus long lot
            options.enable_mem_pattern = False  # un motif mémoire par forme de lot
            self._session_ = onnxruntime.InferenceSession(
                str(self._dossier / "onnx" / "model_quantized.onnx"),
                options,
                providers=["CPUExecutionProvider"],
            )
            self._entrees = {e.name for e in self._session_.get_inputs()}
        return self._session_

    def liberer(self) -> None:
        """Rend la mémoire du modèle ; il se rechargera si un texte reste à encoder."""
        self._session_ = None

    def passages(self, textes: Sequence[str]) -> Vecteurs:
        return self._encoder([PREFIXE_PASSAGE + t for t in textes])

    def requete(self, texte: str) -> Vecteurs:
        return self._encoder([PREFIXE_REQUETE + texte])[0:1].reshape(-1)

    def nombre_de_jetons(self, texte: str) -> int:
        """Les jetons du passage (préfixe et jetons spéciaux compris), sans troncature."""
        return len(self._jetons.encode((PREFIXE_PASSAGE + texte).strip())) + 2

    def _ids(self, textes: Sequence[str]) -> list[list[int]]:
        """Les identifiants du modèle, comme ``tokenizer.json`` les donne.

        Le décalage de fairseq : le modèle numérote ``<s>`` 0, ``<pad>`` 1, ``</s>`` 2, ``<unk>``
        3, puis chaque pièce à son numéro SentencePiece plus un (l'inconnu de SentencePiece, 0,
        devient 3). ``<s>`` … ``</s>`` encadrent le texte, tronqué à la fenêtre. Les blancs de
        bord sont retirés : SentencePiece les retire, ``tokenizers`` gardait une espace finale.
        """
        codes = self._jetons.encode([t.strip() for t in textes])
        return [
            [DEBUT, *(INCONNU if i == 0 else i + DECALAGE for i in c[: FENETRE_E5 - 2]), FIN]
            for c in codes
        ]

    def _encoder(self, textes: Sequence[str]) -> Vecteurs:
        """Par lots de forme fixe (``FORMES``), complétés de lignes vides.

        La quantification dynamique d'e5 prend son échelle sur tout le lot : le vecteur d'un
        texte dépend un peu de ses voisins de lot (cosinus ≥ 0,997 mesuré). Il est le même d'un
        calcul à l'autre pour les mêmes textes dans le même ordre, et le cache le fige.
        """
        sortie = np.zeros((len(textes), self.dimension), np.float32)
        tous = self._ids(textes)
        par_forme: dict[tuple[int, int], list[int]] = {}
        for i, ids_ in enumerate(tous):
            forme = next(f for f in FORMES if f[1] >= len(ids_))
            par_forme.setdefault(forme, []).append(i)
        for (lignes, largeur), rangs_ in sorted(par_forme.items()):
            for debut in range(0, len(rangs_), lignes):
                rangs = rangs_[debut : debut + lignes]
                ids = np.full((lignes, largeur), REMPLISSAGE, np.int64)
                masque = np.zeros((lignes, largeur), np.int64)
                for ligne, i in enumerate(rangs):
                    ids[ligne, : len(tous[i])] = tous[i]
                    masque[ligne, : len(tous[i])] = 1
                entrees = {"input_ids": ids, "attention_mask": masque}
                session = self._session
                if "token_type_ids" in self._entrees:
                    entrees["token_type_ids"] = np.zeros_like(ids)
                etats = session.run(None, entrees)[0][: len(rangs)]
                poids = masque[: len(rangs), :, None].astype(np.float32)
                moyennes = (etats * poids).sum(axis=1) / np.maximum(poids.sum(axis=1), 1.0)
                sortie[rangs] = normer(moyennes)
        return sortie


class EncodeurTest:
    """Un vecteur tiré de l'empreinte du texte : même texte, même vecteur, sur toute machine."""

    nom = "test"
    empreinte = "test@1"
    dimension = 32

    def passages(self, textes: Sequence[str]) -> Vecteurs:
        return normer(np.stack([self._brut(t) for t in textes])) if textes else self._vide()

    def requete(self, texte: str) -> Vecteurs:
        return self.passages([texte])[0:1].reshape(-1)

    def liberer(self) -> None:
        pass

    def _brut(self, texte: str) -> npt.NDArray[np.float64]:
        graine = int.from_bytes(hashlib.sha256(texte.encode("utf-8")).digest()[:8], "little")
        return np.random.default_rng(graine).standard_normal(self.dimension)

    def _vide(self) -> Vecteurs:
        return np.zeros((0, self.dimension), np.float32)
