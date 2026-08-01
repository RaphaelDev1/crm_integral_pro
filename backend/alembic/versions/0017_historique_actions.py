"""Ajoute la table `historique_actions` — journal d'audit générique, insert-only,
miroir de src/db.py::historique_actions. Nécessaire à la fois pour le scoring
prospect (date de dernier contact, cf. backend/services/prospect_scoring.py)
et pour la conversion prospect → client (cf. backend/services/prospect_conversion.py).

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historique_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entite_type", sa.String(), nullable=False),
        sa.Column("entite_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("details", sa.String(), nullable=True),
        sa.Column("auteur", sa.String(), nullable=True),
        sa.Column("date_action", sa.String(), nullable=True),
    )
    op.create_index("ix_historique_actions_entite", "historique_actions", ["entite_type", "entite_id"])


def downgrade() -> None:
    op.drop_index("ix_historique_actions_entite", table_name="historique_actions")
    op.drop_table("historique_actions")
