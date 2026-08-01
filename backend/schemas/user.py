from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nom_complet: str
    role: str
    actif: bool
    doit_changer_mdp: bool


class UserCreate(BaseModel):
    username: str
    nom_complet: str
    password: str
    role: str = "Conseiller"


class UserUpdate(BaseModel):
    nom_complet: str | None = None
    role: str | None = None
    actif: bool | None = None
    password: str | None = None
