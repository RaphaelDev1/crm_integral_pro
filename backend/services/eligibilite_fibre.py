# ==============================================================================
#  ÉLIGIBILITÉ FIBRE — landing publique /economiser (P2.1).
#
#  Il n'existe pas d'API gratuite officielle donnant l'éligibilité fibre exacte
#  d'une adresse précise : les données ouvertes ARCEP ("Ma connexion internet",
#  data.arcep.fr) sont distribuées en fichiers bruts par département, pas via
#  une API interrogeable à la volée. On utilise donc un taux de couverture FttH
#  au niveau COMMUNE (code INSEE), via un wrapper public gratuit et sans clé
#  qui réexpose ces mêmes données ouvertes. Dégradation totale et silencieuse
#  si le service est indisponible ou désactivé (ELIGIBILITE_FIBRE_API_URL vide)
#  — jamais bloquant pour la capture du lead.
# ==============================================================================
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(3.0)
# Seuil au-delà duquel on considère la fibre "disponible" pour l'affichage
# (couverture partielle d'une commune ne garantit rien pour une adresse
# donnée, mais en dessous ce serait trompeur de l'afficher positivement).
SEUIL_DISPONIBLE = 0.5


@dataclass
class ResultatFibre:
    disponible: bool | None = None
    taux_couverture: float | None = None


async def verifier(code_insee: str | None) -> ResultatFibre:
    if not code_insee or not settings.eligibilite_fibre_api_url:
        return ResultatFibre()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            reponse = await client.get(f"{settings.eligibilite_fibre_api_url}/{code_insee}")
            reponse.raise_for_status()
            data = reponse.json()
    except Exception as exc:
        logger.warning("Éligibilité fibre indisponible pour code_insee=%s : %s", code_insee, exc)
        return ResultatFibre()

    taux = data.get("taux_couverture_fibre") or data.get("fibre_taux") or data.get("couverture_ftth")
    if taux is None:
        return ResultatFibre()
    try:
        taux = float(taux)
    except (TypeError, ValueError):
        return ResultatFibre()
    # Normalise un pourcentage exprimé en 0-100 vers 0-1.
    if taux > 1:
        taux = taux / 100
    return ResultatFibre(disponible=taux >= SEUIL_DISPONIBLE, taux_couverture=round(taux, 3))
