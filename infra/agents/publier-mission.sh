#!/bin/sh
# Publie une mission terminée (relecture CONFORME, feu vert final de l'IeC) :
# un seul push, une seule PR, donc une seule CI. Lancé par beko, depuis
# Terminal.app, dans le dossier principal pharmaflux/ :
#   sh infra/agents/publier-mission.sh 00-socle-et-archivage
# Description de la PR : docs/rapports/mission-NN/pr.md, écrite et committée
# par le codeur (première ligne « # … » = titre).

set -eu
[ $# -eq 1 ] || { echo "usage : sh infra/agents/publier-mission.sh NN-intitule" >&2; exit 1; }
if [ "${CLAUDECODE:-}" = "1" ] || [ "${CLAUDE_CODE_CHILD_SESSION:-}" = "1" ]; then
  echo "REFUS : à lancer par beko depuis Terminal.app, pas par un agent." >&2; exit 1
fi

PRINCIPAL=$(git rev-parse --show-toplevel)
CODEUR="$PRINCIPAL-codeur"
BRANCHE="mission-$1"
CORPS="docs/rapports/mission-${1%%-*}/pr.md"

[ "$(git -C "$CODEUR" branch --show-current)" = "$BRANCHE" ] \
  || { echo "REFUS : $CODEUR n'est pas sur $BRANCHE." >&2; exit 1; }
[ -z "$(git -C "$CODEUR" status --porcelain)" ] \
  || { echo "REFUS : modifications non committées dans $CODEUR." >&2; exit 1; }
git -C "$CODEUR" ls-files --error-unmatch "$CORPS" >/dev/null 2>&1 \
  || { echo "REFUS : $CORPS absent ou non committé." >&2; exit 1; }

TITRE=$(head -1 "$CODEUR/$CORPS" | sed 's/^# *//')
echo "Commits à publier :"
git -C "$CODEUR" log --oneline "main..$BRANCHE"
printf "Pousser %s et ouvrir la PR « %s » ? [o/N] " "$BRANCHE" "$TITRE"
read -r reponse
[ "$reponse" = "o" ] || { echo "Abandon."; exit 1; }

git -C "$CODEUR" push -u origin "$BRANCHE"
gh pr create --base main --head "$BRANCHE" --title "$TITRE" --body-file "$CODEUR/$CORPS"
echo
echo "CI lancée. Suivre :          gh pr checks $BRANCHE --watch"
echo "Après CI verte, fusionner :  gh pr merge $BRANCHE --merge --delete-branch && git pull --ff-only"
