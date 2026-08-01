# ==============================================================================
#  COMPARAISON D'OFFRE — enregistrement d'une comparaison/recommandation
#  d'offres pour un prospect ou un client (logique de calcul portée par
#  src/offres_engine.py::comparer_offres/construire_recommandations, non
#  reprise ici — cette table n'est que la persistance du résultat).
#
#  `offres_comparees` fige un instantané des offres comparées au moment du
#  calcul (nom, fournisseur, prix, économie) : `offres.prix_mensuel` peut
#  changer ensuite via la veille, la comparaison historique ne doit pas bouger.
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client
    from backend.models.offre import Offre
    from backend.models.prospect import Prospect


class ComparaisonOffre(Base):
    __tablename__ = "comparaisons_offres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prospect_id: Mapped[int | None] = mapped_column(ForeignKey("prospects.id"), nullable=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)

    univers: Mapped[str | None] = mapped_column(String, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_actuel_mensuel: Mapped[float | None] = mapped_column(Float, nullable=True)

    offre_recommandee_id: Mapped[int | None] = mapped_column(ForeignKey("offres.id"), nullable=True)
    offres_comparees: Mapped[list | None] = mapped_column(JSON, nullable=True)

    economie_mensuelle_estimee: Mapped[float | None] = mapped_column(Float, default=0)
    economie_annuelle_estimee: Mapped[float | None] = mapped_column(Float, default=0)

    contexte: Mapped[str | None] = mapped_column(String, nullable=True)
    date_comparaison: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)

    prospect: Mapped["Prospect"] = relationship()
    client: Mapped["Client"] = relationship()
    offre_recommandee: Mapped["Offre"] = relationship()
