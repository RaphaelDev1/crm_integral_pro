"""Analyse de facture automatique pour les prospects + demande auto de facture.

Ajoute :
  - `factures_analysees.prospect_id` : permet de lier une analyse à un
    prospect (pas encore client) — `client_id` devient nullable en
    conséquence (une analyse est liée à l'un OU l'autre).
  - `factures_analysees.type_couverture` / `bonus_malus` : champs assurance
    (tiers / tous risques, coefficient bonus-malus) extraits par
    backend/services/facture_analyzer.py quand le document est une facture
    d'assurance auto plutôt que télécom/énergie.
  - `prospects.demande_facture_envoyee` : idempotence de la relance
    automatique SMS/email demandant la facture au prospect (voir
    backend/workers/tasks.py::demander_facture_prospects), même principe que
    `email_j1_envoye`.

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("demande_facture_envoyee", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.alter_column("factures_analysees", "client_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("factures_analysees", sa.Column("prospect_id", sa.Integer(), sa.ForeignKey("prospects.id"), nullable=True))
    op.add_column("factures_analysees", sa.Column("type_couverture", sa.String(), nullable=True))
    op.add_column("factures_analysees", sa.Column("bonus_malus", sa.String(), nullable=True))
    op.create_index("ix_factures_analysees_prospect_id", "factures_analysees", ["prospect_id"])


def downgrade() -> None:
    op.drop_index("ix_factures_analysees_prospect_id", table_name="factures_analysees")
    op.drop_column("factures_analysees", "bonus_malus")
    op.drop_column("factures_analysees", "type_couverture")
    op.drop_column("factures_analysees", "prospect_id")
    op.alter_column("factures_analysees", "client_id", existing_type=sa.Integer(), nullable=False)

    op.drop_column("prospects", "demande_facture_envoyee")
