"""Test du garde-fou Claude Code (.claude/hooks/garde_fou.py).

Construit un dépôt jetable avec les trois dossiers du circuit (principal,
-codeur, -relecteur), puis joue des appels d'outils simulés et vérifie la
décision du crochet. Bibliothèque standard seulement. Lancement :
    python3 infra/agents/test_garde_fou.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CROCHET = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "garde_fou.py"
SANS_CLAUDE = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}


def git(dossier: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(dossier), *args], check=True, capture_output=True, env=SANS_CLAUDE
    )


class GardeFou(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name).resolve()
        cls.principal = base / "pharmaflux"
        cls.codeur = base / "pharmaflux-codeur"
        cls.relecteur = base / "pharmaflux-relecteur"
        cls.autre = base / "ailleurs"
        cls.principal.mkdir()
        git(cls.principal, "init", "-q", "-b", "main")
        git(
            cls.principal,
            "-c",
            "user.email=t@e.invalid",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        )
        git(
            cls.principal,
            "worktree",
            "add",
            "-q",
            "-b",
            "mission-00-essai",
            str(cls.codeur),
            "main",
        )
        git(
            cls.principal,
            "worktree",
            "add",
            "-q",
            "--detach",
            str(cls.relecteur),
            "mission-00-essai",
        )
        git(cls.principal, "worktree", "add", "-q", "--detach", str(cls.autre), "main")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def juger(self, dossier: Path, outil: str, **entree: str) -> bool:
        """True si l'appel passe, False s'il est refusé (code 2)."""
        appel = {"tool_name": outil, "tool_input": entree, "cwd": str(dossier)}
        env = dict(SANS_CLAUDE, CLAUDE_PROJECT_DIR=str(dossier))
        sortie = subprocess.run(
            [sys.executable, "-I", str(CROCHET)],
            input=json.dumps(appel),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertIn(sortie.returncode, (0, 2), sortie.stderr)
        return sortie.returncode == 0

    def bash(self, dossier: Path, commande: str) -> bool:
        return self.juger(dossier, "Bash", command=commande)

    def ecrit(self, dossier: Path, chemin: Path | str) -> bool:
        return self.juger(dossier, "Write", file_path=str(chemin), content="x")

    # ------------------------------------------------------------- codeur

    def test_codeur_ecrit_son_code(self) -> None:
        self.assertTrue(self.ecrit(self.codeur, self.codeur / "src/pharmaflux/cli.py"))
        self.assertTrue(self.ecrit(self.codeur, "docs/rapports/mission-00/palier-1.md"))
        self.assertTrue(self.ecrit(self.codeur, self.codeur / ".github/workflows/ci.yml"))

    def test_codeur_ne_touche_pas_aux_reserves(self) -> None:
        for chemin in (
            "CLAUDE.md",
            ".claude/settings.json",
            ".claude/hooks/garde_fou.py",
            "01_Specifications/PRD.md",
            "infra/git-hooks/pre-push",
            "docs/missions/mission-00.md",
            "docs/agents/processus.md",
            "docs/relectures/mission-00/relecture-1.md",
            "src/../CLAUDE.md",
        ):
            with self.subTest(chemin=chemin):
                self.assertFalse(self.ecrit(self.codeur, self.codeur / chemin))

    def test_codeur_n_ecrit_pas_hors_de_son_dossier(self) -> None:
        self.assertFalse(self.ecrit(self.codeur, self.principal / "src/x.py"))
        self.assertFalse(self.ecrit(self.codeur, Path.home() / ".zshrc"))
        self.assertFalse(self.ecrit(self.codeur, self.codeur / ".git"))

    def test_codeur_git_permis(self) -> None:
        for commande in (
            "git status --short",
            "git log --oneline -5",
            "git diff --stat main...HEAD",
            "git add src/pharmaflux/cli.py tests/test_cli.py",
            "git add docs/relectures/mission-00/relecture-1.md",
            "git commit -F - <<'FIN'\nfeat(m00): palier 1\n\ngit push et CLAUDE.md cités\n"
            "\nCommis-par: codeur\nFIN",
            "git show main:docs/missions/mission-00.md | head -50",
            "git ls-tree --name-only main docs/missions/",
            "git check-ignore -v data/bronze/x.gz",
            "uv run pytest -q 2>&1 | tail -25",
            "cat CLAUDE.md",
            "grep -n push docs/agents/processus.md",
            "sed -n 1,40p CLAUDE.md",
            "sh infra/git-hooks/test-crochets.sh 2>&1 | tail -3",
            "python3 infra/agents/test_garde_fou.py -v 2>&1 | tail -5",
        ):
            with self.subTest(commande=commande):
                self.assertTrue(self.bash(self.codeur, commande))

    def test_faux_positifs_signales_au_paragraphe_0(self) -> None:
        """Mission 00, §0 H.1 : refusées à tort par la première version."""
        for commande in (
            'git status --short && git log --oneline -5 && echo "--- main vs branche ---" '
            "&& git log --oneline main -3 && find . -path ./.git -prune -o -path ./data -prune "
            "-o -type f -print | grep -v '/\\.git/' | sort | head -80 && ls -la",
            'grep -n -i -E "prune|curl|wget|httpx|reseau|MOTIFS|interdit|def '
            're\\.compile|\\bgit\\b" '
            ".claude/hooks/garde_fou.py | head -80",
            "grep -n -i -E 'trailer|Commis|Co-Authored|reserv|RESERV|refus|main|HEAD' "
            "infra/git-hooks/pre-commit | head -30",
            "grep -c 'a;b' CLAUDE.md",
            "cat CLAUDE.md > /tmp/copie.md",
        ):
            with self.subTest(commande=commande):
                self.assertTrue(self.bash(self.codeur, commande))
                self.assertTrue(self.bash(self.relecteur, commande))

    def test_lecture_par_cut_tr_sort_uniq(self) -> None:
        """Palier 1 de la mission 00 : outils de lecture ajoutés, awk reste refusé."""
        permises = (
            "cut -d: -f1 CLAUDE.md",
            "tr a-z A-Z < CLAUDE.md",
            "sort docs/missions/m.md",
            "uniq -c docs/missions/m.md",
            "sort CLAUDE.md | uniq -c | head",
        )
        refusees = (
            "sort -o CLAUDE.md CLAUDE.md",
            "sort --output=docs/missions/m.md x",
            "uniq docs/missions/m.md CLAUDE.md",
            "awk '/x/{p=1} p' docs/missions/m.md",
            "cp x --target-directory=docs/missions/",
        )
        for commande in permises:
            with self.subTest(commande=commande):
                self.assertTrue(self.bash(self.codeur, commande))
        for commande in refusees:
            with self.subTest(commande=commande):
                self.assertFalse(self.bash(self.codeur, commande))

    def test_codeur_git_interdit(self) -> None:
        for commande in (
            "git push",
            "git push -u origin mission-00-essai",
            "git add -A",
            "git add .",
            "git add CLAUDE.md",
            "git commit --amend -m x",
            "git commit -am x",
            "git commit --no-verify -m x",
            "git reset --hard",
            "git checkout main",
            "git switch main",
            "git config core.hooksPath /dev/null",
            "git -C ../pharmaflux log",
            "git -c core.hooksPath=/dev/null commit -m x",
            "git stash",
            "git rebase main",
            "git worktree add ../x",
            "cd src && git push",
            "bash -c 'git push'",
            "echo ok; git reset --hard HEAD~1",
            "xargs git checkout < liste.txt",
            "env -u CLAUDECODE git commit -m x",
            "unset CLAUDECODE",
            "gh pr create --draft",
            "gh repo view",
        ):
            with self.subTest(commande=commande):
                self.assertFalse(self.bash(self.codeur, commande))

    def test_codeur_pas_d_ecriture_shell_sur_les_reserves(self) -> None:
        for commande in (
            "echo x > CLAUDE.md",
            "echo x >> docs/missions/m.md",
            "sed -i '' s/a/b/ CLAUDE.md",
            "rm -rf .claude",
            "cp /tmp/x .claude/settings.json",
            "mv a infra/git-hooks/pre-push",
            "tee docs/relectures/r.md < x",
            'python3 -c \'open("CLAUDE.md","w")\' CLAUDE.md',
            "sh infra/git-hooks/test-crochets.sh > infra/git-hooks/pre-push",
            "cat x 2>&1 >CLAUDE.md",
            "echo x|tee -a docs/missions/m.md",
            "printf x >| CLAUDE.md",
            "echo $(git push)",
            "echo `git reset --hard`",
            "(cd src; git push)",
            "python3 infra/agents/test_garde_fou.py CLAUDE.md",
        ):
            with self.subTest(commande=commande):
                self.assertFalse(self.bash(self.codeur, commande))

    def test_codeur_systeme_interdit(self) -> None:
        for commande in ("launchctl load x.plist", "crontab -l", "brew install jq", "sudo ls"):
            with self.subTest(commande=commande):
                self.assertFalse(self.bash(self.codeur, commande))

    def test_terminal_et_ecran_interdits_aux_agents(self) -> None:
        for outil in (
            "mcp__terminal__run_in_terminal",
            "mcp__computer-use__app_type",
            "mcp__claude-in-chrome__computer",
        ):
            with self.subTest(outil=outil):
                self.assertFalse(self.juger(self.codeur, outil, command="git push"))
                self.assertFalse(self.juger(self.relecteur, outil, command="git push"))
        self.assertTrue(self.juger(self.principal, "mcp__terminal__run_in_terminal", command="ls"))

    def test_dossier_inconnu_traite_comme_codeur(self) -> None:
        self.assertFalse(self.ecrit(self.autre, self.autre / "CLAUDE.md"))
        self.assertFalse(self.bash(self.autre, "git push"))

    def test_session_deplacee_juge_sur_le_dossier_courant(self) -> None:
        """CLAUDE_PROJECT_DIR hors git : le rôle vient du dossier courant."""
        hors_git = Path(self._tmp.name) / "hors-git"
        hors_git.mkdir(exist_ok=True)
        appel = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}

        def code(cwd: Path) -> int:
            env = dict(SANS_CLAUDE, CLAUDE_PROJECT_DIR=str(hors_git))
            return subprocess.run(
                [sys.executable, "-I", str(CROCHET)],
                input=json.dumps(dict(appel, cwd=str(cwd))),
                capture_output=True,
                text=True,
                env=env,
            ).returncode

        self.assertEqual(code(self.codeur), 0)  # codeur : commit permis
        self.assertEqual(code(self.principal), 2)  # IeC : pas de commit
        self.assertEqual(code(hors_git), 0)  # hors git : rôle codeur
        sortie = subprocess.run(
            [sys.executable, "-I", str(CROCHET)],
            input=json.dumps(
                {
                    "tool_name": "Write",
                    "cwd": str(hors_git),
                    "tool_input": {"file_path": str(self.principal / "CLAUDE.md")},
                }
            ),
            capture_output=True,
            text=True,
            env=dict(SANS_CLAUDE, CLAUDE_PROJECT_DIR=str(hors_git)),
        )
        self.assertEqual(sortie.returncode, 2)  # hors git : pas d'écriture ailleurs

    # ----------------------------------------------------------- relecteur

    def test_relecteur_ecrit_seulement_sa_relecture(self) -> None:
        self.assertTrue(
            self.ecrit(self.relecteur, self.codeur / "docs/relectures/mission-00/relecture-1.md")
        )
        self.assertFalse(self.ecrit(self.relecteur, self.relecteur / "src/x.py"))
        self.assertFalse(self.ecrit(self.relecteur, self.codeur / "src/x.py"))
        self.assertFalse(self.ecrit(self.relecteur, self.principal / "docs/relectures/r.md"))

    def test_relecteur_git(self) -> None:
        self.assertTrue(self.bash(self.relecteur, "git switch --detach mission-00-essai"))
        self.assertTrue(self.bash(self.relecteur, "git diff --stat main...HEAD"))
        self.assertTrue(self.bash(self.relecteur, "uv run pytest -q 2>&1 | tail -25"))
        for commande in (
            "git add x",
            "git commit -m x",
            "git switch main",
            "git push",
            "gh pr comment 1 -b x",
        ):
            with self.subTest(commande=commande):
                self.assertFalse(self.bash(self.relecteur, commande))

    # ----------------------------------------------------------------- IeC

    def test_iec_ecrit_partout_mais_ne_touche_pas_a_git(self) -> None:
        self.assertTrue(self.ecrit(self.principal, self.principal / "CLAUDE.md"))
        self.assertTrue(self.ecrit(self.principal, self.principal / "docs/missions/m01.md"))
        self.assertTrue(
            self.ecrit(self.principal, self.codeur / "docs/relectures/mission-00/controle-iec-1.md")
        )
        self.assertTrue(self.bash(self.principal, "git log --oneline main..mission-00-essai"))
        self.assertTrue(self.bash(self.principal, "gh pr checks 3"))
        for commande in (
            "git add CLAUDE.md",
            "git commit -m x",
            "git push",
            "git worktree add ../x",
            "gh pr merge 3",
        ):
            with self.subTest(commande=commande):
                self.assertFalse(self.bash(self.principal, commande))


if __name__ == "__main__":
    unittest.main()
