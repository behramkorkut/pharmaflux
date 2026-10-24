#!/bin/sh
# Rapatrie l'archive Pharmaflux du VPS vers ce poste, en tirage (rsync par SSH).
#
# Usage : sh infra/planification/rapatrier.sh [--simuler] <hote> [destination]
#   <hote>        nom SSH du VPS : un alias de ~/.ssh/config ou utilisateur@hote.
#                 Aucune adresse n'est écrite dans le dépôt.
#   destination   racine locale de la copie. Défaut : $PHARMAFLUX_DATA, sinon
#                 ~/pharmaflux-data (la racine que « pharmaflux etat » lit).
#   --simuler     montre ce qui serait copié, sans rien écrire.
#
# Source distante : $PHARMAFLUX_VPS_DATA, sinon /home/pharmaflux/pharmaflux-data
# (le chemin posé dans pharmaflux-collecte.service).
#
# Jamais de --delete : l'archive ne fait que grandir, et une copie ne doit
# pouvoir supprimer ni un fichier distant ni un fichier local. Les fichiers
# temporaires d'une écriture en cours (.<nom>.partiel-<pid>) ne sont pas copiés.

set -eu

usage() {
    echo "usage : $0 [--simuler] <hote> [destination]" >&2
    exit 2
}

simulation=""
if [ "${1:-}" = "--simuler" ] || [ "${1:-}" = "-n" ]; then
    simulation="-n"
    shift
fi
[ $# -ge 1 ] && [ $# -le 2 ] || usage

hote="$1"
case "$hote" in
    -*) usage ;;
esac
destination="${2:-${PHARMAFLUX_DATA:-$HOME/pharmaflux-data}}"
source_distante="${PHARMAFLUX_VPS_DATA:-/home/pharmaflux/pharmaflux-data}"

mkdir -p "$destination"

echo "rapatriement ${simulation:+(simulation) }: $hote:$source_distante/ -> $destination/"
# -a : droits, dates et arborescence conservés ; --partial : une coupure
# reprend où elle s'était arrêtée ; les .gz sont déjà compressés, pas de -z.
# shellcheck disable=SC2086  # $simulation est vide ou un seul mot
rsync -a -v --partial $simulation \
    --exclude '.*.partiel-*' \
    "$hote:$source_distante/" "$destination/"

if [ -z "$simulation" ]; then
    echo "copie à jour dans $destination ; état : uv run pharmaflux etat --racine \"$destination\""
fi
