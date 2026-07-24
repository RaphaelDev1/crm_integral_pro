from pydantic import BaseModel

from backend.schemas.client import ClientOut
from backend.schemas.dossier import DossierOut
from backend.schemas.facture import FactureClientOut
from backend.schemas.mandat_honoraires import MandatHonorairesOut, MandatOut


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
