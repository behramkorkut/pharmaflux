# Le codeur sur le VPS-1 : un compte à lui, jamais root

Procédure de beko, écrite par l'IeC pour la mission 10 (14/11/2026). Elle donne
au codeur un accès en écriture au VPS-1 **sans jamais lui donner root**, et
garde l'archive hors de sa portée, même quand il y déploie du code que personne
n'a encore relu. Le dispositif a été conçu en trois variantes, puis éprouvé par
six relecteurs adverses (sécurité et exploitation). Ce qui suit retient la plus
fermée, avec leurs corrections.

## Le principe

| compte | qui | peut | ne peut pas |
|---|---|---|---|
| `ubuntu` | beko | tout : `sudo` sans mot de passe, donc root | — |
| `pharmaflux` | la collecte | écrire l'archive, avec le code de `main` que beko met à jour | rien d'autre ne tourne sous ce compte |
| `pharmaflux-chaine` (nouveau) | la chaîne : événements, bus, silver, index | lire l'archive, écrire `/srv/pharmaflux/derive`, joindre les ports de Pharmaflux sur `127.0.0.1` | écrire l'archive, joindre Alamel ou Internet |
| `<utilisateur-codeur>` (nouveau) | le codeur, par l'alias `pharmaflux-vps` | déposer son code dans `/srv/pharmaflux/code`, lire l'archive et le dérivé, lancer et arrêter les unités que polkit lui ouvre, lire le journal de Pharmaflux | `sudo`, `docker`, installer ou modifier une unité, écrire l'archive, joindre Alamel |

Quatre règles tiennent le tout :
1. **Le code du codeur ne tourne que sous `pharmaflux-chaine`**, qui ne fait que
   lire l'archive. Du code non relu peut abîmer le dérivé, qui se reconstruit,
   jamais l'archive, qui est irremplaçable.
2. **Tout fichier que root lit ou exécute** (unités, fichiers compose, règles)
   est installé par beko, depuis un commit que l'IeC a contrôlé, jamais depuis
   le dossier du codeur. Un fichier que le codeur peut écrire et que root
   exécute ferait de lui root.
3. **Aucune ligne `sudoers`.** Le pilotage passe par une règle polkit, qui ne
   permet que `start`, `stop`, `restart` et `reset-failed` sur une liste exacte
   d'unités déjà installées.
4. **La clé de `vps1` est sous phrase de passe**, hors de l'agent SSH et du
   trousseau. Le garde-fou ne juge que le texte des commandes : un script lancé
   par une session pourrait appeler `ssh vps1`. La phrase de passe est la
   barrière qui compte.

`<utilisateur-codeur>` et `<hote>` sont des marques : le vrai nom du compte et
l'adresse du VPS n'entrent jamais dans le dépôt. Seul l'alias `pharmaflux-vps`
y figure.

## Étape 0, sur le Mac, avant tout : fermer le chemin vers root

Aujourd'hui, la clé de `vps1` ouvre `ubuntu`, donc root. Si elle n'a pas de
phrase de passe, ou si l'agent SSH ou le trousseau la gardent, n'importe quelle
session Claude, de ce projet ou d'un autre, peut s'en servir.

```bash
ssh -G vps1 | grep -E '^(identityfile|identitiesonly|identityagent|controlmaster|controlpath) '
```

Relève le chemin de la clé (`identityfile`). Puis, dans Terminal.app :

```bash
ssh-keygen -y -P '' -f <cle-de-vps1> > /dev/null 2>&1 && echo "SANS phrase de passe" || echo "phrase de passe présente"
```

```bash
ssh-keygen -p -f <cle-de-vps1>
```

La seconde commande ne sert que si la première a répondu « SANS ». Retire
ensuite la clé de l'agent et du trousseau :

```bash
ssh-add -D; ssh-add -l
```

Ouvre enfin `~/.ssh/config` dans un éditeur. **Tout en haut du fichier**,
avant tout `Include` et tout `Host *`, colle ce bloc. ssh garde la première
valeur qu'il lit : un `Host *` placé avant l'emporterait.

```
# Pharmaflux, mission 10 : la clé de vps1 (root) ne passe jamais par l'agent ni le trousseau.
Host vps1
    IdentitiesOnly yes
    IdentityAgent none
    AddKeysToAgent no
    UseKeychain no
    ControlMaster no
    ControlPath none
```

Vérifie le résultat : la commande doit échouer avec le code 255, car sans
terminal personne ne peut taper la phrase de passe.

```bash
ssh -o BatchMode=yes vps1 true; echo "vps1 sans phrase -> $?"
```

Désormais, tu tapes ta phrase de passe à chaque `ssh vps1`.

## Étapes 1 à 10, sur le VPS (session `ssh vps1`)

Garde une session ouverte jusqu'à la fin, et pose le nom choisi :

```bash
CODEUR=<utilisateur-codeur>
```

**1. Relever l'état.**

```bash
grep VERSION_ID /etc/os-release; systemctl --version | head -1
systemctl is-active polkit.service; command -v nft setfacl; systemctl is-enabled nftables.service
sudo sshd -T | grep -iE '^(usepam|passwordauthentication|allowusers|allowgroups|authorizedkeysfile) '
getent passwd 2101; getent group 2101; getent passwd 1001
```

Attendu : `passwordauthentication no`. Si `allowusers` ou `allowgroups`
s'affiche, ajoute le compte du codeur à la ligne correspondante à l'étape 4.
L'UID 2101 doit être libre. 1001 est celui de `nextjs` dans l'image d'Alamel :
on s'en tient loin.

**2. Paquets, seulement s'il en manque.**

```bash
sudo apt-get install -y polkitd nftables acl
```

`nftables.service` doit rester **désactivé** : son fichier commence par
`flush ruleset`, qui effacerait les règles de Docker et de fail2ban. Le filtre
de Pharmaflux vit dans sa propre table (étape 6).

**3. Les deux comptes et les dossiers.**

```bash
sudo useradd --system --user-group --no-create-home --home-dir /srv/pharmaflux/derive --shell /usr/sbin/nologin pharmaflux-chaine
sudo usermod -aG pharmaflux pharmaflux-chaine
sudo useradd --uid 2101 --user-group --create-home --shell /bin/bash "$CODEUR"
sudo usermod -p '*' "$CODEUR"
sudo usermod -aG pharmaflux,pharmaflux-chaine "$CODEUR"
sudo chfn -o umask=0027 "$CODEUR"
echo "$CODEUR" | sudo tee -a /etc/cron.deny > /dev/null
sudo install -d -m 0755 -o root -g root /srv/pharmaflux /etc/pharmaflux /etc/pharmaflux/compose
sudo install -d -m 2750 -o "$CODEUR" -g pharmaflux-chaine /srv/pharmaflux/code
sudo install -d -m 2750 -o pharmaflux-chaine -g pharmaflux-chaine /srv/pharmaflux/derive
sudo install -d -m 2750 -o root -g pharmaflux-chaine /srv/pharmaflux/modeles
sudo install -m 0755 -o root -g root /home/pharmaflux/.local/bin/uv /usr/local/bin/uv
id pharmaflux-chaine; id "$CODEUR"; sudo -l -U "$CODEUR"
```

Attendu :
- le codeur n'est que dans son groupe, `pharmaflux` et `pharmaflux-chaine` ;
- `sudo -l -U` répond qu'il n'a droit à rien ;
- `/srv/pharmaflux` reste à root, pour que le codeur ne puisse ni renommer ni
  remplacer `derive` ou `modeles`.

**4. La clé du codeur, sur son seul compte, sans terminal ni renvoi.** Colle la
ligne publique que tu auras créée sur le Mac (étape 11).

```bash
sudo install -d -m 0755 -o root -g root /etc/ssh/authorized_keys.d
printf 'restrict %s\n' '<ligne de ~/.ssh/pharmaflux_codeur_ed25519.pub>' | sudo tee "/etc/ssh/authorized_keys.d/$CODEUR" > /dev/null
sudo chmod 0644 "/etc/ssh/authorized_keys.d/$CODEUR"
sudo tee /etc/ssh/sshd_config.d/60-pharmaflux-codeur.conf > /dev/null <<EOF
# Pharmaflux : le compte du codeur. Sa clé est dans un fichier qu'il ne peut pas écrire ;
# ni terminal, ni renvoi de port ou d'agent, ni fichier rc.
Match User $CODEUR
    AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u
    AuthenticationMethods publickey
    DisableForwarding yes
    PermitTTY no
    PermitTunnel no
    PermitUserRC no
EOF
sudo sshd -t && echo "configuration valide"
sudo sshd -T -C "user=$CODEUR,host=essai,addr=203.0.113.1" | grep -iE '^(authorizedkeysfile|disableforwarding|permittty) '
sudo sshd -T -C "user=ubuntu,host=essai,addr=203.0.113.1" | grep -iE '^(authorizedkeysfile|disableforwarding|permittty) '
sudo systemctl reload ssh.service
```

La seconde vérification prouve que le bloc ne touche pas à `ubuntu`.

**5. Polkit : piloter sans sudo.** La liste est **vide au départ**. beko y
ajoute un nom seulement **après** avoir installé le fichier de l'unité
(étape 12). Un nom sans fichier laisserait créer, par `systemd-run`, une unité
transitoire de ce nom, qui tournerait en root.

```bash
sudo tee /etc/polkit-1/rules.d/60-pharmaflux-codeur.rules > /dev/null <<EOF
// Pharmaflux : ce que le compte du codeur peut demander à systemd et à logind.
// Liste EXACTE d'unités dont le fichier est déjà installé, jamais de motif.
polkit.addRule(function (action, subject) {
    if (subject.user !== "$CODEUR") {
        return polkit.Result.NOT_HANDLED;
    }
    var unites = [];
    var verbes = ["start", "stop", "restart", "reset-failed"];
    if (action.id === "org.freedesktop.systemd1.manage-units" &&
        unites.indexOf(action.lookup("unit")) >= 0 &&
        verbes.indexOf(action.lookup("verb")) >= 0) {
        return polkit.Result.YES;
    }
    if (action.id.indexOf("org.freedesktop.systemd1.") === 0 ||
        action.id.indexOf("org.freedesktop.login1.") === 0 ||
        action.id.indexOf("org.freedesktop.policykit.") === 0) {
        return polkit.Result.NO;
    }
    return polkit.Result.NOT_HANDLED;
});
EOF
sudo chmod 0644 /etc/polkit-1/rules.d/60-pharmaflux-codeur.rules
sudo journalctl -u polkit.service -n 5 --no-pager
```

**6. Le filtre de sortie : ni Alamel, ni Docker, ni les métadonnées.** Une table
à part, rechargée à chaque démarrage.

```bash
sudo tee /etc/pharmaflux/sortie.nft > /dev/null <<EOF
#!/usr/sbin/nft -f
# Pharmaflux : ce que les comptes du codeur et de la chaîne peuvent joindre.
# Une table à part, jamais de flush ruleset : Docker et fail2ban gardent les leurs.
table inet pharmaflux_sortie
delete table inet pharmaflux_sortie
table inet pharmaflux_sortie {
    set ports_pharmaflux {
        type inet_service
        elements = { 16333, 18081, 18082, 19092, 19644 }
    }
    chain sortie {
        type filter hook output priority filter; policy accept;
        meta skuid "pharmaflux-chaine" jump chaine
        meta skuid "$CODEUR" jump codeur
    }
    chain chaine {
        ct state established,related accept
        ct original ip daddr 127.0.0.1 ct original proto-dst @ports_pharmaflux accept
        counter drop
    }
    chain codeur {
        ct state established,related accept
        ct original ip daddr 127.0.0.1 ct original proto-dst @ports_pharmaflux accept
        ct original ip daddr 127.0.0.53 ct original proto-dst 53 accept
        ip daddr { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.168.0.0/16, 224.0.0.0/4 } counter drop
        ip6 daddr { ::1, fc00::/7, fe80::/10, ff00::/8 } counter drop
        tcp dport 443 accept
        counter drop
    }
}
EOF
sudo nft -c -f /etc/pharmaflux/sortie.nft && echo "syntaxe valide"
sudo tee /etc/systemd/system/pharmaflux-sortie.service > /dev/null <<'EOF'
[Unit]
Description=Pharmaflux : filtre de sortie des comptes du codeur et de la chaîne
DefaultDependencies=no
After=local-fs.target
Wants=network-pre.target
Before=network-pre.target shutdown.target
Conflicts=shutdown.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/pharmaflux/sortie.nft
ExecReload=/usr/sbin/nft -f /etc/pharmaflux/sortie.nft
ExecStop=/usr/sbin/nft delete table inet pharmaflux_sortie

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now pharmaflux-sortie.service
```

Le codeur garde HTTPS sortant (443) pour `uv sync`, et rien d'autre vers
Internet.

**7. Un plafond pour tout ce que lancent ses sessions**, sous-agents compris,
pour que la machine ne parte jamais en échange quand Alamel redémarre.

```bash
sudo install -d -m 0755 /etc/systemd/system/user-2101.slice.d
printf '[Slice]\nMemoryHigh=384M\nMemoryMax=512M\nTasksMax=200\nCPUQuota=100%%\n' | sudo tee /etc/systemd/system/user-2101.slice.d/50-pharmaflux-codeur.conf > /dev/null
sudo systemctl daemon-reload
systemctl show user-2101.slice -p MemoryMax -p TasksMax
```

**8. Le journal de Pharmaflux, et rien d'autre.** Les unités de la chaîne et
des conteneurs écrivent dans l'espace `pharmaflux` (`LogNamespace=pharmaflux`).
Le journal du système (sshd, sudo, fail2ban) reste fermé au codeur.

```bash
MID=$(cat /etc/machine-id)
sudo install -d -m 2750 -o root -g systemd-journal "/var/log/journal/$MID.pharmaflux"
sudo setfacl -m "u:$CODEUR:r-x,d:u:$CODEUR:r-x" "/var/log/journal/$MID.pharmaflux"
printf '[Journal]\nSystemMaxUse=200M\n' | sudo tee /etc/systemd/journald@pharmaflux.conf > /dev/null
```

**9. Vérifier le cloisonnement**, avant d'ouvrir l'accès depuis le Mac.

```bash
sudo -u "$CODEUR" touch /home/pharmaflux/pharmaflux-data/.essai; echo "écriture dans l'archive -> $?"
sudo -u "$CODEUR" ls /home/ubuntu; echo "dossier de beko -> $?"
sudo -u "$CODEUR" docker ps; echo "docker -> $?"
sudo -u "$CODEUR" sudo -n true; echo "sudo -> $?"
sudo -u "$CODEUR" systemctl reset-failed pharmaflux-collecte.service; echo "collecte -> $?"
sudo -u "$CODEUR" systemd-run --unit=pharmaflux-essai.service /bin/true; echo "unité transitoire -> $?"
sudo -u "$CODEUR" timeout 5 bash -c 'exec 3<>/dev/tcp/127.0.0.1/3100'; echo "port d'Alamel -> $?"
sudo -u "$CODEUR" timeout 5 bash -c 'exec 3<>/dev/tcp/169.254.169.254/80'; echo "métadonnées -> $?"
sudo -u "$CODEUR" ls /home/pharmaflux/pharmaflux-data/manifeste; echo "lecture de l'archive -> $?"
```

Attendu : **toutes les lignes en code non nul, sauf la dernière**, qui liste le
manifeste. Une seule ligne à 0 parmi les autres : tu t'arrêtes et tu me colles
la sortie.

**10. Rien d'Alamel ne redémarre seul.**

```bash
docker inspect -f '{{.Name}} {{.HostConfig.RestartPolicy.Name}} {{.State.Status}}' alamel-app alamel-postgres alamel-minio
```

Attendu : `unless-stopped` et `exited` pour les trois.

## Étapes 11 à 13, sur le Mac

**11. La clé du codeur**, sans phrase de passe, puisque les sessions n'ont pas
de terminal. Sa ligne publique ne va qu'à l'étape 4 : ni chez `ubuntu`, ni sur
GitHub.

```bash
ssh-keygen -t ed25519 -N '' -C pharmaflux-codeur -f ~/.ssh/pharmaflux_codeur_ed25519
cat ~/.ssh/pharmaflux_codeur_ed25519.pub
```

**12. L'alias `pharmaflux-vps`**, à coller **en haut** de `~/.ssh/config`,
juste sous le bloc `vps1` de l'étape 0. `HostName` et `Port` sont ceux que
donne `ssh -G vps1 | grep -E '^(hostname|port) '`.

```
Host pharmaflux-vps
    HostName <hote>
    Port <port>
    User <utilisateur-codeur>
    IdentityFile ~/.ssh/pharmaflux_codeur_ed25519
    IdentitiesOnly yes
    IdentityAgent none
    ForwardAgent no
    ClearAllForwardings yes
    RequestTTY no
    PermitLocalCommand no
    ControlMaster no
    ControlPath none
    BatchMode yes
    StrictHostKeyChecking yes
```

`StrictHostKeyChecking yes` suppose que l'empreinte du VPS est déjà connue
(c'est le cas, par `vps1`). Si `vps1` a un `HostKeyAlias`, ajoute la même ligne.

**13. Essais**, dans Terminal.app, par toi :

```bash
ssh pharmaflux-vps 'id; umask'
```

```bash
ssh pharmaflux-vps sudo -n true; echo "sudo -> $?"
```

```bash
ssh -l ubuntu pharmaflux-vps true; echo "clé du codeur sur ubuntu -> $?"
```

Attendu : la première affiche le compte, ses groupes et `0027`. Les deux
suivantes échouent.

## Avant de lancer la session du codeur

Commite sur `main` le travail de l'IeC (garde-fou et ses tests, permissions,
`CLAUDE.md`, ordre de la mission 10, ce fichier), pousse-le, puis avance la
branche du codeur, qui n'a encore rien committé :

```bash
git -C ../pharmaflux-codeur merge --ff-only main
```

Le garde-fou que lit une session est celui de **son** dossier : sans cette
avance, le codeur n'aurait pas la règle `ssh`.

Facultatif : pour que la session du codeur ne demande pas une confirmation à
chaque `ssh`, écris toi-même, dans son dossier, le fichier
`.claude/settings.local.json` (ignoré par git, et que le codeur ne peut pas
écrire) :

```json
{ "permissions": { "allow": ["Bash(ssh pharmaflux-vps:*)", "Bash(git archive:*)"] } }
```

Le garde-fou s'applique toujours.

## Installer un fichier que root lit (à chaque palier qui en livre un)

Une unité, un fichier compose ou une règle passe toujours par trois mains :
1. le codeur l'écrit dans sa branche ;
2. l'IeC le contrôle, au commit précis ;
3. beko l'installe depuis ce commit, **jamais depuis `/srv/pharmaflux/code`**,
   jamais par un lien.

```bash
git show <commit>:<chemin> | ssh vps1 'sudo tee /etc/systemd/system/<fichier> > /dev/null && sudo chmod 0644 /etc/systemd/system/<fichier> && sudo systemctl daemon-reload'
```

Pour un fichier compose, la cible est `/etc/pharmaflux/compose/<fichier>`.

Après le `daemon-reload` et **avant** d'ajouter le nom à polkit, colle à l'IeC :

```bash
systemctl show <unite> -p User -p Group -p SupplementaryGroups -p Environment -p EnvironmentFiles -p WorkingDirectory -p ExecStart -p ExecStartPre -p ExecStartPost -p ExecStop -p Conflicts -p AllowIsolate -p OnSuccess -p OnFailure -p FailureAction -p SuccessAction -p LogNamespace -p DropInPaths
```

```bash
sudo docker compose -p pharmaflux -f /etc/pharmaflux/compose/docker-compose.yml -f /etc/pharmaflux/compose/vps.yml config --format json
```

C'est la lecture de systemd et de Docker eux-mêmes, qu'aucune ruse de syntaxe
ne trompe. L'IeC y vérifie au moins :
- une unité de la chaîne tourne en `User=pharmaflux-chaine`, sans `+` ni `!`
  dans ses `Exec`, sans `Conflicts=` ni `AllowIsolate=yes` ;
- la règle vise ce que **root** lit ou lance (précisée par l'addendum 1 de la
  mission 10) :
  - une unité de la chaîne lance son `ExecStart=` sous
    `/srv/pharmaflux/code/courante/`, c'est son rôle, et passe ses chemins en
    arguments ; elle n'a **aucun `EnvironmentFile=`** (systemd le lit en root,
    et suivrait un lien), ni `WorkingDirectory=` ;
  - l'unité des conteneurs, qui tourne en root, ne nomme rien sous
    `/srv/pharmaflux` : ni `Exec`, ni `Environment`, ni fichier ;
- un complément d'unité (`.service.d/*.conf`) n'a qu'une section `[Unit]`,
  et pour la collecte, seulement `OnSuccess=` et `OnFailure=` vers
  `pharmaflux-chaine.service` ; le score de la collecte, relu après
  (`systemd-analyze security pharmaflux-collecte.service`), ne bouge pas ;
- dans le compose : des volumes nommés seulement, aucun montage de l'hôte,
  aucun `privileged`, `cap_add`, `user: 0`, `network_mode: host`, `pid` ou
  `docker.sock`, et des ports sur `127.0.0.1` seulement ;
- l'unité des conteneurs lance `docker compose -p pharmaflux` avec les deux
  fichiers de `/etc/pharmaflux/compose/`, `up -d --wait --pull never` au
  démarrage et `stop` à l'arrêt : jamais `down`, `rm` ni `-v`, qui effacent
  les conteneurs ou les volumes du projet, ni `prune`, qui effacerait aussi
  ce qui est arrêté, Alamel compris.

Une fois le contrôle passé, ajoute le nom à la liste `unites` de la règle
polkit (étape 5). Pour retirer une unité, l'ordre s'inverse : le nom d'abord,
le fichier ensuite.

## Clôture d'une mission

Une fois la PR fusionnée et le VPS revenu sur le code de `main` :

```bash
sudo usermod --expiredate 1 "$CODEUR"
sudo pkill -u "$CODEUR"
sudo chown -R root:pharmaflux-chaine /srv/pharmaflux/code
```

Puis, sur le Mac : supprime `~/.ssh/pharmaflux_codeur_ed25519` et sa partie
publique, et le bloc `pharmaflux-vps` de `~/.ssh/config`. Une mission suivante
reçoit une clé neuve.

Pour rouvrir le compte :

```bash
sudo usermod --expiredate '' "$CODEUR" && sudo chown -R "$CODEUR":pharmaflux-chaine /srv/pharmaflux/code
```

## Ce que le dispositif ne couvre pas

- **Le garde-fou n'arrête que les accidents.** Il juge le texte des commandes,
  pas ce que fait un script. La barrière réelle est sur le VPS (aucun sudo,
  polkit à liste exacte, filtre de sortie, droits Unix) et sur le Mac (la clé
  de `vps1` sous phrase de passe).
- **Un processus du codeur peut survivre à sa déconnexion** : Ubuntu garde
  `KillUserProcesses=no`. Pendant l'observation de 48 heures, beko vide la
  liste polkit : le codeur garde la lecture, rien d'autre.
- **La discipline « fichier d'abord, nom ensuite »** dans polkit n'a pas de
  contrôle automatique : elle repose sur beko.
