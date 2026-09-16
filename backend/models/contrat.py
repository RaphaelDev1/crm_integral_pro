# ==============================================================================
#  CONTRAT — miroir de la table `contrats` (src/db.py).
# ==============================================================================
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client
    from backend.models.prospect import Prospect


class Contrat(Base):
    __tablename__ = "contrats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    # Rattachement à un prospect non converti — un prospect a souvent déjà des
    # contrats en cours (concurrents) avant de devenir client. Migration 0039.
    prospect_id: Mapped[int | None] = mapped_column(ForeignKey("prospects.id"), nullable=True)
    univers: Mapped[str | None] = mapped_column(String, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)
    nom_offre: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_mensuel: Mapped[float | None] = mapped_column(Float, default=0)
    economie_mensuelle: Mapped[float | None] = mapped_column(Float, default=0)
    reference_contrat: Mapped[str | None] = mapped_column(String, nullable=True)
    statut_contrat: Mapped[str | None] = mapped_column(String, nullable=True)
    date_souscription: Mapped[str | None] = mapped_column(String, nullable=True)
    date_fin_engagement: Mapped[str | None] = mapped_column(String, nullable=True)
    # Texte libre — ex. "120 Go", "3500 kWh". Migration 0039.
    consommation: Mapped[str | None] = mapped_column(String, nullable=True)
    # Distingue un contrat souscrit chez nous d'un contrat concurrent en cours
    # (indépendant de `statut_contrat`, qui décrit notre propre pipeline de
    # vente). Migration 0039.
    chez_nous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # "Situation actuelle" du contrat concurrent (chez_nous=False) — mêmes
    # champs que l'ancienne SituationActuelleCard.tsx sur Client/Prospect,
    # désormais rattachés au contrat concerné plutôt qu'à la personne.
    # Migration 0040.
    satisfaction_reseau: Mapped[str | None] = mapped_column(String, nullable=True)
    veut_rester: Mapped[str | None] = mapped_column(String, nullable=True)
    defaut_technique: Mapped[str | None] = mapped_column(String, nullable=True)
    # Débit mesuré (speedtest) rattaché à ce forfait mobile/box. Migration 0040.
    speed_down: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_up: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Débit auto-déclaré sur la landing publique (jamais mesuré) — distinct de
    # speed_down, réservé à un test réellement effectué. Migration 0046.
    debit_declare: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Posé uniquement par portail_public.py::renseigner_situation_actuelle
    # (vraie soumission du prospect) — seule source de vérité pour
    # `situation_renseignee`, à ne jamais renseigner depuis ContratForm.tsx ou
    # la capture landing. Migration 0043.
    situation_confirmee_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Ligne mobile de référence d'un client/prospect (un seul contrat "Forfait
    # mobile" à True par entité) — voir backend/routers/contrats.py::creer_contrat
    # (posé automatiquement sur la première ligne) et portail_public.py::
    # _contrat_situation_actuelle_prospect. Migration 0041.
    ligne_principale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # M1a (docs/QUESTIONS_PAR_SECTEUR.md) — posé par le conseiller sur la ligne
    # `ligne_principale=True` une fois le détail multi-lignes obtenu au
    # téléphone (Prospect.nb_lignes_mobiles == "2+"). Migration : 0050.
    meme_operateur_mobile: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)
    # ==========================================================================
    #  QUESTIONS PAR SECTEUR — trame de la landing /economiser (docs/
    #  QUESTIONS_PAR_SECTEUR.md), posées uniquement pour le contrat du secteur
    #  concerné (chauffage/puissance/option tarifaire sur un contrat Électricité,
    #  usage TV sur un contrat Box / Fibre ou Pack Box + Mobile).
    #  Migration : 0047_questions_par_secteur.
    # ==========================================================================
    # E1 : "Électrique" | "Gaz" | "Bois / fioul / PAC" | "Chauffage collectif inclus".
    chauffage_principal: Mapped[str | None] = mapped_column(String, nullable=True)
    # E5 : "3" | "6" | "9" | "12+" (kVA), contrat Électricité uniquement.
    puissance_kva: Mapped[str | None] = mapped_column(String, nullable=True)
    # E6 : "Base" | "Heures Pleines-Creuses" | "Tempo".
    option_tarifaire: Mapped[str | None] = mapped_column(String, nullable=True)
    # E5a : clim/piscine/véhicule électrique/plaques induction déclarés — si
    # False avec puissance_kva >= 9, la baisse de puissance est une économie
    # immédiate quasi sans risque (cf. doc, "RECOMMANDATION FORTE").
    gros_equipement_electrique: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # B3 : "Jamais, uniquement streaming" | "Quelques chaînes" | "Bouquet premium".
    usage_tv: Mapped[str | None] = mapped_column(String, nullable=True)
    # B3b : détail des abonnements payants en plus du bouquet (Canal+, beIN…),
    # texte libre, uniquement si usage_tv != "Jamais, uniquement streaming".
    abonnements_payants: Mapped[str | None] = mapped_column(String, nullable=True)
    # ==========================================================================
    #  PORTABILITÉ — mêmes questions que la démarche "portabilite" (voir
    #  document_engine.CHAMPS_REQUIS_PAR_TEMPLATE), mais posées ici dès le lien
    #  prospect (avant qu'un dossier n'existe), sur le contrat mobile
    #  concurrent concerné. Migration : 0048_trame_mobile_portabilite.
    # ==========================================================================
    # "oui" | "non" — si "oui", rio/numero_ligne deviennent pertinents.
    conserver_numero: Mapped[str | None] = mapped_column(String, nullable=True)
    rio: Mapped[str | None] = mapped_column(String, nullable=True)
    numero_ligne: Mapped[str | None] = mapped_column(String, nullable=True)
    # "esim" | "carte_sim".
    type_sim: Mapped[str | None] = mapped_column(String, nullable=True)
    # ==========================================================================
    #  TRAME BOX — B4/B5/B6/B7 (docs/QUESTIONS_PAR_SECTEUR.md), posées
    #  uniquement sur le lien personnel du prospect (jamais sur /economiser,
    #  qui reste volontairement courte). Migration : 0051_trame_box_lien.
    # ==========================================================================
    # B4 : "1-2" | "3+" utilisateurs simultanés en streaming.
    nb_utilisateurs_streaming: Mapped[str | None] = mapped_column(String, nullable=True)
    # B4 : vidéo 4K régulière déclarée.
    usage_4k: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # B5 : "non" | "oui_occasionnel" | "oui_frequent".
    teletravail: Mapped[str | None] = mapped_column(String, nullable=True)
    # B6 : "oui" | "non" | "a_voir" — intérêt pour une box 4G/5G en
    # remplacement, posé si le prospect a aussi une ligne mobile.
    interet_box_4g5g: Mapped[str | None] = mapped_column(String, nullable=True)
    # B7 : "oui" | "non" — téléphone fixe rattaché à la box, utilisé.
    telephone_fixe_utilise: Mapped[str | None] = mapped_column(String, nullable=True)
    # B7 : texte libre, posé seulement si telephone_fixe_utilise == "oui".
    appels_fixe_mensuels: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="contrats")
    prospect: Mapped["Prospect"] = relationship(back_populates="contrats")
