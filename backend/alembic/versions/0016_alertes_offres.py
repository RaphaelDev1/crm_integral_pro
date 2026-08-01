"""Ajoute la table `alertes_offres` — détection automatique d'une offre du
catalogue moins chère que le contrat actif d'un client (voir
backend/services/alertes_offres_engine.py), sur le modèle exact de
`veille_alertes` (backend/models/veille.py).

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alertes_offres",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("contrat_id", sa.Integer(), sa.ForeignKey("contrats.id"), nullable=True),
        sa.Column("offre_id", sa.Integer(), sa.ForeignKey("offres.id"), nullable=True),
        sa.Column("cout_actuel", sa.Float(), nullable=True),
        sa.Column("cout_propose", sa.Float(), nullable=True),
        sa.Column("economie_mensuelle", sa.Float(), nullable=True),
        sa.Column("economie_annuelle", sa.Float(), nullable=True),
        sa.Column("statut", sa.String(), nullable=False, server_default="en_attente"),
        sa.Column("date_detection", sa.String(), nullable=True),
        sa.Column("date_traitement", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("alertes_offres")
