from pydantic import BaseModel, ConfigDict


class MandatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None = None
    statut: str
    notes: str | None = None
    date_creation: str | None = None
    date_envoi: str | None = None
    date_signature: str | None = None
    pdf_url: str | None = None


class MarquerMandatSigne(BaseModel):
    signataire: str
