"""Le texte d'une page d'avis de la HAS, mot pour mot, ou son rejet motivé (mission 09, §0 D).

La licence de la HAS interdit d'altérer le texte ou d'en dénaturer le sens (ADR 0004). On le
reprend donc tel quel, bloc par bloc, dans l'ordre de la page ; seules les espaces et les
entités HTML se normalisent. Aucun LLM, aucun résumé. Les mêmes octets donnent le même texte,
et la même empreinte.

Ce qui est gardé, dans l'ordre (``Ligne.rubrique``) :

- ``demande`` : la nature de la demande (« Inscription »…), puis le paragraphe de motif ;
- une rubrique par section du corps, nommée par son titre de la page (« L'essentiel »,
  « Quel progrès ? », « Quelle place dans la stratégie thérapeutique ? »,
  « Recommandations particulières »…) : ses intertitres, paragraphes et éléments de liste ;
- ``smr`` puis ``asmr`` : le titre de la table, puis, par ligne, le niveau et son libellé.

Le titre (``<h1>``) et les dates sont à part : la date de l'avis (``datePublished`` du JSON-LD),
la date de mise en ligne et, si la page l'affiche, celle de mise à jour (« Mis en ligne le … »,
« Mis à jour le … »). Le reste de la page est écarté : menus, table des matières, partage,
documents (dont le PDF de l'avis, gardé en métadonnée), contact, étiquettes, pied de page.

Le JSON-LD n'est jamais du texte : il sert de **contrôle**. Une page dont la structure manque,
ou dont le JSON-LD contredit le corps, est **rejetée avec son motif** (``PageRejetee``), jamais
devinée.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

VERSION_EXTRACTEUR = 1

# Les motifs de rejet : un motif, un défaut de structure.
REJET_ENCODAGE = "encodage"
REJET_JSONLD_ABSENT = "jsonld_absent"
REJET_JSONLD_ILLISIBLE = "jsonld_illisible"
REJET_DATE_AVIS = "date_avis_illisible"
REJET_TITRE = "titre_absent"
REJET_RUBRIQUE = "rubrique_inattendue"
REJET_MISE_EN_LIGNE = "mise_en_ligne_absente"
REJET_NATURE = "nature_absente"
REJET_CORPS_VIDE = "corps_vide"
REJET_NOM = "nom_incoherent"
REJET_NIVEAUX = "niveaux_incoherents"
REJET_DOSSIER = "dossier_incoherent"

RUBRIQUE_DEMANDE = "demande"
RUBRIQUE_SMR = "smr"
RUBRIQUE_ASMR = "asmr"
LIBELLE_RUBRIQUE_SITE = "Avis sur les Médicaments"
TITRE_NATURE = "Nature de la demande"

_BLOCS = frozenset(
    {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "div", "ul", "ol", "table", "tr"}
)
_IGNORES = frozenset({"script", "style", "nav", "noscript", "form", "button", "svg"})
_ESPACES = re.compile(r"\s+")
_MIS_EN_LIGNE = re.compile(r"Mis en ligne le\s+(\d{1,2}(?:er)?\s+\S+\s+\d{4})")
_MIS_A_JOUR = re.compile(r"Mis à jour le\s+(\d{1,2}(?:er)?\s+\S+\s+\d{4})")
_DOSSIER_AVIS = re.compile(r"_AVIS_CT-?(\d{4,6})\b", re.IGNORECASE)
_CIP13 = re.compile(r"\b\d{13}\b")
_MOIS = {
    "janv": 1, "janvier": 1, "févr": 2, "février": 2, "fevr": 2, "fevrier": 2, "mars": 3,
    "avr": 4, "avril": 4, "mai": 5, "juin": 6, "juil": 7, "juillet": 7, "août": 8, "aout": 8,
    "sept": 9, "septembre": 9, "oct": 10, "octobre": 10, "nov": 11, "novembre": 11,
    "déc": 12, "décembre": 12, "dec": 12, "decembre": 12,
}  # fmt: skip


class PageRejetee(ValueError):  # noqa: N818 (nom français voulu)
    """La structure attendue d'une page d'avis manque : rejet motivé, jamais deviné."""

    def __init__(self, motif: str, detail: str) -> None:
        super().__init__(f"{motif} : {detail}")
        self.motif = motif
        self.detail = detail


@dataclass(frozen=True, slots=True)
class Ligne:
    """Un bloc de la page, mot pour mot : sa rubrique, sa nature, son texte."""

    rubrique: str  # demande, le titre d'une section du corps, smr, asmr
    genre: str  # nature, intertitre, paragraphe, element, niveau
    texte: str


@dataclass(frozen=True, slots=True)
class AvisExtrait:
    """Ce qu'une page d'avis donne : le texte gardé, ses dates, et des métadonnées de contrôle."""

    titre: str
    date_avis: date
    date_avis_brute: str
    mis_en_ligne: date
    mis_en_ligne_brut: str
    mis_a_jour: date | None
    mis_a_jour_brut: str | None
    lignes: tuple[Ligne, ...]
    url_canonique: str | None = None
    pdf_avis: str | None = None
    cip13: tuple[str, ...] = ()
    atc: str | None = None
    dossiers_documents: tuple[str, ...] = ()  # les dossiers que nomme le document d'avis

    @property
    def date_mise_a_jour(self) -> date:
        """La « date de dernière mise à jour » de la licence : mise à jour, sinon mise en ligne."""
        return self.mis_a_jour or self.mis_en_ligne

    @property
    def nature_demande(self) -> str:
        return next(ligne.texte for ligne in self.lignes if ligne.genre == "nature")

    def niveaux(self, rubrique: str) -> tuple[str, ...]:
        return tuple(
            ligne.texte
            for ligne in self.lignes
            if ligne.rubrique == rubrique and ligne.genre == "niveau"
        )

    def empreinte(self) -> str:
        """Le sha256 du texte extrait et de ses dates : il ne change qu'avec ce que dit la page.

        Le sha256 des octets bruts change à chaque réponse (jeton CSRF, horodatage) ; c'est
        celui-ci qui servira à toute revisite (addendum 1, C2).
        """
        canonique = {
            "version": VERSION_EXTRACTEUR,
            "titre": self.titre,
            "date_avis": self.date_avis.isoformat(),
            "mis_en_ligne": self.mis_en_ligne.isoformat(),
            "mis_a_jour": self.mis_a_jour.isoformat() if self.mis_a_jour else None,
            "lignes": [[ligne.rubrique, ligne.genre, ligne.texte] for ligne in self.lignes],
        }
        brut = json.dumps(canonique, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(brut.encode("utf-8")).hexdigest()

    def lignes_rendues(self) -> list[str]:
        """Le texte lisible, une ligne par bloc ; seuls les préfixes sont à nous."""
        rendu = [self.titre]
        for ligne in self.lignes:
            if ligne.genre == "nature":
                rendu.append(f"{TITRE_NATURE} : {ligne.texte}")
            elif ligne.genre == "element":
                rendu.append(f"- {ligne.texte}")
            elif ligne.genre == "niveau":
                rendu.append(f"{ligne.rubrique.upper()} : {ligne.texte}")
            else:
                rendu.append(ligne.texte)
        return rendu


def normaliser(texte: str) -> str:
    """Les espaces (insécables comprises) réduites à une seule, sans espace de bord."""
    return _ESPACES.sub(" ", texte).strip()


def date_francaise(texte: str) -> date:
    """« 12 juin 2026 », « 10 janv. 2025 », « 1er mai 2015 ». Lève ``ValueError`` sinon."""
    morceaux = normaliser(texte).split(" ")
    if len(morceaux) != 3:
        raise ValueError(f"date illisible : {texte!r}")
    jour, mois, annee = morceaux
    numero = _MOIS.get(mois.lower().rstrip("."))
    if numero is None:
        raise ValueError(f"mois inconnu : {mois!r}")
    return date(int(annee), numero, int(jour.removesuffix("er")))


def extraire(octets: bytes, *, dossiers: tuple[str, ...] | None = None) -> AvisExtrait:
    """Le texte et les dates d'une page d'avis ; ``PageRejetee`` si sa structure manque.

    ``dossiers`` : ceux qui lient la page dans la BDPM. S'ils sont donnés, le document d'avis
    de la page ne doit pas en nommer un autre.
    """
    try:
        html = octets.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PageRejetee(REJET_ENCODAGE, f"page non UTF-8 ({exc.reason})") from exc
    lecteur = _Lecteur()
    lecteur.feed(html)
    lecteur.close()

    jsonld = _jsonld(lecteur.jsonld)
    titre = normaliser(lecteur.titre)
    if not titre:
        raise PageRejetee(REJET_TITRE, "aucun <h1>")
    sous_titre = normaliser(lecteur.sous_titre)
    if LIBELLE_RUBRIQUE_SITE not in sous_titre:
        raise PageRejetee(REJET_RUBRIQUE, f"sous-titre « {sous_titre[:80]} »")
    mis_en_ligne_brut, mis_en_ligne = _date_du_sous_titre(_MIS_EN_LIGNE, sous_titre)
    if mis_en_ligne_brut is None or mis_en_ligne is None:
        raise PageRejetee(REJET_MISE_EN_LIGNE, f"sous-titre « {sous_titre[:80]} »")
    mis_a_jour_brut, mis_a_jour = _date_du_sous_titre(_MIS_A_JOUR, sous_titre)

    date_brute = str(jsonld.get("datePublished") or "")
    try:
        # La date telle qu'écrite (minuit, heure de Paris) : jamais convertie en UTC, qui la
        # ferait reculer d'un jour.
        date_avis = datetime.fromisoformat(date_brute).date()
    except ValueError as exc:
        raise PageRejetee(REJET_DATE_AVIS, f"datePublished « {date_brute} »") from exc

    lignes = tuple(lecteur.lignes)
    if not any(ligne.genre == "nature" for ligne in lignes):
        raise PageRejetee(REJET_NATURE, f"aucune valeur sous « {TITRE_NATURE} »")
    if len(lignes) < 2:
        raise PageRejetee(REJET_CORPS_VIDE, "ni motif, ni section, ni table")

    nom = normaliser(str(jsonld.get("name") or ""))
    if nom != f"Avis sur {titre}":
        raise PageRejetee(REJET_NOM, f"JSON-LD « {nom[:80]} » contre le titre « {titre[:80]} »")
    extrait = AvisExtrait(
        titre=titre,
        date_avis=date_avis,
        date_avis_brute=date_brute,
        mis_en_ligne=mis_en_ligne,
        mis_en_ligne_brut=mis_en_ligne_brut,
        mis_a_jour=mis_a_jour,
        mis_a_jour_brut=mis_a_jour_brut,
        lignes=lignes,
        url_canonique=lecteur.url_canonique,
        **_metadonnees(jsonld),
    )
    _controler_niveaux(extrait, jsonld)
    if dossiers is not None:
        autres = sorted(set(extrait.dossiers_documents) - set(dossiers))
        if autres:
            raise PageRejetee(
                REJET_DOSSIER, f"le document d'avis nomme {', '.join(autres)}, hors {dossiers}"
            )
    return extrait


def texte_principal(octets: bytes) -> str | None:
    """Le texte de ``<main>`` d'une page du site, sans scripts : pour les mentions légales.

    Le jeton CSRF et l'horodatage de la page sont hors de ``<main>`` : deux réponses d'une même
    page donnent le même texte. ``None`` si la page n'a pas de ``<main>`` ou n'est pas en UTF-8.
    """
    try:
        html = octets.decode("utf-8")
    except UnicodeDecodeError:
        return None
    lecteur = _LecteurPrincipal()
    lecteur.feed(html)
    lecteur.close()
    if not lecteur.vu:
        return None
    return "\n".join(ligne for ligne in lecteur.lignes if ligne)


def empreinte_texte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _date_du_sous_titre(motif: re.Pattern[str], sous_titre: str) -> tuple[str | None, date | None]:
    correspondance = motif.search(sous_titre)
    if correspondance is None:
        return None, None
    try:
        return correspondance[1], date_francaise(correspondance[1])
    except ValueError:
        return correspondance[1], None


def _jsonld(blocs: list[str]) -> dict[str, Any]:
    """Le bloc JSON-LD de type ``Review`` : un seul attendu."""
    if not blocs:
        raise PageRejetee(REJET_JSONLD_ABSENT, "aucun bloc application/ld+json")
    for bloc in blocs:
        try:
            valeur = json.loads(bloc)
        except ValueError as exc:
            raise PageRejetee(REJET_JSONLD_ILLISIBLE, str(exc)) from exc
        if isinstance(valeur, dict) and valeur.get("@type") == "Review":
            return valeur
    raise PageRejetee(REJET_JSONLD_ABSENT, "aucun bloc JSON-LD de type Review")


def _metadonnees(jsonld: dict[str, Any]) -> dict[str, Any]:
    """Le PDF de l'avis, les CIP13, l'ATC et les dossiers du document : des métadonnées."""
    pdf_avis, dossiers = None, []
    for partie in jsonld.get("hasPart") or []:
        nom = str(partie.get("name") or "")
        trouve = _DOSSIER_AVIS.search(nom)
        if trouve:
            dossiers.append(f"CT-{trouve[1]}")
            pdf_avis = pdf_avis or partie.get("contentUrl")
    produit = jsonld.get("itemReviewed") or {}
    code = produit.get("code") or {}
    return {
        "pdf_avis": pdf_avis,
        "cip13": tuple(_CIP13.findall(str(produit.get("dosageForm") or ""))),
        "atc": code.get("codeValue"),
        "dossiers_documents": tuple(sorted(set(dossiers))),
    }


def _controler_niveaux(extrait: AvisExtrait, jsonld: dict[str, Any]) -> None:
    """Les niveaux des tables SMR et ASMR doivent égaler ceux du JSON-LD, dans l'ordre."""
    attendus: dict[str, list[str]] = {RUBRIQUE_SMR: [], RUBRIQUE_ASMR: []}
    for aspect in jsonld.get("reviewAspect") or []:
        propriete = str(aspect.get("propertyID") or "")
        rubrique = RUBRIQUE_ASMR if "(ASMR)" in propriete else RUBRIQUE_SMR
        attendus[rubrique].append(normaliser(str(aspect.get("value") or "")).casefold())
    for rubrique, valeurs in attendus.items():
        lus = [niveau.casefold() for niveau in extrait.niveaux(rubrique)]
        if lus != valeurs:
            raise PageRejetee(REJET_NIVEAUX, f"{rubrique} : table {lus} contre JSON-LD {valeurs}")


@dataclass
class _Ouvert:
    balise: str
    attributs: dict[str, str | None] = field(default_factory=dict)


class _Lecteur(HTMLParser):
    """Un seul passage sur la page : le titre, le sous-titre, le JSON-LD, les blocs du corps."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titre = ""
        self.sous_titre = ""
        self.url_canonique: str | None = None
        self.jsonld: list[str] = []
        self.lignes: list[Ligne] = []
        self._dans_jsonld = False
        self._tampon_jsonld: list[str] = []
        self._ignore = 0
        self._dans_titre = False
        self._dans_sous_titre = 0  # profondeur de div depuis le sous-titre
        self._capture = False  # dans content--main, avant les documents
        self._fini = False
        self._pile: list[_Ouvert] = []
        self._texte: list[str] = []
        self._rubrique = RUBRIQUE_DEMANDE
        self._attend_nature = False

    def handle_starttag(self, balise: str, attributs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attributs)
        if balise == "script" and attrs.get("type") == "application/ld+json":
            self._dans_jsonld, self._tampon_jsonld = True, []
            return
        if balise == "meta" and attrs.get("property") == "og:url":
            self.url_canonique = attrs.get("content")
        if balise in _IGNORES:
            self._ignore += 1
            return
        if balise == "h1":
            self._dans_titre = True
        classes = (attrs.get("class") or "").split()
        if balise == "div":
            if self._dans_sous_titre:
                self._dans_sous_titre += 1
            elif "sub-title" in classes:
                self._dans_sous_titre = 1
            if "content--main" in classes and not self._fini:
                self._capture = True
        if not self._capture or self._fini:
            return
        if balise == "a" and attrs.get("id") in (RUBRIQUE_SMR, RUBRIQUE_ASMR):
            self._vider()
            self._rubrique = str(attrs["id"])
        if balise in _BLOCS or balise == "br":
            self._vider()
        if balise in _BLOCS:
            self._pile.append(_Ouvert(balise, attrs))

    def handle_endtag(self, balise: str) -> None:
        if balise == "script" and self._dans_jsonld:
            self._dans_jsonld = False
            self.jsonld.append("".join(self._tampon_jsonld))
            return
        if balise in _IGNORES:
            self._ignore = max(0, self._ignore - 1)
            return
        if balise == "h1":
            self._dans_titre = False
        if balise == "div" and self._dans_sous_titre:
            self._dans_sous_titre -= 1
        if not self._capture or self._fini or balise not in _BLOCS:
            return
        self._vider()
        for position in range(len(self._pile) - 1, -1, -1):
            if self._pile[position].balise == balise:
                del self._pile[position:]
                break

    def handle_data(self, donnees: str) -> None:
        if self._dans_jsonld:
            self._tampon_jsonld.append(donnees)
            return
        if self._ignore:
            return
        if self._dans_titre:
            self.titre += donnees
        if self._dans_sous_titre:
            self.sous_titre += donnees
        if self._capture and not self._fini:
            self._texte.append(donnees)

    def handle_comment(self, commentaire: str) -> None:
        if self._capture and commentaire.strip() == "documents associés":
            self._vider()
            self._fini = True

    def close(self) -> None:
        super().close()
        self._vider()

    def _vider(self) -> None:
        texte = normaliser("".join(self._texte))
        self._texte = []
        if not texte:
            return
        ouvert = next((o for o in reversed(self._pile) if o.balise not in ("ul", "ol")), None)
        balise = ouvert.balise if ouvert else "div"
        if balise == "h4" and texte == TITRE_NATURE:
            self._rubrique, self._attend_nature = RUBRIQUE_DEMANDE, True
            return
        if self._attend_nature:
            self._attend_nature = False
            self.lignes.append(Ligne(RUBRIQUE_DEMANDE, "nature", texte))
            return
        if balise == "h3" and self._rubrique not in (RUBRIQUE_SMR, RUBRIQUE_ASMR):
            self._rubrique = texte
            self.lignes.append(Ligne(texte, "intertitre", texte))
            return
        if balise in ("h3", "h4", "h5", "h6"):
            self.lignes.append(Ligne(self._rubrique, "intertitre", texte))
        elif balise == "li":
            self.lignes.append(Ligne(self._rubrique, "element", texte))
        elif balise == "td" and ouvert is not None and ouvert.attributs.get("width") == "20%":
            self.lignes.append(Ligne(self._rubrique, "niveau", texte))
        else:
            self.lignes.append(Ligne(self._rubrique, "paragraphe", texte))


class _LecteurPrincipal(HTMLParser):
    """Le texte de ``<main>``, une ligne par bloc, sans scripts ni styles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lignes: list[str] = []
        self.vu = False
        self._profondeur = 0
        self._ignore = 0
        self._texte: list[str] = []

    def handle_starttag(self, balise: str, attributs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002 (signature de HTMLParser)
        if balise == "main":
            self.vu = True
            self._profondeur += 1
        elif balise in ("script", "style", "noscript"):
            self._ignore += 1
        elif self._profondeur and (balise in _BLOCS or balise == "br"):
            self._vider()

    def handle_endtag(self, balise: str) -> None:
        if balise == "main":
            self._vider()
            self._profondeur = max(0, self._profondeur - 1)
        elif balise in ("script", "style", "noscript"):
            self._ignore = max(0, self._ignore - 1)
        elif self._profondeur and balise in _BLOCS:
            self._vider()

    def handle_data(self, donnees: str) -> None:
        if self._profondeur and not self._ignore:
            self._texte.append(donnees)

    def _vider(self) -> None:
        texte = normaliser("".join(self._texte))
        self._texte = []
        if texte:
            self.lignes.append(texte)
