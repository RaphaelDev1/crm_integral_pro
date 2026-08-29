# ==============================================================================
#  TRAME_RUNTIME — gère l'état d'une session de trame : quelles questions
#  restent éligibles compte tenu des réponses déjà données, des branches
#  actives (branches.when) et de leurs effets (branches.skip, questions
#  insérées) ainsi que du show_if de chaque question. PLAN_IMPLEMENTATION_
#  4_PHASES.md §0.2.
#
#  Ce module ne décide PAS quelle question éligible afficher en priorité
#  (c'est le rôle de question_selector.py, le cœur "escargot") : il se
#  contente de calculer l'ensemble des questions encore pertinentes.
# ==============================================================================
from typing import Any

from backend.rules_engine.condition_evaluator import evaluate, existe

Question = dict[str, Any]
Trame = dict[str, Any]
Reponses = dict[str, Any]


def _champs_requis(condition: dict | None) -> set[str]:
    """Chemins référencés directement par `condition` (hors $or/$not, où on ne
    peut pas déterminer un unique champ requis) — sert à exiger que la réponse
    dont dépend un show_if/when existe déjà, pour éviter qu'une question
    dérivée (ex. "roaming_hors_ue" qui dépend de "roaming_ue") ne devienne
    éligible avant que sa dépendance ait été répondue (le DSL générique traite
    une valeur manquante comme "!= X", ce qui serait sinon vrai trop tôt)."""
    if not condition:
        return set()
    champs: set[str] = set()
    for cle, valeur in condition.items():
        if cle == "$and":
            for sous in valeur:
                champs |= _champs_requis(sous)
        elif cle in ("$or", "$not"):
            continue
        elif isinstance(valeur, dict) and set(valeur.keys()) == {"$exists"}:
            continue  # un test $exists est justement un test d'absence légitime
        else:
            champs.add(cle)
    return champs


def _condition_satisfaite(condition: dict | None, reponses: Reponses) -> bool:
    if not condition:
        return True
    if any(not existe(reponses, champ) for champ in _champs_requis(condition)):
        return False
    return evaluate(condition, reponses)


def _questions_de_base(trame: Trame) -> list[Question]:
    questions = []
    for section in trame.get("sections", []) or []:
        questions.extend(section.get("questions", []) or [])
    return questions


def _branches_actives(trame: Trame, reponses: Reponses) -> list[dict]:
    return [
        branche
        for branche in (trame.get("branches", []) or [])
        if _condition_satisfaite(branche.get("when"), reponses)
    ]


def _questions_inserees_par_branches(trame: Trame, reponses: Reponses) -> list[Question]:
    questions = []
    for branche in _branches_actives(trame, reponses):
        questions.extend(branche.get("questions", []) or [])
    return questions


def _ids_skippes(trame: Trame, reponses: Reponses) -> set[str]:
    skippes: set[str] = set()
    for branche in _branches_actives(trame, reponses):
        skippes.update(branche.get("skip", []) or [])
    return skippes


def questions_eligibles(trame: Trame, reponses: Reponses | None = None) -> list[Question]:
    """Toutes les questions (base + insérées par branches actives) qui ne
    sont ni déjà répondues, ni skippées par une branche active, ni exclues
    par leur propre show_if."""
    reponses = reponses or {}
    skippes = _ids_skippes(trame, reponses)

    toutes = _questions_de_base(trame) + _questions_inserees_par_branches(trame, reponses)

    eligibles: list[Question] = []
    vus: set[str] = set()
    for question in toutes:
        qid = question["id"]
        if qid in vus:
            continue
        vus.add(qid)
        if qid in reponses:
            continue
        if qid in skippes:
            continue
        if not _condition_satisfaite(question.get("show_if"), reponses):
            continue
        eligibles.append(question)
    return eligibles


def next_question(trame: Trame, reponses: Reponses | None = None) -> Question | None:
    """Prochaine question éligible, dans l'ordre structurel de la trame (sans
    scoring d'information — voir question_selector.prochaine_question pour la
    sélection "escargot" par score)."""
    eligibles = questions_eligibles(trame, reponses)
    return eligibles[0] if eligibles else None


def is_terminee(trame: Trame, reponses: Reponses | None = None) -> bool:
    return not questions_eligibles(trame, reponses)


def flags_actifs(trame: Trame, reponses: Reponses | None = None) -> list[str]:
    """Flags déclarés par les branches actives (ex. "anti_survente_mobile"),
    utilisés pour informer scoring.py/alertes.py hors du DSL de règles."""
    reponses = reponses or {}
    flags: list[str] = []
    for branche in _branches_actives(trame, reponses):
        flags.extend(branche.get("flags", []) or [])
    return flags
