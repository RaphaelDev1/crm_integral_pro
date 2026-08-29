from pydantic import BaseModel, ConfigDict


class FactureAnalyseOut(BaseModel):
    operateur: str
    prix_ht: float
    prix_ttc: float
    data_conso_go: float
    options: list[str]
    engagement_mois: int
    date_fin_engagement: str
    iban_prelevement: str
    type_couverture: str = ""
    bonus_malus: str = ""


class FactureClientOut(BaseModel):
    """Version persistée (table `factures_analysees`) d'une analyse de facture,
    liée à un client (briefing conseiller, GET /clients/{id}/briefing) ou à un
    prospect (analyse automatique à l'upload, voir portail_public.py)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None = None
    prospect_id: int | None = None
    dossier_id: int | None = None
    operateur: str | None = None
    prix_ht: float = 0.0
    prix_ttc: float = 0.0
    data_conso_go: float = 0.0
    options: list[str] | None = None
    engagement_mois: int = 0
    date_fin_engagement: str | None = None
    iban_prelevement: str | None = None
    type_couverture: str | None = None
    bonus_malus: str | None = None
    date_analyse: str | None = None
    analyse_par: str | None = None
