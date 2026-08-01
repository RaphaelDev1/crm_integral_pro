# ==============================================================================
#  CATALOGUE SOURCE — pages tarifs/flux à ingérer pour découvrir de nouvelles
#  offres (miroir de src/db.py : catalogue_sources). Voir
#  backend/services/catalogue_engine.py pour la logique de scraping/extraction.
# ==============================================================================
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class CatalogueSource(Base):
    __tablename__ = "catalogue_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    univers: Mapped[str | None] = mapped_column(String, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    type_source: Mapped[str] = mapped_column(String, default="page_officielle", server_default="page_officielle")
    methode: Mapped[str] = mapped_column(String, default="requests", server_default="requests")
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    robots_ok: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    frequence_h: Mapped[int] = mapped_column(Integer, default=24, server_default="24")
    date_derniere_ingestion: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
