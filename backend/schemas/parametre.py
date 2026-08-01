from pydantic import BaseModel, ConfigDict


class ParametreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cle: str
    valeur: str | None = None


class ParametreUpdate(BaseModel):
    valeur: str | None = None
