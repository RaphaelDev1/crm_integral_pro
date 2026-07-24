"""Ajoute la table `mandats_honoraires` — mandat de rémunération du cabinet
(taux/montant d'honoraires) rattaché à un dossier, distinct du mandat de
représentation Yousign (`mandats`). Permet d'unifier sur la fiche client
l'affichage du statut des deux mandats aux côtés du stepper du dossier.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mandats_honoraires",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("montant", sa.Float(), server_default="0.0"),
        sa.Column("taux", sa.Float(), server_default="0.0"),
        sa.Column("statut", sa.String(), server_default="brouillon", nullable=False),
        sa.Column("signataire", sa.String(), nullable=True),
        sa.Column("date_signature", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_mandats_honoraires_dossier_id", "mandats_honoraires", ["dossier_id"], unique=True
    )


def downgrade() -> None:
    op.drop_table("mandats_honoraires")
