"""Comparaison de deux snapshots retenus : les événements, triés de façon déterministe.

Fichier à clé : ``creee``, ``supprimee``, ``modifiee`` avec les champs
modifiés, sur les valeurs normalisées. Fichier ligne à ligne : multiensemble
des lignes normalisées, une ligne qui change donne une ``supprimee`` puis une
``creee``, jamais de ``modifiee`` ; le rang distingue les occurrences d'une
même ligne. Le premier snapshot d'un fichier donne une ``creee`` par entité,
``etat_initial`` vrai (ADR 0006). ``appliquer`` est l'inverse : rejouer les
événements sur un état redonne le snapshot retenu, ce que les tests vérifient.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from pharmaflux.evenements import schema
from pharmaflux.evenements.schema import Evenement, TypeEvenement
from pharmaflux.evenements.snapshot import Identite, Ligne, Snapshot, empreinte_ligne


def comparer(
    precedent: Snapshot | None, nouveau: Snapshot, *, date_source: str | None = None
) -> list[Evenement]:
    """Les événements de ``precedent`` (dernier retenu, ou None au début) vers ``nouveau``.

    Les deux snapshots sont lus avec le même contrat (ADR 0005, point I).
    ``date_source`` est la date affichée par la source pour l'archive de
    ``nouveau`` (manifeste), ou None quand la page ne la donne pas.
    """
    if precedent is not None and precedent.contrat.identifiant != nouveau.contrat.identifiant:
        raise ValueError("deux snapshots d'un même fichier sont attendus")
    if nouveau.horodatage is None:
        raise ValueError(f"{nouveau.archive} : horodatage inconnu, date_observation impossible")
    fabrique = _Fabrique(precedent, nouveau, date_source)
    if nouveau.identite is Identite.CLE:
        evenements = list(_par_cle(fabrique, precedent, nouveau))
    else:
        evenements = list(_par_ligne(fabrique, precedent, nouveau))
    evenements.sort(key=Evenement.cle_de_tri)
    return evenements


@dataclass(slots=True)
class _Fabrique:
    """Ce qui est commun à tous les événements d'une comparaison."""

    precedent: Snapshot | None
    nouveau: Snapshot
    date_source: str | None
    noms: tuple[str, ...] = field(init=False)
    index_cle: list[int] = field(init=False)

    def __post_init__(self) -> None:
        contrat = self.nouveau.contrat
        self.noms = contrat.noms_colonnes
        self.index_cle = [contrat.index(nom) for nom in contrat.cle.colonnes]

    def evenement(
        self, type_: TypeEvenement, avant: Ligne | None, apres: Ligne | None, rang: int = 1
    ) -> Evenement:
        ligne = apres if apres is not None else avant
        assert ligne is not None
        cle = {self.noms[i]: ligne.normalisees[i] for i in self.index_cle}
        empreinte = empreinte_ligne(ligne.normalisees)
        identite = self.nouveau.identite
        archive_precedente = None if self.precedent is None else self.precedent.archive
        horodatage = self.nouveau.horodatage
        assert horodatage is not None
        champs: tuple[str, ...] = ()
        if type_ is TypeEvenement.MODIFIEE:
            assert avant is not None and apres is not None
            champs = tuple(
                nom
                for nom, a, b in zip(self.noms, avant.normalisees, apres.normalisees, strict=True)
                if a != b
            )
        return Evenement(
            id=schema.identifiant(
                self.nouveau.contrat.identifiant,
                self.nouveau.archive,
                archive_precedente,
                type_,
                schema.identite_de_ligne(identite, cle, empreinte, rang),
            ),
            entite=self.nouveau.contrat.identifiant,
            fichier=self.nouveau.contrat.fichier,
            version_contrat=self.nouveau.contrat.version,
            type=type_,
            etat_initial=self.precedent is None,
            identite=identite,
            cle=cle,
            empreinte_ligne=empreinte,
            rang=rang,
            avant=None if avant is None else dict(zip(self.noms, avant.normalisees, strict=True)),
            apres=None if apres is None else dict(zip(self.noms, apres.normalisees, strict=True)),
            champs_modifies=champs,
            anomalies=ligne.anomalies,
            date_source=self.date_source,
            date_observation=horodatage.strftime("%Y-%m-%dT%H:%M:%SZ"),
            archive=self.nouveau.archive,
            archive_sha256=self.nouveau.sha256,
            archive_precedente=archive_precedente,
            archive_precedente_sha256=None if self.precedent is None else self.precedent.sha256,
        )


def _par_cle(
    fabrique: _Fabrique, precedent: Snapshot | None, nouveau: Snapshot
) -> Iterable[Evenement]:
    avant = {} if precedent is None else precedent.par_cle
    for cle, ligne in nouveau.par_cle.items():
        ancienne = avant.get(cle)
        if ancienne is None:
            yield fabrique.evenement(TypeEvenement.CREEE, None, ligne)
        elif ancienne.normalisees != ligne.normalisees:
            yield fabrique.evenement(TypeEvenement.MODIFIEE, ancienne, ligne)
    for cle, ancienne in avant.items():
        if cle not in nouveau.par_cle:
            yield fabrique.evenement(TypeEvenement.SUPPRIMEE, ancienne, None)


def _par_ligne(
    fabrique: _Fabrique, precedent: Snapshot | None, nouveau: Snapshot
) -> Iterable[Evenement]:
    avant = {} if precedent is None else precedent.par_ligne
    for empreinte, (ligne, apres_n) in nouveau.par_ligne.items():
        avant_n = avant[empreinte][1] if empreinte in avant else 0
        for rang in range(avant_n + 1, apres_n + 1):
            yield fabrique.evenement(TypeEvenement.CREEE, None, ligne, rang)
    for empreinte, (ligne, avant_n) in avant.items():
        apres_n = nouveau.par_ligne[empreinte][1] if empreinte in nouveau.par_ligne else 0
        for rang in range(apres_n + 1, avant_n + 1):
            yield fabrique.evenement(TypeEvenement.SUPPRIMEE, ligne, None, rang)


# Un état reconstruit par ``appliquer`` : identité de ligne → (colonne → valeur normalisée,
# occurrences). Des dictionnaires, comparés sans égard à l'ordre des colonnes.
Etat = dict[str, tuple[Mapping[str, str], int]]


def appliquer(etat: Etat, evenements: Iterable[Evenement]) -> Etat:
    """Rejoue ``evenements`` sur ``etat`` (vide au départ) ; rend le nouvel état.

    Les événements d'une comparaison sont triés de sorte que, pour une même
    ligne, la suppression précède la création. Une incohérence (supprimer ce
    qui n'existe pas, créer ce qui existe pour une clé) lève ``ValueError`` :
    c'est la propriété « aucun changement perdu » qui serait fausse.
    """
    suivant = dict(etat)
    for evenement in evenements:
        if evenement.identite is Identite.CLE:
            identite = schema.identite_de_ligne(Identite.CLE, evenement.cle, "", 1)
        else:
            identite = evenement.empreinte_ligne
        present = suivant.get(identite)
        if evenement.type is TypeEvenement.SUPPRIMEE:
            if present is None or (
                evenement.identite is Identite.LIGNE and present[1] != evenement.rang
            ):
                raise ValueError(
                    f"{evenement.id} : suppression d'une ligne absente ou de mauvais rang"
                )
            if present[1] == 1:
                del suivant[identite]
            else:
                suivant[identite] = (present[0], present[1] - 1)
            continue
        assert evenement.apres is not None
        valeurs = dict(evenement.apres)
        if evenement.type is TypeEvenement.MODIFIEE:
            if present is None:
                raise ValueError(f"{evenement.id} : modification d'une ligne absente")
            suivant[identite] = (valeurs, 1)
        elif evenement.identite is Identite.CLE:
            if present is not None:
                raise ValueError(f"{evenement.id} : création d'une clé déjà présente")
            suivant[identite] = (valeurs, 1)
        else:
            occurrences = 0 if present is None else present[1]
            if occurrences + 1 != evenement.rang:
                raise ValueError(
                    f"{evenement.id} : création de rang {evenement.rang} sur {occurrences}"
                )
            suivant[identite] = (valeurs, occurrences + 1)
    return suivant


def etat_du_snapshot(snapshot: Snapshot) -> Etat:
    """L'état qu'``appliquer`` doit redonner pour ``snapshot``."""
    noms = snapshot.contrat.noms_colonnes
    colonnes_cle = snapshot.contrat.cle.colonnes

    def valeurs(ligne: Ligne) -> dict[str, str]:
        return dict(zip(noms, ligne.normalisees, strict=True))

    if snapshot.identite is Identite.CLE:
        return {
            schema.identite_de_ligne(
                Identite.CLE, dict(zip(colonnes_cle, cle, strict=True)), "", 1
            ): (valeurs(ligne), 1)
            for cle, ligne in snapshot.par_cle.items()
        }
    return {empreinte: (valeurs(ligne), n) for empreinte, (ligne, n) in snapshot.par_ligne.items()}
