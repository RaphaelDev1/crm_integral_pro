"""La landing publique /economiser ne demandait qu'un seul "opérateur actuel",
partagé entre mobile et box — un même prospect peut pourtant avoir deux
opérateurs différents pour ces deux services. On ajoute `operateur_box`,
distinct de `operateur_actuel` (qui reste dédié au mobile, cohérent avec le
reste de l'app).

Revision ID: 0044
Revises: 0043
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("operateur_box", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("prospects", "operateur_box")
