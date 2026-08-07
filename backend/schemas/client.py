from pydantic import BaseModel, ConfigDict


class ClientBase(BaseModel):
    ref: str | None = None
    prenom: str | None = None
    nom: str | None = None
    telephone: str | None = None
    email: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    adresse: str | None = None
    type_client: str | None = None
    raison_sociale: str | None = None
    effectif: str | None = None
    operateur_actuel: str | None = None
    techno: str | None = None
    data_go: str | None = None
    offre_actuelle: str | None = None
    cout_mensuel_actuel: float | None = None
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    defaut_technique: str | None = None
    speed_down: float | None = None
    speed_up: float | None = None
    fournisseur_energie: str | None = None
    cout_elec: float | None = None
    cout_gaz: float | None = None
    economie_estimee_an: float | None = None
    notes: str | None = None
    date_relance: str | None = None
    statut_relance: str | None = None


class ClientCreate(ClientBase):
    prenom: str
    nom: str


class ClientUpdate(ClientBase):
    pass


class RelanceUpdate(BaseModel):
    date_relance: str | None = None
    statut_relance: str | None = None


class ClientOut(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_creation: str | None = None
    cree_par: str | None = None
    conseiller_id: int | None = None
