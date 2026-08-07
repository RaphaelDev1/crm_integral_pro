# ==============================================================================
#  NOTIFICATION — alerte in-app pour le conseiller quand le client agit de son
#  côté sans que le conseiller ne regarde (upload de document, speedtest,
#  signature de mandat) ou quand un dossier change de statut. Distinct des
#  notifications envoyées au client (voir backend/services/dossier_notifications.py).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.dossier import Dossier


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conseiller_username: Mapped[str] = mapped_column(String, nullable=False)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id"), nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    lu: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)

    dossier: Mapped["Dossier"] = relationship()
