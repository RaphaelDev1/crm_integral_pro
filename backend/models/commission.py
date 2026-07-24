# ==============================================================================
#  COMMISSION — tracking des commissions à recevoir (fournisseur) et à
#  facturer (client sur % économies).
#
#  Statuts :
#    - attendue : commission promise mais non encore confirmée
#    - confirmee : le fournisseur/client a confirmé le paiement
#    - recue : argent reçu sur le compte
#    - contestee : problème à investiguer
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.dossier import Dossier


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id"), nullable=False)

    source: Mapped[str] = mapped_column(String, nullable=False)   # 'fournisseur' | 'client'
    montant: Mapped[float] = mapped_column(Float, nullable=False)
    statut: Mapped[str] = mapped_column(String, default="attendue")

    date_prevue: Mapped[str | None] = mapped_column(String, nullable=True)
    date_recue: Mapped[str | None] = mapped_column(String, nullable=True)

    reference_paiement: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    dossier: Mapped["Dossier"] = relationship(back_populates="commissions")
