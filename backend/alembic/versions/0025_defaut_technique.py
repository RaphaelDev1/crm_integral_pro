"""Ajoute `defaut_technique` sur `prospects` et `clients` — signalement d'un
défaut technique potentiel constaté sur le réseau actuel (Faible/Moyen/Critique),
voir frontend-conseiller/lib/diagnosticConstants.ts::NIVEAUX_DEFAUT_TECHNIQUE.

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("defaut_technique", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("defaut_technique", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "defaut_technique")
    op.drop_column("prospects", "defaut_technique")
