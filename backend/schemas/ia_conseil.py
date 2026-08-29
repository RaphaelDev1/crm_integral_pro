# ==============================================================================
#  SCHÉMAS — sous-système "IA Conseil" (trame adaptative + recommandation).
#  PLAN_IMPLEMENTATION_4_PHASES.md §0.5.
# ==============================================================================
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CategorieOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    nom: str
    ordre: int | None = None
    actif: bool


class FournisseurOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom: str
    categorie_slug: str | None = None
    note_fiabilite: float | None = None
    logo_url: str | None = None
    site_url: str | None = None
    affilie: bool
    taux_commission: float | None = None


class OffreConseilBase(BaseModel):
    fournisseur_id: uuid.UUID | None = None
    categorie_slug: str | None = None
    nom: str
    prix_mensuel: float | None = None
    prix_apres_promo: float | None = None
    duree_promo_mois: int | None = None
    engagement_mois: int = 0
    frais_mise_en_service: float = 0
    caracteristiques: dict[str, Any]
    conditions: dict[str, Any] | None = None
    source: str | None = None
    source_ref: str | None = None
    valide: bool = True


class OffreConseilCreate(OffreConseilBase):
    pass


class OffreConseilUpdate(BaseModel):
    nom: str | None = None
    prix_mensuel: float | None = None
    prix_apres_promo: float | None = None
    duree_promo_mois: int | None = None
    engagement_mois: int | None = None
    frais_mise_en_service: float | None = None
    caracteristiques: dict[str, Any] | None = None
    conditions: dict[str, Any] | None = None
    valide: bool | None = None


class OffreConseilOut(OffreConseilBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date_maj: datetime


class ClientConseilCreate(BaseModel):
    prenom: str | None = None
    nom: str | None = None
    email: str | None = None
    telephone: str | None = None
    adresse: dict[str, Any] | None = None
    foyer: dict[str, Any] | None = None
    profil: dict[str, Any] | None = None


class ClientConseilOut(ClientConseilCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conseiller_id: int | None = None
    cree_le: datetime


class SessionTrameCreate(BaseModel):
    client_id: uuid.UUID
    categorie_slug: str
    canal: str | None = None  # visio | telephone | physique


class CrossSellSuggestion(BaseModel):
    type: str
    categorie_source: str | None = None
    message: str


class SessionTrameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID | None = None
    conseiller_id: int | None = None
    categorie_slug: str | None = None
    trame_template_id: uuid.UUID | None = None
    reponses: dict[str, Any]
    etat: str
    canal: str | None = None
    demarree_le: datetime
    terminee_le: datetime | None = None
    # Renseigné uniquement par POST /{session_id}/finalize (§2.4) — attribut
    # transitoire posé sur l'ORM SessionTrame avant sérialisation, jamais
    # persisté. Vide (mais toujours présent) pour les autres endpoints.
    suggestions_cross_sell: list[CrossSellSuggestion] = []


class ReponseIn(BaseModel):
    question_id: str
    valeur: Any


class NextQuestionOut(BaseModel):
    question: dict[str, Any] | None
    questions_restantes_estimees: int
    terminee: bool


class AlerteOut(BaseModel):
    regle: str
    severite: str
    message: str


class RecommandationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    offre_id: uuid.UUID
    offre: OffreConseilOut | None = None
    score: float
    rang: int
    justifications: list[str] = []
    alertes: list[AlerteOut] = []
    economie_mensuelle: float | None = None
    economie_annuelle: float | None = None


class ShareTokenOut(BaseModel):
    token: str


class SessionPublicOut(BaseModel):
    """Vue lecture-seule d'une session, exposée sans authentification via un
    jeton `session_view` (§1.5.1) — volontairement plus étroite que
    SessionTrameOut : jamais `conseiller_id`, ni les réponses brutes (déjà
    restituées via `next_question`/`recommandations`)."""

    id: uuid.UUID
    categorie_slug: str | None = None
    etat: str
    demarree_le: datetime
    terminee_le: datetime | None = None
    next_question: NextQuestionOut
    recommandations: list[RecommandationOut]


class AlerteOverrideCreate(BaseModel):
    offre_id: uuid.UUID
    regle_nom: str
    justification: str = Field(min_length=10)


class AlerteOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID | None = None
    offre_id: uuid.UUID | None = None
    regle_nom: str
    justification: str
    conseiller_id: int | None = None
    cree_le: datetime


class EconomieParCategorie(BaseModel):
    categorie_slug: str | None = None
    economie_annuelle_totale: float


class PipelineOut(BaseModel):
    en_attente: int
    active: int
    resiliee: int
    annulee: int


class AlerteClientOut(BaseModel):
    id: uuid.UUID
    type: str
    date_prevue: date
    client_id: uuid.UUID | None = None


class CommissionMensuelleOut(BaseModel):
    mois: str
    prevue: float
    encaissee: float


class DashboardIaConseilOut(BaseModel):
    economies_ytd_total: float
    economies_ytd_par_categorie: list[EconomieParCategorie]
    pipeline: PipelineOut
    alertes_clients: list[AlerteClientOut]
    commissions_mensuelles: list[CommissionMensuelleOut]


class SouscriptionCreate(BaseModel):
    client_id: uuid.UUID
    offre_id: uuid.UUID
    session_id: uuid.UUID | None = None
    date_souscription: date | None = None
    prix_mensuel_negocie: float | None = None
    fin_engagement: date | None = None


class CopilotIn(BaseModel):
    mode: str  # suggestion | incoherence | reformulation
    message: str | None = None


class SessionFactureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID | None = None
    categorie_slug: str | None = None
    nom_fichier: str | None = None
    statut: str
    extraction: dict[str, Any] | None = None
    reponses_appliquees: dict[str, Any] | None = None
    erreur: str | None = None
    cree_le: datetime
    analysee_le: datetime | None = None


class FactureAppliquerIn(BaseModel):
    reponses: dict[str, Any]


class RapportVeilleMarcheOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    categorie_slug: str | None = None
    semaine_debut: date
    offres_detectees: list[dict[str, Any]]
    statut: str
    cree_le: datetime


class ScoreClientOut(BaseModel):
    client_id: uuid.UUID
    proba_churn: float | None = None
    proba_cross_sell: float | None = None
    segment: str | None = None
    source: str  # "modele" | "heuristique"


class SouscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID | None = None
    offre_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    conseiller_id: int | None = None
    date_souscription: date | None = None
    date_activation: date | None = None
    prix_mensuel_negocie: float | None = None
    commission_prevue: float | None = None
    commission_encaissee: float | None = None
    statut: str
    fin_engagement: date | None = None
