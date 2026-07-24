# ==============================================================================
#  NOTIFICATION ENGINE — envoi réel du lien client par email (Resend) et SMS
#  (OVH ou Twilio selon `settings.sms_provider`).
#
#  Repli gracieux (même logique que src/notifications.py) : si les identifiants
#  du fournisseur ne sont pas configurés dans backend/.env, la fonction se
#  contente de journaliser l'absence de config et renvoie False — jamais
#  d'exception propagée à l'appelant (le conseiller doit toujours voir le lien
#  généré, même si l'envoi automatique échoue).
# ==============================================================================
from __future__ import annotations

import hashlib
import json
import logging
import time

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

_OVH_BASE_URLS = {
    "ovh-eu": "https://eu.api.ovh.com/1.0",
    "ovh-ca": "https://ca.api.ovh.com/1.0",
    "ovh-us": "https://api.us.ovhcloud.com/1.0",
}


def envoyer_email(destinataire: str, sujet: str, corps_html: str) -> bool:
    """Envoie un email transactionnel via Resend. False (sans exception) si
    RESEND_API_KEY absente ou si l'envoi échoue."""
    if not destinataire:
        return False
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY absente — email non envoyé à %s.", destinataire)
        return False
    try:
        import resend

        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": f"{settings.email_from_name} <{settings.email_from}>",
            "to": [destinataire],
            "subject": sujet,
            "html": corps_html,
        })
        return True
    except Exception:
        logger.exception("Échec de l'envoi email (Resend) à %s.", destinataire)
        return False


def _envoyer_sms_ovh(destinataire: str, message: str) -> bool:
    if not (settings.ovh_application_key and settings.ovh_application_secret
            and settings.ovh_consumer_key and settings.ovh_sms_service_name):
        logger.warning("Identifiants OVH SMS incomplets — SMS non envoyé à %s.", destinataire)
        return False

    base_url = _OVH_BASE_URLS.get(settings.ovh_sms_endpoint, _OVH_BASE_URLS["ovh-eu"])
    chemin = f"/sms/{settings.ovh_sms_service_name}/jobs"
    url = base_url + chemin
    corps = json.dumps(
        {"message": message, "receivers": [destinataire], "senderForResponse": True},
        separators=(",", ":"),
    )
    timestamp = str(int(time.time()))
    # Schéma de signature OVH API (v6/v7) : "$1$" + sha1("AS+CK+METHODE+URL+CORPS+TIMESTAMP")
    a_signer = "+".join([
        settings.ovh_application_secret, settings.ovh_consumer_key, "POST", url, corps, timestamp,
    ])
    signature = "$1$" + hashlib.sha1(a_signer.encode("utf-8")).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Ovh-Application": settings.ovh_application_key,
        "X-Ovh-Consumer": settings.ovh_consumer_key,
        "X-Ovh-Timestamp": timestamp,
        "X-Ovh-Signature": signature,
    }
    try:
        reponse = httpx.post(url, content=corps, headers=headers, timeout=10)
        reponse.raise_for_status()
        return True
    except Exception:
        logger.exception("Échec de l'envoi SMS (OVH) à %s.", destinataire)
        return False


def _envoyer_sms_twilio(destinataire: str, message: str) -> bool:
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        logger.warning("Identifiants Twilio incomplets — SMS non envoyé à %s.", destinataire)
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    try:
        reponse = httpx.post(
            url,
            data={"From": settings.twilio_from_number, "To": destinataire, "Body": message},
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=10,
        )
        reponse.raise_for_status()
        return True
    except Exception:
        logger.exception("Échec de l'envoi SMS (Twilio) à %s.", destinataire)
        return False


def envoyer_sms(destinataire: str, message: str) -> bool:
    """Envoie un SMS via le fournisseur configuré (`settings.sms_provider`,
    "ovh" par défaut ou "twilio"). False (sans exception) si non configuré ou
    en cas d'échec."""
    if not destinataire:
        return False
    if settings.sms_provider == "twilio":
        return _envoyer_sms_twilio(destinataire, message)
    return _envoyer_sms_ovh(destinataire, message)
