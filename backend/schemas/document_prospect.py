from pydantic import BaseModel, ConfigDict


class DocumentProspectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prospect_id: int
    type_document: str | None = None
    nom_fichier: str | None = None
    mime: str | None = None
    date_upload: str | None = None
    url: str
