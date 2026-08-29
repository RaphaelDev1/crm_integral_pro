"""Relances planifiées IA Conseil — PLAN_IMPLEMENTATION_4_PHASES.md §2.3.

Nouvelle table `evenement_planifie` (fin d'engagement J-60, bilan annuel,
NPS J+30, alerte de veille prix §2.2) exécutée par un worker Celery quotidien
(backend/services/evenement_planifie_engine.py).

Réutilisation de la table `notifications` existante plutôt qu'un système
parallèle (§2.3/§Décisions) : `dossier_id` devient nullable et un champ
`lien` est ajouté pour pointer vers une route ia-conseil quand la
notification ne concerne pas un dossier CRM.

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        "evenement_planifie",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client.id"), nullable=True),
        sa.Column("conseiller_id", sa.Integer(), sa.ForeignKey("utilisateurs.id"), nullable=True),
        # type: 'fin_engagement_J-60' | 'bilan_annuel' | 'nps_j30' | 'veille_alerte'
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("date_prevue", sa.Date(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("execute", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("execute_le", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_evenement_planifie_date_prevue",
        "evenement_planifie",
        ["date_prevue"],
        postgresql_where=sa.text("NOT execute"),
    )

    op.alter_column("notifications", "dossier_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("notifications", sa.Column("lien", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("notifications", "lien")
    op.alter_column("notifications", "dossier_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("idx_evenement_planifie_date_prevue", table_name="evenement_planifie")
    op.drop_table("evenement_planifie")
