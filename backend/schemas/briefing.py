from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.schemas.client import ClientOut
from backend.schemas.dossier import DossierOut
from backend.schemas.facture import FactureClientOut
from backend.schemas.mandat_honoraires import MandatHonorairesOut, MandatOut


class DocumentStatutUpdate(BaseModel):
    """Validation/rejet manuel d'un document par le conseiller (en plus de la
    validation automatique KYC — voir backend/services/kyc_engine.py)."""

    statut_kyc: Literal["valide", "rejete"]
    motif_rejet: str | None = None


class DocumentOut(BaseModel):
    """Document KYC (CNI, justificatif de domicile, RIB...) transmis par le client via le
    portail public — vue conseiller avec URL signée temporaire vers le fichier stocké."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type_document: str | None = None
    statut_kyc: str
    motif_rejet: str | None = None
    date_upload: str | None = None
    url: str


class ClientBriefingOut(BaseModel):
    """Vue agrégée servie au conseiller avant d'appeler un client : ses
    informations, son dossier de souscription en cours (le cas échéant) et la
    dernière facture analysée — pour avoir le maximum de contexte en un seul
    appel (GET /clients/{id}/briefing)."""

    client: ClientOut
    dossier_en_cours: DossierOut | None = None
    derniere_facture: FactureClientOut | None = None
    nb_dossiers: int = 0
    mandat_representation: MandatOut | None = None
    mandat_honoraires: MandatHonorairesOut | None = None
    documents: list[DocumentOut] = []
