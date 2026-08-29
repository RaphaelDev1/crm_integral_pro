# ==============================================================================
#  SCORING — score chaque offre du catalogue pour un client donné, §0.3.
#  Applique d'abord les règles type='filtre' (exclusion), puis les règles
#  type='scoring' (ajustement de score), triées par priorité croissante
#  (une priorité plus haute s'applique en dernier, donc "a le dernier mot").
#
#  Simplification assumée sur les règles de scoring : le plan illustre les
#  ajustements avec une pseudo-formule textuelle libre
#  (`IF(offre.data_go <= 40, +30, IF(...))`). Pour rester cohérent avec le
#  reste du moteur (même DSL partout, testable sans parseur d'expressions),
#  ce module attend soit un ajustement constant (`action.valeur`), soit un
#  barème de conditions DSL ordonnées (`action.bareme`, la première qui
#  matche l'emporte) — équivalent fonctionnel du IF/ELSE imbriqué du plan.
# ==============================================================================
from typing import Any

from backend.rules_engine.condition_evaluator import evaluate

Offre = dict[str, Any]
Regle = dict[str, Any]
Reponses = dict[str, Any]

SCORE_DE_BASE = 50.0
SCORE_MIN = 0.0
SCORE_MAX = 100.0


def _regles_actives(regles: list[Regle], type_: str) -> list[Regle]:
    return [r for r in (regles or []) if r.get("type") == type_ and r.get("actif", True)]


def _valeur_ajustement(action: dict, contexte: dict) -> float:
    if "bareme" in action:
        for entree in action["bareme"]:
            if evaluate(entree.get("si"), contexte):
                return float(entree.get("valeur", 0))
        return float(action.get("defaut", 0))
    return float(action.get("valeur", 0))


def score_offres(offres: list[Offre], reponses: Reponses | None = None, regles: list[Regle] | None = None) -> list[dict]:
    """Retourne une liste de {offre, score, rang, justifications}, triée par
    score décroissant, après application des filtres puis du scoring."""
    reponses = reponses or {}
    regles_filtre = _regles_actives(regles or [], "filtre")
    regles_scoring = sorted(_regles_actives(regles or [], "scoring"), key=lambda r: r.get("priorite", 0))

    resultats = []
    for offre in offres:
        contexte = {"offre": offre, "reponses": reponses}

        exclue = any(
            evaluate(regle["condition"], contexte) and regle.get("action", {}).get("kind") == "exclude"
            for regle in regles_filtre
        )
        if exclue:
            continue

        score = SCORE_DE_BASE
        justifications: list[str] = []
        for regle in regles_scoring:
            if not evaluate(regle["condition"], contexte):
                continue
            action = regle.get("action", {})
            if action.get("kind") not in ("score_adjust", "boost"):
                continue
            delta = _valeur_ajustement(action, contexte)
            if delta == 0:
                continue
            score += delta
            justifications.append(regle.get("nom", ""))

        score = max(SCORE_MIN, min(SCORE_MAX, score))
        resultats.append({"offre": offre, "score": score, "justifications": justifications})

    resultats.sort(key=lambda r: r["score"], reverse=True)
    for rang, resultat in enumerate(resultats, start=1):
        resultat["rang"] = rang
    return resultats
