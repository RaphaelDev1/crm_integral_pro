# ==============================================================================
#  ALERTES — génère les alertes (anti-survente, sous-couverture...) pour une
#  offre donnée, à partir des règles type='alerte'. §0.3.
# ==============================================================================
import re
from typing import Any

from backend.rules_engine.condition_evaluator import evaluate, existe, get_path

Offre = dict[str, Any]
Regle = dict[str, Any]
Reponses = dict[str, Any]
Alerte = dict[str, Any]

_MOTIF_TEMPLATE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _rendre_template(template: str, contexte: dict) -> str:
    def _remplacer(match: re.Match) -> str:
        chemin = match.group(1)
        if not existe(contexte, chemin):
            return ""
        valeur = get_path(contexte, chemin)
        return "" if valeur is None else str(valeur)

    return _MOTIF_TEMPLATE.sub(_remplacer, template or "")


def generer_alertes(offre: Offre, reponses: Reponses | None = None, regles: list[Regle] | None = None) -> list[Alerte]:
    reponses = reponses or {}
    contexte = {"offre": offre, "reponses": reponses}

    alertes: list[Alerte] = []
    for regle in regles or []:
        if regle.get("type") != "alerte" or not regle.get("actif", True):
            continue
        if not evaluate(regle["condition"], contexte):
            continue
        action = regle.get("action", {})
        alertes.append(
            {
                "regle": regle.get("nom", ""),
                "severite": action.get("severite", "info"),
                "message": _rendre_template(action.get("message", ""), contexte),
            }
        )
    return alertes
