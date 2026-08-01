"""Ajoute les tables de veille prix — `sources_veille`, `veille_historique_prix`,
`veille_alertes` (miroir de src/db.py, voir backend/models/veille.py). Couche
de données uniquement : la logique de scraping/validation reste dans
src/veille_prix_engine.py.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources_veille",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("univers", sa.String(), nullable=True),
        sa.Column("categorie", sa.String(), nullable=True),
        sa.Column("fournisseur", sa.String(), nullable=True),
        sa.Column("nom_offre", sa.String(), nullable=True),
        sa.Column("offre_id", sa.Integer(), sa.ForeignKey("offres.id"), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("selecteur_prix", sa.String(), nullable=True),
        sa.Column("actif", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("dernier_prix", sa.Float(), nullable=True),
        sa.Column("date_derniere_verif", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
    )

    op.create_table(
        "veille_historique_prix",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources_veille.id"), nullable=True),
        sa.Column("prix", sa.Float(), nullable=True),
        sa.Column("date_releve", sa.String(), nullable=True),
    )
    op.create_index("ix_veille_historique_prix_source_id", "veille_historique_prix", ["source_id"])

    op.create_table(
        "veille_alertes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources_veille.id"), nullable=True),
        sa.Column("ancien_prix", sa.Float(), nullable=True),
        sa.Column("nouveau_prix", sa.Float(), nullable=True),
        sa.Column("statut", sa.String(), server_default="en_attente", nullable=False),
        sa.Column("date_detection", sa.String(), nullable=True),
        sa.Column("date_traitement", sa.String(), nullable=True),
    )
    op.create_index("ix_veille_alertes_source_id", "veille_alertes", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_veille_alertes_source_id", table_name="veille_alertes")
    op.drop_table("veille_alertes")
    op.drop_index("ix_veille_historique_prix_source_id", table_name="veille_historique_prix")
    op.drop_table("veille_historique_prix")
    op.drop_table("sources_veille")
