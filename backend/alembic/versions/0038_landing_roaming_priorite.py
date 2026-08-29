"""Ajoute `roaming_europe` et `sensibilite_prix` sur `prospects` et `clients` —
mêmes libellés/valeurs que les questions `roaming_ue`/`sensibilite_prix` de la
trame mobile (backend/scripts/seed_ia_conseil.py), désormais aussi posées sur
la landing publique /economiser pour que le conseiller n'ait plus à les
redemander au téléphone (voir backend/routers/leads_public.py).

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("roaming_europe", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("sensibilite_prix", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("roaming_europe", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("sensibilite_prix", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "sensibilite_prix")
    op.drop_column("clients", "roaming_europe")
    op.drop_column("prospects", "sensibilite_prix")
    op.drop_column("prospects", "roaming_europe")
