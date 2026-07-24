"""Ajoute `dossiers.date_derniere_transition` et
`dossiers.derniere_relance_envoyee_le` — nécessaires pour détecter la
stagnation d'un dossier (relance automatique) sans reparser `notes_workflow`
à chaque requête.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dossiers", sa.Column("date_derniere_transition", sa.String(), nullable=True))
    op.add_column("dossiers", sa.Column("derniere_relance_envoyee_le", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("dossiers", "derniere_relance_envoyee_le")
    op.drop_column("dossiers", "date_derniere_transition")
