# ==============================================================================
#  DASHBOARD UTM — schémas pour le tunnel de conversion par campagne (P4.1) et
#  l'attribution multi-touch (P4.3). Voir backend/routers/dashboard_utm.py.
# ==============================================================================
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CampagneStatsOut(BaseModel):
    utm_source: str
    utm_campaign: str | None = None
    leads: int
    rappels_effectues: int
    conversions: int
    taux_conversion: float  # % — conversions / leads * 100
    ca_genere: float        # € — somme des commissions liées aux dossiers issus de la campagne
    cout_pub: float | None = None   # € — saisi manuellement (campagnes_couts), None si non renseigné
    cac: float | None = None        # € — cout_pub / conversions, None si cout_pub absent ou 0 conversion


class DashboardUtmOut(BaseModel):
    periode_debut: str | None = None
    periode_fin: str | None = None
    campagnes: list[CampagneStatsOut]
    totaux: CampagneStatsOut


class CampagneCoutIn(BaseModel):
    utm_source: str = Field(..., min_length=1, max_length=64)
    utm_campaign: str | None = Field(None, max_length=128)
    mois: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    cout: float = Field(..., ge=0)
    notes: str | None = Field(None, max_length=512)


class CampagneCoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    utm_source: str
    utm_campaign: str | None = None
    mois: str
    cout: float
    notes: str | None = None
    cree_par: str | None = None
    date_creation: str | None = None


class ParcoursAttributionOut(BaseModel):
    premier_touch_source: str
    dernier_touch_source: str
    nb_prospects: int
    nb_conversions: int


class RepartitionSourceOut(BaseModel):
    utm_source: str
    nb_prospects: int
    nb_conversions: int


class DashboardAttributionOut(BaseModel):
    periode_debut: str | None = None
    periode_fin: str | None = None
    parcours: list[ParcoursAttributionOut]
    par_source_premier_touch: list[RepartitionSourceOut]
    par_source_dernier_touch: list[RepartitionSourceOut]


class InscritUtmOut(BaseModel):
    id: int
    prenom: str | None = None
    nom: str | None = None
    email: str | None = None
    telephone: str | None = None
    ville: str | None = None
    utm_source: str
    utm_campaign: str | None = None
    date_creation: str | None = None  # "%d/%m/%Y %H:%M"
    statut: str | None = None


class DashboardUtmInscritsOut(BaseModel):
    periode_debut: str | None = None
    periode_fin: str | None = None
    total: int
    inscrits: list[InscritUtmOut]
