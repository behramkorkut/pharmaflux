"""Les fragments d'une fiche médicament : le texte que l'index encode, et ses métadonnées.

Une fonction de la fiche du gold (une ligne de la vue, ``to_pylist``), et de
rien d'autre : ni horloge, ni LLM, ni ordre de dictionnaire. Les mêmes fiches
donnent les mêmes fragments, à l'octet, et les mêmes identifiants (PRD §6.7,
mission 07, addendum 1 D).

Cinq fragments par fiche au plus, chacun ouvert par la ligne d'identité
(``CIS … — dénomination``) pour qu'il se comprenne seul :

- ``identite`` : la spécialité, sa composition, ses groupes génériques, ses
  conditions de prescription ; ou la phrase d'une fiche partielle ;
- ``presentations`` : les présentations, leurs taux et leurs prix ;
- ``avis`` : les avis SMR et ASMR de la BDPM ;
- ``disponibilite`` : le statut MITM et les signalements en cours, ou la
  phrase « aucun signalement », qui n'est jamais « disponible » (ADR 0003) ;
- ``informations`` : les informations importantes en cours.

``identite`` et ``disponibilite`` existent pour toute fiche ; les trois autres
seulement quand leur section n'est pas vide. Un fragment trop long se découpe
par élément, jamais au milieu d'une ligne : chaque partie répète la ligne
d'identité et dit « (partie k sur n) ».

Ce que le texte encodé ne contient pas : l'instant de l'état (tenu une fois,
par l'index, addendum 1 D2), les liens (en métadonnée) et les citations (en
métadonnée : fichier, date de la source, observée depuis). Une valeur absente
ou illisible ne s'écrit pas : la phrase est omise, jamais devinée.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

FORMAT = (
    1  # change dès que, pour les mêmes fiches, un texte, un identifiant ou une métadonnée change
)
BORNE_CARACTERES = 1200  # recalée au palier 2 : au pire 2,48 caractères par jeton e5, 512 au plus
ESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/behramkorkut/pharmaflux/fragments")

SECTIONS = ("identite", "presentations", "avis", "disponibilite", "informations")
# Les entités qui nourrissent chaque section : ses citations, et la place de ses illisibles.
ENTITES_SECTION: dict[str, tuple[str, ...]] = {
    "identite": (
        "bdpm.specialites",
        "bdpm.compositions",
        "bdpm.generiques",
        "bdpm.conditions_prescription",
    ),
    "presentations": ("bdpm.presentations",),
    "avis": ("bdpm.smr", "bdpm.asmr"),
    "disponibilite": ("bdpm.mitm", "bdpm.disponibilite"),
    "informations": ("bdpm.infos_importantes",),
}
FICHIER_DISPONIBILITE = "CIS_CIP_Dispo_Spec.txt"
FICHIER_SPECIALITES = "CIS_bdpm.txt"

AUCUN_SIGNALEMENT = (
    "Aucun signalement dans le fichier de disponibilité de l'ANSM. Cela ne veut pas dire"
    " « disponible » : le fichier ne liste que les ruptures, tensions, arrêts et remises à"
    " disposition déclarés."
)
PORTEE_SPECIALITE = (
    "vise la spécialité entière (toutes ses présentations), aucune présentation (CIP13)"
    " n'est nommée"
)
_MENTION_LA_PLUS_LONGUE = "(suite, partie 99 sur 99)"
_LIEN = re.compile(r"<a\b[^>]*?\bhref=(['\"])(.*?)\1[^>]*>(.*?)</a>", re.DOTALL | re.IGNORECASE)
_BALISE = re.compile(r"<[^>]+>")

Fiche = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Source:
    """Une citation : le fichier BDPM, la date de la source, depuis quand la valeur est observée."""

    fichier: str
    date_source: str | None
    observee_depuis: str | None


@dataclass(frozen=True, slots=True)
class Fragment:
    identifiant: str
    code_cis: str
    section: str
    partie: int
    parties: int
    denomination: str | None
    dans_referentiel: bool
    texte: str
    sources: tuple[Source, ...]
    liens: tuple[str, ...]

    @property
    def empreinte_texte(self) -> str:
        return hashlib.sha256(self.texte.encode("utf-8")).hexdigest()

    def en_dict(self) -> dict[str, object]:
        """Le fragment tel que l'écrivent ``index fragments`` et l'index : clés dans cet ordre."""
        return {
            "identifiant": self.identifiant,
            "format": FORMAT,
            "code_cis": self.code_cis,
            "section": self.section,
            "partie": self.partie,
            "parties": self.parties,
            "denomination": self.denomination,
            "dans_referentiel": self.dans_referentiel,
            "texte": self.texte,
            "empreinte_texte": self.empreinte_texte,
            "sources": [
                {
                    "fichier": s.fichier,
                    "date_source": s.date_source,
                    "observee_depuis": s.observee_depuis,
                }
                for s in self.sources
            ],
            "liens": list(self.liens),
        }

    def en_jsonl(self) -> str:
        return json.dumps(self.en_dict(), ensure_ascii=False, separators=(",", ":"))


def identifiant(code_cis: str, section: str, partie: int) -> str:
    """Déterministe, et indépendant du texte : un fragment qui change garde son identifiant."""
    return str(uuid.uuid5(ESPACE, f"f{FORMAT}/{code_cis}/{section}/{partie}"))


@dataclass(frozen=True, slots=True)
class _Bloc:
    """Un sous-titre et ses éléments (une ligne chacun) ; la découpe ne coupe qu'entre deux."""

    titre: str
    elements: tuple[str, ...]


def fragments(fiche: Fiche) -> list[Fragment]:
    """Les fragments d'une fiche, dans l'ordre des sections, puis des parties."""
    code_cis = str(fiche["code_cis"])
    entete = f"CIS {code_cis} — {fiche['denomination'] or '(dénomination inconnue)'}"
    illisibles = _illisibles_par_section(fiche)
    resultat: list[Fragment] = []
    for section in SECTIONS:
        contenu = _SECTIONS[section](fiche)
        if contenu is None:
            continue
        blocs, liens = contenu
        if section in illisibles:
            blocs = [
                *blocs,
                _Bloc(
                    "Valeurs illisibles dans la source, non reprises : "
                    + ", ".join(illisibles[section]),
                    (),
                ),
            ]
        parties = _decouper(entete, blocs, BORNE_CARACTERES)
        if len(parties) > 1:  # la place de la mention « (suite, partie k sur n) »
            parties = _decouper(entete, blocs, BORNE_CARACTERES - len(_MENTION_LA_PLUS_LONGUE) - 1)
        sources = _sources(fiche, section)
        for numero, lignes in enumerate(parties, start=1):
            if len(parties) > 1:
                mention = f"(partie 1 sur {len(parties)})" if numero == 1 else None
                mention = mention or f"(suite, partie {numero} sur {len(parties)})"
                lignes = [lignes[0], mention, *lignes[1:]]
            resultat.append(
                Fragment(
                    identifiant=identifiant(code_cis, section, numero),
                    code_cis=code_cis,
                    section=section,
                    partie=numero,
                    parties=len(parties),
                    denomination=fiche["denomination"],
                    dans_referentiel=bool(fiche["dans_referentiel"]),
                    texte="\n".join(lignes),
                    sources=sources,
                    liens=tuple(liens),
                )
            )
    return resultat


def fragments_des_fiches(fiches: Any, lot: int = 500) -> Iterator[Fragment]:
    """Les fragments de toutes les fiches d'une table PyArrow (la vue du gold), par lots."""
    for morceau in fiches.to_batches(max_chunksize=lot):
        for fiche in morceau.to_pylist():
            yield from fragments(fiche)


# --- les sections ------------------------------------------------------------------------------

Contenu = tuple[list[_Bloc], list[str]] | None


def _identite(fiche: Fiche) -> Contenu:
    if not fiche["dans_referentiel"]:
        fichiers = sorted({p["fichier"] for p in fiche["provenance"] or ()})
        blocs = [
            _Bloc(
                "Absent du référentiel des spécialités (CIS_bdpm.txt) : fiche partielle, faite des"
                f" seuls fichiers qui citent ce CIS ({', '.join(fichiers) or 'aucun'}).",
                (),
            )
        ]
    else:
        morceaux = [
            fiche["forme_pharmaceutique"],
            _avec("voie(s) ", _liste(fiche["voies_administration"])),
            _statut_amm(fiche),
            fiche["etat_commercialisation"],
            _avec("titulaire(s) ", _liste(fiche["titulaires"])),
        ]
        blocs = [_Bloc("Spécialité : " + _joindre(morceaux), ())]
        if fiche["surveillance_renforcee"]:
            blocs.append(_Bloc("Sous surveillance renforcée.", ()))
    blocs.append(_bloc("Composition", fiche["composition"], _composant))
    blocs.append(_bloc("Groupes génériques", fiche["groupes_generiques"], _groupe))
    blocs.append(_bloc("Conditions de prescription", fiche["conditions_prescription"], str))
    return blocs, []


def _presentations(fiche: Fiche) -> Contenu:
    if not fiche["presentations"]:
        return None
    return [_bloc("Présentations", fiche["presentations"], _presentation)], []


def _avis(fiche: Fiche) -> Contenu:
    if not fiche["avis_smr"] and not fiche["avis_asmr"]:
        return None
    blocs, liens = [], []
    for genre in ("smr", "asmr"):
        avis = fiche[f"avis_{genre}"] or []
        blocs.append(_bloc(f"Avis {genre.upper()}", avis, lambda a, g=genre: _un_avis(a, g)))
        liens += [lien for a in avis for lien in a["liens_avis"] or ()]
    return blocs, _distincts(liens)


def _disponibilite(fiche: Fiche) -> Contenu:
    blocs: list[_Bloc] = []
    if fiche["mitm"]:
        blocs.append(
            _Bloc(
                "Médicament d'intérêt thérapeutique majeur"
                + _entre(
                    _joindre(
                        [
                            _avec("ATC ", fiche["code_atc"]),
                            _avec("liste publiée le ", _texte(fiche["date_publication_mitm"])),
                        ],
                        ", ",
                    )
                )
                + ".",
                (),
            )
        )
    signalements = fiche["disponibilite"] or []
    libelles = {p["code_cip13"]: p["libelle_presentation"] for p in fiche["presentations"] or ()}
    if signalements:
        blocs.append(
            _bloc(
                "Disponibilité, signalements en cours dans le fichier de l'ANSM",
                signalements,
                lambda s: _signalement(s, libelles),
            )
        )
    else:
        blocs.append(_Bloc(AUCUN_SIGNALEMENT, ()))
    return blocs, _distincts([s["lien_ansm"] for s in signalements if s["lien_ansm"]])


def _informations(fiche: Fiche) -> Contenu:
    infos = fiche["infos_importantes"]
    if not infos:
        return None
    titres, liens = [], []
    for info in infos:
        titre, lien = titre_et_lien(info["texte_et_lien"])
        fin = _texte(info["date_fin"])
        periode = f"du {_texte(info['date_debut'])} " + (f"au {fin}" if fin else "sans date de fin")
        titres.append(f"{periode} : {titre}")
        if lien:
            liens.append(lien)
    return [_Bloc(f"Informations importantes en cours ({len(infos)}) :", tuple(titres))], (
        _distincts(liens)
    )


_SECTIONS = {
    "identite": _identite,
    "presentations": _presentations,
    "avis": _avis,
    "disponibilite": _disponibilite,
    "informations": _informations,
}


# --- les éléments ------------------------------------------------------------------------------


def _statut_amm(fiche: Fiche) -> str | None:
    statut = fiche["statut_amm"]
    if statut is None:
        return None
    return (
        str(statut)
        + _avec(" depuis le ", _texte(fiche["date_amm"]))
        + _entre(fiche["type_procedure_amm"], " ")
    )


def _composant(c: Mapping[str, Any]) -> str:
    substance = _joindre([c["denomination_substance"], c["dosage"]], " ")
    return f"{c['designation_element']} : {substance}" + _entre(c["nature_composant"], " ")


def _groupe(g: Mapping[str, Any]) -> str:
    return (
        f"groupe {g['identifiant_groupe']}"
        + _entre(g["libelle_groupe"], " ")
        + _avec(", type ", g["type_generique"])
    )


def _presentation(p: Mapping[str, Any]) -> str:
    taux = _liste(p["taux_remboursement"])
    prix = p["prix_public"]
    morceaux = [
        p["libelle_presentation"],
        p["etat_commercialisation"],
        f"taux {taux}" if taux else "taux non renseigné",
        f"prix public {_texte(prix)} €" if prix is not None else "prix public non renseigné",
    ]
    return f"{p['code_cip13']} : {_joindre(morceaux)}"


def _un_avis(a: Mapping[str, Any], genre: str) -> str:
    valeur = a[f"valeur_{genre}"] or "valeur non renseignée"
    precision = _joindre([a["motif_evaluation"], a["code_dossier_has"]], ", ")
    return f"{_texte(a['date_avis']) or 'date inconnue'} : {valeur}" + _entre(precision, " ")


def _signalement(s: Mapping[str, Any], libelles: Mapping[str, Any]) -> str:
    statut, debut = s["libelle_statut"] or "statut non renseigné", _texte(s["date_debut"])
    if s["debut_a_venir"]:
        quand = f"annoncé à partir du {debut}, pas encore commencé au jour de l'état"
    else:
        quand = f"depuis le {debut}" if debut else "sans date de début"
    morceaux = [
        f"{statut} {quand}",
        _avec("mis à jour le ", _texte(s["date_mise_a_jour"])),
        _avec("remise à disposition le ", _texte(s["date_remise_a_disposition"])),
    ]
    cip13 = s["code_cip13"]
    if cip13 is None:
        portee = PORTEE_SPECIALITE
    else:
        portee = f"vise la présentation {cip13}" + _entre(libelles.get(cip13), " ")
    return _joindre([*morceaux, portee])


def titre_et_lien(brut: str | None) -> tuple[str, str | None]:
    """Le titre d'une information importante, mot pour mot, et son lien (addendum 1 D3).

    La BDPM donne une balise ``<a … href='…'>Titre</a>`` ; le titre est extrait et ses
    entités décodées (``&ecirc;`` → « ê ») : la forme change, pas le sens. Sans balise, le
    texte entier, entités décodées et balises éventuelles retirées.
    """
    if brut is None:
        return "texte non renseigné", None
    trouve = _LIEN.search(brut)
    if trouve is None:
        return html.unescape(_BALISE.sub("", brut)).strip(), None
    return html.unescape(_BALISE.sub("", trouve[3])).strip(), html.unescape(trouve[2])


# --- la mise en forme --------------------------------------------------------------------------


def _bloc(titre: str, elements: Sequence[Any] | None, decrire: Any) -> _Bloc:
    if not elements:
        return _Bloc(f"{titre} : aucun élément dans la source.", ())
    return _Bloc(f"{titre} ({len(elements)}) :", tuple(decrire(e) for e in elements))


def _decouper(entete: str, blocs: Sequence[_Bloc], borne: int) -> list[list[str]]:
    """Les parties d'un fragment, chacune sous ``borne`` si ses éléments le permettent.

    On remplit dans l'ordre ; une ligne qui ferait dépasser la borne ouvre une partie, qui
    répète le sous-titre du bloc en cours avec « (suite) ». Une ligne seule plus longue que la
    borne reste entière, dans sa partie.
    """
    parties: list[list[str]] = [[entete]]
    fixes = 1  # les lignes répétées en tête de la partie en cours (identité, sous-titre)
    for bloc in blocs:
        for rang, ligne in enumerate([bloc.titre, *(f"  - {e}" for e in bloc.elements)]):
            courante = parties[-1]
            taille = sum(len(x) + 1 for x in courante) + len(ligne)
            if taille > borne and len(courante) > fixes:
                courante = [entete]
                if rang > 0:
                    courante.append(f"{bloc.titre.removesuffix(' :')} (suite) :")
                parties.append(courante)
                fixes = len(courante)
            courante.append(ligne)
    return parties


def _sources(fiche: Fiche, section: str) -> tuple[Source, ...]:
    entites = ENTITES_SECTION[section]
    partielle = section == "identite" and not fiche["dans_referentiel"]
    sources = {
        p["fichier"]: Source(p["fichier"], p["date_source"], _texte(p["connu_depuis"]))
        for p in fiche["provenance"] or ()
        if p["entite"] in entites or partielle  # une fiche partielle cite ce qui la fait
    }
    if partielle:
        sources[FICHIER_SPECIALITES] = Source(FICHIER_SPECIALITES, None, None)
    if section == "disponibilite" and FICHIER_DISPONIBILITE not in sources:
        # « aucun signalement » se lit dans un fichier qui ne cite pas ce CIS : pas de date à lui,
        # l'instant de l'index dit à quel état il se rapporte. De même pour une fiche partielle.
        sources[FICHIER_DISPONIBILITE] = Source(FICHIER_DISPONIBILITE, None, None)
    return tuple(sources[f] for f in sorted(sources))


def _illisibles_par_section(fiche: Fiche) -> dict[str, list[str]]:
    """Les colonnes illisibles (« entite.colonne »), rangées dans la section de leur entité.

    Sans fragment pour cette section (une section vide), elles vont dans ``identite``.
    """
    par_section: dict[str, list[str]] = {}
    for colonne in fiche["colonnes_illisibles"] or ():
        entite = "bdpm." + colonne.partition(".")[0]
        section = next((s for s, e in ENTITES_SECTION.items() if entite in e), "identite")
        if section not in ("identite", "disponibilite") and _SECTIONS[section](fiche) is None:
            section = "identite"
        par_section.setdefault(section, []).append(colonne)
    return par_section


def _texte(valeur: object) -> str | None:
    """Une valeur de la fiche en texte : date ``AAAA-MM-JJ``, instant ``…Z``, décimal exact."""
    if valeur is None:
        return None
    if isinstance(valeur, datetime):
        return valeur.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return str(valeur)
    return str(valeur)


def _liste(valeurs: Sequence[Any] | None) -> str | None:
    texte = ", ".join(str(v) for v in valeurs or ())
    return texte or None


def _avec(prefixe: str, valeur: str | None) -> str:
    return "" if valeur is None else prefixe + valeur


def _entre(valeur: str | None, avant: str = " ") -> str:
    return "" if not valeur else f"{avant}({valeur})"


def _joindre(morceaux: Sequence[str | None], separateur: str = " ; ") -> str:
    return separateur.join(m for m in morceaux if m)


def _distincts(valeurs: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(valeurs))
