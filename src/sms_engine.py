# ==============================================================================
#  SMS — envoi via OVH (par défaut) ou Twilio, selon `secrets_config.sms_config()`
#  (mêmes variables d'environnement que backend/.env.example : SMS_PROVIDER,
#  OVH_*, TWILIO_*, réutilisables telles quelles des deux côtés).
#
#  Repli gracieux (même logique que notifications.py) : si les identifiants du
#  fournisseur ne sont pas configurés, la fonction se contente de le signaler
#  et renvoie False — jamais d'exception propagée à l'appelant (le conseiller
#  doit toujours voir le lien généré, même si l'envoi automatique échoue).
# ==============================================================================
import hashlib
import json
import time

import requests

import secrets_config

_OVH_BASE_URLS = {
    "ovh-eu": "https://eu.api.ovh.com/1.0",
    "ovh-ca": "https://ca.api.ovh.com/1.0",
    "ovh-us": "https://api.us.ovhcloud.com/1.0",
}


def _envoyer_sms_ovh(cfg: dict, destinataire: str, message: str) -> bool:
    if not (cfg["ovh_application_key"] and cfg["ovh_application_secret"]
            and cfg["ovh_consumer_key"] and cfg["ovh_service_name"]):
        print("Identifiants OVH SMS incomplets — SMS non envoyé.")
        return False

    base_url = _OVH_BASE_URLS.get(cfg["ovh_endpoint"], _OVH_BASE_URLS["ovh-eu"])
    url = f"{base_url}/sms/{cfg['ovh_service_name']}/jobs"
    corps = json.dumps(
        {"message": message, "receivers": [destinataire], "senderForResponse": True},
        separators=(",", ":"),
    )
    timestamp = str(int(time.time()))
    # Schéma de signature OVH API (v6/v7) : "$1$" + sha1("AS+CK+METHODE+URL+CORPS+TIMESTAMP")
    a_signer = "+".join([
        cfg["ovh_application_secret"], cfg["ovh_consumer_key"], "POST", url, corps, timestamp,
    ])
    signature = "$1$" + hashlib.sha1(a_signer.encode("utf-8")).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Ovh-Application": cfg["ovh_application_key"],
        "X-Ovh-Consumer": cfg["ovh_consumer_key"],
        "X-Ovh-Timestamp": timestamp,
        "X-Ovh-Signature": signature,
    }
    try:
        reponse = requests.post(url, data=corps, headers=headers, timeout=10)
        reponse.raise_for_status()
        return True
    except Exception as e:
        print(f"Échec de l'envoi SMS (OVH) : {e}")
        return False


def _envoyer_sms_twilio(cfg: dict, destinataire: str, message: str) -> bool:
    if not (cfg["twilio_account_sid"] and cfg["twilio_auth_token"] and cfg["twilio_from_number"]):
        print("Identifiants Twilio incomplets — SMS non envoyé.")
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['twilio_account_sid']}/Messages.json"
    try:
        reponse = requests.post(
            url,
            data={"From": cfg["twilio_from_number"], "To": destinataire, "Body": message},
            auth=(cfg["twilio_account_sid"], cfg["twilio_auth_token"]),
            timeout=10,
        )
        reponse.raise_for_status()
        return True
    except Exception as e:
        print(f"Échec de l'envoi SMS (Twilio) : {e}")
        return False


def envoyer_sms(destinataire: str, message: str) -> bool:
    """Envoie un SMS via le fournisseur configuré. False (sans exception) si
    aucun numéro, non configuré, ou en cas d'échec."""
    if not destinataire:
        return False
    cfg = secrets_config.sms_config()
    if cfg["provider"] == "twilio":
        return _envoyer_sms_twilio(cfg, destinataire, message)
    return _envoyer_sms_ovh(cfg, destinataire, message)
