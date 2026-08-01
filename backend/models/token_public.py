# ==============================================================================
#  TOKEN PUBLIC — lien unique donné au client pour accéder à son dossier sans
#  login. Généré par le conseiller, envoyé au client par SMS/email.
#
#  URL type : https://client.iaconseil.fr/dossier/<token>
#
#  Sécurité :
#    - Token = 32 caractères URL-safe (secrets.token_urlsafe)
#    - Expiration configurable (par défaut 30 jours)
#    - Optionnel : lock sur l'IP de première utilisation
#    - Révocable à tout moment par le conseiller
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.dossier import Dossier
    from backend.models.client import Client
    from backend.models.prospect import Prospect


class TokenPublic(Base):
    __tablename__ = "tokens_publics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # Ce à quoi le token donne accès — exactement l'un des deux (contrainte XOR en base,
    # cf. migration 0019) : soit un Client (parcours dossier standard), soit un Prospect
    # pas encore converti (parcours « transmettre facture/speedtest avant conversion »,
    # cf. backend/services/token_engine.py::generer_token_prospect_documents).
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    prospect_id: Mapped[int | None] = mapped_column(ForeignKey("prospects.id"), nullable=True)
    dossier_id: Mapped[int | None] = mapped_column(ForeignKey("dossiers.id"), nullable=True)

    # Permissions granulaires
    peut_uploader_docs: Mapped[bool] = mapped_column(Boolean, default=True)
    peut_signer_mandat: Mapped[bool] = mapped_column(Boolean, default=True)
    peut_voir_suivi: Mapped[bool] = mapped_column(Boolean, default=True)
    peut_renseigner_demarches: Mapped[bool] = mapped_column(Boolean, default=True)
    peut_transmettre_speedtest: Mapped[bool] = mapped_column(Boolean, default=True)

    # Cycle de vie
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_expiration: Mapped[str | None] = mapped_column(String, nullable=True)
    date_premiere_utilisation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_derniere_utilisation: Mapped[str | None] = mapped_column(String, nullable=True)

    # Sécurité
    ip_premiere_utilisation: Mapped[str | None] = mapped_column(String, nullable=True)
    nb_utilisations: Mapped[int] = mapped_column(Integer, default=0)
    revoque: Mapped[bool] = mapped_column(Boolean, default=False)
    motif_revocation: Mapped[str | None] = mapped_column(String, nullable=True)

    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)

    client: Mapped["Client | None"] = relationship()
    prospect: Mapped["Prospect | None"] = relationship()
    dossier: Mapped["Dossier | None"] = relationship()
