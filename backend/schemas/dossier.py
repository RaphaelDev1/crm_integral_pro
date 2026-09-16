from typing import Literal

from pydantic import BaseModel, ConfigDict


class DossierBase(BaseModel):
    univers: str
    fournisseur_cible: str | None = None
    offre_cible_id: int | None = None
    economie_annuelle_estimee: float = 0.0
    frais_annexes_cible: float = 0.0


class DossierCreate(DossierBase):
    client_id: int
    est_prospect: bool = True


class DossierUpdate(BaseModel):
    fournisseur_cible: str | None = None
    offre_cible_id: int | None = None
    economie_annuelle_estimee: float | None = None
    frais_annexes_cible: float | None = None
    reference_fournisseur: str | None = None
    date_activation_prevue: str | None = None
    conseiller_responsable: str | None = None
    est_prospect: bool | None = None


class DossierOut(DossierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    statut: str
    est_prospect: bool = True
    date_creation: str | None = None
    date_soumission: str | None = None
    date_activation_prevue: str | None = None
    date_activation_reelle: str | None = None
    date_derniere_transition: str | None = None
    reference_fournisseur: str | None = None
    commission_attendue: float = 0.0
    commission_recue: float = 0.0
    part_client_totale: float = 0.0
    duree_prelevement_mois: int = 0
    conseiller_responsable: str | None = None
    notes_workflow: list | None = None
    documents_requis: list[str] = []
    offre_nom: str | None = None


class TransitionStatut(BaseModel):
    nouveau_statut: str
    commentaire: str | None = None


class NoteDossierCreate(BaseModel):
    texte: str


class EnvoiLienClient(BaseModel):
    canal: Literal["sms", "email"]
    # Uniquement pertinent pour le lien personnel d'un prospect (voir
    # backend/routers/prospects.py::envoyer_lien_documents_prospect) — ignoré
    # pour les liens client (clients.py/dossiers.py), qui n'ont pas cette
    # distinction. True = le client répond seul (formulaire allégé),
    # False = le conseiller répond avec lui au téléphone (formulaire complet).
    remplissage_autonome: bool = True


class EtapeTimeline(BaseModel):
    cle: str
    label: str
    statut: str
    date: str | None = None
    icone: str


class PreRemplirSouscriptionIn(BaseModel):
    """Position/taille écran (pixels) souhaitées pour la fenêtre Playwright, pour
    l'afficher à côté de la fenêtre de référence ouverte par le frontend — voir
    souscription_engine.lancer_souscription. Optionnel : sans valeur, Chromium
    choisit sa position par défaut."""
    window_position: tuple[int, int] | None = None
    window_size: tuple[int, int] | None = None


class PreRemplirSouscriptionOut(BaseModel):
    ok: bool
    message: str
    # Renseigné uniquement si ok=False et qu'une URL de souscription réelle
    # (non ".invalid") existe malgré tout pour l'offre — permet au frontend de
    # proposer d'ouvrir le site de l'opérateur manuellement (ex. fournisseur
    # non pris en charge par l'automatisation) plutôt que de laisser le
    # conseiller sans recours.
    url_manuelle: str | None = None
