"""Ajoute la table `factures_analysees` — persiste le résultat de l'analyse
LLM d'une facture télécom/énergie (backend/services/facture_analyzer.py),
liée à un client (et optionnellement à un dossier), pour le briefing
conseiller avant appel (GET /clients/{id}/briefing).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "factures_analysees",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers.id"), nullable=True),
        sa.Column("operateur", sa.String(), nullable=True),
        sa.Column("prix_ht", sa.Float(), server_default="0.0"),
        sa.Column("prix_ttc", sa.Float(), server_default="0.0"),
        sa.Column("data_conso_go", sa.Float(), server_default="0.0"),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("engagement_mois", sa.Integer(), server_default="0"),
        sa.Column("date_fin_engagement", sa.String(), nullable=True),
        sa.Column("iban_prelevement", sa.String(), nullable=True),
        sa.Column("date_analyse", sa.String(), nullable=True),
        sa.Column("analyse_par", sa.String(), nullable=True),
    )
    op.create_index("ix_factures_analysees_client_id", "factures_analysees", ["client_id"])


def downgrade() -> None:
    op.drop_table("factures_analysees")
