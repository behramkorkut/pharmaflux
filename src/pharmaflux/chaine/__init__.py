"""La chaîne en service (mission 10, ADR 0014) : enchaîner les commandes existantes.

Ce paquet ne calcule rien. Il prend un verrou, lance les commandes de la ligne
de commande une par une, chacune dans un sous-processus, et consigne ce qu'elles
ont rendu dans un journal des passages. Les événements, le bus, le silver et
l'index restent ce que leurs commandes en font.
"""
