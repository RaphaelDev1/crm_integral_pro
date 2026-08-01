# ==============================================================================
#  PARAMETRE — réglages clé/valeur génériques (nom société, taux d'honoraires,
#  SMTP, Telegram, clé API...), miroir de src/db.py::parametres.
#
#  ⚠️ Certaines valeurs sont des secrets en clair (smtp_mdp, telegram_bot_token,
#  anthropic_api_key) — l'accès en lecture (GET /parametres) doit rester
#  réservé au rôle Admin (voir backend/routers/parametres.py). Aucun
#  chiffrement au repos n'est mis en place ici, à considérer plus tard.
# ==============================================================================
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Parametre(Base):
    __tablename__ = "parametres"

    cle: Mapped[str] = mapped_column(String, primary_key=True)
    valeur: Mapped[str | None] = mapped_column(String, nullable=True)
