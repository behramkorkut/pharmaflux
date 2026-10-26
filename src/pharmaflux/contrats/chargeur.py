"""Lecture stricte des contrats TOML : un contrat mal formé est refusé, avec le motif.

Chaque clé d'une table doit être consommée : une clé inconnue, un paramètre
sans objet pour le type, une colonne de clé absente, une énumération vide,
un motif qui ne compile pas, sont autant de refus. Un paramètre de la v1
(``milliers``, ``canonique``) dans un contrat ``v0`` est refusé aussi : la
v0 reste figée. Les contrats du paquet sont dans ``bdpm/<nom>.toml``, un par
identifiant du catalogue (``bdpm.specialites`` → ``bdpm/specialites.toml``).
"""

from __future__ import annotations

import codecs
import re
import tomllib
from datetime import date
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from pharmaflux.contrats.modele import (
    FORMATS_DATE,
    PARAMETRES_V1,
    VERSIONS_CONTRAT,
    Cle,
    Colonne,
    Contrat,
    FinDeLigne,
    Format,
    Lien,
    LignesVides,
    RetourFinal,
    Source,
    TypeNom,
    TypeValeur,
)
from pharmaflux.tomlstrict import TableStricte

MOTIF_IDENTIFIANT = re.compile(r"[a-z]+\.[a-z][a-z0-9_]*")
MOTIF_NOM_COLONNE = re.compile(r"[a-z][a-z0-9_]*")
MOTIF_SHA256 = re.compile(r"[0-9a-f]{64}")


class ContratInvalide(ValueError):  # noqa: N818 (nom français voulu)
    """Un contrat mal formé : le message nomme le fichier, la table et la clé en cause."""


class ContratIntrouvable(LookupError):  # noqa: N818 (nom français voulu)
    """Aucun contrat dans le paquet pour cet identifiant."""


class _Table(TableStricte):
    """Une table TOML d'un contrat : ce qui n'est pas consommé est un ``ContratInvalide``."""

    erreur = ContratInvalide


def charger(chemin: Path) -> Contrat:
    """Le contrat d'un fichier TOML sur le disque."""
    try:
        octets = chemin.read_bytes()
    except OSError as exc:
        raise ContratInvalide(f"{chemin} : illisible ({exc})") from exc
    return charger_octets(octets, str(chemin))


def charger_octets(octets: bytes, origine: str) -> Contrat:
    """Le contrat contenu dans ``octets`` ; ``origine`` nomme le fichier dans les messages."""
    try:
        brut = tomllib.loads(octets.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ContratInvalide(f"{origine} : TOML illisible : {exc}") from exc
    racine = _Table(brut, origine)
    version = racine.texte("version")
    if version not in VERSIONS_CONTRAT:
        admises = ", ".join(f"« {v} »" for v in VERSIONS_CONTRAT)
        raise ContratInvalide(f"{origine} : version « {version} » ; attendu {admises}")
    identifiant = racine.texte("identifiant")
    if not MOTIF_IDENTIFIANT.fullmatch(identifiant):
        raise ContratInvalide(f"{origine} : identifiant « {identifiant} » hors forme source.nom")
    fichier = racine.texte("fichier")
    description = racine.texte("description")
    source = _source(racine.table("source"))
    format_ = _format(racine.table("format"))
    colonnes = tuple(
        _colonne(table, version) for table in racine.tables("colonnes", obligatoire=True)
    )
    if not colonnes:
        raise ContratInvalide(f"{origine} : aucune colonne")
    noms = [colonne.nom for colonne in colonnes]
    if len(set(noms)) != len(noms):
        doublons = sorted({nom for nom in noms if noms.count(nom) > 1})
        raise ContratInvalide(f"{origine} : colonne(s) en double : {', '.join(doublons)}")
    cle = _cle(racine.table("cle"), noms)
    liens = tuple(_lien(table, noms) for table in racine.tables("liens", obligatoire=False))
    racine.terminer()
    return Contrat(
        version=version,
        identifiant=identifiant,
        fichier=fichier,
        description=description,
        source=source,
        format=format_,
        colonnes=colonnes,
        cle=cle,
        liens=liens,
    )


def _source(table: _Table) -> Source:
    source = Source(
        documentation=table.texte("documentation"),
        documentation_sha256=_sha256(table, "documentation_sha256"),
        section=table.texte("section"),
        date_verification=_date_obligatoire(table, "date_verification"),
        archive_reference=table.texte("archive_reference"),
        archive_sha256=_sha256(table, "archive_sha256"),
    )
    table.terminer()
    return source


def _sha256(table: _Table, cle: str) -> str:
    valeur = table.texte(cle)
    if not MOTIF_SHA256.fullmatch(valeur):
        raise ContratInvalide(f"{table.contexte} : « {cle} » doit être un sha256 hexadécimal")
    return valeur


def _date_obligatoire(table: _Table, cle: str) -> date:
    valeur = table.date(cle, obligatoire=True)
    assert valeur is not None  # ``obligatoire`` garantit une valeur ou une exception
    return valeur


def _format(table: _Table) -> Format:
    encodage = table.texte("encodage")
    try:
        codecs.lookup(encodage)
    except LookupError as exc:
        raise ContratInvalide(f"{table.contexte} : encodage « {encodage} » inconnu") from exc
    format_ = Format(
        encodage=encodage,
        fin_de_ligne=_choix(table, "fin_de_ligne", FinDeLigne, None),
        separateur=table.texte_facultatif("separateur", blancs_admis=True) or "\t",
        retour_final=_choix(table, "retour_final", RetourFinal, RetourFinal.OBLIGATOIRE),
        lignes_vides=_choix(table, "lignes_vides", LignesVides, LignesVides.INTERDITES),
    )
    table.terminer()
    return format_


def _choix[E: FinDeLigne | RetourFinal | LignesVides](
    table: _Table, cle: str, enumeration: type[E], defaut: E | None
) -> E:
    valeur = table.texte(cle) if defaut is None else table.texte_facultatif(cle)
    if valeur is None:
        assert defaut is not None
        return defaut
    try:
        return enumeration(valeur)
    except ValueError as exc:
        choix = ", ".join(membre.value for membre in enumeration)
        raise ContratInvalide(
            f"{table.contexte} : « {cle} » vaut {valeur!r} ; attendu : {choix}"
        ) from exc


def _colonne(table: _Table, version: str) -> Colonne:
    nom = table.texte("nom")
    if not MOTIF_NOM_COLONNE.fullmatch(nom):
        raise ContratInvalide(f"{table.contexte} : nom « {nom} » hors forme snake_case sans accent")
    colonne = Colonne(
        nom=nom,
        type=_type(table, version),
        obligatoire=table.booleen("obligatoire"),
        description=table.texte_facultatif("description") or "",
    )
    table.terminer()
    return colonne


def _type(table: _Table, version: str) -> TypeValeur:
    """Le type déclaré dans ``table`` avec ses seuls paramètres ; les autres clés restent."""
    if version == "v0":
        presents = sorted(PARAMETRES_V1 & table.cles_restantes())
        if presents:
            raise ContratInvalide(
                f"{table.contexte} : {', '.join(presents)} : paramètre(s) de la v1 dans un"
                " contrat v0"
            )
    nom_brut = table.texte("type")
    try:
        nom = TypeNom(nom_brut)
    except ValueError as exc:
        types = ", ".join(membre.value for membre in TypeNom)
        raise ContratInvalide(
            f"{table.contexte} : type « {nom_brut} » inconnu ; attendu : {types}"
        ) from exc
    match nom:
        case TypeNom.TEXTE:
            return TypeValeur(nom, longueur_max=table.entier_facultatif("longueur_max", minimum=1))
        case TypeNom.ENTIER:
            return TypeValeur(nom)
        case TypeNom.DECIMAL:
            return TypeValeur(
                nom,
                decimales=table.entier_facultatif("decimales", minimum=1) or 2,
                milliers=_milliers(table),
            )
        case TypeNom.DATE:
            format_ = table.texte("format")
            if format_ not in FORMATS_DATE:
                formats = ", ".join(FORMATS_DATE)
                raise ContratInvalide(
                    f"{table.contexte} : format de date « {format_} » ; attendu : {formats}"
                )
            plage_min = table.date("plage_min", obligatoire=False)
            plage_max = table.date("plage_max", obligatoire=False)
            if plage_min and plage_max and plage_min > plage_max:
                raise ContratInvalide(f"{table.contexte} : plage_min après plage_max")
            return TypeValeur(nom, format=format_, plage_min=plage_min, plage_max=plage_max)
        case TypeNom.BOOLEEN:
            vrai, faux = table.texte("vrai"), table.texte("faux")
            if vrai == faux:
                raise ContratInvalide(f"{table.contexte} : « vrai » et « faux » sont identiques")
            return TypeValeur(nom, vrai=vrai, faux=faux)
        case TypeNom.ENUMERATION:
            valeurs = table.textes("valeurs", obligatoire=True)
            if not valeurs:
                raise ContratInvalide(f"{table.contexte} : énumération sans valeurs")
            if len(set(valeurs)) != len(valeurs):
                raise ContratInvalide(f"{table.contexte} : valeur d'énumération en double")
            return TypeValeur(nom, valeurs=valeurs, canonique=_canonique(table, valeurs))
        case TypeNom.CODE:
            motif = table.texte("motif")
            try:
                return TypeValeur(nom, motif=re.compile(motif))
            except re.error as exc:
                raise ContratInvalide(
                    f"{table.contexte} : motif {motif!r} invalide : {exc}"
                ) from exc
        case TypeNom.URL:
            return TypeValeur(nom, hotes=table.textes("hotes", obligatoire=False))
        case TypeNom.LISTE:
            separateur = table.texte("separateur")
            table_de = table.table("de")
            de = _type(table_de, version)
            table_de.terminer()
            if de.nom is TypeNom.LISTE:
                raise ContratInvalide(f"{table.contexte} : une liste de listes n'est pas admise")
            return TypeValeur(nom, de=de, separateur=separateur)


def _milliers(table: _Table) -> str | None:
    """Le séparateur des milliers d'un décimal (v1) : un seul caractère, ni chiffre ni signe."""
    milliers = table.texte_facultatif("milliers", blancs_admis=True)
    if milliers is None:
        return None
    if len(milliers) != 1 or milliers.isdigit() or milliers in "-.":
        raise ContratInvalide(
            f"{table.contexte} : « milliers » doit être un seul caractère, ni chiffre, ni « - »,"
            " ni « . »"
        )
    return milliers


def _canonique(table: _Table, valeurs: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """La table ``canonique`` d'une énumération (v1) : graphie → graphie canonique.

    Chaque clé et chaque valeur sont dans ``valeurs`` ; une valeur n'est jamais
    elle-même une clé (pas de chaîne), et une clé égale à sa valeur est sans objet.
    """
    sous_table = table.table_facultative("canonique")
    if sous_table is None:
        return ()
    paires = sous_table.chaines()
    if not paires:
        raise ContratInvalide(f"{sous_table.contexte} : table vide")
    for graphie, canon in paires.items():
        if graphie not in valeurs or canon not in valeurs:
            raise ContratInvalide(
                f"{sous_table.contexte} : « {graphie} » = « {canon} » : les deux graphies doivent"
                " être dans « valeurs »"
            )
        if graphie == canon:
            raise ContratInvalide(f"{sous_table.contexte} : « {graphie} » renvoie à elle-même")
        if canon in paires:
            raise ContratInvalide(
                f"{sous_table.contexte} : « {canon} » est à la fois graphie et forme canonique"
            )
    return tuple(paires.items())


def _cle(table: _Table, noms: list[str]) -> Cle:
    colonnes = table.textes("colonnes", obligatoire=True)
    if not colonnes:
        raise ContratInvalide(f"{table.contexte} : clé sans colonne")
    _colonnes_connues(table, colonnes, noms)
    unique = table.booleen("unique")
    raison = table.texte_facultatif("raison")
    if not unique and raison is None:
        raise ContratInvalide(f"{table.contexte} : une clé non unique exige une « raison »")
    if unique and raison is not None:
        raise ContratInvalide(
            f"{table.contexte} : « raison » n'a de sens que pour une clé non unique"
        )
    table.terminer()
    return Cle(colonnes=colonnes, unique=unique, raison=raison or "")


def _lien(table: _Table, noms: list[str]) -> Lien:
    colonne = table.texte("colonne")
    _colonnes_connues(table, (colonne,), noms)
    vers = table.texte("vers")
    if not MOTIF_IDENTIFIANT.fullmatch(vers):
        raise ContratInvalide(f"{table.contexte} : « vers » doit être un identifiant du catalogue")
    lien = Lien(colonne=colonne, vers=vers, colonne_cible=table.texte("colonne_cible"))
    table.terminer()
    return lien


def _colonnes_connues(table: _Table, colonnes: tuple[str, ...], noms: list[str]) -> None:
    inconnues = [colonne for colonne in colonnes if colonne not in noms]
    if inconnues:
        raise ContratInvalide(f"{table.contexte} : colonne(s) inconnue(s) : {', '.join(inconnues)}")


def _dossier(source: str) -> Traversable:
    return files("pharmaflux.contrats") / source


def charger_identifiant(identifiant: str) -> Contrat:
    """Le contrat du paquet pour un identifiant du catalogue (``bdpm.specialites``)."""
    source, _, nom = identifiant.partition(".")
    ressource = _dossier(source) / f"{nom}.toml"
    if not source or not nom or not ressource.is_file():
        raise ContratIntrouvable(f"aucun contrat pour « {identifiant} » ({source}/{nom}.toml)")
    contrat = charger_octets(ressource.read_bytes(), f"{source}/{nom}.toml")
    if contrat.identifiant != identifiant:
        raise ContratInvalide(
            f"{source}/{nom}.toml : identifiant {contrat.identifiant}, attendu {identifiant}"
        )
    return contrat


def charger_tous(source: str = "bdpm") -> dict[str, Contrat]:
    """Tous les contrats de ``source`` dans le paquet, par identifiant, liens vérifiés.

    Un lien doit viser un contrat chargé et une de ses colonnes : c'est la seule
    cohérence qu'un contrat seul ne peut pas garantir.
    """
    contrats: dict[str, Contrat] = {}
    for ressource in sorted(_dossier(source).iterdir(), key=lambda r: r.name):
        if not ressource.name.endswith(".toml") or not ressource.is_file():
            continue
        nom = ressource.name.removesuffix(".toml")
        contrat = charger_identifiant(f"{source}.{nom}")
        contrats[contrat.identifiant] = contrat
    for contrat in contrats.values():
        for lien in contrat.liens:
            cible = contrats.get(lien.vers)
            if cible is None:
                raise ContratInvalide(
                    f"{contrat.identifiant} : lien vers « {lien.vers} », contrat absent"
                )
            if lien.colonne_cible not in cible.noms_colonnes:
                cible_absente = f"{lien.vers}.{lien.colonne_cible}"
                raise ContratInvalide(
                    f"{contrat.identifiant} : lien vers {cible_absente}, colonne absente"
                )
    return contrats
