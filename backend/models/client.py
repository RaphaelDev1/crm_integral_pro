# ==============================================================================
#  CLIENT — miroir de la table `clients` (src/db.py, création + colonnes
#  ajoutées par _migrer_bdd()).
# ==============================================================================
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.contrat import Contrat


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ref: Mapped[str | None] = mapped_column(String, nullable=True)
    # Conseiller propriétaire de la fiche — seul lui (ou un Admin) peut la voir/modifier
    # (voir backend/routers/clients.py). NULL = fiche existante avant l'introduction de
    # cette colonne, restant visible/éditable transitoirement le temps d'être réclamée.
    conseiller_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateurs.id"), nullable=True)
    # ClientConseil IA Conseil rattaché (cf. backend/services/ia_conseil_bridge.py) —
    # créé à la demande à l'entrée de l'étape "Trame" du diagnostic fusionné,
    # jamais recréé ensuite. Migration : 0037_ia_conseil_bridge.
    ia_conseil_client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("client.id"), nullable=True)
    prenom: Mapped[str | None] = mapped_column(String, nullable=True)
    nom: Mapped[str | None] = mapped_column(String, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    code_postal: Mapped[str | None] = mapped_column(String, nullable=True)
    ville: Mapped[str | None] = mapped_column(String, nullable=True)
    adresse: Mapped[str | None] = mapped_column(String, nullable=True)
    type_client: Mapped[str | None] = mapped_column(String, nullable=True)
    # Renseignés uniquement pour type_client == "Professionnel", repris du
    # prospect à la conversion (voir prospect_conversion.CHAMPS_PROSPECT_VERS_CLIENT).
    raison_sociale: Mapped[str | None] = mapped_column(String, nullable=True)
    effectif: Mapped[str | None] = mapped_column(String, nullable=True)
    operateur_actuel: Mapped[str | None] = mapped_column(String, nullable=True)
    techno: Mapped[str | None] = mapped_column(String, nullable=True)
    data_go: Mapped[str | None] = mapped_column(String, nullable=True)
    # Mêmes questions/valeurs que la trame mobile (roaming_ue / sensibilite_prix,
    # voir backend/scripts/seed_ia_conseil.py) — désormais posées aussi sur la
    # landing publique /economiser. Migration : 0038_landing_roaming_priorite.
    roaming_europe: Mapped[str | None] = mapped_column(String, nullable=True)
    sensibilite_prix: Mapped[str | None] = mapped_column(String, nullable=True)
    offre_actuelle: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_mensuel_actuel: Mapped[float | None] = mapped_column(Float, default=0)
    satisfaction_reseau: Mapped[str | None] = mapped_column(String, nullable=True)
    veut_rester: Mapped[str | None] = mapped_column(String, nullable=True)
    # Signalement d'un défaut technique potentiel constaté sur le réseau actuel
    # du client ("Faible" | "Moyen" | "Critique"), voir NIVEAUX_DEFAUT_TECHNIQUE
    # côté frontend (lib/diagnosticConstants.ts).
    defaut_technique: Mapped[str | None] = mapped_column(String, nullable=True)
    speed_down: Mapped[float | None] = mapped_column(Float, default=0)
    speed_up: Mapped[float | None] = mapped_column(Float, default=0)
    fournisseur_energie: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_elec: Mapped[float | None] = mapped_column(Float, default=0)
    cout_gaz: Mapped[float | None] = mapped_column(Float, default=0)
    economie_estimee_an: Mapped[float | None] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)
    date_relance: Mapped[str | None] = mapped_column(String, nullable=True)
    statut_relance: Mapped[str | None] = mapped_column(String, default="Aucune")

    contrats: Mapped[list["Contrat"]] = relationship(back_populates="client")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)