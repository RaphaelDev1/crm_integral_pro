"""Ajoute `telephone` sur `utilisateurs` — permet d'afficher le contact du
conseiller (nom + téléphone) sur le PDF de restitution remis au prospect/client,
voir backend/services/restitution_pdf_engine.py.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("utilisateurs", sa.Column("telephone", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("utilisateurs", "telephone")
