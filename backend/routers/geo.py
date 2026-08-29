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
ADRESSE_API_URL = "https://api-adresse.data.gouv.fr/search/"


@router.get("/adresses", response_model=dict)
async def rechercher_adresses(q: str) -> dict:
    """Auto-complétion d'adresse postale complète (API officielle gratuite
    api-adresse.data.gouv.fr, utilisée par l'AnswerInput de type "adresse" des
    trames IA Conseil, PLAN_IMPLEMENTATION_4_PHASES.md §1.2). Même contrainte
    CSP que /geo/communes ci-dessus : proxy obligatoire. Ne lève jamais."""
    q = (q or "").strip()
    if len(q) < 3:
        return {"resultats": []}

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            reponse = await client.get(ADRESSE_API_URL, params={"q": q, "limit": 5})
            reponse.raise_for_status()
            donnees = reponse.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Échec de la recherche d'adresse pour %r : %s", q, exc)
        return {"resultats": []}

    resultats = []
    for feature in donnees.get("features", []):
        proprietes = feature.get("properties", {})
        coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
        resultats.append(
            {
                "label": proprietes.get("label"),
                "rue": proprietes.get("name"),
                "code_postal": proprietes.get("postcode"),
                "ville": proprietes.get("city"),
                "lat": coords[1],
                "lng": coords[0],
            }
        )
    return {"resultats": resultats}


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
