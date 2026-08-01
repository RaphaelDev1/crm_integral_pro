"""Ajoute la table `parametres` — réglages clé/valeur génériques (nom société,
taux d'honoraires par défaut, SMTP, Telegram, clé API Anthropic...), miroir de
src/db.py::parametres.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parametres",
        sa.Column("cle", sa.String(), primary_key=True),
        sa.Column("valeur", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("parametres")
