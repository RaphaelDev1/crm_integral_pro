# ==============================================================================
#  FACTURE ANALYSÉE — résultat persisté de backend/services/facture_analyzer.py
#  (extraction LLM d'une facture télécom/énergie), lié à un client pour former
#  le « briefing avant appel » du conseiller (GET /clients/{id}/briefing).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client
    from backend.models.dossier import Dossier
    from backend.models.prospect import Prospect


class FactureAnalyse(Base):
    __tablename__ = "factures_analysees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Une analyse est liée à un client OU à un prospect (pas encore client) —
    # prospect_id alimenté automatiquement à l'upload d'une facture via le
    # lien de collecte documents (voir backend/routers/portail_public.py).
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    prospect_id: Mapped[int | None] = mapped_column(ForeignKey("prospects.id"), nullable=True)
    dossier_id: Mapped[int | None] = mapped_column(ForeignKey("dossiers.id"), nullable=True)

    operateur: Mapped[str | None] = mapped_column(String, nullable=True)
    prix_ht: Mapped[float] = mapped_column(Float, default=0.0)
    prix_ttc: Mapped[float] = mapped_column(Float, default=0.0)
    data_conso_go: Mapped[float] = mapped_column(Float, default=0.0)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    engagement_mois: Mapped[int] = mapped_column(Integer, default=0)
    date_fin_engagement: Mapped[str | None] = mapped_column(String, nullable=True)
    iban_prelevement: Mapped[str | None] = mapped_column(String, nullable=True)
    # Champs assurance auto (facture d'assurance plutôt que télécom/énergie) —
    # chaîne vide si non applicable au document analysé.
    type_couverture: Mapped[str | None] = mapped_column(String, nullable=True)
    bonus_malus: Mapped[str | None] = mapped_column(String, nullable=True)

    date_analyse: Mapped[str | None] = mapped_column(String, nullable=True)
    analyse_par: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client | None"] = relationship()
    prospect: Mapped["Prospect | None"] = relationship()
    dossier: Mapped["Dossier | None"] = relationship()
