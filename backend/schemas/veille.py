from pydantic import BaseModel, ConfigDict


class SourceVeilleCreate(BaseModel):
    univers: str | None = None
    categorie: str | None = None
    fournisseur: str | None = None
    nom_offre: str | None = None
    offre_id: int | None = None
    url: str | None = None
    selecteur_prix: str | None = None
    actif: bool = True


class SourceVeilleUpdate(BaseModel):
    univers: str | None = None
    categorie: str | None = None
    fournisseur: str | None = None
    nom_offre: str | None = None
    offre_id: int | None = None
    url: str | None = None
    selecteur_prix: str | None = None
    actif: bool | None = None


class SourceVeilleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    univers: str | None = None
    categorie: str | None = None
    fournisseur: str | None = None
    nom_offre: str | None = None
    offre_id: int | None = None
    url: str | None = None
    selecteur_prix: str | None = None
    actif: bool = True
    dernier_prix: float | None = None
    date_derniere_verif: str | None = None
    date_creation: str | None = None


class VeilleHistoriquePrixOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None = None
    prix: float | None = None
    date_releve: str | None = None


class VeilleAlerteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None = None
    ancien_prix: float | None = None
    nouveau_prix: float | None = None
    statut: str
    date_detection: str | None = None
    date_traitement: str | None = None
