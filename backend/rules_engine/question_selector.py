# ==============================================================================
#  QUESTION_SELECTOR — ★ CŒUR ESCARGOT ★ (PLAN_IMPLEMENTATION_4_PHASES.md
#  §Principe #1). À chaque étape, choisit parmi les questions encore
#  éligibles (trame_runtime.questions_eligibles) celle de score_info maximal
#  (information_scorer.score_info). Quand toutes les questions restantes ont
#  un score < seuil, la trame est considérée terminée : la fonction renvoie
#  None sans attendre que toutes les questions du template soient répondues
#  — c'est précisément ce qui permet un audit "en < 20 min" plutôt qu'un
#  formulaire exhaustif.
# ==============================================================================
from typing import Any, NamedTuple

from backend.rules_engine.information_scorer import score_info
from backend.rules_engine.trame_runtime import questions_eligibles

Question = dict[str, Any]
Trame = dict[str, Any]
Reponses = dict[str, Any]
Offre = dict[str, Any]
Regle = dict[str, Any]

SEUIL_INFO_PAR_DEFAUT = 0.0


class ResultatSelection(NamedTuple):
    question: Question | None
    questions_restantes_estimees: int


def prochaine_question(
    trame: Trame,
    reponses: Reponses | None = None,
    offres: list[Offre] | None = None,
    regles: list[Regle] | None = None,
    seuil: float = SEUIL_INFO_PAR_DEFAUT,
) -> ResultatSelection:
    """Sélectionne la question à score d'information maximal parmi les
    questions encore éligibles. `questions_restantes_estimees` (exposé au
    conseiller en UI, §Principe #1) compte celles dont le score dépasse le
    seuil — pas la totalité des questions éligibles au sens structurel."""
    reponses = reponses or {}
    eligibles = questions_eligibles(trame, reponses)
    if not eligibles:
        return ResultatSelection(None, 0)

    scores = [(q, score_info(q, reponses, offres, regles)) for q in eligibles]
    au_dessus_du_seuil = [(q, s) for q, s in scores if s >= seuil]

    if not au_dessus_du_seuil:
        return ResultatSelection(None, 0)

    meilleure_question, _ = max(au_dessus_du_seuil, key=lambda paire: paire[1])
    return ResultatSelection(meilleure_question, len(au_dessus_du_seuil))


def trame_terminee(
    trame: Trame,
    reponses: Reponses | None = None,
    offres: list[Offre] | None = None,
    regles: list[Regle] | None = None,
    seuil: float = SEUIL_INFO_PAR_DEFAUT,
) -> bool:
    return prochaine_question(trame, reponses, offres, regles, seuil).question is None
