# Mission 10 — contrôle du correctif MemoryDenyWriteExecute (IeC)

**Commit contrôlé** : `e12c14d1c2e68047293a0ab2b798e41317f1402c` · **Date** : 14/11/2026
**Verdict : accepté.** beko peut installer les deux unités à ce commit.

## Le défaut

Le 14/11, la collecte passe sur `main` (étape 0, vers 21 h UTC). Dès lors,
chaque passage meurt en 2 s : à 21:02 (lancé à la main), à 21:17 et à 22:17.

- `pharmaflux collecte` importe numpy au démarrage, par
  `evaluation.verification` puis `index.lexical` (code de la mission 09).
- OpenBLAS, chargé par numpy, ne peut pas créer son fil :
  `pthread_create … Permission denied`.
- OpenBLAS s'envoie alors SIGINT : on lit `status=2/INT` et `Result=signal`.

**La cause**, établie par le codeur et vérifiée sur le VPS :
- le `python3.12` installé par uv n'a pas d'en-tête `GNU_STACK` ;
- sur x86_64, glibc donne alors une pile exécutable à chaque fil ;
- sur ce VPS (noyau 7.0, systemd 259), `MemoryDenyWriteExecute=yes` refuse
  cette pile par EACCES : aucun fil ne peut naître.

La preuve directe tient en deux essais, faits hors unité, dans le processus
du codeur. Après `prctl(PR_SET_MDWE, REFUSE_EXEC_GAIN)` :
- le Python d'uv ne peut plus créer de fil ;
- le Python du système, qui a l'en-tête, le peut.

L'unité de remplissage avait la même directive. Elle aurait échoué dès sa
première étape, puisque la chaîne, numpy et onnxruntime créent tous des fils.

**Le retour en service** : la collecte a été remise par beko à `67d9d3c` (le
commit d'avant l'étape 0), avec un passage manuel à 22:48 UTC.
- Le résultat : 12 fichiers inchangés, 0 erreur.
- Rien n'est perdu : les sources n'avaient pas changé.

## Ce que l'IeC a vérifié

- **Le diff des deux unités** (`eecc9f3..e12c14d`) : seule la ligne
  `MemoryDenyWriteExecute=true` est retirée, et un commentaire dit pourquoi.
  Aucune autre directive ne change.
- **L'unité de la collecte installée** est identique, à l'octet, à celle de
  `main` (sha256 `97b173fc…`). Installer celle de `e12c14d` ne change donc
  que cette ligne.
- **Les autres fichiers que root lit** (compose, `vps.yml`, l'unité des
  conteneurs) n'ont pas changé depuis `13168f5`. L'unité des conteneurs
  garde la directive : elle ne lance que le client docker.
- **Le score hors ligne ne bouge pas** : 1,1 pour le remplissage, 1,3 pour la
  collecte. La directive pèse 0,1 et ne change pas l'arrondi.
- **Le nouveau test** refuse la directive dans les deux unités Python, pour
  qu'elle ne revienne pas.

## Ce qui reste

1. **beko** installe les deux unités depuis `e12c14d`. L'IeC compare leurs
   empreintes : remplissage `f9b05d8e…`, collecte `3a0d0834…`.
2. **beko** refait l'étape 0 (`git checkout main`, `pull`, `uv sync`), puis
   lance un passage à la main. Ce passage est la preuve sous l'unité.
3. **Au palier 2**, le codeur met à jour les deux README qui désignaient
   encore la directive comme « à soupçonner d'abord ».
4. **Le codeur** dit par quelle commande il a lancé l'essai `prctl` sur le
   VPS. Un programme passé par `-c` ou par l'entrée standard ne passe pas le
   garde-fou. S'il est passé autrement, c'est un trou du garde-fou, à
   signaler et non à réutiliser.
