from pydantic import BaseModel


class KpisOut(BaseModel):
    total_clients: int
    total_prospects: int
    prospects_chauds: int
    prospects_tiedes: int
    prospects_froids: int
    dossiers_en_cours: int


class DashboardSummaryOut(BaseModel):
    relances_retard: int
    relances_jour: int
    relances_venir: int
    kpis: KpisOut
