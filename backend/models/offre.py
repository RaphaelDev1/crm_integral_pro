# ==============================================================================
#  OFFRE — miroir de la table `offres` (catalogue, src/db.py).
# ==============================================================================
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Offre(Base):
    __tablename__ = "offres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    univers: Mapped[str | None] = mapped_column(String, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)
    nom_offre: Mapped[str | None] = mapped_column(String, nullable=True)
    prix_mensuel: Mapped[float | None] = mapped_column(Float, nullable=True)
    frais_activation: Mapped[float | None] = mapped_column(Float, nullable=True)
    engagement_mois: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caracteristiques: Mapped[str | None] = mapped_column(String, nullable=True)
    commission_affiliation: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_go: Mapped[float | None] = mapped_column(Float, default=0)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    url_souscription: Mapped[str | None] = mapped_column(String, nullable=True)
    code_affiliation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_maj: Mapped[str | None] = mapped_column(String, nullable=True)
