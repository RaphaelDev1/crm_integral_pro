# ==============================================================================
#  LOGIN TENTATIVE — audit + rate limiting login (insert-only), une ligne par
#  tentative de connexion (succès ou échec), miroir de src/db.py::login_tentatives.
#  Voir backend/core/security.py::compte_verrouille/enregistrer_tentative.
# ==============================================================================
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class LoginTentative(Base):
    __tablename__ = "login_tentatives"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identifiant: Mapped[str | None] = mapped_column(String, nullable=True)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    succes: Mapped[bool] = mapped_column(Boolean, default=False)
    date_tentative: Mapped[str | None] = mapped_column(String, nullable=True)
