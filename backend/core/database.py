# ==============================================================================
#  BASE DE DONNÉES — engine SQLAlchemy async (Postgres) + session par requête.
#  Le schéma est géré par Alembic (backend/alembic/) — aucun create_all ici.
# ==============================================================================
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import settings
from backend.models.base import Base  # noqa: F401 — réexporté pour Alembic (env.py)

if not settings.database_url:
    raise RuntimeError(
        "DATABASE_URL doit être défini (copier backend/.env.example vers backend/.env) — "
        "ex. postgresql+asyncpg://user:password@host/dbname"
    )

# statement_cache_size=0 : requis par Neon en mode pooler (PgBouncer, connexion
# transaction-pooling) — asyncpg met en cache les requêtes préparées par
# connexion physique, mais PgBouncer peut faire basculer la session vers une
# autre connexion physique entre deux requêtes, d'où des erreurs intermittentes
# "prepared statement does not exist" sans ce réglage.
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
