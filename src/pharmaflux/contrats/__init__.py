"""Contrats de schéma des fichiers sources (v0) et leur vérification.

- ``modele`` : les types fermés, les règles, les anomalies, les dataclasses
  d'un contrat ;
- ``chargeur`` : lecture stricte des fichiers TOML ``bdpm/<identifiant>.toml`` ;
- ``verification`` : une archive contre son contrat, des anomalies en sortie,
  jamais une correction.
"""
