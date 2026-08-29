# ==============================================================================
#  NOTIFICATION — alerte in-app pour le conseiller quand le client agit de son
#  côté sans que le conseiller ne regarde (upload de document, speedtest,
#  signature de mandat) ou quand un dossier change de statut. Distinct des
#  notifications envoyées au client (voir backend/services/dossier_notifications.py).
#
#  `dossier_id` est nullable et `lien` existe depuis PLAN_IMPLEMENTATION_4_PHASES.md
#  §2.3 : le sous-système IA Conseil (evenement_planifie, veille souscriptions,
#  anti-biais...) n'a pas de `Dossier` CRM à pointer, mais réutilise cette même
#  table plutôt qu'un système de notifications parallèle — `lien` porte alors
#  une route relative (ex. "/ia-conseil/clients/{id}"), voir
#  backend/services/notification_engine.py::creer_notification_generique et
#  components/layout/NotificationsBell.tsx qui préfère `lien` à `dossier_id`
#  quand les deux sont possibles.
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
    dossier_id: Mapped[int | None] = mapped_column(ForeignKey("dossiers.id"), nullable=True)
    message: Mapped[str] = mapped_column(String, nullable=False)
    lien: Mapped[str | None] = mapped_column(String, nullable=True)
    lu: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)

    dossier: Mapped["Dossier | None"] = relationship()
