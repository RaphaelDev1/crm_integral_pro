from pydantic import BaseModel


class ComparerOffresRequest(BaseModel):
    univers: str
    categorie: str
    cout_actuel_mensuel: float
    fournisseurs_autorises: list[str] | None = None
    fournisseur_exclu: str | None = None
    data_go_min: float | None = None


class OffreCompareeOut(BaseModel):
    id: int
    nom: str | None = None
    fournisseur: str | None = None
    categorie: str | None = None
    univers: str | None = None
    prix_mensuel: float
    frais_activation: float
    engagement: int
    caracteristiques: str
    commission: float
    data_go: float
    economie_mensuelle: float
    economie_annuelle: float
    cout_1_an: float
    url_souscription: str
    code_affiliation: str


class RecommandationsRequest(BaseModel):
    service_principal: str
    cout_tel: float
    fournisseurs_autorises: list[str] | None = None
    fournisseur_exclu: str | None = None
    data_go_min: float | None = None


class BlocRecommandationOut(BaseModel):
    titre: str
    offres: list[OffreCompareeOut]


class RecommandationsOut(BaseModel):
    principal: BlocRecommandationOut
    cross_sell: list[BlocRecommandationOut]
