# ==============================================================================
#  DOCUMENT PROSPECT — fichier (facture, speedtest) transmis par un prospect
#  via son lien personnel (portail prospect, src/chatbot_api.py), miroir de
#  src/db.py::documents_prospect. Table dédiée, distincte de `documents` (KYC
#  client) : cycle de vie différent — soumis par le prospect lui-même avant
#  toute conversion en client, pas de workflow de validation KYC.
#
#  Stocké sur S3 (backend/services/storage_engine.py::upload_fichier), comme
#  `Document.url_stockage`/`Mandat.pdf_url` — pas de contenu inline en base.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.prospect import Prospect


class DocumentProspect(Base):
    __tablename__ = "documents_prospect"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prospect_id: Mapped[int] = mapped_column(ForeignKey("prospects.id"), nullable=False)
    type_document: Mapped[str | None] = mapped_column(String, nullable=True)  # "facture" | "speedtest"
    nom_fichier: Mapped[str | None] = mapped_column(String, nullable=True)
    cle_stockage: Mapped[str] = mapped_column(String, nullable=False)
    mime: Mapped[str | None] = mapped_column(String, nullable=True)
    date_upload: Mapped[str | None] = mapped_column(String, nullable=True)

    prospect: Mapped["Prospect"] = relationship()
