#!/bin/sh
# Les prérequis de la démo Pharmaflux (mission 04), sans rien télécharger ni démarrer.
#
# Usage : sh infra/demo/prerequis.sh [console]
#   console   vérifie aussi l'image de la console (profil « console » du fichier compose),
#             pour « make console » ; sans lui, seules les images des services sans profil,
#             celles que « make up » et « make demo » lancent.
#
# Quatre contrôles, chacun avec le geste à faire s'il échoue :
#   1. docker est installé et le démon répond ;
#   2. Compose lit docker-compose.yml (le bloc « configs: content: » demande la 2.23.1 au moins) ;
#   3. les images que la cible lance sont déjà présentes : « make up » passe --pull never, le
#      premier téléchargement est un geste à part (beko) ;
#   4. uv est installé.
# La liste des images vient de « docker compose config --images », qui résout les profils
# lui-même (Compose 5.1.4 sur le Mac : vérifié, la console n'y figure que sous --profile console).
# PHARMAFLUX_IMAGES remplace cette liste (noms séparés par des espaces) : pour montrer le refus
# d'une image absente sans toucher au fichier compose.
#
# Lectures seulement (info, config, image inspect) : aucun conteneur, volume ou réseau touché.

set -eu

profil=""
if [ "${1:-}" = "console" ]; then
    profil="--profile console"
elif [ -n "${1:-}" ]; then
    echo "usage : $0 [console]" >&2
    exit 2
fi

compose="docker compose -p pharmaflux"
echec=0

refus() {
    echo "prérequis manquant : $1" >&2
    echo "  → $2" >&2
    echec=1
}

if ! command -v docker >/dev/null 2>&1; then
    refus "docker introuvable" "installe Docker (sur le Mac : colima et le client docker)"
elif ! version=$(docker info --format '{{.ServerVersion}}' 2>/dev/null) || [ -z "$version" ]; then
    refus "le démon Docker ne répond pas" "lance-le (sur le Mac : colima start)"
else
    echo "docker : démon $version"
    # shellcheck disable=SC2086 # $profil est vide ou deux mots voulus séparés
    if ! $compose $profil config --quiet 2>/dev/null; then
        refus "Compose ne lit pas docker-compose.yml ($($compose version 2>/dev/null || echo 'version inconnue'))" \
            "mets Docker Compose à jour (2.23.1 au moins, pour le bloc « configs: content: »)"
    else
        echo "compose : $($compose version --short 2>/dev/null || echo ok)"
        # shellcheck disable=SC2086
        if [ -n "${PHARMAFLUX_IMAGES:-}" ]; then
            images="$PHARMAFLUX_IMAGES"
        elif ! images=$($compose $profil config --images 2>/dev/null); then
            # config --quiet vient de passer : un Compose qui ne connaît pas --images, par exemple
            refus "Compose ne liste pas les images (config --images)" \
                "mets Docker Compose à jour (2.23.1 au moins)"
            images=""
        fi
        for image in $images; do
            if docker image inspect "$image" >/dev/null 2>&1; then
                echo "image présente : $image"
            else
                refus "image absente : $image" \
                    "télécharge les images une fois : docker compose -p pharmaflux --profile console pull"
            fi
        done
    fi
fi

if command -v uv >/dev/null 2>&1; then
    echo "uv : $(uv --version 2>/dev/null || echo présent)"
else
    refus "uv introuvable" "installe uv : https://docs.astral.sh/uv/"
fi

if [ "$echec" -ne 0 ]; then
    echo "prérequis : NON" >&2
    exit 1
fi
echo "prérequis : OK"
