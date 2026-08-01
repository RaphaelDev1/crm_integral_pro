# ==============================================================================
#  OFFRE STAGING — offre détectée par le pipeline d'ingestion LLM (voir
#  backend/services/catalogue_engine.py), en attente de validation admin avant
#  d'être copiée dans `offres` (miroir de src/db.py : offres_staging). Le
#  catalogue (`offres`) n'est jamais modifié directement par l'ingestion.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.catalogue_source import CatalogueSource
    from backend.models.offre import Offre


class OffreStaging(Base):
    __tablename__ = "offres_staging"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("catalogue_sources.id"), nullable=True)
    univers: Mapped[str | None] = mapped_column(String, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)
    nom_offre: Mapped[str | None] = mapped_column(String, nullable=True)
    prix_mensuel: Mapped[float | None] = mapped_column(Float, nullable=True)
    frais_activation: Mapped[float | None] = mapped_column(Float, default=0)
    engagement_mois: Mapped[int | None] = mapped_column(Integer, default=0)
    data_go: Mapped[float | None] = mapped_column(Float, default=0)
    caracteristiques: Mapped[str | None] = mapped_column(String, nullable=True)
    commission_affiliation: Mapped[float | None] = mapped_column(Float, default=0)
    url_souscription: Mapped[str | None] = mapped_column(String, nullable=True)
    code_affiliation: Mapped[str | None] = mapped_column(String, nullable=True)
    hash_contenu: Mapped[str | None] = mapped_column(String, nullable=True)
    statut: Mapped[str] = mapped_column(String, default="en_attente", server_default="en_attente")
    confiance_llm: Mapped[float | None] = mapped_column(Float, nullable=True)
    champs_incertains: Mapped[list | None] = mapped_column(JSON, nullable=True)
    payload_brut: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    offre_existante_id: Mapped[int | None] = mapped_column(ForeignKey("offres.id"), nullable=True)
    date_detection: Mapped[str | None] = mapped_column(String, nullable=True)
    date_traitement: Mapped[str | None] = mapped_column(String, nullable=True)

    source: Mapped["CatalogueSource"] = relationship()
    offre_existante: Mapped["Offre"] = relationship()
