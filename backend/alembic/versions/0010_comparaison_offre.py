"""Ajoute la table `comparaisons_offres` — persistance des comparaisons/
recommandations d'offres calculées pour un prospect ou un client (la logique
de calcul reste dans src/offres_engine.py, cette table n'en stocke que le
résultat, avec un instantané JSON des offres comparées pour ne pas dépendre
des prix actuels du catalogue qui peuvent évoluer via la veille).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comparaisons_offres",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prospect_id", sa.Integer(), sa.ForeignKey("prospects.id"), nullable=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("univers", sa.String(), nullable=True),
        sa.Column("categorie", sa.String(), nullable=True),
        sa.Column("cout_actuel_mensuel", sa.Float(), nullable=True),
        sa.Column("offre_recommandee_id", sa.Integer(), sa.ForeignKey("offres.id"), nullable=True),
        sa.Column("offres_comparees", sa.JSON(), nullable=True),
        sa.Column("economie_mensuelle_estimee", sa.Float(), nullable=True),
        sa.Column("economie_annuelle_estimee", sa.Float(), nullable=True),
        sa.Column("contexte", sa.String(), nullable=True),
        sa.Column("date_comparaison", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
    )
    op.create_index("ix_comparaisons_offres_prospect_id", "comparaisons_offres", ["prospect_id"])
    op.create_index("ix_comparaisons_offres_client_id", "comparaisons_offres", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_comparaisons_offres_client_id", table_name="comparaisons_offres")
    op.drop_index("ix_comparaisons_offres_prospect_id", table_name="comparaisons_offres")
    op.drop_table("comparaisons_offres")
