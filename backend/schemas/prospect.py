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
    raison_sociale: str | None = None
    effectif: str | None = None
    univers_interesse: str | None = None
    service_principal: str | None = None
    operateur_actuel: str | None = None
    techno: str | None = None
    data_go: str | None = None
    roaming_europe: str | None = None
    sensibilite_prix: str | None = None
    cout_mensuel_actuel: float | None = None
    offre_actuelle: str | None = None
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    defaut_technique: str | None = None
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
    code_insee: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    fibre_disponible: bool | None = None
    fibre_taux_couverture: float | None = None
    telephone_verifie: bool | None = None
    telephone_type_ligne: str | None = None
    operateur_detecte_ip: str | None = None
    bonus_malus_auto: str | None = None
    plage_horaire_rappel: str | None = None
    motif_refus: str | None = None


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
    dernier_contact: str | None = None


class ContacterTelephoneIn(BaseModel):
    # True si le prospect a décroché, False s'il n'a pas répondu (déclenche
    # alors un SMS/email pour l'informer de l'appel manqué).
    repondu: bool


class DetailScoreOut(BaseModel):
    facteur: str
    poids: int
    valeur: str


class ScoreProspectOut(BaseModel):
    score: float
    indicateur: str
    details: list[DetailScoreOut]
