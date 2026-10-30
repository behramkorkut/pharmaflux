#!/bin/sh
# Lance une commande de l'assistant avec la clé de l'API Claude (mission 08).
# La clé vit dans le trousseau macOS de beko, jamais dans un fichier, jamais
# dans l'environnement de sa session : elle n'est donnée qu'au processus lancé
# ici. Lancé par beko seul, depuis Terminal.app, dans un dossier du projet :
#   sh infra/agents/avec-cle.sh uv run pharmaflux assistant demander "…"
# Mise dans le trousseau, une fois (la clé est demandée, rien dans l'historique) :
#   security add-generic-password -a "$USER" -s pharmaflux-anthropic -w

set -eu
[ $# -ge 1 ] || { echo "usage : sh infra/agents/avec-cle.sh <commande> [arguments…]" >&2; exit 1; }
if [ "${CLAUDECODE:-}" = "1" ] || [ "${CLAUDE_CODE_CHILD_SESSION:-}" = "1" ]; then
  echo "REFUS : à lancer par beko depuis Terminal.app, pas par un agent." >&2; exit 1
fi

ANTHROPIC_API_KEY=$(security find-generic-password -a "$USER" -s pharmaflux-anthropic -w 2>/dev/null) \
  || { echo "REFUS : clé absente du trousseau (service pharmaflux-anthropic)." >&2; exit 2; }
export ANTHROPIC_API_KEY
exec "$@"
