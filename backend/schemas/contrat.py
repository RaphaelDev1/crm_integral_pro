from pydantic import BaseModel, ConfigDict


class ContratBase(BaseModel):
    univers: str | None = None
    categorie: str | None = None
    fournisseur: str | None = None
    nom_offre: str | None = None
    cout_mensuel: float | None = None
    economie_mensuelle: float | None = None
    reference_contrat: str | None = None
    statut_contrat: str | None = None
    date_souscription: str | None = None
    date_fin_engagement: str | None = None
    notes: str | None = None


class ContratCreate(ContratBase):
    client_id: int
    fournisseur: str


class ContratUpdate(ContratBase):
    pass


class ContratOut(ContratBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None = None
    cree_par: str | None = None
