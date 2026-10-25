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
# Un transfert coupé laisse son morceau dans un dossier .rsync-partiel/ à côté
# du fichier, jamais sous le nom définitif : la copie ne contient aucune
# archive tronquée qui aurait l'air bonne, et le transfert suivant reprend là.

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
if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    usage
fi

hote="$1"
case "$hote" in
    -*) usage ;;
esac
destination="${2:-${PHARMAFLUX_DATA:-$HOME/pharmaflux-data}}"
source_distante="${PHARMAFLUX_VPS_DATA:-/home/pharmaflux/pharmaflux-data}"

mkdir -p "$destination"

echo "rapatriement ${simulation:+(simulation) }: $hote:$source_distante/ -> $destination/"
# -a : droits, dates et arborescence conservés ; --partial-dir : une coupure
# reprend où elle s'était arrêtée, le morceau attend dans .rsync-partiel/ ;
# les .gz sont déjà compressés, pas de -z.
# shellcheck disable=SC2086  # $simulation est vide ou un seul mot
rsync -a -v --partial-dir=.rsync-partiel $simulation \
    --exclude '.*.partiel-*' \
    "$hote:$source_distante/" "$destination/"

if [ -z "$simulation" ]; then
    echo "copie à jour dans $destination ; état : uv run pharmaflux etat --racine \"$destination\""
fi
