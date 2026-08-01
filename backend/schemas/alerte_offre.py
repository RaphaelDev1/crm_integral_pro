from pydantic import BaseModel, ConfigDict


class AlerteOffreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None = None
    contrat_id: int | None = None
    offre_id: int | None = None
    cout_actuel: float | None = None
    cout_propose: float | None = None
    economie_mensuelle: float | None = None
    economie_annuelle: float | None = None
    statut: str
    date_detection: str | None = None
    date_traitement: str | None = None
