# Contenu complet du backend/



## 📄 backend\__init__.py

\\\python


\\\`n

## 📄 backend\alembic\env.py

\\\python

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.core.config import settings
from backend.models import Base  # noqa: F401 — importe tous les modèles pour target_metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

\\\`n

## 📄 backend\alembic\versions\0001_initial_schema.py

\\\python

"""État initial — miroir du schéma SQLite existant (utilisateurs, prospects,
clients, contrats, offres), tel que produit par src/db.py::initialiser_bdd()
et _migrer_bdd() au moment de la migration vers Postgres.

Revision ID: 0001
Revises:
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "utilisateurs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("nom_complet", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), server_default="Conseiller"),
        sa.Column("actif", sa.Boolean(), server_default=sa.true()),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("doit_changer_mdp", sa.Boolean(), server_default=sa.false()),
    )

    op.create_table(
        "prospects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ref", sa.String(), nullable=True),
        sa.Column("prenom", sa.String(), nullable=True),
        sa.Column("nom", sa.String(), nullable=True),
        sa.Column("telephone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("code_postal", sa.String(), nullable=True),
        sa.Column("ville", sa.String(), nullable=True),
        sa.Column("adresse", sa.String(), nullable=True),
        sa.Column("type_client", sa.String(), nullable=True),
        sa.Column("univers_interesse", sa.String(), nullable=True),
        sa.Column("service_principal", sa.String(), nullable=True),
        sa.Column("operateur_actuel", sa.String(), nullable=True),
        sa.Column("techno", sa.String(), nullable=True),
        sa.Column("data_go", sa.String(), nullable=True),
        sa.Column("cout_mensuel_actuel", sa.Float(), server_default="0"),
        sa.Column("offre_actuelle", sa.String(), nullable=True),
        sa.Column("satisfaction_reseau", sa.String(), nullable=True),
        sa.Column("veut_rester", sa.String(), nullable=True),
        sa.Column("speed_down", sa.Float(), server_default="0"),
        sa.Column("speed_up", sa.Float(), server_default="0"),
        sa.Column("cout_elec", sa.Float(), server_default="0"),
        sa.Column("cout_gaz", sa.Float(), server_default="0"),
        sa.Column("fournisseur_energie", sa.String(), nullable=True),
        sa.Column("abonnements", sa.String(), nullable=True),
        sa.Column("lignes_multi", sa.String(), nullable=True),
        sa.Column("economie_estimee_an", sa.Float(), server_default="0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("statut", sa.String(), server_default="À relancer"),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("date_relance", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
        sa.Column("offres_interet", sa.String(), nullable=True),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.Column("origine", sa.String(), server_default="Manuel"),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ref", sa.String(), nullable=True),
        sa.Column("prenom", sa.String(), nullable=True),
        sa.Column("nom", sa.String(), nullable=True),
        sa.Column("telephone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("code_postal", sa.String(), nullable=True),
        sa.Column("ville", sa.String(), nullable=True),
        sa.Column("adresse", sa.String(), nullable=True),
        sa.Column("type_client", sa.String(), nullable=True),
        sa.Column("operateur_actuel", sa.String(), nullable=True),
        sa.Column("techno", sa.String(), nullable=True),
        sa.Column("data_go", sa.String(), nullable=True),
        sa.Column("offre_actuelle", sa.String(), nullable=True),
        sa.Column("cout_mensuel_actuel", sa.Float(), server_default="0"),
        sa.Column("satisfaction_reseau", sa.String(), nullable=True),
        sa.Column("veut_rester", sa.String(), nullable=True),
        sa.Column("speed_down", sa.Float(), server_default="0"),
        sa.Column("speed_up", sa.Float(), server_default="0"),
        sa.Column("fournisseur_energie", sa.String(), nullable=True),
        sa.Column("cout_elec", sa.Float(), server_default="0"),
        sa.Column("cout_gaz", sa.Float(), server_default="0"),
        sa.Column("economie_estimee_an", sa.Float(), server_default="0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
        sa.Column("date_relance", sa.String(), nullable=True),
        sa.Column("statut_relance", sa.String(), server_default="Aucune"),
    )

    op.create_table(
        "contrats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("univers", sa.String(), nullable=True),
        sa.Column("categorie", sa.String(), nullable=True),
        sa.Column("fournisseur", sa.String(), nullable=True),
        sa.Column("nom_offre", sa.String(), nullable=True),
        sa.Column("cout_mensuel", sa.Float(), server_default="0"),
        sa.Column("economie_mensuelle", sa.Float(), server_default="0"),
        sa.Column("reference_contrat", sa.String(), nullable=True),
        sa.Column("statut_contrat", sa.String(), nullable=True),
        sa.Column("date_souscription", sa.String(), nullable=True),
        sa.Column("date_fin_engagement", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
    )

    op.create_table(
        "offres",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("univers", sa.String(), nullable=True),
        sa.Column("categorie", sa.String(), nullable=True),
        sa.Column("fournisseur", sa.String(), nullable=True),
        sa.Column("nom_offre", sa.String(), nullable=True),
        sa.Column("prix_mensuel", sa.Float(), nullable=True),
        sa.Column("frais_activation", sa.Float(), nullable=True),
        sa.Column("engagement_mois", sa.Integer(), nullable=True),
        sa.Column("caracteristiques", sa.String(), nullable=True),
        sa.Column("commission_affiliation", sa.Float(), nullable=True),
        sa.Column("data_go", sa.Float(), server_default="0"),
        sa.Column("actif", sa.Boolean(), server_default=sa.true()),
        sa.Column("url_souscription", sa.String(), nullable=True),
        sa.Column("code_affiliation", sa.String(), nullable=True),
        sa.Column("date_maj", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("offres")
    op.drop_table("contrats")
    op.drop_table("clients")
    op.drop_table("prospects")
    op.drop_table("utilisateurs")

\\\`n

## 📄 backend\alembic\versions\0002_mandats_documents.py

\\\python

"""Ajoute les tables `mandats` (signature électronique Yousign) et
`documents` (validation KYC) — voir backend/models/mandat.py et
backend/models/document.py.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mandats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("statut", sa.String(), server_default="brouillon", nullable=False),
        sa.Column("pdf_url", sa.String(), nullable=True),
        sa.Column("pdf_signe_url", sa.String(), nullable=True),
        sa.Column("yousign_signature_request_id", sa.String(), nullable=True),
        sa.Column("yousign_document_id", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("date_envoi", sa.String(), nullable=True),
        sa.Column("date_signature", sa.String(), nullable=True),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("type_document", sa.String(), nullable=True),
        sa.Column("url_stockage", sa.String(), nullable=False),
        sa.Column("statut_kyc", sa.String(), server_default="en_attente", nullable=False),
        sa.Column("motif_rejet", sa.String(), nullable=True),
        sa.Column("date_upload", sa.String(), nullable=True),
        sa.Column("date_validation", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("mandats")

\\\`n

## 📄 backend\core\__init__.py

\\\python


\\\`n

## 📄 backend\core\config.py

\\\python

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

\\\`n

## 📄 backend\core\database.py

\\\python

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

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

\\\`n

## 📄 backend\core\security.py

\\\python

# ==============================================================================
#  SECURITY — hachage des mots de passe (PBKDF2-SHA256, repris de src/auth.py)
#  et JWT access/refresh/reset (logique reprise de src/jwt_auth.py), adaptés à
#  SQLAlchemy async pour l'API FastAPI.
# ==============================================================================
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.models.user import User

_PBKDF2_ITERATIONS = 260_000   # OWASP 2024 recommandation pour PBKDF2-SHA256

_bearer = HTTPBearer(auto_error=False)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"


def hash_password(password: str) -> str:
    """Retourne 'salt:hash' stockable en base (identique à src/auth.py)."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Vérifie un mot de passe contre le hash stocké. Résistant aux attaques de timing."""
    try:
        salt, h = stored.split(":", 1)
        new_h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
        return secrets.compare_digest(new_h.hex(), h)
    except Exception:
        return False


def _creer_token(user: User, type_: TokenType, duree: timedelta) -> str:
    maintenant = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
        "type": type_.value,
        "iat": maintenant,
        "exp": maintenant + duree,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithme)


def creer_access_token(user: User) -> str:
    return _creer_token(user, TokenType.ACCESS, timedelta(minutes=settings.access_token_expire_minutes))


def creer_refresh_token(user: User) -> str:
    return _creer_token(user, TokenType.REFRESH, timedelta(days=settings.refresh_token_expire_days))


def creer_reset_token(user: User) -> str:
    """Jeton à courte durée de vie pour le flux « mot de passe oublié »."""
    return _creer_token(user, TokenType.RESET, timedelta(minutes=settings.reset_token_expire_minutes))


def decoder_token(token: str, type_attendu: TokenType) -> dict:
    """Décode et valide un JWT, en vérifiant qu'il est du type attendu — empêche
    par exemple un refresh token d'être présenté comme access token."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithme])
    if payload.get("type") != type_attendu.value:
        raise jwt.InvalidTokenError("Type de jeton inattendu.")
    return payload


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dépendance FastAPI : extrait l'utilisateur courant depuis l'en-tête
    Authorization: Bearer <access_token>. Revérifie l'existence et le flag
    `actif` en base à chaque requête, afin qu'une désactivation de compte
    révoque immédiatement les jetons déjà émis."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")
    try:
        payload = decoder_token(creds.credentials, TokenType.ACCESS)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide ou expiré.")

    user = await db.get(User, payload["user_id"])
    if user is None or not user.actif:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur introuvable ou désactivé.")
    return user


def require_role(*roles: str):
    """Fabrique une dépendance FastAPI qui exige que l'utilisateur courant ait
    l'un des rôles donnés (ex. require_role("Conseiller", "Admin"))."""
    def _dependance(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès refusé pour ce rôle.")
        return user
    return _dependance

\\\`n

## 📄 backend\main.py

\\\python

# ==============================================================================
#  API IA CONSEIL — point d'entrée FastAPI. Lancement : uvicorn backend.main:app
#  Le schéma de base de données est géré par Alembic (voir alembic.ini) ; aucune
#  création de table n'a lieu au démarrage.
# ==============================================================================
from fastapi import FastAPI

from backend.core.config import settings
from backend.routers import auth, clients, factures, prospects, webhooks

app = FastAPI(title="IA Conseil — API", version="0.1.0")

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(prospects.router)
app.include_router(factures.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok", "environnement": settings.app_env}

\\\`n

## 📄 backend\models\__init__.py

\\\python

from backend.models.abonnement import Abonnement
from backend.models.base import Base
from backend.models.client import Client
from backend.models.commission import Commission
from backend.models.contrat import Contrat
from backend.models.document import Document
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.models.offre import Offre
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic
from backend.models.user import User

__all__ = [
    "Base",
    "User",
    "Prospect",
    "Client",
    "Contrat",
    "Offre",
    "Mandat",
    "Document",
    "Dossier",
    "TokenPublic",
    "Commission",
    "Abonnement",
]

\\\`n

## 📄 backend\models\abonnement.py

\\\python

# ==============================================================================
#  ABONNEMENT — abonnement Gestionnaire personnel (4,90€/mois particuliers,
#  14,90€/mois pro). MRR récurrent, prélèvement Stripe SEPA.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client


class Abonnement(Base):
    __tablename__ = "abonnements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)

    formule: Mapped[str] = mapped_column(String, nullable=False)   # 'gestionnaire_perso' | 'gestionnaire_pro'
    prix_mensuel: Mapped[float] = mapped_column(Float, nullable=False)

    date_debut: Mapped[str | None] = mapped_column(String, nullable=True)
    date_fin: Mapped[str | None] = mapped_column(String, nullable=True)

    statut: Mapped[str] = mapped_column(String, default="actif")   # actif | suspendu | resilie

    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship()

\\\`n

## 📄 backend\models\base.py

\\\python

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

\\\`n

## 📄 backend\models\client.py

\\\python

# ==============================================================================
#  CLIENT — miroir de la table `clients` (src/db.py, création + colonnes
#  ajoutées par _migrer_bdd()).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.contrat import Contrat


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ref: Mapped[str | None] = mapped_column(String, nullable=True)
    prenom: Mapped[str | None] = mapped_column(String, nullable=True)
    nom: Mapped[str | None] = mapped_column(String, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    code_postal: Mapped[str | None] = mapped_column(String, nullable=True)
    ville: Mapped[str | None] = mapped_column(String, nullable=True)
    adresse: Mapped[str | None] = mapped_column(String, nullable=True)
    type_client: Mapped[str | None] = mapped_column(String, nullable=True)
    operateur_actuel: Mapped[str | None] = mapped_column(String, nullable=True)
    techno: Mapped[str | None] = mapped_column(String, nullable=True)
    data_go: Mapped[str | None] = mapped_column(String, nullable=True)
    offre_actuelle: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_mensuel_actuel: Mapped[float | None] = mapped_column(Float, default=0)
    satisfaction_reseau: Mapped[str | None] = mapped_column(String, nullable=True)
    veut_rester: Mapped[str | None] = mapped_column(String, nullable=True)
    speed_down: Mapped[float | None] = mapped_column(Float, default=0)
    speed_up: Mapped[float | None] = mapped_column(Float, default=0)
    fournisseur_energie: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_elec: Mapped[float | None] = mapped_column(Float, default=0)
    cout_gaz: Mapped[float | None] = mapped_column(Float, default=0)
    economie_estimee_an: Mapped[float | None] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)
    date_relance: Mapped[str | None] = mapped_column(String, nullable=True)
    statut_relance: Mapped[str | None] = mapped_column(String, default="Aucune")

    contrats: Mapped[list["Contrat"]] = relationship(back_populates="client")

\\\`n

## 📄 backend\models\commission.py

\\\python

# ==============================================================================
#  COMMISSION — tracking des commissions à recevoir (fournisseur) et à
#  facturer (client sur % économies).
#
#  Statuts :
#    - attendue : commission promise mais non encore confirmée
#    - confirmee : le fournisseur/client a confirmé le paiement
#    - recue : argent reçu sur le compte
#    - contestee : problème à investiguer
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.dossier import Dossier


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id"), nullable=False)

    source: Mapped[str] = mapped_column(String, nullable=False)   # 'fournisseur' | 'client'
    montant: Mapped[float] = mapped_column(Float, nullable=False)
    statut: Mapped[str] = mapped_column(String, default="attendue")

    date_prevue: Mapped[str | None] = mapped_column(String, nullable=True)
    date_recue: Mapped[str | None] = mapped_column(String, nullable=True)

    reference_paiement: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    dossier: Mapped["Dossier"] = relationship(back_populates="commissions")

\\\`n

## 📄 backend\models\contrat.py

\\\python

# ==============================================================================
#  CONTRAT — miroir de la table `contrats` (src/db.py).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client


class Contrat(Base):
    __tablename__ = "contrats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    univers: Mapped[str | None] = mapped_column(String, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)
    nom_offre: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_mensuel: Mapped[float | None] = mapped_column(Float, default=0)
    economie_mensuelle: Mapped[float | None] = mapped_column(Float, default=0)
    reference_contrat: Mapped[str | None] = mapped_column(String, nullable=True)
    statut_contrat: Mapped[str | None] = mapped_column(String, nullable=True)
    date_souscription: Mapped[str | None] = mapped_column(String, nullable=True)
    date_fin_engagement: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="contrats")

\\\`n

## 📄 backend\models\document.py

\\\python

# ==============================================================================
#  DOCUMENT — document KYC uploadé par un client (CNI, justificatif de
#  domicile, RIB), validé par backend/services/kyc_engine.py.
#  `statut_kyc` : en_attente | valide | rejete | erreur.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    type_document: Mapped[str | None] = mapped_column(String, nullable=True)
    url_stockage: Mapped[str] = mapped_column(String, nullable=False)
    statut_kyc: Mapped[str] = mapped_column(String, default="en_attente", server_default="en_attente")
    motif_rejet: Mapped[str | None] = mapped_column(String, nullable=True)
    date_upload: Mapped[str | None] = mapped_column(String, nullable=True)
    date_validation: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship()

\\\`n

## 📄 backend\models\dossier.py

\\\python

# ==============================================================================
#  DOSSIER — représente un dossier de souscription / changement d'offre pour un
#  client. Machine à états stricte via `statut`.
#
#  Cycle de vie type :
#    initie → docs_demandes → docs_recus → mandat_a_signer → mandat_signe
#            → soumis_fournisseur → en_activation → actif → facture
#            (ou → echec / annule)
#
#  Chaque transition d'état est validée par backend/services/dossier_engine.py
#  et journalisée dans notes_workflow (JSONB).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client
    from backend.models.commission import Commission


STATUTS_DOSSIER = (
    "initie",
    "docs_demandes",
    "docs_recus",
    "mandat_a_signer",
    "mandat_signe",
    "soumis_fournisseur",
    "en_activation",
    "actif",
    "facture",
    "echec",
    "annule",
)


class Dossier(Base):
    __tablename__ = "dossiers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    contrat_id: Mapped[int | None] = mapped_column(ForeignKey("contrats.id"), nullable=True)
    offre_cible_id: Mapped[int | None] = mapped_column(ForeignKey("offres.id"), nullable=True)

    # Contexte du dossier
    univers: Mapped[str] = mapped_column(String, nullable=False)          # telecom, energie, alarme, tpe...
    fournisseur_cible: Mapped[str | None] = mapped_column(String, nullable=True)
    economie_annuelle_estimee: Mapped[float] = mapped_column(Float, default=0.0)

    # État
    statut: Mapped[str] = mapped_column(String, default="initie", nullable=False)

    # Dates clés (chaînes "%d/%m/%Y %H:%M" pour cohérence avec le reste)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_soumission: Mapped[str | None] = mapped_column(String, nullable=True)
    date_activation_prevue: Mapped[str | None] = mapped_column(String, nullable=True)
    date_activation_reelle: Mapped[str | None] = mapped_column(String, nullable=True)

    # Suivi fournisseur
    reference_fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)

    # Rémunération
    commission_attendue: Mapped[float] = mapped_column(Float, default=0.0)
    commission_recue: Mapped[float] = mapped_column(Float, default=0.0)
    part_client_totale: Mapped[float] = mapped_column(Float, default=0.0)
    duree_prelevement_mois: Mapped[int] = mapped_column(Integer, default=0)

    # Journal des transitions (JSONB en Postgres)
    notes_workflow: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Assignation
    conseiller_responsable: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relations
    client: Mapped["Client"] = relationship()
    commissions: Mapped[list["Commission"]] = relationship(back_populates="dossier")

\\\`n

## 📄 backend\models\mandat.py

\\\python

# ==============================================================================
#  MANDAT — mandat de représentation envoyé en signature électronique (Yousign)
#  pour un client. `statut` : brouillon | envoye | signe | refuse | erreur.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client


class Mandat(Base):
    __tablename__ = "mandats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    statut: Mapped[str] = mapped_column(String, default="brouillon", server_default="brouillon")
    pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_signe_url: Mapped[str | None] = mapped_column(String, nullable=True)
    yousign_signature_request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    yousign_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_envoi: Mapped[str | None] = mapped_column(String, nullable=True)
    date_signature: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship()

\\\`n

## 📄 backend\models\offre.py

\\\python

# ==============================================================================
#  OFFRE — miroir de la table `offres` (catalogue, src/db.py).
# ==============================================================================
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Offre(Base):
    __tablename__ = "offres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    univers: Mapped[str | None] = mapped_column(String, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)
    nom_offre: Mapped[str | None] = mapped_column(String, nullable=True)
    prix_mensuel: Mapped[float | None] = mapped_column(Float, nullable=True)
    frais_activation: Mapped[float | None] = mapped_column(Float, nullable=True)
    engagement_mois: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caracteristiques: Mapped[str | None] = mapped_column(String, nullable=True)
    commission_affiliation: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_go: Mapped[float | None] = mapped_column(Float, default=0)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    url_souscription: Mapped[str | None] = mapped_column(String, nullable=True)
    code_affiliation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_maj: Mapped[str | None] = mapped_column(String, nullable=True)

\\\`n

## 📄 backend\models\prospect.py

\\\python

# ==============================================================================
#  PROSPECT — miroir de la table `prospects` (src/db.py, création + colonnes
#  ajoutées par _migrer_bdd()). Les dates restent des chaînes "%d/%m/%Y %H:%M"
#  pour rester compatibles avec le formatage utilisé côté Streamlit (src/app.py).
# ==============================================================================
from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ref: Mapped[str | None] = mapped_column(String, nullable=True)
    prenom: Mapped[str | None] = mapped_column(String, nullable=True)
    nom: Mapped[str | None] = mapped_column(String, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    code_postal: Mapped[str | None] = mapped_column(String, nullable=True)
    ville: Mapped[str | None] = mapped_column(String, nullable=True)
    adresse: Mapped[str | None] = mapped_column(String, nullable=True)
    type_client: Mapped[str | None] = mapped_column(String, nullable=True)
    univers_interesse: Mapped[str | None] = mapped_column(String, nullable=True)
    service_principal: Mapped[str | None] = mapped_column(String, nullable=True)
    operateur_actuel: Mapped[str | None] = mapped_column(String, nullable=True)
    techno: Mapped[str | None] = mapped_column(String, nullable=True)
    data_go: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_mensuel_actuel: Mapped[float | None] = mapped_column(Float, default=0)
    offre_actuelle: Mapped[str | None] = mapped_column(String, nullable=True)
    satisfaction_reseau: Mapped[str | None] = mapped_column(String, nullable=True)
    veut_rester: Mapped[str | None] = mapped_column(String, nullable=True)
    speed_down: Mapped[float | None] = mapped_column(Float, default=0)
    speed_up: Mapped[float | None] = mapped_column(Float, default=0)
    cout_elec: Mapped[float | None] = mapped_column(Float, default=0)
    cout_gaz: Mapped[float | None] = mapped_column(Float, default=0)
    fournisseur_energie: Mapped[str | None] = mapped_column(String, nullable=True)
    abonnements: Mapped[str | None] = mapped_column(String, nullable=True)
    lignes_multi: Mapped[str | None] = mapped_column(String, nullable=True)
    economie_estimee_an: Mapped[float | None] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    statut: Mapped[str | None] = mapped_column(String, default="À relancer")
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_relance: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)
    offres_interet: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, default=0)
    origine: Mapped[str | None] = mapped_column(String, default="Manuel")

\\\`n

## 📄 backend\models\token_public.py

\\\python

# ==============================================================================
#  TOKEN PUBLIC — lien unique donné au client pour accéder à son dossier sans
#  login. Généré par le conseiller, envoyé au client par SMS/email.
#
#  URL type : https://client.iaconseil.fr/dossier/<token>
#
#  Sécurité :
#    - Token = 32 caractères URL-safe (secrets.token_urlsafe)
#    - Expiration configurable (par défaut 30 jours)
#    - Optionnel : lock sur l'IP de première utilisation
#    - Révocable à tout moment par le conseiller
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.dossier import Dossier
    from backend.models.client import Client


class TokenPublic(Base):
    __tablename__ = "tokens_publics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # Ce à quoi le token donne accès
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    dossier_id: Mapped[int | None] = mapped_column(ForeignKey("dossiers.id"), nullable=True)

    # Permissions granulaires
    peut_uploader_docs: Mapped[bool] = mapped_column(Boolean, default=True)
    peut_signer_mandat: Mapped[bool] = mapped_column(Boolean, default=True)
    peut_voir_suivi: Mapped[bool] = mapped_column(Boolean, default=True)

    # Cycle de vie
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_expiration: Mapped[str | None] = mapped_column(String, nullable=True)
    date_premiere_utilisation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_derniere_utilisation: Mapped[str | None] = mapped_column(String, nullable=True)

    # Sécurité
    ip_premiere_utilisation: Mapped[str | None] = mapped_column(String, nullable=True)
    nb_utilisations: Mapped[int] = mapped_column(Integer, default=0)
    revoque: Mapped[bool] = mapped_column(Boolean, default=False)
    motif_revocation: Mapped[str | None] = mapped_column(String, nullable=True)

    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship()
    dossier: Mapped["Dossier | None"] = relationship()

\\\`n

## 📄 backend\models\user.py

\\\python

# ==============================================================================
#  UTILISATEUR — miroir de la table `utilisateurs` (src/db.py). Le hachage du
#  mot de passe (PBKDF2-SHA256, 260k itérations) reste géré par
#  backend/core/security.py, pas par le modèle.
# ==============================================================================
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class User(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nom_complet: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="Conseiller", server_default="Conseiller")
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    doit_changer_mdp: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

\\\`n

## 📄 backend\routers\__init__.py

\\\python


\\\`n

## 📄 backend\routers\auth.py

\\\python

# ==============================================================================
#  AUTH — login, refresh token, mot de passe oublié / réinitialisation.
# ==============================================================================
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import (
    TokenType,
    creer_access_token,
    creer_refresh_token,
    decoder_token,
    get_current_user,
    hash_password,
    verify_password,
)
from backend.models.user import User
from backend.schemas.auth import (
    AccessTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from backend.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == payload.username.strip().lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.actif or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiant ou mot de passe incorrect.")
    return TokenResponse(
        access_token=creer_access_token(user),
        refresh_token=creer_refresh_token(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = decoder_token(payload.refresh_token, TokenType.REFRESH)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton de rafraîchissement invalide ou expiré.")

    user = await db.get(User, data["user_id"])
    if user is None or not user.actif:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur introuvable ou désactivé.")
    return AccessTokenResponse(access_token=creer_access_token(user))


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Génère un jeton de réinitialisation à courte durée de vie. La réponse est
    volontairement neutre (ne révèle jamais si l'identifiant existe).

    TODO (sprint notifications) : envoyer le jeton par email via
    src/email_engine.py / Resend plutôt que de le journaliser — non implémenté
    ici pour rester dans le périmètre du squelette backend/."""
    result = await db.execute(select(User).where(User.username == payload.username.strip().lower()))
    user = result.scalar_one_or_none()
    if user is not None and user.actif:
        pass  # noqa: à brancher sur l'envoi d'email une fois le service dispo
    return {"message": "Si ce compte existe, un lien de réinitialisation a été envoyé."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = decoder_token(payload.reset_token, TokenType.RESET)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Jeton de réinitialisation invalide ou expiré.")

    user = await db.get(User, data["user_id"])
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Jeton de réinitialisation invalide ou expiré.")

    user.password_hash = hash_password(payload.nouveau_mot_de_passe)
    user.doit_changer_mdp = False
    await db.commit()
    return {"message": "Mot de passe mis à jour."}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user

\\\`n

## 📄 backend\routers\clients.py

\\\python

# ==============================================================================
#  CLIENTS — CRUD, protégé par JWT (get_current_user).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.client import Client
from backend.models.user import User
from backend.schemas.client import ClientCreate, ClientOut, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ClientOut])
async def lister_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).order_by(Client.id.desc()))
    return result.scalars().all()


@router.get("/{client_id}", response_model=ClientOut)
async def obtenir_client(client_id: int, db: AsyncSession = Depends(get_db)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    return client


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def creer_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    client = Client(
        **payload.model_dump(),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        cree_par=user.nom_complet,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


@router.put("/{client_id}", response_model=ClientOut)
async def maj_client(client_id: int, payload: ClientUpdate, db: AsyncSession = Depends(get_db)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(client, champ, valeur)
    await db.commit()
    await db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_client(client_id: int, db: AsyncSession = Depends(get_db)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    await db.delete(client)
    await db.commit()

\\\`n

## 📄 backend\routers\dossiers.py

\\\python

# ==============================================================================
#  DOSSIERS — CRUD + machine à états. Protégé par JWT (conseillers uniquement).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.dossier import Dossier
from backend.models.user import User
from backend.schemas.dossier import DossierCreate, DossierOut, DossierUpdate, TransitionStatut
from backend.services import dossier_engine, token_engine

router = APIRouter(prefix="/dossiers", tags=["dossiers"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DossierOut])
async def lister_dossiers(
    statut: str | None = None,
    client_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Dossier).order_by(Dossier.id.desc())
    if statut:
        query = query.where(Dossier.statut == statut)
    if client_id:
        query = query.where(Dossier.client_id == client_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{dossier_id}", response_model=DossierOut)
async def obtenir_dossier(dossier_id: int, db: AsyncSession = Depends(get_db)):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return dossier


@router.post("", response_model=DossierOut, status_code=status.HTTP_201_CREATED)
async def creer_dossier(
    payload: DossierCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dossier = Dossier(
        **payload.model_dump(),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        conseiller_responsable=user.nom_complet,
        notes_workflow=[],
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.put("/{dossier_id}", response_model=DossierOut)
async def maj_dossier(
    dossier_id: int, payload: DossierUpdate, db: AsyncSession = Depends(get_db)
):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(dossier, champ, valeur)
    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.post("/{dossier_id}/transition", response_model=DossierOut)
async def transiter_dossier(
    dossier_id: int,
    payload: TransitionStatut,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    try:
        await dossier_engine.transiter(
            db, dossier, payload.nouveau_statut,
            par=user.username, commentaire=payload.commentaire,
        )
    except dossier_engine.TransitionInvalide as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    return dossier


@router.post("/{dossier_id}/token-client", response_model=dict)
async def generer_lien_client(
    dossier_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère un lien unique à envoyer au client (SMS/email) pour qu'il accède
    à son dossier sans se connecter.
    """
    from backend.core.config import settings

    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")

    token = await token_engine.generer_token(
        db,
        client_id=dossier.client_id,
        dossier_id=dossier.id,
        cree_par=user.username,
    )

    url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
    return {
        "token": token.token,
        "url": url,
        "expire_le": token.date_expiration,
        "message_sms_suggere": (
            f"Bonjour, voici votre lien personnel pour finaliser votre changement d'offre "
            f"en quelques clics : {url} (valable 30 jours). Votre conseiller."
        ),
    }

\\\`n

## 📄 backend\routers\factures.py

\\\python

# ==============================================================================
#  FACTURES — analyse structurée d'une facture PDF (télécom/énergie) via LLM.
#  Expose backend/services/facture_analyzer.py en HTTP (jusque-là écrit mais
#  jamais appelable autrement qu'en import Python direct).
# ==============================================================================
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from backend.core.security import get_current_user
from backend.models.user import User
from backend.schemas.facture import FactureAnalyseOut
from backend.services.facture_analyzer import FactureAnalyzerError, analyser_facture

router = APIRouter(prefix="/factures", tags=["factures"], dependencies=[Depends(get_current_user)])


@router.post("/analyze", response_model=FactureAnalyseOut)
async def analyser(fichier: UploadFile, user: User = Depends(get_current_user)):
    if Path(fichier.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Seuls les fichiers PDF sont acceptés.")

    contenu = await fichier.read()
    # delete=False + suppression manuelle : sous Windows, un NamedTemporaryFile
    # ouvert (delete=True) ne peut pas être rouvert par chemin par un second
    # appel (PermissionError) — analyser_facture() a besoin de le rouvrir.
    fd, chemin_tmp = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(contenu)
        return analyser_facture(chemin_tmp)
    except FactureAnalyzerError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    finally:
        os.unlink(chemin_tmp)

\\\`n

## 📄 backend\routers\portail_public.py

\\\python

# ==============================================================================
#  PORTAIL PUBLIC — endpoints accessibles au client via son token unique.
#
#  Option A (retenue) : pas de login. Le token est vérifié à chaque appel.
#
#  Sécurité :
#    - Rate limiting côté reverse proxy (nginx) + slowapi (à ajouter)
#    - Token vérifié à chaque requête (pas de session)
#    - IP loggée à chaque accès pour audit
#    - Pas de données sensibles remontées
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.models.client import Client
from backend.models.document import Document
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.models.token_public import TokenPublic
from backend.schemas.portail_public import (
    DocumentDemandeOut,
    SuiviDossierOut,
    SuiviEtape,
    TokenPublicContexte,
    UploadResultOut,
)
from backend.services import dossier_engine, storage_engine, token_engine
from backend.services.kyc_engine import KycError, valider_document

router = APIRouter(prefix="/portail", tags=["portail_public"])


async def _resoudre_token(
    token: str, request: Request, db: AsyncSession
) -> TokenPublic:
    ip = request.client.host if request.client else None
    token_obj = await token_engine.valider_token(db, token, ip_appelant=ip)
    if token_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lien invalide, expiré ou révoqué.")
    return token_obj


@router.get("/{token}", response_model=TokenPublicContexte)
async def contexte_token(
    request: Request,
    token: str = Path(..., min_length=32),
    db: AsyncSession = Depends(get_db),
):
    token_obj = await _resoudre_token(token, request, db)

    client = await db.get(Client, token_obj.client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")

    dossier: Dossier | None = None
    if token_obj.dossier_id:
        dossier = await db.get(Dossier, token_obj.dossier_id)

    univers = dossier.univers if dossier else "telecom_mobile"
    types_requis = dossier_engine.documents_requis_pour_univers(univers)

    docs_existants = (await db.execute(
        select(Document).where(Document.client_id == client.id)
    )).scalars().all()
    docs_par_type = {d.type_document: d for d in docs_existants}

    documents_a_fournir: list[DocumentDemandeOut] = []
    for demande in types_requis:
        doc_existant = docs_par_type.get(demande["type_document"])
        if doc_existant is None:
            documents_a_fournir.append(DocumentDemandeOut(
                type_document=demande["type_document"],
                label_affiche=demande["label_affiche"],
                statut="a_fournir",
            ))
        else:
            documents_a_fournir.append(DocumentDemandeOut(
                type_document=demande["type_document"],
                label_affiche=demande["label_affiche"],
                statut=doc_existant.statut_kyc,
                motif_rejet=doc_existant.motif_rejet,
                date_upload=doc_existant.date_upload,
            ))

    mandat_statut = None
    if dossier and dossier.statut == "mandat_a_signer":
        mandat = (await db.execute(
            select(Mandat).where(Mandat.client_id == client.id).order_by(Mandat.id.desc())
        )).scalars().first()
        if mandat:
            mandat_statut = "signe" if mandat.statut == "signe" else "a_signer"

    return TokenPublicContexte(
        prenom_client=client.prenom or "",
        nom_client=client.nom or "",
        dossier_id=dossier.id if dossier else None,
        univers=dossier.univers if dossier else None,
        fournisseur_cible=dossier.fournisseur_cible if dossier else None,
        economie_annuelle_estimee=dossier.economie_annuelle_estimee if dossier else 0.0,
        statut_dossier=dossier.statut if dossier else None,
        conseiller_nom=dossier.conseiller_responsable if dossier else client.cree_par,
        documents_a_fournir=documents_a_fournir,
        mandat_statut=mandat_statut,
        peut_uploader_docs=token_obj.peut_uploader_docs,
        peut_signer_mandat=token_obj.peut_signer_mandat,
    )


@router.post("/{token}/documents", response_model=UploadResultOut)
async def uploader_document(
    request: Request,
    token: str = Path(..., min_length=32),
    type_document: str = "cni",
    fichier: UploadFile = None,
    db: AsyncSession = Depends(get_db),
):
    token_obj = await _resoudre_token(token, request, db)

    if not token_obj.peut_uploader_docs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Upload de documents non autorisé.")

    if fichier is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Aucun fichier.")

    contenu = await fichier.read()
    if len(contenu) > 10 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Fichier trop volumineux (max 10 Mo).")

    try:
        cle_s3 = storage_engine.upload_document(
            client_id=token_obj.client_id,
            type_document=type_document,
            contenu=contenu,
            nom_fichier=fichier.filename or "document.pdf",
        )
    except storage_engine.StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Stockage impossible : {exc}")

    type_detecte = None
    statut_kyc = "en_attente"
    motif = None
    try:
        resultat = valider_document(contenu, fichier.filename or "document.pdf")
        type_detecte = resultat["type"]
        statut_kyc = "valide" if resultat["valide"] else "rejete"
        motif = resultat["motif_rejet"]
    except KycError as exc:
        statut_kyc = "erreur"
        motif = str(exc)

    document = Document(
        client_id=token_obj.client_id,
        type_document=type_detecte or type_document,
        url_stockage=cle_s3,
        statut_kyc=statut_kyc,
        motif_rejet=motif,
        date_upload=datetime.now().strftime("%d/%m/%Y %H:%M"),
        date_validation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return UploadResultOut(
        document_id=document.id,
        type_detecte=type_detecte,
        statut_kyc=statut_kyc,
        motif_rejet=motif,
        message=_message_client(statut_kyc, motif),
    )


def _message_client(statut: str, motif: str | None) -> str:
    if statut == "valide":
        return "✅ Document reçu et validé automatiquement."
    if statut == "rejete":
        return f"⚠️ Document non conforme : {motif or 'motif non précisé'}. Merci de refaire l'upload."
    if statut == "erreur":
        return "Document reçu, en attente de vérification par votre conseiller."
    return "Document reçu."


@router.get("/{token}/suivi", response_model=SuiviDossierOut)
async def suivi_dossier(
    request: Request,
    token: str = Path(..., min_length=32),
    db: AsyncSession = Depends(get_db),
):
    token_obj = await _resoudre_token(token, request, db)

    if not token_obj.peut_voir_suivi or not token_obj.dossier_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Suivi non disponible.")

    dossier = await db.get(Dossier, token_obj.dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")

    etapes_dict = dossier_engine.construire_timeline(dossier)
    etapes = [SuiviEtape(**e) for e in etapes_dict]

    return SuiviDossierOut(
        dossier_id=dossier.id,
        statut_actuel=dossier.statut,
        etapes=etapes,
        prochaine_action=_prochaine_action(dossier.statut),
    )


def _prochaine_action(statut: str) -> str | None:
    return {
        "initie": "Votre conseiller prépare votre dossier.",
        "docs_demandes": "Merci d'uploader les documents demandés.",
        "docs_recus": "Vos documents sont en cours de vérification.",
        "mandat_a_signer": "Merci de signer votre mandat de représentation.",
        "mandat_signe": "Votre dossier va être envoyé au fournisseur.",
        "soumis_fournisseur": "Dossier envoyé, en attente de validation fournisseur.",
        "en_activation": "Votre nouvelle offre s'active.",
        "actif": "🎉 Tout est actif ! Bienvenue.",
    }.get(statut)

\\\`n

## 📄 backend\routers\prospects.py

\\\python

# ==============================================================================
#  PROSPECTS — CRUD, protégé par JWT (get_current_user).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.schemas.prospect import ProspectCreate, ProspectOut, ProspectUpdate

router = APIRouter(prefix="/prospects", tags=["prospects"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ProspectOut])
async def lister_prospects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prospect).order_by(Prospect.id.desc()))
    return result.scalars().all()


@router.get("/{prospect_id}", response_model=ProspectOut)
async def obtenir_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    return prospect


@router.post("", response_model=ProspectOut, status_code=status.HTTP_201_CREATED)
async def creer_prospect(
    payload: ProspectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prospect = Prospect(
        **payload.model_dump(),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        cree_par=user.nom_complet,
    )
    db.add(prospect)
    await db.commit()
    await db.refresh(prospect)
    return prospect


@router.put("/{prospect_id}", response_model=ProspectOut)
async def maj_prospect(prospect_id: int, payload: ProspectUpdate, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(prospect, champ, valeur)
    await db.commit()
    await db.refresh(prospect)
    return prospect


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    await db.delete(prospect)
    await db.commit()

\\\`n

## 📄 backend\routers\webhooks.py

\\\python

# ==============================================================================
#  WEBHOOKS — endpoints appelés par des prestataires externes (Yousign). Non
#  protégés par JWT : l'authenticité est vérifiée via signature HMAC.
# ==============================================================================
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.models.mandat import Mandat
from backend.services import signature_engine
from backend.workers.tasks import telecharger_mandat_signe

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/yousign", status_code=status.HTTP_204_NO_CONTENT)
async def webhook_yousign(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_yousign_signature_256: str | None = Header(default=None),
):
    corps_brut = await request.body()
    if not signature_engine.verifier_signature_webhook(corps_brut, x_yousign_signature_256):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signature webhook invalide.")

    evenement = signature_engine.parser_evenement_webhook(await request.json())
    signature_request_id = evenement["signature_request_id"]
    if not signature_request_id:
        return

    mandat = (
        await db.execute(select(Mandat).where(Mandat.yousign_signature_request_id == signature_request_id))
    ).scalar_one_or_none()
    if mandat is None:
        return

    if evenement["event_name"] == "signature_request.done":
        telecharger_mandat_signe.delay(mandat.id)
    elif evenement["event_name"] == "signature_request.refused":
        mandat.statut = "refuse"
        await db.commit()

\\\`n

## 📄 backend\schemas\__init__.py

\\\python


\\\`n

## 📄 backend\schemas\auth.py

\\\python

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    nouveau_mot_de_passe: str

\\\`n

## 📄 backend\schemas\client.py

\\\python

from pydantic import BaseModel, ConfigDict


class ClientBase(BaseModel):
    ref: str | None = None
    prenom: str | None = None
    nom: str | None = None
    telephone: str | None = None
    email: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    adresse: str | None = None
    type_client: str | None = None
    operateur_actuel: str | None = None
    techno: str | None = None
    data_go: str | None = None
    offre_actuelle: str | None = None
    cout_mensuel_actuel: float | None = None
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    speed_down: float | None = None
    speed_up: float | None = None
    fournisseur_energie: str | None = None
    cout_elec: float | None = None
    cout_gaz: float | None = None
    economie_estimee_an: float | None = None
    notes: str | None = None
    date_relance: str | None = None
    statut_relance: str | None = None


class ClientCreate(ClientBase):
    prenom: str
    nom: str


class ClientUpdate(ClientBase):
    pass


class ClientOut(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_creation: str | None = None
    cree_par: str | None = None

\\\`n

## 📄 backend\schemas\dossier.py

\\\python

from pydantic import BaseModel, ConfigDict


class DossierBase(BaseModel):
    univers: str
    fournisseur_cible: str | None = None
    offre_cible_id: int | None = None
    economie_annuelle_estimee: float = 0.0


class DossierCreate(DossierBase):
    client_id: int


class DossierUpdate(BaseModel):
    fournisseur_cible: str | None = None
    offre_cible_id: int | None = None
    economie_annuelle_estimee: float | None = None
    reference_fournisseur: str | None = None
    date_activation_prevue: str | None = None
    conseiller_responsable: str | None = None


class DossierOut(DossierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    statut: str
    date_creation: str | None = None
    date_soumission: str | None = None
    date_activation_prevue: str | None = None
    date_activation_reelle: str | None = None
    reference_fournisseur: str | None = None
    commission_attendue: float = 0.0
    commission_recue: float = 0.0
    part_client_totale: float = 0.0
    duree_prelevement_mois: int = 0
    conseiller_responsable: str | None = None
    notes_workflow: list | None = None


class TransitionStatut(BaseModel):
    nouveau_statut: str
    commentaire: str | None = None

\\\`n

## 📄 backend\schemas\facture.py

\\\python

from pydantic import BaseModel


class FactureAnalyseOut(BaseModel):
    operateur: str
    prix_ht: float
    prix_ttc: float
    data_conso_go: float
    options: list[str]
    engagement_mois: int
    date_fin_engagement: str
    iban_prelevement: str

\\\`n

## 📄 backend\schemas\portail_public.py

\\\python

# ==============================================================================
#  SCHEMAS PORTAIL PUBLIC — vue simplifiée du dossier, exposée au client via
#  son lien unique. On ne remonte que le strict nécessaire — pas de données
#  internes conseiller, pas de commissions, pas de refs autres clients.
# ==============================================================================
from pydantic import BaseModel


class DocumentDemandeOut(BaseModel):
    """Un document que le client doit uploader."""
    type_document: str          # "cni", "justificatif_domicile", "rib"
    label_affiche: str          # "Pièce d'identité", "Justificatif de domicile", etc.
    statut: str                 # "a_fournir", "en_attente", "valide", "rejete"
    motif_rejet: str | None = None
    date_upload: str | None = None


class TokenPublicContexte(BaseModel):
    """Vue publique du contexte du token — ce que le client voit en arrivant."""
    prenom_client: str
    nom_client: str
    dossier_id: int | None
    univers: str | None
    fournisseur_cible: str | None
    economie_annuelle_estimee: float
    statut_dossier: str | None
    conseiller_nom: str | None
    conseiller_telephone: str | None = None

    # Ce qu'il doit faire
    documents_a_fournir: list[DocumentDemandeOut]
    mandat_statut: str | None      # "a_signer", "signe", None
    peut_uploader_docs: bool
    peut_signer_mandat: bool


class UploadResultOut(BaseModel):
    document_id: int
    type_detecte: str | None
    statut_kyc: str
    motif_rejet: str | None = None
    message: str


class SuiviEtape(BaseModel):
    """Une étape de timeline pour l'affichage client."""
    cle: str                    # "docs_demandes", "mandat_signe", ...
    label: str                  # "Vos documents nous parviennent"
    statut: str                 # "termine", "en_cours", "a_venir"
    date: str | None = None
    icone: str = "circle"


class SuiviDossierOut(BaseModel):
    dossier_id: int
    statut_actuel: str
    etapes: list[SuiviEtape]
    prochaine_action: str | None = None

\\\`n

## 📄 backend\schemas\prospect.py

\\\python

from pydantic import BaseModel, ConfigDict


class ProspectBase(BaseModel):
    ref: str | None = None
    prenom: str | None = None
    nom: str | None = None
    telephone: str | None = None
    email: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    adresse: str | None = None
    type_client: str | None = None
    univers_interesse: str | None = None
    service_principal: str | None = None
    operateur_actuel: str | None = None
    techno: str | None = None
    data_go: str | None = None
    cout_mensuel_actuel: float | None = None
    offre_actuelle: str | None = None
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    speed_down: float | None = None
    speed_up: float | None = None
    cout_elec: float | None = None
    cout_gaz: float | None = None
    fournisseur_energie: str | None = None
    abonnements: str | None = None
    lignes_multi: str | None = None
    economie_estimee_an: float | None = None
    notes: str | None = None
    statut: str | None = None
    date_relance: str | None = None
    offres_interet: str | None = None
    score: float | None = None
    origine: str | None = None


class ProspectCreate(ProspectBase):
    prenom: str
    nom: str


class ProspectUpdate(ProspectBase):
    pass


class ProspectOut(ProspectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_creation: str | None = None
    cree_par: str | None = None

\\\`n

## 📄 backend\schemas\user.py

\\\python

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nom_complet: str
    role: str
    actif: bool
    doit_changer_mdp: bool

\\\`n

## 📄 backend\services\__init__.py

\\\python


\\\`n

## 📄 backend\services\dossier_engine.py

\\\python

# ==============================================================================
#  DOSSIER ENGINE — machine à états stricte pour le workflow de souscription.
#
#  Transitions autorisées :
#
#   initie ──► docs_demandes ──► docs_recus ──► mandat_a_signer ──►
#     mandat_signe ──► soumis_fournisseur ──► en_activation ──►
#     actif ──► facture
#
#  N'importe quel état non-terminal peut aussi transiter vers :
#    - echec (échec fournisseur/technique)
#    - annule (client renonce)
# ==============================================================================
from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.dossier import Dossier


FORMAT_DATE = "%d/%m/%Y %H:%M"


TRANSITIONS_AUTORISEES: dict[str, set[str]] = {
    "initie":              {"docs_demandes", "annule"},
    "docs_demandes":       {"docs_recus", "annule", "echec"},
    "docs_recus":          {"mandat_a_signer", "annule", "echec"},
    "mandat_a_signer":     {"mandat_signe", "annule", "echec"},
    "mandat_signe":        {"soumis_fournisseur", "annule", "echec"},
    "soumis_fournisseur":  {"en_activation", "echec"},
    "en_activation":       {"actif", "echec"},
    "actif":               {"facture"},
    "facture":             set(),
    "echec":               set(),
    "annule":              set(),
}


class TransitionInvalide(Exception):
    """La transition demandée n'est pas autorisée depuis l'état actuel."""


def peut_transiter(depuis: str, vers: str) -> bool:
    return vers in TRANSITIONS_AUTORISEES.get(depuis, set())


async def transiter(
    db: AsyncSession,
    dossier: Dossier,
    nouveau_statut: str,
    *,
    par: str = "systeme",
    commentaire: str | None = None,
    on_transition: Callable[[Dossier, str], None] | None = None,
) -> Dossier:
    """Effectue la transition d'état, journalise et met à jour les dates clés."""
    ancien_statut = dossier.statut
    if not peut_transiter(ancien_statut, nouveau_statut):
        raise TransitionInvalide(
            f"Transition invalide : {ancien_statut} → {nouveau_statut}. "
            f"Transitions possibles : {sorted(TRANSITIONS_AUTORISEES.get(ancien_statut, set()))}"
        )

    now_str = datetime.now().strftime(FORMAT_DATE)
    dossier.statut = nouveau_statut

    if nouveau_statut == "soumis_fournisseur":
        dossier.date_soumission = now_str
    elif nouveau_statut == "actif":
        dossier.date_activation_reelle = now_str

    entree = {
        "date": now_str,
        "de": ancien_statut,
        "vers": nouveau_statut,
        "par": par,
    }
    if commentaire:
        entree["commentaire"] = commentaire
    dossier.notes_workflow = (dossier.notes_workflow or []) + [entree]

    if on_transition:
        on_transition(dossier, ancien_statut)

    await db.commit()
    await db.refresh(dossier)
    return dossier


def documents_requis_pour_univers(univers: str) -> list[dict]:
    """Retourne la liste des documents à demander au client pour un univers donné."""
    base = [
        {"type_document": "cni", "label_affiche": "Pièce d'identité (recto + verso)"},
        {"type_document": "rib", "label_affiche": "RIB"},
    ]
    if univers in ("telecom_box", "energie", "energie_pro", "assurance_habitation"):
        base.insert(1, {"type_document": "justificatif_domicile", "label_affiche": "Justificatif de domicile (< 3 mois)"})
    return base


def construire_timeline(dossier: Dossier) -> list[dict]:
    """Retourne la timeline à afficher au client dans son portail."""
    ordre = [
        ("docs_demandes",       "Nous vous demandons vos documents"),
        ("docs_recus",          "Documents vérifiés"),
        ("mandat_a_signer",     "Signature de votre mandat"),
        ("mandat_signe",        "Mandat signé"),
        ("soumis_fournisseur",  "Envoi de votre dossier au fournisseur"),
        ("en_activation",       "Activation en cours"),
        ("actif",               "Votre nouvelle offre est active"),
    ]
    statut_actuel = dossier.statut
    ordre_index = {k: i for i, (k, _) in enumerate(ordre)}
    idx_actuel = ordre_index.get(statut_actuel, -1)

    dates_par_statut = {}
    for entree in (dossier.notes_workflow or []):
        dates_par_statut[entree.get("vers")] = entree.get("date")

    etapes = []
    for i, (cle, label) in enumerate(ordre):
        if i < idx_actuel:
            statut_etape = "termine"
        elif i == idx_actuel:
            statut_etape = "en_cours"
        else:
            statut_etape = "a_venir"
        etapes.append({
            "cle": cle,
            "label": label,
            "statut": statut_etape,
            "date": dates_par_statut.get(cle),
            "icone": "check" if statut_etape == "termine" else ("clock" if statut_etape == "en_cours" else "circle"),
        })
    return etapes

\\\`n

## 📄 backend\services\facture_analyzer.py

\\\python

# ==============================================================================
#  ANALYSE FACTURE — extraction structurée (télécom/énergie) via Claude Haiku
#  vision, en remplacement du regex src/pdf_engine.py::analyser_facture
#  (~60% de précision). Même approche que backend/services/kyc_engine.py
#  (prompt système strict, parsing tolérant), avec ici des exemples few-shot
#  dans le prompt système pour stabiliser le format de sortie.
# ==============================================================================
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import anthropic

from backend.core.config import settings

MODEL_FACTURE_DEFAUT = "claude-haiku-4-5-20251001"

CHAMPS_FACTURE = (
    "operateur", "prix_ht", "prix_ttc", "data_conso_go", "options",
    "engagement_mois", "date_fin_engagement", "iban_prelevement",
)

SYSTEM_PROMPT_FACTURE = """Tu es un extracteur de données pour des factures françaises de télécom \
(mobile, box/fibre) et d'énergie (électricité, gaz), fournies en PDF (texte ou scan/image).

Réponds UNIQUEMENT avec un objet JSON valide (rien avant, rien après), avec exactement ces clés :
{"operateur": "", "prix_ht": 0.0, "prix_ttc": 0.0, "data_conso_go": 0.0, "options": [], \
"engagement_mois": 0, "date_fin_engagement": "", "iban_prelevement": ""}

Règles :
- operateur : nom de l'opérateur télécom ou du fournisseur d'énergie émetteur de la facture \
(Orange, SFR, Bouygues, Free, EDF, Engie, TotalEnergies, Ekwateur...)
- prix_ht / prix_ttc : montants hors taxes et toutes taxes comprises, nombres décimaux avec un \
point (0.0 si absent ou illisible)
- data_conso_go : quantité de data mobile en Go si applicable (forfait mobile), sinon 0.0
- options : liste des options/services inclus mentionnés (ex. "Appels illimités", "Assurance \
smartphone", "TV incluse", "Fibre 1Gb/s"), liste vide si aucune
- engagement_mois : durée d'engagement restante en mois, 0 si sans engagement ou introuvable
- date_fin_engagement : date de fin d'engagement au format "JJ/MM/AAAA", chaîne vide si absente
- iban_prelevement : IBAN utilisé pour le prélèvement s'il est visible sur le document, chaîne \
vide sinon
Si une information est absente ou illisible, utilise la valeur par défaut indiquée ci-dessus. \
Ne réponds rien d'autre que ce JSON.

Exemples :

Facture : Orange, forfait 5G 150 Go, prix HT 38,33 EUR, prix TTC 45,99 EUR, engagement 12 mois \
jusqu'au 15/03/2027, options "Appels illimités" et "Cloud 100 Go", prélèvement IBAN \
FR7630001007941234567890185.
JSON : {"operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99, "data_conso_go": 150.0, \
"options": ["Appels illimités", "Cloud 100 Go"], "engagement_mois": 12, \
"date_fin_engagement": "15/03/2027", "iban_prelevement": "FR7630001007941234567890185"}

Facture : EDF, abonnement + consommation électricité, montant TTC 89,00 EUR, sans engagement, \
aucun prélèvement automatique renseigné sur le document.
JSON : {"operateur": "EDF", "prix_ht": 0.0, "prix_ttc": 89.0, "data_conso_go": 0.0, \
"options": [], "engagement_mois": 0, "date_fin_engagement": "", "iban_prelevement": ""}
"""


class FactureAnalyzerError(Exception):
    """Échec de l'analyse facture (fichier introuvable/non PDF, clé API
    absente, appel ou réponse Claude inexploitables) — à l'appelant de
    décider du repli (nouvelle tentative, saisie manuelle...)."""


def _resultat_vide() -> dict:
    return {
        "operateur": "", "prix_ht": 0.0, "prix_ttc": 0.0, "data_conso_go": 0.0,
        "options": [], "engagement_mois": 0, "date_fin_engagement": "",
        "iban_prelevement": "",
    }


def _vers_float(valeur) -> float:
    if valeur in (None, ""):
        return 0.0
    try:
        return float(str(valeur).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return 0.0


def _vers_int(valeur) -> int:
    if valeur in (None, ""):
        return 0
    try:
        return int(float(str(valeur).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _normaliser(brut: dict) -> dict:
    res = _resultat_vide()
    if not isinstance(brut, dict):
        return res
    for champ in CHAMPS_FACTURE:
        if champ in brut and brut[champ] is not None:
            res[champ] = brut[champ]

    for champ in ("prix_ht", "prix_ttc", "data_conso_go"):
        res[champ] = _vers_float(res[champ])
    res["engagement_mois"] = _vers_int(res["engagement_mois"])

    if not isinstance(res["options"], list):
        res["options"] = []
    res["options"] = [str(o) for o in res["options"]]

    res["operateur"] = str(res["operateur"] or "")
    res["date_fin_engagement"] = str(res["date_fin_engagement"] or "")
    res["iban_prelevement"] = str(res["iban_prelevement"] or "")
    return res


def analyser_facture(
    chemin_pdf: str | Path, model: str = MODEL_FACTURE_DEFAUT, api_key: str | None = None
) -> dict:
    """Extrait les données structurées d'une facture PDF (télécom ou énergie,
    texte ou scan/image) via Claude Haiku vision. Retourne un dict avec les
    clés operateur, prix_ht, prix_ttc, data_conso_go, options,
    engagement_mois, date_fin_engagement, iban_prelevement.

    `api_key` permet à un appelant qui gère sa propre résolution de clé (ex.
    src/secrets_config.py côté Streamlit) de la fournir directement ; à
    défaut, repli sur `settings.anthropic_api_key` (backend/.env).

    Lève FactureAnalyzerError si le fichier est introuvable/vide/non PDF, si
    la clé API est absente, ou si l'appel/la réponse Claude sont
    inexploitables — jamais d'exception non gérée en cas d'échec réseau ou de
    réponse malformée."""
    chemin = Path(chemin_pdf)
    if chemin.suffix.lower() != ".pdf":
        raise FactureAnalyzerError(f"Format non supporté (PDF attendu) : {chemin}")
    if not chemin.is_file():
        raise FactureAnalyzerError(f"Fichier introuvable : {chemin}")
    cle = api_key or settings.anthropic_api_key
    if not cle:
        raise FactureAnalyzerError("ANTHROPIC_API_KEY absente (voir backend/.env.example).")

    contenu = chemin.read_bytes()
    if not contenu:
        raise FactureAnalyzerError(f"Fichier vide : {chemin}")
    b64 = base64.b64encode(contenu).decode("ascii")

    try:
        client = anthropic.Anthropic(api_key=cle)
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT_FACTURE,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                    {"type": "text", "text": "Analyse cette facture et réponds avec le JSON attendu."},
                ],
            }],
        )
    except anthropic.APIError as exc:
        raise FactureAnalyzerError(f"Appel Claude échoué : {exc}") from exc

    texte = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    texte = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
    try:
        brut = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise FactureAnalyzerError(f"Réponse Claude inexploitable : {exc}") from exc

    return _normaliser(brut)

\\\`n

## 📄 backend\services\kyc_engine.py

\\\python

# ==============================================================================
#  VALIDATION KYC — CNI, justificatif de domicile (< 3 mois), RIB, via Claude
#  Haiku vision (coût cible ~0,002 € / document). Même approche que
#  src/pdf_engine.py::analyser_facture_vision (prompt JSON strict, parsing
#  tolérant).
# ==============================================================================
from __future__ import annotations

import base64
import json
import re

import anthropic

from backend.core.config import settings

MODEL_KYC_DEFAUT = "claude-haiku-4-5-20251001"

TYPES_DOCUMENT = ("cni", "justificatif_domicile", "rib", "autre")

_MIME_PAR_EXTENSION = {
    "pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
}

PROMPT_KYC = (
    "Tu es un contrôleur KYC pour un mandataire multi-univers (télécom, énergie). "
    "Ce document est-il une CNI valide, un justificatif de domicile de moins de "
    "3 mois, ou un RIB ? Réponds UNIQUEMENT avec un objet JSON valide (rien avant, "
    "rien après), avec exactement ces clés :\n"
    '{"type": "cni|justificatif_domicile|rib|autre", "valide": true|false, "motif_rejet": ""}\n\n'
    "Règles :\n"
    "- type : nature réelle du document, même s'il est invalide\n"
    "- valide : true seulement si le document est lisible, complet, non expiré "
    "(CNI), daté de moins de 3 mois (justificatif de domicile), ou cohérent avec "
    "un IBAN lisible (RIB)\n"
    "- motif_rejet : raison courte et précise si valide=false (ex. \"CNI expirée "
    "le 01/2024\", \"document illisible\", \"facture de plus de 3 mois\"), chaîne "
    "vide si valide=true\n"
    "Ne réponds rien d'autre que ce JSON."
)


class KycError(Exception):
    """Échec de l'analyse KYC (clé API absente, format non supporté, appel ou
    réponse Claude inexploitables) — à l'appelant de décider du repli (relance
    manuelle, nouvelle tentative Celery...)."""


def valider_document(contenu: bytes, nom_fichier: str, model: str = MODEL_KYC_DEFAUT) -> dict:
    """Valide un document KYC (CNI, justificatif de domicile ou RIB — PDF, JPG
    ou PNG) via Claude Haiku vision. Retourne {type, valide, motif_rejet}."""
    if not settings.anthropic_api_key:
        raise KycError("ANTHROPIC_API_KEY absente (voir backend/.env.example).")
    if not contenu:
        raise KycError("Document vide.")

    ext = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else ""
    mime = _MIME_PAR_EXTENSION.get(ext)
    if not mime:
        raise KycError(f"Format non supporté : .{ext or '?'} (attendu pdf/jpg/jpeg/png).")

    bloc_type = "document" if mime == "application/pdf" else "image"
    b64 = base64.b64encode(contenu).decode("ascii")

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {"type": bloc_type, "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": PROMPT_KYC},
                ],
            }],
        )
        texte = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        texte = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
        brut = json.loads(texte)
    except anthropic.APIError as exc:
        raise KycError(f"Appel Claude échoué : {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise KycError(f"Réponse Claude inexploitable : {exc}") from exc

    type_doc = brut.get("type") if brut.get("type") in TYPES_DOCUMENT else "autre"
    return {
        "type": type_doc,
        "valide": bool(brut.get("valide", False)),
        "motif_rejet": str(brut.get("motif_rejet") or ""),
    }

\\\`n

## 📄 backend\services\signature_engine.py

\\\python

# ==============================================================================
#  SIGNATURE ÉLECTRONIQUE — wrapper API Yousign v3 : créer une demande de
#  signature, y attacher le PDF du mandat et le signataire, l'activer (envoi),
#  vérifier/parser les webhooks, télécharger le PDF signé une fois la
#  procédure terminée. Référence API : https://developers.yousign.com
# ==============================================================================
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Literal

import httpx

from backend.core.config import settings

SignatureLevel = Literal["electronic_signature", "advanced_electronic_signature"]
AuthMode = Literal["no_otp", "otp_email", "otp_sms"]


class SignatureEngineError(Exception):
    """Erreur retournée par l'API Yousign (statut HTTP non 2xx) ou clé API
    absente."""


def _client() -> httpx.AsyncClient:
    if not settings.yousign_api_key:
        raise SignatureEngineError("YOUSIGN_API_KEY absente (voir backend/.env.example).")
    return httpx.AsyncClient(
        base_url=settings.yousign_api_url,
        headers={"Authorization": f"Bearer {settings.yousign_api_key}"},
        timeout=30.0,
    )


async def _appel(methode: str, chemin: str, **kwargs: Any) -> dict:
    async with _client() as client:
        reponse = await client.request(methode, chemin, **kwargs)
    if reponse.status_code >= 400:
        raise SignatureEngineError(f"Yousign {methode} {chemin} → {reponse.status_code} : {reponse.text}")
    return reponse.json() if reponse.content else {}


async def creer_demande_signature(nom: str, delivery_mode: str = "email") -> dict:
    """Crée une demande de signature à l'état 'draft'. Retourne l'objet Yousign
    (son id est nécessaire pour toutes les étapes suivantes)."""
    return await _appel(
        "POST",
        "/signature_requests",
        json={"name": nom, "delivery_mode": delivery_mode, "timezone": "Europe/Paris"},
    )


async def ajouter_document(signature_request_id: str, pdf: bytes, nom_fichier: str) -> dict:
    """Attache le PDF du mandat à la demande de signature. Retourne l'objet
    document Yousign (son id est nécessaire pour positionner le champ de
    signature)."""
    fichiers = {"file": (nom_fichier, pdf, "application/pdf")}
    return await _appel(
        "POST",
        f"/signature_requests/{signature_request_id}/documents",
        data={"nature": "signable_document"},
        files=fichiers,
    )


async def ajouter_signataire(
    signature_request_id: str,
    document_id: str,
    *,
    prenom: str,
    nom: str,
    email: str,
    telephone: str | None = None,
    page: int = 1,
    x: int = 100,
    y: int = 100,
    signature_level: SignatureLevel = "electronic_signature",
    auth_mode: AuthMode = "otp_email",
) -> dict:
    """Ajoute le client comme signataire, avec un champ de signature positionné
    sur le document. `auth_mode="otp_email"` par défaut (code reçu par email
    avant signature) — passer "otp_sms" si le téléphone client est vérifié."""
    info: dict[str, Any] = {"first_name": prenom, "last_name": nom, "email": email, "locale": "fr"}
    if telephone:
        info["phone_number"] = telephone
    return await _appel(
        "POST",
        f"/signature_requests/{signature_request_id}/signers",
        json={
            "info": info,
            "signature_level": signature_level,
            "signature_authentication_mode": auth_mode,
            "fields": [{"document_id": document_id, "type": "signature", "page": page, "x": x, "y": y}],
        },
    )


async def activer_demande(signature_request_id: str) -> dict:
    """Passe la demande de 'draft' à 'ongoing' — déclenche l'envoi de
    l'invitation à signer (email ou SMS) au(x) signataire(s)."""
    return await _appel("POST", f"/signature_requests/{signature_request_id}/activate")


async def telecharger_document_signe(signature_request_id: str, document_id: str) -> bytes:
    """Télécharge le PDF signé — disponible uniquement une fois la demande au
    statut 'done' (après réception de l'événement webhook correspondant)."""
    async with _client() as client:
        reponse = await client.get(f"/signature_requests/{signature_request_id}/documents/{document_id}/download")
    if reponse.status_code >= 400:
        raise SignatureEngineError(
            f"Yousign download {signature_request_id}/{document_id} → {reponse.status_code}"
        )
    return reponse.content


async def envoyer_mandat(
    *,
    nom_demande: str,
    pdf: bytes,
    nom_fichier: str,
    prenom: str,
    nom: str,
    email: str,
    telephone: str | None = None,
) -> dict:
    """Orchestration complète : crée la demande, y attache le mandat, ajoute le
    client comme signataire et active l'envoi. Retourne
    {signature_request_id, document_id} à stocker sur le Mandat pour
    retrouver la procédure lors du webhook."""
    demande = await creer_demande_signature(nom_demande)
    signature_request_id = demande["id"]
    document = await ajouter_document(signature_request_id, pdf, nom_fichier)
    document_id = document["id"]
    await ajouter_signataire(
        signature_request_id, document_id,
        prenom=prenom, nom=nom, email=email, telephone=telephone,
    )
    await activer_demande(signature_request_id)
    return {"signature_request_id": signature_request_id, "document_id": document_id}


def verifier_signature_webhook(corps_brut: bytes, signature_recue: str | None) -> bool:
    """Vérifie l'en-tête `X-Yousign-Signature-256` (HMAC-SHA256 du corps brut de
    la requête avec le secret webhook Yousign) — indispensable avant de
    traiter un webhook, qui expose sinon la mise à jour de statut des mandats
    à n'importe quel appelant."""
    if not signature_recue or not settings.yousign_webhook_secret:
        return False
    attendu = hmac.new(settings.yousign_webhook_secret.encode(), corps_brut, hashlib.sha256).hexdigest()
    return hmac.compare_digest(attendu, signature_recue)


def parser_evenement_webhook(payload: dict) -> dict:
    """Extrait du payload webhook Yousign le nom de l'événement ainsi que
    l'id/statut de la demande de signature concernée."""
    demande = payload.get("data", {}).get("signature_request", {})
    return {
        "event_name": payload.get("event_name", ""),
        "signature_request_id": demande.get("id"),
        "status": demande.get("status"),
    }

\\\`n

## 📄 backend\services\storage_engine.py

\\\python

# ==============================================================================
#  STORAGE ENGINE — stockage sécurisé des documents client sur S3 (Scaleway
#  Object Storage recommandé, compatible S3 API).
#
#  Sécurité :
#    - Chiffrement SSE-S3 côté serveur (AES-256)
#    - URLs signées à durée limitée pour les téléchargements
#    - Clés d'objet non-devinables (uuid + hash)
#    - Bucket privé, pas d'accès public
# ==============================================================================
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from backend.core.config import settings


class StorageError(Exception):
    """Erreur d'accès au stockage S3."""


def _client_s3():
    if not settings.s3_bucket:
        raise StorageError("S3 non configuré (voir .env : S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY_ID...).")
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=BotoConfig(signature_version="s3v4"),
    )


def _generer_cle(client_id: int, type_document: str, nom_fichier: str) -> str:
    now = datetime.now()
    unique = uuid.uuid4().hex[:8]
    h = hashlib.sha256(nom_fichier.encode()).hexdigest()[:8]
    ext = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else "bin"
    return f"clients/{client_id}/{now.year}/{now.month:02d}/{type_document}_{unique}_{h}.{ext}"


def upload_document(
    client_id: int,
    type_document: str,
    contenu: bytes,
    nom_fichier: str,
) -> str:
    """Upload un document sur S3 chiffré. Retourne la clé S3."""
    if not contenu:
        raise StorageError("Contenu vide.")

    s3 = _client_s3()
    cle = _generer_cle(client_id, type_document, nom_fichier)

    try:
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=cle,
            Body=contenu,
            ServerSideEncryption="AES256",
            ContentType=_deviner_mime(nom_fichier),
            Metadata={
                "client_id": str(client_id),
                "type_document": type_document,
                "upload_date": datetime.now().isoformat(),
            },
        )
    except ClientError as exc:
        raise StorageError(f"Upload S3 échoué : {exc}") from exc

    return cle


def telecharger_document(cle: str) -> bytes:
    s3 = _client_s3()
    try:
        response = s3.get_object(Bucket=settings.s3_bucket, Key=cle)
        return response["Body"].read()
    except ClientError as exc:
        raise StorageError(f"Download S3 échoué : {exc}") from exc


def url_signee(cle: str, duree_secondes: int = 3600) -> str:
    s3 = _client_s3()
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": cle},
            ExpiresIn=duree_secondes,
        )
    except ClientError as exc:
        raise StorageError(f"Génération URL signée échouée : {exc}") from exc


def supprimer_document(cle: str) -> None:
    s3 = _client_s3()
    try:
        s3.delete_object(Bucket=settings.s3_bucket, Key=cle)
    except ClientError as exc:
        raise StorageError(f"Suppression S3 échouée : {exc}") from exc


def _deviner_mime(nom_fichier: str) -> str:
    ext = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else ""
    return {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")

\\\`n

## 📄 backend\services\token_engine.py

\\\python

# ==============================================================================
#  TOKEN ENGINE — génération et validation des tokens publics (lien unique
#  donné au client, sans login).
#
#  Sécurité :
#    - secrets.token_urlsafe(32) — ~256 bits d'entropie, impossible à deviner
#    - Expiration configurable (défaut 30 jours)
#    - Optionnel : lock sur IP de première utilisation (blocage si IP change)
#    - Rate limiting côté router (à ajouter avec slowapi)
#    - Journalisation à chaque accès (audit trail)
# ==============================================================================
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.token_public import TokenPublic


DUREE_VALIDITE_PAR_DEFAUT = timedelta(days=30)
FORMAT_DATE = "%d/%m/%Y %H:%M"


def _maintenant_str() -> str:
    return datetime.now().strftime(FORMAT_DATE)


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, FORMAT_DATE)
    except ValueError:
        return None


async def generer_token(
    db: AsyncSession,
    *,
    client_id: int,
    dossier_id: int | None = None,
    cree_par: str | None = None,
    duree: timedelta = DUREE_VALIDITE_PAR_DEFAUT,
    peut_uploader_docs: bool = True,
    peut_signer_mandat: bool = True,
    peut_voir_suivi: bool = True,
) -> TokenPublic:
    """Génère un nouveau token public pour un client."""
    now = datetime.now()
    token = TokenPublic(
        token=secrets.token_urlsafe(32),
        client_id=client_id,
        dossier_id=dossier_id,
        peut_uploader_docs=peut_uploader_docs,
        peut_signer_mandat=peut_signer_mandat,
        peut_voir_suivi=peut_voir_suivi,
        date_creation=now.strftime(FORMAT_DATE),
        date_expiration=(now + duree).strftime(FORMAT_DATE),
        cree_par=cree_par,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def valider_token(
    db: AsyncSession,
    token_str: str,
    ip_appelant: str | None = None,
    strict_ip: bool = False,
) -> TokenPublic | None:
    """Retourne le TokenPublic si valide, None sinon."""
    result = await db.execute(select(TokenPublic).where(TokenPublic.token == token_str))
    token: TokenPublic | None = result.scalar_one_or_none()

    if token is None or token.revoque:
        return None

    date_exp = _parse_date(token.date_expiration)
    if date_exp is not None and datetime.now() > date_exp:
        return None

    if strict_ip and token.ip_premiere_utilisation and ip_appelant:
        if token.ip_premiere_utilisation != ip_appelant:
            return None

    now_str = _maintenant_str()
    if token.date_premiere_utilisation is None:
        token.date_premiere_utilisation = now_str
        if ip_appelant:
            token.ip_premiere_utilisation = ip_appelant
    token.date_derniere_utilisation = now_str
    token.nb_utilisations = (token.nb_utilisations or 0) + 1
    await db.commit()
    return token


async def revoquer_token(db: AsyncSession, token_id: int, motif: str) -> bool:
    token = await db.get(TokenPublic, token_id)
    if token is None:
        return False
    token.revoque = True
    token.motif_revocation = motif
    await db.commit()
    return True


def construire_url_client(token: str, base_url: str = "https://client.iaconseil.fr") -> str:
    return f"{base_url}/dossier/{token}"

\\\`n

## 📄 backend\tests\test_facture_analyzer.py

\\\python

# ==============================================================================
#  TESTS — facture_analyzer.py (extraction structurée via Claude Haiku).
#  Le client Anthropic est mocké : aucun appel réseau réel n'est effectué.
# ==============================================================================
import json

import pytest

from backend.core.config import settings
from backend.services import facture_analyzer


class FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, texte: str):
        self.content = [FakeTextBlock(texte)]


class FakeMessages:
    def __init__(self, texte: str):
        self._texte = texte
        self.dernier_appel: dict | None = None

    def create(self, **kwargs):
        self.dernier_appel = kwargs
        return FakeResponse(self._texte)


class FakeAnthropicClient:
    def __init__(self, texte: str):
        self.messages = FakeMessages(texte)


def _patch_claude(monkeypatch, payload: dict | None = None, texte: str | None = None) -> FakeAnthropicClient:
    """Redirige facture_analyzer.anthropic.Anthropic vers un faux client qui
    renvoie soit le JSON de `payload`, soit le texte brut `texte` (pour tester
    les réponses malformées)."""
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
    corps = texte if texte is not None else json.dumps(payload)
    fake_client = FakeAnthropicClient(corps)
    monkeypatch.setattr(facture_analyzer.anthropic, "Anthropic", lambda api_key: fake_client)
    return fake_client


# ------------------------------------------------------------------------------
#  3 fixtures de factures anonymisées (mobile, box/fibre, énergie). Le contenu
#  binaire est factice : facture_analyzer envoie le fichier tel quel à Claude
#  vision (mocké dans ces tests), il n'y a pas de parsing PDF côté Python.
# ------------------------------------------------------------------------------
@pytest.fixture
def facture_mobile_pdf(tmp_path):
    chemin = tmp_path / "facture_mobile_anonymisee.pdf"
    chemin.write_bytes(b"%PDF-1.4 FACTURE ORANGE FORFAIT 5G 150GO ENGAGEMENT 12 MOIS")
    return chemin


@pytest.fixture
def facture_box_pdf(tmp_path):
    chemin = tmp_path / "facture_box_anonymisee.pdf"
    chemin.write_bytes(b"%PDF-1.4 FACTURE SFR BOX FIBRE SANS ENGAGEMENT")
    return chemin


@pytest.fixture
def facture_energie_pdf(tmp_path):
    chemin = tmp_path / "facture_energie_anonymisee.pdf"
    chemin.write_bytes(b"%PDF-1.4 FACTURE EDF ABONNEMENT CONSOMMATION")
    return chemin


class TestExtractionParUnivers:
    def test_facture_mobile_avec_engagement(self, facture_mobile_pdf, monkeypatch):
        fake_client = _patch_claude(monkeypatch, {
            "operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99,
            "data_conso_go": 150.0, "options": ["Appels illimités", "Cloud 100 Go"],
            "engagement_mois": 12, "date_fin_engagement": "15/03/2027",
            "iban_prelevement": "FR7630001007941234567890185",
        })
        res = facture_analyzer.analyser_facture(facture_mobile_pdf)

        assert res == {
            "operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99,
            "data_conso_go": 150.0, "options": ["Appels illimités", "Cloud 100 Go"],
            "engagement_mois": 12, "date_fin_engagement": "15/03/2027",
            "iban_prelevement": "FR7630001007941234567890185",
        }
        # Le prompt système (avec ses exemples few-shot) doit bien être transmis.
        assert "few-shot" not in fake_client.messages.dernier_appel["system"]  # pas de méta-texte qui fuite
        assert "JSON" in fake_client.messages.dernier_appel["system"]

    def test_facture_box_sans_engagement(self, facture_box_pdf, monkeypatch):
        _patch_claude(monkeypatch, {
            "operateur": "SFR", "prix_ht": 27.49, "prix_ttc": 32.99,
            "data_conso_go": 0.0, "options": ["Fibre 1Gb/s", "TV incluse"],
            "engagement_mois": 0, "date_fin_engagement": "",
            "iban_prelevement": "",
        })
        res = facture_analyzer.analyser_facture(facture_box_pdf)

        assert res["operateur"] == "SFR"
        assert res["engagement_mois"] == 0
        assert res["data_conso_go"] == 0.0
        assert res["options"] == ["Fibre 1Gb/s", "TV incluse"]

    def test_facture_energie_normalise_types_texte_en_nombres(self, facture_energie_pdf, monkeypatch):
        # Le modèle répond parfois des nombres sous forme de chaîne ("89,00")
        # ou omet des clés — la normalisation doit rester robuste.
        _patch_claude(monkeypatch, {
            "operateur": "EDF", "prix_ht": "", "prix_ttc": "89,00",
            "data_conso_go": None, "options": None,
            "engagement_mois": None, "date_fin_engagement": None,
            "iban_prelevement": None,
        })
        res = facture_analyzer.analyser_facture(facture_energie_pdf)

        assert res["operateur"] == "EDF"
        assert res["prix_ht"] == 0.0
        assert res["prix_ttc"] == 89.0
        assert res["data_conso_go"] == 0.0
        assert res["options"] == []
        assert res["engagement_mois"] == 0
        assert res["date_fin_engagement"] == ""
        assert res["iban_prelevement"] == ""


class TestParsingReponse:
    def test_reponse_entouree_de_balises_markdown(self, facture_mobile_pdf, monkeypatch):
        payload = {
            "operateur": "Free", "prix_ht": 16.66, "prix_ttc": 19.99,
            "data_conso_go": 350.0, "options": [], "engagement_mois": 0,
            "date_fin_engagement": "", "iban_prelevement": "",
        }
        _patch_claude(monkeypatch, texte=f"```json\n{json.dumps(payload)}\n```")
        res = facture_analyzer.analyser_facture(facture_mobile_pdf)
        assert res["operateur"] == "Free"
        assert res["prix_ttc"] == 19.99


class TestGestionErreurs:
    def test_fichier_introuvable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(tmp_path / "absent.pdf")

    def test_extension_non_pdf_rejetee(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
        chemin = tmp_path / "facture.jpg"
        chemin.write_bytes(b"donnees-image")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(chemin)

    def test_fichier_vide(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
        chemin = tmp_path / "facture_vide.pdf"
        chemin.write_bytes(b"")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(chemin)

    def test_sans_cle_api(self, facture_mobile_pdf, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(facture_mobile_pdf)

    def test_reponse_json_invalide(self, facture_mobile_pdf, monkeypatch):
        _patch_claude(monkeypatch, texte="Désolé, je ne peux pas analyser ce document.")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(facture_mobile_pdf)

    def test_erreur_api_anthropic_est_convertie(self, facture_mobile_pdf, monkeypatch):
        import anthropic

        class ClientEnErreur:
            class messages:
                @staticmethod
                def create(**kwargs):
                    raise anthropic.APIConnectionError(request=None)

        monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
        monkeypatch.setattr(facture_analyzer.anthropic, "Anthropic", lambda api_key: ClientEnErreur())
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(facture_mobile_pdf)

\\\`n

## 📄 backend\tests\test_factures_router.py

\\\python

# ==============================================================================
#  TESTS — routers/factures.py (endpoint POST /factures/analyze). Le service
#  facture_analyzer et l'authentification JWT sont tous deux mockés/surchargés :
#  aucun appel réseau réel (Claude ni Postgres) n'est nécessaire.
# ==============================================================================
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.security import get_current_user
from backend.main import app
from backend.models.user import User
from backend.services.facture_analyzer import FactureAnalyzerError

FAKE_USER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)

RESULTAT_ATTENDU = {
    "operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99, "data_conso_go": 150.0,
    "options": ["Appels illimités"], "engagement_mois": 12,
    "date_fin_engagement": "15/03/2027", "iban_prelevement": "FR7630001007941234567890185",
}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_analyse_facture_pdf_valide(client):
    with patch("backend.routers.factures.analyser_facture", return_value=RESULTAT_ATTENDU) as mock_analyse:
        reponse = client.post(
            "/factures/analyze",
            files={"fichier": ("facture.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
    assert reponse.json() == RESULTAT_ATTENDU
    mock_analyse.assert_called_once()
    # Le chemin passé au service est un fichier temporaire réel, supprimé après l'appel.
    chemin_tmp = mock_analyse.call_args.args[0]
    import os
    assert not os.path.exists(chemin_tmp)


def test_rejette_extension_non_pdf(client):
    reponse = client.post(
        "/factures/analyze",
        files={"fichier": ("facture.jpg", b"donnees-image", "image/jpeg")},
    )
    assert reponse.status_code == 422


def test_erreur_analyse_devient_422(client):
    with patch("backend.routers.factures.analyser_facture", side_effect=FactureAnalyzerError("boom")):
        reponse = client.post(
            "/factures/analyze",
            files={"fichier": ("facture.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert reponse.status_code == 422
    assert "boom" in reponse.json()["detail"]


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.post(
            "/factures/analyze",
            files={"fichier": ("facture.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert reponse.status_code == 401

\\\`n

## 📄 backend\workers\__init__.py

\\\python


\\\`n

## 📄 backend\workers\celery_app.py

\\\python

# ==============================================================================
#  CELERY — file de tâches asynchrones (validation KYC, envoi et suivi des
#  demandes de signature Yousign) sur broker/backend Redis.
#  Lancement worker : celery -A backend.workers.celery_app worker --loglevel=info
# ==============================================================================
from celery import Celery

from backend.core.config import settings

celery_app = Celery("ia_conseil", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_acks_late=True,
    task_routes={"backend.workers.tasks.*": {"queue": "ia_conseil"}},
)

celery_app.autodiscover_tasks(["backend.workers"])

\\\`n

## 📄 backend\workers\tasks.py

\\\python

# ==============================================================================
#  TÂCHES CELERY — validation KYC des documents uploadés (kyc_engine) et
#  envoi/téléchargement des mandats via Yousign (signature_engine). Chaque
#  tâche ouvre sa propre session DB : un worker Celery ne partage pas le
#  cycle de vie requête/réponse de FastAPI.
# ==============================================================================
from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from backend.core.database import AsyncSessionLocal
from backend.models.client import Client
from backend.models.document import Document
from backend.models.mandat import Mandat
from backend.services import kyc_engine, signature_engine
from backend.workers.celery_app import celery_app

_MAINTENANT = lambda: datetime.now().strftime("%d/%m/%Y %H:%M")  # noqa: E731


def _run(coro):
    """Exécute une coroutine dans un event loop dédié. Un worker Celery
    (pool prefork ou solo) démarre chaque tâche sans loop actif : pas de
    nesting, asyncio.run() est donc sûr ici."""
    return asyncio.run(coro)


async def _telecharger(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0) as client:
        reponse = await client.get(url)
        reponse.raise_for_status()
        return reponse.content


async def _valider_document_kyc(document_id: int) -> None:
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        if document is None:
            return
        try:
            contenu = await _telecharger(document.url_stockage)
            resultat = kyc_engine.valider_document(contenu, document.url_stockage)
        except (httpx.HTTPError, kyc_engine.KycError) as exc:
            document.statut_kyc = "erreur"
            document.motif_rejet = str(exc)
        else:
            document.type_document = resultat["type"]
            document.statut_kyc = "valide" if resultat["valide"] else "rejete"
            document.motif_rejet = resultat["motif_rejet"]
        document.date_validation = _MAINTENANT()
        await db.commit()


@celery_app.task(name="backend.workers.tasks.valider_document_kyc", bind=True, max_retries=3, default_retry_delay=60)
def valider_document_kyc(self, document_id: int) -> None:
    try:
        _run(_valider_document_kyc(document_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _envoyer_mandat_signature(mandat_id: int) -> None:
    async with AsyncSessionLocal() as db:
        mandat = await db.get(Mandat, mandat_id)
        if mandat is None or not mandat.pdf_url:
            return
        client = await db.get(Client, mandat.client_id) if mandat.client_id else None
        if client is None or not client.email:
            mandat.statut = "erreur"
            mandat.notes = "Client introuvable ou sans email."
            await db.commit()
            return

        try:
            pdf = await _telecharger(mandat.pdf_url)
            resultat = await signature_engine.envoyer_mandat(
                nom_demande=f"Mandat {client.prenom} {client.nom}",
                pdf=pdf,
                nom_fichier=f"mandat_{mandat.id}.pdf",
                prenom=client.prenom or "",
                nom=client.nom or "",
                email=client.email,
                telephone=client.telephone,
            )
        except (httpx.HTTPError, signature_engine.SignatureEngineError) as exc:
            mandat.statut = "erreur"
            mandat.notes = str(exc)
            await db.commit()
            return

        mandat.yousign_signature_request_id = resultat["signature_request_id"]
        mandat.yousign_document_id = resultat["document_id"]
        mandat.statut = "envoye"
        mandat.date_envoi = _MAINTENANT()
        await db.commit()


@celery_app.task(
    name="backend.workers.tasks.envoyer_mandat_signature", bind=True, max_retries=3, default_retry_delay=60
)
def envoyer_mandat_signature(self, mandat_id: int) -> None:
    try:
        _run(_envoyer_mandat_signature(mandat_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _telecharger_mandat_signe(mandat_id: int) -> None:
    async with AsyncSessionLocal() as db:
        mandat = await db.get(Mandat, mandat_id)
        if mandat is None or not mandat.yousign_signature_request_id or not mandat.yousign_document_id:
            return
        try:
            pdf = await signature_engine.telecharger_document_signe(
                mandat.yousign_signature_request_id, mandat.yousign_document_id
            )
        except signature_engine.SignatureEngineError as exc:
            mandat.notes = str(exc)
            await db.commit()
            return
        # Stockage définitif (S3 Scaleway) à brancher une fois le bucket en
        # place (sprint 3) — pour l'instant on marque simplement le mandat
        # signé ; `pdf` est disponible ici pour l'appelant qui persistera le
        # fichier.
        mandat.statut = "signe"
        mandat.date_signature = _MAINTENANT()
        await db.commit()


@celery_app.task(
    name="backend.workers.tasks.telecharger_mandat_signe", bind=True, max_retries=3, default_retry_delay=60
)
def telecharger_mandat_signe(self, mandat_id: int) -> None:
    try:
        _run(_telecharger_mandat_signe(mandat_id))
    except Exception as exc:
        raise self.retry(exc=exc)

\\\`n
