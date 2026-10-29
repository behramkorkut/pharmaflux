"""Les requêtes DuckDB de référence des vues du gold (addendum 1, exigence 1), pour les tests.

Chaque vue est construite en PyArrow et en Python par ``pharmaflux.gold.vues``.
Ici, la même vue est écrite **à part**, en SQL, aussi simplement que possible,
sur les entités typées données à DuckDB ; les deux doivent rendre le même
multiensemble de lignes, listes comprises (``multiensemble``). La fermeture
des lignes de disponibilité est lue ici dans **toutes** les versions du silver
(``historique``, typées, avec leur ``fin_validite``), filtrées en SQL, et non
par ``vues.fermees``. Les alternatives partent de la vue de disponibilité,
qui a sa propre référence.

Ces requêtes ne servent qu'aux tests : elles montent trop haut en mémoire sur
le jeu entier (§0 K), d'où l'échantillon de CIS sur le jeu de démo.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime

import duckdb
import pyarrow as pa
import pyarrow.compute as pc

from pharmaflux.gold.rendu import en_json
from pharmaflux.gold.typage import EntiteTypee, typer_etat
from pharmaflux.gold.vues import jour
from pharmaflux.silver.entrepot import Entrepot
from pharmaflux.silver.sql import CONFIGURATION, REGLAGES

FICHE = """
WITH cis AS (
  SELECT code_cis FROM specialites UNION SELECT code_cis FROM presentations
  UNION SELECT code_cis FROM compositions UNION SELECT code_cis FROM generiques
  UNION SELECT code_cis FROM conditions_prescription UNION SELECT code_cis FROM smr
  UNION SELECT code_cis FROM asmr UNION SELECT code_cis FROM disponibilite
  UNION SELECT code_cis FROM mitm UNION SELECT code_cis FROM infos_importantes
),
pres AS (
  SELECT code_cis, list(struct_pack(code_cip13, code_cip7, libelle_presentation,
    statut_administratif, etat_commercialisation, date_declaration_commercialisation,
    agrement_collectivites, taux_remboursement, prix_medicament, prix_public,
    honoraires_dispensation, indications_remboursement) ORDER BY code_cip13) AS l
  FROM presentations GROUP BY code_cis
),
compo AS (
  SELECT code_cis, list(struct_pack(designation_element, code_substance, denomination_substance,
    dosage, reference_dosage, nature_composant, numero_liaison)
    ORDER BY designation_element, numero_liaison, nature_composant, code_substance) AS l
  FROM compositions GROUP BY code_cis
),
gen AS (
  SELECT code_cis, list(struct_pack(identifiant_groupe, libelle_groupe, type_generique, numero_tri)
    ORDER BY identifiant_groupe) AS l
  FROM generiques GROUP BY code_cis
),
cpd AS (SELECT code_cis, list(condition ORDER BY condition) AS l FROM conditions_prescription
  GROUP BY code_cis),
liens AS (SELECT code_dossier_has, list(lien_avis ORDER BY lien_avis) AS l FROM liens_ct
  GROUP BY code_dossier_has),
smr_ AS (
  SELECT a.code_cis, list(struct_pack(a.code_dossier_has, a.motif_evaluation, a.date_avis,
    a.valeur_smr, a.libelle_smr, liens_avis := k.l, a.occurrences)
    ORDER BY a.date_avis DESC, a.code_dossier_has, a.motif_evaluation, a.valeur_smr,
      a.libelle_smr) AS l
  FROM (SELECT code_cis, code_dossier_has, motif_evaluation, date_avis, valeur_smr, libelle_smr,
          count(*) AS occurrences FROM smr GROUP BY ALL) a
  LEFT JOIN liens k USING (code_dossier_has) GROUP BY a.code_cis
),
asmr_ AS (
  SELECT a.code_cis, list(struct_pack(a.code_dossier_has, a.motif_evaluation, a.date_avis,
    a.valeur_asmr, a.libelle_asmr, liens_avis := k.l, a.occurrences)
    ORDER BY a.date_avis DESC, a.code_dossier_has, a.motif_evaluation, a.valeur_asmr,
      a.libelle_asmr) AS l
  FROM (SELECT code_cis, code_dossier_has, motif_evaluation, date_avis, valeur_asmr, libelle_asmr,
          count(*) AS occurrences FROM asmr GROUP BY ALL) a
  LEFT JOIN liens k USING (code_dossier_has) GROUP BY a.code_cis
),
dispo AS (
  SELECT code_cis, list(struct_pack(code_cip13, code_statut, libelle_statut, date_debut,
    date_mise_a_jour, date_remise_a_disposition, lien_ansm,
    portee := CASE WHEN code_cip13 IS NULL THEN 'specialite' ELSE 'presentation' END,
    occurrences, debut_a_venir := date_debut > $jour)
    ORDER BY date_debut, lien_ansm, code_cip13, code_statut, date_mise_a_jour,
      date_remise_a_disposition) AS l
  FROM (SELECT code_cis, code_cip13, code_statut, libelle_statut, date_debut, date_mise_a_jour,
          date_remise_a_disposition, lien_ansm, count(*) AS occurrences
        FROM disponibilite GROUP BY ALL)
  GROUP BY code_cis
),
infos AS (
  SELECT code_cis, list(struct_pack(date_debut, date_fin, texte_et_lien)
    ORDER BY date_debut, date_fin, texte_et_lien) AS l
  FROM infos_importantes
  WHERE date_debut <= $jour AND (date_fin IS NULL OR date_fin >= $jour)
  GROUP BY code_cis
),
prov AS (
  SELECT code_cis,
    list(struct_pack(entite, fichier, date_source, connu_depuis) ORDER BY entite) AS l
  FROM (
    SELECT code_cis, 'bdpm.asmr' AS entite, 'CIS_HAS_ASMR_bdpm.txt' AS fichier,
      max(date_source) AS date_source, max(debut_validite) AS connu_depuis FROM asmr GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.compositions', 'CIS_COMPO_bdpm.txt', max(date_source),
      max(debut_validite) FROM compositions GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.conditions_prescription', 'CIS_CPD_bdpm.txt',
      max(date_source), max(debut_validite) FROM conditions_prescription GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.disponibilite', 'CIS_CIP_Dispo_Spec.txt', max(date_source),
      max(debut_validite) FROM disponibilite GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.generiques', 'CIS_GENER_bdpm.txt', max(date_source),
      max(debut_validite) FROM generiques GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.infos_importantes', 'CIS_InfoImportantes.txt',
      max(date_source), max(debut_validite) FROM infos_importantes GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.mitm', 'CIS_MITM.txt', max(date_source),
      max(debut_validite) FROM mitm GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.presentations', 'CIS_CIP_bdpm.txt', max(date_source),
      max(debut_validite) FROM presentations GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.smr', 'CIS_HAS_SMR_bdpm.txt', max(date_source),
      max(debut_validite) FROM smr GROUP BY 1
    UNION ALL SELECT code_cis, 'bdpm.specialites', 'CIS_bdpm.txt', max(date_source),
      max(debut_validite) FROM specialites GROUP BY 1
  ) GROUP BY code_cis
),
illisibles AS (
  SELECT code_cis, list_sort(list_distinct(list(colonne))) AS l FROM (
    SELECT code_cis, 'asmr.' || unnest(colonnes_illisibles) AS colonne FROM asmr
    UNION ALL SELECT code_cis, 'compositions.' || unnest(colonnes_illisibles) FROM compositions
    UNION ALL SELECT code_cis, 'conditions_prescription.' || unnest(colonnes_illisibles)
      FROM conditions_prescription
    UNION ALL SELECT code_cis, 'disponibilite.' || unnest(colonnes_illisibles) FROM disponibilite
    UNION ALL SELECT code_cis, 'generiques.' || unnest(colonnes_illisibles) FROM generiques
    UNION ALL SELECT code_cis, 'infos_importantes.' || unnest(colonnes_illisibles)
      FROM infos_importantes
    UNION ALL SELECT code_cis, 'mitm.' || unnest(colonnes_illisibles) FROM mitm
    UNION ALL SELECT code_cis, 'presentations.' || unnest(colonnes_illisibles) FROM presentations
    UNION ALL SELECT code_cis, 'smr.' || unnest(colonnes_illisibles) FROM smr
    UNION ALL SELECT code_cis, 'specialites.' || unnest(colonnes_illisibles) FROM specialites
  ) GROUP BY code_cis
)
SELECT c.code_cis, s.code_cis IS NOT NULL AS dans_referentiel,
  s.denomination, s.forme_pharmaceutique, s.voies_administration, s.statut_amm,
  s.type_procedure_amm, s.etat_commercialisation, s.date_amm, s.statut_bdm,
  s.numero_autorisation_europeenne, s.titulaires, s.surveillance_renforcee,
  m.code_cis IS NOT NULL AS mitm, m.code_atc, m.date_publication AS date_publication_mitm,
  pres.l AS presentations, compo.l AS composition, gen.l AS groupes_generiques,
  cpd.l AS conditions_prescription, smr_.l AS avis_smr, asmr_.l AS avis_asmr,
  dispo.l AS disponibilite, infos.l AS infos_importantes, prov.l AS provenance,
  coalesce(illisibles.l, []) AS colonnes_illisibles, $instant AS instant
FROM cis c
LEFT JOIN specialites s USING (code_cis) LEFT JOIN mitm m USING (code_cis)
LEFT JOIN pres USING (code_cis) LEFT JOIN compo USING (code_cis) LEFT JOIN gen USING (code_cis)
LEFT JOIN cpd USING (code_cis) LEFT JOIN smr_ USING (code_cis) LEFT JOIN asmr_ USING (code_cis)
LEFT JOIN dispo USING (code_cis) LEFT JOIN infos USING (code_cis) LEFT JOIN prov USING (code_cis)
LEFT JOIN illisibles USING (code_cis)
"""

# La priorité : déclaré (en cours), sinon fin de publication (fermée au plus à l'instant), sinon
# aucun signalement. Une ligne sans CIP13 vise toutes les présentations de sa spécialité.
DISPONIBILITE = """
WITH lignes AS (
  SELECT code_cis, code_cip13, code_statut, libelle_statut, date_debut, date_mise_a_jour,
    date_remise_a_disposition, lien_ansm, count(*) AS occurrences,
    max(date_source) AS date_source, max(debut_validite) AS connu_depuis,
    list_sort(list_distinct(flatten(list(colonnes_illisibles)))) AS colonnes_illisibles
  FROM disponibilite GROUP BY ALL
),
visees AS (
  SELECT l.*, l.code_cip13 AS cible FROM lignes l WHERE l.code_cip13 IS NOT NULL
  UNION ALL
  SELECT l.*, p.code_cip13 FROM lignes l LEFT JOIN presentations p ON p.code_cis = l.code_cis
  WHERE l.code_cip13 IS NULL
),
declarees AS (
  SELECT v.code_cis, v.cible AS code_cip13, p.libelle_presentation,
    'declare' AS etat_signalement, v.code_statut, v.libelle_statut, v.date_debut,
    v.date_mise_a_jour, v.date_remise_a_disposition, v.lien_ansm,
    CASE WHEN v.code_cip13 IS NULL THEN 'specialite' ELSE 'presentation' END AS portee,
    v.occurrences, p.code_cip13 IS NOT NULL AS presentation_connue,
    v.date_debut > $jour AS debut_a_venir, NULL::TIMESTAMPTZ AS fin_publication,
    v.date_source, v.connu_depuis, v.colonnes_illisibles
  FROM visees v LEFT JOIN presentations p ON p.code_cip13 = v.cible
),
fermees AS (SELECT * FROM historique WHERE fin_validite <= $instant),
fermees_visees AS (
  SELECT f.*, f.code_cip13 AS cible FROM fermees f WHERE f.code_cip13 IS NOT NULL
  UNION ALL
  SELECT f.*, p.code_cip13 FROM fermees f LEFT JOIN presentations p ON p.code_cis = f.code_cis
  WHERE f.code_cip13 IS NULL
),
retirees AS (
  SELECT fv.*, row_number() OVER (
    PARTITION BY fv.code_cis, fv.cible
    ORDER BY fv.fin_validite DESC, CAST(fv.code_cip13 AS VARCHAR) DESC,
      CAST(fv.code_statut AS VARCHAR) DESC, CAST(fv.libelle_statut AS VARCHAR) DESC,
      CAST(fv.date_debut AS VARCHAR) DESC, CAST(fv.date_mise_a_jour AS VARCHAR) DESC,
      CAST(fv.date_remise_a_disposition AS VARCHAR) DESC, fv.lien_ansm DESC) AS rang_fin
  FROM fermees_visees fv
  WHERE NOT EXISTS (SELECT 1 FROM declarees d WHERE d.code_cis = fv.code_cis
                    AND d.code_cip13 IS NOT DISTINCT FROM fv.cible)
),
fins AS (
  SELECT r.code_cis, r.cible AS code_cip13, p.libelle_presentation,
    'fin_de_publication' AS etat_signalement, r.code_statut, r.libelle_statut, r.date_debut,
    r.date_mise_a_jour, r.date_remise_a_disposition, r.lien_ansm,
    CASE WHEN r.code_cip13 IS NULL THEN 'specialite' ELSE 'presentation' END AS portee,
    1 AS occurrences, p.code_cip13 IS NOT NULL AS presentation_connue,
    r.date_debut > $jour AS debut_a_venir, r.fin_validite AS fin_publication,
    r.date_source, r.debut_validite AS connu_depuis,
    list_sort(list_distinct(r.colonnes_illisibles)) AS colonnes_illisibles
  FROM retirees r LEFT JOIN presentations p ON p.code_cip13 = r.cible
  WHERE r.rang_fin = 1
),
aucun AS (
  SELECT p.code_cis, p.code_cip13, p.libelle_presentation, 'aucun_signalement',
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, true, NULL, NULL, NULL, NULL,
    []::VARCHAR[]
  FROM presentations p
  WHERE NOT EXISTS (SELECT 1 FROM declarees d WHERE d.code_cis = p.code_cis
                    AND d.code_cip13 = p.code_cip13)
    AND NOT EXISTS (SELECT 1 FROM fins f WHERE f.code_cis = p.code_cis
                    AND f.code_cip13 = p.code_cip13)
),
tout AS (SELECT * FROM declarees UNION ALL SELECT * FROM fins UNION ALL SELECT * FROM aucun)
SELECT t.code_cis, t.code_cip13, t.libelle_presentation, s.denomination, t.etat_signalement,
  t.code_statut, t.libelle_statut, t.date_debut, t.date_mise_a_jour, t.date_remise_a_disposition,
  t.lien_ansm, t.portee, t.occurrences, t.presentation_connue, t.debut_a_venir,
  t.fin_publication, t.date_source, t.connu_depuis, t.colonnes_illisibles
FROM tout t LEFT JOIN specialites s USING (code_cis)
"""

ALTERNATIVES = """
SELECT g.identifiant_groupe, g.libelle_groupe, g.code_cis, s.denomination, g.type_generique,
  g.numero_tri, p.code_cip13, p.libelle_presentation, p.etat_commercialisation,
  p.statut_administratif, d.etat_signalement, d.code_statut, d.libelle_statut, d.date_debut,
  d.date_remise_a_disposition, d.lien_ansm, d.portee, d.debut_a_venir, d.fin_publication
FROM generiques g
LEFT JOIN specialites s USING (code_cis)
LEFT JOIN presentations p USING (code_cis)
LEFT JOIN (SELECT * FROM disponibilite_courante
           WHERE presentation_connue AND code_cip13 IS NOT NULL) d
  ON d.code_cip13 = p.code_cip13
"""


def historique(entrepot: Entrepot, etats: Mapping[str, EntiteTypee]) -> pa.Table:
    """Toutes les versions de disponibilité, typées, avec leur ``fin_validite``."""
    table = entrepot.table("bdpm.disponibilite")
    assert table is not None
    toutes = table.scan().to_arrow()
    contrat = etats["bdpm.disponibilite"].contrat
    typees = typer_etat("bdpm.disponibilite", contrat, toutes).table
    return typees.append_column("fin_validite", toutes["fin_validite"])


def connexion_reference(
    etats: Mapping[str, EntiteTypee],
    historique_: pa.Table,
    cis: Sequence[str] | None = None,
    disponibilite_courante: pa.Table | None = None,
) -> duckdb.DuckDBPyConnection:
    """Les entités typées données à DuckDB, réduites à ``cis`` si on le demande.

    La connexion a la barrière de ``silver sql`` et un seul fil : avec les huit
    fils du Mac, la requête de la fiche prenait 190 Mo de plus, même sur 28 CIS.
    """
    con = duckdb.connect(config={**CONFIGURATION, "threads": 1})
    for reglage in REGLAGES:
        con.execute(reglage)
    for entite, etat in etats.items():
        con.register(entite.partition(".")[2], _reduire(etat.table, cis))
    con.register("historique", _reduire(historique_, cis))
    if disponibilite_courante is not None:
        con.register("disponibilite_courante", _reduire(disponibilite_courante, cis))
    return con


def _reduire(table: pa.Table, cis: Sequence[str] | None) -> pa.Table:
    if cis is None or "code_cis" not in table.column_names:
        return table
    return table.filter(pc.is_in(table["code_cis"], value_set=pa.array(list(cis), pa.string())))


def reference(con: duckdb.DuckDBPyConnection, requete: str, instant: datetime) -> pa.Table:
    """Le résultat d'une requête de référence, avec ``$jour`` et ``$instant`` liés."""
    parametres: dict[str, object] = {}
    if "$jour" in requete:
        parametres["jour"] = jour(instant)
    if "$instant" in requete:
        parametres["instant"] = instant
    return con.execute(requete, parametres).to_arrow_table()


def multiensemble(table: pa.Table, cis: Sequence[str] | None = None) -> Counter[str]:
    """Les lignes d'une table, écrites en JSON trié : l'égalité des deux en multiensemble."""
    lignes = _reduire(table, cis).to_pylist()
    return Counter(
        json.dumps(en_json(ligne), sort_keys=True, ensure_ascii=False) for ligne in lignes
    )
