# ==============================================================================
#  HISTORIQUE ACTIONS — journal d'audit générique, insert-only, miroir de
#  src/db.py::historique_actions. Alimenté par backend/services/audit_engine.py.
# ==============================================================================
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class HistoriqueAction(Base):
    __tablename__ = "historique_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entite_type: Mapped[str] = mapped_column(String, nullable=False)
    entite_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str | None] = mapped_column(String, nullable=True)
    auteur: Mapped[str | None] = mapped_column(String, nullable=True)
    date_action: Mapped[str | None] = mapped_column(String, nullable=True)
