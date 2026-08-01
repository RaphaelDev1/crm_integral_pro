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
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.models.login_tentative import LoginTentative
from backend.models.user import User

_PBKDF2_ITERATIONS = 260_000   # OWASP 2024 recommandation pour PBKDF2-SHA256

# ── Rate limiting login — repris de src/auth.py (MAX_TENTATIVES/FENETRE_MINUTES),
#    qui n'avait pas d'équivalent côté backend/ avant l'unification de l'auth. ──
MAX_TENTATIVES = 5    # échecs consécutifs autorisés
FENETRE_MINUTES = 15  # fenêtre glissante de blocage
_PURGE_RETENTION_JOURS = 1   # historique des tentatives conservé (purge opportuniste)
_FMT_TENTATIVE = "%Y-%m-%d %H:%M:%S"   # format triable lexicographiquement

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
        "nom_complet": user.nom_complet,  # requis par src/crm_api.py (current["nom_complet"]) — voir src/jwt_auth.py
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


async def _purger_vieilles_tentatives(db: AsyncSession) -> None:
    seuil = (datetime.now(timezone.utc) - timedelta(days=_PURGE_RETENTION_JOURS)).strftime(_FMT_TENTATIVE)
    await db.execute(delete(LoginTentative).where(LoginTentative.date_tentative < seuil))


async def enregistrer_tentative(db: AsyncSession, identifiant: str, ip: str, succes: bool) -> None:
    await _purger_vieilles_tentatives(db)
    db.add(LoginTentative(
        identifiant=identifiant.strip().lower(),
        ip=ip or "",
        succes=succes,
        date_tentative=datetime.now(timezone.utc).strftime(_FMT_TENTATIVE),
    ))
    await db.commit()


async def compte_verrouille(db: AsyncSession, identifiant: str, ip: str) -> tuple[bool, int]:
    """Renvoie (verrouillé, minutes_restantes) selon les échecs consécutifs du
    couple (identifiant, ip) sur la fenêtre glissante — logique reprise de
    src/auth.py::_compte_verrouille. Un succès plus récent qu'un échec
    réinitialise le compteur."""
    seuil = (datetime.now(timezone.utc) - timedelta(minutes=FENETRE_MINUTES)).strftime(_FMT_TENTATIVE)
    result = await db.execute(
        select(LoginTentative.succes, LoginTentative.date_tentative)
        .where(
            LoginTentative.identifiant == identifiant.strip().lower(),
            LoginTentative.ip == (ip or ""),
            LoginTentative.date_tentative >= seuil,
        )
        .order_by(LoginTentative.date_tentative.desc())
    )
    echecs, plus_recent_echec = 0, None
    for succes, date_tentative in result.all():
        if succes:
            break
        echecs += 1
        if plus_recent_echec is None:
            plus_recent_echec = date_tentative

    if echecs >= MAX_TENTATIVES and plus_recent_echec:
        expiration = datetime.strptime(plus_recent_echec, _FMT_TENTATIVE).replace(tzinfo=timezone.utc) + timedelta(
            minutes=FENETRE_MINUTES
        )
        restant_min = (expiration - datetime.now(timezone.utc)).total_seconds() / 60
        if restant_min > 0:
            return True, max(1, round(restant_min))
    return False, 0
