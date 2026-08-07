"""Ajoute `conseiller_id` sur `clients` — le conseiller propriétaire de la
fiche (celui qui a converti le prospect, ou qui a créé le client directement).
Seul lui (ou un Admin) peut voir/modifier la fiche ensuite — voir
backend/routers/clients.py et backend/services/prospect_conversion.py.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("conseiller_id", sa.Integer(), sa.ForeignKey("utilisateurs.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clients", "conseiller_id")
