# Fonctions partagées par les crochets git de Pharmaflux (sourcé, pas exécuté).

# Claude Code pose l'une de ces variables dans toutes les commandes qu'il
# lance ; Terminal.app (beko) n'en pose aucune. Aucune variable de
# contournement : un agent pourrait la poser aussi.
sous_claude_code() {
  [ "${CLAUDE_CODE_CHILD_SESSION:-}" = "1" ] || [ "${CLAUDECODE:-}" = "1" ]
}

refus() {
  echo "$NOM_CROCHET : REFUS — $1" >&2
  exit 1
}

# Chemins réservés à l'IeC (committés sur main par beko). docs/relectures/
# n'y figure pas : le codeur committe les relectures sur sa branche.
RESERVES_RE='^(01_Specifications/|CLAUDE\.md$|\.claude/|infra/git-hooks/|infra/agents/|docs/agents/|docs/missions/)'
