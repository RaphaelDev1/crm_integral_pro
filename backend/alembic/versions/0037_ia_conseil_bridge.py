"""Pont d'identité CRM <-> IA Conseil — PLAN "Fusionner la trame IA Conseil
dans Nouveau diagnostic".

Ajoute `ia_conseil_client_id` (nullable, FK `client.id`) sur `prospects` et
`clients` : permet de rattacher une fiche CRM au `ClientConseil` créé/réutilisé
pour lancer des sessions de trame IA Conseil depuis le diagnostic (voir
backend/services/ia_conseil_bridge.py).

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prospects",
        sa.Column("ia_conseil_client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client.id"), nullable=True),
    )
    op.add_column(
        "clients",
        sa.Column("ia_conseil_client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clients", "ia_conseil_client_id")
    op.drop_column("prospects", "ia_conseil_client_id")
