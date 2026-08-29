# ==============================================================================
#  TOUCHPOINT — point de contact UTM d'un prospect avant sa conversion en lead
#  (première visite landing, visites suivantes avant remplissage du formulaire).
#  Alimenté côté client par frontend-portail/lib/attribution.ts (historique
#  first-party stocké en localStorage), envoyé avec le payload de
#  POST /public/leads/capture et persisté par backend/routers/leads_public.py.
#  Sert l'attribution multi-touch (premier vs dernier contact) du dashboard
#  conseiller — voir backend/routers/dashboard_utm.py. Migration : 0029.
# ==============================================================================
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Touchpoint(Base):
    __tablename__ = "touchpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prospect_id: Mapped[int] = mapped_column(ForeignKey("prospects.id"), nullable=False)
    # Position dans la chaîne (0 = premier contact connu, croissant jusqu'à la
    # conversion) — reçue telle quelle depuis le client, pas recalculée.
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    utm_source: Mapped[str | None] = mapped_column(String, nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String, nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String, nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String, nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String, nullable=True)
    referrer: Mapped[str | None] = mapped_column(String, nullable=True)
    landing_page: Mapped[str | None] = mapped_column(String, nullable=True)
    # Horodatage déclaré par le navigateur (ISO 8601) — indicatif seulement,
    # ne pas utiliser pour trier de façon fiable (horloge client non fiable) ;
    # préférer `ordre`.
    horodatage_client: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
