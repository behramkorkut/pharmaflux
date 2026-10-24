#!/usr/bin/env python3
"""Garde-fou PreToolUse de Pharmaflux (crochet Claude Code).

Claude Code appelle ce script avant chaque appel d'outil Bash, Edit, Write,
MultiEdit ou NotebookEdit, avec l'appel en JSON sur l'entrée standard. Code
de sortie 2 : l'appel est refusé et le message (sortie d'erreur) est montré
à l'agent. Code 0 : l'appel passe ensuite par les permissions habituelles.

Le RÔLE se déduit du dossier où la session a été lancée
(CLAUDE_PROJECT_DIR), jamais d'une variable que l'agent pourrait poser :

- dépôt principal `pharmaflux/` (branche main) ............ iec
- worktree `pharmaflux-codeur/` (branche de mission) ...... codeur
- worktree `pharmaflux-relecteur/` (sommet figé) .......... relecteur
- tout autre dossier (autre worktree, hors git) ........... codeur
  (on retombe sur le rôle le plus contraint).

Ce crochet arrête les ACCIDENTS et les excès de zèle, pas un contournement
délibéré : les vraies barrières restent les crochets git
(`infra/git-hooks/`), la relecture et la validation de beko, seul à pousser.
Testé par `infra/agents/test_garde_fou.py`.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# Chemins réservés à l'IeC (relatifs à la racine du dépôt). Le codeur ne les
# écrit jamais ; docs/relectures/ est écrit par le relecteur et l'IeC, puis
# seulement committé par le codeur.
RESERVES = (
    "01_Specifications/",
    "CLAUDE.md",
    ".claude/",
    "infra/git-hooks/",
    "infra/agents/",
    "docs/agents/",
    "docs/missions/",
    "docs/relectures/",
)
RELECTURES = "docs/relectures/"

# Sous-commandes git en lecture seule, permises à tous les rôles.
GIT_LECTURE = {
    "status",
    "log",
    "diff",
    "show",
    "rev-parse",
    "ls-files",
    "blame",
    "grep",
    "shortlog",
    "describe",
    "cat-file",
    "merge-base",
    "rev-list",
}
# Commandes qui ne font que lire : elles peuvent nommer un chemin réservé.
LECTURE = {
    "cat",
    "head",
    "tail",
    "grep",
    "rg",
    "ls",
    "wc",
    "diff",
    "file",
    "stat",
    "sed",
    "echo",
    "printf",
    "test",
    "[",
    "realpath",
    "dirname",
    "basename",
    "cut",
    "tr",
    "sort",
    "uniq",
}
# awk n'y est pas : print > fichier et system() en font un outil d'écriture.
# Exécutions permises sous un chemin réservé : les tests des garde-fous.
TESTS_GARDE_FOUS = (
    ["sh", "infra/git-hooks/test-crochets.sh"],
    ["python3", "infra/agents/test_garde_fou.py"],
)
# Commandes système interdites à tous les agents (beko installe).
SYSTEME = {"launchctl", "crontab", "brew", "sudo", "su", "chmod", "chown"}
# Préfixes neutres devant une commande.
PREFIXES = {"command", "builtin", "exec", "nohup", "time", "noglob"}

# Filet sur la commande brute : git appelé ailleurs qu'en tête de segment
# (bash -c, xargs, eval…) pour une opération qui écrit.
GIT_ECRIT_BRUT = re.compile(
    r"(?<![\w./-])git\b[^\n|;&]*?\b(push|reset|rebase|checkout|merge|config|worktree|"
    r"stash|clean|restore|filter-branch|filter-repo|update-ref|symbolic-ref|"
    r"replace|notes|tag|cherry-pick|revert|am|apply|gc|prune|remote)\b"
)


class Refus(Exception):  # noqa: N818 (nom français voulu)
    """Appel refusé ; le message est montré à l'agent."""


# --------------------------------------------------------------------- rôle


def _git(dossier: Path, *args: str) -> str:
    sortie = subprocess.run(
        ["git", "-C", str(dossier), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return sortie.stdout.strip()


def determiner_role(*candidats: Path) -> tuple[str, Path, Path]:
    """Rend (rôle, racine du dossier de la session, racine du dépôt principal).

    Candidats dans l'ordre : CLAUDE_PROJECT_DIR, puis le dossier courant
    (seulement si le premier n'est pas dans git : session déplacée d'un
    dossier à l'autre). Aucun dans git : rôle codeur.
    """
    for dossier_projet in candidats:
        try:
            racine = Path(_git(dossier_projet, "rev-parse", "--show-toplevel")).resolve()
            commun = Path(
                _git(dossier_projet, "rev-parse", "--path-format=absolute", "--git-common-dir")
            ).resolve()
            break
        except (OSError, subprocess.SubprocessError):
            continue
    else:
        return "codeur", candidats[0].resolve(), candidats[0].resolve()
    principal = commun.parent
    if racine == principal:
        return "iec", racine, principal
    if racine == principal.with_name(principal.name + "-relecteur"):
        return "relecteur", racine, principal
    return "codeur", racine, principal


# ------------------------------------------------------------------ chemins


def chemin_relatif(chemin: Path, racine: Path) -> str | None:
    """Chemin relatif à la racine, ou None s'il est hors de la racine."""
    try:
        return chemin.resolve().relative_to(racine).as_posix()
    except ValueError:
        return None


def est_reserve(relatif: str) -> bool:
    return any(relatif == r.rstrip("/") or relatif.startswith(r) for r in RESERVES)


def mentionne_reserve(mot: str) -> bool:
    """Un mot de commande shell désigne-t-il un chemin réservé (aussi dans --option=chemin) ?"""
    mot = mot.strip("'\"")
    for r in RESERVES:
        nu = r.rstrip("/")
        if nu in mot and re.search(r"(^|[/=:])" + re.escape(nu) + r"(/|$)", mot):
            return True
    return False


def verifier_ecriture(role: str, cible: Path, racine: Path, principal: Path) -> None:
    if role == "iec":
        return
    if role == "relecteur":
        zone = principal.with_name(principal.name + "-codeur") / RELECTURES
        if chemin_relatif(cible, zone.resolve()) is None:
            raise Refus(
                f"le relecteur n'écrit que dans {zone}/ "
                "(sa relecture) ; il ne modifie jamais le code."
            )
        return
    relatif = chemin_relatif(cible, racine)
    if relatif is None:
        raise Refus(f"écriture hors du dossier du codeur ({racine}) : {cible}")
    if relatif == ".git" or relatif.startswith(".git/"):
        raise Refus("écriture dans .git interdite.")
    if est_reserve(relatif):
        raise Refus(
            f"« {relatif} » est réservé à l'IeC (consignes, ordres de mission, "
            "garde-fous, relectures). Propose la modification dans ton rapport."
        )


# --------------------------------------------------------------------- bash


def retirer_heredocs(commande: str) -> str:
    """Retire le corps des heredocs (message de commit, etc.)."""
    lignes = commande.split("\n")
    sortie: list[str] = []
    fin: str | None = None
    for ligne in lignes:
        if fin is not None:
            if ligne.strip() == fin:
                fin = None
            continue
        sortie.append(ligne)
        m = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", ligne)
        if m:
            fin = m.group(1)
    return "\n".join(sortie)


# Jetons qui séparent deux commandes, et redirections (le jeton suivant est
# leur cible ; seules celles en écriture comptent).
SEPARATEURS = {"|", "||", "&", "&&", ";", ";;", "|&", "(", ")", "`", "{", "}"}
REDIRECTIONS_ECRITURE = {">", ">>", ">|", "&>", "&>>"}
REDIRECTIONS_AUTRES = {"<", "<<", "<<<", ">&", "<&", "<>"}


def _jetons(ligne: str) -> list[str]:
    """Découpe une ligne en mots et opérateurs, en respectant les guillemets
    (un « | » dans un motif grep -E entre guillemets n'est pas un tube)."""
    lexeur = shlex.shlex(ligne, posix=True, punctuation_chars="();<>|&`")
    lexeur.whitespace_split = True
    lexeur.commenters = ""
    try:
        return list(lexeur)
    except ValueError:  # guillemet non fermé : découpage grossier
        return ligne.split()


def segments(commande: str) -> list[tuple[list[str], list[str]]]:
    """Rend, pour chaque commande simple : (mots, cibles des redirections en écriture)."""
    resultat: list[tuple[list[str], list[str]]] = []
    for ligne in commande.split("\n"):
        mots: list[str] = []
        cibles: list[str] = []
        jetons = _jetons(ligne)
        i = 0
        while i <= len(jetons):
            jeton = jetons[i] if i < len(jetons) else ";"
            if jeton in SEPARATEURS:
                while mots and (
                    re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", mots[0]) or mots[0] in PREFIXES
                ):
                    mots = mots[1:]
                if mots or cibles:
                    resultat.append((mots or ["(redirection)"], cibles))
                mots, cibles = [], []
            elif jeton in REDIRECTIONS_ECRITURE or jeton in REDIRECTIONS_AUTRES:
                if mots and mots[-1].isdigit():
                    mots.pop()  # descripteur : « 2>&1 »
                if i + 1 < len(jetons) and jeton in REDIRECTIONS_ECRITURE:
                    cibles.append(jetons[i + 1])
                i += 1  # saute la cible
            else:
                mots.append(jeton)
            i += 1
    return resultat


def verifier_git(role: str, mots: list[str]) -> None:
    args = mots[1:]
    while args and args[0] in ("--no-pager", "-P"):
        args = args[1:]
    if not args:
        return
    if args[0].startswith("-"):
        raise Refus(f"option globale git interdite : {args[0]} (-C, -c, --git-dir…).")
    sous, reste = args[0], args[1:]
    if sous in GIT_LECTURE:
        return
    if sous == "branch" and all(
        a in ("--show-current", "--list", "-v", "-vv", "-a") for a in reste
    ):
        return
    if sous == "worktree" and reste[:1] == ["list"]:
        return
    if role == "relecteur" and sous == "switch" and reste[:1] == ["--detach"] and len(reste) == 2:
        return
    if role == "codeur" and sous == "add":
        for a in reste:
            if a in ("-A", "--all", ".", "-u", "--update", "*", ":/") or a.startswith("-"):
                raise Refus(f"git add {a} interdit : ajoute des fichiers précis.")
            if mentionne_reserve(a) and RELECTURES.rstrip("/") not in a:
                raise Refus(f"git add {a} : chemin réservé à l'IeC.")
        return
    if role == "codeur" and sous == "commit":
        for a in reste:
            if a in (
                "--amend",
                "-a",
                "--all",
                "-am",
                "--no-verify",
                "-n",
                "--fixup",
                "--squash",
            ) or a.startswith(("--fixup", "--squash", "--author")):
                raise Refus(
                    f"git commit {a} interdit (un commit par palier, jamais de réécriture)."
                )
        return
    if sous == "push":
        raise Refus("aucun agent ne pousse : beko seul pousse, ouvre la PR et fusionne.")
    raise Refus(
        f"git {sous} n'est pas permis au rôle {role}. "
        + (
            "Le codeur committe en local ; tout le reste de git est à beko."
            if role == "codeur"
            else "Ce rôle ne fait que lire git ; beko fait le reste."
        )
    )


def ecrit_par_option(mots: list[str]) -> bool:
    """Une commande de LECTURE qui écrit quand même : sed -i, sort -o, uniq ENTREE SORTIE."""
    tete, args = mots[0], mots[1:]
    if tete == "sed":
        return any(a.startswith("-i") or a == "--in-place" for a in args)
    if tete == "sort":
        return any(a.startswith(("-o", "--output")) for a in args)
    if tete == "uniq":
        return len([a for a in args if not a.startswith("-")]) > 1
    return False


def verifier_bash(role: str, commande: str) -> None:
    nette = retirer_heredocs(commande)
    for mots, cibles in segments(nette):
        tete = Path(mots[0]).name
        # Filet : git caché derrière bash -c, xargs, eval…
        if tete != "git" and tete not in LECTURE:
            cache = GIT_ECRIT_BRUT.search(" ".join(mots[1:]))
            if cache:
                raise Refus(f"opération git « {cache.group(1)} » interdite aux agents.")
        if tete in SYSTEME:
            raise Refus(
                f"« {tete} » touche au système : beko s'en charge (CLAUDE.md, « Système »)."
            )
        if tete == "env" and any(
            a.startswith(("-u", "--unset", "-i", "--ignore")) for a in mots[1:]
        ):
            raise Refus("env -u / -i interdit devant une commande.")
        if tete == "unset" and any("CLAUDE" in a for a in mots[1:]):
            raise Refus("unset d'une variable CLAUDE* interdit.")
        if tete == "git":
            verifier_git(role, mots)
            continue
        if tete == "gh":
            if (
                role == "iec"
                and mots[1:3]
                and (
                    (mots[1] == "pr" and mots[2] in ("view", "checks", "list", "diff"))
                    or (mots[1] == "run" and mots[2] in ("list", "view"))
                )
            ):
                continue
            raise Refus("gh est réservé à beko (PR, dépôt, CI).")
        if role == "iec":
            continue
        ecrit_reserve = any(mentionne_reserve(c) for c in cibles)
        if not ecrit_reserve and any(
            mots[: len(t)] == t and all(a.startswith("-") for a in mots[len(t) :])
            for t in TESTS_GARDE_FOUS
        ):
            continue
        # Codeur et relecteur : pas d'écriture shell vers un chemin réservé.
        if not ecrit_reserve and not any(mentionne_reserve(a) for a in mots[1:]):
            continue
        lecture_pure = tete in LECTURE and not ecrit_reserve and not ecrit_par_option(mots)
        if not lecture_pure:
            raise Refus(
                f"« {tete} » sur un chemin réservé à l'IeC : en lecture seulement "
                "(cat, head, grep, sed -n…)."
            )


# --------------------------------------------------------------------- main


def juger(appel: dict, dossier_projet: Path) -> None:
    role, racine, principal = determiner_role(
        dossier_projet, Path(appel.get("cwd") or dossier_projet)
    )
    outil = appel.get("tool_name", "")
    entree = appel.get("tool_input") or {}
    # Le terminal de l'application et le pilotage d'écran tournent hors de
    # Claude Code (sans CLAUDECODE) : ils échapperaient aux crochets git.
    if role != "iec" and re.match(r"mcp__(terminal|computer-use|claude-in-chrome)__", outil):
        raise Refus(f"outil « {outil} » réservé : il contourne les garde-fous de ton rôle.")
    if outil == "Bash":
        verifier_bash(role, str(entree.get("command", "")))
        return
    if outil in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        brut = entree.get("file_path") or entree.get("notebook_path") or ""
        cible = Path(brut)
        if not cible.is_absolute():
            cible = Path(appel.get("cwd") or dossier_projet) / cible
        verifier_ecriture(role, cible, racine, principal)


def main() -> int:
    try:
        appel = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("garde-fou : entrée illisible, appel refusé.", file=sys.stderr)
        return 2
    dossier = Path(os.environ.get("CLAUDE_PROJECT_DIR") or appel.get("cwd") or ".")
    if not dossier.is_dir():
        dossier = Path(appel.get("cwd") or ".")
    try:
        juger(appel, dossier)
    except Refus as refus:
        print(
            f"garde-fou Pharmaflux : REFUS — {refus} "
            "Si c'est nécessaire, signale-le à beko ; ne contourne pas.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
