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
        "synchroniser-catalogue-ia-conseil-quotidien": {
            "task": "backend.workers.tasks.synchroniser_catalogue_ia_conseil_periodique",
            "schedule": crontab(hour=3, minute=30),
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
        "relancer-email-j1-landing": {
            "task": "backend.workers.tasks.relancer_email_j1_leads_landing",
            # Horaire, comme la vérification LRE — la fenêtre 24h-25h côté
            # tâche garantit qu'aucun lead n'est raté entre deux exécutions.
            "schedule": crontab(minute=15),
        },
        "relancer-nurturing-landing": {
            "task": "backend.workers.tasks.relancer_nurturing_leads_landing",
            # Horaire aussi (fenêtres 48h-49h/72h-73h/96h-97h/120h-121h côté
            # tâche) — décalée de 30 min sur l'email J+1 pour ne pas cumuler
            # les deux tâches leads landing sur le même tick.
            "schedule": crontab(minute=45),
        },
        "demander-facture-prospects": {
            "task": "backend.workers.tasks.demander_facture_prospects",
            # Horaire (fenêtre 48h-49h côté tâche) — décalée pour ne pas
            # cumuler avec les deux tâches leads landing ci-dessus.
            "schedule": crontab(minute=30),
        },
        "detecter-alternatives-souscriptions-quotidien": {
            "task": "backend.workers.tasks.detecter_alternatives_souscriptions_periodique",
            # Calée après la veille prix legacy (7h30) pour comparer contre un
            # catalogue fraîchement mis à jour.
            "schedule": crontab(hour=7, minute=45),
        },
        "planifier-evenements-ia-conseil-quotidien": {
            "task": "backend.workers.tasks.planifier_evenements_ia_conseil_periodique",
            # Avant l'exécution (08h15) pour que les événements du jour créés
            # ici puissent être traités dans la même journée.
            "schedule": crontab(hour=8, minute=0),
        },
        "executer-evenements-ia-conseil-quotidien": {
            "task": "backend.workers.tasks.executer_evenements_ia_conseil_periodique",
            "schedule": crontab(hour=8, minute=15),
        },
        "auditer-biais-commercial-hebdomadaire": {
            "task": "backend.workers.tasks.auditer_biais_commercial_periodique",
            # Lundi matin, après le digest quotidien — vue hebdomadaire du
            # garde-fou anti-biais commercial (§2.6).
            "schedule": crontab(day_of_week=1, hour=8, minute=30),
        },
        "veille-marche-hebdomadaire": {
            "task": "backend.workers.tasks.veille_marche_hebdomadaire_task",
            # Lundi, après l'audit anti-biais (08h30) — agent de veille marché
            # autonome IA Conseil (§3.4).
            "schedule": crontab(day_of_week=1, hour=9, minute=0),
        },
    },
)

celery_app.autodiscover_tasks(["backend.workers"])
