"""Ajoute la table `documents_prospect` — fichiers (facture, speedtest) transmis
par un prospect via son lien personnel, miroir de src/db.py::documents_prospect
mais stockage S3 (cle_stockage) au lieu du BLOB inline SQLite, cohérent avec
`documents`/`mandats`. Table dédiée, indépendante de `documents` (KYC client).

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents_prospect",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prospect_id", sa.Integer(), sa.ForeignKey("prospects.id"), nullable=False),
        sa.Column("type_document", sa.String(), nullable=True),
        sa.Column("nom_fichier", sa.String(), nullable=True),
        sa.Column("cle_stockage", sa.String(), nullable=False),
        sa.Column("mime", sa.String(), nullable=True),
        sa.Column("date_upload", sa.String(), nullable=True),
    )
    op.create_index("ix_documents_prospect_prospect_id", "documents_prospect", ["prospect_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_prospect_prospect_id", table_name="documents_prospect")
    op.drop_table("documents_prospect")
