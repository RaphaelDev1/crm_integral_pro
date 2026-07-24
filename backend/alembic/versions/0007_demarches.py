"""Ajoute la table `demarches` — génération/envoi des documents de démarche
(résiliation, portabilité, changement de fournisseur, mandat, souscription)
rattachés à un dossier, envoyés par un canal tracé (LRE AR24 par défaut).

Refus de génération si le mandat de représentation du client (`mandats.statut`)
n'est pas "signe" — règle légale imposée côté service
(backend/services/demarches_engine.py), non modélisable en contrainte SQL
portable.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demarches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("mandat_id", sa.Integer(), sa.ForeignKey("mandats.id"), nullable=True),
        sa.Column("univers", sa.String(), nullable=False),
        sa.Column("type_demarche", sa.String(), nullable=False),
        sa.Column("statut", sa.String(), server_default="a_generer", nullable=False),
        sa.Column("canal", sa.String(), server_default="lre"),
        sa.Column("document_url", sa.String(), nullable=True),
        sa.Column("preuve_envoi", sa.String(), nullable=True),
        sa.Column("preuve_url", sa.String(), nullable=True),
        sa.Column("donnees_requises", sa.JSON(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("date_generation", sa.String(), nullable=True),
        sa.Column("date_envoi", sa.String(), nullable=True),
        sa.Column("date_accuse", sa.String(), nullable=True),
    )
    op.create_index("ix_demarches_dossier_id", "demarches", ["dossier_id"])


def downgrade() -> None:
    op.drop_table("demarches")
