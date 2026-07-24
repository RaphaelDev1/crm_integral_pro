# ==============================================================================
#  UTILISATEUR — miroir de la table `utilisateurs` (src/db.py). Le hachage du
#  mot de passe (PBKDF2-SHA256, 260k itérations) reste géré par
#  backend/core/security.py, pas par le modèle.
# ==============================================================================
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class User(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nom_complet: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="Conseiller", server_default="Conseiller")
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    doit_changer_mdp: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
