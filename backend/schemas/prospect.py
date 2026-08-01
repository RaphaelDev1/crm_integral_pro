from pydantic import BaseModel, ConfigDict


class ProspectBase(BaseModel):
    ref: str | None = None
    prenom: str | None = None
    nom: str | None = None
    telephone: str | None = None
    email: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    adresse: str | None = None
    type_client: str | None = None
    univers_interesse: str | None = None
    service_principal: str | None = None
    operateur_actuel: str | None = None
    techno: str | None = None
    data_go: str | None = None
    cout_mensuel_actuel: float | None = None
    offre_actuelle: str | None = None
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    speed_down: float | None = None
    speed_up: float | None = None
    cout_elec: float | None = None
    cout_gaz: float | None = None
    fournisseur_energie: str | None = None
    abonnements: str | None = None
    lignes_multi: str | None = None
    economie_estimee_an: float | None = None
    notes: str | None = None
    statut: str | None = None
    date_relance: str | None = None
    offres_interet: str | None = None
    score: float | None = None
    origine: str | None = None


class ProspectCreate(ProspectBase):
    prenom: str
    nom: str


class ProspectUpdate(ProspectBase):
    pass


class ProspectOut(ProspectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_creation: str | None = None
    cree_par: str | None = None
    client_id: int | None = None
    converti_at: str | None = None


class DetailScoreOut(BaseModel):
    facteur: str
    poids: int
    valeur: str


class ScoreProspectOut(BaseModel):
    score: float
    indicateur: str
    details: list[DetailScoreOut]
