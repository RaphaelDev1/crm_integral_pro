from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dossier_id: int
    message: str
    lu: bool
    date_creation: str | None = None
