# ==============================================================================
#  INFORMATION_SCORER — calcule score_info(question) selon PLAN_
#  IMPLEMENTATION_4_PHASES.md §Principe #1 :
#
#    score_info(question) =
#        SI déjà répondue OU incompatible avec les réponses actuelles → 0
#        SINON :
#          nombre d'offres du catalogue que la question permettrait d'éliminer
#        + nombre de règles de recommandation qui l'utilisent
#        + poids éthique
#        - coût cognitif
#
#  Simplification assumée sur `elimine_offres_si` : le plan illustre ce champ
#  avec des expressions texte libres ("offres.data_go > 40"). Pour rester
#  cohérent avec le reste du moteur (et testable sans écrire un parseur
#  d'expressions), ce module exige que chaque scénario de `elimine_offres_si`
#  soit exprimé avec le même DSL que le reste du moteur (condition_evaluator).
#  Un scénario mal formé (texte libre) est ignoré plutôt que de lever une
#  erreur — dégradation silencieuse, cohérent avec le reste du projet.
# ==============================================================================
from typing import Any

from backend.rules_engine.condition_evaluator import evaluate, existe

Question = dict[str, Any]
Offre = dict[str, Any]
Regle = dict[str, Any]
Reponses = dict[str, Any]


def _estimation_offres_eliminees(question: Question, offres: list[Offre]) -> float:
    scenarios = question.get("elimine_offres_si") or {}
    if not scenarios or not offres:
        return 0.0
    totaux = [
        sum(1 for offre in offres if evaluate(condition, {"offre": offre}))
        for condition in scenarios.values()
        if isinstance(condition, dict)
    ]
    return (sum(totaux) / len(totaux)) if totaux else 0.0


def score_info(
    question: Question,
    reponses: Reponses | None = None,
    offres: list[Offre] | None = None,
    regles: list[Regle] | None = None,
) -> float:
    reponses = reponses or {}
    qid = question["id"]

    if existe(reponses, qid):
        return 0.0
    if not evaluate(question.get("show_if"), reponses):
        return 0.0  # incompatible avec les réponses actuelles

    nb_offres_eliminees = _estimation_offres_eliminees(question, offres or [])
    nb_regles = len(question.get("utilise_par_regles", []) or [])
    poids_ethique = question.get("poids_ethique", 0) or 0
    cout_cognitif = question.get("cout_cognitif", 1) or 1

    return float(nb_offres_eliminees + nb_regles + poids_ethique - cout_cognitif)
