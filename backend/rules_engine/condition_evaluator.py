# ==============================================================================
#  CONDITION_EVALUATOR — évalue le DSL de condition JSON utilisé partout dans
#  le moteur de règles (branches.when, question.show_if, regle_recommandation
#  .condition). PLAN_IMPLEMENTATION_4_PHASES.md §0.2/§0.3.
#
#  Deux formes de condition :
#  - opérateur logique en clé unique : {"$and": [cond, ...]}, {"$or": [...]},
#    {"$not": cond}
#  - chemin de champ en clé(s) : {"chemin.pointe": valeur} (raccourci $eq) ou
#    {"chemin.pointe": {"$gt": 10, "$lte": 100}} (plusieurs opérateurs sur le
#    même champ = ET implicite). Plusieurs clés au même niveau = ET implicite.
#
#  Opérateurs supportés : $eq $ne $gt $gte $lt $lte $in $nin $and $or $not
#  $exists.
# ==============================================================================
from typing import Any

_MISSING = object()


def existe(contexte: dict, chemin: str) -> bool:
    """True si `chemin` résout à une valeur (même None) dans `contexte`."""
    return get_path(contexte, chemin) is not _MISSING


def get_path(contexte: dict, chemin: str) -> Any:
    """Résout un chemin pointé ("reponses.conso_data_go") dans un dict imbriqué.
    Retourne le sentinel _MISSING si le chemin n'existe pas (distinct de None,
    qui est une valeur explicite) — utilisé notamment par $exists."""
    valeur = contexte
    for segment in chemin.split("."):
        if not isinstance(valeur, dict) or segment not in valeur:
            return _MISSING
        valeur = valeur[segment]
    return valeur


def _compare(operateur: str, valeur: Any, attendu: Any) -> bool:
    trouve = valeur is not _MISSING
    reelle = None if not trouve else valeur

    if operateur == "$exists":
        return trouve is bool(attendu)
    if operateur == "$eq":
        return reelle == attendu
    if operateur == "$ne":
        return reelle != attendu
    if operateur == "$in":
        return reelle in attendu
    if operateur == "$nin":
        return reelle not in attendu
    if operateur in ("$gt", "$gte", "$lt", "$lte"):
        if reelle is None:
            return False
        try:
            if operateur == "$gt":
                return reelle > attendu
            if operateur == "$gte":
                return reelle >= attendu
            if operateur == "$lt":
                return reelle < attendu
            return reelle <= attendu
        except TypeError:
            return False
    raise ValueError(f"Opérateur de condition inconnu : {operateur}")


def evaluate(condition: dict | None, contexte: dict) -> bool:
    """Évalue récursivement une condition du DSL contre `contexte`.
    Une condition vide/None est considérée toujours vraie (pas de restriction)."""
    if not condition:
        return True

    for cle, valeur in condition.items():
        if cle == "$and":
            resultat = all(evaluate(sous, contexte) for sous in valeur)
        elif cle == "$or":
            resultat = any(evaluate(sous, contexte) for sous in valeur)
        elif cle == "$not":
            resultat = not evaluate(valeur, contexte)
        else:
            reelle = get_path(contexte, cle)
            if isinstance(valeur, dict) and valeur and all(k.startswith("$") for k in valeur):
                resultat = all(_compare(op, reelle, attendu) for op, attendu in valeur.items())
            else:
                resultat = _compare("$eq", reelle, valeur)

        if not resultat:
            return False

    return True
