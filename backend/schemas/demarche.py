from pydantic import BaseModel, ConfigDict


class DemarcheCreate(BaseModel):
    type_demarche: str


class ChampDonneeOut(BaseModel):
    valeur: str | None = None
    requis: bool = True
    label: str


class DemarcheOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dossier_id: int
    mandat_id: int | None = None
    univers: str
    type_demarche: str
    statut: str
    canal: str
    document_url: str | None = None
    preuve_envoi: str | None = None
    preuve_url: str | None = None
    donnees_requises: dict[str, ChampDonneeOut] | None = None
    notes: str | None = None
    date_creation: str | None = None
    date_generation: str | None = None
    date_envoi: str | None = None
    date_accuse: str | None = None


class DemarcheRequiseOut(BaseModel):
    """Type de démarche attendu pour l'univers du dossier mais pas encore créé."""
    type_demarche: str
    label: str


class DemarchesDossierOut(BaseModel):
    existantes: list[DemarcheOut]
    requises_non_creees: list[DemarcheRequiseOut]


class ChampsDemarcheUpdate(BaseModel):
    valeurs: dict[str, str]


class DocumentDemarcheUrlOut(BaseModel):
    url: str
