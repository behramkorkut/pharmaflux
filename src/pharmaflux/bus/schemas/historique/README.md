# Versions publiées des schémas

Les versions **déjà publiées** d'un sujet, dans l'ordre, sous le nom
`<schema sans .json>.<numéro>.json` (par exemple
`evenement.v1.schema.1.json`). `pharmaflux schemas enregistrer` les
enregistre dans cet ordre avant le schéma courant, pour qu'un registre neuf
(celui de la CI) refuse une évolution incompatible avec la règle
`BACKWARD_TRANSITIVE`. Vide tant que la première version de chaque schéma
est la seule publiée : le schéma courant est alors la version 1.
