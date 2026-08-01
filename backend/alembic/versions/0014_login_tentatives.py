"""Ajoute la table `login_tentatives` — audit + rate limiting du login backend
(verrouillage après 5 échecs / 15 min), porté depuis src/auth.py qui n'avait
d'équivalent que côté SQLite. Voir backend/core/security.py::compte_verrouille.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_tentatives",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("identifiant", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("succes", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("date_tentative", sa.String(), nullable=True),
    )
    op.create_index("ix_login_tentatives_identifiant", "login_tentatives", ["identifiant"])


def downgrade() -> None:
    op.drop_index("ix_login_tentatives_identifiant", table_name="login_tentatives")
    op.drop_table("login_tentatives")
