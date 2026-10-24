#!/bin/sh
# Test des crochets git de Pharmaflux, dans un dépôt jetable : rien n'est
# poussé, rien n'est modifié dans le vrai dépôt. Lancement :
#   sh infra/git-hooks/test-crochets.sh
# Sortie 0 si tous les cas donnent le résultat attendu.

set -u
CROCHETS=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echecs=0

# beko : aucune variable Claude Code ; agent : CLAUDECODE=1.
beko() { env -u CLAUDECODE -u CLAUDE_CODE_CHILD_SESSION "$@"; }
agent() { env CLAUDECODE=1 "$@"; }

attendu() { # attendu <ok|refus> <libellé> <commande…>
  verdict=$1; libelle=$2; shift 2
  if "$@" >/dev/null 2>&1; then obtenu=ok; else obtenu=refus; fi
  if [ "$obtenu" = "$verdict" ]; then
    echo "  ok   $libelle"
  else
    echo "  ÉCHEC $libelle (attendu $verdict, obtenu $obtenu)"
    echecs=$((echecs + 1))
  fi
}

cd "$TMP" || exit 1
beko git init -q -b main
beko git config user.email test@example.invalid
beko git config user.name test
beko git config core.hooksPath "$CROCHETS"
echo a > a.txt && beko git add a.txt && beko git commit -qm init

TRAILERS='

Commis-par: codeur
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>'

echo "pre-commit / commit-msg"
echo b > b.txt; beko git add b.txt
attendu refus "agent sur main" agent git commit -qm "x$TRAILERS"
attendu ok    "beko sur main"  beko git commit -qm "beko"
beko git switch -qc mission-00-essai
echo c > c.txt; beko git add c.txt
attendu refus "agent sans trailers" agent git commit -qm "sans"
attendu ok    "agent sur sa branche avec trailers" agent git commit -qm "palier$TRAILERS"
echo regle > CLAUDE.md; beko git add CLAUDE.md
attendu refus "agent touche CLAUDE.md" agent git commit -qm "x$TRAILERS"
beko git reset -q CLAUDE.md
mkdir -p docs/relectures; echo r > docs/relectures/r.md; beko git add docs/relectures/r.md
attendu ok    "agent committe une relecture" agent git commit -qm "relecture$TRAILERS"
beko git switch -q --detach HEAD
echo d > d.txt; beko git add d.txt
attendu refus "agent sur HEAD détachée" agent git commit -qm "x$TRAILERS"
beko git switch -q mission-00-essai

echo "pre-push"
TETE=$(git rev-parse HEAD); AVANT=$(git rev-parse HEAD~1); ZERO=0000000000000000000000000000000000000000
pousse() { # pousse <qui> <ligne stdin>
  qui=$1; ligne=$2
  printf '%s\n' "$ligne" | $qui sh "$CROCHETS/pre-push" origin https://exemple.invalid/depot.git
}
attendu refus "agent pousse sa branche" pousse agent "refs/heads/m $TETE refs/heads/m $ZERO"
attendu ok    "beko pousse une branche neuve" pousse beko "refs/heads/m $TETE refs/heads/m $ZERO"
attendu ok    "beko pousse en avance rapide" pousse beko "refs/heads/m $TETE refs/heads/m $AVANT"
attendu refus "beko pousse en forcé" pousse beko "refs/heads/m $AVANT refs/heads/m $TETE"
attendu refus "beko supprime une branche distante" pousse beko "(delete) $ZERO refs/heads/m $TETE"

if [ "$echecs" -eq 0 ]; then echo "crochets git : tout est conforme"; else echo "crochets git : $echecs échec(s)"; fi
[ "$echecs" -eq 0 ]
