# ==============================================================================
#  API IA CONSEIL — point d'entrée FastAPI. Lancement : uvicorn backend.main:app
#  Le schéma de base de données est géré par Alembic (voir alembic.ini) ; aucune
#  création de table n'a lieu au démarrage.
# ==============================================================================
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.logging import configurer_logging
from backend.routers import auth, clients, demarches, dossiers, factures, honoraires, portail_public, prospects, webhooks

configurer_logging()

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env, traces_sample_rate=0.1)

app = FastAPI(title="IA Conseil — API", version="0.2.0")

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
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(prospects.router)
app.include_router(dossiers.router)
app.include_router(factures.router)
app.include_router(honoraires.router)
app.include_router(demarches.router)

# Routers publics
app.include_router(portail_public.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok", "environnement": settings.app_env, "version": "0.2.0"}
