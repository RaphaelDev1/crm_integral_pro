"""Rapport hebdomadaire de l'agent de veille marché — PLAN_IMPLEMENTATION_4_PHASES.md §3.4.

Nouvelle table `rapport_veille_marche` : un agent Claude (outil serveur
web_search) scanne le web une fois par semaine par catégorie pour détecter
des offres pas encore au catalogue `offre`. N'écrit jamais directement dans
`offre` — chaque entrée détectée est revue par un admin avant intégration
(voir routers/ia_conseil_catalogue.py).

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        "rapport_veille_marche",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("categorie_slug", sa.Text(), sa.ForeignKey("categorie.slug"), nullable=True),
        sa.Column("semaine_debut", sa.Date(), nullable=False),
        sa.Column("offres_detectees", postgresql.JSONB(), server_default="[]", nullable=False),
        # statut : en_attente | traite
        sa.Column("statut", sa.Text(), server_default="en_attente", nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_rapport_veille_marche_statut", "rapport_veille_marche", ["statut"],
        postgresql_where=sa.text("statut = 'en_attente'"),
    )


def downgrade() -> None:
    op.drop_index("idx_rapport_veille_marche_statut", table_name="rapport_veille_marche")
    op.drop_table("rapport_veille_marche")
