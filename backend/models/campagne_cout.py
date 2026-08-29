# ==============================================================================
#  CAMPAGNE COÛT — dépense publicitaire saisie manuellement par campagne/mois
#  (Meta Ads, TikTok Ads, Google Ads…), faute d'intégration API directe avec
#  ces régies. Sert uniquement au calcul du CAC (coût d'acquisition client)
#  dans le dashboard UTM — backend/routers/dashboard_utm.py (P4.1).
#  Saisie/édition : Admin > Dashboard UTM (frontend-conseiller). Migration : 0029.
# ==============================================================================
from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class CampagneCout(Base):
    __tablename__ = "campagnes_couts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    utm_source: Mapped[str] = mapped_column(String, nullable=False)
    utm_campaign: Mapped[str | None] = mapped_column(String, nullable=True)
    # Format "YYYY-MM" — un coût par campagne et par mois calendaire.
    mois: Mapped[str] = mapped_column(String, nullable=False)
    cout: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
