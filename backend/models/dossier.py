# ==============================================================================
#  DOSSIER — représente un dossier de souscription / changement d'offre pour un
#  client. Machine à états stricte via `statut`.
#
#  Cycle de vie type :
#    initie → docs_demandes → docs_recus → mandat_a_signer → mandat_signe
#            → soumis_fournisseur → en_activation → actif → facture
#            (ou → echec / annule)
#
#  Chaque transition d'état est validée par backend/services/dossier_engine.py
#  et journalisée dans notes_workflow (JSONB).
# ==============================================================================
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.client import Client
    from backend.models.commission import Commission


STATUTS_DOSSIER = (
    "initie",
    "docs_demandes",
    "docs_recus",
    "mandat_a_signer",
    "mandat_signe",
    "soumis_fournisseur",
    "en_activation",
    "actif",
    "facture",
    "echec",
    "annule",
)


class Dossier(Base):
    __tablename__ = "dossiers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    contrat_id: Mapped[int | None] = mapped_column(ForeignKey("contrats.id"), nullable=True)
    offre_cible_id: Mapped[int | None] = mapped_column(ForeignKey("offres.id"), nullable=True)

    # Contexte du dossier
    univers: Mapped[str] = mapped_column(String, nullable=False)          # telecom, energie, alarme, tpe...
    fournisseur_cible: Mapped[str | None] = mapped_column(String, nullable=True)
    economie_annuelle_estimee: Mapped[float] = mapped_column(Float, default=0.0)
    # Snapshot des frais annexes de l'offre cible (SIM, résiliation, portabilité)
    # au moment où le conseiller l'a choisie — voir offres_engine.comparer_offres.
    frais_annexes_cible: Mapped[float] = mapped_column(Float, default=0.0)

    # True tant que le client rattaché n'est encore qu'un prospect côté CRM (cf.
    # backend/services/prospect_conversion.py) — bascule à False lors de la conversion
    # officielle (signature du mandat). Purement informatif : la collecte de documents
    # (cf. dossier_engine.documents_requis_pour_univers) ne dépend plus de ce flag —
    # elle démarre dès la création du dossier, en parallèle de la signature du mandat.
    est_prospect: Mapped[bool] = mapped_column(default=True, server_default="true")

    # État
    statut: Mapped[str] = mapped_column(String, default="initie", nullable=False)

    # Dates clés (chaînes "%d/%m/%Y %H:%M" pour cohérence avec le reste)
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_soumission: Mapped[str | None] = mapped_column(String, nullable=True)
    date_activation_prevue: Mapped[str | None] = mapped_column(String, nullable=True)
    date_activation_reelle: Mapped[str | None] = mapped_column(String, nullable=True)
    date_derniere_transition: Mapped[str | None] = mapped_column(String, nullable=True)
    derniere_relance_envoyee_le: Mapped[str | None] = mapped_column(String, nullable=True)

    # Suivi fournisseur
    reference_fournisseur: Mapped[str | None] = mapped_column(String, nullable=True)

    # Rémunération
    commission_attendue: Mapped[float] = mapped_column(Float, default=0.0)
    commission_recue: Mapped[float] = mapped_column(Float, default=0.0)
    part_client_totale: Mapped[float] = mapped_column(Float, default=0.0)
    duree_prelevement_mois: Mapped[int] = mapped_column(Integer, default=0)

    # Journal des transitions (JSONB en Postgres)
    notes_workflow: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Assignation
    conseiller_responsable: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relations
    client: Mapped["Client"] = relationship()
    commissions: Mapped[list["Commission"]] = relationship(back_populates="dossier")
