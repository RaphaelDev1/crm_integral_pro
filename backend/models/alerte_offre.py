# ==============================================================================
#  ALERTE OFFRE — détection automatique d'une offre du catalogue moins chère
#  que le contrat actif d'un client (voir backend/services/alertes_offres_engine.py
#  et la tâche Celery Beat périodique backend/workers/tasks.py::detecter_offres_moins_cheres_periodique).
#  Même principe que backend/models/veille.py::VeilleAlerte : ne modifie jamais
#  le contrat directement, une validation explicite du conseiller déclenche la
#  notification client.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client
    from backend.models.contrat import Contrat
    from backend.models.offre import Offre


class AlerteOffre(Base):
    __tablename__ = "alertes_offres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    contrat_id: Mapped[int | None] = mapped_column(ForeignKey("contrats.id"), nullable=True)
    offre_id: Mapped[int | None] = mapped_column(ForeignKey("offres.id"), nullable=True)

    cout_actuel: Mapped[float | None] = mapped_column(Float, nullable=True)
    cout_propose: Mapped[float | None] = mapped_column(Float, nullable=True)
    economie_mensuelle: Mapped[float | None] = mapped_column(Float, nullable=True)
    economie_annuelle: Mapped[float | None] = mapped_column(Float, nullable=True)

    statut: Mapped[str] = mapped_column(String, default="en_attente", server_default="en_attente")
    date_detection: Mapped[str | None] = mapped_column(String, nullable=True)
    date_traitement: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client"] = relationship()
    contrat: Mapped["Contrat"] = relationship()
    offre: Mapped["Offre"] = relationship()
