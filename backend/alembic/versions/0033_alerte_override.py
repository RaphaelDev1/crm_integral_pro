"""Levée d'alerte critique (override) — PLAN_IMPLEMENTATION_4_PHASES.md §2.1.

Une souscription IA Conseil ne peut être enregistrée si la recommandation
choisie porte une alerte 'critique' non levée (voir
backend/services/alertes_engine.py). Lever une alerte crée une ligne ici,
avec justification obligatoire — trace d'audit, jamais de suppression.

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        "alerte_override",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("session_trame.id"), nullable=True),
        sa.Column("offre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offre.id"), nullable=True),
        sa.Column("regle_nom", sa.Text(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("conseiller_id", sa.Integer(), sa.ForeignKey("utilisateurs.id"), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_alerte_override_session_offre", "alerte_override", ["session_id", "offre_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_alerte_override_session_offre", table_name="alerte_override")
    op.drop_table("alerte_override")
