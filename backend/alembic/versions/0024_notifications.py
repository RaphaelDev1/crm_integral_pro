"""Ajoute la table `notifications` — alerte in-app pour le conseiller quand le
client agit de son côté (upload de document, speedtest, signature de mandat)
ou quand un dossier change de statut, sans que le conseiller ne le sache tant
qu'il n'a pas rouvert le dossier. Distinct des notifications email/SMS envoyées
au client (backend/services/dossier_notifications.py).

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conseiller_username", sa.String(), nullable=False),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("lu", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("date_creation", sa.String(), nullable=True),
    )
    op.create_index("ix_notifications_conseiller_username", "notifications", ["conseiller_username"])


def downgrade() -> None:
    op.drop_index("ix_notifications_conseiller_username", table_name="notifications")
    op.drop_table("notifications")
