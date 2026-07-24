# ==============================================================================
#  ABONNEMENT — abonnement Gestionnaire personnel (4,90€/mois particuliers,
#  14,90€/mois pro). MRR récurrent, prélèvement Stripe SEPA.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client


class Abonnement(Base):
    __tablename__ = "abonnements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)

    formule: Mapped[str] = mapped_column(String, nullable=False)   # 'gestionnaire_perso' | 'gestionnaire_pro'
    prix_mensuel: Mapped[float] = mapped_column(Float, nullable=False)

    date_debut: Mapped[str | None] = mapped_column(String, nullable=True)
    date_fin: Mapped[str | None] = mapped_column(String, nullable=True)

    statut: Mapped[str] = mapped_column(String, default="actif")   # actif | suspendu | resilie

    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship()
