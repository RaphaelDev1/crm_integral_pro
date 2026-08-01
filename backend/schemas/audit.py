from pydantic import BaseModel

from backend.schemas.offre import OffreCompareeOut


class AbonnementSituation(BaseModel):
    nom: str | None = None
    categorie: str | None = None
    cout: float = 0.0


class ContratReference(BaseModel):
    categorie: str | None = None
    cout_mensuel: float = 0.0


class SituationAudit(BaseModel):
    service_principal: str | None = None
    cout_mensuel_actuel: float = 0.0
    ville: str | None = None
    operateur_actuel: str | None = None
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    cout_elec: float = 0.0
    cout_gaz: float = 0.0
    fournisseur_energie: str | None = None
    abonnements: list[AbonnementSituation] = []
    data_go_min: float | None = None


class AuditRequest(BaseModel):
    situation: SituationAudit
    contrats: list[ContratReference] = []


class OffreRecommandeeOut(BaseModel):
    offre: OffreCompareeOut
    economie_an: float
    pourquoi: str
    source: str


class AuditResultOut(BaseModel):
    situation_detectee: str
    offres_recommandees: list[OffreRecommandeeOut]
    economie_totale_an: float
    points_attention: list[str]
    niveau_confiance: float
    tracabilite: list[dict]
