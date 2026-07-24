# ==============================================================================
#  MANDAT HONORAIRES — mandat de représentation distinct du mandat Yousign
#  (`Mandat`) : couvre la rémunération du cabinet (taux/montant d'honoraires),
#  rattaché à un dossier. `statut` : brouillon | envoye | signe.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.dossier import Dossier


class MandatHonoraires(Base):
    __tablename__ = "mandats_honoraires"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id"), nullable=False, unique=True)
    montant: Mapped[float] = mapped_column(Float, default=0.0)
    taux: Mapped[float] = mapped_column(Float, default=0.0)
    statut: Mapped[str] = mapped_column(String, default="brouillon", server_default="brouillon")
    signataire: Mapped[str | None] = mapped_column(String, nullable=True)
    date_signature: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    dossier: Mapped["Dossier"] = relationship()
