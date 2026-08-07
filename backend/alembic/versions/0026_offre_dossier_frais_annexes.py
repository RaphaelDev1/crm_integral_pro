"""Ajoute les frais annexes (SIM, résiliation, portabilité) sur `offres`, et
leur snapshot `frais_annexes_cible` sur `dossiers` — capturé au moment où le
conseiller choisit l'offre visée (comme `economie_annuelle_estimee`), pour
afficher l'économie nette de la 1ère année sur la fiche dossier.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offres", sa.Column("frais_sim", sa.Float(), nullable=True))
    op.add_column("offres", sa.Column("frais_resiliation", sa.Float(), nullable=True))
    op.add_column("offres", sa.Column("frais_portabilite", sa.Float(), nullable=True))
    op.add_column(
        "dossiers",
        sa.Column("frais_annexes_cible", sa.Float(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("dossiers", "frais_annexes_cible")
    op.drop_column("offres", "frais_portabilite")
    op.drop_column("offres", "frais_resiliation")
    op.drop_column("offres", "frais_sim")
