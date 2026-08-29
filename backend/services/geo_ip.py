# ==============================================================================
#  DÉTECTION FAI PAR IP — landing publique /economiser (P2.3).
#  ipapi.co, gratuit sans clé jusqu'à 30k requêtes/mois. Sert uniquement à
#  pré-remplir (de façon éditable) le champ "Opérateur actuel" du formulaire —
#  jamais une donnée de facturation ou de scoring fiable.
# ==============================================================================
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(2.0)

# Correspondance approximative organisation FAI -> nom commercial affiché.
# Ordre important : "orange" doit être testé avant un éventuel match générique.
_MAPPING_OPERATEURS = [
    ("orange", "Orange"),
    ("free", "Free"),
    ("sfr", "SFR"),
    ("bouygues", "Bouygues Telecom"),
    ("numericable", "SFR"),
]


@dataclass
class ResultatGeoIp:
    organisation: str | None = None
    operateur_probable: str | None = None
    region: str | None = None


def _deviner_operateur(org: str | None) -> str | None:
    if not org:
        return None
    org_lower = org.lower()
    for cle, nom in _MAPPING_OPERATEURS:
        if cle in org_lower:
            return nom
    return None


async def detecter(ip: str) -> ResultatGeoIp:
    if not ip or ip in ("unknown", "127.0.0.1", "::1"):
        return ResultatGeoIp()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            reponse = await client.get(f"https://ipapi.co/{ip}/json/")
            reponse.raise_for_status()
            data = reponse.json()
    except Exception as exc:
        logger.info("Détection FAI par IP indisponible : %s", exc)
        return ResultatGeoIp()

    if data.get("error"):
        return ResultatGeoIp()

    org = data.get("org")
    return ResultatGeoIp(
        organisation=org,
        operateur_probable=_deviner_operateur(org),
        region=data.get("region"),
    )
