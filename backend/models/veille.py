# ==============================================================================
#  VEILLE — surveillance des prix opérateurs (miroir de src/db.py : sources_veille,
#  veille_historique_prix, veille_alertes). La logique de scraping/validation reste
#  dans src/veille_prix_engine.py — ces tables ne sont que la couche de données.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.offre import Offre


class SourceVeille(Base):
    __tablename__ = "sources_veille"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    univers: Mapped[str | None] = mapped_column(String, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)
    nom_offre: Mapped[str | None] = mapped_column(String, nullable=True)
    offre_id: Mapped[int | None] = mapped_column(ForeignKey("offres.id"), nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    selecteur_prix: Mapped[str | None] = mapped_column(String, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    dernier_prix: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_derniere_verif: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)

    offre: Mapped["Offre"] = relationship()


class VeilleHistoriquePrix(Base):
    __tablename__ = "veille_historique_prix"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources_veille.id"), nullable=True)
    prix: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_releve: Mapped[str | None] = mapped_column(String, nullable=True)


class VeilleAlerte(Base):
    __tablename__ = "veille_alertes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources_veille.id"), nullable=True)
    ancien_prix: Mapped[float | None] = mapped_column(Float, nullable=True)
    nouveau_prix: Mapped[float | None] = mapped_column(Float, nullable=True)
    statut: Mapped[str] = mapped_column(String, default="en_attente", server_default="en_attente")
    date_detection: Mapped[str | None] = mapped_column(String, nullable=True)
    date_traitement: Mapped[str | None] = mapped_column(String, nullable=True)
