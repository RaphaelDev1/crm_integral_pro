from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nom_complet: str
    role: str
    actif: bool
    doit_changer_mdp: bool
