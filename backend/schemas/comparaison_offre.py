from pydantic import BaseModel, ConfigDict


class OffreCompareeItem(BaseModel):
    offre_id: int
    nom: str | None = None
    fournisseur: str | None = None
    prix_mensuel: float | None = None
    economie_mensuelle: float | None = None
    frais_annexes_total: float | None = None
    comparable: bool = True


class ComparaisonOffreCreate(BaseModel):
    prospect_id: int | None = None
    client_id: int | None = None
    univers: str | None = None
    categorie: str | None = None
    cout_actuel_mensuel: float | None = None
    offre_recommandee_id: int | None = None
    offres_comparees: list[OffreCompareeItem] | None = None
    economie_mensuelle_estimee: float = 0.0
    economie_annuelle_estimee: float = 0.0
    contexte: str | None = None


class ComparaisonOffreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prospect_id: int | None = None
    client_id: int | None = None
    univers: str | None = None
    categorie: str | None = None
    cout_actuel_mensuel: float | None = None
    offre_recommandee_id: int | None = None
    offres_comparees: list[dict] | None = None
    economie_mensuelle_estimee: float = 0.0
    economie_annuelle_estimee: float = 0.0
    contexte: str | None = None
    date_comparaison: str | None = None
    cree_par: str | None = None
