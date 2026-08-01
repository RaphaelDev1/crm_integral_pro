from pydantic import BaseModel, ConfigDict


class CatalogueSourceCreate(BaseModel):
    univers: str | None = None
    categorie: str | None = None
    fournisseur: str | None = None
    url: str
    type_source: str = "page_officielle"
    methode: str = "requests"
    frequence_h: int = 24
    actif: bool = True


class CatalogueSourceUpdate(BaseModel):
    univers: str | None = None
    categorie: str | None = None
    fournisseur: str | None = None
    url: str | None = None
    type_source: str | None = None
    methode: str | None = None
    frequence_h: int | None = None
    actif: bool | None = None


class CatalogueSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    univers: str | None = None
    categorie: str | None = None
    fournisseur: str | None = None
    url: str | None = None
    type_source: str
    methode: str
    actif: bool
    robots_ok: bool
    frequence_h: int
    date_derniere_ingestion: str | None = None
    date_creation: str | None = None


class OffreStagingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None = None
    univers: str | None = None
    categorie: str | None = None
    fournisseur: str | None = None
    nom_offre: str | None = None
    prix_mensuel: float | None = None
    frais_activation: float | None = None
    engagement_mois: int | None = None
    data_go: float | None = None
    caracteristiques: str | None = None
    commission_affiliation: float | None = None
    url_souscription: str | None = None
    code_affiliation: str | None = None
    statut: str
    confiance_llm: float | None = None
    champs_incertains: list[str] | None = None
    offre_existante_id: int | None = None
    date_detection: str | None = None
    date_traitement: str | None = None


class IngestionResumeOut(BaseModel):
    detectees: int
    doublons: int
    a_verifier: int
    changements: int
