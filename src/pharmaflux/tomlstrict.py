"""Lecture stricte d'une table TOML : chaque clé doit être consommée.

Les contrats de schéma et le jeu de questions de référence sont des fichiers
TOML écrits à la main : une clé inconnue, mal orthographiée ou sans objet y
est une erreur, jamais un silence. ``TableStricte`` enveloppe un ``dict``
issu de ``tomllib`` ; chaque lecture retire la clé, et ``terminer`` refuse
ce qui reste. L'exception levée est celle de la classe fille (``erreur``),
pour que chaque format garde la sienne.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar, Self


class TableStricte:
    """Une table TOML dont chaque clé doit être consommée ; ce qui reste est une erreur."""

    erreur: ClassVar[type[ValueError]] = ValueError

    def __init__(self, valeurs: object, contexte: str) -> None:
        if not isinstance(valeurs, dict):
            raise self.erreur(f"{contexte} : une table est attendue")
        self.contexte = contexte
        self._restants: dict[str, object] = dict(valeurs)

    def _prendre(self, cle: str, obligatoire: bool) -> object | None:
        if cle not in self._restants:
            if obligatoire:
                raise self.erreur(f"{self.contexte} : clé « {cle} » manquante")
            return None
        return self._restants.pop(cle)

    def _refuser(self, cle: str, attendu: str) -> ValueError:
        return self.erreur(f"{self.contexte} : « {cle} » doit être {attendu}")

    def texte(self, cle: str) -> str:
        valeur = self._prendre(cle, obligatoire=True)
        if not isinstance(valeur, str) or not valeur.strip():
            raise self._refuser(cle, "une chaîne non vide")
        return valeur

    def texte_facultatif(self, cle: str, *, blancs_admis: bool = False) -> str | None:
        """``blancs_admis`` : une chaîne d'espaces ou de tabulations passe (le séparateur)."""
        valeur = self._prendre(cle, obligatoire=False)
        if valeur is None:
            return None
        if not isinstance(valeur, str) or not (valeur if blancs_admis else valeur.strip()):
            raise self._refuser(cle, "une chaîne non vide")
        return valeur

    def booleen(self, cle: str) -> bool:
        valeur = self._prendre(cle, obligatoire=True)
        if not isinstance(valeur, bool):
            raise self._refuser(cle, "un booléen")
        return valeur

    def entier_facultatif(self, cle: str, *, minimum: int) -> int | None:
        valeur = self._prendre(cle, obligatoire=False)
        if valeur is None:
            return None
        if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < minimum:
            raise self._refuser(cle, f"un entier d'au moins {minimum}")
        return valeur

    def date(self, cle: str, *, obligatoire: bool) -> date | None:
        valeur = self._prendre(cle, obligatoire)
        if valeur is None:
            return None
        if not isinstance(valeur, date) or isinstance(valeur, datetime):
            raise self._refuser(cle, "une date TOML (AAAA-MM-JJ), sans heure")
        return valeur

    def textes(self, cle: str, *, obligatoire: bool) -> tuple[str, ...]:
        valeur = self._prendre(cle, obligatoire)
        if valeur is None:
            return ()
        if not isinstance(valeur, list) or not all(isinstance(v, str) and v for v in valeur):
            raise self._refuser(cle, "une liste de chaînes non vides")
        return tuple(valeur)

    def table(self, cle: str) -> Self:
        return type(self)(self._prendre(cle, obligatoire=True), f"{self.contexte}.{cle}")

    def table_facultative(self, cle: str) -> Self | None:
        valeur = self._prendre(cle, obligatoire=False)
        if valeur is None:
            return None
        return type(self)(valeur, f"{self.contexte}.{cle}")

    def tables(self, cle: str, *, obligatoire: bool) -> list[Self]:
        valeur = self._prendre(cle, obligatoire)
        if valeur is None:
            return []
        if not isinstance(valeur, list):
            raise self._refuser(cle, "un tableau de tables ([[...]])")
        return [type(self)(v, f"{self.contexte}.{cle}[{i}]") for i, v in enumerate(valeur)]

    def chaines(self) -> dict[str, str]:
        """Toutes les clés restantes, dont les valeurs doivent être des chaînes (vide admise)."""
        restants = dict(self._restants)
        self._restants.clear()
        for cle, valeur in restants.items():
            if not isinstance(valeur, str):
                raise self._refuser(cle, "une chaîne")
        return {cle: valeur for cle, valeur in restants.items() if isinstance(valeur, str)}

    def terminer(self) -> None:
        if self._restants:
            inconnues = ", ".join(sorted(self._restants))
            raise self.erreur(
                f"{self.contexte} : clé(s) inconnue(s) ou sans objet ici : {inconnues}"
            )
