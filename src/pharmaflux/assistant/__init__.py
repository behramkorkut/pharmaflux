"""L'assistant gouverné (mission 08) : recherche hybride, réponse sourcée et datée,
abstention et refus médical décidés hors du LLM, contrôle des citations par le code.

Le chemin d'une question est dans ``chemin`` ; les règles de refus et d'abstention dans
``regles`` ; le repérage du médicament visé dans ``repere`` ; le contrôle des nombres et des
dates dans ``controle`` ; le budget, la grille de prix et le journal des dépenses dans
``budget`` ; le client Claude (et son double de test) dans ``client``. Aucun appel réel ne
part des tests : ils passent tous par le double (addendum 1 J).
"""
