# Pharmaflux : la démo en deux commandes, « make up » puis « make demo » (mission 04, ADR 0008),
# puis « make silver » pour le silver Iceberg et sa vérification contre l'archive (mission 05, ADR 0009),
# puis « make gold » pour les contrôles de qualité et les questions recalculées depuis le gold
# (mission 06, ADR 0010), puis « make index » pour l'index de l'assistant (mission 07, ADR 0011).
#
# GNU Make 3.81 (celui des outils de ligne de commande du Mac) suffit : recettes en tabulations,
# .PHONY, « ?= », rien de 3.82 ni de 4.x. Les agents Claude Code ne lancent que « make -n <cible> » ;
# « make <cible> » est à beko et à la CI. Aucune cible ne télécharge une image (--pull never, les
# prérequis refusent avant), aucune ne nomme autre chose que le projet compose « pharmaflux ».
# make s'arrête à la première commande en échec : le code de sortie de « make demo » est celui
# de la démo, et verifier-bus a le dernier mot.

COMPOSE = docker compose -p pharmaflux
PHARMAFLUX = uv run pharmaflux
DEMO_OPTIONS ?=
SORTIE_DEMO = data/demo
JEU = demo/archive
ENTREPOT_DEMO = $(SORTIE_DEMO)/lakehouse
# make etat ENTITE=bdpm.presentations A=2026-10-26T14:00:00Z [ETAT_OPTIONS="--ou code_cip13=…"]
ENTITE ?= bdpm.presentations
A ?= 2026-10-26T14:00:00Z
ETAT_OPTIONS ?=
# make fiche CIS=65999556 [A=2026-10-24T20:00:00Z] [FICHE_OPTIONS="--format jsonl"] ; sans A sur la
# ligne de commande (le défaut de A sert à make etat), la dernière observation du silver.
CIS ?= 65999556
FICHE_A = $(if $(filter command line,$(origin A)),--a $(A),)
FICHE_OPTIONS ?= --format texte
# make index [INDEX_MODELE=test] : le modèle épinglé par défaut ; « test » pour l'encodeur de test
# (la CI, sans téléchargement).
INDEX_MODELE ?= e5-small-int8
INDEX_OPTIONS = --entrepot $(ENTREPOT_DEMO) --modele $(INDEX_MODELE)

.PHONY: help prerequis up demo verifier suivre console down rebatir verifications silver etat \
	gold fiche index

help:
	@echo "make up             vérifie les prérequis (images déjà présentes) et démarre le bus"
	@echo "make demo           up, enregistre les schémas, rejoue demo/archive sur le bus à la cadence"
	@echo "                    accélérée, puis verifier-bus ; DEMO_OPTIONS=--sans-pause pour la CI"
	@echo "make verifier       verifier-bus seul (référence : le jeu, --racine demo/archive)"
	@echo "make silver         après make demo : le silver Iceberg du jeu depuis le bus (data/demo/lakehouse),"
	@echo "                    puis silver verifier contre l'archive (18 retenues, 4 écartées)"
	@echo "make etat           l'état à une date : ENTITE=bdpm.presentations A=2026-10-26T14:00:00Z"
	@echo "                    ETAT_OPTIONS=\"--ou code_cip13=… --format tableau\""
	@echo "make gold           après make silver : les contrôles de qualité du gold (code 2 si un bloquant"
	@echo "                    tombe), puis les 25 questions recalculées depuis le gold, qui doivent concorder"
	@echo "make index          après make gold : l'index de l'assistant ; construit en entier s'il n'en existe"
	@echo "                    pas, sinon mis à jour par incréments (la sortie dit lequel), puis vérifié"
	@echo "                    contre sa reconstruction depuis le gold ; INDEX_MODELE=test sans modèle"
	@echo "make fiche          la fiche médicament en texte : CIS=65999556 A=2026-10-24T20:00:00Z"
	@echo "                    (sans A : la dernière observation du silver)"
	@echo "make suivre         les événements publiés au fil de l'eau (à lancer avant make demo)"
	@echo "make console        la console Redpanda sur http://127.0.0.1:18080"
	@echo "make down           arrête le bus, garde les données"
	@echo "make rebatir        efface le bus et l'index (volumes du projet pharmaflux) et data/demo (silver"
	@echo "                    compris), redémarre ; le cache des vecteurs (data/index) reste"
	@echo "make verifications  ruff, mypy, pytest, comme la CI"

prerequis:
	sh infra/demo/prerequis.sh

up: prerequis
	$(COMPOSE) up -d --wait --pull never

demo: up
	$(PHARMAFLUX) schemas enregistrer
	$(PHARMAFLUX) demo rejouer --racine $(JEU) --sortie $(SORTIE_DEMO) $(DEMO_OPTIONS)
	$(PHARMAFLUX) verifier-bus --sortie $(SORTIE_DEMO) --racine $(JEU)

verifier:
	$(PHARMAFLUX) verifier-bus --sortie $(SORTIE_DEMO) --racine $(JEU)

silver:
	$(PHARMAFLUX) silver consommer --entrepot $(ENTREPOT_DEMO)
	$(PHARMAFLUX) silver verifier --entrepot $(ENTREPOT_DEMO) --sortie $(SORTIE_DEMO) --racine $(JEU)

etat:
	$(PHARMAFLUX) silver etat --entrepot $(ENTREPOT_DEMO) --entite $(ENTITE) --a $(A) $(ETAT_OPTIONS)

gold:
	$(PHARMAFLUX) gold qualite --entrepot $(ENTREPOT_DEMO)
	$(PHARMAFLUX) questions verifier --racine $(JEU) --entrepot $(ENTREPOT_DEMO)

# Une construction complète s'il n'y a pas d'index lisible et complet (aucun, un alias que
# l'état ne décrit pas après une construction coupée, ou un index réduit par --cis), sinon une
# mise à jour ; puis la vérification, qui a le dernier mot (code 1 au moindre écart).
index:
	sh infra/demo/prerequis.sh index $(INDEX_MODELE)
	@if $(PHARMAFLUX) index etat --complet > /dev/null 2>&1; then \
		echo "make index : un index existe, mise à jour par incréments (index mettre-a-jour)"; \
		$(PHARMAFLUX) index mettre-a-jour $(INDEX_OPTIONS); \
	else \
		echo "make index : aucun index lisible, construction complète (index construire)"; \
		$(PHARMAFLUX) index construire $(INDEX_OPTIONS); \
	fi
	$(PHARMAFLUX) index verifier $(INDEX_OPTIONS)

fiche:
	$(PHARMAFLUX) gold fiche --entrepot $(ENTREPOT_DEMO) --cis $(CIS) $(FICHE_A) $(FICHE_OPTIONS)

suivre:
	$(PHARMAFLUX) suivre

console:
	sh infra/demo/prerequis.sh console
	$(COMPOSE) --profile console up -d --pull never
	@echo "console : http://127.0.0.1:18080"

down:
	$(COMPOSE) down

rebatir:
	$(COMPOSE) down -v
	rm -rf $(SORTIE_DEMO)
	$(MAKE) up

verifications:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
