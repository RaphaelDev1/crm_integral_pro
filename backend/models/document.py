# ==============================================================================
#  DOCUMENT — document KYC uploadé par un client (CNI, justificatif de
#  domicile, RIB), validé par backend/services/kyc_engine.py.
#  `statut_kyc` : en_attente | valide | rejete | erreur.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    type_document: Mapped[str | None] = mapped_column(String, nullable=True)
    url_stockage: Mapped[str] = mapped_column(String, nullable=False)
    statut_kyc: Mapped[str] = mapped_column(String, default="en_attente", server_default="en_attente")
    motif_rejet: Mapped[str | None] = mapped_column(String, nullable=True)
    date_upload: Mapped[str | None] = mapped_column(String, nullable=True)
    date_validation: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship()
