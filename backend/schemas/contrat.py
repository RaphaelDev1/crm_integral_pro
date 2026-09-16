from pydantic import BaseModel, ConfigDict, model_validator


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
    consommation: str | None = None
    chez_nous: bool = False
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    defaut_technique: str | None = None
    speed_down: float | None = None
    speed_up: float | None = None
    debit_declare: float | None = None
    ligne_principale: bool = False
    # M1a (docs/QUESTIONS_PAR_SECTEUR.md) — voir backend/models/contrat.py.
    meme_operateur_mobile: bool | None = None
    # Portabilité mobile (M-portabilité). Migration 0049.
    conserver_numero: str | None = None
    rio: str | None = None
    numero_ligne: str | None = None
    type_sim: str | None = None
    # Questions par secteur (Énergie/Box, docs/QUESTIONS_PAR_SECTEUR.md).
    # Migration 0047.
    chauffage_principal: str | None = None
    puissance_kva: str | None = None
    option_tarifaire: str | None = None
    gros_equipement_electrique: bool | None = None
    usage_tv: str | None = None
    abonnements_payants: str | None = None
    # Trame Box B4/B5/B6/B7 (docs/QUESTIONS_PAR_SECTEUR.md). Migration 0051.
    nb_utilisateurs_streaming: str | None = None
    usage_4k: bool | None = None
    teletravail: str | None = None
    interet_box_4g5g: str | None = None
    telephone_fixe_utilise: str | None = None
    appels_fixe_mensuels: str | None = None
    notes: str | None = None


class ContratCreate(ContratBase):
    client_id: int | None = None
    prospect_id: int | None = None
    fournisseur: str

    @model_validator(mode="after")
    def valider_rattachement(self) -> "ContratCreate":
        if self.client_id is None and self.prospect_id is None:
            raise ValueError("Un contrat doit être rattaché à un client ou un prospect.")
        return self


class ContratUpdate(ContratBase):
    pass


class ContratOut(ContratBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None = None
    prospect_id: int | None = None
    cree_par: str | None = None


class LigneEstimationContratOut(BaseModel):
    categorie: str
    cout_actuel_mensuel: float
    notre_moyenne_mensuel: float
    economie_mensuelle_basse: float
    economie_mensuelle_haute: float
    economie_annuelle_typique: float
    source: str
    echantillon: int
    tranche_age_utilisee: str | None = None


class EstimationContratOut(BaseModel):
    lignes: list[LigneEstimationContratOut]
    economie_annuelle_totale_basse: float
    economie_annuelle_totale_haute: float
    economie_annuelle_totale_typique: float
    calculee_le: str
