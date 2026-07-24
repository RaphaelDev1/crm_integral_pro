# ==============================================================================
#  SECRETS — point d'accès unique aux identifiants sensibles (SMTP, clés API,
#  jetons). Priorité aux variables d'environnement (.env en dev, variables
#  réelles en prod) ; repli sur l'ancien stockage en base (table `parametres`)
#  pour ne pas casser une instance existante tant que .env n'est pas rempli.
#
#  Migration prod (AWS Secrets Manager, etc.) : remplacer uniquement `_get()`
#  ci-dessous par un appel au backend de secrets choisi — le reste du code
#  (smtp_config(), anthropic_api_key(), ...) n'a pas à changer.
# ==============================================================================
import os

from dotenv import load_dotenv

load_dotenv()


def _get(env_var: str, cle_db: str, defaut: str = "") -> str:
    valeur = os.environ.get(env_var)
    if valeur:
        return valeur
    from db import lire_parametre
    return lire_parametre(cle_db, defaut)


def source_env(env_var: str) -> bool:
    """True si `env_var` est définie dans l'environnement (.env inclus) — sert
    à l'UI Admin pour savoir si un champ doit être affiché en lecture seule."""
    return bool(os.environ.get(env_var))


def smtp_config() -> dict:
    from utils import safe_float
    return {
        "serveur":    _get("SMTP_SERVEUR", "smtp_serveur"),
        "port":       int(safe_float(_get("SMTP_PORT", "smtp_port", "587"), 587)),
        "user":       _get("SMTP_USER", "smtp_user"),
        "mdp":        _get("SMTP_MDP", "smtp_mdp"),
        "expediteur": _get("SMTP_EXPEDITEUR", "smtp_expediteur"),
    }


def anthropic_api_key() -> str:
    return _get("ANTHROPIC_API_KEY", "anthropic_api_key")


def telegram_bot_token() -> str:
    return _get("TELEGRAM_BOT_TOKEN", "telegram_bot_token")


def telegram_chat_id() -> str:
    return _get("TELEGRAM_CHAT_ID", "telegram_chat_id")


def sms_config() -> dict:
    """Identifiants SMS (OVH par défaut, ou Twilio) — mêmes noms de variables que
    backend/.env.example pour pouvoir réutiliser le même compte des deux côtés."""
    return {
        "provider":            _get("SMS_PROVIDER", "sms_provider", "ovh"),
        "ovh_endpoint":        _get("OVH_SMS_ENDPOINT", "ovh_sms_endpoint", "ovh-eu"),
        "ovh_service_name":    _get("OVH_SMS_SERVICE_NAME", "ovh_sms_service_name"),
        "ovh_application_key": _get("OVH_APPLICATION_KEY", "ovh_application_key"),
        "ovh_application_secret": _get("OVH_APPLICATION_SECRET", "ovh_application_secret"),
        "ovh_consumer_key":    _get("OVH_CONSUMER_KEY", "ovh_consumer_key"),
        "twilio_account_sid":  _get("TWILIO_ACCOUNT_SID", "twilio_account_sid"),
        "twilio_auth_token":   _get("TWILIO_AUTH_TOKEN", "twilio_auth_token"),
        "twilio_from_number":  _get("TWILIO_FROM_NUMBER", "twilio_from_number"),
    }


def sentry_dsn() -> str:
    return _get("SENTRY_DSN", "sentry_dsn")


def portail_prospect_base_url() -> str:
    """Base publique de la mini-page « envoyer facture + test de débit »
    (servie par chatbot_api.py, GET /portail/{token})."""
    return _get("PORTAIL_PROSPECT_BASE_URL", "portail_prospect_base_url", "http://127.0.0.1:8001")
