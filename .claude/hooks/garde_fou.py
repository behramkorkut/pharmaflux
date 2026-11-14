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
    "ls-tree",
    "check-ignore",
    "count-objects",
}
# git fetch, pour l'IeC seulement : rafraîchir les références distantes (refs/remotes,
# FETCH_HEAD) et lire l'état de GitHub. Ni refspec (« main:main » écrirait une branche
# locale), ni --upload-pack (exécute une commande), ni --tags (écrit les étiquettes locales).
GIT_FETCH_IEC = {"origin", "--prune", "-p", "--quiet", "-q"}
# git ls-remote, pour l'IeC seulement : relever l'empreinte d'une étiquette à épingler (une
# action de la CI). Il lit et n'écrit rien en local ; --upload-pack exécuterait une commande.
GIT_LS_REMOTE_OPTIONS = {"--tags", "--heads", "--refs", "-t", "-h", "-q", "--quiet"}
# Les outils d'un connecteur GitHub : l'IeC n'en lit que ce qui commence ainsi.
MCP_GITHUB_LECTURE = ("get", "list", "search", "read", "view")
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
    "which",
    "whereis",
    "type",
    "find",
}
# Actions de find qui écrivent (-delete, -fprint…) ou lancent une autre commande (-exec, -ok).
FIND_ECRIT = ("-delete", "-fprint", "-fls")
FIND_EXECUTE = ("-exec", "-ok")
# awk n'y est pas : print > fichier et system() en font un outil d'écriture.
# Exécutions permises sous un chemin réservé : les tests des garde-fous.
TESTS_GARDE_FOUS = (
    ["sh", "infra/git-hooks/test-crochets.sh"],
    ["python3", "infra/agents/test_garde_fou.py"],
)
# Commandes système interdites à tous les agents (beko installe).
SYSTEME = {"launchctl", "crontab", "brew", "sudo", "su", "chmod", "chown", "security"}
# La clé de l'API Claude (mission 08) : dans le trousseau de beko, lue par avec-cle.sh, que
# beko seul lance. Aucun agent ne la lit, même cachée derrière bash -c, xargs ou eval.
CLE_BRUT = re.compile(r"\bsecurity\s+(find|dump|export)-|\bavec-cle\.sh\b")
# make, pour tous les rôles (mission 04) : ses recettes échappent au garde-fou
# (docker compris). Les agents l'appellent en simulation, qui affiche les
# commandes sans les lancer ; make <cible> est à beko et à la CI.
MAKE_SIMULATION = {"-n", "--dry-run", "--just-print", "--recon"}
# make --version (ou -v), seul, affiche la version sans lire de Makefile.
MAKE_VERSION = (["--version"], ["-v"])
# Lanceurs qui exécutent leurs arguments (mission 10, signalé par le codeur) :
# « /usr/bin/time -l make index » ou « uv run make index » ne doivent pas passer
# là où « make index » est refusé.
LANCEURS = {
    "time",
    "nice",
    "timeout",
    "env",
    "xargs",
    "caffeinate",
    "stdbuf",
    "nohup",
    "ionice",
    "taskset",
    "watch",
    "flock",
}
# docker, pour tous les rôles (mission 03) : le colima de beko fait aussi
# tourner les conteneurs d'Alamel. Hors compose, docker ne fait que lire ;
# compose ne vise que le projet pharmaflux et ne télécharge aucune image
# (le premier pull est à beko).
PROJET_COMPOSE = "pharmaflux"
DOCKER_LECTURE = {"ps", "version", "info", "images", "--version", "-v", "--help"}
COMPOSE_SANS_PROJET = {"ls", "version"}
COMPOSE_PERMIS = {
    "up",
    "down",
    "ps",
    "logs",
    "config",
    "start",
    "stop",
    "restart",
    "exec",
    "port",
    "top",
    "images",
    "rm",
    "wait",
    "create",
    "run",
}
COMPOSE_PULL_INTERDIT = {"up", "create", "run"}  # téléchargent une image absente
COMPOSE_OPTIONS_A_VALEUR = {
    "-p",
    "--project-name",
    "-f",
    "--file",
    "--project-directory",
    "--env-file",
    "--profile",
    "--ansi",
    "--progress",
    "--parallel",
}
COLIMA_LECTURE = {"list", "status", "version"}
# Préfixes neutres devant une commande, et mots-clés du shell qui introduisent
# la commande suivante (« do cat … » est jugé comme « cat … »).
PREFIXES = {"command", "builtin", "exec", "nohup", "time", "noglob"}
MOTS_CLES = {"do", "then", "else", "elif", "if", "while", "until", "!"}

# Filet sur la commande brute : git appelé ailleurs qu'en tête de segment
# (bash -c, xargs, eval…) pour une opération qui écrit.
GIT_ECRIT_BRUT = re.compile(
    r"(?<![\w./-])git\b[^\n|;&]*?\b(push|reset|rebase|checkout|merge|config|worktree|"
    r"stash|clean|restore|filter-branch|filter-repo|update-ref|symbolic-ref|"
    r"replace|notes|tag|cherry-pick|revert|am|apply|gc|prune|remote)\b"
)
# Filet : docker ou colima appelés ailleurs qu'en tête de segment.
CONTENEURS_BRUT = re.compile(r"(?<![\w./-])(docker(-compose)?|colima)(?![\w.-])")

# Le VPS-1 (mission 10, infra/agents/vps/README.md) : un seul alias, celui du compte du
# codeur, sans sudo ni docker ; jamais vps1, qui ouvre le compte root de beko. Ce filtre
# n'arrête que les accidents : la barrière est sur le VPS (droits Unix, polkit à liste
# exacte, filtre de sortie) et sur le Mac (la clé de vps1 sous phrase de passe).
ALIAS_VPS = "pharmaflux-vps"
OUTILS_SSH = {
    "ssh",
    "scp",
    "sftp",
    "rsync",
    "sshfs",
    "mosh",
    "autossh",
    "ssh-copy-id",
    "ssh-add",
    "ssh-agent",
    "ssh-keygen",
    "ssh-keyscan",
}
# Options qui ne changent ni le compte, ni la clé, ni les renvois de l'alias.
SSH_OPTIONS_PERMISES = {"-q", "-T", "-n", "-x", "-a"}
# Filet : ssh appelé ailleurs qu'en tête de segment (bash -c, xargs, timeout, une variable).
SSH_BRUT = re.compile(r"(?<![\w./-])(ssh|scp|sftp|rsync|sshfs|mosh|autossh)(?![\w.-])")
# Un mot qui nomme ~/.ssh : les clés et la configuration de beko, jamais lues par un agent.
DOSSIER_SSH = re.compile(r"(^|/)\.ssh(/|$)")
# Sur le VPS : ce qui donnerait root, toucherait au système ou survivrait à la commande.
DISTANT_INTERDIT = (
    SYSTEME
    | {
        "doas",
        "pkexec",
        "run0",
        "systemd-run",
        "machinectl",
        "nsenter",
        "unshare",
        "chroot",
        "setpriv",
        "sg",
        "newgrp",
        "docker",
        "docker-compose",
        "podman",
        "nerdctl",
        "ctr",
        "at",
        "batch",
        "loginctl",
        "nohup",
        "setsid",
        "disown",
        "screen",
        "tmux",
        "nft",
        "iptables",
        "ufw",
        "apt",
        "apt-get",
        "dpkg",
        "snap",
        "passwd",
        "chsh",
        "chfn",
        "setfacl",
        "chattr",
        "mount",
        "umount",
        "reboot",
        "shutdown",
        "poweroff",
        "halt",
    }
    | OUTILS_SSH
)
# Filet sur toute la commande, heredocs compris, dès qu'elle passe par ssh.
DISTANT_BRUT = re.compile(
    r"(?<![\w./-])(sudo|su|doas|pkexec|run0|systemd-run|docker|podman|nsenter|crontab|"
    r"nohup|setsid)(?![\w.-])"
)
# Alamel n'est jamais touché, et aucune requête ne part du VPS vers les sources.
NOMS_INTERDITS = re.compile(
    r"alamel|(127\.0\.0\.1|localhost):(3100|9100|9101)\b|169\.254\.169\.254|"
    r"medicaments\.gouv\.fr|data\.gouv\.fr|has-sante\.fr",
    re.IGNORECASE,
)
# Un interprète qui lit son programme sur l'entrée standard ou en argument échappe au jugement.
INTERPRETES = {"bash", "sh", "dash", "zsh", "ksh", "python", "python3", "perl", "ruby", "node"}
SYSTEMCTL_LECTURE = {
    "status",
    "show",
    "cat",
    "is-active",
    "is-failed",
    "is-enabled",
    "list-units",
    "list-timers",
    "list-unit-files",
    "--version",
}
SYSTEMCTL_PILOTAGE = {"start", "stop", "restart", "reset-failed"}
SYSTEMCTL_OPTIONS_INTERDITES = (
    "--user",
    "--global",
    "-H",
    "--host",
    "-M",
    "--machine",
    "--root",
    "--runtime",
    "--now",
    "-f",
    "--force",
)
JOURNALCTL_ECRIT = ("--vacuum", "--rotate", "--flush", "--sync", "--setup-keys", "--relinquish")
# Ce que l'IeC lit sur le VPS ; il n'y pilote rien.
LECTURE_DISTANTE = LECTURE | {
    "journalctl",
    "systemctl",
    "free",
    "df",
    "du",
    "uptime",
    "id",
    "uname",
    "findmnt",
    "nproc",
    "pharmaflux",
}
PHARMAFLUX_LECTURE = (["etat"], ["--version"], ["chaine", "etat"], ["index", "etat"])
# Où une écriture shell du codeur peut aller hors de son dossier : des brouillons jetables.
TEMPORAIRES = ("/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/", "/dev/")


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


def dossier_temporaire(racine: Path) -> Path:
    """Dossier temporaire des sessions Claude Code lancées dans `racine` :
    /tmp/claude-<uid>/<chemin de la racine, tout sauf [A-Za-z0-9-] changé en ->."""
    nom = re.sub(r"[^A-Za-z0-9-]", "-", str(racine))
    return Path("/tmp").resolve() / f"claude-{os.getuid()}" / nom


def verifier_ecriture(role: str, cible: Path, racine: Path, principal: Path) -> None:
    if DOSSIER_SSH.search(str(cible)):
        raise Refus("~/.ssh est à beko : aucun agent n'y écrit (mission 10).")
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
        # Brouillons jetables de ses propres sessions (mission 01, §0 H.9) ;
        # un script dont les mesures sont citées dans un rapport va dans le dépôt.
        if chemin_relatif(cible, dossier_temporaire(racine)) is not None:
            return
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


def segments(
    commande: str, affectations: list[str] | None = None
) -> list[tuple[list[str], list[str]]]:
    """Rend, pour chaque commande simple : (mots, cibles des redirections en écriture).
    Les affectations de tête (« A=b commande ») sont retirées des mots ; si une liste est
    donnée, elles y sont ajoutées, pour que leur valeur soit jugée."""
    resultat: list[tuple[list[str], list[str]]] = []
    # « \ » en fin de ligne continue la commande : recoller avant de couper en lignes,
    # sinon « git \⏎ push » donnerait deux commandes, « git » puis « push ».
    commande = re.sub(r"\\\r?\n", " ", commande)
    for ligne in commande.split("\n"):
        mots: list[str] = []
        cibles: list[str] = []
        jetons = _jetons(ligne)
        i = 0
        while i <= len(jetons):
            jeton = jetons[i] if i < len(jetons) else ";"
            if jeton in SEPARATEURS:
                while mots and (
                    re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", mots[0])
                    or mots[0] in PREFIXES
                    or mots[0] in MOTS_CLES
                ):
                    if affectations is not None and "=" in mots[0]:
                        affectations.append(mots[0])
                    retire, mots = mots[0], mots[1:]
                    # « time -p make … » : les options de time ne sont pas la commande.
                    while retire == "time" and mots and mots[0].startswith("-"):
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


def _ls_remote_iec(reste: list[str]) -> bool:
    """« origin » ou un dépôt https de GitHub, puis des motifs de références, en lecture."""
    positionnels = [a for a in reste if not a.startswith("-")]
    if any(a.startswith("-") and a not in GIT_LS_REMOTE_OPTIONS for a in reste):
        return False
    return bool(positionnels) and (
        positionnels[0] == "origin" or positionnels[0].startswith("https://github.com/")
    )


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
    if sous == "archive":
        # Vers la sortie standard seulement, pour extraire un commit dans un dossier
        # temporaire (git archive <commit> | tar -x -C …) : -o écrirait un fichier,
        # --remote et --exec s'adressent à un autre dépôt.
        interdit = next(
            (a for a in reste if a.startswith(("-o", "--output", "--remote", "--exec"))), None
        )
        if interdit:
            raise Refus(f"git archive {interdit} interdit : l'archive sort sur la sortie standard.")
        return
    if sous == "branch" and all(
        a in ("--show-current", "--list", "-v", "-vv", "-a") for a in reste
    ):
        return
    if sous == "worktree" and reste[:1] == ["list"]:
        return
    if sous == "config" and (
        (
            reste[:1] in (["--get"], ["--get-all"], ["get"])
            and len(reste) == 2
            and not reste[1].startswith("-")
        )
        or reste in (["--list"], ["-l"], ["list"])
    ):
        # Lecture d'une clé ou de toute la configuration ; toute autre forme écrit.
        return
    if role == "iec" and sous == "fetch" and all(a in GIT_FETCH_IEC for a in reste):
        return
    if role == "iec" and sous == "ls-remote" and _ls_remote_iec(reste):
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


def verifier_compose(args: list[str]) -> None:
    """args : ce qui suit « docker compose » (ou « docker-compose »)."""
    projet: str | None = None
    sous: str | None = None
    reste: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if sous is not None:
            reste.append(a)
        elif a in COMPOSE_OPTIONS_A_VALEUR:
            valeur = args[i + 1] if i + 1 < len(args) else ""
            if a in ("-p", "--project-name"):
                projet = valeur
            i += 1
        elif a.startswith("--project-name="):
            projet = a.split("=", 1)[1]
        elif a.startswith("-p") and len(a) > 2:
            projet = a[2:]
        elif not a.startswith("-"):
            sous = a
        i += 1
    if sous is None or sous in COMPOSE_SANS_PROJET:
        return
    if sous not in COMPOSE_PERMIS:
        raise Refus(
            f"docker compose {sous} n'est pas permis aux agents"
            + (" : télécharger une image est à beko." if sous == "pull" else ".")
        )
    if projet != PROJET_COMPOSE:
        raise Refus(
            f"docker compose doit nommer le projet : -p {PROJET_COMPOSE} "
            "(le colima fait aussi tourner les conteneurs d'Alamel)."
        )
    if sous in COMPOSE_PULL_INTERDIT and not any(
        a == "--pull=never" or (a == "--pull" and reste[j + 1 : j + 2] == ["never"])
        for j, a in enumerate(reste)
    ):
        raise Refus(
            f"docker compose {sous} sans --pull never : une image absente serait "
            "téléchargée, et le premier pull est à beko."
        )


def verifier_conteneurs(tete: str, mots: list[str]) -> None:
    """docker, docker-compose et colima, pour tous les rôles."""
    args = mots[1:]
    if tete == "colima":
        if args[:1] and args[0] not in COLIMA_LECTURE:
            raise Refus(
                f"colima {args[0]} interdit : la machine virtuelle porte aussi les "
                "conteneurs d'Alamel ; beko s'en charge."
            )
        return
    if tete == "docker-compose":
        verifier_compose(args)
        return
    if args[:1] == ["compose"]:
        verifier_compose(args[1:])
        return
    if args and args[0] not in DOCKER_LECTURE:
        raise Refus(
            f"docker {args[0]} interdit : hors compose, docker ne fait que lire "
            f"(ps, images…). Passe par docker compose -p {PROJET_COMPOSE}."
        )


def execute_par_option(mots: list[str]) -> bool:
    """find -exec, -execdir, -ok, -okdir : la commande lancée échappe au jugement par tête."""
    return Path(mots[0]).name == "find" and any(a.startswith(FIND_EXECUTE) for a in mots[1:])


def ecrit_par_option(mots: list[str]) -> bool:
    """Une commande de LECTURE qui écrit quand même : sed -i, sort -o, uniq ENTREE SORTIE,
    find -delete, -fprint, -fls, ou -exec (qui peut tout faire)."""
    tete, args = Path(mots[0]).name, mots[1:]
    if tete == "find":
        return execute_par_option(mots) or any(a.startswith(FIND_ECRIT) for a in args)
    if tete == "sed":
        return any(a.startswith("-i") or a == "--in-place" for a in args)
    if tete == "sort":
        return any(a.startswith(("-o", "--output")) for a in args)
    if tete == "uniq":
        return len([a for a in args if not a.startswith("-")]) > 1
    return False


def verifier_systemctl(role: str, mots: list[str]) -> None:
    """Sur le VPS : le codeur lit et pilote les unités que polkit lui ouvre, l'IeC lit."""
    args = mots[1:]
    if any(a.startswith(SYSTEMCTL_OPTIONS_INTERDITES) for a in args):
        raise Refus("systemctl : options --user, --runtime, --now, -H, -M… interdites sur le VPS.")
    verbe = next((a for a in args if not a.startswith("-")), "status")
    if verbe in SYSTEMCTL_LECTURE:
        return
    if role == "codeur" and verbe in SYSTEMCTL_PILOTAGE:
        if any("pharmaflux-collecte" in a for a in args):
            raise Refus("la collecte est à beko : le codeur ne la pilote pas.")
        return
    raise Refus(
        f"systemctl {verbe} : sur le VPS, le codeur lit et lance (start, stop, restart, "
        "reset-failed) ; enable, daemon-reload, edit… sont à beko."
    )


def verifier_distante(role: str, distante: str) -> None:
    """La commande envoyée au VPS par « ssh pharmaflux-vps … », segment par segment."""
    if NOMS_INTERDITS.search(distante):
        raise Refus(
            "Alamel, les métadonnées de l'hébergeur et les sites sources sont hors d'atteinte."
        )
    for mots, cibles in segments(distante):
        tete = Path(mots[0]).name
        if mots[0].startswith("$") or "$(" in mots[0] or "`" in mots[0]:
            raise Refus("une commande cachée dans une variable n'est pas jugeable.")
        if role == "iec":
            if tete not in LECTURE_DISTANTE or ecrit_par_option(mots):
                raise Refus(f"« {tete} » : l'IeC ne fait que lire sur le VPS.")
            if any(c != "/dev/null" for c in cibles):
                raise Refus("l'IeC n'écrit rien sur le VPS.")
            if tete == "systemctl":
                verifier_systemctl("iec", mots)
            if tete == "pharmaflux" and [a for a in mots[1:]] not in PHARMAFLUX_LECTURE:
                raise Refus("pharmaflux sur le VPS : l'IeC n'en lit que l'état.")
            if tete == "journalctl" and any(a.startswith(JOURNALCTL_ECRIT) for a in mots[1:]):
                raise Refus("journalctl : en lecture seulement.")
            continue
        if tete in DISTANT_INTERDIT:
            raise Refus(
                f"« {tete} » sur le VPS : root, conteneurs, système et tâches qui survivent "
                "sont à beko."
            )
        if tete in INTERPRETES and (
            len(mots) == 1 or any(a in ("-s", "-", "-c", "-e", "-i") for a in mots[1:])
        ):
            raise Refus(
                f"« {tete} » sans fichier de script : un programme passé à ssh échapperait au "
                "jugement. Dépose le script avec le code, puis lance-le par son chemin."
            )
        if tete == "systemctl":
            verifier_systemctl("codeur", mots)
        if tete == "journalctl" and any(a.startswith(JOURNALCTL_ECRIT) for a in mots[1:]):
            raise Refus("journalctl : en lecture seulement.")
        if tete in ("curl", "wget") and not all(
            re.match(r"^https?://(127\.0\.0\.1|localhost):\d+(/|$)", a)
            for a in mots[1:]
            if re.match(r"^[a-z]+://", a)
        ):
            raise Refus(
                "curl et wget, sur le VPS, ne visent que les services locaux de Pharmaflux."
            )


def verifier_ssh(role: str, mots: list[str], brute: str) -> None:
    """ssh, et rien d'autre de la famille, vers le seul alias du VPS (mission 10)."""
    tete = Path(mots[0]).name
    if tete != "ssh":
        if tete == "rsync" and not any(
            ":" in a or a.startswith(("-e", "--rsh", "--rsync-path")) for a in mots[1:]
        ):
            return  # copie locale
        raise Refus(
            f"« {tete} » : seul « ssh {ALIAS_VPS} <commande> » parle au VPS ; le code s'y dépose "
            f"par « git archive … | ssh {ALIAS_VPS} 'tar -x …' »."
        )
    if role == "relecteur":
        raise Refus("le relecteur n'a rien à faire sur le VPS.")
    reste = mots[1:]
    i = 0
    while i < len(reste) and reste[i].startswith("-"):
        if reste[i] not in SSH_OPTIONS_PERMISES:
            raise Refus(f"ssh {reste[i]} : seules -q -T -n -x -a sont permises.")
        i += 1
    if i >= len(reste) or reste[i] != ALIAS_VPS:
        raise Refus(
            f"ssh ne vise que l'alias {ALIAS_VPS} (le compte du codeur) ; jamais vps1, qui "
            "ouvre le compte root de beko, ni une adresse."
        )
    i += 1
    # OpenSSH lit encore des options juste après la destination.
    while i < len(reste) and reste[i].startswith("-"):
        if reste[i] not in SSH_OPTIONS_PERMISES:
            raise Refus(f"ssh {reste[i]} : seules -q -T -n -x -a sont permises.")
        i += 1
    distante = " ".join(reste[i:]).strip()
    if not distante:
        raise Refus("ssh sans commande ouvrirait une session interactive : donne la commande.")
    if DISTANT_BRUT.search(brute):
        raise Refus("sudo, su, docker, systemd-run, nohup… ne passent jamais par ssh.")
    verifier_distante(role, distante)


def verifier_cible_shell(cible: str, cwd: Path | None, racine: Path | None) -> None:
    """Codeur : une écriture shell reste dans son dossier ou dans un dossier temporaire."""
    if racine is None or cible.startswith("&"):
        return
    brut = re.sub(r"^(~|\$\{?HOME\}?)(?=/|$)", str(Path.home()), cible)
    if re.match(r"^\$\{?TMPDIR\}?(/|$)", brut):
        return
    if "$" in brut or "`" in brut:
        raise Refus(f"cible d'écriture non jugeable (variable) : {cible}")
    chemin = Path(brut) if brut.startswith("/") else (cwd or racine) / brut
    normal = Path(os.path.normpath(str(chemin)))
    if chemin_relatif(normal, racine) is not None:
        return
    # À côté de son dossier : les autres dossiers du circuit (le dépôt principal, son .git).
    if chemin_relatif(normal, racine.parent) is None and str(normal).startswith(TEMPORAIRES):
        return
    raise Refus(f"écriture hors du dossier du codeur ({racine}) : {cible}")


def verifier_bash(
    role: str, commande: str, racine: Path | None = None, cwd: Path | None = None
) -> None:
    nette = retirer_heredocs(commande)
    affectations: list[str] = []
    decoupe = segments(nette, affectations)
    for affectation in affectations:
        valeur = affectation.split("=", 1)[1]
        if (
            SSH_BRUT.search(valeur)
            or CONTENEURS_BRUT.search(valeur)
            or GIT_ECRIT_BRUT.search(valeur)
        ):
            raise Refus(f"commande cachée dans une variable : {affectation[:60]}")
    if any(DOSSIER_SSH.search(m) for mots, cibles in decoupe for m in mots + cibles):
        raise Refus("~/.ssh est à beko : aucun agent n'y lit ni n'y écrit (mission 10).")
    # Variables d'une boucle « for » dont la liste nomme un chemin réservé :
    # dans le corps, « $f » désigne ce chemin (lecture permise, écriture non).
    variables_reservees: set[str] = set()

    def designe_reserve(mot: str) -> bool:
        return mentionne_reserve(mot) or any(
            re.search(r"\$\{?" + re.escape(v) + r"\b", mot) for v in variables_reservees
        )

    for mots, cibles in decoupe:
        tete = Path(mots[0]).name
        if role != "iec" and (mots[0].startswith("$") or "$(" in mots[0] or "`" in mots[0]):
            raise Refus("une commande cachée dans une variable n'est pas jugeable.")
        if tete in OUTILS_SSH:
            verifier_ssh(role, mots, commande)
            continue
        if role == "codeur":
            for cible in cibles:
                verifier_cible_shell(cible, cwd, racine)
            if tete == "tee":
                for a in mots[1:]:
                    if not a.startswith("-"):
                        verifier_cible_shell(a, cwd, racine)
            if tete in ("cp", "mv", "install", "ln") and len(mots) > 2:
                verifier_cible_shell(mots[-1], cwd, racine)
        # La clé de l'API : lire le script se fait par l'outil Read ; le lancer est à beko.
        if tete not in LECTURE and tete != "git" and CLE_BRUT.search(" ".join(mots)):
            raise Refus(
                "la clé de l'API Claude est à beko : aucun agent ne la lit ni ne s'en sert."
            )
        # Filet : git caché derrière bash -c, xargs, eval…
        # Une commande de lecture est exemptée du filet, sauf si elle en lance une autre.
        lit_seulement = tete in LECTURE and not execute_par_option(mots)
        if tete != "git" and not lit_seulement:
            cache = GIT_ECRIT_BRUT.search(" ".join(mots[1:]))
            if cache:
                raise Refus(f"opération git « {cache.group(1)} » interdite aux agents.")
        if tete not in ("docker", "docker-compose", "colima") and not lit_seulement:
            cache = CONTENEURS_BRUT.search(" ".join(mots[1:]))
            if cache:
                raise Refus(
                    f"« {cache.group(1)} » appelé par « {tete} » : lance-le en tête de "
                    "commande, pour que ses règles s'appliquent."
                )
            cache = SSH_BRUT.search(" ".join(mots[1:]))
            if cache:
                raise Refus(
                    f"« {cache.group(1)} » appelé par « {tete} » : lance ssh en tête de "
                    "commande, pour que ses règles s'appliquent."
                )
        if tete in ("docker", "docker-compose", "colima"):
            verifier_conteneurs(tete, mots)
            continue
        if tete in SYSTEME:
            raise Refus(
                f"« {tete} » touche au système : beko s'en charge (CLAUDE.md, « Système »)."
            )
        if (
            tete in ("make", "gmake")
            and mots[1:] not in MAKE_VERSION
            and not any(a in MAKE_SIMULATION for a in mots[1:])
        ):
            raise Refus(
                "make lance des recettes que le garde-fou ne voit pas : « make -n <cible> » "
                "les affiche, lance ensuite les commandes elles-mêmes ; make <cible> est à beko."
            )
        if tete in LANCEURS:
            lances = mots[1:]
        elif tete == "uv" and mots[1:2] == ["run"]:
            lances = mots[2:]
        else:
            lances = []
        rang = next((k for k, a in enumerate(lances) if Path(a).name in ("make", "gmake")), None)
        # Seules les options qui suivent make comptent : « nice -n 5 make up » n'est pas
        # une simulation.
        if rang is not None and not any(a in MAKE_SIMULATION for a in lances[rang + 1 :]):
            raise Refus(
                f"make derrière « {tete} » : la même règle que make en tête, "
                "« make -n <cible> » seulement ; make <cible> est à beko."
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
            # L'IeC lit GitHub (PR, CI, artefacts de diagnostic, versions à épingler) ; il
            # n'y écrit jamais : push, PR, fusion et tout le reste sont à beko.
            if (
                role == "iec"
                and mots[1:3]
                and (
                    (mots[1] == "pr" and mots[2] in ("view", "checks", "list", "diff"))
                    or (mots[1] == "run" and mots[2] in ("list", "view", "download"))
                    or (mots[1] == "release" and mots[2] in ("list", "view"))
                )
            ):
                continue
            raise Refus("gh est réservé à beko (PR, dépôt, CI).")
        if (
            tete == "for"
            and len(mots) >= 3
            and mots[2] == "in"
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", mots[1])
            and not cibles
        ):
            # La liste n'est pas exécutée : seul le corps de la boucle est jugé.
            if any(mentionne_reserve(a) for a in mots[3:]):
                variables_reservees.add(mots[1])
            continue
        if role == "iec":
            continue
        ecrit_reserve = any(designe_reserve(c) for c in cibles)
        if not ecrit_reserve and any(
            mots[: len(t)] == t and all(a.startswith("-") for a in mots[len(t) :])
            for t in TESTS_GARDE_FOUS
        ):
            continue
        # Codeur et relecteur : pas d'écriture shell vers un chemin réservé.
        if not ecrit_reserve and not any(designe_reserve(a) for a in mots[1:]):
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
    # Un connecteur GitHub échappe aux règles de Bash : lecture seule, pour l'IeC seulement.
    if outil.startswith("mcp__") and "github" in outil.lower():
        action = outil.rsplit("__", 1)[-1].lower()
        if role != "iec" or not action.startswith(MCP_GITHUB_LECTURE):
            raise Refus(f"outil « {outil} » : GitHub en lecture seule, pour l'IeC seulement.")
        return
    if outil == "Bash":
        verifier_bash(
            role,
            str(entree.get("command", "")),
            racine,
            Path(appel.get("cwd") or dossier_projet),
        )
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
