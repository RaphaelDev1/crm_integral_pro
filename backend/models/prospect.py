# ==============================================================================
#  PROSPECT — miroir de la table `prospects` (src/db.py, création + colonnes
#  ajoutées par _migrer_bdd()). Les dates restent des chaînes "%d/%m/%Y %H:%M"
#  pour rester compatibles avec le formatage utilisé côté Streamlit (src/app.py).
# ==============================================================================
from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Client "miroir" (cf. backend/services/prospect_conversion.py) : renseigné dès qu'un
    # dossier ou un token de documents pré-conversion a besoin d'un Client réel, réutilisé
    # (pas recréé) comme client définitif à la conversion.
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    converti_at: Mapped[str | None] = mapped_column(String, nullable=True)
    ref: Mapped[str | None] = mapped_column(String, nullable=True)
    prenom: Mapped[str | None] = mapped_column(String, nullable=True)
    nom: Mapped[str | None] = mapped_column(String, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    code_postal: Mapped[str | None] = mapped_column(String, nullable=True)
    ville: Mapped[str | None] = mapped_column(String, nullable=True)
    adresse: Mapped[str | None] = mapped_column(String, nullable=True)
    type_client: Mapped[str | None] = mapped_column(String, nullable=True)
    univers_interesse: Mapped[str | None] = mapped_column(String, nullable=True)
    service_principal: Mapped[str | None] = mapped_column(String, nullable=True)
    operateur_actuel: Mapped[str | None] = mapped_column(String, nullable=True)
    techno: Mapped[str | None] = mapped_column(String, nullable=True)
    data_go: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_mensuel_actuel: Mapped[float | None] = mapped_column(Float, default=0)
    offre_actuelle: Mapped[str | None] = mapped_column(String, nullable=True)
    satisfaction_reseau: Mapped[str | None] = mapped_column(String, nullable=True)
    veut_rester: Mapped[str | None] = mapped_column(String, nullable=True)
    speed_down: Mapped[float | None] = mapped_column(Float, default=0)
    speed_up: Mapped[float | None] = mapped_column(Float, default=0)
    cout_elec: Mapped[float | None] = mapped_column(Float, default=0)
    cout_gaz: Mapped[float | None] = mapped_column(Float, default=0)
    fournisseur_energie: Mapped[str | None] = mapped_column(String, nullable=True)
    abonnements: Mapped[str | None] = mapped_column(String, nullable=True)
    lignes_multi: Mapped[str | None] = mapped_column(String, nullable=True)
    economie_estimee_an: Mapped[float | None] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    statut: Mapped[str | None] = mapped_column(String, default="À relancer")
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_relance: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)
    offres_interet: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, default=0)
    origine: Mapped[str | None] = mapped_column(String, default="Manuel")
