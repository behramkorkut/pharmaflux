"""Le corpus des avis de la HAS (mission 09, ADR 0004) : collecte polie, extraction sans altération.

- ``perimetre`` : les pages à demander, tirées des liens, du SMR et de l'ASMR de la BDPM
  archivés, sans réseau ;
- ``client`` : le client HTTP de la collecte (pause, aucune redirection, arrêt net) ;
- ``manifeste`` : le manifeste en ajout seul ``manifeste/has-pages.jsonl`` ;
- ``collecte`` : un passage (``robots.txt``, mentions légales, pages), sa reprise, sa simulation ;
- ``extraction`` : le texte d'une page d'avis, mot pour mot, ou son rejet motivé ;
- ``verification`` : la preuve de non-altération, par un second lecteur sans code commun.
"""
