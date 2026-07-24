from pydantic import BaseModel, ConfigDict


class MandatOut(BaseModel):
    """Vue minimale du mandat de représentation (Yousign) pour le briefing
    conseiller — le modèle `Mandat` n'a pas d'autre router exposé à ce jour."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    statut: str
    date_envoi: str | None = None
    date_signature: str | None = None


class MandatHonorairesCreate(BaseModel):
    montant: float = 0.0
    taux: float = 0.0


class MandatHonorairesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dossier_id: int
    montant: float = 0.0
    taux: float = 0.0
    statut: str
    signataire: str | None = None
    date_signature: str | None = None
    date_creation: str | None = None


class MarquerSigneHonoraires(BaseModel):
    signataire: str
