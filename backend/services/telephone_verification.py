# ==============================================================================
#  VALIDATION TÉLÉPHONE — Twilio Lookup v2 (P2.2), landing publique.
#
#  Réutilise les identifiants Twilio existants (TWILIO_ACCOUNT_SID/AUTH_TOKEN,
#  backend/core/config.py) indépendamment de SMS_PROVIDER : Lookup est une API
#  Twilio séparée de l'envoi de SMS, un compte Twilio suffit pour les deux même
#  si l'envoi effectif passe par OVH.
#
#  Fail-open : credentials absents ou erreur réseau -> (None, None). On ne
#  bloque jamais un lead sur un souci technique côté Twilio ; seul un `False`
#  explicite signifie que le numéro n'existe pas.
# ==============================================================================
from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0)


@dataclass
class ResultatVerification:
    verifie: bool | None = None
    type_ligne: str | None = None


def _vers_e164(numero: str) -> str:
    """Le numéro stocké côté prospect est au format FR local (0612345678) —
    Twilio Lookup exige de l'E.164 (+33612345678)."""
    n = numero.strip().replace(" ", "")
    if n.startswith("+"):
        return n
    if n.startswith("0033"):
        return "+" + n[2:]
    if n.startswith("00"):
        return "+" + n[2:]
    if n.startswith("0"):
        return "+33" + n[1:]
    return n


async def verifier(numero: str) -> ResultatVerification:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return ResultatVerification()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            reponse = await client.get(
                f"https://lookups.twilio.com/v2/PhoneNumbers/{quote(_vers_e164(numero), safe='')}",
                params={"Fields": "line_type_intelligence"},
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
        if reponse.status_code == 404:
            # Twilio renvoie 404 pour un numéro qui n'existe pas.
            return ResultatVerification(verifie=False)
        reponse.raise_for_status()
        data = reponse.json()
    except Exception as exc:
        logger.warning("Twilio Lookup indisponible pour un numéro : %s", exc)
        return ResultatVerification()

    valide = bool(data.get("valid"))
    type_ligne = (data.get("line_type_intelligence") or {}).get("type")
    return ResultatVerification(verifie=valide, type_ligne=type_ligne)
