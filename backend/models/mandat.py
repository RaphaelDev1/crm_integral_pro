# ==============================================================================
#  MANDAT — mandat de représentation envoyé en signature électronique (Yousign)
#  pour un client. `statut` : brouillon | envoye | recu | signe | refuse | erreur.
#  "recu" = document signé reçu (webhook Yousign) mais pas encore validé par le
#  conseiller — même logique que la vérification manuelle des documents KYC :
#  la réception ne suffit pas, il faut le clic "Valider" (voir
#  backend/routers/mandats.py::valider_mandat) pour passer à "signe" et
#  déclencher la suite (conversion prospect→client, relance).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client


class Mandat(Base):
    __tablename__ = "mandats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    statut: Mapped[str] = mapped_column(String, default="brouillon", server_default="brouillon")
    pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_signe_url: Mapped[str | None] = mapped_column(String, nullable=True)
    yousign_signature_request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    yousign_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_envoi: Mapped[str | None] = mapped_column(String, nullable=True)
    date_signature: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship()
