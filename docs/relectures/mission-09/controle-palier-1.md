# Mission 09 — contrôle du palier 1 par l'IeC

**Commit contrôlé** : `dff0a34` (collecte et extraction des pages d'avis),
revu contre l'ordre et l'addendum 1 (`main`, `a7df8ef`).
**Verdict : palier 1 accepté. beko peut lancer la collecte de la première
étape** avec la commande du rapport. Aucune correction n'est demandée avant
la collecte.

## Revérifié par l'IeC

Dans ton dossier, arbre propre sur `dff0a34` :

| commande | résultat |
|---|---|
| `uv run ruff check .` / `uv run mypy src` | verts (86 fichiers) |
| `GITHUB_ACTIONS=true uv run pytest -q -rE -rs` | **810 passed** en 6 min 10 |
| `has collecter --simuler --racine ~/pharmaflux-data` | 746 dossiers, 720 avec un lien, **722 pages**, 724 requêtes, ≈ 26 min, plafond conseillé 761 ; 0 déjà archivée. C'est ce que j'avais recalculé à l'addendum |
| `has extraire --verifier --page …` (trois pages et la page de mesure d'audience) | 3 extraites, 1 rejetée (`jsonld_absent`), 3 conformes, 0 écart, 0 divergence |
| `~/pharmaflux-data/manifeste/has-pages.jsonl` | absent : rien n'a été collecté avant beko |

Lus dans le code :
- **Seules des pages d'avis peuvent partir.** Le périmètre ne garde que les
  URL de la forme exacte `https://www.has-sante.fr/jcms/(p|c)_N`. Une autre
  forme est comptée « hors forme » et n'est pas demandée. Les deux autres
  URL (`robots.txt`, les mentions légales) sont des constantes du code. Une
  ligne du fichier des liens, qui est de la donnée, ne peut donc pas
  envoyer une requête ailleurs.
- **Le client est poli par construction.** La pause est tenue avant toute
  requête, réessai compris, et ne descend jamais sous 2 s. Le plafond est
  vérifié avant l'envoi, sans redirection suivie. Le client s'arrête net au
  premier 429 ou à la seconde défaillance d'affilée, sans aucun cookie
  écrit.
- **`robots.txt`** est lu au début du passage, et chaque URL passe par
  `can_fetch`. S'il est illisible, la commande refuse ; s'il ne répond pas,
  elle s'arrête.
- **Le second lecteur** ne reprend de l'extracteur que le type de son
  résultat (`AvisExtrait`), aucun code d'analyse : c'est ce que demandait
  l'addendum.
- **La garde réseau des tests** coupe la résolution et la connexion vers
  tout hôte qui n'est pas la machine. `test_reseau.py` l'éprouve pour
  plusieurs clients.

Les quatre décisions prises en codant sont acceptées. Elles vont dans le
sens de l'ordre : refuser ou arrêter selon le cas, n'archiver `robots.txt`
et les mentions que s'ils changent, prendre le texte de `<main>`, et
`--simuler` sans plafond.

## À faire au palier 2 (non bloquant pour la collecte)

1. **Respecter un `Crawl-delay`** s'il apparaît dans `robots.txt` : la pause
   devient alors `max(pause, crawl_delay)`. Le fichier du 31/10 n'en a pas,
   d'où le caractère non bloquant. Mais une collecte périodique future
   doit le suivre. Ajoute un test.
2. **Citer la sortie de beko** dans un commit à part, avant le palier 2,
   comme prévu :
   - le bilan, avec les mentions légales (une première référence, donc
     « nouveau ») ;
   - le nombre de pages archivées, rejetées et en erreur, par statut et par
     motif ;
   - les requêtes envoyées contre le plafond ;
   - la durée et le résident ;
   - la sortie de `has extraire --verifier`.

   Si une page est rejetée, nomme son motif : elle peut fournir la question
   piège « page rejetée » de la v2.
3. **Si la collecte sort en code 3**, ne relance rien toi-même : dis-le à
   beko et à l'IeC, avec le message d'arrêt. La relance se décide après
   lecture.
