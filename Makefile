# Pharmaflux : la démo en deux commandes, « make up » puis « make demo » (mission 04, ADR 0008).
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

.PHONY: help prerequis up demo verifier suivre console down rebatir verifications

help:
	@echo "make up             vérifie les prérequis (images déjà présentes) et démarre le bus"
	@echo "make demo           up, enregistre les schémas, rejoue demo/archive sur le bus à la cadence"
	@echo "                    accélérée, puis verifier-bus ; DEMO_OPTIONS=--sans-pause pour la CI"
	@echo "make verifier       verifier-bus seul (référence : le jeu, --racine demo/archive)"
	@echo "make suivre         les événements publiés au fil de l'eau (à lancer avant make demo)"
	@echo "make console        la console Redpanda sur http://127.0.0.1:18080"
	@echo "make down           arrête le bus, garde les données"
	@echo "make rebatir        efface le bus (volume du projet pharmaflux) et data/demo, redémarre"
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
