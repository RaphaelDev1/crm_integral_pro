# ==============================================================================
#  DEMARCHE — document généré pour une démarche post-vente (résiliation,
#  portabilité, changement de fournisseur, mandat, souscription) rattachée à
#  un dossier, envoyé par un canal tracé (LRE AR24 par défaut).
#
#  Cycle de vie type :
#    a_generer → generee → envoyee → accusee
#              (ou → echouee depuis n'importe quelle étape)
#
#  RÈGLE LÉGALE : aucun document n'est généré tant que le mandat de
#  représentation du client (`mandats.statut`) n'est pas "signe" — appliquée
#  dans backend/services/demarches_engine.py::generer_document, pas ici (pas
#  modélisable en contrainte SQL portable).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.dossier import Dossier
    from backend.models.mandat import Mandat


TYPES_DEMARCHE = ("mandat", "resiliation", "portabilite", "souscription", "changement_fournisseur")
STATUTS_DEMARCHE = ("a_generer", "generee", "envoyee", "accusee", "echouee")


class Demarche(Base):
    __tablename__ = "demarches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id"), nullable=False)
    mandat_id: Mapped[int | None] = mapped_column(ForeignKey("mandats.id"), nullable=True)

    # Copié depuis dossier.univers à la création (dénormalisé — la démarche
    # reste cohérente même si l'univers du dossier est modifié plus tard).
    univers: Mapped[str] = mapped_column(String, nullable=False)
    type_demarche: Mapped[str] = mapped_column(String, nullable=False)
    statut: Mapped[str] = mapped_column(String, default="a_generer", server_default="a_generer", nullable=False)
    canal: Mapped[str] = mapped_column(String, default="lre", server_default="lre")

    document_url: Mapped[str | None] = mapped_column(String, nullable=True)   # clé S3 du PDF généré
    preuve_envoi: Mapped[str | None] = mapped_column(String, nullable=True)   # id LRE (AR24)
    preuve_url: Mapped[str | None] = mapped_column(String, nullable=True)     # clé S3 de l'accusé de dépôt
    donnees_requises: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_generation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_envoi: Mapped[str | None] = mapped_column(String, nullable=True)
    date_accuse: Mapped[str | None] = mapped_column(String, nullable=True)

    dossier: Mapped["Dossier"] = relationship()
    mandat: Mapped["Mandat | None"] = relationship()
