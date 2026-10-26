"""Rendu d'un profil : texte Markdown, lisible tel quel dans un terminal.

Les tableaux sont alignés pour rester lisibles sans rendu Markdown. Les
valeurs brutes sont reproduites telles quelles, barres verticales échappées.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from pharmaflux.contrats.profil import Profil, ProfilColonne, ProfilLien

Rangee = Sequence[str]


def nombre(n: int) -> str:
    """15883 → ``15 883`` (espace fine insécable, usage français)."""
    return f"{n:,}".replace(",", "\u202f")


def pourcentage(partie: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{100 * partie / total:.1f}".replace(".", ",") + "\u202f%"


def _cellule(valeur: str) -> str:
    return valeur.replace("|", "\\|").replace("\t", "⇥").replace("\r", "␍").replace("\n", "␊")


def tableau(entetes: Rangee, rangees: Sequence[Rangee]) -> str:
    """Un tableau Markdown aux colonnes alignées."""
    cellules = [[_cellule(v) for v in rangee] for rangee in rangees]
    largeurs = [
        max(len(entete), *(len(rangee[i]) for rangee in cellules)) if cellules else len(entete)
        for i, entete in enumerate(entetes)
    ]

    def ligne(valeurs: Rangee) -> str:
        return "| " + " | ".join(v.ljust(largeurs[i]) for i, v in enumerate(valeurs)) + " |"

    lignes = [ligne(entetes), "|" + "|".join("-" * (largeur + 2) for largeur in largeurs) + "|"]
    lignes.extend(ligne(rangee) for rangee in cellules)
    return "\n".join(lignes)


def rendre_markdown(profil: Profil, maintenant: datetime | None = None) -> str:
    """Le profil complet, en Markdown, archive et sha256 en tête (décision 5)."""
    contrat = profil.contrat
    instant = (maintenant or datetime.now(UTC)).strftime("%Y-%m-%d %H:%MZ")
    nom_contrat = contrat.identifiant.partition(".")[2]
    reference = (
        "archive de référence du contrat"
        if profil.archive_de_reference
        else f"le contrat a été vérifié sur `{contrat.source.archive_reference}`"
    )
    parties = [
        f"# Profil — `{contrat.fichier}` ({contrat.identifiant})",
        "",
        f"{contrat.description}.",
        "",
        f"- **Archive** : `{profil.archive}`, sha256 `{profil.sha256}` ({reference}).",
        f"- **Contrat** : `src/pharmaflux/contrats/bdpm/{nom_contrat}.toml` {contrat.version},"
        f" documentation BDPM §{contrat.source.section}.",
        f"- **Produit** par `pharmaflux profil --markdown` le {instant}.",
        "- Données de la BDPM (base-donnees-publique.medicaments.gouv.fr), reproduites telles"
        " que reçues, sans altération : les valeurs citées sont des extraits bruts de l'archive.",
        "",
        "## Conformité au contrat",
        "",
        _phrase_conformite(profil),
        "",
        _tableau_anomalies(profil),
        "",
        "## Clé",
        "",
        _phrase_cle(profil),
        "",
        "## Colonnes",
        "",
        _tableau_colonnes(profil),
    ]
    repartitions = [c for c in profil.colonnes if c.repartition is not None]
    if repartitions:
        parties += [
            "",
            "### Répartitions (énumérations et colonnes à 30 valeurs distinctes au plus)",
        ]
        for colonne in repartitions:
            parties += ["", *_repartition(colonne, profil.lignes_bien_formees)]
    if profil.ordres_dates:
        parties += [
            "",
            "## Ordre des dates",
            "",
            "Lignes où les deux dates se lisent, et ordre observé.",
            "",
            tableau(
                (
                    "première",
                    "seconde",
                    "comparables",
                    "première après",
                    "égales",
                    "première avant",
                ),
                [
                    (
                        o.premiere,
                        o.seconde,
                        nombre(o.comparables),
                        nombre(o.posterieure),
                        nombre(o.egales),
                        nombre(o.anterieure),
                    )
                    for o in profil.ordres_dates
                ],
            ),
        ]
    if profil.liens:
        parties += [
            "",
            "## Liens vers d'autres fichiers",
            "",
            "Taux de correspondance, mesurés sur la dernière archive du fichier cible ;"
            " jamais une anomalie.",
            "",
            tableau(
                ("colonne", "cible", "archive cible", "lignes", "valeurs distinctes", "absentes"),
                [_rangee_lien(lien) for lien in profil.liens],
            ),
        ]
    return "\n".join(parties) + "\n"


def _phrase_conformite(profil: Profil) -> str:
    contrat = profil.contrat
    if profil.nombre_bloquantes == 0:
        verdict = "**aucune anomalie bloquante**"
    else:
        verdict = f"**{nombre(profil.nombre_bloquantes)} anomalie(s) bloquante(s)**"
    return (
        f"{nombre(profil.nombre_lignes)} lignes non vides, {nombre(profil.lignes_bien_formees)}"
        f" bien formées ({len(contrat.colonnes)} colonnes, {contrat.format.encodage},"
        f" {contrat.format.fin_de_ligne}) ; {verdict}."
    )


def _tableau_anomalies(profil: Profil) -> str:
    if not profil.anomalies:
        return "Aucune anomalie."
    rangees = [
        (
            groupe.regle.value,
            "oui" if groupe.bloquante else "non",
            nombre(groupe.nombre),
            " ; ".join(_exemple(a.ligne, a.colonne, a.valeur) for a in groupe.exemples),
        )
        for groupe in profil.anomalies
    ]
    return tableau(
        ("règle", "bloquante", "nombre", "exemples (cinq au plus : ligne, colonne, valeur brute)"),
        rangees,
    )


def _phrase_cle(profil: Profil) -> str:
    cle = profil.contrat.cle
    declaration = "déclarée unique" if cle.unique else f"déclarée non unique ({cle.raison})"
    return (
        f"`{' + '.join(cle.colonnes)}`, {declaration} : {nombre(profil.cle_distinctes)} valeurs"
        f" distinctes pour {nombre(profil.lignes_bien_formees)} lignes,"
        f" {nombre(profil.cle_repetees)} ligne(s) au-delà de la première pour une même clé."
    )


def _tableau_colonnes(profil: Profil) -> str:
    total = profil.lignes_bien_formees
    rangees = [
        (
            str(i + 1),
            c.nom,
            c.type,
            "oui" if c.obligatoire else "non",
            f"{nombre(c.vides)} ({pourcentage(c.vides, total)})",
            nombre(c.distinctes),
            c.minimum or "—",
            c.maximum or "—",
        )
        for i, c in enumerate(profil.colonnes)
    ]
    return tableau(
        ("#", "colonne", "type", "obligatoire", "vides", "distinctes", "minimum", "maximum"),
        rangees,
    )


def _repartition(colonne: ProfilColonne, lignes: int) -> list[str]:
    repartition = colonne.repartition or []
    total = lignes - colonne.vides
    titre = f"**{colonne.nom}** ({nombre(len(repartition))} valeurs, {nombre(colonne.vides)} vides)"
    if not repartition:
        return [titre, "", "Toujours vide."]
    rangees = [(_valeur_visible(v), nombre(n), pourcentage(n, total)) for v, n in repartition]
    return [titre, "", tableau(("valeur", "nombre", "part des non vides"), rangees)]


def _valeur_visible(valeur: str) -> str:
    """Les espaces de tête ou de fin se voient : la valeur est alors entre accents graves."""
    return f"`{valeur}`" if valeur != valeur.strip() else valeur


def _rangee_lien(lien: ProfilLien) -> tuple[str, ...]:
    cible = f"{lien.vers}.{lien.colonne_cible}"
    if lien.archive_cible is None:
        return (lien.colonne, cible, "aucune archive du fichier cible", "—", "—", "—")
    return (
        lien.colonne,
        cible,
        f"`{lien.archive_cible}`",
        f"{nombre(lien.lignes_trouvees)} / {nombre(lien.lignes)}"
        f" ({pourcentage(lien.lignes_trouvees, lien.lignes)})",
        f"{nombre(lien.distinctes_trouvees)} / {nombre(lien.distinctes)}"
        f" ({pourcentage(lien.distinctes_trouvees, lien.distinctes)})",
        ", ".join(lien.exemples_absents) or "—",
    )


def _exemple(ligne: int, colonne: str | None, valeur: str) -> str:
    ou = f"l. {ligne}" if ligne else "fichier"
    if colonne:
        ou += f", {colonne}"
    return f"{ou} : `{valeur}`" if valeur else ou


def resume(profil: Profil) -> str:
    """Une ligne par fichier, pour le terminal."""
    regles = ", ".join(f"{g.regle.value} {nombre(g.nombre)}" for g in profil.anomalies)
    bloquantes = f"{profil.nombre_bloquantes} bloquante(s)"
    return (
        f"{profil.contrat.identifiant:30} {nombre(profil.nombre_lignes):>7} lignes"
        f"  {bloquantes:16} {regles or 'aucune anomalie'}"
    )
