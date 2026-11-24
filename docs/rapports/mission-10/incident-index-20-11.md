# Mission 10 — l'étape `index` tuée cinq fois le 20/11 : analyse

## Synthèse

Le lot de la semaine est arrivé le vendredi 20/11 à 10:17 UTC. Cinq passages de suite, de 10:17
à 14:18, ont eu leur étape `index` tuée par le plafond de mémoire. Celui de 15:17 a réussi, sans
que personne n'intervienne.

**Ce que dit le code (question 1)**
- Chaque tentative garde ce qu'elle a fini, lot de 256 CIS par lot de 256 CIS. Les points écrits
  dans Qdrant restent, et le cache des vecteurs garde ce qui a été encodé.
- La tentative suivante retrouve donc ces fragments « inchangés », sans les réécrire ni les
  réencoder.
- Le bilan de 15:17 est compatible avec une reprise qui ne restait qu'à finir : 715 textes encodés
  et 944 écrits, pour 5 200 CIS touchés.
- Le journal ne dit pas combien chaque tentative a avancé : la mise à jour n'écrit rien pendant sa
  boucle.

**Qui est tué, et où (question 2)**
- C'est le processus principal de `index mettre-a-jour`, et non le sous-processus des fragments.
- Il est tué dans sa boucle d'écriture, après 200 à 1 030 s.
- Il y porte le modèle, l'encodage d'un lot entier, puis l'écriture du lot dans Qdrant en une
  seule requête.
- Le code de la mission 09 l'écrit lui-même : encoder et écrire en même temps fait monter le pic.
  C'est pour cela que `construire` encode d'abord tout, libère le modèle, puis écrit.
  `mettre-a-jour` ne le fait pas.

**Quel lot ne passerait jamais (question 3)** : la borne porte sur ce que contient un lot de
256 CIS, pas sur le nombre total de CIS touchés. Le journal ne permet pas de la chiffrer.

**Le remède (question 4)** : la voie (c), sans relever le plafond. Je propose de faire dans
`mettre-a-jour` ce que fait déjà `construire` :
- encoder d'abord dans le cache, par lots bornés, puis libérer le modèle ;
- écrire ensuite par lots bornés en nombre de points ;
- écrire une ligne de journal par lot.

Le calcul ne change pas. Relever `MemoryMax` ne donne aucune borne.

**Ce que l'incident change (question 5)** : la phrase « 450 jamais franchi » n'est plus vraie
depuis le 20/11, et la fraîcheur a un maximum de 18 253 s. L'ADR 0014, le README, le journal et
l'observation le disent dans le commit de l'observation. Le contrôle du palier 3 reste tel quel.

**Ce que je n'ai pas** : les journaux du noyau et de systemd sur les processus tués. beko les
relève demain. Ils trancheront ce qui reste ouvert à la question 2.

## Les faits, revérifiés

Le 24/11 vers 14:00 UTC, par `pharmaflux-vps`, en lecture seule, avec l'accord de beko. J'ai lu
`derive/chaine/passages.jsonl` (222 lignes) et `chaine etat --format json`. Les faits de l'IeC
se vérifient tous.

| passage | issue | durée | `index` : durée | `index` : résident | signal | morts |
|---|---|---|---|---|---|---|
| 20/11 10:17 | arrêté | 269,0 s | 234,0 s | 514 Mio | 9 | 1 |
| 20/11 11:17 | arrêté | 1 066,5 s | 1 053,4 s | 515 Mio | 9 | 1 |
| 20/11 12:17 | arrêté | 296,5 s | 283,8 s | 515 Mio | 9 | 1 |
| 20/11 13:17 | arrêté | 236,4 s | 222,8 s | 514 Mio | 9 | 1 |
| 20/11 14:18 | arrêté | 245,0 s | 232,1 s | 514 Mio | 9 | 1 |
| 20/11 15:17 | complet | 231,2 s | 218,3 s | 424 Mio | — | 0 |

**Les cinq tentatives tuées**
- Le pic du groupe est à 512 Mio, comme à chaque passage.
- Les quatre étapes d'avant sont en code 0. `silver` monte à 260 Mio à 10:17, en consommant
  10 817 messages, puis reste à 151 Mio.
- L'étape `index` ne garde que trois lignes d'erreur, celles d'onnxruntime sur `/proc/cpuinfo`.
  Elle n'écrit rien d'autre avant d'être tuée.

**Le passage de 15:17**
- Il reprend une mise à jour interrompue : 5 200 CIS touchés, tous par une version.
- Fragments : 239 ajoutés, 705 remplacés, 658 retirés, 17 997 inchangés.
- 715 textes encodés, 77 548 fragments au total, 199 s dans la boucle de mise à jour.
- Résident maximal : 390 Mo pour l'encodage et 444 Mo pour les fragments, en Mo décimaux.

**Depuis**
- 94 passages, tous en code 0.
- Les vérifications sont en code 0 chaque nuit, du 20/11 au 24/11, de 264,7 à 290,2 s, sans
  processus tué.
- `chaine etat` est `à jour`. Il compte 6 passages porteurs, avec un délai médian de 63 s et un
  maximum de 18 253 s : `CIS_bdpm`, arrivé le 20/11 à 10:17:24, est indexé à 15:21:21.
- Aucun lot n'est arrivé le mardi 24/11, jusqu'au passage de 13:17 inclus.

## 1. Chaque tentative tuée a-t-elle avancé ?

### Ce que garde le code d'une tentative à l'autre

`index mettre-a-jour` (`cli.py`, `index/construction.py`) suit cet ordre :

1. **Le verrou de l'index, puis l'état de Qdrant.** Le modèle est déclaré, mais sa session
   onnxruntime ne se charge qu'au premier texte à encoder (`_session`, chargement paresseux).
2. **Les fragments des CIS touchés**, depuis l'instant de l'index. Ils sont calculés par un
   sous-processus (`calculer_fragments`), qui les écrit dans `fragments.jsonl`. Cette phase dure
   environ 19 s : 218,3 s pour l'étape, contre 199 s pour la boucle.
3. **`mettre_a_jour`.**
   - Il écrit d'abord `vise` dans l'état de Qdrant. L'instant de l'index ne change qu'à la toute
     fin.
   - Puis il lit les fragments **par lots de 256 CIS** (`LOT_CIS`). Pour chaque lot, `_remplacer`
     fait cinq choses :
     1. il lit les points existants de ces CIS dans Qdrant ;
     2. il range chaque fragment en ajouté, remplacé ou inchangé, en comparant sa charge en JSON
        canonique ;
     3. il calcule le vecteur de tous les fragments à écrire du lot (`vecteurs_de`) : le cache
        d'abord, puis l'encodeur pour les autres. Les vecteurs nouveaux entrent dans le cache, une
        transaction SQLite validée **avant** l'écriture dans Qdrant ;
     4. il écrit tous ces points dans Qdrant en **une seule requête** (`PUT …/points?wait=true`) ;
     5. il retire les points qui ne sont plus dans le lot.

Une tentative tuée garde donc trois choses :
- **les lots finis**, écrits dans Qdrant. `wait=true` attend qu'ils soient appliqués ;
- **les vecteurs encodés**, jusqu'au dernier lot dont l'encodage s'est terminé, même si son
  écriture n'a pas eu lieu ;
- **`vise`**, qui fait dire « reprise d'une mise à jour interrompue » à la tentative suivante.

Une tentative tuée perd deux choses :
- **le lot en cours**, s'il est tué pendant son encodage : rien de ce lot n'entre dans le cache ;
- **le calcul des fragments**, refait à chaque tentative. Le même intervalle donne les mêmes
  fragments.

La tentative suivante relit les mêmes fragments. Un lot fini est vu « inchangé » : il n'est ni
encodé ni écrit. Un lot dont les vecteurs sont en cache est écrit sans encodage.

### Ce que montre le journal

- **Les fragments ont été calculés à chaque tentative, et la mort vient dans la boucle.** Le
  sous-processus a fini : s'il avait été tué, le processus principal aurait rendu le code 2
  (« calcul des fragments (code -9) »), et non le signal 9. Et chaque tentative dure de 223 à
  1 053 s, bien plus que les 19 s de ce calcul.
- **La tentative réussie n'a eu qu'une partie du travail à faire.**
  - Elle a écrit 944 points (239 + 705) et en a encodé 715. Les vecteurs des 229 autres étaient
    déjà en cache : ils viennent d'un encodage antérieur, d'une tentative tuée ou d'un texte
    identique déjà indexé.
  - Aux passages porteurs du 16/11 au 21/11, un CIS touché par une version a eu 12 à 50 % de
    ses fragments remplacés : 16/75, 4/8, 38/159 et 4/32.
  - À ces taux, les 18 941 fragments de ces 5 200 CIS (hors retraits) auraient demandé de
    2 400 à 9 500 écritures.
    La tentative de 15:17 n'en a fait que 944.
  - Les points écrits par les tentatives tuées sont comptés parmi les 17 997 « inchangés ».
- **Ce que je ne peux pas montrer** : l'avancée de chaque tentative. La boucle ne journalise
  rien, et ni Qdrant ni le cache ne datent leurs écritures. Le taux de remplacement des autres
  lots est un repère, pas une mesure de celui-ci.

### Avancée, ou hasard ?

Le succès de 15:17 vient de l'avancée des tentatives d'avant. Trois raisons :
- **Le travail diminue d'une tentative à l'autre** : c'est ce que garantit le code, lot par lot.
- **À 15:17, il ne restait que 944 points à écrire.** Le processus principal a culminé à 390 Mo
  décimaux (372 Mio), loin des 514 Mio des tentatives tuées.
- **Rien d'autre n'avait changé.** Même code, même plafond, même instant visé. Les étapes d'avant
  avaient le même résident (151 Mio pour `silver`) et la même durée.

L'état du cache de pages a pu peser sur le moment exact où chaque tentative est morte. Il ne peut
pas expliquer qu'une tentative passe avec 140 Mio de marge.

## 2. D'où viennent les 514 Mio, et les 1 053 s

### Ce que mesurent les chiffres

- **Le résident de l'étape** est le `ru_maxrss` que rend `wait4` : le plus gros résident du
  processus principal et des sous-processus qu'il a attendus.
- **Le processus tué est le processus principal.** Le signal 9 est rendu pour lui, et le
  sous-processus avait fini (point 1). Les 514-515 Mio sont donc son résident, ou celui du
  sous-processus s'il a culminé plus haut. Le journal ne distingue pas les deux cas.
- **Le pic du groupe est à 512 Mio à chaque passage, réussi ou non.** C'est le `MemoryPeak` de
  l'unité : il compte aussi le cache de pages, que le noyau reprend avant de tuer.

### Ce qui coexiste dans le groupe

Le groupe de `pharmaflux-chaine.service` contient trois processus, et le cache de pages.

| | résident (journal) | quand |
|---|---|---|
| `chaine passer` (le parent) | non mesuré | tout le passage |
| `index`, processus principal, sans modèle | 130 Mio (136 Mo) | début de l'étape, passages à vide |
| `index`, processus principal, avec modèle et encodage | 335 à 372 Mio (351 à 390 Mo) | passages porteurs, dont 15:17 |
| sous-processus des fragments | 400 à 432 Mio | pendant son calcul, avant la boucle |
| cache de pages (archive, Parquet, cache SQLite, bibliothèques) | ce que le noyau laisse | tout le passage |

- **Le sous-processus et la boucle ne se recouvrent pas.** Pendant le calcul des fragments, le
  processus principal attend, sans modèle (130 Mio). Leur somme dépasse 512 Mio en résident, mais
  une partie de ce résident est faite de pages de fichiers partagées (l'interprète, les
  bibliothèques) : le groupe ne les compte qu'une fois, et le noyau peut les reprendre. Cette
  phase passe à chaque passage.
- **Dans la boucle, le processus principal porte quatre choses :**
  - la session onnxruntime, chargée au premier texte à encoder ;
  - l'encodage de tous les fragments à écrire d'un lot. Il est découpé en appels de 1 024 jetons
    au plus (`BUDGET_JETONS`), et mesuré à 477 Mo sur les textes les plus longs ;
  - les fragments du lot et les charges existantes de ses 256 CIS ;
  - la requête d'écriture du lot entier. Chaque point y est une liste de 384 flottants Python,
    puis un dict, puis du JSON : plusieurs dizaines de Ko par point.

### Ce qui est établi, et ce qui ne l'est pas

**Établi**
- Le processus principal meurt dans la boucle.
- À 15:17, avec 944 points écrits en tout, il culmine à 372 Mio.
- Le code de la mission 09 a déjà mesuré l'effet de l'encodage pendant l'écriture : une
  construction qui faisait les deux à la fois passait de 418 à 586 Mo. `remplir_cache`
  (`construction.py`, l. 118-138) existe pour cela, mais `mettre_a_jour` ne s'en sert pas.

**Probable, non mesuré** : le pic vient d'un lot de 256 CIS lourd, celui où beaucoup de fragments
changent. Le modèle est alors chargé, et la requête d'écriture de tout le lot se construit
par-dessus. La part de chacun au moment de la mort n'est dans aucun fichier que je peux lire.

**Ce qui le tranchera** : la ligne du noyau, `Killed process … anon-rss:… file-rss:…`, que beko
relève demain. Elle dira le résident anonyme du processus tué, et `memory.stat` le reste du
groupe.

### Les 1 053 s de 11:17

- **L'hypothèse, non établie** : le processus a tourné longtemps juste sous le plafond, avant
  d'être tué. Au plafond, le noyau reprend le cache de pages à chaque allocation, et chaque page
  reprise (le modèle, les bibliothèques, le cache SQLite) se relit sur le disque : le travail
  avance très lentement.
- **Ce qui s'y accorde** : les autres tentatives meurent en 223 à 284 s, et la boucle complète
  de 15:17 a pris 199 s. Celle-ci a donc passé de longues minutes près de la limite, et non à
  avancer.
- **Ce qui le confirmera** : le compteur `max` de `memory.events` et la pression mémoire du
  groupe. Le journal des passages ne garde ni l'un ni l'autre. Les journaux de beko montreront
  au moins l'heure de la mort.

## 3. Quel lot ne passerait jamais ?

**La borne ne porte pas sur le nombre total de CIS touchés.**
- Chaque tentative finit au moins les lots qui tiennent dans la mémoire, et la suivante repart de
  là.
- Un lot de 5 200 CIS, ou de 20 000, finit donc par passer en plusieurs tentatives, une par
  heure, tant que chaque lot de 256 CIS tient. Le 20/11, il en a fallu six.

**Elle porte sur un seul lot de 256 CIS.** Un lot ne passe jamais quand il tue chaque tentative
sans rien laisser derrière lui. Deux cas :
- **mort pendant l'encodage du lot** : rien n'entre dans le cache. La tentative suivante refait le
  même travail et meurt au même endroit ;
- **mort pendant l'écriture du lot** : les vecteurs sont en cache. La tentative suivante écrit
  sans charger le modèle, si aucun lot d'avant ne l'a chargé : elle a une chance de passer.

**Ce que je ne peux pas chiffrer** : le nombre de fragments à écrire, dans un lot, au-delà duquel
il ne passe plus. Il faudrait le résident de chaque lot, que rien ne journalise.
- **Un ordre de grandeur, à titre indicatif** : un point coûte plusieurs dizaines de Ko pendant
  l'écriture. Il y a environ 3,6 fragments par CIS (77 548 pour 21 463 fiches), soit environ
  930 fragments par lot de 256 CIS, au plus quelques milliers pour les CIS riches en avis de la
  HAS.
- **La conclusion** : un lot de 256 CIS dont presque tous les fragments changent, sur des CIS
  riches en avis, est le cas le plus exposé.
- **Le pire scénario** : les avis d'une grande classe thérapeutique réévalués d'un coup, ou un
  changement d'extracteur qui touche tous les fragments d'avis. Il pourrait arrêter la chaîne
  jusqu'à un geste.

**Ce qui borne vraiment** : un lot défini par le nombre de points, et non par le nombre de CIS
(question 4).

## 4. Le remède

### La voie (c) : des lots bornés dans `mettre-a-jour`

Il s'agit de faire dans `mettre_a_jour` ce que `construire` fait déjà, sans toucher au calcul.

1. **Encoder d'abord**, comme `remplir_cache` : seulement les textes des fragments ajoutés ou
   remplacés, absents du cache.
   - Par lots de 256 textes au plus : le cache garde chaque lot dès qu'il est encodé, et une
     tentative tuée y perd au plus un lot, soit environ 47 s à 5,4 fragments/s.
   - Puis `liberer()` : la session du modèle est rendue avant toute écriture.
2. **Écrire ensuite** par lots bornés en nombre de points, par exemple 256 points par requête
   au plus, et non plus un lot de 256 CIS entier. Les retraits suivent le même découpage.
3. **Une ligne de journal par lot** : CIS faits sur CIS touchés, points écrits, encodés, résident
   courant. L'avancée d'une tentative tuée se lira alors dans le journal du passage.

Ce qui ne change pas :
- **les fragments, leurs identifiants, leurs charges et l'instant**. L'ordre « écrire d'abord,
  retirer ensuite » est gardé dans chaque lot : un CIS n'est jamais vide.
- **le calcul des fragments et le format de l'index**. Le témoin des formats ne bouge pas.

**Une réserve, à mesurer** : un vecteur dépend un peu de ses voisins de lot dans le modèle (la
quantification dynamique, cosinus ≥ 0,997, `encodeur.py`). Changer le découpage change donc les
voisins de quelques textes neufs.
- Le cache fige le vecteur obtenu, et `index verifier` compare l'index au cache, avec un
  échantillon réencodé au cosinus de 0,99 au moins.
- Le verdict sur le jeu de démo doit rester « conforme ». La CI le montre, et le rapport le cite.
- C'est la condition de l'addendum 1, question 4.

**Ce que la voie (c) demande**
- **Au codeur** : le code, ses tests, la CI de la PR et le contrôle de l'IeC.
  - Les tests : la reprise après une coupure à chaque lot, la mémoire bornée par un encodeur de
    test, et le même index final qu'avant sur le jeu de démo.
  - Le dépôt sous le verrou, comme pour `f35d797`.
- **À beko** : rien. Aucun fichier que root lit ne change, et aucune unité ne se réinstalle.
- **L'observation** : la preuve est le prochain gros lot de la BDPM, passé en un seul passage
  sans processus tué. D'ici là, l'observation continue sur la nouvelle version. Les passages à
  vide montrent qu'elle ne régresse pas, et la vérification de 03:40 la contrôle chaque nuit.

### Contre elle : relever le `MemoryMax` du passage

- **De combien ?** On ne le sait pas. Le pic d'un lot n'a pas de borne dans le code actuel : il
  croît avec le nombre de fragments à écrire. On peut seulement prendre une marge au-dessus des
  514 Mio observés, par exemple `768M`, sans savoir si le prochain lot y tiendra.
- **La somme des 2 Go, mesurée comme au point B**, c'est-à-dire la somme des pics :
  - aujourd'hui : Redpanda 464,2 + Qdrant 470,4 + chaîne 512 + collecte 104,3 =
    1 550,9 Mio (relevés du 17/11) ;
  - avec `768M`, et une chaîne qui monterait jusqu'au plafond : 1 806,9 Mio, sous 2 048 Mio ;
  - mais la somme des **plafonds** passerait de 2 304 à 2 560 Mio. Et depuis le 18/11, Alamel
    tourne à côté sans plafond pour son application, Postgres et MinIO. Le VPS a 3 814 Mio en
    tout.
- **Ce qu'elle demande** :
  - un fichier que root lit change (`pharmaflux-chaine.service`) : la branche, le contrôle de
    l'IeC, puis l'installation par beko, `daemon-reload` et les empreintes comparées ;
  - le même geste pour `pharmaflux-remplissage.service` et `pharmaflux-verification.service`,
    si l'on veut la même règle partout ;
  - la même observation que la voie (c), sur le prochain gros lot.

### Mon avis : la voie (c), sans toucher au plafond

- **Elle supprime la cause.** Le pic ne dépendra plus de la taille d'un lot de la BDPM. Relever le
  plafond la déplace, et il ne borne rien.
- **Elle est déjà écrite dans le dépôt.** C'est `remplir_cache` puis `liberer`, la leçon de la
  mission 09, que `mettre-a-jour` n'applique pas.
- **Elle rend l'avancée lisible**, ce qui manque à cette analyse.
- **Elle ne demande aucune installation à beko**, et garde la somme des plafonds à 2 304 Mio.
- **Elle a un coût** : un dépôt de code au milieu de l'observation, à décider par l'IeC.
  - Si on le fait maintenant, l'observation repart sur la nouvelle version, et le prochain gros
    lot en est la preuve.
  - Si on le fait après la clôture, la mission se ferme avec un défaut connu, écrit dans
    l'ADR 0014. Ce défaut se rattrape seul, comme le 20/11, avec un délai de quelques heures.
- **Si l'IeC veut une marge tout de suite**, sans dépôt : `768M`, en le disant provisoire, à
  retirer quand la voie (c) sera déployée.

## 5. Ce que l'incident change

**ADR 0014, Conséquences**
- « Le plus gros processus … monte à 432 Mio au plus … aucun processus n'a été tué » n'est plus
  vrai. Il faut écrire les cinq morts du 20/11, la reprise seule en six passages, et la cause
  dans `mettre-a-jour`.
- La fraîcheur passe à 6 passages porteurs, avec un délai médian de 63 s et un maximum de
  18 253 s.
- « À surveiller » gagne la taille des lots de la BDPM, et la voie retenue à la question 4.

**README, l'état de la mission 10**
- « 99 passages horaires, tous complets » devient les chiffres finaux, avec les cinq passages
  arrêtés du 20/11 et leur reprise sans geste.
- Le délai médian reste à 63 s. Il faut y ajouter le maximum.

**Le journal**
- Une entrée de plus, en fin de fichier : l'incident du 20/11, et la décision de l'IeC.
- L'entrée du palier 3 reste ce qu'elle était au 19/11.

**Le palier 3**
- `palier-3.md` et `controle-palier-3.md` restent tels quels. Ce qu'ils disent était vrai au
  19/11.
- Les faits nouveaux vont dans le commit de l'observation, comme la retouche 5 du contrôle le
  prévoit.

**L'observation** (`observation.md`, non commité)
- une section pour le 20/11 : les six tentatives, et un renvoi vers ce fichier ;
- la fraîcheur, avec ses six passages porteurs ;
- la clôture : un lot de la semaine est bien arrivé (le vendredi 20/11, au lieu du mardi), et il
  est passé de la collecte à l'index sans geste de personne, avec un délai de 18 253 s.

**La clôture** (addendum 1)
- La condition « sans geste de personne » est tenue.
- « Pharmaflux reste sous 2 Go résidents » aussi : la chaîne a été tuée sous son propre plafond,
  et n'a pas débordé.
- C'est à l'IeC de dire si une étape tuée cinq fois compte comme une chaîne « qui se vérifie et se
  reprend », ou comme un défaut qui demande la voie (c) avant la fusion.

## Ce qui reste

1. La décision de l'IeC sur le remède, et sur le moment du dépôt.
2. Les journaux du noyau et de systemd de beko, le 25/11. Ils diront le résident anonyme du
   processus tué, et si 11:17 a passé ses minutes au plafond.
3. Le commit de l'observation, après cette décision. Il portera aussi les retouches 1 à 5 du
   contrôle du palier 3, déjà préparées dans l'arbre.
