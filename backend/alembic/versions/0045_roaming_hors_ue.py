"""Ajoute `roaming_hors_ue` sur `prospects` et `clients` — même principe que
`roaming_europe` (migration 0038_landing_roaming_priorite) : reprend la
question `roaming_hors_ue` de la trame mobile (backend/scripts/seed_ia_conseil.py),
désormais aussi posée sur la landing publique /economiser ("Voyagez-vous dans
le monde ?").

Revision ID: 0045
Revises: 0044
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("roaming_hors_ue", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("roaming_hors_ue", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "roaming_hors_ue")
    op.drop_column("prospects", "roaming_hors_ue")
