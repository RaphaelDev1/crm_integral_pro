"""Ajoute `raison_sociale` et `effectif` sur `prospects` et `clients` — champs
collectés à l'étape Identité du diagnostic uniquement quand type_client ==
"Professionnel" (voir EtapeIdentite.tsx). Voir aussi
prospect_conversion.CHAMPS_PROSPECT_VERS_CLIENT.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("raison_sociale", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("effectif", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("raison_sociale", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("effectif", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "effectif")
    op.drop_column("clients", "raison_sociale")
    op.drop_column("prospects", "effectif")
    op.drop_column("prospects", "raison_sociale")
