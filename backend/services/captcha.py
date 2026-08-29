# ==============================================================================
#  CAPTCHA INVISIBLE — Cloudflare Turnstile (P3.3), landing publique.
#  TURNSTILE_SECRET_KEY vide = vérification désactivée (retourne toujours
#  True), même pattern de dégradation gracieuse que les autres intégrations
#  externes de ce routeur (Slack/SMS/email).
# ==============================================================================
from __future__ import annotations

import logging

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0)
_URL_VERIFICATION = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verifier(token: str | None, ip: str) -> bool:
    if not settings.turnstile_secret_key:
        return True
    if not token:
        return False

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            reponse = await client.post(
                _URL_VERIFICATION,
                data={
                    "secret": settings.turnstile_secret_key,
                    "response": token,
                    "remoteip": ip,
                },
            )
        reponse.raise_for_status()
        data = reponse.json()
    except Exception as exc:
        logger.warning("Vérification Turnstile indisponible : %s", exc)
        # Fail-open : un incident Cloudflare ne doit pas bloquer tous les leads.
        return True

    return bool(data.get("success"))
