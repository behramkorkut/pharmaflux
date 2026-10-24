#!/bin/sh
# Prépare une mission : branche depuis main, dossiers du codeur et du
# relecteur (worktrees git). Lancé par beko, depuis Terminal.app, dans le
# dossier principal pharmaflux/ :
#   sh infra/agents/preparer-mission.sh 00-socle-et-archivage
# Refuse si un dossier d'agent a des modifications non committées.

set -eu
[ $# -eq 1 ] || { echo "usage : sh infra/agents/preparer-mission.sh NN-intitule" >&2; exit 1; }
if [ "${CLAUDECODE:-}" = "1" ] || [ "${CLAUDE_CODE_CHILD_SESSION:-}" = "1" ]; then
  echo "REFUS : à lancer par beko depuis Terminal.app, pas par un agent." >&2; exit 1
fi

PRINCIPAL=$(git rev-parse --show-toplevel)
[ "$PRINCIPAL" = "$(cd "$(git rev-parse --git-common-dir)/.." && pwd)" ] \
  || { echo "REFUS : lancer depuis le dossier principal pharmaflux/." >&2; exit 1; }
cd "$PRINCIPAL"
[ "$(git branch --show-current)" = "main" ] || { echo "REFUS : le dossier principal doit être sur main." >&2; exit 1; }

NUMERO=${1%%-*}
BRANCHE="mission-$1"
CODEUR="$PRINCIPAL-codeur"
RELECTEUR="$PRINCIPAL-relecteur"

git config core.hooksPath infra/git-hooks
if git remote get-url origin >/dev/null 2>&1; then git pull --ff-only --quiet; fi

if git show-ref --verify --quiet "refs/heads/$BRANCHE"; then
  echo "La branche $BRANCHE existe déjà : on la reprend."
else
  git branch "$BRANCHE" main
fi

propre() {
  [ -z "$(git -C "$1" status --porcelain)" ] \
    || { echo "REFUS : $1 a des modifications non committées." >&2; exit 1; }
}

if [ -d "$CODEUR" ]; then
  propre "$CODEUR"; git -C "$CODEUR" switch --quiet "$BRANCHE"
else
  git worktree add --quiet "$CODEUR" "$BRANCHE"
fi
if [ -d "$RELECTEUR" ]; then
  propre "$RELECTEUR"; git -C "$RELECTEUR" switch --quiet --detach "$BRANCHE"
else
  git worktree add --quiet --detach "$RELECTEUR" "$BRANCHE"
fi
mkdir -p "$CODEUR/docs/relectures/mission-$NUMERO" "$CODEUR/docs/rapports/mission-$NUMERO"

echo
echo "Mission prête : branche $BRANCHE"
git worktree list
echo
echo "Codeur    : session Claude Code dans $CODEUR"
echo "Relecteur : session neuve dans $RELECTEUR, commande /relire-mission $NUMERO"
