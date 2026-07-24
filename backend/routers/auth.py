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
        pass  # TODO: à brancher sur l'envoi d'email une fois le service dispo
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
