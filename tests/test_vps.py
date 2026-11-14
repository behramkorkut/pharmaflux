"""Mission 10, palier 1 : les fichiers que root lira sur le VPS-1, vérifiés sans VPS.

Lecture statique de ``docker-compose.yml``, de ``infra/vps/vps.yml``, des unités systemd et de
la procédure. C'est la liste de contrôle de l'IeC (``infra/agents/vps/README.md``, « Installer
un fichier que root lit »), écrite en tests : elle passe avant que l'IeC ne relise, et à chaque
passage de la CI. Le vrai contrôle reste sur le VPS (``systemd-analyze verify``, ``systemctl
show``, ``docker compose config``) : un test statique ne lit pas un fichier comme systemd le lit.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
import yaml

from tests.conftest import commande_cli

VPS = Path("infra/vps")
COMPOSE = Path("docker-compose.yml")
COMPOSE_VPS = VPS / "vps.yml"
CONTENEURS = VPS / "pharmaflux-conteneurs.service"
REMPLISSAGE = VPS / "pharmaflux-remplissage.service"
COLLECTE = Path("infra/planification/pharmaflux-collecte.service")
PROCEDURE = VPS / "README.md"

FICHIERS_COMPOSE = (
    "-f /etc/pharmaflux/compose/docker-compose.yml -f /etc/pharmaflux/compose/vps.yml"
)
DOCKER_COMPOSE = f"/usr/bin/docker compose -p pharmaflux {FICHIERS_COMPOSE}"
SERVICES_VPS = {"redpanda", "qdrant"}  # la console est sous un profil : absente du VPS

Unite = dict[str, dict[str, list[str]]]


def lire_unite(chemin: Path) -> Unite:
    """Les directives d'une unité, par section ; une directive répétée garde toutes ses valeurs."""
    sections: Unite = {}
    section = ""
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne[0] in "#;":
            continue
        assert not ligne.endswith("\\"), f"{chemin} : pas de ligne continuée ({ligne})"
        if ligne.startswith("["):
            section = ligne.strip("[]")
            sections.setdefault(section, {})
            continue
        cle, separateur, valeur = ligne.partition("=")
        assert separateur and section, f"{chemin} : ligne incomprise ({ligne})"
        sections[section].setdefault(cle.strip(), []).append(valeur.strip())
    return sections


def une(unite: Unite, section: str, cle: str) -> str:
    """La valeur d'une directive qui n'apparaît qu'une fois."""
    (valeur,) = unite[section][cle]
    return valeur


def _yaml(chemin: Path) -> dict[str, object]:
    contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    assert isinstance(contenu, dict)
    return contenu


def _octets(taille: str) -> int:
    nombre, unite = re.fullmatch(r"(\d+)([mMgG])", taille).groups()  # type: ignore[union-attr]
    return int(nombre) * {"m": 1024**2, "g": 1024**3}[unite.lower()]


# --- vps.yml : ce qui s'ajoute, et rien d'autre ------------------------------------------------


def test_vps_yml_ne_porte_que_des_reglages_qui_se_remplacent() -> None:
    """Ni image, ni commande, ni port, ni volume, ni variable : sur ces points, ce qui tourne sur
    le VPS est ce que la CI teste avec docker-compose.yml seul."""
    vps = _yaml(COMPOSE_VPS)
    assert set(vps) == {"services"}
    services = vps["services"]
    assert isinstance(services, dict) and set(services) == SERVICES_VPS
    permis = {"restart", "memswap_limit", "stop_grace_period", "logging"}
    for nom, service in services.items():
        assert set(service) == permis, nom
        assert service["restart"] == "unless-stopped", nom
        assert service["logging"]["driver"] == "json-file", nom
        assert set(service["logging"]["options"]) == {"max-size", "max-file"}, nom


def test_pas_d_echange_le_plafond_avec_echange_egale_le_plafond_de_memoire() -> None:
    base, vps = _yaml(COMPOSE)["services"], _yaml(COMPOSE_VPS)["services"]  # type: ignore[index]
    for nom in SERVICES_VPS:
        assert _octets(vps[nom]["memswap_limit"]) == _octets(base[nom]["mem_limit"]), nom


def test_l_arret_laisse_a_redpanda_le_temps_d_ecrire() -> None:
    """Redpanda accuse réception avant d'écrire (write_caching) : 10 s par défaut ne suffisent
    pas à en être sûr, et l'unité attend plus longtemps que le conteneur."""
    vps = _yaml(COMPOSE_VPS)["services"]
    assert vps["redpanda"]["stop_grace_period"] == "1m"  # type: ignore[index]
    assert int(une(lire_unite(CONTENEURS), "Service", "TimeoutStopSec")) > 60


# --- docker-compose.yml : la liste de contrôle de l'IeC ----------------------------------------


CLES_D_UN_SERVICE = {
    "image",
    "container_name",
    "command",
    "ports",
    "volumes",
    "configs",
    "mem_limit",
    "healthcheck",
    "environment",
    "profiles",
    "depends_on",
}


def test_le_compose_ne_porte_que_des_cles_connues() -> None:
    """Une liste fermée : ce qui ferait lire ou monter un fichier de l'hôte par Docker
    (extends, env_file, include, secrets, un config « file: »…) n'y est pas, et toute clé
    nouvelle fait échouer ce test avant d'arriver au contrôle de l'IeC."""
    compose = _yaml(COMPOSE)
    assert set(compose) == {"name", "services", "configs", "volumes"}
    assert compose["name"] == "pharmaflux"
    for nom, service in compose["services"].items():  # type: ignore[union-attr]
        assert set(service) <= CLES_D_UN_SERVICE, (nom, set(service) - CLES_D_UN_SERVICE)
        for config in service.get("configs", []):
            assert set(config) == {"source", "target"}, nom
    for nom, config in compose["configs"].items():  # type: ignore[union-attr]
        assert set(config) == {"content"}, nom  # écrit dans le fichier, jamais lu sur l'hôte


def test_le_compose_n_ouvre_rien_vers_l_hote() -> None:
    compose = _yaml(COMPOSE)
    volumes_nommes = set(compose["volumes"])  # type: ignore[arg-type]
    interdits = {"privileged", "cap_add", "user", "network_mode", "pid", "ipc", "devices"}
    for nom, service in compose["services"].items():  # type: ignore[union-attr]
        assert not interdits & set(service), nom
        for port in service.get("ports", []):
            assert isinstance(port, str) and port.startswith("127.0.0.1:"), (nom, port)
        for volume in service.get("volumes", []):
            source = volume.split(":")[0]
            assert source in volumes_nommes, (nom, volume)  # jamais un chemin de l'hôte
        assert "docker.sock" not in str(service), nom
    for nom, volume in compose["volumes"].items():  # type: ignore[union-attr]
        assert volume == {"name": nom}, nom  # un volume nommé, sans pilote ni chemin


def test_les_images_du_vps_sont_epinglees_par_leur_empreinte() -> None:
    services = _yaml(COMPOSE)["services"]
    for nom in SERVICES_VPS:
        image = services[nom]["image"]  # type: ignore[index]
        assert re.fullmatch(r"[\w./-]+:v[\d.]+@sha256:[0-9a-f]{64}", image), (nom, image)


def test_les_plafonds_du_remplissage_tiennent_dans_deux_gigaoctets() -> None:
    services = _yaml(COMPOSE)["services"]
    conteneurs = sum(_octets(services[nom]["mem_limit"]) for nom in SERVICES_VPS)  # type: ignore[index]
    unite = _octets(une(lire_unite(REMPLISSAGE), "Service", "MemoryMax"))
    assert conteneurs + unite <= 2 * 1024**3


# --- les unités : chaque directive est connue ---------------------------------------------------

DURCISSEMENT_COMMUN = {
    "NoNewPrivileges",
    "PrivateTmp",
    "PrivateDevices",
    "ProtectSystem",
    "ProtectHome",
    "ProtectKernelTunables",
    "ProtectKernelModules",
    "ProtectKernelLogs",
    "ProtectControlGroups",
    "ProtectClock",
    "ProtectHostname",
    "RestrictSUIDSGID",
    "RestrictRealtime",
    "RestrictNamespaces",
    "LockPersonality",
    "MemoryDenyWriteExecute",
    "RestrictAddressFamilies",
    "IPAddressDeny",
    "SystemCallArchitectures",
}
DIRECTIVES = {
    CONTENEURS: {
        "Unit": {"Description", "Documentation", "After", "Wants"},
        "Service": DURCISSEMENT_COMMUN
        | {
            "Type",
            "RemainAfterExit",
            "ExecStart",
            "ExecStop",
            "TimeoutStartSec",
            "TimeoutStopSec",
            "SyslogIdentifier",
            "LogNamespace",
        },
        "Install": {"WantedBy"},
    },
    REMPLISSAGE: {
        "Unit": {"Description", "Documentation", "After"},
        "Service": DURCISSEMENT_COMMUN
        | {
            "Type",
            "User",
            "Group",
            "Environment",
            "ExecStart",
            "SyslogIdentifier",
            "LogNamespace",
            "TimeoutStartSec",
            "Nice",
            "IOSchedulingClass",
            "CPUQuota",
            "CPUWeight",
            "MemoryMax",
            "MemorySwapMax",
            "OOMPolicy",
            "OOMScoreAdjust",
            "ReadWritePaths",
            "BindReadOnlyPaths",
            "UMask",
            "ProtectProc",
            "ProcSubset",
            "IPAddressAllow",
            "CapabilityBoundingSet",
            "AmbientCapabilities",
            "SystemCallFilter",
            "SystemCallErrorNumber",
            "RemoveIPC",
        },
    },
}


@pytest.mark.parametrize("chemin", [CONTENEURS, REMPLISSAGE], ids=str)
def test_une_unite_ne_porte_que_des_directives_connues(chemin: Path) -> None:
    """Une liste fermée, pas une liste d'interdits : ExecCondition=, FailureAction=,
    LoadCredential=, RootDirectory= ou toute directive ajoutée fait échouer ce test, et doit
    s'y justifier avant d'arriver au contrôle de l'IeC."""
    unite = lire_unite(chemin)
    assert {section: set(directives) for section, directives in unite.items()} == DIRECTIVES[chemin]


# --- l'unité des conteneurs --------------------------------------------------------------------


def test_l_unite_des_conteneurs_demarre_et_arrete_sans_rien_effacer() -> None:
    unite = lire_unite(CONTENEURS)
    service = unite["Service"]
    demarrage, arret = une(unite, "Service", "ExecStart"), une(unite, "Service", "ExecStop")
    assert demarrage == f"{DOCKER_COMPOSE} up -d --wait --wait-timeout 180 --pull never"
    assert arret == f"{DOCKER_COMPOSE} stop"
    assert not {"ExecStartPre", "ExecStartPost", "ExecStopPost", "ExecReload"} & set(service)
    for commande in (demarrage, arret):
        mots = shlex.split(commande)
        assert not {"down", "rm", "-v", "--volumes", "prune", "kill", "--profile"} & set(mots)
        assert "--remove-orphans" not in mots
    assert une(unite, "Service", "Type") == "oneshot"
    assert une(unite, "Service", "RemainAfterExit") == "yes"
    attente = int(shlex.split(demarrage)[shlex.split(demarrage).index("--wait-timeout") + 1])
    assert int(une(unite, "Service", "TimeoutStartSec")) > attente


def test_l_unite_des_conteneurs_ne_nomme_rien_que_le_codeur_ecrit() -> None:
    """Elle tourne en root : ni Exec, ni variable, ni fichier sous /srv/pharmaflux."""
    unite = lire_unite(CONTENEURS)
    service = unite["Service"]
    assert not {"User", "Group", "Environment", "EnvironmentFile", "WorkingDirectory"} & set(
        service
    )
    for section in unite.values():
        for cle, valeurs in section.items():
            assert not any("/srv/pharmaflux" in v or "/home" in v for v in valeurs), cle
    assert une(unite, "Service", "LogNamespace") == "pharmaflux"


def test_l_unite_des_conteneurs_ne_depend_pas_durement_de_docker() -> None:
    """Avec Requires= ou PartOf=, une mise à jour de Docker arrêterait l'unité, et « stop »
    marquerait les conteneurs comme arrêtés à la main."""
    unite = lire_unite(CONTENEURS)["Unit"]
    assert unite["After"] == ["docker.service"] and unite["Wants"] == ["docker.service"]
    assert not {"Requires", "PartOf", "BindsTo", "Conflicts", "OnFailure", "OnSuccess"} & set(unite)
    assert lire_unite(CONTENEURS)["Install"] == {"WantedBy": ["multi-user.target"]}


# --- l'unité de remplissage --------------------------------------------------------------------

# Reprises telles quelles de l'unité de collecte (score d'exposition 1,3) : même valeur ici.
DIRECTIVES_DU_MODELE = (
    "Type",
    "Nice",
    "IOSchedulingClass",
    "NoNewPrivileges",
    "PrivateTmp",
    "PrivateDevices",
    "ProtectSystem",
    "ProtectHome",
    "UMask",
    "ProtectKernelTunables",
    "ProtectKernelModules",
    "ProtectControlGroups",
    "ProtectKernelLogs",
    "ProtectClock",
    "ProtectHostname",
    "ProtectProc",
    "ProcSubset",
    "RestrictSUIDSGID",
    "RestrictRealtime",
    "RestrictNamespaces",
    "LockPersonality",
    "MemoryDenyWriteExecute",
    "CapabilityBoundingSet",
    "AmbientCapabilities",
    "SystemCallArchitectures",
    "SystemCallFilter",
    "SystemCallErrorNumber",
    "RemoveIPC",
)


def test_le_remplissage_garde_le_durcissement_de_la_collecte() -> None:
    modele, unite = lire_unite(COLLECTE)["Service"], lire_unite(REMPLISSAGE)["Service"]
    for directive in DIRECTIVES_DU_MODELE:
        assert unite.get(directive) == modele[directive], directive


def test_le_remplissage_tourne_sous_le_compte_de_la_chaine() -> None:
    unite = lire_unite(REMPLISSAGE)
    service = unite["Service"]
    assert service["User"] == ["pharmaflux-chaine"] and service["Group"] == ["pharmaflux-chaine"]
    # Ni ce que systemd lirait ou lancerait en root, ni ce qui arrêterait une autre unité.
    interdites = {
        "EnvironmentFile",
        "WorkingDirectory",
        "ExecStartPre",
        "ExecStartPost",
        "ExecStop",
        "ExecStopPost",
        "ExecReload",
        "SupplementaryGroups",
        "PAMName",
    }
    assert not interdites & set(service)
    assert not {"Conflicts", "AllowIsolate", "OnSuccess", "OnFailure", "Requires"} & set(
        unite["Unit"]
    )
    assert "Install" not in unite  # lancée à la main, jamais au démarrage
    assert service["LogNamespace"] == ["pharmaflux"]
    assert "pharmaflux-collecte" not in REMPLISSAGE.name
    # Elle ne démarre pas les conteneurs : la commande sonde les services elle-même.
    assert (
        unite["Unit"]["After"] == ["pharmaflux-conteneurs.service"] and "Wants" not in unite["Unit"]
    )


def test_la_commande_du_remplissage_existe_et_porte_ses_chemins() -> None:
    """Un seul Exec, sans préfixe (+, !, -, @, :), sous la version en service ; ses options sont
    celles que la ligne de commande connaît, et tous ses chemins sont en arguments, absolus."""
    execution = une(lire_unite(REMPLISSAGE), "Service", "ExecStart")
    assert re.match(r"[A-Za-z/]", execution), "aucun préfixe d'exécution"
    binaire, *arguments = shlex.split(execution)
    assert binaire == "/srv/pharmaflux/code/courante/.venv/bin/pharmaflux"
    commande, reste = commande_cli(arguments)
    assert commande.name == "remplir"
    parametres = commande.make_context("remplir", list(reste)).params
    assert Path(parametres["racine"]) == Path("/home/pharmaflux/pharmaflux-data")
    assert Path(parametres["derive"]) == Path("/srv/pharmaflux/derive")
    assert Path(parametres["modeles"]) == Path("/srv/pharmaflux/modeles")
    assert parametres["modele"] == "e5-small-int8"


def test_le_remplissage_lit_l_archive_et_n_ecrit_que_le_derive() -> None:
    service = lire_unite(REMPLISSAGE)["Service"]
    assert service["ReadWritePaths"] == ["/srv/pharmaflux/derive"]
    assert service["BindReadOnlyPaths"] == ["/home/pharmaflux/pharmaflux-data"]
    assert "BindPaths" not in service  # c'est par là que la collecte écrit l'archive
    # Environment= ne porte que des valeurs écrites en clair, hors de ce que le codeur écrit.
    assert service["Environment"] == [
        "PYTHONUNBUFFERED=1",
        "TMPDIR=/srv/pharmaflux/derive/tmp",
    ]


def test_le_remplissage_a_ses_plafonds() -> None:
    """Les valeurs tranchées par l'addendum 1 (B, F, M)."""
    unite = lire_unite(REMPLISSAGE)
    attendu = {
        "MemoryMax": "512M",
        "MemorySwapMax": "0",
        "OOMPolicy": "continue",
        "OOMScoreAdjust": "500",
        "CPUQuota": "150%",
        "CPUWeight": "20",
        "TimeoutStartSec": "6h",
    }
    for directive, valeur in attendu.items():
        assert une(unite, "Service", directive) == valeur, directive


def test_le_remplissage_ne_joint_que_la_boucle_locale() -> None:
    unite = lire_unite(REMPLISSAGE)
    assert une(unite, "Service", "IPAddressDeny") == "any"
    assert une(unite, "Service", "IPAddressAllow") == "127.0.0.1"
    assert une(unite, "Service", "RestrictAddressFamilies") == "AF_INET AF_UNIX"


# --- la procédure ------------------------------------------------------------------------------


def _blocs(texte: str) -> list[tuple[str, str]]:
    """Les blocs ``bash`` de la procédure, chacun avec le titre de sa section."""
    blocs, titre = [], ""
    for morceau in re.split(r"(?m)^(## .*)$", texte):
        if morceau.startswith("## "):
            titre = morceau
            continue
        blocs += [(titre, b) for b in re.findall(r"```bash\n(.*?)```", morceau, re.S)]
    return blocs


def test_chaque_commande_de_la_procedure_tient_sur_une_ligne() -> None:
    blocs = _blocs(PROCEDURE.read_text(encoding="utf-8"))
    assert len(blocs) > 30
    for _, bloc in blocs:
        assert bloc.count("\n") == 1, bloc  # une commande par bloc : elle se copie telle quelle


LECTURES_DOCKER = ("image ls", "ps", "stats")  # hors compose : rien d'autre, sauf ci-dessous
RETRAIT_DES_VOLUMES = "sudo docker volume rm pharmaflux-redpanda pharmaflux-qdrant"


def test_la_procedure_ne_nomme_docker_que_pour_le_projet() -> None:
    for titre, bloc in _blocs(PROCEDURE.read_text(encoding="utf-8")):
        assert "prune" not in bloc, bloc
        for suite in re.findall(r"\bdocker +(.*)", bloc):
            if suite.startswith("compose "):
                assert suite.startswith(f"compose -p pharmaflux {FICHIERS_COMPOSE} "), bloc
                efface = re.search(r" (down|rm|kill)\b| -v\b|--volumes", suite)
            else:
                efface = None
                if bloc.strip() != RETRAIT_DES_VOLUMES:
                    assert suite.startswith(LECTURES_DOCKER), bloc
                else:
                    efface = True
            if efface:
                assert titre.startswith("## Désinstaller"), bloc


def test_un_fichier_que_root_lit_vient_du_commit_controle() -> None:
    """Jamais depuis /srv/pharmaflux/code, que le codeur écrit, jamais par un lien ni une
    copie : « git show <commit>:<chemin> | ssh vps1 'sudo tee …' », et rien d'autre."""
    installes = 0
    for _, bloc in _blocs(PROCEDURE.read_text(encoding="utf-8")):
        cible = re.search(r"/etc/(systemd/system|pharmaflux/compose)/\S+", bloc)
        if not cible or re.match(r"sudo (rm|docker|systemd-analyze) |systemd-analyze ", bloc):
            continue
        installes += 1
        assert re.match(r"git show <commit>:\S+ \| ssh vps1 'sudo tee /etc/", bloc), bloc
        assert "/srv/pharmaflux" not in bloc and not re.search(r"\b(ln|cp|link)\b", bloc), bloc
    assert installes == 4  # deux fichiers compose, deux unités


def test_la_procedure_ne_touche_pas_a_l_archive_sans_garde() -> None:
    """Toute copie vers le VPS est sans --delete ; vers l'archive, elle n'écrase rien et ne vise
    jamais sa racine."""
    copies = [b for _, b in _blocs(PROCEDURE.read_text(encoding="utf-8")) if "rsync" in b]
    assert len(copies) == 5  # le modèle ; l'essai à blanc, les pages, leur manifeste ; la preuve
    for bloc in copies:
        assert bloc.startswith("rsync "), bloc
        commande = bloc.split(";")[0].split()
        assert "--delete" not in bloc, bloc
        destination = commande[-1]
        assert destination.startswith("vps1:/"), bloc
        if "pharmaflux-data" in destination:
            assert not destination.rstrip("/").endswith("pharmaflux-data"), bloc
            assert "--ignore-existing" in commande or "-rnci" in commande, bloc


def test_la_procedure_a_toutes_ses_etapes() -> None:
    titres = re.findall(r"(?m)^## (.*)$", PROCEDURE.read_text(encoding="utf-8"))
    for debut in ("Étape 0.", "Étape 1.", "Étape 2.", "Étape 3.", "Étape 4.", "Étapes 5 à 8."):
        assert any(titre.startswith(debut) for titre in titres), debut
    assert any(titre.startswith("Désinstaller") for titre in titres)


@pytest.mark.parametrize("chemin", sorted(p for p in VPS.iterdir() if p.is_file()), ids=str)
def test_aucune_adresse_ni_compte_reel_dans_les_fichiers_du_vps(chemin: Path) -> None:
    """Seuls les alias ``vps1`` et ``pharmaflux-vps`` et la marque ``<hote>`` désignent le VPS."""
    texte = chemin.read_text(encoding="utf-8")
    adresses = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", texte))
    assert adresses <= {"127.0.0.1", "0.0.0.0"}, adresses
    for cible in re.findall(r"\bssh (?:-\S+ )*([\w.<>@-]+)", texte):
        assert cible in {"vps1", "pharmaflux-vps"}, cible
    for cible in re.findall(r"(?<![\w/.@-])([\w.-]+):/[\w~]", texte):  # rsync, scp : hôte:/chemin
        assert cible in {"vps1", "pharmaflux-vps"}, cible
    comptes = set(re.findall(r"\b[\w.-]+@[\w.-]+\b", texte))
    assert not {c for c in comptes if "@sha256" not in c}, comptes  # ni compte@hôte
