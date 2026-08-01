from pydantic import BaseModel, ConfigDict


class HistoriqueActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    details: str | None = None
    auteur: str | None = None
    date_action: str | None = None
