"""Vérification d'une archive contre son contrat : des anomalies, jamais une correction.

Dans l'ordre : décodage strict dans l'encodage déclaré, fin de ligne, retour
final, lignes vides, nombre de colonnes, fichier sans aucune ligne, type de
chaque valeur, valeurs obligatoires, unicité de la clé déclarée unique,
lignes entières en doublon. Une anomalie n'arrête pas la lecture du reste du
fichier : les lignes bien formées sont rendues telles quelles (chaînes), avec
la liste des anomalies.
"""

from __future__ import annotations

import codecs
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from urllib.parse import urlsplit

from pharmaflux.contrats.modele import (
    FORMATS_DATE,
    Anomalie,
    Contrat,
    FinDeLigne,
    LignesVides,
    Regle,
    RetourFinal,
    TypeNom,
    TypeValeur,
    tronquer,
)

# Ligne d'une anomalie qui porte sur le fichier entier.
FICHIER_ENTIER = 0


@dataclass(slots=True)
class Lecture:
    """Le résultat : les lignes bien formées, le compte des lignes, les anomalies."""

    contrat: Contrat
    fichier: str
    nombre_lignes: int = 0  # lignes non vides, bien formées ou non
    lignes: list[tuple[int, tuple[str, ...]]] = field(default_factory=list)  # (numéro, valeurs)
    anomalies: list[Anomalie] = field(default_factory=list)

    @property
    def bloquantes(self) -> list[Anomalie]:
        return [anomalie for anomalie in self.anomalies if anomalie.bloquante]

    def par_regle(self) -> dict[Regle, list[Anomalie]]:
        """Les anomalies groupées par règle, dans l'ordre de première apparition."""
        groupes: dict[Regle, list[Anomalie]] = {}
        for anomalie in self.anomalies:
            groupes.setdefault(anomalie.regle, []).append(anomalie)
        return groupes


def verifier(contrat: Contrat, octets: bytes, *, fichier: str | None = None) -> Lecture:
    """Vérifie ``octets`` (le fichier tel que reçu) contre ``contrat``.

    ``fichier`` nomme le fichier dans les anomalies (par défaut, le nom du
    contrat ; le profil y met le chemin de l'archive).
    """
    lecture = Lecture(contrat, fichier or contrat.fichier)
    texte = _decoder(lecture, octets)
    _decouper(lecture, texte)
    if lecture.nombre_lignes == 0:
        # Non bloquant : le contrat décrit la forme, un fichier vide la respecte ; c'est au
        # garde-fou de volume (mission 02) de décider d'écarter un snapshot vide.
        constat = f"{len(octets)} octet(s), aucune ligne non vide"
        _signaler(lecture, FICHIER_ENTIER, None, Regle.FICHIER_VIDE, constat)
    _verifier_valeurs(lecture)
    _verifier_cle(lecture)
    _verifier_doublons(lecture)
    lecture.anomalies.sort(key=lambda anomalie: anomalie.ligne)
    return lecture


def _signaler(lecture: Lecture, ligne: int, colonne: str | None, regle: Regle, valeur: str) -> None:
    lecture.anomalies.append(Anomalie(lecture.fichier, ligne, colonne, regle, tronquer(valeur)))


def _decoder(lecture: Lecture, octets: bytes) -> str:
    """Décode strictement ; une erreur est signalée et la lecture continue avec substitution.

    L'anomalie porte la première séquence fautive et le nombre de lignes où la
    substitution (U+FFFD) a eu lieu. Deux signes d'un changement d'encodage
    sont aussi signalés : une marque d'ordre des octets (BOM) UTF-8 en tête,
    et, pour un contrat en encodage à un octet (cp1252), un fichier non ASCII
    qui se décode entièrement en UTF-8, ce que du texte cp1252 réel ne fait
    pratiquement jamais (``é`` vaut un seul octet 0xE9, invalide en UTF-8),
    alors que l'inverse passerait inaperçu.
    """
    encodage = lecture.contrat.format.encodage
    if octets.startswith(codecs.BOM_UTF8):
        _signaler(lecture, 1, None, Regle.ENCODAGE, "marque d'ordre des octets (BOM) UTF-8 en tête")
        octets = octets[len(codecs.BOM_UTF8) :]
    try:
        texte = octets.decode(encodage)
    except UnicodeDecodeError as exc:
        ligne = octets.count(b"\n", 0, exc.start) + 1
        fautifs = octets[exc.start : exc.end].hex(" ")
        texte = octets.decode(encodage, errors="replace")
        touchees = sum(1 for morceau in texte.split("\n") if "\ufffd" in morceau)
        pluriel = "s" if touchees > 1 else ""
        _signaler(
            lecture,
            ligne,
            None,
            Regle.ENCODAGE,
            f"octets {fautifs} illisibles en {encodage}"
            f" ({touchees} ligne{pluriel} touchée{pluriel})",
        )
        return texte
    if _codec_un_octet(encodage) and not octets.isascii() and _se_decode_en_utf8(octets):
        _signaler(
            lecture,
            FICHIER_ENTIER,
            None,
            Regle.ENCODAGE,
            f"le fichier se décode entièrement en UTF-8 alors que le contrat dit {encodage}",
        )
    return texte


def _codec_un_octet(encodage: str) -> bool:
    return codecs.lookup(encodage).name not in ("utf-8", "ascii")


def _se_decode_en_utf8(octets: bytes) -> bool:
    try:
        octets.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _decouper(lecture: Lecture, texte: str) -> None:
    """Fins de ligne, retour final, lignes vides, nombre de colonnes."""
    format_ = lecture.contrat.format
    morceaux = texte.split("\n")
    dernier = morceaux.pop()  # ce qui suit le dernier ``\n`` : vide si le fichier finit bien
    sans_retour: int | None = None
    if dernier != "":
        morceaux.append(dernier)
        sans_retour = len(morceaux)
        if format_.retour_final is RetourFinal.OBLIGATOIRE:
            _signaler(
                lecture, sans_retour, None, Regle.RETOUR_FINAL, "pas de retour à la ligne final"
            )
    crlf_attendu = format_.fin_de_ligne is FinDeLigne.CRLF
    nombre_colonnes = len(lecture.contrat.colonnes)
    for numero, brut in enumerate(morceaux, 1):
        termine_par_cr = brut.endswith("\r")
        if numero != sans_retour and termine_par_cr != crlf_attendu:
            constat = "CRLF" if termine_par_cr else "LF seul"
            _signaler(
                lecture,
                numero,
                None,
                Regle.FIN_DE_LIGNE,
                f"{constat} au lieu de {format_.fin_de_ligne}",
            )
        contenu = brut[:-1] if termine_par_cr else brut
        if contenu.strip() == "":
            if format_.lignes_vides is LignesVides.ANOMALIE:
                _signaler(lecture, numero, None, Regle.LIGNE_VIDE, repr(contenu) if contenu else "")
            else:
                _signaler(lecture, numero, None, Regle.NOMBRE_COLONNES, "ligne vide")
            continue
        lecture.nombre_lignes += 1
        valeurs = contenu.split(format_.separateur)
        if len(valeurs) != nombre_colonnes:
            constat = f"{len(valeurs)} colonnes au lieu de {nombre_colonnes} : {contenu}"
            _signaler(lecture, numero, None, Regle.NOMBRE_COLONNES, constat)
            continue
        lecture.lignes.append((numero, tuple(valeurs)))


def _verifier_valeurs(lecture: Lecture) -> None:
    colonnes = lecture.contrat.colonnes
    for numero, valeurs in lecture.lignes:
        for colonne, valeur in zip(colonnes, valeurs, strict=True):
            if valeur == "":
                if colonne.obligatoire:
                    _signaler(lecture, numero, colonne.nom, Regle.VALEUR_MANQUANTE, "")
                continue
            regle = verifier_valeur(colonne.type, valeur)
            if regle is not None:
                _signaler(lecture, numero, colonne.nom, regle, valeur)


def verifier_valeur(type_: TypeValeur, valeur: str) -> Regle | None:
    """La règle qu'enfreint ``valeur`` pour ce type, ou None si elle est conforme."""
    match type_.nom:
        case TypeNom.TEXTE:
            if valeur != valeur.strip():
                return Regle.ESPACE_PARASITE
            if type_.longueur_max is not None and len(valeur) > type_.longueur_max:
                return Regle.LONGUEUR_DEPASSEE
            return None
        case TypeNom.ENTIER:
            return None if _entier(valeur) else Regle.ENTIER_ILLISIBLE
        case TypeNom.DECIMAL:
            return None if forme_decimale(type_, valeur) is not None else Regle.DECIMAL_ILLISIBLE
        case TypeNom.DATE:
            return _verifier_date(type_, valeur)
        case TypeNom.BOOLEEN:
            return None if valeur in (type_.vrai, type_.faux) else Regle.BOOLEEN_INCONNU
        case TypeNom.ENUMERATION:
            return None if valeur in type_.valeurs else Regle.VALEUR_INCONNUE
        case TypeNom.CODE:
            assert type_.motif is not None
            return None if type_.motif.fullmatch(valeur) else Regle.CODE_ILLISIBLE
        case TypeNom.URL:
            return _verifier_url(type_, valeur)
        case TypeNom.LISTE:
            assert type_.de is not None and type_.separateur is not None
            for element in valeur.split(type_.separateur):
                regle = verifier_valeur(type_.de, element)
                if regle is not None:
                    return regle
            return None


def _entier(valeur: str) -> bool:
    chiffres = valeur[1:] if valeur.startswith("-") else valeur
    return chiffres.isdigit() and chiffres.isascii()


def forme_decimale(type_: TypeValeur, valeur: str) -> str | None:
    """La forme canonique d'un décimal (« 12,50 » → « 12.50 »), ou None s'il est illisible.

    La virgule est le séparateur décimal, suivie d'exactement ``decimales``
    chiffres ASCII (« ²³ » passe ``isdigit``, comme pour ``_entier``). Quand le
    type déclare ``milliers`` (contrat v1, ADR 0005), la partie entière peut
    aussi s'écrire par groupes de trois chiffres (« 1,003,48 » → « 1003.48 »).
    La forme canonique n'a ni séparateur de milliers ni zéro de tête.
    """
    partie_entiere, virgule, decimales = valeur.rpartition(",")
    if not virgule or len(decimales) != type_.decimales or not _entier(decimales):
        return None
    if decimales.startswith("-"):
        return None
    if _entier(partie_entiere):
        chiffres = partie_entiere
    elif type_.milliers is not None and _motif_milliers(type_.milliers).fullmatch(partie_entiere):
        chiffres = partie_entiere.replace(type_.milliers, "")
    else:
        return None
    return f"{_entier_canonique(chiffres)}.{decimales}"


@cache
def _motif_milliers(milliers: str) -> re.Pattern[str]:
    """Une partie entière par groupes de trois chiffres, au moins un séparateur."""
    return re.compile(rf"-?\d{{1,3}}(?:{re.escape(milliers)}\d{{3}})+")


def _entier_canonique(chiffres: str) -> str:
    """« 007 » → « 7 », « -0 » → « 0 » : la forme de ``int``, sans zéro de tête ni signe inutile."""
    return str(int(chiffres))


def _verifier_date(type_: TypeValeur, valeur: str) -> Regle | None:
    assert type_.format is not None
    motif, format_strptime = FORMATS_DATE[type_.format]
    if not motif.fullmatch(valeur):
        return Regle.DATE_ILLISIBLE
    try:
        jour = datetime.strptime(valeur, format_strptime).date()
    except ValueError:
        return Regle.DATE_ILLISIBLE
    if (type_.plage_min is not None and jour < type_.plage_min) or (
        type_.plage_max is not None and jour > type_.plage_max
    ):
        return Regle.DATE_HORS_PLAGE
    return None


def _verifier_url(type_: TypeValeur, valeur: str) -> Regle | None:
    parties = urlsplit(valeur)
    if parties.scheme not in ("http", "https") or not parties.hostname:
        return Regle.URL_ILLISIBLE
    if type_.hotes and parties.hostname not in type_.hotes:
        return Regle.HOTE_INCONNU
    return None


def _verifier_cle(lecture: Lecture) -> None:
    """Une clé déclarée unique qui se répète : bloquant, sur chaque répétition."""
    cle = lecture.contrat.cle
    if not cle.unique:
        return
    index = [lecture.contrat.index(nom) for nom in cle.colonnes]
    libelle = ", ".join(cle.colonnes)
    vues: dict[tuple[str, ...], int] = {}
    for numero, valeurs in lecture.lignes:
        valeur_cle = tuple(valeurs[i] for i in index)
        premiere = vues.setdefault(valeur_cle, numero)
        if premiere != numero:
            constat = f"déjà vue ligne {premiere} : {' | '.join(valeur_cle)}"
            _signaler(lecture, numero, libelle, Regle.CLE_NON_UNIQUE, constat)


def _verifier_doublons(lecture: Lecture) -> None:
    """Deux lignes entières identiques : signalé partout, jamais bloquant (addendum 1)."""
    vues: dict[tuple[str, ...], int] = {}
    for numero, valeurs in lecture.lignes:
        premiere = vues.setdefault(valeurs, numero)
        if premiere != numero:
            constat = f"identique à la ligne {premiere} : {chr(9).join(valeurs)}"
            _signaler(lecture, numero, None, Regle.LIGNE_DUPLIQUEE, constat)
