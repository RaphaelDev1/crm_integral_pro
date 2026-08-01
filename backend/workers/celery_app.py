# ==============================================================================
#  CELERY — file de tâches asynchrones (validation KYC, envoi et suivi des
#  demandes de signature Yousign, relance des dossiers stagnants, génération
#  et envoi LRE des documents de démarche, veille prix concurrentielle, digest
#  quotidien admin) sur broker/backend Redis.
#  Lancement worker : celery -A backend.workers.celery_app worker --loglevel=info
#  Lancement du planificateur (tâches périodiques) : celery -A backend.workers.celery_app beat
# ==============================================================================
import sentry_sdk
from celery import Celery
from celery.schedules import crontab
from sentry_sdk.integrations.celery import CeleryIntegration

from backend.core.config import settings
from backend.core.logging import configurer_logging

configurer_logging()

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.1,
    )

celery_app = Celery("ia_conseil", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_acks_late=True,
    task_routes={"backend.workers.tasks.*": {"queue": "ia_conseil"}},
    beat_schedule={
        "relancer-dossiers-stagnants-quotidien": {
            "task": "backend.workers.tasks.relancer_dossiers_stagnants",
            "schedule": crontab(hour=8, minute=0),
        },
        "verifier-accuses-lre-horaire": {
            "task": "backend.workers.tasks.verifier_accuses_lre_en_attente",
            "schedule": crontab(minute=0),
        },
        "lancer-veille-prix-quotidien": {
            "task": "backend.workers.tasks.lancer_veille_periodique",
            "schedule": crontab(hour=7, minute=0),
        },
        "ingerer-catalogue-quotidien": {
            "task": "backend.workers.tasks.ingerer_catalogue_periodique",
            "schedule": crontab(hour=3, minute=0),
        },
        "detecter-offres-moins-cheres-quotidien": {
            "task": "backend.workers.tasks.detecter_offres_moins_cheres_periodique",
            # Calée 30 min après la veille prix (7h00) pour comparer contre un
            # catalogue fraîchement mis à jour.
            "schedule": crontab(hour=7, minute=30),
        },
        "envoyer-digest-quotidien": {
            "task": "backend.workers.tasks.envoyer_digest_quotidien",
            "schedule": crontab(hour=8, minute=0),
        },
    },
)

celery_app.autodiscover_tasks(["backend.workers"])
