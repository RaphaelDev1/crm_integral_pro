from pydantic import BaseModel

from backend.schemas.user import UserOut


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


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


class ChangePasswordRequest(BaseModel):
    nouveau_mot_de_passe: str
