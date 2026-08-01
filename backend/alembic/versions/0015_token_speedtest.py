"""Ajoute `peut_transmettre_speedtest` sur `tokens_publics` — autorise le
client à soumettre, depuis son portail, un résultat de test de débit
(LibreSpeed auto-hébergé) ou une capture d'écran/PDF de secours.

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tokens_publics",
        sa.Column("peut_transmettre_speedtest", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tokens_publics", "peut_transmettre_speedtest")
