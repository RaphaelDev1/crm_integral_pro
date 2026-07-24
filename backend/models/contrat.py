# ==============================================================================
#  CONTRAT — miroir de la table `contrats` (src/db.py).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client


class Contrat(Base):
    __tablename__ = "contrats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
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
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="contrats")
