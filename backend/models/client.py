# ==============================================================================
#  CLIENT — miroir de la table `clients` (src/db.py, création + colonnes
#  ajoutées par _migrer_bdd()).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.contrat import Contrat


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ref: Mapped[str | None] = mapped_column(String, nullable=True)
    prenom: Mapped[str | None] = mapped_column(String, nullable=True)
    nom: Mapped[str | None] = mapped_column(String, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    code_postal: Mapped[str | None] = mapped_column(String, nullable=True)
    ville: Mapped[str | None] = mapped_column(String, nullable=True)
    adresse: Mapped[str | None] = mapped_column(String, nullable=True)
    type_client: Mapped[str | None] = mapped_column(String, nullable=True)
    operateur_actuel: Mapped[str | None] = mapped_column(String, nullable=True)
    techno: Mapped[str | None] = mapped_column(String, nullable=True)
    data_go: Mapped[str | None] = mapped_column(String, nullable=True)
    offre_actuelle: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_mensuel_actuel: Mapped[float | None] = mapped_column(Float, default=0)
    satisfaction_reseau: Mapped[str | None] = mapped_column(String, nullable=True)
    veut_rester: Mapped[str | None] = mapped_column(String, nullable=True)
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
