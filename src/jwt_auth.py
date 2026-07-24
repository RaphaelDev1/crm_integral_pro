# ==============================================================================
#  JWT — émission/validation des jetons pour l'API CRM interne (crm_api.py)
#
#  Le secret est lu dans la variable d'environnement CRM_API_SECRET (.env en
#  dev, variable réelle en prod). En son absence : secret de dev + avertissement
#  si APP_ENV != production, sinon échec au démarrage (on refuse de tourner en
#  prod avec un secret JWT prévisible).
# ==============================================================================
import os
import sys
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

ALGORITHME = "HS256"
DUREE_VALIDITE_MINUTES = 8 * 60   # 8h — la durée d'une journée de travail

_SECRET = os.environ.get("CRM_API_SECRET")
if not _SECRET:
    if os.environ.get("APP_ENV", "development") == "production":
        raise RuntimeError(
            "CRM_API_SECRET doit être défini en production (voir .env.example)."
        )
    _SECRET = "dev-secret-a-changer-en-production"
    print("⚠️  CRM_API_SECRET non défini — utilisation d'un secret de développement. "
          "Définissez cette variable d'environnement avant tout déploiement.", file=sys.stderr)

_bearer = HTTPBearer(auto_error=False)


def creer_token(user: dict) -> str:
    """Émet un JWT à partir d'un utilisateur (dict avec id/username/nom_complet/role).

    Inclut "type": "access" pour rester compatible avec backend/core/security.py
    (backend/, API FastAPI Postgres) qui exige ce champ sur les jetons d'accès —
    sans lui, un jeton émis ici est rejeté par backend.main:app et api_client.py
    retombe silencieusement sur l'accès direct SQLite (cf. api_client.py)."""
    maintenant = datetime.now(timezone.utc)
    payload = {
        "sub":         user["username"],
        "user_id":     user["id"],
        "nom_complet": user["nom_complet"],
        "role":        user["role"],
        "type":        "access",
        "iat":         maintenant,
        "exp":         maintenant + timedelta(minutes=DUREE_VALIDITE_MINUTES),
    }
    return jwt.encode(payload, _SECRET, algorithm=ALGORITHME)


def decoder_token(token: str) -> dict:
    """Décode et valide un JWT. Lève jwt.PyJWTError si invalide/expiré."""
    return jwt.decode(token, _SECRET, algorithms=[ALGORITHME])


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """Dépendance FastAPI : extrait et valide l'utilisateur courant depuis l'en-tête
    Authorization: Bearer <token>. Lève 401 si absent ou invalide."""
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Authentification requise.")
    try:
        return decoder_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Jeton invalide ou expiré.")


def require_role(*roles: str):
    """Fabrique une dépendance FastAPI qui exige que l'utilisateur courant ait
    l'un des rôles donnés (ex. require_role("Conseiller", "Admin"))."""
    def _dependance(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                 detail="Accès refusé pour ce rôle.")
        return user
    return _dependance
