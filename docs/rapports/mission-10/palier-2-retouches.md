# Mission 10 — palier 2 : les retouches du contrôle

## Synthèse

**Fait** : les trois retouches de `controle-palier-2.md`, dans un commit, avec le fichier de
contrôle commité tel quel.

**Vérifications locales** (arbre propre avant le commit) : vertes.
- ruff, `format --check` et mypy (101 fichiers) passent.
- `uv run pytest -q` : 1040 tests passent et 14 d'intégration sautent, sans service.

**Les unités ne changent pas.** Les quatre empreintes sont celles du tableau du contrôle :
`git diff --stat 95a35ac` est vide sur ces fichiers.

**Écarts** : aucun. **Questions** : aucune.

Ensuite :
1. beko pousse, la CI de la PR doit être verte, puis l'IeC contrôle.
2. Je dépose sous le verrou, et je cite la bascule, les droits et
   `git diff --stat eecc9f3 <commit> -- src`.

## Détail

**1. `chaine etat` : la première ligne dit tout** (`src/pharmaflux/chaine/etat.py`).

Le verdict du passage horaire s'enrichit de trois cas :
- **un échec circonscrit** : un passage en code 1, sans `arret`, avec des `signalements`, se
  lit `échec circonscrit au dernier passage (publier : …)`, et non plus `en panne (code 1)` ;
- **une vérification en échec** : on ajoute `; vérification en échec (code N, étape X)`. L'étape
  est celle de l'arrêt, ou celles des échecs circonscrits ;
- **une vérification trop ancienne** : au-delà de 26 h (`VERIFICATION_MAX_H`, un jour et deux
  heures de marge), on ajoute `; dernière vérification il y a N h`. S'il n'y en a aucune alors
  que le premier passage horaire a plus de 26 h, on ajoute `; aucune vérification depuis la
  mise en service, il y a N h`.

La ligne `vérification` finit par son âge (`, il y a N h`), et le JSON porte
`age_verification_h`.

Les tests sont dans `tests/test_chaine_horaire.py`, un par cas :

| cas | test |
|---|---|
| vérification récente et conforme | `test_une_verification_recente_et_conforme_laisse_le_verdict` |
| vérification en échec | `test_une_verification_en_echec_entre_dans_le_verdict` |
| vérification de plus de 26 h | `test_une_verification_de_plus_de_26_heures_entre_dans_le_verdict` |
| aucune vérification après 26 h de service | `test_aucune_verification_apres_26_heures_de_service` |
| aucune vérification avant 26 h | `test_aucune_verification_avant_26_heures_ne_dit_rien` |
| échec circonscrit | `test_un_echec_circonscrit_est_nomme_avec_son_etape` |

**2. `infra/vps/README.md`, étape 9.**
- Avant 9b, « Avant 9b, le code » : le dépôt et la bascule sous le verrou (4a). beko vérifie
  le lien par `ls -l /srv/pharmaflux/code/courante`.
- En 9b, dans l'ordre :
  1. le minuteur ;
  2. une vérification (`sudo systemctl start pharmaflux-verification.service`) ;
  3. à coller à l'IeC : `systemctl show … -p Result -p ExecMainStatus` et `chaine etat`.
     Si ce n'est pas `success` et 0, on s'arrête ;
  4. seulement ensuite, le complément de la collecte, entre deux passages.

**3. `src/pharmaflux/chaine/formats.py`.** Le commentaire de `EMPREINTE_SILVER` renvoie
désormais à `tests/test_chaine_horaire.py::test_le_numero_du_silver_suit_son_schema`.

**Les empreintes des unités** (`shasum -a 256`, huit premiers caractères) :

| fichier | sha256 |
|---|---|
| `pharmaflux-chaine.service` | `dd8234f6` |
| `pharmaflux-verification.service` | `52d180b4` |
| `pharmaflux-verification.timer` | `f7890ec7` |
| `pharmaflux-collecte.service.d/chaine.conf` | `fe92cab7` |
