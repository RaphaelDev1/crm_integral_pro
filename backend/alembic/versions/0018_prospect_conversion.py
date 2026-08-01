"""Ajoute `client_id` (nullable) et `converti_at` sur `prospects` — support de la
conversion prospect → client (cf. backend/services/prospect_conversion.py).
`client_id` joue un double rôle : avant conversion, il pointe vers le client
« miroir » créé au premier besoin (dossier ou token de documents, cf.
src/api_client.py::_backend_client_id_pour) ; à la conversion, il devient le
client définitif (réutilisé, pas recréé).

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True))
    op.add_column("prospects", sa.Column("converti_at", sa.String(), nullable=True))
    op.create_index("ix_prospects_client_id", "prospects", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_prospects_client_id", table_name="prospects")
    op.drop_column("prospects", "converti_at")
    op.drop_column("prospects", "client_id")
