# ==============================================================================
#  API IA CONSEIL — point d'entrée FastAPI. Lancement : uvicorn backend.main:app
#  Le schéma de base de données est géré par Alembic (voir alembic.ini) ; aucune
#  création de table n'a lieu au démarrage.
# ==============================================================================
import logging

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from backend.core.config import settings
from backend.core.logging import configurer_logging
from backend.core.rate_limit import limiter
from backend.routers import (
    admin,
    alertes_offres,
    audit_agent,
    auth,
    catalogue,
    clients,
    comparaisons_offres,
    contrats,
    dashboard,
    dashboard_utm,
    demarches,
    dossiers,
    factures,
    geo,
    honoraires,
    ia_conseil_catalogue,
    ia_conseil_clients,
    ia_conseil_dashboard,
    ia_conseil_sessions,
    ia_conseil_souscriptions,
    leads_public,
    mandats,
    notifications,
    offres,
    parametres,
    portail_public,
    prospects,
    speedtest_backend,
    stockage_local,
    users,
    veille,
    webhooks,
)

configurer_logging()
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env, traces_sample_rate=0.1)

app = FastAPI(title="IA Conseil — API", version="0.2.0")

# Rate limiting (slowapi) — landing publique /economiser (backend/routers/leads_public.py)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _gerer_depassement_rate_limit(request: Request, exc: RateLimitExceeded):
    message = "Quota journalier atteint." if "day" in str(exc.detail) else "Trop de requêtes, réessayez dans 1 minute."
    return JSONResponse(status_code=429, content={"detail": message})


@app.exception_handler(Exception)
async def _gerer_exception_non_geree(request: Request, exc: Exception):
    # Filet de sécurité : toute exception non gérée jusqu'ici (contrainte FK
    # non couverte, bug non anticipé...) remontait un 500 brut, sans trace
    # exploitable côté client ni log serveur clair. On journalise le
    # traceback complet ici et on renvoie un message générique — le détail
    # technique ne doit jamais fuiter au client.
    logger.error("Exception non gérée sur %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Une erreur inattendue est survenue. Réessayez ou contactez le support."})


# CORS — autoriser le portail Next.js
origines_autorisees = [
    settings.portail_client_base_url,
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origines_autorisees,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers protégés par JWT
app.include_router(admin.router)
app.include_router(alertes_offres.router)
app.include_router(audit_agent.router)
app.include_router(auth.router)
app.include_router(catalogue.router)
app.include_router(clients.router)
app.include_router(contrats.router)
app.include_router(prospects.router)
app.include_router(dossiers.router)
app.include_router(factures.router)
app.include_router(honoraires.router)
app.include_router(honoraires.router_liste)
app.include_router(mandats.router)
app.include_router(mandats.router_mandats)
app.include_router(demarches.router)
app.include_router(comparaisons_offres.router)
app.include_router(offres.router)
app.include_router(veille.router)
app.include_router(parametres.router)
app.include_router(dashboard.router)
app.include_router(dashboard_utm.router)
app.include_router(notifications.router)
app.include_router(users.router)
app.include_router(geo.router)

# Sous-système "IA Conseil" — trame adaptative + recommandation, préfixe
# /api/v1, isolé du CRM existant ci-dessus (voir PLAN_IMPLEMENTATION_4_PHASES.md).
app.include_router(ia_conseil_sessions.router)
app.include_router(ia_conseil_catalogue.router)
app.include_router(ia_conseil_catalogue.admin_router)
app.include_router(ia_conseil_clients.router)
app.include_router(ia_conseil_souscriptions.router)
app.include_router(ia_conseil_dashboard.router)

# Routers publics
app.include_router(portail_public.router)
app.include_router(leads_public.router)
app.include_router(speedtest_backend.router)
app.include_router(stockage_local.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok", "environnement": settings.app_env, "version": "0.2.0"}
