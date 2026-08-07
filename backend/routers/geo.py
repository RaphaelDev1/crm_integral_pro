# ==============================================================================
#  GEO — auto-complétion ville à partir d'un code postal (étape Identité du
#  diagnostic). Le frontend a une CSP `connect-src 'self'` : impossible d'appeler
#  une API externe depuis le navigateur, donc ce petit proxy passe par le BFF
#  (/api/backend/geo/communes) comme tout le reste de l'app.
# ==============================================================================
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends

from backend.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/geo", tags=["geo"], dependencies=[Depends(get_current_user)])

GEO_API_URL = "https://geo.api.gouv.fr/communes"


@router.get("/communes", response_model=dict)
async def communes_par_code_postal(code_postal: str) -> dict:
    """Retourne les communes correspondant à un code postal (API officielle
    gratuite geo.api.gouv.fr — un code postal peut couvrir plusieurs communes).
    Ne lève jamais : une erreur réseau/timeout renvoie une liste vide plutôt
    que de casser le formulaire du conseiller."""
    if not code_postal or len(code_postal) != 5 or not code_postal.isdigit():
        return {"villes": []}

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            reponse = await client.get(GEO_API_URL, params={"codePostal": code_postal, "fields": "nom", "format": "json"})
            reponse.raise_for_status()
            communes = reponse.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Échec de la recherche de communes pour le code postal %s : %s", code_postal, exc)
        return {"villes": []}

    return {"villes": [c["nom"] for c in communes if c.get("nom")]}
