# ==============================================================================
#  CONFIGURATION — Pydantic Settings, lues depuis backend/.env (dev) ou les
#  variables d'environnement réelles (prod). Voir backend/.env.example.
# ==============================================================================
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = ""
    crm_api_secret: str = ""

    jwt_algorithme: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    reset_token_expire_minutes: int = 30

    anthropic_api_key: str = ""

    yousign_api_key: str = ""
    yousign_api_url: str = "https://api-sandbox.yousign.app/v3"
    yousign_webhook_secret: str = ""

    redis_url: str = "redis://localhost:6379/0"

    # -- Observabilité --
    sentry_dsn: str = ""

    # -- Portail client --
    portail_client_base_url: str = "http://localhost:3000"

    # -- S3 (Scaleway Object Storage recommandé) --
    s3_endpoint_url: str = "https://s3.fr-par.scw.cloud"
    s3_region: str = "fr-par"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    # -- Stripe (facturation client) --
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""

    # -- SMS (OVH ou Twilio) --
    sms_provider: str = "ovh"
    ovh_sms_endpoint: str = ""
    ovh_sms_service_name: str = ""
    ovh_application_key: str = ""
    ovh_application_secret: str = ""
    ovh_consumer_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # -- Email transactionnel (Resend) --
    resend_api_key: str = ""
    email_from: str = "contact@iaconseil.fr"
    email_from_name: str = "IA Conseil"

    # -- LRE (AR24 — lettre recommandée électronique) --
    # ⚠️ Schéma d'authentification exact (bearer token vs login/mot de passe)
    # à vérifier contre la doc AR24 réelle avant mise en prod (aucun compte
    # créé à ce jour — voir SETUP_STATUS.md).
    ar24_api_key: str = ""
    ar24_api_url: str = "https://api.ar24.fr"
    ar24_login: str = ""
    ar24_password: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def jwt_secret(self) -> str:
        """Reprend la logique de src/jwt_auth.py : secret de dev toléré hors
        production, mais obligatoire en production (on refuse de tourner avec
        un secret JWT prévisible)."""
        if self.crm_api_secret:
            return self.crm_api_secret
        if self.is_production:
            raise RuntimeError(
                "CRM_API_SECRET doit être défini en production (voir backend/.env.example)."
            )
        return "dev-secret-a-changer-en-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
