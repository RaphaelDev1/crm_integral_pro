"""Ajoute les tables `mandats` (signature électronique Yousign) et
`documents` (validation KYC) — voir backend/models/mandat.py et
backend/models/document.py.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mandats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("statut", sa.String(), server_default="brouillon", nullable=False),
        sa.Column("pdf_url", sa.String(), nullable=True),
        sa.Column("pdf_signe_url", sa.String(), nullable=True),
        sa.Column("yousign_signature_request_id", sa.String(), nullable=True),
        sa.Column("yousign_document_id", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("date_envoi", sa.String(), nullable=True),
        sa.Column("date_signature", sa.String(), nullable=True),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("type_document", sa.String(), nullable=True),
        sa.Column("url_stockage", sa.String(), nullable=False),
        sa.Column("statut_kyc", sa.String(), server_default="en_attente", nullable=False),
        sa.Column("motif_rejet", sa.String(), nullable=True),
        sa.Column("date_upload", sa.String(), nullable=True),
        sa.Column("date_validation", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("mandats")
