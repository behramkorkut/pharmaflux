"""Forme canonique d'une valeur : le type et le contrat la donnent, jamais le code seul (ADR 0005).

La normalisation change la **forme**, jamais le sens. Une valeur vide reste
vide. Une valeur que le type ne sait pas lire (anomalie de *lisibilité* :
``decimal_illisible``, ``date_illisible``, ``valeur_inconnue``…) reste brute,
avec sa règle. Une valeur qui se lit mais dont l'anomalie dit la forme ou la
vraisemblance (``espace_parasite``, ``longueur_depassee``, ``date_hors_plage``,
``hote_inconnu``) prend sa forme canonique, et la règle reste consignée.

Les formes canoniques, par type :

- ``texte`` : espaces de tête et de fin retirés, intérieur intact ;
- ``entier`` : sans zéro de tête ni signe inutile (``007`` → ``7``) ;
- ``decimal`` : point décimal, exactement ``decimales`` chiffres après, pas de
  séparateur de milliers (``12,50`` → ``12.50`` ; ``1,003,48`` → ``1003.48``
  quand le contrat déclare ``milliers``) ;
- ``date`` : ISO 8601 ``AAAA-MM-JJ``, quel que soit le format du contrat ;
- ``booleen`` : ``true`` ou ``false`` ;
- ``enumeration`` : la graphie canonique de la table ``canonique`` du contrat,
  sinon la graphie telle quelle ;
- ``code`` et ``url`` : inchangés ;
- ``liste`` : chaque élément normalisé selon ``de``, même séparateur, même
  ordre, sans dédoublonnage.

Toutes les formes canoniques sont des chaînes : elles se comparent, se hachent
et s'écrivent en JSON sans conversion ; le type reste dans le contrat.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pharmaflux.contrats.modele import Regle, TypeNom, TypeValeur
from pharmaflux.contrats.verification import forme_decimale, verifier_valeur

# ISO 8601 depuis chaque format de date du contrat, par découpage : ``verifier_valeur``
# a déjà vérifié le motif et l'existence de la date au calendrier.
_ISO_DEPUIS_FORMAT: dict[str, Callable[[str], str]] = {
    "JJ/MM/AAAA": lambda v: f"{v[6:10]}-{v[3:5]}-{v[0:2]}",
    "AAAAMMJJ": lambda v: f"{v[0:4]}-{v[4:6]}-{v[6:8]}",
    "AAAA-MM-JJ": lambda v: v,
}

# La valeur se lit ; l'anomalie porte sur sa forme ou sa vraisemblance : la forme
# canonique s'applique et la règle reste consignée.
REGLES_DE_FORME = frozenset(
    {Regle.ESPACE_PARASITE, Regle.LONGUEUR_DEPASSEE, Regle.DATE_HORS_PLAGE, Regle.HOTE_INCONNU}
)

# Le type ne sait pas lire la valeur : elle reste brute, avec sa règle.
REGLES_DE_LISIBILITE = frozenset(
    {
        Regle.ENTIER_ILLISIBLE,
        Regle.DECIMAL_ILLISIBLE,
        Regle.DATE_ILLISIBLE,
        Regle.BOOLEEN_INCONNU,
        Regle.VALEUR_INCONNUE,
        Regle.CODE_ILLISIBLE,
        Regle.URL_ILLISIBLE,
    }
)


@dataclass(frozen=True, slots=True)
class Normalisee:
    """La valeur normalisée et la règle qu'enfreint la brute, s'il y en a une."""

    valeur: str
    regle: Regle | None


def normaliser_valeur(type_: TypeValeur, valeur: str) -> Normalisee:
    """La forme canonique de ``valeur`` pour ``type_`` ; la brute si le type ne la lit pas.

    Une valeur vide reste vide, sans règle : ``valeur_manquante`` dépend de la
    colonne, pas du type. L'objet rendu est ``valeur`` elle-même quand la forme
    canonique lui est égale, pour que le snapshot partage les chaînes.
    """
    if valeur == "":
        return Normalisee(valeur, None)
    if type_.nom is TypeNom.LISTE:
        assert type_.de is not None and type_.separateur is not None
        elements = [
            _normaliser_simple(type_.de, element) for element in valeur.split(type_.separateur)
        ]
        regle = next((e.regle for e in elements if e.regle is not None), None)
        return Normalisee(
            _meme_objet(valeur, type_.separateur.join(e.valeur for e in elements)), regle
        )
    return _normaliser_simple(type_, valeur)


def _normaliser_simple(type_: TypeValeur, valeur: str) -> Normalisee:
    regle = verifier_valeur(type_, valeur)
    if regle is not None and regle not in REGLES_DE_FORME:
        return Normalisee(valeur, regle)
    return Normalisee(_meme_objet(valeur, _canonique(type_, valeur)), regle)


def _meme_objet(brute: str, canonique: str) -> str:
    return brute if canonique == brute else canonique


def _canonique(type_: TypeValeur, valeur: str) -> str:
    """La forme canonique d'une valeur que le type sait lire (``verifier_valeur`` l'a admise)."""
    match type_.nom:
        case TypeNom.TEXTE:
            return valeur.strip()
        case TypeNom.ENTIER:
            return str(int(valeur))
        case TypeNom.DECIMAL:
            forme = forme_decimale(type_, valeur)
            assert forme is not None
            return forme
        case TypeNom.DATE:
            assert type_.format is not None
            return _ISO_DEPUIS_FORMAT[type_.format](valeur)
        case TypeNom.BOOLEEN:
            return "true" if valeur == type_.vrai else "false"
        case TypeNom.ENUMERATION:
            for graphie, canon in type_.canonique:
                if valeur == graphie:
                    return canon
            return valeur
        case TypeNom.CODE | TypeNom.URL:
            return valeur
        case TypeNom.LISTE:
            raise AssertionError("une liste se normalise élément par élément")
