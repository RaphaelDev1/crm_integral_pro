# ==============================================================================
#  SCHEMAS PORTAIL PUBLIC — vue simplifiée du dossier, exposée au client via
#  son lien unique. On ne remonte que le strict nécessaire — pas de données
#  internes conseiller, pas de commissions, pas de refs autres clients.
# ==============================================================================
from pydantic import BaseModel


class DocumentDemandeOut(BaseModel):
    """Un document que le client doit uploader."""
    type_document: str          # "cni", "justificatif_domicile", "rib"
    label_affiche: str          # "Pièce d'identité", "Justificatif de domicile", etc.
    statut: str                 # "a_fournir", "en_attente", "valide", "rejete"
    motif_rejet: str | None = None
    date_upload: str | None = None


class ChampDemarchePublicOut(BaseModel):
    """Un champ que le client doit renseigner pour une démarche (RIO, PDL/PCE, RIB...)."""
    cle: str
    label: str
    valeur: str | None = None
    requis: bool = True


class DemarcheAFournirOut(BaseModel):
    """Une démarche dont il manque des champs à compléter côté client."""
    demarche_id: int
    type_demarche: str
    statut: str
    champs: list[ChampDemarchePublicOut]


class ChampsDemarchePublicUpdate(BaseModel):
    valeurs: dict[str, str]


class TokenPublicContexte(BaseModel):
    """Vue publique du contexte du token — ce que le client voit en arrivant."""
    prenom_client: str
    nom_client: str
    dossier_id: int | None
    univers: str | None
    fournisseur_cible: str | None
    economie_annuelle_estimee: float
    statut_dossier: str | None
    conseiller_nom: str | None
    conseiller_telephone: str | None = None

    # Ce qu'il doit faire
    documents_a_fournir: list[DocumentDemandeOut]
    mandat_statut: str | None      # "a_signer", "signe", None
    peut_uploader_docs: bool
    peut_signer_mandat: bool
    demarches_a_completer: list[DemarcheAFournirOut] = []
    peut_renseigner_demarches: bool = True
    peut_transmettre_speedtest: bool = True


class UploadResultOut(BaseModel):
    document_id: int
    type_detecte: str | None
    statut_kyc: str
    motif_rejet: str | None = None
    message: str


class SpeedtestResultatOut(BaseModel):
    """Résultat de la soumission — mesure numérique (LibreSpeed) ou capture
    fichier (fallback), jamais les deux à la fois."""
    speed_down: float | None = None
    speed_up: float | None = None
    document_id: int | None = None
    message: str


class SuiviEtape(BaseModel):
    """Une étape de timeline pour l'affichage client."""
    cle: str                    # "docs_demandes", "mandat_signe", ...
    label: str                  # "Vos documents nous parviennent"
    statut: str                 # "termine", "en_cours", "a_venir"
    date: str | None = None
    icone: str = "circle"


class SuiviDossierOut(BaseModel):
    dossier_id: int
    statut_actuel: str
    etapes: list[SuiviEtape]
    prochaine_action: str | None = None
