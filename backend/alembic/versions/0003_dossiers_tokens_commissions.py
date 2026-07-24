"""Ajoute les tables `dossiers` (workflow souscription), `tokens_publics`
(lien unique client sans login), `commissions` (tracking rémunération) et
`abonnements` (Gestionnaire perso récurrent).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # DOSSIERS — workflow souscription
    # -----------------------------------------------------------------
    op.create_table(
        "dossiers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("contrat_id", sa.Integer(), sa.ForeignKey("contrats.id"), nullable=True),
        sa.Column("offre_cible_id", sa.Integer(), sa.ForeignKey("offres.id"), nullable=True),
        sa.Column("univers", sa.String(), nullable=False),
        sa.Column("fournisseur_cible", sa.String(), nullable=True),
        sa.Column("economie_annuelle_estimee", sa.Float(), server_default="0.0"),
        sa.Column("statut", sa.String(), server_default="initie", nullable=False),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("date_soumission", sa.String(), nullable=True),
        sa.Column("date_activation_prevue", sa.String(), nullable=True),
        sa.Column("date_activation_reelle", sa.String(), nullable=True),
        sa.Column("reference_fournisseur", sa.String(), nullable=True),
        sa.Column("commission_attendue", sa.Float(), server_default="0.0"),
        sa.Column("commission_recue", sa.Float(), server_default="0.0"),
        sa.Column("part_client_totale", sa.Float(), server_default="0.0"),
        sa.Column("duree_prelevement_mois", sa.Integer(), server_default="0"),
        sa.Column("notes_workflow", sa.JSON(), nullable=True),
        sa.Column("conseiller_responsable", sa.String(), nullable=True),
    )
    op.create_index("ix_dossiers_client_id", "dossiers", ["client_id"])
    op.create_index("ix_dossiers_statut", "dossiers", ["statut"])

    # -----------------------------------------------------------------
    # TOKENS PUBLICS — lien unique client (Option A : pas de login)
    # -----------------------------------------------------------------
    op.create_table(
        "tokens_publics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(), unique=True, nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers.id"), nullable=True),
        sa.Column("peut_uploader_docs", sa.Boolean(), server_default="true"),
        sa.Column("peut_signer_mandat", sa.Boolean(), server_default="true"),
        sa.Column("peut_voir_suivi", sa.Boolean(), server_default="true"),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("date_expiration", sa.String(), nullable=True),
        sa.Column("date_premiere_utilisation", sa.String(), nullable=True),
        sa.Column("date_derniere_utilisation", sa.String(), nullable=True),
        sa.Column("ip_premiere_utilisation", sa.String(), nullable=True),
        sa.Column("nb_utilisations", sa.Integer(), server_default="0"),
        sa.Column("revoque", sa.Boolean(), server_default="false"),
        sa.Column("motif_revocation", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
    )
    op.create_index("ix_tokens_publics_token", "tokens_publics", ["token"], unique=True)

    # -----------------------------------------------------------------
    # COMMISSIONS
    # -----------------------------------------------------------------
    op.create_table(
        "commissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("montant", sa.Float(), nullable=False),
        sa.Column("statut", sa.String(), server_default="attendue"),
        sa.Column("date_prevue", sa.String(), nullable=True),
        sa.Column("date_recue", sa.String(), nullable=True),
        sa.Column("reference_paiement", sa.String(), nullable=True),
        sa.Column("stripe_payment_id", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
    )
    op.create_index("ix_commissions_dossier_id", "commissions", ["dossier_id"])
    op.create_index("ix_commissions_statut", "commissions", ["statut"])

    # -----------------------------------------------------------------
    # ABONNEMENTS — Gestionnaire perso récurrent
    # -----------------------------------------------------------------
    op.create_table(
        "abonnements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("formule", sa.String(), nullable=False),
        sa.Column("prix_mensuel", sa.Float(), nullable=False),
        sa.Column("date_debut", sa.String(), nullable=True),
        sa.Column("date_fin", sa.String(), nullable=True),
        sa.Column("statut", sa.String(), server_default="actif"),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
    )
    op.create_index("ix_abonnements_client_id", "abonnements", ["client_id"])
    op.create_index("ix_abonnements_statut", "abonnements", ["statut"])


def downgrade() -> None:
    op.drop_table("abonnements")
    op.drop_table("commissions")
    op.drop_table("tokens_publics")
    op.drop_table("dossiers")
